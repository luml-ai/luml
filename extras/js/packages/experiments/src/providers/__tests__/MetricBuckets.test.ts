import { beforeAll, describe, expect, it } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import {
  INVALID_LEVEL,
  NEEDS_NEWER_READER,
  READ_FAILED,
  TOO_MANY_BUCKETS,
} from '@/metric-buckets/types'
import type {
  ExperimentMetricCatalog,
  ExperimentResult,
  MetricBucket,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogsRequest,
} from '@/metric-buckets/types'
import { MetricBucketStore, type ChartState } from '@/metric-buckets/MetricBucketStore'
import {
  legacyCatalog,
  oracleBuckets,
  oracleCatalog,
  rawBuffer,
  revision2Database,
  revision3Database,
  zipped,
  type MetricPoint,
  type OracleBucket,
} from './helpers/metricDatabases'
import { GENERATED_KEYS, generatedMetrics, SUB_RANGES } from './helpers/generatedMetrics'
import { indexTar, readFixtureTar } from './helpers/snapshotSources'

const LEVELS = Array.from({ length: 15 }, (_, level) => level)

function valueOf<T>(result: ExperimentResult<T> | undefined): T {
  if (!result?.ok) throw new Error(`expected a value, got ${JSON.stringify(result)}`)
  return result.value
}

/** Exact on every field except `sum`, which the contract compares within 1e-9 of sum(|v|). */
function expectSameBuckets(actual: MetricBucket[], expected: OracleBucket[], label: string) {
  const exact = (bucket: MetricBucket) => ({ ...bucket, sum: bucket.sum === null })
  expect(actual.map(exact), label).toEqual(
    expected.map(({ sumAbs: _sumAbs, ...bucket }) => exact(bucket)),
  )
  actual.forEach((bucket, index) => {
    const reference = expected[index]
    if (bucket.sum === null || !reference || reference.sum === null) return
    expect(Math.abs(bucket.sum - reference.sum), label).toBeLessThanOrEqual(1e-9 * reference.sumAbs)
  })
}

async function providerFor(
  sources: { modelId: string; db: Uint8Array; zip?: boolean }[],
): Promise<ExperimentSnapshotDatabaseProvider> {
  const provider = new ExperimentSnapshotDatabaseProvider()
  const modelsInfo = await Promise.all(
    sources.map(async ({ modelId, db, zip }) =>
      zip
        ? { modelId, buffer: await zipped(db) }
        : { modelId, source: { kind: 'raw' as const, buffer: rawBuffer(db) } },
    ),
  )
  await provider.init({ modelsInfo })
  return provider
}

function seriesOf(response: MetricBucketsResponse, key: string) {
  const series = response.series.find((item) => item.key === key)
  if (!series) throw new Error(`no series ${key}`)
  return series
}

