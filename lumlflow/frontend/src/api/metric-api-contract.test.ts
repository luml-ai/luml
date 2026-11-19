import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { ExperimentSnapshotApiProvider } from '@luml/experiments'
import { api } from './client'
import { apiService } from './api.service'
import pinnedCases from '../../../tests/fixtures/metric_api_contract.json'

// Pinned by lumlflow/tests/integration/server/test_metric_api_contract.py, which
// proves the real server gives exactly these answers to exactly these requests.
interface ContractCase {
  name: string
  experiment: string
  method: 'GET' | 'POST'
  endpoint: string
  request: Record<string, unknown> | null
  response: { status: number; body: unknown }
}

const cases = pinnedCases as ContractCase[]

function contractCase(name: string): ContractCase {
  const found = cases.find((candidate) => candidate.name === name)
  if (!found) throw new Error(`No contract case named ${name}`)
  return found
}

const sentBodies: unknown[] = []

const contractServer: AxiosAdapter = async (config: InternalAxiosRequestConfig) => {
  const body = config.data ? JSON.parse(config.data) : null
  sentBodies.push(body)
  const match = cases.find(
    (candidate) =>
      config.method?.toUpperCase() === candidate.method &&
      config.url === `/experiments/${candidate.experiment}/${candidate.endpoint}` &&
      JSON.stringify(body) === JSON.stringify(candidate.request),
  )
  if (!match) throw new Error(`Unexpected request ${config.method} ${config.url} ${config.data}`)
  const response = {
    data: match.response.body,
    status: match.response.status,
    statusText: String(match.response.status),
    headers: {},
    config,
  }
  if (response.status >= 400) {
    throw new AxiosError('Request failed', AxiosError.ERR_BAD_RESPONSE, config, null, response)
  }
  return response
}

async function provider(ids: string[]) {
  const instance = new ExperimentSnapshotApiProvider(apiService)
  await instance.init({
    artifacts: ids.map((id) => ({ id, dynamicMetrics: [], staticParams: {} })),
  })
  return instance
}

describe('metric catalog and bucket transport against the pinned server answers', () => {
  const realAdapter = api.defaults.adapter

  beforeEach(() => {
    sentBodies.length = 0
    api.defaults.adapter = contractServer
  })

  afterEach(() => {
    api.defaults.adapter = realAdapter
  })

  it('decodes the catalog, infinities included', async () => {
    const [catalog] = await (await provider(['main'])).getMetricCatalogs()

    expect(catalog).toMatchObject({ modelId: 'main', ok: true })
    const metrics = catalog?.ok ? catalog.value.metrics : []
    expect(metrics.map(({ key, min, max }) => [key, min, max])).toEqual([
      ['train/loss', -Infinity, Infinity],
      ['ünïcode/métric', 0.5, 1.5],
    ])
  })

  it('decodes a revision 2 catalog without count, min and max', async () => {
    const [catalog] = await (await provider(['legacy'])).getMetricCatalogs()

    expect(catalog).toEqual({
      modelId: 'legacy',
      ok: true,
      value: {
        revision: 2,
        bucket_min_level: null,
        bucket_max_level: null,
        skipped_rows: 0,
        metrics: [
          {
            key: 'train/loss',
            first_step: 0,
            last_step: 149,
            count: null,
            min: null,
            max: null,
            writes: null,
          },
        ],
      },
    })
  })

  it.each(['buckets over the whole range', 'buckets over a step range'])(
    'sends the pinned request and decodes the answer: %s',
    async (name) => {
      const pinned = contractCase(name)
      const request = pinned.request as {
        keys: string[]
        start_step: number | null
        end_step: number | null
        level: number
      }
      const instance = await provider(['main'])

      const [result] = await instance.getMetricBuckets({
        keys: request.keys,
        level: request.level,
        ...(request.start_step === null ? {} : { start_step: request.start_step }),
        ...(request.end_step === null ? {} : { end_step: request.end_step }),
      })

      expect(sentBodies).toEqual([request])
      expect(result?.ok).toBe(true)
      const series = result?.ok ? result.value.series : []
      const wire = (
        pinned.response.body as { series: { buckets: unknown[][]; skipped_rows: number }[] }
      ).series
      expect(series.map((entry) => entry.buckets.length)).toEqual(
        wire.map((entry) => entry.buckets.length),
      )
      expect(series.map((entry) => entry.skipped_rows)).toEqual(
        wire.map((entry) => entry.skipped_rows),
      )
      for (const entry of series) {
        for (const bucket of entry.buckets) {
          expect(typeof bucket.min === 'number' || bucket.min === null).toBe(true)
          expect(typeof bucket.max === 'number' || bucket.max === null).toBe(true)
          expect(bucket.sum === null || Number.isFinite(bucket.sum)).toBe(true)
        }
      }
    },
  )

  it('keeps the infinite range of a bucket and the empty series of a missing key', async () => {
    const [result] = await (
      await provider(['main'])
    ).getMetricBuckets({
      keys: ['train/loss', 'ünïcode/métric', 'missing', 'train/loss'],
      level: 3,
    })

    const series = result?.ok ? result.value.series : []
    expect(series.map((entry) => entry.key)).toEqual(['train/loss', 'ünïcode/métric', 'missing'])
    expect(series[0]?.buckets.at(-1)).toEqual({
      bucket: 3,
      first_step: 200,
      last_step: 202,
      count: 3,
      finite_count: 0,
      min: -Infinity,
      max: Infinity,
      sum: null,
    })
    expect(series[2]).toEqual({
      key: 'missing',
      first_step: null,
      last_step: null,
      buckets: [],
      skipped_rows: 0,
    })
  })

  it('carries the fractional steps a revision 2 store left out of its buckets', async () => {
    const pinned = contractCase('buckets of a revision 2 store')
    const [result] = await (
      await provider(['legacy'])
    ).getMetricBuckets({ keys: ['train/loss'], level: 6 })

    expect(sentBodies).toEqual([pinned.request])
    expect(result).toEqual({
      modelId: 'legacy',
      ok: true,
      value: {
        level: 6,
        series: [
          {
            key: 'train/loss',
            first_step: 0,
            last_step: 149,
            buckets: [
              {
                bucket: 0,
                first_step: 0,
                last_step: 149,
                count: 150,
                finite_count: 150,
                min: 0.51,
                max: 2.0,
                sum: 188.25,
              },
            ],
            skipped_rows: 1,
          },
        ],
      },
    })
  })

  it('maps the server error codes to the typed errors', async () => {
    const [invalid] = await (
      await provider(['main'])
    ).getMetricBuckets({
      keys: ['train/loss'],
      level: 32,
    })
    const future = await provider(['future'])
    const [catalog] = await future.getMetricCatalogs()
    const [buckets] = await future.getMetricBuckets({ keys: ['train/loss'], level: 0 })

    expect(invalid).toMatchObject({ ok: false, error: { code: 'invalid-level' } })
    expect(catalog).toMatchObject({ ok: false, error: { code: 'needs-newer-reader' } })
    expect(buckets).toMatchObject({ ok: false, error: { code: 'needs-newer-reader' } })
  })
})
