import type { Page } from '@playwright/test'
import { test, expect } from './fixtures/snapshot-error-guard'
import { build, type Plugin } from 'esbuild'
import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { indexTar, writeTar } from './fixtures/snapshot-tar'
import { craftedZip } from '../../../extras/js/packages/experiments/src/providers/__tests__/helpers/craftedZip'
import {
  revision3Database,
  seededRandom,
  type MetricPoint,
} from '../../../extras/js/packages/experiments/src/providers/__tests__/helpers/metricDatabases'

// Generation 2 snapshots (raw exp.db read by HTTP Range) next to generation 1 ones, through the
// real worker, provider, range VFS and bucket store in Chromium, served by a local store that
// logs every request. Expectations come from the fixture JSON (an independent brute force).

// No retries: a flaky read is a failure here.
test.describe.configure({ mode: 'serial', retries: 0 })

const here = dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const EXPERIMENTS_SRC = resolve(here, '../../../extras/js/packages/experiments/src')
const FIXTURES_DIR = resolve(here, '../../../sdk/python/sdk/tests/fixtures/experiment_snapshots')
const WORKER_ENTRY = resolve(here, '../../../extras/js/experimentSnapshotWorker.ts')
const HARNESS_ENTRY = resolve(here, 'fixtures/experiment-snapshot-esbuild-entry.ts')
const SNAPSHOT_MEMBER =
  /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v[12]~~et~~[^/]+\/exp\.db(\.zip)?$|^exp\.db(\.zip)?$/
const SUM_TOLERANCE = 1e-9
const CHART_BUDGET = 1000
const LARGE = 'synthetic_gen2_large'
const LARGE_POINTS = 600_000
const LARGE_KEYS = ['train/loss', 'val/accuracy', 'lr']
const HUGE_ZIP = 'crafted_huge_zip'
const ZIP_TAIL_BYTES = 128 * 1024

type JsonNumber = number | 'Infinity' | '-Infinity' | null
type JsonBucket = [number, number, number, number, number, JsonNumber, JsonNumber, number | null]

interface Bucket {
  bucket: number
  first_step: number
  last_step: number
  count: number
  finite_count: number
  min: number | null
  max: number | null
  sum: number | null
}

interface CatalogEntry {
  key: string
  first_step: number
  last_step: number
  count: number | null
  min: number | null
  max: number | null
}

interface Artifact {
  name: string
  tar: Uint8Array
  member: string
  offset: number
  size: number
  /** Brute-force metric summary recorded when the fixture was built. */
  expectedMetrics: Record<string, { count: number; first_step: number; last_step: number }>
  json: {
    user_version: number
    metrics: {
      skipped_rows: number
      levels: number[]
      catalog: (Omit<CatalogEntry, 'min' | 'max'> & {
        min: JsonNumber
        max: JsonNumber
        writes?: number
      })[]
      buckets: Record<string, Record<string, JsonBucket[]>>
    }
  } | null
}

interface LoggedRequest {
  artifact: string
  range: [number, number] | null
  status: number
  bytes: number
}

type Settled = { ok: boolean; value?: unknown; error?: Record<string, unknown> }

interface HarnessWindow {
  harness: {
    init(sources: unknown[]): Promise<Settled>
    call(method: string, args?: unknown[]): Promise<Settled>
    stats(): Promise<Settled>
    chartState(request: unknown): Promise<Settled>
  }
}

interface ChartSnapshot {
  level: number
  fetchLevels: number[]
  errors: unknown[]
  series: { modelId: string; key: string; level: number; final: boolean; buckets: Bucket[] }[]
  statuses: { modelId: string; skippedMetricRows: number | null; fractionalMetricSteps?: boolean }[]
}

type Result<T> =
  | { modelId: string; ok: true; value: T }
  | { modelId: string; ok: false; error: unknown }

