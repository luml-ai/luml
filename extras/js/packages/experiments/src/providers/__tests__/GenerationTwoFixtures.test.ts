import { describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  ExperimentSnapshotDatabaseProvider,
  type ExperimentSnapshotModelSource,
} from '../ExperimentSnapshotDatabaseProvider'
import { MetricBucketStore, type ChartState } from '@/metric-buckets/MetricBucketStore'
import type {
  ExperimentMetricCatalog,
  ExperimentResult,
  MetricBucket,
  MetricBucketsResponse,
  MetricCatalogEntry,
} from '@/metric-buckets/types'
import { FIXTURES_DIR, indexTar, memoryTransport, readFixtureTar } from './helpers/snapshotSources'

/*
 * The generation 2 fixtures (and their generation 1 twins and fallback) read through the
 * production path: the artifact tar, its `file_index`, the member offset, and the transport
 * the platform picks from the member name. Expectations come from the fixture JSON, whose
 * buckets were computed by an independent brute force in Python.
 */

type JsonNumber = number | 'Infinity' | '-Infinity' | null
type JsonBucket = [number, number, number, number, number, JsonNumber, JsonNumber, number | null]

interface FixtureJson {
  expected?: {
    metrics?: Record<string, { count: number }>
    non_finite_metric?: { name: string; stored: unknown[] } | null
  }
  snapshot_member: string
  transport: 'raw' | 'zip'
  user_version: number
  schema_info: Record<string, string>
  metrics: {
    skipped_rows: number
    levels: number[]
    catalog: (Omit<MetricCatalogEntry, 'min' | 'max'> & { min: JsonNumber; max: JsonNumber })[]
    buckets: Record<string, Record<string, JsonBucket[]>>
  }
}

type PathKind = 'in-memory' | 'range'

// Mirrors findExperimentSnapshotArchiveName in frontend/src/lib/fnnx/FnnxService.ts.
const SNAPSHOT_MEMBER =
  /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v[12]~~et~~[^/]+\/exp\.db(\.zip)?$|^exp\.db(\.zip)?$/

const GENERATION_TWO = [
  'i_gen2_sdk_0_6_0',
  'j_gen2_model_sdk_0_6_0',
  'k_gen2_from_rev2',
  'm_gen2_twin',
]
const NEW_FIXTURES = [...GENERATION_TWO, 'l_gen1_twin', 'n_gen1_fallback']
const OLD_ERAS = [
  'a_premigration_legacy_indexes',
  'a_premigration_wal_lost',
  'b_premigration',
  'c_sdk_0_1_0',
  'd_sdk_0_5_0',
  'e_baseline_quirk',
  'f_model_sdk_0_5_0',
  'g_raw_sdk_0_5_0',
  'h_raw_model_sdk_0_5_0',
]
const SUM_TOLERANCE = 1e-9

function readJson(name: string): FixtureJson {
  return JSON.parse(readFileSync(resolve(FIXTURES_DIR, `${name}.json`), 'utf-8')) as FixtureJson
}

function decode(value: JsonNumber): number | null {
  if (value === 'Infinity') return Infinity
  if (value === '-Infinity') return -Infinity
  return value
}

function snapshotMember(name: string): { member: string; offset: number; size: number } {
  const fileIndex = indexTar(readFixtureTar(name))
  const members = Object.keys(fileIndex).filter((file) => SNAPSHOT_MEMBER.test(file))
  expect(members).toHaveLength(1)
  const [offset, size] = fileIndex[members[0]!]!
  return { member: members[0]!, offset, size }
}

/** The platform's choice: zip members are downloaded whole, raw ones by Range or in memory. */
function sourceOf(name: string, path: PathKind): ExperimentSnapshotModelSource {
  const { member, offset, size } = snapshotMember(name)
  const bytes = readFixtureTar(name).slice(offset, offset + size).buffer
  if (member.endsWith('.zip')) return { modelId: name, buffer: bytes }
  if (path === 'in-memory') return { modelId: name, source: { kind: 'raw', buffer: bytes } }
  return { modelId: name, source: { kind: 'range', url: `fixture:${name}`, offset, size } }
}

