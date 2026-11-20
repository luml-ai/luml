import { describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotApiProvider } from '../ExperimentSnapshotApiProvider'
import { MetricBucketStore } from '@/metric-buckets/MetricBucketStore'
import type {
  ApiServiceInterface,
  MetricBucketsWire,
  MetricCatalogWire,
} from '../ExperimentSnapshotApiProvider.interface'

const catalogWire: MetricCatalogWire = {
  revision: 3,
  bucket_min_level: 3,
  bucket_max_level: 12,
  skipped_rows: 4,
  metrics: [
    {
      key: 'loss',
      first_step: 0,
      last_step: 99,
      count: 100,
      min: '-Infinity',
      max: 'Infinity',
      writes: 120,
    },
    { key: 'acc', first_step: -5, last_step: 5, count: 11, min: null, max: 0.5 },
  ],
}

const lossWire: MetricBucketsWire['series'][number] = {
  key: 'loss',
  first_step: 0,
  last_step: 99,
  buckets: [
    [0, 0, 99, 100, 98, '-Infinity', 'Infinity', 12.5],
    [1, 256, 256, 1, 0, null, null, null],
    [2, 512, 513, 2, 0, 1e308, 1.7e308, null],
  ],
  skipped_rows: 2,
}

const bucketsWire: MetricBucketsWire = {
  level: 4,
  series: [
    lossWire,
    { key: 'gone/x', first_step: null, last_step: null, buckets: [], skipped_rows: 0 },
  ],
}

async function provider(service: Partial<ApiServiceInterface>, ids = ['e1', 'e2']) {
  const instance = new ExperimentSnapshotApiProvider(service as ApiServiceInterface)
  await instance.init({
    artifacts: ids.map((id) => ({ id, dynamicMetrics: [], staticParams: {} })),
  })
  return instance
}