const GENERATION_TWO = [
  'i_gen2_sdk_0_6_0',
  'j_gen2_model_sdk_0_6_0',
  'k_gen2_from_rev2',
  'm_gen2_twin',
  'p_gen2_rev4_sdk_0_6_0',
]
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
const TWINS = ['l_gen1_twin', 'm_gen2_twin']
const FALLBACK = 'n_gen1_fallback'

function artifactOf(
  name: string,
  tar: Uint8Array,
  json: Artifact['json'],
  expectedMetrics: Artifact['expectedMetrics'] = {},
): Artifact {
  const index = indexTar(tar)
  const members = Object.keys(index).filter((file) => SNAPSHOT_MEMBER.test(file))
  if (members.length !== 1) throw new Error(`${name}: snapshot members ${members.join(', ')}`)
  const [offset, size] = index[members[0]!]!
  return { name, tar, member: members[0]!, offset, size, expectedMetrics, json }
}

function readFixture(name: string): Artifact {
  const description = JSON.parse(readFileSync(resolve(FIXTURES_DIR, `${name}.json`), 'utf-8'))
  const tar = new Uint8Array(readFileSync(resolve(FIXTURES_DIR, `${name}.tar`)))
  return artifactOf(
    name,
    tar,
    description.metrics ? description : null,
    description.expected?.metrics ?? {},
  )
}

/** A large generation 2 experiment: three metrics of 200k points each, seeded. */
async function largeArtifact(): Promise<Artifact> {
  const random = seededRandom(1100)
  const points: MetricPoint[] = []
  const perKey = LARGE_POINTS / LARGE_KEYS.length
  for (const key of LARGE_KEYS) {
    for (let step = 0; step < perKey; step++) {
      points.push({ key, step, value: Math.exp(-step / perKey) + random() * 0.01 })
    }
  }
  const db = await revision3Database(points)
  const manifest = new TextEncoder().encode('{"producer_tags":["luml.ai::experiment_snapshot:v2"]}')
  const tar = writeTar([
    { name: 'manifest.json', data: manifest },
    { name: 'exp.db', data: db },
  ])
  return artifactOf(LARGE, tar, null)
}

const wasmUrlPlugin: Plugin = {
  name: 'wasm-url',
  setup(builder) {
    builder.onResolve({ filter: /\?url$/ }, (args) => ({ path: args.path, namespace: 'wasm-url' }))
    builder.onLoad({ filter: /.*/, namespace: 'wasm-url' }, () => ({
      contents: `export default ${JSON.stringify('/sqlite3.wasm')}`,
    }))
    builder.onResolve({ filter: /^@luml\/experiments$/ }, () => ({
      path: 'experiments',
      namespace: 'luml-experiments',
    }))
    builder.onLoad({ filter: /.*/, namespace: 'luml-experiments' }, () => ({
      resolveDir: EXPERIMENTS_SRC,
      contents: [
        "export { ExperimentSnapshotDatabaseProvider } from './providers/ExperimentSnapshotDatabaseProvider'",
        "export { ExperimentSnapshotWorkerProxy } from './providers/ExperimentSnapshotWorkerProxy'",
        "export { MetricBucketStore } from './metric-buckets/MetricBucketStore'",
        "export { redactSecrets, snapshotErrorFields } from './providers/snapshot-source/errors'",
        "export { assertZipSnapshotFits } from './providers/snapshot-source/zipDirectory'",
        "export { toExperimentReadError } from './metric-buckets/errors'",
      ].join('\n'),
    }))
  },
}

async function bundle(entry: string): Promise<string> {
  const result = await build({
    entryPoints: [entry],
    bundle: true,
    format: 'esm',
    platform: 'browser',
    write: false,
    alias: { '@': EXPERIMENTS_SRC },
    plugins: [wasmUrlPlugin],
    logLevel: 'silent',
  })
  return result.outputFiles[0]!.text
}

const artifacts = new Map<string, Artifact>()
let server: Server
let origin: string
let requests: LoggedRequest[] = []
let signs: string[] = []