async function openProvider(names: string[], path: PathKind = 'range') {
  const recorded = memoryTransport(
    Object.fromEntries(names.map((name) => [`fixture:${name}`, readFixtureTar(name)])),
  )
  const provider = new ExperimentSnapshotDatabaseProvider({ transport: recorded.transport })
  const failures = await provider.init({ modelsInfo: names.map((name) => sourceOf(name, path)) })
  expect(failures).toEqual([])
  return { provider, requests: recorded.requests }
}

/** Exact point counts of an old era, recorded when the fixture was built. */
function recordedCounts(name: string): Record<string, number> {
  const expected = readJson(name).expected
  const counts = Object.fromEntries(
    Object.entries(expected?.metrics ?? {}).map(([key, stats]) => [key, stats.count]),
  )
  const nonFinite = expected?.non_finite_metric
  if (nonFinite) counts[nonFinite.name] = nonFinite.stored.length
  return counts
}

function expectedCatalogEntries(json: FixtureJson): MetricCatalogEntry[] {
  return json.metrics.catalog
    .map((entry) => ({ ...entry, min: decode(entry.min), max: decode(entry.max) }))
    .sort((left, right) => (left.key < right.key ? -1 : 1))
}

function sortedMetrics(catalog: ExperimentMetricCatalog): MetricCatalogEntry[] {
  return [...catalog.metrics].sort((left, right) => (left.key < right.key ? -1 : 1))
}

interface ExpectedBucket extends MetricBucket {
  sumAbs: number
}

/** Level 0 holds one bucket per point, so it gives each bucket's sum of magnitudes. */
function expectedBuckets(json: FixtureJson, key: string, level: number): ExpectedBucket[] {
  const points = json.metrics.buckets[key]?.['0'] ?? []
  const sumAbs = new Map<number, number>()
  for (const [, step, , , , , , sum] of points) {
    const bucket = Math.floor(step / 4 ** level)
    sumAbs.set(bucket, (sumAbs.get(bucket) ?? 0) + Math.abs(sum ?? 0))
  }
  return (json.metrics.buckets[key]?.[String(level)] ?? []).map(
    ([bucket, first_step, last_step, count, finite_count, min, max, sum]) => ({
      bucket,
      first_step,
      last_step,
      count,
      finite_count,
      min: decode(min),
      max: decode(max),
      sum,
      sumAbs: sumAbs.get(bucket) ?? 0,
    }),
  )
}

function inRange(buckets: ExpectedBucket[], level: number, start: number, end: number) {
  if (start > end) return []
  const width = 4 ** level
  return buckets.filter(
    (item) => item.bucket >= Math.floor(start / width) && item.bucket <= Math.floor(end / width),
  )
}

function expectBucketsMatch(actual: MetricBucket[], expected: ExpectedBucket[], label: string) {
  expect(
    actual.map((item) => item.bucket),
    label,
  ).toEqual(expected.map((item) => item.bucket))
  for (const [index, want] of expected.entries()) {
    const got = actual[index]!
    const { sumAbs, sum, ...exact } = want
    const { sum: gotSum, ...gotExact } = got
    expect(gotExact, `${label} bucket ${want.bucket}`).toEqual(exact)
    if (sum === null) {
      expect(gotSum, `${label} bucket ${want.bucket} sum`).toBeNull()
    } else {
      expect(gotSum, `${label} bucket ${want.bucket} sum`).not.toBeNull()
      expect(
        Math.abs(gotSum! - sum),
        `${label} bucket ${want.bucket} sum ${gotSum} vs ${sum}`,
      ).toBeLessThanOrEqual(SUM_TOLERANCE * sumAbs)
    }
  }
}

