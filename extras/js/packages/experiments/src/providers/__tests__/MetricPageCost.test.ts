import { beforeAll, describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import { MetricBucketStore, type ChartSubscription } from '@/metric-buckets/MetricBucketStore'
import type { MetricBucketsRequest } from '@/metric-buckets/types'
import { revision3Database, type MetricPoint } from './helpers/metricDatabases'
import { memoryTransport } from './helpers/snapshotSources'

const PAGE_KEYS = Array.from({ length: 12 }, (_, index) => `train/metric_${index}`)
const STEPS = 20_000

function pagePoints(): MetricPoint[] {
  return PAGE_KEYS.flatMap((key, index) =>
    Array.from({ length: STEPS }, (_, step) => ({ key, step, value: Math.cos(step / 50 + index) })),
  )
}

/** Two revision-3 experiments read by range, each with the page's twelve metrics. */
async function rangeProvider(db: Uint8Array) {
  const urls = ['https://bucket.test/a.db', 'https://bucket.test/b.db']
  const { transport, requests } = memoryTransport(Object.fromEntries(urls.map((url) => [url, db])))
  const provider = new ExperimentSnapshotDatabaseProvider({ transport })
  await provider.init({
    modelsInfo: urls.map((url, index) => ({
      modelId: index ? 'b' : 'a',
      source: { kind: 'range' as const, url, offset: 0, size: db.length },
    })),
  })
  const bucketCalls: { request: MetricBucketsRequest; signal: AbortSignal | undefined }[] = []
  let gate: Promise<void> = Promise.resolve()
  const source = {
    getExperimentStatuses: () => provider.getExperimentStatuses(),
    getMetricCatalogs: provider.getMetricCatalogs.bind(provider),
    getMetricBuckets: async (request: MetricBucketsRequest, signal?: AbortSignal) => {
      bucketCalls.push({ request, signal })
      await gate
      return provider.getMetricBuckets(request)
    },
  }
  /** Holds bucket reads until the returned function is called. */
  const hold = () => {
    let release = () => {}
    gate = new Promise<void>((resolve) => (release = resolve))
    return release
  }
  return { source, requests, bucketCalls, hold }
}

const settle = async () => {
  for (let round = 0; round < 5; round++) await new Promise((resolve) => setTimeout(resolve, 5))
}

describe('a page of twelve charts over a revision-3 range snapshot', () => {
  let db: Uint8Array

  // Building 240k points takes seconds when the whole suite runs in parallel.
  beforeAll(async () => {
    db = await revision3Database(pagePoints())
  }, 60_000)

  it('costs one query per experiment, and a chart closed mid-fetch cancels no other', async () => {
    const { source, requests, bucketCalls, hold } = await rangeProvider(db)
    const store = new MetricBucketStore(source, { debounceMs: 5 })
    await store.loadCatalogs()
    const before = requests.length
    const release = hold()
    const charts: ChartSubscription[] = PAGE_KEYS.map((key) => {
      const chart = store.subscribe(() => {})
      chart.request({ modelIds: ['a', 'b'], keys: [key], bucketBudget: 400 })
      return chart
    })
    await vi.waitFor(() => expect(bucketCalls).toHaveLength(2))
    charts[3]?.close()
    expect(bucketCalls.every((call) => call.signal?.aborted === false)).toBe(true)
    release()
    await vi.waitFor(
      () =>
        expect(charts.filter((_, index) => index !== 3).some((c) => c.state.loading)).toBe(false),
      { timeout: 10_000 },
    )
    await settle()

    expect(bucketCalls.map(({ request }) => [request.modelIds, request.keys.length])).toEqual([
      [['a'], 12],
      [['b'], 12],
    ])
    for (const [index, chart] of charts.entries()) {
      if (index === 3) continue
      expect(chart.state.loading).toBe(false)
      expect(chart.state.errors).toEqual([])
      expect(chart.state.series.map((series) => [series.modelId, series.final])).toEqual([
        ['a', true],
        ['b', true],
      ])
    }
    const page = requests.slice(before)
    expect(page.length).toBeGreaterThan(0)
    store.dispose()
  })
})