test.beforeAll(async () => {
  test.setTimeout(180_000)
  for (const name of [...new Set([...GENERATION_TWO, ...OLD_ERAS, ...TWINS, FALLBACK])]) {
    artifacts.set(name, readFixture(name))
  }
  const [workerJs, harnessJs, large] = await Promise.all([
    bundle(WORKER_ENTRY),
    bundle(HARNESS_ENTRY),
    largeArtifact(),
  ])
  artifacts.set(LARGE, large)
  // Only the directory claims 3.8 GB, so the zip is tiny; JSZip could never open it.
  const hugeZip = craftedZip([{ name: 'exp.db', size: 0, zip64Size: 3_811_495_936 }], '', 300_000)
  artifacts.set(
    HUGE_ZIP,
    artifactOf(HUGE_ZIP, writeTar([{ name: 'exp.db.zip', data: hugeZip }]), null),
  )
  const assets: Record<string, [string, string | Uint8Array]> = {
    '/': ['text/html', '<!doctype html><script type="module" src="/main.js"></script>'],
    '/main.js': ['text/javascript', harnessJs],
    '/worker.js': ['text/javascript', workerJs],
    '/sqlite3.wasm': [
      'application/wasm',
      readFileSync(require.resolve('@sqlite.org/sqlite-wasm/sqlite3.wasm')),
    ],
  }
  server = createServer((request, response) => {
    const url = new URL(request.url!, 'http://store')
    if (url.pathname === '/sign') {
      const name = url.searchParams.get('artifact') ?? ''
      signs.push(name)
      response.end(`${origin}/artifact/${name}?sig=${signs.length}`)
      return
    }
    if (url.pathname.startsWith('/artifact/')) {
      const name = url.pathname.slice('/artifact/'.length)
      const tar = artifacts.get(name)?.tar
      if (!tar) {
        response.writeHead(404).end()
        return
      }
      const match = /^bytes=(\d+)-(\d+)$/.exec(request.headers.range ?? '')
      if (!match) {
        requests.push({ artifact: name, range: null, status: 200, bytes: tar.length })
        response.writeHead(200, { 'Content-Length': tar.length }).end(tar)
        return
      }
      const start = Number(match[1])
      const end = Math.min(Number(match[2]), tar.length - 1)
      const body = tar.subarray(start, end + 1)
      requests.push({ artifact: name, range: [start, end], status: 206, bytes: body.length })
      response
        .writeHead(206, {
          'Content-Length': body.length,
          'Content-Range': `bytes ${start}-${end}/${tar.length}`,
        })
        .end(body)
      return
    }
    const asset = assets[url.pathname]
    if (!asset) {
      response.writeHead(404).end()
      return
    }
    response.writeHead(200, { 'Content-Type': asset[0] }).end(asset[1])
  })
  await new Promise<void>((done) => server.listen(0, '127.0.0.1', done))
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
})

test.afterAll(async () => {
  await new Promise((done) => server?.close(done))
})

test.beforeEach(() => {
  requests = []
  signs = []
})

async function open(page: Page, names: string[]): Promise<void> {
  await page.goto(origin)
  await page.waitForFunction(() => 'harness' in window)
  const sources = names.map((name) => {
    const artifact = artifacts.get(name)!
    return {
      modelId: name,
      artifact: name,
      kind: artifact.member.endsWith('.zip') ? 'zip' : 'range',
      offset: artifact.offset,
      size: artifact.size,
    }
  })
  const opened = await page.evaluate(
    (items) => (window as never as HarnessWindow).harness.init(items),
    sources,
  )
  expect(opened, JSON.stringify(opened.error)).toMatchObject({ ok: true })
}

async function call<T>(page: Page, method: string, args: unknown[] = []): Promise<T> {
  const settled = await page.evaluate(
    ([name, values]) => (window as never as HarnessWindow).harness.call(name, values),
    [method, args] as const,
  )
  expect(settled, `${method}: ${JSON.stringify(settled.error)}`).toMatchObject({ ok: true })
  return settled.value as T
}