function okValue<T>(results: ExperimentResult<T>[], modelId: string): T {
  const result = results.find((item) => item.modelId === modelId)
  expect(result, `result for ${modelId}`).toBeDefined()
  if (!result!.ok) throw new Error(`${modelId}: ${result!.error.code} ${result!.error.message}`)
  return result!.value
}

/** Sub-ranges cutting through buckets at every level, plus the empty and reversed cases. */
function subRanges(entry: { first_step: number; last_step: number }): [number, number][] {
  const { first_step: first, last_step: last } = entry
  const span = last - first
  return [
    [first, last],
    [first, first + Math.floor(span / 3)],
    [first + Math.floor(span / 3) + 1, last - Math.floor(span / 5)],
    [last - Math.floor(span / 7), last],
    [first + 1, first + 1],
    [last + 1, last + 1000],
  ]
}

describe.each(NEW_FIXTURES)('fixture %s through the production path', (name) => {
  const json = readJson(name)
  const paths: PathKind[] = json.transport === 'raw' ? ['in-memory', 'range'] : ['in-memory']

  it('is found by its member name and opens with the transport the name implies', async () => {
    const { member } = snapshotMember(name)
    expect(member).toBe(json.snapshot_member)
    const { provider } = await openProvider([name])
    const [status] = await provider.getExperimentStatuses()
    expect(status).toMatchObject({
      modelId: name,
      revision: json.user_version,
      transport: json.transport === 'zip' ? 'zip-full' : 'raw-range',
      transportFallback: null,
      unknownNewerRevision: false,
      error: null,
    })
  })

  it.each(paths)('returns the expected catalog (%s)', async (path) => {
    const { provider } = await openProvider([name], path)
    const catalog = okValue(await provider.getMetricCatalogs(), name)
    expect(catalog.revision).toBe(json.user_version)
    expect(catalog.skipped_rows).toBe(json.metrics.skipped_rows)
    const levels = json.schema_info
    expect([catalog.bucket_min_level, catalog.bucket_max_level]).toEqual(
      levels.bucket_min_level
        ? [Number(levels.bucket_min_level), Number(levels.bucket_max_level)]
        : [null, null],
    )
    expect(sortedMetrics(catalog)).toEqual(expectedCatalogEntries(json))
    const [status] = await provider.getExperimentStatuses()
    expect(status!.skippedMetricRows).toBe(json.metrics.skipped_rows)
  })

  it.each(paths)('returns the expected buckets at every level and sub-range (%s)', async (path) => {
    const { provider } = await openProvider([name], path)
    const keys = json.metrics.catalog.map((entry) => entry.key)
    for (const level of json.metrics.levels) {
      const whole = await provider.getMetricBuckets({ keys, level })
      const response = okValue(whole, name)
      expect(response.level).toBe(level)
      for (const entry of json.metrics.catalog) {
        const series = response.series.find((item) => item.key === entry.key)!
        expect([series.first_step, series.last_step]).toEqual([entry.first_step, entry.last_step])
        expectBucketsMatch(
          series.buckets,
          expectedBuckets(json, entry.key, level),
          `${entry.key} L${level}`,
        )
        for (const [start, end] of subRanges(entry)) {
          const part = okValue(
            await provider.getMetricBuckets({
              keys: [entry.key],
              level,
              start_step: start,
              end_step: end,
            }),
            name,
          )
          expectBucketsMatch(
            part.series[0]!.buckets,
            inRange(expectedBuckets(json, entry.key, level), level, start, end),
            `${entry.key} L${level} [${start}, ${end}]`,
          )
        }
      }
    }
  })
})

describe('generation 1 fallback n_gen1_fallback', () => {
  it('leaves out its fractional REAL step without counting it as skipped', async () => {
    const { provider } = await openProvider(['n_gen1_fallback'])
    const catalog = okValue(await provider.getMetricCatalogs(), 'n_gen1_fallback')
    expect(catalog.skipped_rows).toBe(0)
    expect(sortedMetrics(catalog)).toEqual(expectedCatalogEntries(readJson('n_gen1_fallback')))
    expect(await provider.getExperimentStatuses()).toEqual([
      expect.objectContaining({ transport: 'zip-full', revision: 2, skippedMetricRows: 0 }),
    ])
  })
})

