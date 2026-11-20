import type { Page } from '@playwright/test'
import { BROWSER_NETWORK_REPORT, test, expect } from './fixtures/snapshot-error-guard'
import { build, type Plugin } from 'esbuild'
import { build as viteBuild } from 'vite'
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { dirname, extname, join, resolve } from 'node:path'
import {
  dataAnswers,
  issueLocation,
  type LoggedStorageRequest,
  newStorageState,
  respondAsStorage,
  STORAGE_PROFILES,
  type StorageHost,
  type StorageProfile,
  type StorageResponse,
  type StorageState,
} from '../../../extras/js/packages/experiments/src/providers/__tests__/helpers/storageProfiles'

// Serves fixture artifacts from a local object store that honours Range (or not, per test),
// loads them through the real snapshot worker, provider and range VFS in Chromium, and checks
// the results and the requests the worker's synchronous XHRs made.

// No retries: a flaky read is a failure here.
test.describe.configure({ retries: 0 })

const here = dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const EXPERIMENTS_SRC = resolve(here, '../../../extras/js/packages/experiments/src')
const FIXTURES_DIR = resolve(here, '../../../sdk/python/sdk/tests/fixtures/experiment_snapshots')
const WORKER_ENTRY = resolve(here, '../../../extras/js/experimentSnapshotWorker.ts')
const HARNESS_ENTRY = resolve(here, 'fixtures/experiment-snapshot-esbuild-entry.ts')
const VITE_HTML = resolve(here, 'fixtures/experiment-snapshot-vite.html')
const MAX_REQUEST = 4 * 1024 * 1024 + 64 * 1024

interface Fixture {
  name: string
  member: string
  tar: Uint8Array
  offset: number
  size: number
  expected: {
    metrics: Record<string, MetricStats>
    non_finite_metric: { name: string } | null
    traces: { trace_id: string; span_count: number }[]
    static_params: Record<string, unknown>
    datasets: Record<string, { eval_ids: string[] }>
  }
}

interface MetricStats {
  count: number
  first_step: number
  last_step: number
  first: number
  last: number
}

interface MetricSeries {
  modelId: string
  x: number[]
  y: number[]
}

interface ArtifactRequest {
  sig: string
  range: string | null
  status: number
  bytes: number
}

interface StoreState {
  ignoreRange: boolean
  /** Honour Range but answer 200 without Content-Range, as some S3-compatible stores do. */
  rangeWith200: boolean
  rejectedSigs: Set<string>
  rejectAll: boolean
  /** The next `times` artifact requests fail this way, then the store recovers. */
  failing: { failure: StoreFailure; times: number } | null
  /** Artifacts whose every request is denied, whatever URL it was signed with. */
  deniedArtifacts: Set<string>
  issued: number
  signs: number
  requests: ArtifactRequest[]
}

/** An error status, or `cut`: a 206 whose connection drops halfway through the body. */
type StoreFailure = number | 'cut'

/** Builds the platform `file_index` entry of one member of a ustar/pax archive. */
function memberRange(tar: Uint8Array, wanted: string): [number, number] {
  let offset = 0
  let paxPath: string | null = null
  const text = (start: number, length: number) => {
    const bytes = tar.subarray(start, start + length)
    const end = bytes.indexOf(0)
    return new TextDecoder().decode(end === -1 ? bytes : bytes.subarray(0, end))
  }
  while (offset + 512 <= tar.length && tar[offset] !== 0) {
    const size = parseInt(text(offset + 124, 12).trim() || '0', 8)
    const type = String.fromCharCode(tar[offset + 156] ?? 0)
    const data = offset + 512
    if (type === 'x') {
      paxPath = /(?:^|\n)\d+ path=([^\n]*)\n/.exec(text(data, size))?.[1] ?? null
    } else {
      const prefix = text(offset + 345, 155)
      const name = paxPath ?? (prefix ? `${prefix}/${text(offset, 100)}` : text(offset, 100))
      if (name === wanted) return [data, size]
      paxPath = null
    }
    offset = data + Math.ceil(size / 512) * 512
  }
  throw new Error(`${wanted} not found`)
}

function readFixture(name: string): Fixture {
  const description = JSON.parse(readFileSync(resolve(FIXTURES_DIR, `${name}.json`), 'utf-8'))
  const tar = new Uint8Array(readFileSync(resolve(FIXTURES_DIR, `${name}.tar`)))
  const [offset, size] = memberRange(tar, description.snapshot_member)
  return { name, member: description.snapshot_member, tar, offset, size, ...description }
}