async function chart(page: Page, request: Record<string, unknown>): Promise<ChartSnapshot> {
  const settled = await page.evaluate(
    (value) => (window as never as HarnessWindow).harness.chartState(value),
    request,
  )
  expect(settled, JSON.stringify(settled.error)).toMatchObject({ ok: true })
  return settled.value as ChartSnapshot
}

function value<T>(results: Result<T>[], modelId: string): T {
  const result = results.find((item) => item.modelId === modelId)
  if (!result?.ok) throw new Error(`${modelId}: ${JSON.stringify(result)}`)
  return result.value
}

function decode(raw: JsonNumber): number | null {
  if (raw === 'Infinity') return Infinity
  if (raw === '-Infinity') return -Infinity
  return raw
}

// A published snapshot reports no `writes` counter: it never changes after export.
function expectedCatalog(artifact: Artifact): CatalogEntry[] {
  return artifact
    .json!.metrics.catalog.map(({ writes: _writes, ...entry }) => ({
      ...entry,
      min: decode(entry.min),
      max: decode(entry.max),
    }))
    .sort((left, right) => (left.key < right.key ? -1 : 1))
}

function sortedByKey<T extends { key: string }>(entries: T[]): T[] {
  return [...entries].sort((left, right) => (left.key < right.key ? -1 : 1))
}

function expectBuckets(actual: Bucket[], artifact: Artifact, key: string, level: number) {
  const byLevel = artifact.json!.metrics.buckets[key]!
  const sumAbs = new Map<number, number>()
  for (const [, step, , , , , , sum] of byLevel['0'] ?? []) {
    const bucket = Math.floor(step / 4 ** level)
    sumAbs.set(bucket, (sumAbs.get(bucket) ?? 0) + Math.abs(sum ?? 0))
  }
  const expected = (byLevel[String(level)] ?? []).map(
    ([bucket, first_step, last_step, count, finite_count, min, max, sum]) => ({
      bucket,
      first_step,
      last_step,
      count,
      finite_count,
      min: decode(min),
      max: decode(max),
      sum,
    }),
  )
  const label = `${artifact.name} ${key} L${level}`
  expect(
    actual.map((item) => item.bucket),
    label,
  ).toEqual(expected.map((item) => item.bucket))
  for (const [index, want] of expected.entries()) {
    const { sum, ...exact } = actual[index]!
    const { sum: wantSum, ...wantExact } = want
    expect(exact, `${label} bucket ${want.bucket}`).toEqual(wantExact)
    if (wantSum === null) expect(sum, label).toBeNull()
    else
      expect(Math.abs((sum ?? NaN) - wantSum), `${label} sum`).toBeLessThanOrEqual(
        SUM_TOLERANCE * (sumAbs.get(want.bucket) ?? 0),
      )
  }
}

function requestsOf(name: string): LoggedRequest[] {
  return requests.filter((request) => request.artifact === name)
}

/** Every request a range reader makes stays inside the DB member of the artifact. */
function expectRangeReadsOnly(artifact: Artifact) {
  const own = requestsOf(artifact.name)
  expect(own.length, `${artifact.name} requests`).toBeGreaterThan(0)
  for (const request of own) {
    expect(request.status, `${artifact.name} full download`).toBe(206)
    const [start, end] = request.range!
    expect(start).toBeGreaterThanOrEqual(artifact.offset)
    expect(end).toBeLessThan(artifact.offset + artifact.size)
  }
}

