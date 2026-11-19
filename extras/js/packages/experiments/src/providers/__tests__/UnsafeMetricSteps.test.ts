import { describe, expect, it } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import { ExperimentSnapshotApiProvider } from '../ExperimentSnapshotApiProvider'
import type {
  ApiServiceInterface,
  MetricBucketsWire,
  MetricCatalogWire,
} from '../ExperimentSnapshotApiProvider.interface'
import {
  MetricBucketStore,
  type ChartState,
  type MetricBucketSource,
} from '@/metric-buckets/MetricBucketStore'
import {
  rawBuffer,
  revision2Database,
  revision3Database,
  type MetricPoint,
} from './helpers/metricDatabases'

// Steps logged as time.time_ns() are about 1.7e18; int64 steps beyond 2^53 arrive rounded.
const BIG_STEP = 2 ** 60
const POINTS: MetricPoint[] = [
  ...Array.from({ length: 1000 }, (_, step) => ({ key: 'loss', step, value: step })),
  { key: 'loss', step: BIG_STEP, value: 1 },
  ...Array.from({ length: 10 }, (_, index) => ({
    key: 'time_ns',
    step: 1.7e18 + index * 1e9,
    value: index,
  })),
]
const KEYS = ['loss', 'time_ns']

async function chartOf(source: MetricBucketSource, modelIds: string[]) {
  const store = new MetricBucketStore(source, { debounceMs: 0 })
  const settled = new Promise<ChartState>((resolve) => {
    const chart = store.subscribe((state) => {
      if (state.request && !state.loading) resolve(state)
    })
    chart.request({ modelIds, keys: KEYS, bucketBudget: 1000 })
  })
  const state = await settled
  const { statuses } = await store.loadCatalogs()
  store.dispose()
  return { state, statuses }
}

const pointsOf = (state: ChartState, modelId: string, key: string) =>
  state.series
    .filter((series) => series.modelId === modelId && series.key === key)
    .flatMap((series) => series.buckets)
    .reduce((total, bucket) => total + bucket.count, 0)

describe('metric steps beyond 2^53', () => {
  it('are drawn up to 2^53 from revision 2 and 3 databases, and flag the experiment', async () => {
    const provider = new ExperimentSnapshotDatabaseProvider()
    const databases = [
      ['rev2', await revision2Database(POINTS)],
      ['rev3', await revision3Database(POINTS)],
    ] as const
    await provider.init({
      modelsInfo: databases.map(([modelId, db]) => ({
        modelId,
        source: { kind: 'raw' as const, buffer: rawBuffer(db) },
      })),
    })

    const catalogs = await provider.getMetricCatalogs()
    for (const result of catalogs) {
      expect(result.ok && result.value.metrics.find((entry) => entry.key === 'loss')).toMatchObject(
        { first_step: 0, last_step: BIG_STEP },
      )
    }
    const { state, statuses } = await chartOf(provider, ['rev2', 'rev3'])

    expect(state.errors).toEqual([])
    for (const modelId of ['rev2', 'rev3']) {
      expect(pointsOf(state, modelId, 'loss')).toBe(1000)
      expect(pointsOf(state, modelId, 'time_ns')).toBe(0)
    }
    expect(statuses.map((status) => [status.modelId, status.unsafeMetricSteps])).toEqual([
      ['rev2', true],
      ['rev3', true],
    ])
  })

  it('leave out a step of exactly -2^53 alike from raw points and stored buckets', async () => {
    // -2^53 is a double, but outside +-(2^53 - 1): from level 1 on its bucket is the one
    // reads start at, so a stored bucket read whole would keep it.
    const low: MetricPoint[] = [
      ...Array.from({ length: 1000 }, (_, step) => ({ key: 'loss', step, value: step })),
      { key: 'loss', step: -(2 ** 53), value: 1e6 },
      { key: 'loss', step: -(2 ** 53) + 1, value: -5 },
    ]
    const provider = new ExperimentSnapshotDatabaseProvider()
    await provider.init({
      modelsInfo: [
        {
          modelId: 'rev2',
          source: { kind: 'raw', buffer: rawBuffer(await revision2Database(low)) },
        },
        {
          modelId: 'rev3',
          source: { kind: 'raw', buffer: rawBuffer(await revision3Database(low)) },
        },
      ],
    })

    for (const level of [0, 1, 2, 5, 13, 14, 20, 27]) {
      const [rev2, rev3] = await provider.getMetricBuckets({
        modelIds: ['rev2', 'rev3'],
        keys: ['loss'],
        level,
      })
      expect(rev2?.ok && rev3?.ok, `level ${level}`).toBe(true)
      if (!rev2?.ok || !rev3?.ok) continue
      expect(rev3.value.series, `level ${level}`).toEqual(rev2.value.series)
      const buckets = rev3.value.series[0]!.buckets
      expect(buckets.reduce((total, bucket) => total + bucket.count, 0)).toBe(1001)
      expect(buckets[0]!.first_step).toBe(-(2 ** 53) + 1)
      expect(Math.max(...buckets.map((bucket) => bucket.max ?? -Infinity))).toBe(999)
    }
    const { statuses } = await chartOf(provider, ['rev2', 'rev3'])
    expect(statuses.map((status) => [status.modelId, status.unsafeMetricSteps])).toEqual([
      ['rev2', true],
      ['rev3', true],
    ])
  })

  it('are drawn up to 2^53 from the API, whose JSON numbers arrive rounded', async () => {
    const catalog = JSON.parse(`{
      "revision": 3, "bucket_min_level": 3, "bucket_max_level": 12, "skipped_rows": 0,
      "metrics": [
        {"key": "loss", "first_step": 0, "last_step": 1152921504606846977,
         "count": 1001, "min": 0, "max": 999},
        {"key": "time_ns", "first_step": 1700000000000000001, "last_step": 1700000009000000001,
         "count": 10, "min": 0, "max": 9}
      ]
    }`) as MetricCatalogWire
    const buckets: MetricBucketsWire = {
      level: 22,
      series: [
        {
          key: 'loss',
          first_step: 0,
          last_step: catalog.metrics[0]!.last_step,
          buckets: [[0, 0, 999, 1000, 1000, 0, 999, 499_500]],
        },
      ],
    }
    const service: Partial<ApiServiceInterface> = {
      getExperimentMetricCatalog: async () => catalog,
      getExperimentMetricBuckets: async () => buckets,
    }
    const provider = new ExperimentSnapshotApiProvider(service as ApiServiceInterface)
    await provider.init({ artifacts: [{ id: 'e1', dynamicMetrics: [], staticParams: {} }] })

    const { state, statuses } = await chartOf(provider, ['e1'])

    expect(state.errors).toEqual([])
    expect(pointsOf(state, 'e1', 'loss')).toBe(1000)
    expect(statuses).toEqual([expect.objectContaining({ modelId: 'e1', unsafeMetricSteps: true })])
  })
})