describe('metric catalog and buckets on revision 2 and revision 3 databases', () => {
  const points = generatedMetrics()
  let provider: ExperimentSnapshotDatabaseProvider

  beforeAll(async () => {
    provider = await providerFor([
      { modelId: 'rev2', db: await revision2Database(points), zip: true },
      { modelId: 'rev3', db: await revision3Database(points) },
    ])
  })

  it('returns identical catalogs equal to the brute-force summary', async () => {
    const [rev2, rev3] = (await provider.getMetricCatalogs()).map(valueOf)
    const metrics = oracleCatalog(points)

    expect(metrics.map((entry) => entry.key)).toEqual(GENERATED_KEYS)
    expect(rev2).toEqual({
      revision: 2,
      bucket_min_level: null,
      bucket_max_level: null,
      skipped_rows: 0,
      metrics: legacyCatalog(metrics),
    } satisfies ExperimentMetricCatalog)
    expect(rev3).toEqual({
      revision: 3,
      bucket_min_level: 3,
      bucket_max_level: 12,
      skipped_rows: 0,
      metrics,
    })
  })

  it('returns the same buckets at every level 0-14 and sub-range from every source', async () => {
    for (const level of LEVELS) {
      for (const [start, end] of SUB_RANGES) {
        const results = await provider.getMetricBuckets({
          keys: [...GENERATED_KEYS, 'missing'],
          start_step: start,
          end_step: end,
          level,
        })
        const [rev2, rev3] = results.map(valueOf)
        for (const key of GENERATED_KEYS) {
          const expected = oracleBuckets(points, key, level, start, end)
          const label = `${key} level ${level} [${start}, ${end}]`
          expectSameBuckets(seriesOf(rev2!, key).buckets, expected, `rev2 ${label}`)
          expectSameBuckets(seriesOf(rev3!, key).buckets, expected, `rev3 ${label}`)
          expect(seriesOf(rev3!, key).first_step).toBe(seriesOf(rev2!, key).first_step)
        }
        for (const response of [rev2!, rev3!]) {
          expect(seriesOf(response, 'missing')).toEqual({
            key: 'missing',
            first_step: null,
            last_step: null,
            buckets: [],
          })
          expect(response.level).toBe(level)
        }
      }
    }
  }, 60_000)

  it('reports the metric range, not the requested one, and orders series as requested', async () => {
    const [rev3] = (
      await provider.getMetricBuckets({
        modelIds: ['rev3'],
        keys: ['warmup', 'loss'],
        start_step: 10,
        end_step: 20,
        level: 1,
      })
    ).map(valueOf)

    expect(rev3!.series.map((series) => series.key)).toEqual(['warmup', 'loss'])
    expect(seriesOf(rev3!, 'loss')).toMatchObject({ first_step: 0, last_step: 2999 })
    expect(seriesOf(rev3!, 'loss').buckets.map((bucket) => bucket.bucket)).toEqual([2, 3, 4, 5])
    expect(seriesOf(rev3!, 'warmup').buckets).toEqual([])
  })

  it('rejects a series of more than 20,000 buckets with a typed per-experiment error', async () => {
    const many: MetricPoint[] = Array.from({ length: 20_001 }, (_, step) => ({
      key: 'dense',
      step,
      value: step,
    }))
    const capped = await providerFor([
      { modelId: 'dense', db: await revision3Database(many) },
      { modelId: 'other', db: await revision3Database(points) },
    ])

    const [dense, other] = await capped.getMetricBuckets({ keys: ['dense', 'loss'], level: 0 })
    expect(dense).toMatchObject({ modelId: 'dense', ok: false, error: { code: TOO_MANY_BUCKETS } })
    expect(other).toMatchObject({ modelId: 'other', ok: true })
    const [fits] = await capped.getMetricBuckets({ modelIds: ['dense'], keys: ['dense'], level: 1 })
    expect(valueOf(fits).series[0]!.buckets).toHaveLength(5001)
  })
})

describe('a database that stores levels 2 to 4 only, with text and BLOB values', () => {
  const points: MetricPoint[] = [
    ...generatedMetrics(5),
    ...Array.from({ length: 300 }, (_, index) => ({
      key: 'mixed',
      step: index * 7 - 900,
      value: index % 5 === 0 ? 'text' : index % 7 === 0 ? new Uint8Array([0, 255]) : index - 150,
    })),
  ]
  const keys = [...GENERATED_KEYS, 'mixed']
  let provider: ExperimentSnapshotDatabaseProvider

  beforeAll(async () => {
    provider = await providerFor([
      { modelId: 'rev2', db: await revision2Database(points), zip: true },
      {
        modelId: 'narrow',
        db: await revision3Database(points, { bucketLevels: { min: 2, max: 4 } }),
      },
    ])
  })

  it('reads the level range from exp_schema_info and counts non-numeric values only', async () => {
    const [rev2Result, narrowResult] = await provider.getMetricCatalogs()
    const narrow = valueOf(narrowResult)
    expect(narrow).toMatchObject({ bucket_min_level: 2, bucket_max_level: 4 })
    expect(narrow.metrics).toEqual(oracleCatalog(points))
    expect(valueOf(rev2Result).metrics).toEqual(legacyCatalog(narrow.metrics))
    const mixed = narrow.metrics.find((entry) => entry.key === 'mixed')
    expect(mixed).toMatchObject({ count: 300, min: -149, max: 149 })
  })

  // Above level 4 every metric has many stored top-level buckets, so each coarse bucket is
  // aggregated from several children.
  it('matches the oracle from raw points, stored levels and coarse aggregates', async () => {
    for (let level = 0; level <= 9; level++) {
      for (const [start, end] of SUB_RANGES) {
        const results = await provider.getMetricBuckets({
          keys,
          start_step: start,
          end_step: end,
          level,
        })
        for (const response of results.map(valueOf)) {
          for (const key of keys) {
            expectSameBuckets(
              seriesOf(response, key).buckets,
              oracleBuckets(points, key, level, start, end),
              `${key} level ${level} [${start}, ${end}]`,
            )
          }
        }
      }
    }
  }, 60_000)
})