for (const name of GENERATION_TWO) {
  test(`${name}: catalog and buckets at every level by range reads`, async ({ page }) => {
    const artifact = artifacts.get(name)!
    await open(page, [name])
    const catalogs = await call<
      Result<{ revision: number; skipped_rows: number; metrics: CatalogEntry[] }>[]
    >(page, 'getMetricCatalogs')
    const catalog = value(catalogs, name)
    expect(catalog.revision).toBe(artifact.json!.user_version)
    expect(catalog.skipped_rows).toBe(0)
    expect(sortedByKey(catalog.metrics)).toEqual(expectedCatalog(artifact))
    const openRequests = requestsOf(name).length

    const keys = catalog.metrics.map((entry) => entry.key)
    for (const level of artifact.json!.metrics.levels) {
      const response = value(
        await call<Result<{ level: number; series: { key: string; buckets: Bucket[] }[] }>[]>(
          page,
          'getMetricBuckets',
          [{ keys, level }],
        ),
        name,
      )
      for (const series of response.series)
        expectBuckets(series.buckets, artifact, series.key, level)
    }
    const [stat] = await call<{ transport: string; requests: number; bytesFetched: number }[]>(
      page,
      'getTransportStats',
    )
    expect(stat).toMatchObject({ modelId: name, transport: 'raw-range' })
    expectRangeReadsOnly(artifact)
    expect(signs).toEqual([name])
    // Catalog plus every level of every metric of a 400 KiB DB: a handful of 64 KiB reads.
    expect(openRequests).toBeLessThanOrEqual(4)
    expect(requestsOf(name).length).toBeLessThanOrEqual(10)
  })
}

test('the largest frozen fixture opens and draws a chart without downloading its DB', async ({
  page,
}) => {
  const name = 'j_gen2_model_sdk_0_6_0'
  const artifact = artifacts.get(name)!
  await open(page, [name])
  const drawn = await chart(page, {
    modelIds: [name],
    keys: ['train/long_running_metric/with_a_fairly_long_key_name'],
    bucketBudget: CHART_BUDGET,
  })
  expect(drawn.errors).toEqual([])
  expect(drawn.series).toHaveLength(1)
  expectRangeReadsOnly(artifact)
  const bytes = requestsOf(name).reduce((sum, request) => sum + request.bytes, 0)
  // The DB of this fixture is 640 KiB, ten 64 KiB chunks. The trace and eval indexes sit
  // before the metric leaves, so the chart reads two chunks the catalog did not: six in all.
  expect(bytes, `fetched ${bytes} of ${artifact.size}`).toBeLessThanOrEqual(6 * 64 * 1024)
})

test('a large generation 2 experiment: open, chart, zoom read a small fraction of the DB', async ({
  page,
}) => {
  const artifact = artifacts.get(LARGE)!
  expect(artifact.size).toBeGreaterThan(10 * 1024 * 1024)
  await open(page, [LARGE])
  const lastStep = LARGE_POINTS / LARGE_KEYS.length - 1
  const whole = await chart(page, {
    modelIds: [LARGE],
    keys: LARGE_KEYS,
    bucketBudget: CHART_BUDGET,
  })
  expect(whole.errors).toEqual([])
  expect(whole.series.map((series) => series.key).sort()).toEqual([...LARGE_KEYS].sort())
  for (const series of whole.series) {
    expect(series.final).toBe(true)
    expect(series.buckets.reduce((sum, bucket) => sum + bucket.count, 0)).toBe(lastStep + 1)
  }
  expect(new Set(whole.fetchLevels)).toEqual(new Set([whole.level]))
  const afterOpen = requestsOf(LARGE).reduce((sum, request) => sum + request.bytes, 0)
  expect(afterOpen, `fetched ${afterOpen} of ${artifact.size}`).toBeLessThan(artifact.size * 0.05)

  const before = requests.length
  const zoomStart = Math.floor(lastStep * 0.4)
  const zoomEnd = zoomStart + 2_000
  const zoomed = await chart(page, {
    modelIds: [LARGE],
    keys: ['train/loss'],
    bucketBudget: CHART_BUDGET,
    startStep: zoomStart,
    endStep: zoomEnd,
  })
  expect(zoomed.level).toBeLessThan(whole.level)
  const [series] = zoomed.series
  expect(series!.buckets[0]!.first_step).toBeLessThanOrEqual(zoomStart)
  expect(series!.buckets.at(-1)!.last_step).toBeGreaterThanOrEqual(zoomEnd)
  expect(series!.buckets.every((bucket) => bucket.last_step >= zoomStart - 4 ** zoomed.level)).toBe(
    true,
  )
  const zoomReads = requests.slice(before)
  expect(zoomReads.every((request) => request.status === 206)).toBe(true)
  const zoomBytes = zoomReads.reduce((sum, request) => sum + request.bytes, 0)
  expect(zoomBytes, `zoom fetched ${zoomBytes}`).toBeLessThan(artifact.size * 0.05)
  expectRangeReadsOnly(artifact)
  expect(signs).toEqual([LARGE])
})