describe('generation 1 and generation 2 twins l_gen1_twin and m_gen2_twin', () => {
  const twins = ['l_gen1_twin', 'm_gen2_twin']
  const [gen1, gen2] = twins as [string, string]
  const json = readJson(gen2)
  const keys = json.metrics.catalog.map((entry) => entry.key)

  it('give identical catalogs in one provider', async () => {
    const { provider } = await openProvider(twins)
    const catalogs = await provider.getMetricCatalogs()
    const steps = (catalog: ExperimentMetricCatalog) =>
      sortedMetrics(catalog).map(({ key, first_step, last_step }) => [key, first_step, last_step])
    expect(steps(okValue(catalogs, gen1))).toEqual(steps(okValue(catalogs, gen2)))
    expect(sortedMetrics(okValue(catalogs, gen1))).toEqual(expectedCatalogEntries(readJson(gen1)))
    expect(sortedMetrics(okValue(catalogs, gen2))).toEqual(expectedCatalogEntries(json))
    expect(await provider.getExperimentStatuses()).toEqual([
      expect.objectContaining({ modelId: gen1, transport: 'zip-full', revision: 2, error: null }),
      expect.objectContaining({ modelId: gen2, transport: 'raw-range', revision: 3, error: null }),
    ])
  })

  it('give identical buckets at every level 0-31 and several sub-ranges', async () => {
    const { provider } = await openProvider(twins)
    const closeSeries = (
      left: MetricBucketsResponse,
      right: MetricBucketsResponse,
      label: string,
    ) => {
      expect(right.series.map((s) => s.key)).toEqual(left.series.map((s) => s.key))
      for (const [index, series] of left.series.entries()) {
        const other = right.series[index]!
        const leftAsExpected = series.buckets.map((bucket) => ({
          ...bucket,
          sumAbs: Math.max(Math.abs(bucket.sum ?? 0), 1e-300) * bucket.finite_count,
        }))
        expect([other.first_step, other.last_step]).toEqual([series.first_step, series.last_step])
        expectBucketsMatch(other.buckets, leftAsExpected, `${label} ${series.key}`)
      }
    }
    for (let level = 0; level <= 31; level++) {
      const both = await provider.getMetricBuckets({ keys, level })
      closeSeries(okValue(both, gen1), okValue(both, gen2), `L${level}`)
    }
    for (const entry of json.metrics.catalog) {
      for (const level of [0, 1, 3, 4, 6, 12, 13]) {
        for (const [start, end] of subRanges(entry)) {
          const both = await provider.getMetricBuckets({
            keys: [entry.key],
            level,
            start_step: start,
            end_step: end,
          })
          closeSeries(okValue(both, gen1), okValue(both, gen2), `L${level} [${start}, ${end}]`)
        }
      }
    }
  })

  it('are fetched at one level by a comparison chart of the store', async () => {
    const { provider } = await openProvider(twins)
    const fetchBuckets = vi.spyOn(provider, 'getMetricBuckets')
    const store = new MetricBucketStore(provider, { debounceMs: 0 })
    const key = 'train/long_running_metric/with_a_fairly_long_key_name'
    const settled = new Promise<ChartState>((done) => {
      const chart = store.subscribe((state) => {
        if (state.plan && !state.loading && state.series.length === 2) done(state)
      })
      chart.request({ modelIds: twins, keys: [key], bucketBudget: 300 })
    })
    const state = await settled
    store.dispose()

    const levels = fetchBuckets.mock.calls.map(([request]) => request.level)
    expect(new Set(levels).size).toBe(1)
    expect(fetchBuckets.mock.calls.flatMap(([request]) => request.modelIds ?? []).sort()).toEqual(
      [...twins].sort(),
    )
    expect(state.plan!.experiments.map((plan) => plan.modelId).sort()).toEqual([...twins].sort())
    expect(state.series.map((series) => series.level)).toEqual([
      state.plan!.level,
      state.plan!.level,
    ])
    expect(state.series.every((series) => series.final)).toBe(true)
    const [first, second] = state.series
    expect(second!.buckets).toEqual(first!.buckets)
    expect(first!.buckets.reduce((sum, bucket) => sum + bucket.count, 0)).toBe(
      json.metrics.catalog.find((entry) => entry.key === key)!.count,
    )
  })
})