describe('ExperimentSnapshotApiProvider metric catalog and buckets', () => {
  it('makes one catalog request per experiment and decodes infinities and write counters', async () => {
    const getExperimentMetricCatalog = vi
      .fn()
      .mockResolvedValueOnce(catalogWire)
      .mockRejectedValueOnce(new Error('Request failed with status code 500'))
    const instance = await provider({ getExperimentMetricCatalog })

    const [first, second] = await instance.getMetricCatalogs()
    expect(getExperimentMetricCatalog.mock.calls.map((call) => call[0])).toEqual(['e1', 'e2'])
    expect(first).toEqual({
      modelId: 'e1',
      ok: true,
      value: {
        ...catalogWire,
        metrics: [
          {
            key: 'loss',
            first_step: 0,
            last_step: 99,
            count: 100,
            min: -Infinity,
            max: Infinity,
            writes: 120,
          },
          // A server that predates the write counter leaves it out.
          {
            key: 'acc',
            first_step: -5,
            last_step: 5,
            count: 11,
            min: null,
            max: 0.5,
            writes: null,
          },
        ],
      },
    })
    expect(second).toMatchObject({ modelId: 'e2', ok: false, error: { code: 'read-failed' } })
    expect(await instance.getExperimentStatuses()).toEqual([
      {
        modelId: 'e1',
        revision: 3,
        transport: 'api',
        transportFallback: null,
        unknownNewerRevision: false,
        skippedMetricRows: 4,
        error: null,
      },
      {
        modelId: 'e2',
        revision: null,
        transport: 'api',
        transportFallback: null,
        unknownNewerRevision: false,
        skippedMetricRows: null,
        error: { code: 'read-failed', message: 'Request failed with status code 500' },
      },
    ])
  })

  it('flags a catalog of a revision newer than the viewer knows', async () => {
    const instance = await provider(
      { getExperimentMetricCatalog: vi.fn().mockResolvedValue({ ...catalogWire, revision: 9 }) },
      ['e1'],
    )
    await instance.getMetricCatalogs()

    expect(await instance.getExperimentStatuses()).toEqual([
      expect.objectContaining({ revision: 9, unknownNewerRevision: true }),
    ])
  })

  it('refetches only the chosen experiments on a refresh', async () => {
    const getExperimentMetricCatalog = vi.fn().mockResolvedValue(catalogWire)
    const instance = await provider({ getExperimentMetricCatalog })

    const results = await instance.getMetricCatalogs({ modelIds: ['e2'], refresh: true })
    expect(results.map((result) => result.modelId)).toEqual(['e2'])
    expect(getExperimentMetricCatalog).toHaveBeenCalledExactlyOnceWith('e2', undefined)
  })

  it('posts every key of an experiment in one request and decodes bucket tuples', async () => {
    const getExperimentMetricBuckets = vi.fn().mockResolvedValue(bucketsWire)
    const instance = await provider({ getExperimentMetricBuckets })
    const signal = new AbortController().signal

    const results = await instance.getMetricBuckets(
      { modelIds: ['e2'], keys: ['loss', 'gone/x'], start_step: 10, level: 4 },
      signal,
    )
    expect(getExperimentMetricBuckets).toHaveBeenCalledExactlyOnceWith(
      'e2',
      { keys: ['loss', 'gone/x'], start_step: 10, end_step: null, level: 4 },
      signal,
    )
    expect(results).toEqual([
      {
        modelId: 'e2',
        ok: true,
        value: {
          level: 4,
          series: [
            {
              key: 'loss',
              first_step: 0,
              last_step: 99,
              buckets: [
                {
                  bucket: 0,
                  first_step: 0,
                  last_step: 99,
                  count: 100,
                  finite_count: 98,
                  min: -Infinity,
                  max: Infinity,
                  sum: 12.5,
                },
                {
                  bucket: 1,
                  first_step: 256,
                  last_step: 256,
                  count: 1,
                  finite_count: 0,
                  min: null,
                  max: null,
                  sum: null,
                },
                {
                  bucket: 2,
                  first_step: 512,
                  last_step: 513,
                  count: 2,
                  finite_count: 0,
                  min: 1e308,
                  max: 1.7e308,
                  sum: null,
                },
              ],
              skipped_rows: 2,
            },
            { key: 'gone/x', first_step: null, last_step: null, buckets: [], skipped_rows: 0 },
          ],
        },
      },
    ])
  })

  it('fails per experiment when the API predates the endpoints or sends a bad number', async () => {
    const bad: MetricBucketsWire = {
      level: 0,
      series: [{ ...lossWire, buckets: [[0, 0, 0, 1, 1, 'NaN' as unknown as number, 1, 1]] }],
    }
    const instance = await provider({ getExperimentMetricBuckets: vi.fn().mockResolvedValue(bad) })

    const [catalog] = await instance.getMetricCatalogs()
    expect(catalog).toMatchObject({ ok: false, error: { code: 'read-failed' } })
    const [buckets] = await instance.getMetricBuckets({ keys: ['loss'], level: 0 })
    expect(buckets).toMatchObject({ ok: false, error: { message: expect.stringMatching(/NaN/) } })
  })

  it('treats a string sum as a malformed answer, not as a value', async () => {
    const sum = 'Infinity' as unknown as number
    const bad: MetricBucketsWire = {
      level: 0,
      series: [{ ...lossWire, buckets: [[0, 0, 0, 1, 1, 1, 1, sum]] }],
    }
    const instance = await provider({ getExperimentMetricBuckets: vi.fn().mockResolvedValue(bad) })

    const [buckets] = await instance.getMetricBuckets({ keys: ['loss'], level: 0 })
    expect(buckets).toMatchObject({ ok: false, error: { message: expect.stringMatching(/sum/) } })
  })

  it('maps detail.code of 409 and 422 answers to the typed errors, the rest to read-failed', async () => {
    const httpError = (status: number, data: unknown) =>
      Object.assign(new Error(`Request failed with status code ${status}`), {
        response: { status, data },
      })
    const answers = [
      httpError(409, { detail: { code: 'needs-newer-reader', message: 'needs revision 4' } }),
      httpError(422, { detail: { code: 'too-many-buckets', message: 'over 20000' } }),
      httpError(422, { detail: { code: 'invalid-level', message: 'level 40' } }),
      httpError(422, { detail: [{ loc: ['body', 'level'], msg: 'not an int' }] }),
      httpError(409, { detail: { code: 'too-many-buckets', message: 'wrong status' } }),
      httpError(404, { detail: 'Experiment not found' }),
      httpError(500, 'Internal Server Error'),
      new Error('Network Error'),
    ]
    const getExperimentMetricBuckets = vi.fn()
    for (const answer of answers) getExperimentMetricBuckets.mockRejectedValueOnce(answer)
    const instance = await provider({ getExperimentMetricBuckets }, ['e1'])

    const errors = []
    for (let index = 0; index < answers.length; index++) {
      const [result] = await instance.getMetricBuckets({ keys: ['loss'], level: 0 })
      errors.push(result?.ok ? null : result?.error)
    }
    expect(errors).toEqual([
      { code: 'needs-newer-reader', message: 'needs revision 4' },
      { code: 'too-many-buckets', message: 'over 20000' },
      { code: 'invalid-level', message: 'level 40' },
      { code: 'read-failed', message: 'Request failed with status code 422' },
      { code: 'read-failed', message: 'Request failed with status code 409' },
      { code: 'read-failed', message: 'Request failed with status code 404' },
      { code: 'read-failed', message: 'Request failed with status code 500' },
      { code: 'read-failed', message: 'Network Error' },
    ])
  })

  it('maps a 409 catalog answer to needs-newer-reader in the status', async () => {
    const getExperimentMetricCatalog = vi.fn().mockRejectedValue(
      Object.assign(new Error('Request failed with status code 409'), {
        response: { status: 409, data: { detail: { code: 'needs-newer-reader', message: 'm' } } },
      }),
    )
    const instance = await provider({ getExperimentMetricCatalog }, ['e1'])

    await instance.getMetricCatalogs()
    expect(await instance.getExperimentStatuses()).toEqual([
      expect.objectContaining({ error: { code: 'needs-newer-reader', message: 'm' } }),
    ])
  })

  it('rejects the whole call when it is aborted', async () => {
    const controller = new AbortController()
    const getExperimentMetricBuckets = vi.fn(async () => {
      controller.abort()
      throw new DOMException('Aborted', 'AbortError')
    })
    const instance = await provider({ getExperimentMetricBuckets })

    await expect(
      instance.getMetricBuckets({ keys: ['loss'], level: 0 }, controller.signal),
    ).rejects.toThrow('Aborted')
  })

  it('flags in the store only the experiment whose answer left out fractional steps', async () => {
    const legacyCatalog: MetricCatalogWire = {
      ...catalogWire,
      revision: 2,
      bucket_min_level: null,
      bucket_max_level: null,
      skipped_rows: 0,
      metrics: [{ key: 'loss', first_step: 0, last_step: 99, count: null, min: null, max: null }],
    }
    const getExperimentMetricBuckets = vi.fn(async (id: string) => ({
      level: 0,
      series: [{ ...lossWire, buckets: [], skipped_rows: id === 'e2' ? 1 : 0 }],
    }))
    const instance = await provider({
      getExperimentMetricCatalog: vi.fn().mockResolvedValue(legacyCatalog),
      getExperimentMetricBuckets,
    })
    const store = new MetricBucketStore(instance, { debounceMs: 0 })
    await new Promise<void>((done) => {
      const chart = store.subscribe((state) => {
        if (state.plan && !state.loading) done()
      })
      chart.request({ modelIds: ['e1', 'e2'], keys: ['loss'], bucketBudget: 100 })
    })
    const { statuses } = await store.loadCatalogs()
    store.dispose()
    expect(statuses.map((status) => [status.modelId, status.fractionalMetricSteps])).toEqual([
      ['e1', undefined],
      ['e2', true],
    ])
  })
})