const wasmUrlPlugin: Plugin = {
  name: 'wasm-url',
  setup(builder) {
    builder.onResolve({ filter: /\?url$/ }, (args) => ({ path: args.path, namespace: 'wasm-url' }))
    builder.onLoad({ filter: /.*/, namespace: 'wasm-url' }, (args) => ({
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

function serveArtifact(
  request: IncomingMessage,
  response: ServerResponse,
  fixtures: Map<string, Fixture>,
  state: StoreState,
) {
  const url = new URL(request.url!, 'http://store')
  const fixture = fixtures.get(url.pathname.slice('/artifact/'.length))!
  const sig = url.searchParams.get('sig') ?? ''
  const range = request.headers.range ?? null
  const log = (status: number, bytes: number) => state.requests.push({ sig, range, status, bytes })
  const failure = state.failing && state.failing.times-- > 0 ? state.failing.failure : null
  if (typeof failure === 'number') {
    log(failure, 0)
    response.writeHead(failure, { 'Content-Type': 'text/plain' }).end('storage error')
    return
  }
  if (state.rejectAll || state.rejectedSigs.has(sig) || state.deniedArtifacts.has(fixture.name)) {
    log(403, 0)
    response.writeHead(403).end('expired')
    return
  }
  const match = range && !state.ignoreRange ? /^bytes=(\d+)-(\d+)$/.exec(range) : null
  if (!match) {
    log(200, fixture.tar.length)
    response.writeHead(200, { 'Content-Length': fixture.tar.length }).end(fixture.tar)
    return
  }
  const start = Number(match[1])
  const end = Math.min(Number(match[2]), fixture.tar.length - 1)
  const body = fixture.tar.subarray(start, end + 1)
  if (state.rangeWith200) {
    log(200, body.length)
    response.writeHead(200, { 'Content-Length': body.length }).end(body)
    return
  }
  const headers = {
    'Content-Length': body.length,
    'Content-Range': `bytes ${start}-${end}/${fixture.tar.length}`,
  }
  if (failure === 'cut') {
    const kept = Math.floor(body.length / 2)
    log(206, kept)
    response.writeHead(206, headers)
    response.write(body.subarray(0, kept), () => response.socket?.destroy())
    return
  }
  log(206, body.length)
  response.writeHead(206, headers).end(body)
}

const RAW_FIXTURES = ['g_raw_sdk_0_5_0', 'h_raw_model_sdk_0_5_0']
const ZIPPED_FIXTURES = [
  'a_premigration_legacy_indexes',
  'a_premigration_wal_lost',
  'b_premigration',
  'c_sdk_0_1_0',
  'd_sdk_0_5_0',
  'e_baseline_quirk',
  'f_model_sdk_0_5_0',
]
const fixtures = new Map(
  [...RAW_FIXTURES, ...ZIPPED_FIXTURES].map((name) => [name, readFixture(name)]),
)
let server: Server
let origin: string
let state: StoreState
// A second origin (another port) for the cross-origin storage profiles.
let storageServer: Server
let storageOrigin: string
let storage: StorageState
let profileSigns: number

/** Serves a storage profile's object routes; false for any other path. */
function serveProfile(host: StorageHost, request: IncomingMessage, response: ServerResponse) {
  const answer = respondAsStorage(
    {
      host,
      method: request.method ?? 'GET',
      target: request.url ?? '/',
      headers: request.headers as Record<string, string | undefined>,
    },
    {
      origins: { page: origin, storage: storageOrigin },
      state: storage,
      object: (name) => fixtures.get(name)?.tar,
    },
  )
  if (!answer) return false
  writeStorageResponse(response, answer)
  return true
}

function writeStorageResponse(response: ServerResponse, answer: StorageResponse) {
  response.writeHead(answer.status, answer.headers)
  if (answer.dropAfter === undefined) {
    response.end(answer.body)
    return
  }
  // A transfer cut short: fewer bytes than Content-Length, then the connection closes.
  response.write(answer.body.subarray(0, answer.dropAfter), () => response.socket?.destroy())
}

test.beforeAll(async () => {
  const [workerJs, harnessJs] = await Promise.all([bundle(WORKER_ENTRY), bundle(HARNESS_ENTRY)])
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
    if (serveProfile('page', request, response)) return
    if (url.pathname.startsWith('/artifact/')) {
      serveArtifact(request, response, fixtures, state)
    } else if (url.pathname === '/sign-profile') {
      const profile = STORAGE_PROFILES.find((item) => item.name === url.searchParams.get('profile'))
      const artifact = url.searchParams.get('artifact') ?? ''
      if (!profile) {
        response.writeHead(404).end()
        return
      }
      const origins = { page: origin, storage: storageOrigin }
      const location = issueLocation(profile, origins, artifact, String(++profileSigns))
      response.writeHead(200, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify(location))
    } else if (url.pathname === '/sign') {
      state.signs++
      const artifact = url.searchParams.get('artifact')
      response.end(`${origin}/artifact/${artifact}?sig=${++state.issued}`)
    } else if (assets[url.pathname]) {
      const [type, body] = assets[url.pathname]!
      response.writeHead(200, { 'Content-Type': type }).end(body)
    } else {
      response.writeHead(404).end()
    }
  })
  await new Promise<void>((done) => server.listen(0, '127.0.0.1', done))
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
  storageServer = createServer((request, response) => {
    if (!serveProfile('storage', request, response)) response.writeHead(404).end()
  })
  await new Promise<void>((done) => storageServer.listen(0, '127.0.0.1', done))
  storageOrigin = `http://127.0.0.1:${(storageServer.address() as AddressInfo).port}`
})

test.afterAll(async () => {
  await new Promise((done) => server.close(done))
  await new Promise((done) => storageServer.close(done))
})

// Messages that reach the UI or the console: harness errors, chart errors, console output and
// what the worker posted. None may carry a URL's query, a path or a credential.
const LEAK = /\?\S*=|sig=|tok-\d|\/artifact\/|\/o\/|Bearer\s+\S/
let shownMessages: string[] = []
let consoleOutput: string[] = []

test.beforeEach(({ page }) => {
  shownMessages = []
  consoleOutput = []
  page.on('console', (message) => {
    if (!BROWSER_NETWORK_REPORT.test(message.text())) consoleOutput.push(message.text())
  })
  page.on('pageerror', (error) => consoleOutput.push(`${error.name}: ${error.message}`))
})

test.afterEach(async ({ page }) => {
  const harnessed = await page.evaluate(() => 'harness' in window).catch(() => false)
  let posted: string[] = []
  if (harnessed) {
    const key = await page.evaluate(async () => {
      const harness = (window as never as HarnessWindow).harness
      const catalogs = (await harness.call('getMetricCatalogs')).value as
        | { ok: boolean; value?: { metrics: { key: string }[] } }[]
        | undefined
      return catalogs?.find((item) => item.ok)?.value?.metrics[0]?.key ?? 'train_loss'
    })
    shownMessages.push(
      ...(await page.evaluate(
        (metric) => (window as never as HarnessWindow).harness.chartErrors(metric),
        key,
      )),
    )
    const statuses = (await call(page, 'getExperimentStatuses')).value as
      | { error: { message: string } | null }[]
      | undefined
    shownMessages.push(...(statuses ?? []).flatMap((status) => status.error?.message ?? []))
    posted = await page.evaluate(() => (window as never as HarnessWindow).harness.posted())
  }
  for (const text of [...shownMessages, ...consoleOutput]) expect(text).not.toMatch(LEAK)
  for (const message of posted) expect(message).not.toMatch(/sig=|tok-\d/)
})

test.beforeEach(() => {
  state = {
    ignoreRange: false,
    rangeWith200: false,
    rejectedSigs: new Set(),
    rejectAll: false,
    failing: null,
    deniedArtifacts: new Set(),
    issued: 0,
    signs: 0,
    requests: [],
  }
  storage = newStorageState()
  profileSigns = 0
})

type Settled = { ok: boolean; value?: unknown; error?: Record<string, unknown> }

async function openHarness(page: Page, names: string[], minRenewAgeMs?: number): Promise<Settled> {
  await page.goto(
    minRenewAgeMs === undefined ? origin : `${origin}/?minRenewAgeMs=${minRenewAgeMs}`,
  )
  await page.waitForFunction(() => 'harness' in window)
  return initHarness(page, names)
}

/** Initialises the harness again on the loaded page; the transport follows the member name. */
function initHarness(page: Page, names: string[], profile?: string): Promise<Settled> {
  const sources = names.map((name) => {
    const fixture = fixtures.get(name)!
    const kind = fixture.member.endsWith('.zip') ? 'zip' : 'range'
    return {
      modelId: name,
      artifact: name,
      profile,
      kind,
      offset: fixture.offset,
      size: fixture.size,
    }
  })
  return recorded(
    page.evaluate((items) => (window as never as HarnessWindow).harness.init(items), sources),
  )
}

async function recorded(settled: Promise<Settled>): Promise<Settled> {
  const result = await settled
  const message = result.error?.message
  if (typeof message === 'string') shownMessages.push(message)
  return result
}

interface HarnessWindow {
  harness: {
    init(sources: unknown[]): Promise<Settled>
    call(method: string, args?: unknown[]): Promise<Settled>
    callAfter(first: [string, unknown[]], method: string, args?: unknown[]): Promise<Settled>
    stats(): Promise<Settled>
    posted(): string[]
    statusChanges(): number
    chartErrors(key: string): Promise<string[]>
  }
}

function call(page: Page, method: string, args: unknown[] = []): Promise<Settled> {
  return recorded(
    page.evaluate(
      ([name, values]) => (window as never as HarnessWindow).harness.call(name, values),
      [method, args] as const,
    ),
  )
}

const traceParams = { limit: 10, sort_by: 'created_at', order: 'desc', search: '', filters: [] }

function expectedMetricNames(fixture: Fixture): string[] {
  const nonFinite = fixture.expected.non_finite_metric
  return [...Object.keys(fixture.expected.metrics), ...(nonFinite ? [nonFinite.name] : [])].sort()
}

test('the error guard sees errors and unhandled rejections of the page and its workers', async ({
  page,
  errors,
}) => {
  errors.expect({ kind: 'console error', text: /^guard control in a worker$/ })
  errors.expect({ kind: 'page error', text: /guard control rejection$/ })
  errors.expect({ kind: 'page error', text: /guard control worker error$/ })
  errors.expect({ kind: 'page error', text: /guard control worker rejection$/ })
  await page.goto(origin)

  const logged = page.waitForEvent('console', (message) => message.text().startsWith('guard'))
  await page.evaluate(() => {
    const script = "console.error('guard control in a worker')"
    new Worker(URL.createObjectURL(new Blob([script], { type: 'text/javascript' })))
  })
  await logged
  const rejected = page.waitForEvent('pageerror')
  await page.evaluate(() => {
    void Promise.reject(new Error('guard control rejection'))
  })
  await rejected
  // The page handles the worker's error event and stops it there; the error still counts.
  await page.evaluate(async () => {
    const script = [
      "setTimeout(() => { throw new Error('guard control worker error') })",
      "Promise.reject(new Error('guard control worker rejection'))",
    ].join('\n')
    const worker = new Worker(URL.createObjectURL(new Blob([script], { type: 'text/javascript' })))
    await new Promise((resolve) =>
      worker.addEventListener('error', (event) => resolve(event.preventDefault())),
    )
  })
  const seen = (pattern: RegExp) => errors.recorded.some((error) => pattern.test(error.text))
  await expect.poll(() => seen(/guard control worker error$/)).toBe(true)
  await expect.poll(() => seen(/guard control worker rejection$/)).toBe(true)
})

test('reads standalone and embedded raw snapshots page by page through the worker', async ({
  page,
}) => {
  const names = RAW_FIXTURES
  expect(await openHarness(page, names)).toMatchObject({ ok: true })

  const metricNames = await call(page, 'getDynamicMetricsNames')
  expect((metricNames.value as string[]).sort()).toEqual(
    expectedMetricNames(fixtures.get(names[0]!)!),
  )
  const params = await call(page, 'getStaticParamsList')
  expect(params.value).toEqual(
    names.map((name) => ({ ...fixtures.get(name)!.expected.static_params, modelId: name })),
  )
  const traces = await call(page, 'getAllTraces', [traceParams])
  expect(traces.value).toHaveLength(
    names.reduce((sum, name) => sum + fixtures.get(name)!.expected.traces.length, 0),
  )

  const stats = (await page.evaluate(() => (window as never as HarnessWindow).harness.stats()))
    .value as { transport: string; requests: number; bytesFetched: number }[]
  expect(stats.map((item) => item.transport)).toEqual(['raw-range', 'raw-range'])
  for (const [index, name] of names.entries()) {
    expect(stats[index]!.bytesFetched).toBeLessThanOrEqual(fixtures.get(name)!.size)
  }
  expect(state.requests.every((request) => request.status === 206 && request.range)).toBe(true)
  expect(state.requests.every((request) => request.bytes <= MAX_REQUEST)).toBe(true)
  // Each probe reads its member's first 64 KiB chunk, which seeds the cache, so no range read
  // starts there.
  const probeRanges = names.map((name) => {
    const { offset, size } = fixtures.get(name)!
    return `bytes=${offset}-${offset + Math.min(64 * 1024, size) - 1}`
  })
  const headerProbes = state.requests.filter((request) => probeRanges.includes(request.range ?? ''))
  expect(headerProbes).toHaveLength(names.length)
  const rangeReads = state.requests.length - headerProbes.length
  expect(rangeReads).toBe(stats.reduce((sum, item) => sum + item.requests, 0))
  expect(rangeReads).toBeLessThanOrEqual(12)
  expect(state.signs).toBe(names.length)
})

test('reads by range from a store that honours Range with status 200', async ({ page }) => {
  state.rangeWith200 = true
  const name = 'h_raw_model_sdk_0_5_0'
  const fixture = fixtures.get(name)!
  expect(await openHarness(page, [name])).toMatchObject({ ok: true })

  const traces = await call(page, 'getAllTraces', [traceParams])
  expect(traces.value).toHaveLength(fixture.expected.traces.length)
  const metricNames = await call(page, 'getDynamicMetricsNames')
  expect((metricNames.value as string[]).sort()).toEqual(expectedMetricNames(fixture))
  const [stat] = (await stats(page)).value as { transport: string; bytesFetched: number }[]
  expect(stat).toMatchObject({ transport: 'raw-range' })
  expect(stat!.bytesFetched).toBeLessThan(fixture.size)
  expect(state.requests.every((request) => request.status === 200 && request.range)).toBe(true)
  expect(state.requests.every((request) => request.bytes < fixture.tar.length)).toBe(true)
  expect(state.requests[0]).toMatchObject({ bytes: Math.min(64 * 1024, fixture.size) })
})

test('falls back to one full download when the server ignores Range', async ({ page }) => {
  state.ignoreRange = true
  const name = 'g_raw_sdk_0_5_0'
  expect(await openHarness(page, [name])).toMatchObject({ ok: true })

  const metricNames = await call(page, 'getDynamicMetricsNames')
  expect((metricNames.value as string[]).sort()).toEqual(expectedMetricNames(fixtures.get(name)!))
  const stats = await page.evaluate(() => (window as never as HarnessWindow).harness.stats())
  expect(stats.value).toEqual([expect.objectContaining({ transport: 'raw-full', requests: 0 })])
  expect(state.requests.map((request) => [request.status, request.range !== null])).toEqual([
    [200, true],
    [200, false],
  ])
})

test('a paging reset reaches the worker before the next read while a URL ages', async ({
  page,
}) => {
  const name = 'h_raw_model_sdk_0_5_0'
  await page.goto(`${origin}/?reuseMs=0`)
  await page.waitForFunction(() => 'harness' in window)
  expect(await initHarness(page, [name])).toMatchObject({ ok: true })
  const onePerPage = { ...traceParams, limit: 1 }
  const firstPage = (await call(page, 'getTraces', [onePerPage])).value
  expect((await call(page, 'getTraces', [onePerPage])).value).not.toEqual(firstPage)
  const signsBefore = state.signs

  const afterReset = await page.evaluate(
    (params) =>
      (window as never as HarnessWindow).harness.callAfter(
        ['resetTracesRequestParams', []],
        'getTraces',
        [params],
      ),
    onePerPage,
  )

  expect(state.signs).toBeGreaterThan(signsBefore)
  expect(afterReset).toMatchObject({ ok: true, value: firstPage })
})

test('an experiment loaded in full reads on without requests while its URL ages', async ({
  page,
}) => {
  state.ignoreRange = true
  const name = 'g_raw_sdk_0_5_0'
  await page.goto(`${origin}/?reuseMs=0`)
  await page.waitForFunction(() => 'harness' in window)
  expect(await initHarness(page, [name])).toMatchObject({ ok: true })
  const opened = state.requests.length

  const reads = [
    await call(page, 'getDynamicMetricsNames'),
    await call(page, 'getAllTraces', [traceParams]),
    await call(page, 'getMetricCatalogs'),
  ]

  expect(reads.map((read) => read.ok)).toEqual([true, true, true])
  expect(state.requests.length).toBe(opened)
})

test('a comparison member denied after open is reported, the others load, exports reject', async ({
  page,
}) => {
  const [healthy, denied] = RAW_FIXTURES as [string, string]
  expect(await openHarness(page, RAW_FIXTURES)).toMatchObject({ ok: true })
  state.deniedArtifacts.add(denied)

  const onScreen = await call(page, 'getTraces', [{ ...traceParams, limit: 1000 }])
  const changes = await page.evaluate(() =>
    (window as never as HarnessWindow).harness.statusChanges(),
  )
  const statuses = (await call(page, 'getExperimentStatuses')).value as {
    modelId: string
    error: { code: string } | null
  }[]
  const exported = await call(page, 'getAllTraces', [traceParams])

  expect(onScreen.ok).toBe(true)
  expect(onScreen.value).toHaveLength(fixtures.get(healthy)!.expected.traces.length)
  expect(changes).toBe(1)
  expect(statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual([
    [healthy, null],
    [denied, 'snapshot-source-expired'],
  ])
  expect(exported).toMatchObject({
    ok: false,
    error: { code: 'snapshot-source-expired', modelId: denied },
  })
})

test('renews an expired URL once and retries the failed call', async ({ page }) => {
  const name = 'h_raw_model_sdk_0_5_0'
  expect(await openHarness(page, [name])).toMatchObject({ ok: true })
  state.rejectedSigs.add('1')
  const before = state.requests.length

  const traces = await call(page, 'getAllTraces', [traceParams])
  const evals = await call(page, 'getAllDatasetEvals', [
    { dataset_id: 'qa_set', sort_by: 'created_at', order: 'asc', search: '', filters: [] },
  ])

  expect(traces).toMatchObject({ ok: true })
  expect(traces.value).toHaveLength(fixtures.get(name)!.expected.traces.length)
  expect(evals).toMatchObject({ ok: true })
  const later = state.requests.slice(before)
  expect(later.filter((request) => request.status === 403)).toHaveLength(1)
  expect(later.filter((request) => request.status === 206).every((r) => r.sig === '2')).toBe(true)
  expect(state.signs).toBe(2)
})

test('surfaces a source error without looping when the renewed URL fails too', async ({ page }) => {
  const name = 'g_raw_sdk_0_5_0'
  expect(await openHarness(page, [name])).toMatchObject({ ok: true })
  state.rejectAll = true
  const before = state.requests.length

  const traces = await call(page, 'getAllTraces', [traceParams])
  await page.waitForTimeout(300)

  expect(traces).toMatchObject({
    ok: false,
    error: { code: 'snapshot-source-expired', modelId: name },
  })
  expect(state.requests.slice(before).map((request) => request.status)).toEqual([403, 403])
  expect(state.signs).toBe(2)
})

test('fails for good after one full download when the storage stops honouring Range', async ({
  page,
}) => {
  const name = 'g_raw_sdk_0_5_0'
  expect(await openHarness(page, [name])).toMatchObject({ ok: true })
  state.ignoreRange = true
  const before = state.requests.length

  const first = await call(page, 'getAllTraces', [traceParams])
  const second = await call(page, 'getDynamicMetricData', ['train_loss'])
  const third = await call(page, 'getAllDatasetEvals', [
    { dataset_id: 'qa_set', sort_by: 'created_at', order: 'asc', search: '', filters: [] },
  ])

  for (const result of [first, second, third]) {
    expect(result).toMatchObject({
      ok: false,
      error: { code: 'snapshot-range-unsupported', modelId: name },
    })
  }
  expect(state.requests.slice(before).map((request) => request.status)).toEqual([200])
  expect(state.signs).toBe(1)
})

function stats(page: Page): Promise<Settled> {
  return page.evaluate(() => (window as never as HarnessWindow).harness.stats())
}

function evalParams(datasetId: string) {
  return { dataset_id: datasetId, sort_by: 'created_at', order: 'asc', search: '', filters: [] }
}

function expectSeries(series: MetricSeries, modelId: string, metric: MetricStats) {
  expect(series.modelId).toBe(modelId)
  expect(series.x).toHaveLength(metric.count)
  expect([series.x[0], series.x.at(-1)]).toEqual([metric.first_step, metric.last_step])
  expect([series.y[0], series.y.at(-1)]).toEqual([metric.first, metric.last])
}

async function expectZippedSnapshot(page: Page, fixture: Fixture) {
  const { name, expected } = fixture
  expect((await stats(page)).value).toEqual([
    expect.objectContaining({ modelId: name, transport: 'zip-full', requests: 0 }),
  ])
  const metricNames = await call(page, 'getDynamicMetricsNames')
  expect((metricNames.value as string[]).sort()).toEqual(expectedMetricNames(fixture))
  const [metricName, metric] = Object.entries(expected.metrics)[0] ?? []
  if (metricName && metric) {
    const series = (await call(page, 'getDynamicMetricData', [metricName])).value as MetricSeries[]
    expect(series).toHaveLength(1)
    expectSeries(series[0]!, name, metric)
  }
  expect((await call(page, 'getStaticParamsList')).value).toEqual([
    { ...expected.static_params, modelId: name },
  ])
  const traces = (await call(page, 'getAllTraces', [traceParams])).value as {
    trace_id: string
    span_count: number
  }[]
  const spanCounts = (items: { trace_id: string; span_count: number }[]) =>
    items.map(({ trace_id, span_count }) => [trace_id, span_count]).sort()
  expect(spanCounts(traces)).toEqual(spanCounts(expected.traces))
  for (const [datasetId, dataset] of Object.entries(expected.datasets)) {
    const evals = await call(page, 'getAllDatasetEvals', [evalParams(datasetId)])
    expect((evals.value as { id: string }[]).map((item) => item.id).sort()).toEqual(
      [...dataset.eval_ids].sort(),
    )
  }
}

async function expectZippedAndRangeSnapshotsTogether(page: Page) {
  const names = ['d_sdk_0_5_0', 'h_raw_model_sdk_0_5_0']
  const expectedOf = (name: string) => fixtures.get(name)!.expected
  expect(await initHarness(page, names)).toMatchObject({ ok: true })

  expect((await stats(page)).value).toEqual([
    expect.objectContaining({ modelId: names[0], transport: 'zip-full' }),
    expect.objectContaining({ modelId: names[1], transport: 'raw-range' }),
  ])
  const series = (await call(page, 'getDynamicMetricData', ['train_loss'])).value as MetricSeries[]
  expect(series).toHaveLength(names.length)
  for (const [index, name] of names.entries()) {
    expectSeries(series[index]!, name, expectedOf(name).metrics.train_loss!)
  }
  expect((await call(page, 'getStaticParamsList')).value).toEqual(
    names.map((name) => ({ ...expectedOf(name).static_params, modelId: name })),
  )
  const traces = await call(page, 'getAllTraces', [traceParams])
  expect(traces.value).toHaveLength(
    names.reduce((sum, name) => sum + expectedOf(name).traces.length, 0),
  )
  const evals = await call(page, 'getAllDatasetEvals', [evalParams('qa_set')])
  expect(
    (evals.value as { id: string; modelId: string }[]).map((item) => item.modelId).sort(),
  ).toEqual(
    names.flatMap((name) => expectedOf(name).datasets.qa_set!.eval_ids.map(() => name)).sort(),
  )
}

const CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.wasm': 'application/wasm',
}

test('the worker as Vite builds it loads its wasm and reads range and zipped sources', async ({
  page,
}) => {
  test.setTimeout(180_000)
  const outDir = mkdtempSync(join(tmpdir(), 'experiment-snapshot-vite-'))
  try {
    await viteBuild({
      configFile: resolve(here, '../../vite.config.ts'),
      root: dirname(VITE_HTML),
      logLevel: 'silent',
      build: { outDir, emptyOutDir: true, rollupOptions: { input: VITE_HTML } },
    })
    const servedPaths: string[] = []
    const built = createServer((request, response) => {
      const url = new URL(request.url!, 'http://store')
      servedPaths.push(url.pathname)
      if (url.pathname.startsWith('/artifact/') || url.pathname === '/sign') {
        server.emit('request', request, response)
        return
      }
      const file = url.pathname === '/' ? '/experiment-snapshot-vite.html' : url.pathname
      try {
        const body = readFileSync(join(outDir, file))
        response
          .writeHead(200, {
            'Content-Type': CONTENT_TYPES[extname(file)] ?? 'application/octet-stream',
            // The dev server's isolation headers: they enable the OPFS VFS unless it is disabled.
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Embedder-Policy': 'require-corp',
          })
          .end(body)
      } catch {
        response.writeHead(404).end()
      }
    })
    await new Promise<void>((done) => built.listen(0, '127.0.0.1', done))
    const builtOrigin = `http://127.0.0.1:${(built.address() as AddressInfo).port}`
    const savedOrigin = origin
    origin = builtOrigin
    try {
      const name = 'g_raw_sdk_0_5_0'
      expect(await openHarness(page, [name])).toMatchObject({ ok: true })
      expect(await page.evaluate(() => crossOriginIsolated)).toBe(true)

      const metricNames = await call(page, 'getDynamicMetricsNames')
      expect((metricNames.value as string[]).sort()).toEqual(
        expectedMetricNames(fixtures.get(name)!),
      )
      const stats = await page.evaluate(() => (window as never as HarnessWindow).harness.stats())
      expect(stats.value).toEqual([expect.objectContaining({ transport: 'raw-range' })])
      expect(servedPaths.some((path) => /sqlite3.*\.wasm$/.test(path))).toBe(true)
      expect(servedPaths.filter((path) => /opfs|worker1/.test(path))).toEqual([])

      for (const zipped of ZIPPED_FIXTURES) {
        await test.step(`reads the zipped snapshot ${zipped}`, async () => {
          expect(await initHarness(page, [zipped])).toMatchObject({ ok: true })
          await expectZippedSnapshot(page, fixtures.get(zipped)!)
        })
      }
      await test.step('reads a zipped and a range snapshot in one provider', () =>
        expectZippedAndRangeSnapshotsTogether(page))
    } finally {
      origin = savedOrigin
      await new Promise((done) => built.close(done))
    }
  } finally {
    rmSync(outDir, { recursive: true, force: true })
  }
})

// Storage profiles (helpers/storageProfiles.ts, shared with vitest's memory transport), each on
// the page's origin or on a second one, through real Chromium preflights and redirects.
const PROFILE_FIXTURE = 'h_raw_model_sdk_0_5_0'
const CHUNK = 64 * 1024

function profileAnswers(from = 0) {
  return dataAnswers(storage.log.slice(from))
}

// Firefox adds an RFC 9218 `Priority` header to every request; it is the browser's, not ours.
const BROWSER_HEADERS = new Set(['priority'])

function appHeaders(entry: LoggedStorageRequest | undefined): string[] | undefined {
  return entry?.extraHeaders.filter((name) => !BROWSER_HEADERS.has(name))
}

function preflightCount() {
  return storage.log.filter((entry) => entry.method === 'OPTIONS').length
}

async function openProfile(page: Page, profile: StorageProfile): Promise<Settled> {
  if (profile.auth === 'session-cookie') {
    await page
      .context()
      .addCookies([{ name: 'luml_session', value: '1', domain: '127.0.0.1', path: '/' }])
  }
  await page.goto(origin)
  await page.waitForFunction(() => 'harness' in window)
  return initHarness(page, [PROFILE_FIXTURE], profile.name)
}

/** Preflights expected per session: Chromium caches one per URL for Access-Control-Max-Age. */
function expectPreflights(profile: StorageProfile, browserName: string) {
  const needed = profile.auth === 'bearer' && profile.host === 'storage'
  // Firefox and WebKit also preflight the cross-origin hop of a redirected request that carried
  // Authorization (the hop itself goes without it), once per hop URL for the Max-Age.
  if (browserName !== 'chromium' && profile.redirect && profile.auth === 'bearer') {
    const hops = storage.log.filter((entry) => entry.method === 'GET' && entry.host === 'storage')
    expect(preflightCount()).toBe(new Set(hops.map((entry) => entry.credential)).size)
    return
  }
  // Without a Max-Age Chromium keeps a preflight for 5 s, which a slow run can outlast.
  if (needed && profile.preflightMaxAge === null) expect(preflightCount()).toBeGreaterThan(0)
  else expect(preflightCount()).toBe(needed ? 1 : 0)
}

const rangeProfiles = STORAGE_PROFILES.filter((profile) => profile.expected === 'raw-range')

for (const profile of rangeProfiles) {
  test(`${profile.name}: opens, renews once and reads by range`, async ({ page, browserName }) => {
    const fixture = fixtures.get(PROFILE_FIXTURE)!
    expect(await openProfile(page, profile)).toMatchObject({ ok: true })

    await test.step('opens by range with only the headers the storage asked for', async () => {
      const statuses = await call(page, 'getExperimentStatuses')
      expect(statuses.value).toEqual([
        expect.objectContaining({ transport: 'raw-range', transportFallback: null }),
      ])
      expect(profileAnswers()[0]).toMatchObject({
        range: `bytes=${fixture.offset}-${fixture.offset + CHUNK - 1}`,
      })
      const firstGet = storage.log.find((entry) => entry.method === 'GET')
      expect(appHeaders(firstGet)).toEqual(profile.auth === 'bearer' ? ['authorization'] : [])
    })

    await test.step('renews an expired source once and retries', async () => {
      storage.revoked.add('1')
      const before = storage.log.length
      const traces = await call(page, 'getAllTraces', [traceParams])
      expect(traces.value).toHaveLength(fixture.expected.traces.length)
      const later = profileAnswers(before)
      expect(later.filter((entry) => entry.status === profile.expired.status)).toHaveLength(1)
      expect(later.length).toBeGreaterThan(1)
      expect(later.slice(1).every((entry) => entry.credential === '2')).toBe(true)
      expect(profileSigns).toBe(2)
    })

    await test.step('reads the catalog and a multi-chunk set of evals', async () => {
      const [catalog] = (await call(page, 'getMetricCatalogs')).value as { ok: boolean }[]
      expect(catalog).toMatchObject({ ok: true })
      const evals = await call(page, 'getAllDatasetEvals', [evalParams('qa_set')])
      expect(evals).toMatchObject({ ok: true })
      const [stat] = (await stats(page)).value as { requests: number; cacheMisses: number }[]
      expect(stat!.cacheMisses).toBeGreaterThanOrEqual(2)
      const answers = profileAnswers().filter((entry) => entry.status < 300)
      expect(answers).toHaveLength(1 + stat!.requests)
      const status = profile.rangeAnswer === 200 ? 200 : 206
      expect(answers.every((entry) => entry.status === status)).toBe(true)
      expect(answers.every((entry) => entry.bytes < fixture.tar.length)).toBe(true)
    })

    expectPreflights(profile, browserName)
  })

  test(`${profile.name}: surfaces a permanent failure without looping`, async ({ page }) => {
    expect(await openProfile(page, profile)).toMatchObject({ ok: true })
    storage.rejectAll = true
    const before = storage.log.length

    const traces = await call(page, 'getAllTraces', [traceParams])
    await page.waitForTimeout(200)

    expect(traces).toMatchObject({ ok: false, error: { code: 'snapshot-source-expired' } })
    expect(profileAnswers(before).map((entry) => entry.status)).toEqual([
      profile.expired.status,
      profile.expired.status,
    ])
    expect(profileSigns).toBe(2)
  })
}

for (const profile of rangeProfiles.filter((item) => item.rangeMayStop)) {
  test(`${profile.name}: fails for good after one whole answer when Range stops`, async ({
    page,
  }) => {
    const fixture = fixtures.get(PROFILE_FIXTURE)!
    expect(await openProfile(page, profile)).toMatchObject({ ok: true })
    storage.ignoreRange = true
    const before = storage.log.length

    const results = [
      await call(page, 'getAllTraces', [traceParams]),
      await call(page, 'getAllDatasetEvals', [evalParams('qa_set')]),
    ]

    for (const result of results) {
      expect(result).toMatchObject({ ok: false, error: { code: 'snapshot-range-unsupported' } })
    }
    expect(profileAnswers(before).map((entry) => entry.bytes)).toEqual([fixture.tar.length])
    expect(profileSigns).toBe(1)
  })
}

for (const profile of STORAGE_PROFILES.filter((item) => item.expected === 'raw-full')) {
  test(`${profile.name}: loads whole once, says why, renews once and fails cleanly`, async ({
    page,
  }) => {
    const fixture = fixtures.get(PROFILE_FIXTURE)!

    await test.step('falls back to one full download and reports the reason', async () => {
      expect(await openProfile(page, profile)).toMatchObject({ ok: true })
      expect((await call(page, 'getExperimentStatuses')).value).toEqual([
        expect.objectContaining({ transport: 'raw-full', transportFallback: 'range-ignored' }),
      ])
      const traces = await call(page, 'getAllTraces', [traceParams])
      expect(traces.value).toHaveLength(fixture.expected.traces.length)
      expect(profileAnswers().map((entry) => [entry.status, entry.range !== null])).toEqual([
        [200, true],
        [200, false],
      ])
    })

    await test.step('renews a source that expired before open once', async () => {
      storage.revoked.add(String(profileSigns + 1))
      await page.goto(origin)
      await page.waitForFunction(() => 'harness' in window)
      const before = storage.log.length
      expect(await initHarness(page, [PROFILE_FIXTURE], profile.name)).toMatchObject({
        ok: true,
      })
      expect(profileAnswers(before).map((entry) => entry.status)).toEqual([
        profile.expired.status,
        200,
        200,
      ])
    })

    await test.step('surfaces a permanent failure at open without looping', async () => {
      storage.rejectAll = true
      await page.goto(origin)
      await page.waitForFunction(() => 'harness' in window)
      const before = storage.log.length
      const signs = profileSigns
      const opened = await initHarness(page, [PROFILE_FIXTURE], profile.name)
      expect(opened).toMatchObject({ ok: true })
      expect((await call(page, 'getExperimentStatuses')).value).toEqual([
        expect.objectContaining({
          error: expect.objectContaining({ code: 'snapshot-source-expired' }),
        }),
      ])
      expect(profileAnswers(before)).toHaveLength(2)
      expect(profileSigns).toBe(signs + 2)
    })
    expect(preflightCount()).toBe(0)
  })
}

for (const profile of STORAGE_PROFILES.filter((item) => item.expected === 'redirect-error')) {
  test(`${profile.name}: a redirect that drops the token fails with a typed error`, async ({
    page,
  }) => {
    const opened = await openProfile(page, profile)

    expect(opened).toMatchObject({ ok: true })
    expect((await call(page, 'getExperimentStatuses')).value).toEqual([
      expect.objectContaining({
        error: expect.objectContaining({ code: 'snapshot-source-redirect' }),
      }),
    ])
    expect(
      storage.log
        .filter((entry) => entry.method === 'GET')
        .map((entry) => [entry.host, entry.status, appHeaders(entry)]),
    ).toEqual([
      ['page', 307, ['authorization']],
      ['storage', 401, []],
    ])
    expect(profileSigns).toBe(1)
  })
}

for (const profile of STORAGE_PROFILES.filter((item) => item.expected === 'network-error')) {
  test(`${profile.name}: a storage the browser refuses fails cleanly after one renewal`, async ({
    page,
  }) => {
    const opened = await openProfile(page, profile)
    await page.waitForTimeout(200)

    expect(opened).toMatchObject({ ok: true })
    expect((await call(page, 'getExperimentStatuses')).value).toEqual([
      expect.objectContaining({
        error: { code: 'snapshot-source-expired', message: 'Snapshot request failed: TypeError' },
      }),
    ])
    expect(storage.log.map((entry) => [entry.method, entry.credential])).toEqual([
      ['GET', '1'],
      ['GET', '2'],
    ])
    expect(profileSigns).toBe(2)
  })
}

test.describe('a storage that cuts a range transfer short mid-file', () => {
  const profile = STORAGE_PROFILES.find((item) => item.name === 'azure')!

  test('a short 206 is rejected for good, never read as zero-filled pages', async ({ page }) => {
    const fixture = fixtures.get(PROFILE_FIXTURE)!
    expect(await openProfile(page, profile)).toMatchObject({ ok: true })
    storage.truncateFrom = fixture.offset + CHUNK
    const before = storage.log.length

    const traces = await call(page, 'getAllTraces', [traceParams])
    const evals = await call(page, 'getAllDatasetEvals', [evalParams('qa_set')])

    for (const result of [traces, evals]) {
      expect(result).toMatchObject({ ok: false, error: { code: 'snapshot-range-unsupported' } })
    }
    expect(profileAnswers(before)).toHaveLength(1)
    expect(profileSigns).toBe(1)
  })

  test('a dropped connection is a failed request: one renewal, then a clean error', async ({
    page,
  }) => {
    const fixture = fixtures.get(PROFILE_FIXTURE)!
    expect(await openProfile(page, profile)).toMatchObject({ ok: true })
    storage.truncateFrom = fixture.offset + CHUNK
    storage.truncation = 'dropped'
    const before = storage.log.length

    const traces = await call(page, 'getAllTraces', [traceParams])

    expect(traces).toMatchObject({ ok: false, error: { code: 'snapshot-source-expired' } })
    expect(profileAnswers(before)).toHaveLength(2)
    expect(profileSigns).toBe(2)
  })
})

// Storage errors other than an expired URL. Every failed request is renewed once and retried
// (httpSource.ts, ExperimentSnapshotWorkerProxy.ts); a second failure surfaces as a source error,
// and a read after the storage recovers succeeds.
test.describe('a storage that fails requests', () => {
  const name = 'h_raw_model_sdk_0_5_0'
  const FAILURES: { label: string; failure: StoreFailure; atOpen: string; atRead: string }[] = [
    ...[404, 500, 503, 403].map((status) => ({
      label: `status ${status}`,
      failure: status,
      atOpen: `Snapshot header request returned status ${status}`,
      atRead: `Snapshot range read failed: Range request returned status ${status}`,
    })),
    {
      label: 'a connection dropped mid-body',
      failure: 'cut',
      atOpen: 'Snapshot request failed: TypeError',
      atRead: 'Snapshot range read failed: NetworkError',
    },
  ]
  /** The status the store logged for a failed request: a cut one started as a 206. */
  const loggedStatus = (failure: StoreFailure) => (failure === 'cut' ? 206 : failure)

  async function statusOf(page: Page) {
    const [status] = (await call(page, 'getExperimentStatuses')).value as {
      transport: string
      error: { code: string; message: string } | null
    }[]
    return status
  }

  async function expectTracesLoad(page: Page) {
    const traces = await call(page, 'getAllTraces', [traceParams])
    expect(traces.value).toHaveLength(fixtures.get(name)!.expected.traces.length)
  }

  for (const { label, failure, atOpen, atRead } of FAILURES) {
    test(`${label} at open: one renewal, a clean error, and a new open works`, async ({ page }) => {
      state.failing = { failure, times: Infinity }

      expect(await openHarness(page, [name])).toMatchObject({ ok: true })

      expect(await statusOf(page)).toMatchObject({
        error: { code: 'snapshot-source-expired', message: atOpen },
      })
      expect(state.requests.map((request) => request.status)).toEqual([
        loggedStatus(failure),
        loggedStatus(failure),
      ])
      expect(state.signs).toBe(2)

      state.failing = null
      expect(await initHarness(page, [name])).toMatchObject({ ok: true })
      expect(await statusOf(page)).toMatchObject({ transport: 'raw-range', error: null })
      await expectTracesLoad(page)
    })

    test(`${label} on a later read: one renewal, a clean error, and the next read works`, async ({
      page,
    }) => {
      expect(await openHarness(page, [name])).toMatchObject({ ok: true })
      state.failing = { failure, times: Infinity }
      const before = state.requests.length

      const traces = await call(page, 'getAllTraces', [traceParams])

      expect(traces).toMatchObject({
        ok: false,
        error: { code: 'snapshot-source-expired', modelId: name, message: atRead },
      })
      expect(state.requests.slice(before).map((request) => request.status)).toEqual([
        loggedStatus(failure),
        loggedStatus(failure),
      ])
      expect(state.signs).toBe(2)

      state.failing = null
      await expectTracesLoad(page)
      expect(state.signs).toBe(2)
    })
  }

  for (const { label, failure } of FAILURES.filter((item) => item.failure !== 404)) {
    test(`${label} once at open is renewed and the experiment opens`, async ({ page }) => {
      state.failing = { failure, times: 1 }

      expect(await openHarness(page, [name])).toMatchObject({ ok: true })

      expect(await statusOf(page)).toMatchObject({ transport: 'raw-range', error: null })
      await expectTracesLoad(page)
      expect(state.requests[0]).toMatchObject({ sig: '1', status: loggedStatus(failure) })
      expect(state.requests.slice(1).every((request) => request.sig === '2')).toBe(true)
      expect(state.signs).toBe(2)
    })

    test(`${label} once on a later read is renewed and the read succeeds`, async ({ page }) => {
      expect(await openHarness(page, [name])).toMatchObject({ ok: true })
      state.failing = { failure, times: 1 }
      const before = state.requests.length

      await expectTracesLoad(page)

      const later = state.requests.slice(before)
      expect(later[0]).toMatchObject({ sig: '1', status: loggedStatus(failure) })
      expect(later.slice(1).every((request) => request.sig === '2' && request.status === 206)).toBe(
        true,
      )
      expect(state.signs).toBe(2)
    })
  }

  // The platform does not renew a URL younger than 30 s: the renewal hands it back, and a
  // transient failure is sent once more with it, without asking the backend again.
  const YOUNG_URL_AGE_MS = 30_000
  for (const { label, failure } of FAILURES.filter(
    (item) => item.failure !== 404 && item.failure !== 403,
  )) {
    test(`${label} once at open with a young URL is retried with it and the experiment opens`, async ({
      page,
    }) => {
      state.failing = { failure, times: 1 }

      expect(await openHarness(page, [name], YOUNG_URL_AGE_MS)).toMatchObject({ ok: true })

      expect(await statusOf(page)).toMatchObject({ transport: 'raw-range', error: null })
      await expectTracesLoad(page)
      expect(state.requests[0]).toMatchObject({ sig: '1', status: loggedStatus(failure) })
      expect(state.requests.every((request) => request.sig === '1')).toBe(true)
      expect(state.signs).toBe(1)
    })

    test(`${label} once on a later read with a young URL is retried with it and succeeds`, async ({
      page,
    }) => {
      expect(await openHarness(page, [name], YOUNG_URL_AGE_MS)).toMatchObject({ ok: true })
      state.failing = { failure, times: 1 }
      const before = state.requests.length

      await expectTracesLoad(page)

      const later = state.requests.slice(before)
      expect(later[0]).toMatchObject({ sig: '1', status: loggedStatus(failure) })
      expect(later.slice(1).every((request) => request.sig === '1' && request.status === 206)).toBe(
        true,
      )
      expect(state.signs).toBe(1)
    })
  }

  test('status 500 at open with a young URL fails cleanly after one retry with it', async ({
    page,
  }) => {
    state.failing = { failure: 500, times: Infinity }

    expect(await openHarness(page, [name], YOUNG_URL_AGE_MS)).toMatchObject({ ok: true })

    expect(await statusOf(page)).toMatchObject({ error: { code: 'snapshot-source-expired' } })
    expect(state.requests.map((request) => [request.sig, request.status])).toEqual([
      ['1', 500],
      ['1', 500],
    ])
    expect(state.signs).toBe(1)
  })

  test('status 403 at open with a young URL fails at once, without a retry', async ({ page }) => {
    state.failing = { failure: 403, times: Infinity }

    expect(await openHarness(page, [name], YOUNG_URL_AGE_MS)).toMatchObject({ ok: true })

    expect(await statusOf(page)).toMatchObject({ error: { code: 'snapshot-source-expired' } })
    expect(state.requests.map((request) => request.status)).toEqual([403])
    expect(state.signs).toBe(1)
  })
})