describe('a mixed set: every old era plus generation 2 standalone, embedded and twin', () => {
  const names = [...OLD_ERAS, 'i_gen2_sdk_0_6_0', 'j_gen2_model_sdk_0_6_0', 'm_gen2_twin']
  const expectedStatus: Record<string, { revision: number; transport: string }> = {
    a_premigration_legacy_indexes: { revision: 0, transport: 'zip-full' },
    a_premigration_wal_lost: { revision: 0, transport: 'zip-full' },
    b_premigration: { revision: 0, transport: 'zip-full' },
    c_sdk_0_1_0: { revision: 2, transport: 'zip-full' },
    d_sdk_0_5_0: { revision: 2, transport: 'zip-full' },
    e_baseline_quirk: { revision: 2, transport: 'zip-full' },
    f_model_sdk_0_5_0: { revision: 2, transport: 'zip-full' },
    g_raw_sdk_0_5_0: { revision: 2, transport: 'raw-range' },
    h_raw_model_sdk_0_5_0: { revision: 2, transport: 'raw-range' },
    i_gen2_sdk_0_6_0: { revision: 3, transport: 'raw-range' },
    j_gen2_model_sdk_0_6_0: { revision: 3, transport: 'raw-range' },
    m_gen2_twin: { revision: 3, transport: 'raw-range' },
  }

  it('answers the catalog, one bucket request and the statuses for every experiment', async () => {
    const { provider } = await openProvider(names)
    const catalogs = await provider.getMetricCatalogs()
    expect(catalogs.map((result) => [result.modelId, result.ok])).toEqual(
      names.map((name) => [name, true]),
    )
    const allKeys = [
      ...new Set(
        catalogs.flatMap((result) => okValue([result], result.modelId).metrics.map((m) => m.key)),
      ),
    ]
    const buckets = await provider.getMetricBuckets({ keys: allKeys, level: 4 })
    expect(buckets.map((result) => [result.modelId, result.ok])).toEqual(
      names.map((name) => [name, true]),
    )
    for (const name of names) {
      const catalog = okValue(catalogs, name)
      const response = okValue(buckets, name)
      const recorded = recordedCounts(name)
      expect(response.level).toBe(4)
      for (const entry of catalog.metrics) {
        const series = response.series.find((item) => item.key === entry.key)!
        expect([series.first_step, series.last_step], `${name} ${entry.key}`).toEqual([
          entry.first_step,
          entry.last_step,
        ])
        const points = series.buckets.reduce((sum, bucket) => sum + bucket.count, 0)
        if (entry.count === null) {
          expect(recorded[entry.key], `${name} ${entry.key}`).toBeDefined()
          expect(points, `${name} ${entry.key}`).toBe(recorded[entry.key])
        } else {
          expect(points, `${name} ${entry.key}`).toBe(entry.count)
        }
      }
      const missing = response.series.filter(
        (series) => !catalog.metrics.some((entry) => entry.key === series.key),
      )
      expect(
        missing.every((series) => series.buckets.length === 0 && series.first_step === null),
      ).toBe(true)
    }
    expect(okValue(catalogs, 'a_premigration_wal_lost').metrics).toEqual([])
    const statuses = await provider.getExperimentStatuses()
    expect(
      statuses.map(({ modelId, revision, transport, error }) => ({
        modelId,
        revision,
        transport,
        error,
      })),
    ).toEqual(names.map((name) => ({ modelId: name, ...expectedStatus[name], error: null })))
  })
})