describe('a chart through the store and the database provider', () => {
  it('reads five keys of five lengths with one query per experiment', async () => {
    const lengths = [10, 300, 1000, 2500, 4000]
    const points: MetricPoint[] = lengths.flatMap((length, index) =>
      Array.from({ length }, (_, step) => ({ key: `k${index}`, step: step - 7, value: step })),
    )
    const provider = await providerFor([
      { modelId: 'rev2', db: await revision2Database(points), zip: true },
      { modelId: 'rev3', db: await revision3Database(points) },
    ])
    const calls: MetricBucketsRequest[] = []
    const source = {
      getExperimentStatuses: () => provider.getExperimentStatuses(),
      getMetricCatalogs: (request?: MetricCatalogsRequest) => provider.getMetricCatalogs(request),
      getMetricBuckets: (request: MetricBucketsRequest) => {
        calls.push(request)
        return provider.getMetricBuckets(request)
      },
    }
    const store = new MetricBucketStore(source, { debounceMs: 0 })
    const keys = lengths.map((_, index) => `k${index}`)
    const done = new Promise<ChartState>((resolve) => {
      const chart = store.subscribe((state) => {
        if (state.plan && !state.loading) resolve(state)
      })
      chart.request({ modelIds: ['rev2', 'rev3'], keys, bucketBudget: 300 })
    })
    const state = await done

    expect(calls.map((call) => [call.modelIds, call.keys])).toEqual([
      [['rev2'], keys],
      [['rev3'], keys],
    ])
    for (const series of state.series) {
      expectSameBuckets(
        series.buckets,
        oracleBuckets(points, series.key, series.level),
        `${series.modelId} ${series.key}`,
      )
    }
    expect(state.series).toHaveLength(10)
  })
})

describe('legacy metric rows that cannot be bucketed', () => {
  // Released SDKs stored numpy integers as BLOB steps, floats as REAL steps and odd keys.
  const LEGACY_ROWS = `
    INSERT INTO dynamic_metrics (key, value, step) VALUES
      ('loss', 0.5, X'0500000000000000'), ('loss', 0.7, 2.5), (X'6b', 0.1, 3),
      ('loss', 0.2, NULL), (NULL, 0.3, 4);
  `
  const points: MetricPoint[] = Array.from({ length: 40 }, (_, step) => ({
    key: 'loss',
    step,
    value: 1 / (step + 1),
  }))

  it('are left out of catalog and buckets, counted in the status unless the step is REAL, kept by the old series', async () => {
    const provider = await providerFor([
      { modelId: 'legacy', db: await revision2Database(points, LEGACY_ROWS), zip: true },
    ])

    const [catalog] = await provider.getMetricCatalogs()
    expect(valueOf(catalog)).toMatchObject({
      skipped_rows: 4,
      metrics: legacyCatalog(oracleCatalog(points)),
    })
    const [buckets] = await provider.getMetricBuckets({ keys: ['loss', 'k'], level: 1 })
    expectSameBuckets(
      seriesOf(valueOf(buckets), 'loss').buckets,
      oracleBuckets(points, 'loss', 1),
      'legacy',
    )
    expect(seriesOf(valueOf(buckets), 'k').buckets).toEqual([])
    expect(await provider.getExperimentStatuses()).toEqual([
      expect.objectContaining({ modelId: 'legacy', skippedMetricRows: 4, error: null }),
    ])
    const [series] = await provider.getDynamicMetricData('loss')
    expect(series?.x).toContain(2.5)
  })
})

describe('bucket request validation', () => {
  it('rejects a level outside 0..31 and returns nothing for an inverted range', async () => {
    const points = generatedMetrics(3)
    const provider = await providerFor([{ modelId: 'new', db: await revision3Database(points) }])

    for (const level of [-1, 32, 2.5]) {
      const [result] = await provider.getMetricBuckets({ keys: ['loss'], level })
      expect(result).toMatchObject({ ok: false, error: { code: INVALID_LEVEL } })
    }
    const [top] = await provider.getMetricBuckets({ keys: ['loss'], level: 31 })
    expect(seriesOf(valueOf(top), 'loss').buckets).toHaveLength(1)
    const [inverted] = await provider.getMetricBuckets({
      keys: ['loss'],
      start_step: 10,
      end_step: 9,
      level: 0,
    })
    expect(seriesOf(valueOf(inverted), 'loss')).toMatchObject({ first_step: 0, buckets: [] })
  })
})

describe('an experiment whose snapshot could not be fetched', () => {
  it('is reported by its status and results while the others open', async () => {
    const points = generatedMetrics(3)
    const error = { code: READ_FAILED, message: 'The download failed' }
    const provider = new ExperimentSnapshotDatabaseProvider()
    const failures = await provider.init({
      modelsInfo: [
        { modelId: 'missing', error },
        {
          modelId: 'current',
          source: { kind: 'raw', buffer: rawBuffer(await revision3Database(points)) },
        },
      ],
    })

    expect(failures).toEqual([{ modelId: 'missing', error }])
    const [missing, current] = await provider.getMetricCatalogs()
    expect(missing).toEqual({ modelId: 'missing', ok: false, error })
    expect(valueOf(current).metrics).toEqual(oracleCatalog(points))
    const statuses = await provider.getExperimentStatuses()
    expect(statuses.map((status) => [status.modelId, status.error])).toEqual([
      ['missing', error],
      ['current', null],
    ])
  })
})