test('the generation 1 and generation 2 twins compare equal at one level', async ({ page }) => {
  const [gen1, gen2] = TWINS as [string, string]
  const twin = artifacts.get(gen2)!
  await open(page, TWINS)
  const catalogs = await call<Result<{ metrics: CatalogEntry[] }>[]>(page, 'getMetricCatalogs')
  const expected = expectedCatalog(twin)
  expect(sortedByKey(value(catalogs, gen2).metrics)).toEqual(expected)
  // Revisions 0-2 read only the (key, step) index: steps are exact, count/min/max are unknown.
  expect(sortedByKey(value(catalogs, gen1).metrics)).toEqual(
    expected.map((entry) => ({ ...entry, count: null, min: null, max: null })),
  )

  for (const entry of twin.json!.metrics.catalog) {
    const drawn = await chart(page, { modelIds: TWINS, keys: [entry.key], bucketBudget: 64 })
    expect(drawn.errors).toEqual([])
    expect(new Set(drawn.fetchLevels).size, entry.key).toBe(1)
    const [left, right] = TWINS.map((modelId) => drawn.series.find((s) => s.modelId === modelId)!)
    expect(left!.level).toBe(right!.level)
    expect(
      left!.buckets.reduce((sum, bucket) => sum + bucket.count, 0),
      entry.key,
    ).toBe(entry.count)
    expect(right!.buckets.map(({ sum, ...rest }) => rest)).toEqual(
      left!.buckets.map(({ sum, ...rest }) => rest),
    )
    for (const [index, bucket] of left!.buckets.entries()) {
      const other = right!.buckets[index]!.sum
      if (bucket.sum === null) expect(other).toBeNull()
      else
        expect(Math.abs((other ?? NaN) - bucket.sum)).toBeLessThanOrEqual(
          1e-9 * Math.max(1, Math.abs(bucket.sum)) * bucket.finite_count,
        )
    }
  }
  const statuses = await call<{ modelId: string; transport: string; revision: number }[]>(
    page,
    'getExperimentStatuses',
  )
  expect(
    statuses.map(({ modelId, transport, revision }) => ({ modelId, transport, revision })),
  ).toEqual([
    { modelId: gen1, transport: 'zip-full', revision: 2 },
    { modelId: gen2, transport: 'raw-range', revision: 3 },
  ])
  expect(requestsOf(gen1).map((request) => request.bytes)).toEqual([artifacts.get(gen1)!.size])
  expectRangeReadsOnly(twin)
})