describe('reader rules of section 3', () => {
  const points = generatedMetrics(11)

  it('refuses only the experiment whose min_reader_revision is too new', async () => {
    const provider = await providerFor([
      { modelId: 'future', db: await revision3Database(points, { minReaderRevision: 4 }) },
      { modelId: 'current', db: await revision3Database(points) },
    ])

    const [future, current] = await provider.getMetricCatalogs()
    expect(future).toMatchObject({
      modelId: 'future',
      ok: false,
      error: { code: NEEDS_NEWER_READER },
    })
    expect(valueOf(current).metrics).toEqual(oracleCatalog(points))
    const [futureBuckets, currentBuckets] = await provider.getMetricBuckets({
      keys: ['loss'],
      level: 5,
    })
    expect(futureBuckets).toMatchObject({ ok: false, error: { code: NEEDS_NEWER_READER } })
    expect(currentBuckets).toMatchObject({ ok: true })
    expect((await provider.getDynamicMetricsNames()).sort()).toEqual(GENERATED_KEYS)
    expect(await provider.getExperimentStatuses()).toEqual([
      {
        modelId: 'future',
        revision: 3,
        transport: 'raw-full',
        transportFallback: null,
        unknownNewerRevision: false,
        skippedMetricRows: null,
        error: { code: NEEDS_NEWER_READER, message: expect.stringMatching(/revision 4/) },
      },
      {
        modelId: 'current',
        revision: 3,
        transport: 'raw-full',
        transportFallback: null,
        unknownNewerRevision: false,
        skippedMetricRows: 0,
        error: null,
      },
    ])
  })

  it('reads an unknown newer revision whose minimum is satisfied and flags it', async () => {
    const provider = await providerFor([
      { modelId: 'newer', db: await revision3Database(points, { revision: 5 }) },
    ])

    const [catalog] = await provider.getMetricCatalogs()
    expect(valueOf(catalog)).toMatchObject({ revision: 5, bucket_max_level: 12 })
    const [buckets] = await provider.getMetricBuckets({ keys: ['loss'], level: 6 })
    expectSameBuckets(
      seriesOf(valueOf(buckets), 'loss').buckets,
      oracleBuckets(points, 'loss', 6),
      'newer',
    )
    expect(await provider.getExperimentStatuses()).toEqual([
      expect.objectContaining({ revision: 5, unknownNewerRevision: true, error: null }),
    ])
  })
})

describe('mixed-generation comparison through the real provider', () => {
  it('aligns an old zipped fixture and a revision 3 database at one level', async () => {
    const archive = readFixtureTar('d_sdk_0_5_0')
    const [offset, size] = indexTar(archive)['exp.db.zip']!
    const old = new ExperimentSnapshotDatabaseProvider()
    await old.init({
      modelsInfo: [{ modelId: 'old', buffer: archive.slice(offset, offset + size).buffer }],
    })
    const [history] = await old.getDynamicMetricData('train_loss')
    const points: MetricPoint[] = history!.x.map((step, index) => ({
      key: 'train_loss',
      step,
      value: history!.y[index] ?? null,
    }))
    const provider = new ExperimentSnapshotDatabaseProvider()
    await provider.init({
      modelsInfo: [
        { modelId: 'old', buffer: archive.slice(offset, offset + size).buffer },
        {
          modelId: 'new',
          source: { kind: 'raw', buffer: rawBuffer(await revision3Database(points)) },
        },
      ],
    })

    const [oldResult, newResult] = await provider.getMetricBuckets({
      keys: ['train_loss'],
      start_step: 5,
      end_step: 30,
      level: 1,
    })
    const oldSeries = seriesOf(valueOf(oldResult), 'train_loss')
    const newSeries = seriesOf(valueOf(newResult), 'train_loss')
    expect(oldSeries.buckets.map((bucket) => bucket.bucket)).toEqual([1, 2, 3, 4, 5, 6, 7])
    expectSameBuckets(
      newSeries.buckets,
      oldSeries.buckets.map((bucket) => ({
        ...bucket,
        sumAbs: Math.abs(bucket.sum ?? 0),
      })),
      'mixed',
    )
  })
})