test('a mixed set of every old era and generation 2 opens and charts together', async ({
  page,
}) => {
  const names = [
    ...OLD_ERAS,
    'i_gen2_sdk_0_6_0',
    'j_gen2_model_sdk_0_6_0',
    'm_gen2_twin',
    'p_gen2_rev4_sdk_0_6_0',
  ]
  await open(page, names)
  const catalogs = await call<Result<{ metrics: CatalogEntry[] }>[]>(page, 'getMetricCatalogs')
  expect(catalogs.map((result) => [result.modelId, result.ok])).toEqual(
    names.map((name) => [name, true]),
  )
  const drawn = await chart(page, {
    modelIds: names,
    keys: ['train_loss'],
    bucketBudget: CHART_BUDGET,
  })
  expect(drawn.errors).toEqual([])
  expect(new Set(drawn.fetchLevels).size).toBe(1)
  for (const name of names) {
    const entry = value(catalogs, name).metrics.find((metric) => metric.key === 'train_loss')
    const series = drawn.series.find((item) => item.modelId === name)
    const oracle = artifacts.get(name)!.expectedMetrics.train_loss
    if (!entry) {
      expect(oracle, name).toBeUndefined()
      expect(series, name).toBeUndefined()
      continue
    }
    const points = series!.buckets.reduce((sum, bucket) => sum + bucket.count, 0)
    if (entry.count === null) {
      expect(oracle, name).toBeDefined()
      expect(points, name).toBe(oracle!.count)
      expect([entry.first_step, entry.last_step], name).toEqual([
        oracle!.first_step,
        oracle!.last_step,
      ])
      expect(series!.buckets[0]!.first_step, name).toBe(entry.first_step)
      expect(series!.buckets.at(-1)!.last_step, name).toBe(entry.last_step)
    } else {
      expect(points, name).toBe(entry.count)
    }
  }
  const statuses = await call<
    { modelId: string; transport: string; revision: number; error: unknown }[]
  >(page, 'getExperimentStatuses')
  for (const status of statuses) {
    const artifact = artifacts.get(status.modelId)!
    expect(status.error, status.modelId).toBeNull()
    expect(status.transport, status.modelId).toBe(
      artifact.member.endsWith('.zip') ? 'zip-full' : 'raw-range',
    )
    if (artifact.member.endsWith('.zip')) {
      expect(requestsOf(status.modelId).map((request) => request.bytes)).toEqual([artifact.size])
    } else {
      expectRangeReadsOnly(artifact)
    }
  }
  expect(signs.sort()).toEqual([...names].sort())
})

test('an old experiment whose only odd row is a fractional step is flagged once charted', async ({
  page,
}) => {
  // Written by luml-sdk 0.5.0: loss has one step at 2.5, which its catalog does not count. The
  // flag turns on the skipped-steps notice (experimentStatusNotice.ts).
  const other = 'i_gen2_sdk_0_6_0'
  await open(page, [FALLBACK, other])
  const catalogs = await call<Result<{ skipped_rows: number }>[]>(page, 'getMetricCatalogs')
  expect(value(catalogs, FALLBACK).skipped_rows).toBe(0)
  const drawn = await chart(page, {
    modelIds: [FALLBACK, other],
    keys: ['loss'],
    bucketBudget: CHART_BUDGET,
  })
  expect(drawn.errors).toEqual([])
  expect(drawn.statuses).toEqual([
    expect.objectContaining({
      modelId: FALLBACK,
      skippedMetricRows: 0,
      fractionalMetricSteps: true,
    }),
    expect.not.objectContaining({ fractionalMetricSteps: true }),
  ])
  expect(drawn.statuses[1]!.modelId).toBe(other)
})

test('a zip too large for the browser fails from its directory and the others open', async ({
  page,
}) => {
  const gen2 = 'i_gen2_sdk_0_6_0'
  await open(page, [HUGE_ZIP, gen2])

  const huge = artifacts.get(HUGE_ZIP)!
  const memberEnd = huge.offset + huge.size
  expect(requestsOf(HUGE_ZIP).map((request) => request.range)).toEqual([
    [memberEnd - ZIP_TAIL_BYTES, memberEnd - 1],
  ])
  const statuses = await call<{ modelId: string; error: { code: string } | null }[]>(
    page,
    'getExperimentStatuses',
  )
  expect(statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual([
    [HUGE_ZIP, 'snapshot-too-large-for-browser'],
    [gen2, null],
  ])
  const catalogs = await call<Result<unknown>[]>(page, 'getMetricCatalogs')
  expect(catalogs.map((result) => [result.modelId, result.ok])).toEqual([
    [HUGE_ZIP, false],
    [gen2, true],
  ])
  expect(await call(page, 'getTracesColumns', [HUGE_ZIP])).toEqual({
    attributes: [],
    annotations_feedback: [],
    annotations_expectations: [],
  })
  expectRangeReadsOnly(artifacts.get(gen2)!)
})
