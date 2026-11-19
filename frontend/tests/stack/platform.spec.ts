import type { BrowserContext, Locator, Page, Request, Response } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { PRESIGNED_URL_MIN_RENEW_AGE_MS } from '../../src/lib/bucket-service/presigned-url-cache'
import { ERROR_TOAST, expect, test } from './error_guard'
import {
  SLOW_LINK,
  ThrottleProxy,
  VERY_SLOW_LINK,
  type ProxiedRequest,
  type ProxyConfig,
} from './proxy'
import {
  clickFirstTrace,
  durationText,
  expectAverageScores,
  expectLargeValue,
  expectRegularTrace,
  expectTracesSortedAndPaged,
  expectVirtualisedTree,
  openTrace,
  rowCells,
  runLeftTimers,
  scoreTexts,
  searchEval,
  sortLongestFirst,
  spanAttribute,
  spanRow,
  traceDialog,
  traceFilterFields,
  traceRows,
  type TraceData,
} from './trace_view'
import {
  applyFilter,
  expectChartOfLoggedValues,
  exportedCsv,
  feedbackCsv,
  feedbackText,
  navigateInApp,
  staticParameters,
  tableToolbar,
  type LoggedExperiment,
} from './platform_checks'

// The platform end to end: the real backend, Postgres, Redis and object storage (MinIO through
// an S3 bucket secret, Azurite through an Azure one), the frontend built from this worktree,
// and experiments written by this SDK (and released luml-sdk 0.5.0) published with this API
// client. Asserts what is on screen and what went over the network.

interface PublishedArtifact {
  id: string
  name: string
  kind: 'experiment' | 'model'
  generation: 1 | 2
  member: string
  offset: number
  size: number
  file_size: number
  /** The object key in the bucket; storage requests are matched to artifacts by it. */
  bucket_location: string
  /** Object bytes [first, last] of the 1 MiB span attribute value (traces_new only). */
  payload_region: [number, number] | null
  /** The same for the 100 KiB value. */
  medium_region: [number, number] | null
}

interface ExpectedEval {
  id: string
  question: string
  answer: string
  expected: string
  scores: { accuracy: number; passed: boolean; tokens: number }
  correct: boolean | null
}

interface ExpectedTrace {
  id: string
  execution_time_ns: number
  status: number
  span_count: number
  eval_id: string
  tier: string
  helpful: boolean
}

interface FixtureExpectation {
  user_version: number
  metrics: Record<
    string,
    {
      count: number
      first_step: number
      last_step: number
      first: number
      last: number
      min: number
      max: number
    }
  >
  dataset: string
  eval_ids: string[]
  average_scores: Record<string, number>
}

/** platform_expected.py: logged values and what searches and filters leave. */
interface ExpectedData {
  experiments: Record<'new_a' | 'new_b' | 'old', LoggedExperiment>
  evals: ExpectedEval[]
  eval_search: { text: string; ids: string[]; averages: Record<string, number> }
  eval_filter: { min_tokens: number; ids: string[]; averages: Record<string, number> }
  traces: ExpectedTrace[]
  trace_filter: { tier: string; ids: string[] }
  fixtures: Record<OldEra, FixtureExpectation>
}

type OldEra = 'rev0' | 'rev0_legacy_indexes' | 'sdk_0_1_0' | 'baseline_quirk'

interface StorageData {
  bucket_secret_id: string
  orbit_id: string
  collection_id: string
  artifacts: Record<string, PublishedArtifact>
}

interface PlatformData {
  organization_id: string
  old_source: string
  large: { keys: string[]; points_per_key: number }
  regular_steps: number
  short_steps: number
  twin_key: string
  traces: TraceData
  expected: ExpectedData
  storages: Record<string, StorageData>
  /** The same storages through their delaying proxies (throttle_proxy.mjs), fewer artifacts. */
  proxied: Record<string, StorageData>
}

interface StorageRequest {
  artifactId: string
  range: [number, number] | null
  status: number
  bytes: number
  /** From sending the request to its first byte, as the browser measured it. */
  firstByteMs: number
  /** To the last byte; NaN for a read the viewer cancelled. */
  elapsedMs: number
}

interface ChartLine {
  modelId: string
  x: number[]
  y: (number | null)[]
}

const env = (name: string): string => {
  const value = process.env[name]
  if (!value) throw new Error(`${name} is not set; run the suite through run.sh`)
  return value
}

const FRONTEND = env('E2E_FRONTEND_URL')
const data = JSON.parse(
  readFileSync(join(env('E2E_WORK_DIR'), 'platform.json'), 'utf-8'),
) as PlatformData
const PROXIES = {
  s3: new ThrottleProxy(env('E2E_MINIO_PROXY_PORT')),
  azure: new ThrottleProxy(env('E2E_AZURITE_PROXY_PORT')),
}
const STORAGE_PORTS = [
  env('E2E_MINIO_PORT'),
  env('E2E_AZURITE_PORT'),
  ...Object.values(PROXIES).map((proxy) => proxy.port),
]
const DOWNLOAD_URL = /\/artifacts\/([0-9a-f-]+)\/download-url/

interface ReadBudget {
  requests: number
  bytes: number
}

// Reads of new-format DBs, in read-ahead chunks of 64 KiB: a view reads the catalog, one level
// of buckets and the B-tree pages on the way, however many points the DB holds, so the limits
// are in bytes, not in a share of the DB. Each is the value measured in 10 runs on S3 and on
// Azure (the same in every run) plus one chunk: one more request of read-ahead.
const READ_AHEAD_CHUNK = 64 * 1024
function measuredPlusOneChunk(requests: number, bytes: number): ReadBudget {
  return { requests: requests + 1, bytes: bytes + READ_AHEAD_CHUNK }
}
// `large` (3 metrics of 1M points) opened: 8 requests, 524,290 bytes (0.65% of it).
const FIRST_PAINT_BUDGET = measuredPlusOneChunk(8, 524_290)
// Its chart zoomed to 2% of the axis: 2 requests, 196,608 bytes.
const ZOOM_BUDGET = measuredPlusOneChunk(2, 196_608)
// Each new-format experiment of a comparison, by label, whatever it is compared with. A small DB
// is mostly its catalog and first pages, so the share it reads is high: of its member, new_a
// and new_b 72%, short 59%, gen2_full 78% and model_gen2 all of it; large 0.49%.
const COMPARISON_ITEM_BUDGETS: Record<string, ReadBudget> = {
  new_a: measuredPlusOneChunk(5, 458_752),
  new_b: measuredPlusOneChunk(5, 458_752),
  large: measuredPlusOneChunk(5, 393_216),
  short: measuredPlusOneChunk(4, 327_680),
  gen2_full: measuredPlusOneChunk(9, 688_128),
  model_gen2: measuredPlusOneChunk(9, 655_360),
}

function expectWithinBudget(requests: StorageRequest[], budget: ReadBudget, what: string) {
  expect(requests.length, `${what}: requests`).toBeLessThanOrEqual(budget.requests)
  expect(sumBytes(requests), `${what}: bytes`).toBeLessThanOrEqual(budget.bytes)
}

/** Every request to storage and to the download-url endpoint, by artifact, with sizes. */
class NetworkLog {
  storage: StorageRequest[] = []
  urlIssues: string[] = []
  /** Storage reads sent and not finished yet; each resolves once its entry is complete. */
  private readonly pending = new Set<Promise<void>>()

  constructor(
    context: BrowserContext,
    private readonly artifacts: Record<string, PublishedArtifact>,
  ) {
    const entries = new Map<Request, StorageRequest>()
    const finishers = new Map<Request, () => void>()
    const logging = new Map<Request, Promise<void>>()
    context.on('request', (request) => {
      if (!isStorageRead(request)) return
      const finished = new Promise<void>((resolve) => finishers.set(request, resolve))
      // 'response' comes before 'requestfinished' and 'requestfailed', so its entry is known.
      const settled = finished.then(() => logging.get(request))
      this.pending.add(settled)
      void settled.then(() => this.pending.delete(settled))
    })
    const finish = (request: Request) => finishers.get(request)?.()
    context.on('requestfinished', finish)
    context.on('requestfailed', finish)
    const record = async (response: Response) => {
      const url = new URL(response.url())
      const artifact = Object.values(this.artifacts).find((item) =>
        decodeURIComponent(url.pathname).endsWith(`/${item.bucket_location}`),
      )
      const entry: StorageRequest = {
        artifactId: artifact?.id ?? url.pathname,
        range: null,
        status: response.status(),
        bytes: 0,
        firstByteMs: response.request().timing().responseStart,
        elapsedMs: NaN,
      }
      entries.set(response.request(), entry)
      const header = (await response.request().allHeaders())['range']
      const match = header ? /^bytes=(\d+)-(\d+)$/.exec(header) : null
      const length = Number(response.headers()['content-length'] ?? NaN)
      entry.range = match ? [Number(match[1]), Number(match[2])] : null
      entry.bytes = Number.isFinite(length) ? length : 0
      this.storage.push(entry)
    }
    context.on('response', (response) => {
      const issued = DOWNLOAD_URL.exec(new URL(response.url()).pathname)
      if (issued && response.request().method() === 'GET') this.urlIssues.push(issued[1]!)
      if (isStorageRead(response.request())) logging.set(response.request(), record(response))
    })
    // A read the viewer cancels once it has what it needs fails instead; it has no end time.
    context.on('requestfinished', (request) => {
      const entry = entries.get(request)
      if (entry) entry.elapsedMs = request.timing().responseEnd
    })
  }

  of(artifact: PublishedArtifact): StorageRequest[] {
    return this.storage.filter((request) => request.artifactId === artifact.id)
  }

  bytesOf(artifact: PublishedArtifact): number {
    return this.of(artifact).reduce((sum, request) => sum + request.bytes, 0)
  }

  issuesOf(artifact: PublishedArtifact): number {
    return this.urlIssues.filter((id) => id === artifact.id).length
  }

  /** Resolves once no storage read is in flight, every one finished or failed and logged. */
  async settled(): Promise<void> {
    while (this.pending.size) await Promise.all(this.pending)
  }
}

function isStorageRead(request: Request): boolean {
  return STORAGE_PORTS.includes(new URL(request.url()).port) && request.method() === 'GET'
}

/**
 * Requests that touch the snapshot DB member. The page also reads other small members of the
 * same object (a model's manifest, the attachments index); those are not DB reads.
 */
function memberReads(network: NetworkLog, artifact: PublishedArtifact): StorageRequest[] {
  const end = artifact.offset + artifact.size
  return network
    .of(artifact)
    .filter(
      (request) =>
        request.status !== 403 &&
        (request.range === null || (request.range[1] >= artifact.offset && request.range[0] < end)),
    )
}

/** A generation 2 DB is read page by page inside its member; the object is never fetched whole. */
function expectRangeReads(network: NetworkLog, artifact: PublishedArtifact) {
  const requests = memberReads(network, artifact)
  expect(requests.length, `${artifact.name}: no storage reads`).toBeGreaterThan(0)
  for (const request of network.of(artifact)) {
    expect(request.range, `${artifact.name}: a read without Range`).not.toBeNull()
  }
  for (const request of requests) {
    expect(request.status, `${artifact.name}: ${JSON.stringify(request)}`).toBe(206)
    expect(request.range![0]).toBeGreaterThanOrEqual(artifact.offset)
    expect(request.range![1]).toBeLessThan(artifact.offset + artifact.size)
  }
}

/** The tail of a zipped DB over this size is read first, to check its entry (zipDirectory.ts). */
const ZIP_TAIL_BYTES = 128 * 1024

/**
 * A generation 1 DB (exp.db.zip) is downloaded whole: one download of its member, which a read
 * of its last 128 KiB may come before (a member over that size). When the browser's cache kept
 * that tail, the download asks storage for [offset, tail start - 1] only, and its response, the
 * cached and the fetched part merged, still has the member's full length.
 */
function expectWholeDownload(network: NetworkLog, artifact: PublishedArtifact) {
  const requests = memberReads(network, artifact)
  const end = artifact.offset + artifact.size - 1
  const tailStart = end + 1 - ZIP_TAIL_BYTES
  const probed = artifact.size > ZIP_TAIL_BYTES && requests[0]?.range?.[0] === tailStart
  if (probed) expect(requests[0]!.range).toEqual([tailStart, end])
  const downloads = probed ? requests.slice(1) : requests
  expect(downloads, `${artifact.name}: ${JSON.stringify(requests)}`).toHaveLength(1)
  expect(downloads[0]!.bytes).toBe(artifact.size)
  expect(downloads[0]!.range![0]).toBe(artifact.offset)
  expect(probed ? [tailStart - 1, end] : [end]).toContain(downloads[0]!.range![1])
}

/** "a new" or "an old", for test titles. */
function withArticle(format: 'new' | 'old'): string {
  return format === 'old' ? 'an old' : 'a new'
}

function collectionUrl(storage: StorageData) {
  return `${FRONTEND}/organization/${data.organization_id}/orbit/${storage.orbit_id}/collection/${storage.collection_id}`
}

async function openSnapshot(page: Page, storage: StorageData, artifact: PublishedArtifact) {
  await page.goto(snapshotUrl(storage, artifact))
}

async function openCompare(page: Page, storage: StorageData, artifacts: PublishedArtifact[]) {
  await page.goto(compareUrl(storage, artifacts))
}

/** A chart card, by the stable attributes the chart components put on its root. */
function chartCard(page: Page, key: string): Locator {
  return page.locator(`[data-testid="metric-chart"][data-metric-key="${key}"]`)
}

/** The line traces Plotly holds on the plot element (`gd.data`), one per experiment. */
async function chartLines(card: Locator): Promise<ChartLine[]> {
  return card
    .getByTestId('metric-plot')
    .first()
    .evaluate((element) => {
      const traces = (element as unknown as { data?: Record<string, unknown>[] }).data ?? []
      return (
        traces
          // The line trace's uid is `<experiment id>-line` (bucketTraces.ts); bands are separate.
          .filter((trace) => /[-:]line$/.test(String(trace.uid ?? '')))
          .map((trace) => ({
            modelId: String(trace.uid).replace(/[-:]line$/, ''),
            x: [...(trace.x as number[])],
            y: [...(trace.y as (number | null)[])],
          }))
      )
    })
}

async function displayedLevel(card: Locator): Promise<number> {
  return Number(await card.getAttribute('data-level'))
}

/** Waits until the chart is final and draws every listed experiment. */
async function settledChart(page: Page, key: string, modelIds: string[]): Promise<ChartLine[]> {
  const card = chartCard(page, key)
  await card.scrollIntoViewIfNeeded()
  await expect(card, `chart ${key} final`).toHaveAttribute('data-state', 'final', {
    timeout: 60_000,
  })
  // Plotly draws after the state turns final (it loads and renders asynchronously).
  await expect
    .poll(
      async () => {
        const lines = await chartLines(card)
        return modelIds.filter((id) => !lines.find((line) => line.modelId === id)?.x.length)
      },
      { message: `chart ${key} draws every experiment`, timeout: 30_000 },
    )
    .toEqual([])
  await expect(card.getByTestId('chart-error')).toHaveCount(0)
  return chartLines(card)
}

/** A mouse drag over 2% of the plot's x axis from `start` (a fraction), as a user zooms. */
async function dragZoom(page: Page, card: Locator, start: number) {
  const plot = card.getByTestId('metric-plot').first()
  const box = (await plot.locator('.nsewdrag').boundingBox())!
  const from = box.x + box.width * start
  await page.mouse.move(from, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(from + box.width * 0.02, box.y + box.height / 2, { steps: 5 })
  await page.mouse.up()
}

async function expectNoNotices(page: Page) {
  await expect(page.getByTestId('experiment-status-notice')).toHaveCount(0)
}

function snapshotUrl(storage: StorageData, artifact: PublishedArtifact): string {
  return `${collectionUrl(storage)}/artifacts/${artifact.id}/experiment-snapshot`
}

function compareUrl(storage: StorageData, artifacts: PublishedArtifact[]): string {
  return `${collectionUrl(storage)}/compare?${artifacts.map((item) => `artifacts=${item.id}`).join('&')}`
}

/** The experiments a chart draws a line for, in no particular order. */
async function drawnIds(page: Page, key: string): Promise<string[]> {
  return (await chartLines(chartCard(page, key))).map((line) => line.modelId).sort()
}

/** The chart of `key` draws exactly these experiments, each with its logged values. */
async function expectLoggedCharts(page: Page, items: PublishedArtifact[]) {
  await settledChart(
    page,
    'train/loss',
    items.map((item) => item.id),
  )
  // Right after a switch the chart of the set before may still be shown for a moment.
  await expect
    .poll(() => drawnIds(page, 'train/loss'), { message: 'the chart draws exactly these' })
    .toEqual(items.map((item) => item.id).sort())
  for (const item of items) {
    const logged = data.expected.experiments[item.name as 'new_a' | 'new_b' | 'old']
    await expectChartOfLoggedValues(
      chartCard(page, 'train/loss'),
      item.id,
      logged.metrics['train/loss']!,
    )
  }
}

function stringValues(record: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(Object.entries(record).map(([key, value]) => [key, String(value)]))
}

/** The card of one eval dataset, by its title. */
function datasetCard(page: Page, dataset: string): Locator {
  return page.locator('.card').filter({
    has: page.locator('h3.card__title', { hasText: new RegExp(`^\\s*${dataset}\\s*$`) }),
  })
}

/** The dataset's average score chips, each as the viewer rounds it. */
async function expectScoresIn(card: Locator, averages: Record<string, number>) {
  const chips = card.locator('.scores .score')
  await expect(chips).toHaveCount(Object.keys(averages).length, { timeout: 60_000 })
  for (const [name, value] of Object.entries(averages)) {
    await expect(chips.filter({ hasText: name })).toHaveText(
      new RegExp(`^\\s*${name}\\s*${value.toFixed(3)}\\s*$`),
      { timeout: 60_000 },
    )
  }
}

/** Cell texts with their line breaks folded, as `feedbackText` writes them. */
async function foldedCells(row: Locator): Promise<string[]> {
  return (await rowCells(row)).map((text) => text.replace(/\s+/g, ' '))
}

const TRACES = data.traces
// traces_new is about 3 MB (trace_data.py, the same in every run). Measured in 10 runs on S3 and
// Azure, the same each time; each limit is that plus one read-ahead chunk. Its trace list reads
// the summary table: 819,202 bytes.
const TRACE_LIST_MAX_BYTES = 819_202 + READ_AHEAD_CHUNK
// The big trace's span tree reads the covering index: 655,360 bytes.
const SPAN_TREE_MAX_BYTES = 655_360 + READ_AHEAD_CHUNK
// A chunk that holds a page next to a span's value touches a few of its pages: 27,314 bytes of
// the 1 MiB value and none of the 100 KiB one (by the span tree), plus one 16 KiB page.
const MAX_PAYLOAD_TOUCHED_BYTES = 27_314 + 16 * 1024
// Selecting the span reads its value (97% of the 1 MiB region measured, at least 95% asked),
// then 187,325 bytes of the row pages around it.
const PAYLOAD_READ_MIN_FRACTION = 0.95
const MAX_PAYLOAD_READ_EXTRA = 187_325 + READ_AHEAD_CHUNK
// An eval opened with its trace: 2 requests, 131,072 bytes.
const EVAL_VIEW_BUDGET = measuredPlusOneChunk(2, 131_072)
const BROWSER_STATE = join(env('E2E_WORK_DIR'), 'browser-state.json')

function sumBytes(requests: StorageRequest[]): number {
  return requests.reduce((sum, request) => sum + request.bytes, 0)
}

function regionSize(region: [number, number]): number {
  return region[1] - region[0] + 1
}

/** Bytes of `requests` that fall inside `region` (a read without Range covers it all). */
function bytesWithin(requests: StorageRequest[], region: [number, number]): number {
  return requests.reduce((sum, request) => {
    if (!request.range) return sum + regionSize(region)
    const first = Math.max(request.range[0], region[0])
    const last = Math.min(request.range[1], region[1])
    return sum + Math.max(0, last - first + 1)
  }, 0)
}

/** The reads hold no span payload: at most a few pages of the 1 MiB and the 100 KiB values. */
function expectNoPayloadRead(requests: StorageRequest[], artifact: PublishedArtifact) {
  for (const [name, region] of [
    ['1 MiB', artifact.payload_region!],
    ['100 KiB', artifact.medium_region!],
  ] as const) {
    expect(bytesWithin(requests, region), `bytes of the ${name} value read`).toBeLessThanOrEqual(
      MAX_PAYLOAD_TOUCHED_BYTES,
    )
  }
}

/** Opens an experiment of trace_data.py and waits for its trace list and average scores. */
async function openTraceSnapshot(page: Page, storage: StorageData, artifact: PublishedArtifact) {
  await openSnapshot(page, storage, artifact)
  await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
    timeout: 60_000,
  })
  await expectAverageScores(page, TRACES.averages)
}

/** The bar charts of average scores per experiment: score name to experiment id to value. */
async function scoreCharts(page: Page): Promise<Record<string, Record<string, number>>> {
  const plots = page.locator('.charts .js-plotly-plot')
  await expect(plots).toHaveCount(Object.keys(TRACES.averages).length, { timeout: 60_000 })
  const read = () =>
    plots.evaluateAll((elements) =>
      elements.map((element) => {
        const plot = element as unknown as {
          data?: { x: string[]; y: number[] }[]
          layout?: { title?: { text?: string } | string }
        }
        const title = plot.layout?.title
        return {
          name: typeof title === 'string' ? title : (title?.text ?? ''),
          x: [...(plot.data?.[0]?.x ?? [])],
          y: [...(plot.data?.[0]?.y ?? [])],
        }
      }),
    )
  await expect.poll(async () => (await read()).every((chart) => chart.x.length > 0)).toBe(true)
  const result: Record<string, Record<string, number>> = {}
  for (const chart of await read()) {
    result[chart.name] = Object.fromEntries(chart.x.map((id, index) => [id, chart.y[index]!]))
  }
  return result
}

interface TraceStep {
  bytes: number
  ms: number
}

/**
 * Opens traces_new, then its big trace, then selects the span with the 1 MiB value: the bytes
 * read from storage and the time of each of the three steps.
 */
async function traceSteps(
  page: Page,
  network: NetworkLog,
  storage: StorageData,
  traces: PublishedArtifact,
): Promise<TraceStep[]> {
  const steps: TraceStep[] = []
  let reads = 0
  let started = Date.now()
  // A step ends when its view is shown and its reads are done: a read still on the slow link
  // then would otherwise count in the next step.
  const endStep = async () => {
    const ms = Date.now() - started
    await network.settled()
    const requests = network.of(traces)
    steps.push({ bytes: sumBytes(requests.slice(reads)), ms })
    reads = requests.length
    started = Date.now()
  }
  await openTraceSnapshot(page, storage, traces)
  await endStep()
  await openTrace(page, TRACES.big.trace_id)
  const dialog = traceDialog(page)
  await expectVirtualisedTree(dialog, TRACES)
  await endStep()
  const { large } = TRACES.big
  await spanRow(dialog, large.span).click()
  await expectLargeValue(spanAttribute(dialog, large.key), large.chars!, large.start)
  await endStep()
  return steps
}

// Signed in once by global-setup.ts.
test.use({ storageState: join(env('E2E_WORK_DIR'), 'browser-state.json') })

for (const storageName of Object.keys(data.storages)) {
  const storage = data.storages[storageName]!
  const artifact = (label: string) => storage.artifacts[label]!

  test.describe(`${storageName} storage`, () => {
    let network: NetworkLog

    test.beforeEach(({ context }) => {
      network = new NetworkLog(context, storage.artifacts)
    })

    test('a large generation 2 experiment is read by Range only, a small part of it', async ({
      page,
    }) => {
      const large = artifact('large')
      await openSnapshot(page, storage, large)
      const [line] = await settledChart(page, 'train/loss', [large.id])
      // About two pixels per bucket: a few dozen to a few hundred buckets, never 1M points.
      expect(line!.x.length).toBeGreaterThan(30)
      expect(line!.x.length).toBeLessThan(2_000)
      expect(line!.x.at(-1)).toBeGreaterThan(data.large.points_per_key * 0.99)
      expect(await displayedLevel(chartCard(page, 'train/loss'))).toBeGreaterThanOrEqual(5)
      await expectNoNotices(page)
      expectRangeReads(network, large)
      expectWithinBudget(network.of(large), FIRST_PAINT_BUDGET, 'first paint')
      expect(network.issuesOf(large)).toBe(1)
    })

    test('zooming the large experiment reads the visible range at a finer level', async ({
      page,
    }) => {
      const large = artifact('large')
      await openSnapshot(page, storage, large)
      const [before] = await settledChart(page, 'train/loss', [large.id])
      const card = chartCard(page, 'train/loss')
      const levelBefore = await displayedLevel(card)
      await network.settled()
      const readsBefore = network.of(large).length

      await dragZoom(page, card, 0.4)

      await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
      const [after] = await settledChart(page, 'train/loss', [large.id])
      const span = after!.x.at(-1)! - after!.x[0]!
      expect(span).toBeLessThan(before!.x.at(-1)! * 0.2)
      await network.settled()
      const zoomReads = network.of(large).slice(readsBefore)
      expect(zoomReads.length).toBeGreaterThan(0)
      expectWithinBudget(zoomReads, ZOOM_BUDGET, 'zoom')
      expectRangeReads(network, large)
      expect(network.issuesOf(large)).toBe(1)
    })

    test('an old-format experiment of released luml-sdk 0.5.0 is downloaded whole', async ({
      page,
    }) => {
      const old = artifact('old')
      expect(old.generation).toBe(1)
      await openSnapshot(page, storage, old)
      const [line] = await settledChart(page, 'train/loss', [old.id])
      expect(line!.x.length).toBeGreaterThan(10)
      await expectNoNotices(page)
      expectWholeDownload(network, old)
      expect(network.issuesOf(old)).toBe(1)
    })

    for (const label of ['model_gen2', 'model_gen1']) {
      test(`a model with an embedded ${label.endsWith('2') ? 'new' : 'old'}-format snapshot`, async ({
        page,
      }) => {
        const model = artifact(label)
        expect(model.member).toMatch(/^meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot/)
        await openSnapshot(page, storage, model)
        await settledChart(page, 'train_loss', [model.id])
        await expectNoNotices(page)
        if (model.generation === 2) expectRangeReads(network, model)
        else expectWholeDownload(network, model)
        expect(network.issuesOf(model)).toBe(1)
      })
    }

    test('an old-format experiment with a text step and a fractional step says points are not shown', async ({
      page,
    }) => {
      test.skip(
        !storage.artifacts.fallback,
        'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set',
      )
      // Written by luml-sdk 0.5.0: steps 0..39, one at 2.5 and one at 'oops'. This SDK's export
      // keeps the old format; charts leave both odd rows out and one notice says so.
      const fallback = artifact('fallback')
      expect(fallback.generation).toBe(1)
      await openSnapshot(page, storage, fallback)
      const [line] = await settledChart(page, 'loss', [fallback.id])
      expect(line!.x).toEqual(Array.from({ length: 40 }, (_, step) => step))
      const notice = page.getByTestId('experiment-status-notice')
      await expect(notice).toHaveAttribute('data-code', 'skipped-rows')
      await expect(notice).toHaveText(
        /Some metric points are not shown because their steps are not integers\./,
      )
    })

    const comparisons: [string, string[], string][] = [
      ['new with new', ['new_a', 'new_b'], 'train/loss'],
      ['old with new', ['old', 'new_a'], 'train/loss'],
      ['very different lengths', ['large', 'short'], 'train/loss'],
      ['a large new-format experiment with an old one', ['large', 'old'], 'train/loss'],
      [
        'an experiment with a model holding a new-format snapshot',
        ['gen2_full', 'model_gen2'],
        'train_loss',
      ],
      [
        'an experiment with a model holding an old-format snapshot',
        ['gen2_full', 'model_gen1'],
        'train_loss',
      ],
    ]
    for (const [title, labels, key] of comparisons) {
      test(`compares ${title}`, async ({ page }) => {
        const compared = labels.map(artifact)
        await openCompare(page, storage, compared)
        const lines = await settledChart(
          page,
          key,
          compared.map((item) => item.id),
        )
        expect(lines).toHaveLength(compared.length)
        await expectNoNotices(page)
        await network.settled()
        for (const [index, item] of compared.entries()) {
          if (item.generation === 2) {
            expectRangeReads(network, item)
            const label = labels[index]!
            expectWithinBudget(network.of(item), COMPARISON_ITEM_BUDGETS[label]!, item.name)
          } else expectWholeDownload(network, item)
          expect(network.issuesOf(item), item.name).toBe(1)
        }
        if (labels.includes('short')) {
          const [long, short] = ['large', 'short'].map(
            (label) => lines.find((line) => line.modelId === artifact(label).id)!,
          )
          expect(long!.x.at(-1)).toBeGreaterThan(data.large.points_per_key * 0.99)
          expect(short!.x.at(-1)).toBeLessThan(data.short_steps)
        }
      })
    }

    test('the generation 1 and generation 2 twins show the same points', async ({ page }) => {
      const twins = [artifact('twin_gen1'), artifact('twin_gen2')]
      await openCompare(page, storage, twins)
      const lines = await settledChart(
        page,
        data.twin_key,
        twins.map((item) => item.id),
      )
      const [gen1, gen2] = twins.map((twin) => lines.find((line) => line.modelId === twin.id)!)
      expect(gen1!.x.length).toBeGreaterThan(10)
      expect(gen2!.x).toEqual(gen1!.x)
      expect(gen2!.y.length).toBe(gen1!.y.length)
      for (const [index, value] of gen1!.y.entries()) {
        const other = gen2!.y[index]!
        if (value === null) expect(other).toBeNull()
        else
          expect(Math.abs(other - value)).toBeLessThanOrEqual(1e-9 * Math.max(1, Math.abs(value)))
      }
      expectWholeDownload(network, twins[0]!)
      expectRangeReads(network, twins[1]!)
    })

    test('compares through the collection page selection and its Compare button', async ({
      page,
    }) => {
      const compared = [artifact('new_a'), artifact('old')]
      await page.goto(collectionUrl(storage))
      for (const item of compared) {
        await page
          .getByRole('row')
          .filter({ has: page.getByText(item.name, { exact: true }) })
          .getByRole('checkbox')
          .click()
      }
      await page.getByRole('button', { name: 'Compare', exact: true }).click()
      await page.waitForURL(/\/compare\?/)
      await settledChart(
        page,
        'train/loss',
        compared.map((item) => item.id),
      )
      await expectNoNotices(page)
    })

    // What the views show does not depend on the storage: once, on S3.
    if (storageName === 's3') {
      for (const label of ['new_a', 'old'] as const) {
        const format = label === 'old' ? 'old' : 'new'
        test(`the chart and the static params of ${withArticle(format)}-format experiment show the logged values`, async ({
          page,
        }) => {
          const item = artifact(label)
          const logged = data.expected.experiments[label]
          const values = logged.metrics['train/loss']!
          await openSnapshot(page, storage, item)
          await settledChart(page, 'train/loss', [item.id])
          const buckets = await expectChartOfLoggedValues(
            chartCard(page, 'train/loss'),
            item.id,
            values,
          )
          // A bucket per pixel at most (bucketBudgetForWidth): a chart half the page wide gets
          // buckets of several steps, never every point of the series.
          expect(buckets).toBeGreaterThan(30)
          expect(buckets).toBeLessThan(values.length)
          expect(await staticParameters(page)).toEqual(stringValues(logged.static))
          await expectNoNotices(page)
        })
      }

      for (const [label, era, userVersion] of [
        ['rev0', 'a revision 0 experiment (before migrations)', 0],
        ['rev0_legacy_indexes', 'a revision 0 model with the legacy indexes', 0],
        ['sdk_0_1_0', 'an experiment of luml-sdk 0.1.0', 2],
        ['baseline_quirk', 'a model of a revision 0 store migrated by luml-sdk 0.5.0', 2],
      ] as const) {
        test(`${era} shows the metrics and the evals of its fixture`, async ({ page }) => {
          const item = artifact(label)
          const fixture = data.expected.fixtures[label]
          expect(fixture.user_version).toBe(userVersion)
          await openSnapshot(page, storage, item)
          for (const [key, metric] of Object.entries(fixture.metrics)) {
            const [line] = await settledChart(page, key, [item.id])
            const y = line!.y as number[]
            expect(line!.x, key).toEqual(
              Array.from({ length: metric.count }, (_, index) => metric.first_step + index),
            )
            expect(line!.x.at(-1)).toBe(metric.last_step)
            for (const [value, expected] of [
              [y[0]!, metric.first],
              [y.at(-1)!, metric.last],
              [Math.min(...y), metric.min],
              [Math.max(...y), metric.max],
            ] as [number, number][]) {
              expect(Math.abs(value - expected), key).toBeLessThan(1e-9)
            }
          }
          const dataset = datasetCard(page, fixture.dataset)
          await expectScoresIn(dataset, fixture.average_scores)
          const ids = dataset.locator('.evals-table tbody tr td:first-child')
          await expect(ids).toHaveCount(fixture.eval_ids.length)
          expect((await ids.allInnerTexts()).map((text) => text.trim()).sort()).toEqual(
            [...fixture.eval_ids].sort(),
          )
          expectWholeDownload(network, item)
        })
      }
    }

    // The same traces and evals (trace_data.py), written by this SDK and by luml-sdk 0.5.0: the
    // new format reads its summary tables and indexes by Range, the old one is downloaded whole,
    // and both show the same values.
    for (const label of ['traces_new', 'traces_old']) {
      const format = label === 'traces_new' ? 'new' : 'old'
      const skipWithoutOldSdk = () =>
        test.skip(
          !storage.artifacts[label],
          'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set',
        )
      // This SDK writes the new format, luml-sdk 0.5.0 the old one.
      const traceArtifact = () => {
        const traces = artifact(label)
        expect(traces.generation).toBe(format === 'new' ? 2 : 1)
        return traces
      }
      const expectReads = (traces: PublishedArtifact) => {
        if (traces.generation === 1) return expectWholeDownload(network, traces)
        expectRangeReads(network, traces)
        expectNoPayloadRead(network.of(traces), traces)
      }

      test(`the traces of ${withArticle(format)}-format experiment are listed, sorted and paged`, async ({
        page,
      }) => {
        skipWithoutOldSdk()
        const traces = traceArtifact()
        await openTraceSnapshot(page, storage, traces)
        await network.settled()
        expectReads(traces)
        if (traces.generation === 2) {
          expect(network.bytesOf(traces), `read of ${traces.size}`).toBeLessThanOrEqual(
            TRACE_LIST_MAX_BYTES,
          )
        }

        await expectTracesSortedAndPaged(page, TRACES)
        expectReads(traces)
        await expectNoNotices(page)
      })

      test(`the big trace of ${withArticle(format)}-format experiment: a virtualised tree, payloads on select`, async ({
        page,
      }) => {
        skipWithoutOldSdk()
        const traces = traceArtifact()
        const { large, medium, small } = TRACES.big
        await openTraceSnapshot(page, storage, traces)
        await network.settled()
        let reads = network.of(traces).length
        await openTrace(page, TRACES.big.trace_id)
        const dialog = traceDialog(page)
        await expectVirtualisedTree(dialog, TRACES)
        await network.settled()
        const treeReads = network.of(traces).slice(reads)
        if (traces.generation === 2) {
          expect(sumBytes(treeReads)).toBeLessThanOrEqual(SPAN_TREE_MAX_BYTES)
          expectNoPayloadRead(treeReads, traces)
        } else expect(treeReads).toEqual([])

        reads = network.of(traces).length
        await spanRow(dialog, large.span).click()
        const largeValue = spanAttribute(dialog, large.key)
        await expectLargeValue(largeValue, large.chars!, large.start)
        await network.settled()
        const payloadReads = network.of(traces).slice(reads)
        if (traces.generation === 2) {
          const region = traces.payload_region!
          expect(bytesWithin(payloadReads, region)).toBeGreaterThanOrEqual(
            regionSize(region) * PAYLOAD_READ_MIN_FRACTION,
          )
          expect(sumBytes(payloadReads)).toBeLessThanOrEqual(
            regionSize(region) + MAX_PAYLOAD_READ_EXTRA,
          )
        } else expect(payloadReads).toEqual([])

        await largeValue.getByRole('button', { name: 'Show all' }).click()
        const viewer = page.getByRole('dialog', { name: large.key })
        await expect(viewer.locator('.line').first()).toHaveText(new RegExp(`^${large.start} `))
        await page.keyboard.press('Escape')
        await expect(viewer).toBeHidden()
        const download = page.waitForEvent('download')
        await largeValue.getByRole('button', { name: 'Download' }).click()
        expect(statSync(await (await download).path()).size).toBe(large.chars)

        await spanRow(dialog, medium.span).click()
        await expectLargeValue(spanAttribute(dialog, medium.key), medium.chars!)
        if (traces.generation === 2) {
          // Counted over every read so far: the 1 MiB value's read-ahead may have touched it.
          const region = traces.medium_region!
          expect(bytesWithin(network.of(traces), region)).toBeGreaterThanOrEqual(
            regionSize(region) * PAYLOAD_READ_MIN_FRACTION,
          )
        }
        await spanRow(dialog, small.span).click()
        await expect(spanAttribute(dialog, small.key).locator('.content')).toHaveText(small.value!)
        // A span selected before is shown again without a read.
        reads = network.of(traces).length
        await spanRow(dialog, large.span).click()
        await expectLargeValue(spanAttribute(dialog, large.key), large.chars!, large.start)
        expect(network.of(traces).slice(reads)).toEqual([])
        await expectNoNotices(page)
      })

      test(`the evals of ${withArticle(format)}-format experiment: scores, rows, filter keys and the eval's trace`, async ({
        page,
      }) => {
        skipWithoutOldSdk()
        const traces = traceArtifact()
        await openTraceSnapshot(page, storage, traces)
        const attributeFields = TRACES.attribute_keys.map((key) => `attributes.${key}`)
        const fields = await traceFilterFields(page)
        expect(fields.filter((field) => field.startsWith('attributes.')).sort()).toEqual(
          attributeFields,
        )

        const evalId = 'eval-0003'
        const expected = TRACES.evals[evalId]!
        const rows = await searchEval(page, evalId)
        expect(await rowCells(rows.first())).toEqual(
          expect.arrayContaining([
            evalId,
            `Question ${expected.index}?`,
            `Answer ${expected.index}`,
            ...scoreTexts(expected.scores),
          ]),
        )
        await rows.first().getByRole('button', { name: evalId }).click()
        await page.getByRole('button', { name: 'Trace', exact: true }).click()
        await expectRegularTrace(traceDialog(page), expected.index)
        expectReads(traces)
        await expectNoNotices(page)
      })

      if (storageName !== 's3') continue
      test(`searches, filters, annotations and CSV exports of ${withArticle(format)}-format experiment`, async ({
        page,
      }) => {
        skipWithoutOldSdk()
        const traces = traceArtifact()
        const expected = data.expected
        const evalsById = new Map(expected.evals.map((item) => [item.id, item]))
        const tracesById = new Map(expected.traces.map((item) => [item.id, item]))
        await openTraceSnapshot(page, storage, traces)
        const dataset = datasetCard(page, TRACES.dataset)
        const evalsToolbar = tableToolbar(page, 'Search evals')
        const tracesToolbar = tableToolbar(page, 'Search traces')
        // Each step reads no span payload of the new format: lists, filters and exports read
        // summary tables and indexes.
        const viewStep = (title: string, body: () => Promise<void>) =>
          test.step(title, async () => {
            const from = network.of(traces).length
            await body()
            await network.settled()
            if (traces.generation === 2) expectNoPayloadRead(network.of(traces).slice(from), traces)
          })

        const expectEvalCsv = (rows: Record<string, string>[], ids: string[]) => {
          expect(rows.map((row) => row.id).sort()).toEqual([...ids].sort())
          for (const row of rows) {
            const item = evalsById.get(row.id!)!
            const feedback =
              item.correct === null ? '' : feedbackCsv(item.correct ? 1 : 0, item.correct ? 0 : 1)
            expect(row, row.id).toEqual({
              id: item.id,
              'inputs.question': item.question,
              'outputs.answer': item.answer,
              'refs.expected': item.expected,
              'scores.accuracy': String(item.scores.accuracy),
              'scores.passed': String(item.scores.passed),
              'scores.tokens': String(item.scores.tokens),
              'correct (feedback)': feedback,
            })
          }
        }
        const expectTraceCsv = (rows: Record<string, string>[], ids: string[]) => {
          expect(rows.map((row) => row.trace_id).sort()).toEqual([...ids].sort())
          for (const row of rows) {
            const { created_at: createdAt, ...cells } = row
            expect(createdAt).toMatch(/^\d+\/\d+\/\d{4}, \d{2}:\d{2}:\d{2}$/)
            if (row.trace_id === TRACES.big.trace_id) {
              expect(cells).toEqual({
                trace_id: TRACES.big.trace_id,
                execution_time: String(TRACES.big.execution_time_ns),
                state: '1',
                span_count: String(TRACES.big.span_count),
                'helpful (feedback)': feedbackCsv(1, 0),
                evals: '',
              })
              continue
            }
            const item = tracesById.get(row.trace_id!)!
            expect(cells, row.trace_id).toEqual({
              trace_id: item.id,
              execution_time: String(item.execution_time_ns),
              state: String(item.status),
              span_count: String(item.span_count),
              'helpful (feedback)': item.helpful ? feedbackCsv(1, 0) : '',
              evals: item.eval_id,
            })
          }
        }

        await viewStep(
          'feedback annotations in the trace list, the span and the eval rows',
          async () => {
            // trace_data.py: `helpful` on the root of trace-0000 and on a span of the big trace,
            // `correct` on the first evals, true for an even index.
            await page.getByPlaceholder('Search traces').fill(TRACES.big.trace_id)
            await expect(traceRows(page)).toHaveCount(1, { timeout: 60_000 })
            const bigRow = traceRows(page).first()
            await expect(bigRow.locator('td').first()).toHaveText(TRACES.big.trace_id)
            expect((await foldedCells(bigRow)).slice(0, 5)).toEqual([
              TRACES.big.trace_id,
              durationText(TRACES.big.execution_time_ns),
              TRACES.big.state,
              String(TRACES.big.span_count),
              feedbackText(true),
            ])
            for (const traceId of ['trace-0001', 'trace-0000']) {
              await page.getByPlaceholder('Search traces').fill(traceId)
              await expect(traceRows(page)).toHaveCount(1, { timeout: 60_000 })
              await expect(traceRows(page).first().locator('td').first()).toHaveText(traceId)
              expect((await foldedCells(traceRows(page).first()))[4]).toBe(
                feedbackText(tracesById.get(traceId)!.helpful ? true : null),
              )
            }
            await clickFirstTrace(page, 'trace-0000')
            const dialog = traceDialog(page)
            await expectRegularTrace(dialog, 0)
            await expect(spanRow(dialog, 'request').locator('.p-tag')).toHaveText('1')
            await expect(spanRow(dialog, 'embed').locator('.p-tag')).toHaveCount(0)
            await dialog.locator('.body .header-right').getByRole('button', { name: '1' }).click()
            const annotation = dialog.locator('.view .wrapper')
            await expect(annotation).toHaveCount(1)
            await expect(annotation.locator('.name')).toHaveText('helpful')
            await expect(annotation.locator('.result')).toHaveText('True')
            await expect(annotation.locator('.username')).toHaveText('e2e')
            await dialog.getByRole('button', { name: 'Close' }).click()
            await expect(dialog).toBeHidden()
            await page.getByPlaceholder('Search traces').fill('')
            await expect.poll(() => traceRows(page).count()).toBeGreaterThan(1)

            for (const index of [0, 1, 5]) {
              const item = expected.evals[index]!
              const rows = await searchEval(page, item.id)
              expect((await foldedCells(rows.first())).at(-1), item.id).toBe(
                feedbackText(item.correct),
              )
            }
          },
        )

        await viewStep('an eval search: its rows and the averages of those rows', async () => {
          const search = expected.eval_search
          await page.getByPlaceholder('Search evals').fill(search.text)
          await expectScoresIn(dataset, search.averages)
          // The table draws the rows in view only; the export holds every row the search left.
          const found = await exportedCsv(page, evalsToolbar, `${TRACES.dataset}.csv`)
          expectEvalCsv(found.rows, search.ids)
          await page.getByPlaceholder('Search evals').fill('')
          await expectScoresIn(dataset, TRACES.averages)
        })

        await viewStep('an eval filter: the averages and the CSV of what is left', async () => {
          const filter = expected.eval_filter
          await applyFilter(page, evalsToolbar, {
            field: 'scores.tokens',
            operator: '>',
            value: String(filter.min_tokens),
          })
          await expectScoresIn(dataset, filter.averages)
          const filtered = await exportedCsv(page, evalsToolbar, `${TRACES.dataset}.csv`)
          expectEvalCsv(filtered.rows, filter.ids)
          await evalsToolbar.getByRole('button', { name: 'Filters' }).click()
          await page
            .locator('.table-filter-popover')
            .getByRole('button', { name: 'Clear all' })
            .click()
          await expectScoresIn(dataset, TRACES.averages)
          const all = await exportedCsv(page, evalsToolbar, `${TRACES.dataset}.csv`)
          expect(all.header).toEqual([
            'id',
            'inputs.question',
            'outputs.answer',
            'refs.expected',
            'scores.accuracy',
            'scores.passed',
            'scores.tokens',
            'correct (feedback)',
          ])
          expectEvalCsv(
            all.rows,
            expected.evals.map((item) => item.id),
          )
        })

        // Not a viewStep: a filter on span attributes is a scan of every span's attributes, the
        // 1 MiB value among them (the summary tables answer unfiltered lists only).
        await test.step('a trace attribute filter: the rows and the CSV of what is left', async () => {
          const filter = expected.trace_filter
          await applyFilter(page, tracesToolbar, {
            field: 'attributes.user.tier',
            operator: '=',
            // The filter syntax takes a string value in quotes.
            value: `'${filter.tier}'`,
          })
          // Shortest first: a regular trace takes (10 + index) ms, so the ids in index order.
          await page.getByRole('columnheader', { name: 'execution time' }).click()
          const firstIds = traceRows(page).locator('td:first-child')
          await expect(firstIds.first()).toHaveText(filter.ids[0]!, { timeout: 60_000 })
          expect((await firstIds.allInnerTexts()).slice(0, 10).map((text) => text.trim())).toEqual(
            filter.ids.slice(0, 10),
          )
          const filtered = await exportedCsv(page, tracesToolbar, 'traces.csv')
          expectTraceCsv(filtered.rows, filter.ids)
          await tracesToolbar.getByRole('button', { name: 'Filters' }).click()
          await page
            .locator('.table-filter-popover')
            .getByRole('button', { name: 'Clear all' })
            .click()
          await expect(firstIds.first()).toHaveText('trace-0000', { timeout: 60_000 })
          const all = await exportedCsv(page, tracesToolbar, 'traces.csv')
          expect(all.header).toEqual([
            'trace_id',
            'execution_time',
            'state',
            'span_count',
            'helpful (feedback)',
            'evals',
            'created_at',
          ])
          expectTraceCsv(all.rows, [TRACES.big.trace_id, ...expected.traces.map((item) => item.id)])
        })
        if (traces.generation === 1) expectWholeDownload(network, traces)
        else expectRangeReads(network, traces)
        await expectNoNotices(page)
      })
    }

    test('old and new experiments with the same evals and traces compare equal', async ({
      page,
    }) => {
      test.skip(
        !storage.artifacts.traces_old,
        'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set',
      )
      const compared = [artifact('traces_old'), artifact('traces_new')]
      await openCompare(page, storage, compared)
      const charts = await scoreCharts(page)
      expect(Object.keys(charts).sort()).toEqual(Object.keys(TRACES.averages).sort())
      for (const [name, value] of Object.entries(TRACES.averages)) {
        for (const item of compared) {
          expect(Math.abs(charts[name]![item.id]! - value), `${name} of ${item.name}`).toBeLessThan(
            1e-9,
          )
        }
      }

      const evalId = 'eval-0003'
      const expected = TRACES.evals[evalId]!
      const rows = await searchEval(page, evalId, 2)
      const [first, second] = [await rowCells(rows.nth(0)), await rowCells(rows.nth(1))]
      // The id and experiment cells differ by design (the id is shown once per group).
      expect(first.slice(2)).toEqual(second.slice(2))
      expect(first).toEqual(expect.arrayContaining(scoreTexts(expected.scores)))

      await rows.first().getByRole('button').first().click()
      const scoreBlocks = page.locator('.scores-block .scores')
      await expect(scoreBlocks).toHaveCount(2)
      expect(await scoreBlocks.nth(0).innerText()).toBe(await scoreBlocks.nth(1).innerText())
      const traceButtons = page.getByRole('button', { name: 'Trace', exact: true })
      await expect(traceButtons).toHaveCount(2)
      for (const index of [0, 1]) {
        await traceButtons.nth(index).click()
        const dialog = traceDialog(page)
        await expectRegularTrace(dialog, expected.index)
        await dialog.getByRole('button', { name: 'Close' }).click()
        await expect(dialog).toBeHidden()
      }
      expectWholeDownload(network, compared[0]!)
      expectRangeReads(network, compared[1]!)
      expectNoPayloadRead(network.of(compared[1]!), compared[1]!)
      await expectNoNotices(page)
    })

    if (storageName === 's3') {
      test('a presigned URL that stopped working mid-session is renewed once', async ({
        page,
        errors,
      }) => {
        const large = artifact('large')
        errors.expect(refusedRead(large))
        // The page's clock: a URL younger than the minimum renew age is not renewed.
        await page.clock.install()
        await openSnapshot(page, storage, large)
        await settledChart(page, 'train/loss', [large.id])
        expect(network.issuesOf(large)).toBe(1)
        await page.clock.fastForward(PRESIGNED_URL_MIN_RENEW_AGE_MS + 1_000)

        // A key rotation: MinIO refuses every URL signed with the old key from now on.
        execFileSync(
          'uv',
          [
            'run',
            '--frozen',
            'python',
            join(env('E2E_HERE'), 'rotate_s3_key.py'),
            `e2e-secret-key-${Date.now()}`,
          ],
          { cwd: join(env('E2E_REPO'), 'sdk/python/sdk'), stdio: 'pipe' },
        )
        // A zoom needs pages not read yet, so the next read uses the dead URL.
        const card = chartCard(page, 'train/loss')
        const levelBefore = await displayedLevel(card)
        const readsBefore = network.of(large).length
        await dragZoom(page, card, 0.6)
        await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
        const [line] = await settledChart(page, 'train/loss', [large.id])
        expect(line!.x.length).toBeGreaterThan(30)
        const later = network.of(large).slice(readsBefore)
        expect(later.filter((request) => request.status === 403)).toHaveLength(1)
        expect(later.filter((request) => request.status === 206).length).toBeGreaterThan(0)
        expect(network.issuesOf(large)).toBe(2)
        await expectNoNotices(page)
      })
    }
  })
}

/** Every storage request of `artifact` the browser saw took at least the link's latency. */
function expectSlowed(network: NetworkLog, artifact: PublishedArtifact, link: ProxyConfig) {
  const requests = network.of(artifact)
  expect(requests.length, `${artifact.name}: no storage reads`).toBeGreaterThan(0)
  for (const request of requests) {
    expect(request.firstByteMs, JSON.stringify(request)).toBeGreaterThanOrEqual(link.latencyMs! - 5)
  }
}

/**
 * Opens a page while the proxy holds every read of `held`, switches the theme to dark and back
 * meanwhile, then lets the reads go: the page answers while its data is on the way. An
 * old-format experiment shows skeletons until its download ends, a new-format one a spinner.
 */
async function expectUsableWhileLoading(
  page: Page,
  proxy: ThrottleProxy,
  held: PublishedArtifact[],
  open: () => Promise<void>,
) {
  await proxy.configure({
    stallMatching: held.map((item) => escapeRegExp(item.bucket_location)).join('|'),
  })
  await open()
  const card = chartCard(page, 'train/loss')
  const loading = page.locator('.p-skeleton').or(card.locator('.p-progressspinner'))
  await expect(loading.first()).toBeVisible()
  const root = page.locator('html')
  await page.getByText('Dark', { exact: true }).click()
  await expect(root).toHaveAttribute('data-theme', 'dark')
  await page.getByText('Light', { exact: true }).click()
  await expect(root).not.toHaveAttribute('data-theme', 'dark')
  expect(await page.locator('[data-testid="metric-plot"] .scatterlayer .trace').count()).toBe(0)
  await proxy.configure({ stallMatching: null })
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Storage refusing a read of `artifact`, as the test makes it (an error the guard allows). */
function refusedRead(artifact: PublishedArtifact) {
  return {
    kind: 'response',
    status: 403,
    url: new RegExp(`/${escapeRegExp(artifact.bucket_location)}$`),
  } as const
}

test.describe('slow network to storage', () => {
  const storage = data.proxied.s3!
  const proxy = PROXIES.s3
  const artifact = (label: string) => storage.artifacts[label]!
  let network: NetworkLog

  test.beforeEach(async ({ context }) => {
    await proxy.reset()
    network = new NetworkLog(context, storage.artifacts)
  })

  test.afterAll(async () => {
    await proxy.reset()
  })

  test('a large new-format experiment draws, stays usable and zooms on a slow link', async ({
    page,
  }) => {
    const large = artifact('large')
    await proxy.configure(SLOW_LINK)
    await expectUsableWhileLoading(page, proxy, [large], () => openSnapshot(page, storage, large))
    const [before] = await settledChart(page, 'train/loss', [large.id])
    expect(before!.x.length).toBeGreaterThan(30)
    expect(before!.x.at(-1)).toBeGreaterThan(data.large.points_per_key * 0.99)
    expect(before!.y.every((value) => value === null || (value > 0 && value < 1.1))).toBe(true)
    expectRangeReads(network, large)
    expectSlowed(network, large, SLOW_LINK)
    await network.settled()
    expectWithinBudget(network.of(large), FIRST_PAINT_BUDGET, 'first paint')

    const card = chartCard(page, 'train/loss')
    const levelBefore = await displayedLevel(card)
    const readsBefore = network.of(large).length
    await dragZoom(page, card, 0.4)
    await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
    const [after] = await settledChart(page, 'train/loss', [large.id])
    expect(after!.x.at(-1)! - after!.x[0]!).toBeLessThan(before!.x.at(-1)! * 0.2)
    expect(network.of(large).length).toBeGreaterThan(readsBefore)
    expectRangeReads(network, large)
    expectSlowed(network, large, SLOW_LINK)
    await network.settled()
    const zoomReads = network.of(large).slice(readsBefore)
    expectWithinBudget(zoomReads, ZOOM_BUDGET, 'zoom')
    await expectNoNotices(page)
  })

  test('an old-format experiment is downloaded whole and drawn on a slow link', async ({
    page,
  }) => {
    const old = artifact('old')
    await proxy.configure(SLOW_LINK)
    await expectUsableWhileLoading(page, proxy, [old], () => openSnapshot(page, storage, old))
    const [line] = await settledChart(page, 'train/loss', [old.id])
    expect(line!.x.length).toBeGreaterThan(10)
    expect(line!.x.at(-1)).toBeGreaterThan(data.regular_steps * 0.99)
    expectWholeDownload(network, old)
    // The whole member at the link's rate, plus its latency.
    const [download] = memberReads(network, old)
    expect(download!.elapsedMs).toBeGreaterThanOrEqual(
      SLOW_LINK.latencyMs! + (old.size / SLOW_LINK.bytesPerSecond!) * 1000 * 0.9,
    )
    await expectNoNotices(page)
  })

  test('old and new experiments are compared on a slow link', async ({ page }) => {
    const compared = [artifact('old'), artifact('new_a')]
    await proxy.configure(SLOW_LINK)
    await expectUsableWhileLoading(page, proxy, compared, () =>
      openCompare(page, storage, compared),
    )
    const lines = await settledChart(
      page,
      'train/loss',
      compared.map((item) => item.id),
    )
    for (const item of compared) {
      const line = lines.find((candidate) => candidate.modelId === item.id)!
      expect(line.x.at(-1), item.name).toBeGreaterThan(data.regular_steps * 0.99)
      expectSlowed(network, item, SLOW_LINK)
    }
    expectWholeDownload(network, compared[0]!)
    expectRangeReads(network, compared[1]!)
    await expectNoNotices(page)
  })

  test('a new-format experiment loads on a very slow link without a timeout', async ({ page }) => {
    const small = artifact('new_a')
    await proxy.configure(VERY_SLOW_LINK)
    await openSnapshot(page, storage, small)
    const [line] = await settledChart(page, 'train/loss', [small.id])
    expect(line!.x.at(-1)).toBeGreaterThan(data.regular_steps * 0.99)
    expectRangeReads(network, small)
    expectSlowed(network, small, VERY_SLOW_LINK)
    await expectNoNotices(page)
  })

  test('storage that ignores Range: the experiment is loaded in full and says so', async ({
    page,
  }) => {
    const small = artifact('new_a')
    // Paced to about two objects a second, so a reader that stops early is seen to stop.
    await proxy.configure({ stripRange: true, bytesPerSecond: small.file_size * 2 })
    await openSnapshot(page, storage, small)
    const [line] = await settledChart(page, 'train/loss', [small.id])
    expect(line!.x.at(-1)).toBeGreaterThan(data.regular_steps * 0.99)
    const notice = page.getByTestId('experiment-status-notice')
    await expect(notice).toHaveAttribute('data-code', 'range-ignored')
    await expect(notice).toHaveText(/so the experiment was loaded in full\./)
    // The DB header read answered with the whole object, then one full download; no page reads.
    const requests = memberReads(network, small)
    expect(requests.map((request) => [request.status, request.range !== null])).toEqual([
      [200, true],
      [200, false],
    ])
    expect(requests.every((request) => request.bytes === small.file_size)).toBe(true)
    // The attachments index read got the whole object too; it stopped well before the end.
    const end = small.offset + small.size
    const otherReads = (await proxy.requests()).filter((request) => {
      const range = request.range ? /^bytes=(\d+)-(\d+)$/.exec(request.range) : null
      return (
        decodeURIComponent(request.path).endsWith(`/${small.bucket_location}`) &&
        range !== null &&
        (Number(range[2]) < small.offset || Number(range[1]) >= end)
      )
    })
    expect(otherReads.length).toBeGreaterThan(0)
    for (const request of otherReads) {
      expect(request.bytes, JSON.stringify(request)).toBeLessThan(small.file_size / 2)
    }
  })

  test('a read that never gets an answer shows a timeout, and the next read recovers', async ({
    page,
    errors,
  }) => {
    test.setTimeout(240_000)
    const large = artifact('large')
    errors.expect({ kind: 'error state', text: /^chart train\/loss$/ })
    await openSnapshot(page, storage, large)
    await settledChart(page, 'train/loss', [large.id])
    const card = chartCard(page, 'train/loss')
    const levelBefore = await displayedLevel(card)

    // Every storage read from now on hangs; the viewer's own Range timeout ends it.
    await proxy.configure({ stallMatching: escapeRegExp(large.bucket_location) })
    await dragZoom(page, card, 0.4)
    await expect(card, 'chart shows the read error').toHaveAttribute('data-state', 'error', {
      timeout: 180_000,
    })
    await card.getByTestId('chart-error').hover()
    await expect(page.getByText(/large: The request timed out\./)).toBeVisible()
    expect((await proxy.requests()).some((request) => request.stalled)).toBe(true)

    await proxy.configure({ stallMatching: null })
    await dragZoom(page, card, 0.6)
    await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
    const [line] = await settledChart(page, 'train/loss', [large.id])
    expect(line!.x.length).toBeGreaterThan(30)
  })

  test('traces of a new-format experiment on a slow link: the same reads, each step in time', async ({
    page,
    browser,
  }) => {
    const traces = artifact('traces_new')
    // Watched by the error guard too, as every context the test opens.
    const baselineContext = await browser.newContext({
      storageState: BROWSER_STATE,
      viewport: { width: 1440, height: 1000 },
    })
    const baseline = await traceSteps(
      await baselineContext.newPage(),
      new NetworkLog(baselineContext, storage.artifacts),
      storage,
      traces,
    )
    await baselineContext.close()

    await proxy.configure(SLOW_LINK)
    // Each step waits up to 60 s (the expect timeouts of traceSteps); here they take seconds.
    const slow = await traceSteps(page, network, storage, traces)
    expect(slow.map((step) => step.bytes)).toEqual(baseline.map((step) => step.bytes))
    expectRangeReads(network, traces)
    expectSlowed(network, traces, SLOW_LINK)
    // The 1 MiB value crosses the link at its rate.
    const region = traces.payload_region!
    expect(slow[2]!.ms).toBeGreaterThanOrEqual(
      ((regionSize(region) * PAYLOAD_READ_MIN_FRACTION) / SLOW_LINK.bytesPerSecond!) * 1000 * 0.9,
    )
    await expectNoNotices(page)
  })

  test('a span payload read that fails says so, and selecting the span again loads it', async ({
    page,
    errors,
  }) => {
    const traces = artifact('traces_new')
    errors.expect(refusedRead(traces))
    const { large } = TRACES.big
    await openTraceSnapshot(page, storage, traces)
    await openTrace(page, TRACES.big.trace_id)
    const dialog = traceDialog(page)
    await expectVirtualisedTree(dialog, TRACES)

    // Storage refuses every read of the selected span's value until told otherwise. With a URL
    // under 30 s old the viewer shows the error at once; with an older one it renews the URL,
    // retries once, is refused again and shows the error. Either way the error is final.
    const region = traces.payload_region!
    await proxy.configure({
      refuseMatching: escapeRegExp(traces.bucket_location),
      refuseOverlapping: region,
    })
    await spanRow(dialog, large.span).click()
    await expect(
      dialog.locator('.body').getByText('Cannot load span data.', { exact: true }).first(),
    ).toBeVisible()
    await network.settled()
    await proxy.configure({ refuseMatching: null, refuseOverlapping: null })
    const refused = () => network.of(traces).filter((request) => request.status === 403)
    expect(refused().length).toBeGreaterThan(0)
    for (const request of refused()) {
      expect(bytesWithin([request], region), JSON.stringify(request)).toBeGreaterThan(0)
    }
    const refusedCount = refused().length

    await spanRow(dialog, large.span).click()
    await expectLargeValue(spanAttribute(dialog, large.key), large.chars!, large.start)
    expect(refused()).toHaveLength(refusedCount)
    await expectNoNotices(page)
  })

  /** Sorted longest first, so the big trace is the first row without a search (which reads). */
  async function showBigTraceFirst(page: Page, traces: PublishedArtifact) {
    await openTraceSnapshot(page, storage, traces)
    await sortLongestFirst(page, TRACES)
    await network.settled()
  }

  /** Reads of `item` the proxy holds that the browser has not given up on yet. */
  async function heldReads(item: PublishedArtifact): Promise<ProxiedRequest[]> {
    return (await proxy.requests()).filter(
      (request) =>
        request.stalled &&
        request.endedAt === 0 &&
        decodeURIComponent(request.path).endsWith(`/${item.bucket_location}`),
    )
  }

  /**
   * Leaves the experiment by the collection's link in the breadcrumbs, inside the app as a user
   * does (a reload would take the toast host with it), then runs the timers it left.
   */
  async function leaveExperiment(page: Page, item: PublishedArtifact) {
    await toCollection(page, item)
    await network.settled()
    await runLeftTimers(page)
  }

  /**
   * Leaves while reads are held and waits until the browser has cancelled every one: the snapshot
   * worker is gone, so its pending reads were rejected.
   */
  async function leaveWhileHeld(page: Page, item: PublishedArtifact) {
    await expect
      .poll(async () => (await heldReads(item)).length, { message: 'a read is held' })
      .toBeGreaterThan(0)
    await leaveExperiment(page, item)
    await expect
      .poll(async () => (await heldReads(item)).length, { message: 'held reads cancelled' })
      .toBe(0)
  }

  test('a trace read that fails shows an error toast', async ({ page, errors }) => {
    // The control for the error guard in the tests below: the toast it fails them on is seen
    // here, and declared.
    const traces = artifact('traces_new')
    errors.expect({ kind: 'toast', text: /Snapshot range read failed: .* status 403/ })
    errors.expect(refusedRead(traces))
    await showBigTraceFirst(page, traces)
    await proxy.configure({ refuseMatching: escapeRegExp(traces.bucket_location) })
    await clickFirstTrace(page, TRACES.big.trace_id)
    await expect(page.locator(`.${ERROR_TOAST}`).first()).toBeVisible()
    await network.settled()
  })

  // "Shows no error": the error guard fails these on any error toast or error left behind.
  test('leaving a loaded new-format experiment shows no error', async ({ page }) => {
    // Nothing is read when it is left: what this shows is not about cancelled reads.
    const large = artifact('large')
    await page.clock.install()
    await openSnapshot(page, storage, large)
    await settledChart(page, 'train/loss', [large.id])
    await network.settled()
    await leaveExperiment(page, large)
  })

  test('leaving a new-format experiment while its first reads are held shows no error', async ({
    page,
  }) => {
    const large = artifact('large')
    await page.clock.install()
    await proxy.configure({ stallMatching: escapeRegExp(large.bucket_location) })
    await openSnapshot(page, storage, large)
    // The worker reads one page run at a time, so each held read is let go until the opened
    // experiment's view is mounted; its own first reads (static params, metrics) are then held.
    const view = page.locator('.view-wrapper > .content')
    await expect
      .poll(
        async () => {
          if (await view.count()) return true
          if ((await heldReads(large)).length) await proxy.release()
          return false
        },
        { message: 'the experiment view is mounted', intervals: [100], timeout: 60_000 },
      )
      .toBe(true)
    // Static params and metrics are loading: skeletons and no chart yet.
    await expect(view.locator('> .p-skeleton').first()).toBeVisible()
    await expect(chartCard(page, 'train/loss')).toHaveCount(0)
    await leaveWhileHeld(page, large)
  })

  test('leaving a new-format experiment while a trace read is held shows no error', async ({
    page,
  }) => {
    const traces = artifact('traces_new')
    await page.clock.install()
    await showBigTraceFirst(page, traces)
    await proxy.configure({ stallMatching: escapeRegExp(traces.bucket_location) })
    await clickFirstTrace(page, TRACES.big.trace_id)
    await leaveWhileHeld(page, traces)

    // Back in the app's history: the experiment opens again with fresh reads and no dialog.
    await proxy.configure({ stallMatching: null })
    await page.goBack()
    await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
      timeout: 60_000,
    })
    await expectAverageScores(page, TRACES.averages)
    await expect(traceDialog(page)).toHaveCount(0)
    await network.settled()
  })

  const heldCount = (item: PublishedArtifact) => async () => (await heldReads(item)).length

  /**
   * A stallMatching pattern for the reads of an artifact's snapshot member that start at its
   * first byte (an old-format download; a new-format DB's header read). Other reads of the
   * object (the attachments index) are let through.
   */
  const memberRead = (item: PublishedArtifact) =>
    `${escapeRegExp(item.bucket_location)}.* bytes=${item.offset}-`

  /**
   * Leaves while reads of `item` are held, by `leave`, and waits until the proxy saw each held
   * read given up. Not by the NetworkLog: the browser reports no end for a read of a worker it
   * terminated.
   */
  async function leaveHeld(page: Page, item: PublishedArtifact, leave: () => Promise<void>) {
    await expect.poll(heldCount(item), { message: 'a read is held' }).toBeGreaterThan(0)
    await leave()
    await runLeftTimers(page)
    await expect.poll(heldCount(item), { message: 'held reads cancelled' }).toBe(0)
  }

  /** Back to the collection by its link in the breadcrumbs, as leaveExperiment does. */
  async function toCollection(page: Page, item: PublishedArtifact) {
    await page.locator(`a[href$="/collection/${storage.collection_id}"]`).first().click()
    await page.waitForURL(collectionUrl(storage))
    await expect(
      page.getByRole('row').filter({ has: page.getByText(item.name, { exact: true }) }),
    ).toBeVisible()
  }

  /** Opens an experiment from the collection list as a user does: its row, then its tab. */
  async function openFromCollection(page: Page, item: PublishedArtifact) {
    await page
      .getByRole('row')
      .filter({ has: page.getByText(item.name, { exact: true }) })
      .click()
    await page.waitForURL(`${collectionUrl(storage)}/artifacts/${item.id}`)
    await page.getByText('Experiment snapshot', { exact: true }).first().click()
    await page.waitForURL(snapshotUrl(storage, item))
  }

  async function expectNoTraceList(page: Page) {
    await expect(page.locator('.traces-table')).toHaveCount(0)
    await expect(page.locator('.evals-table')).toHaveCount(0)
  }

  test('switching experiments in the app, then back and forward, shows only the current one', async ({
    page,
  }) => {
    // A new route on the collection page remounts the artifact page (its RouterView is keyed by
    // the artifact id), so a switch ends the worker of the experiment left.
    // large is the experiment left with a read in flight: a zoom of it reads pages not read yet.
    const large = artifact('large')
    const newB = artifact('new_b')
    const traces = artifact('traces_new')
    const expectLarge = async () => {
      const [line] = await settledChart(page, 'train/loss', [large.id])
      expect(await drawnIds(page, 'train/loss')).toEqual([large.id])
      expect(line!.x.at(-1)).toBeGreaterThan(data.large.points_per_key * 0.99)
    }
    await page.clock.install()
    await openSnapshot(page, storage, large)
    await expectLarge()
    const largeParams = await staticParameters(page)
    await network.settled()

    await test.step('to new_b while a zoom read of large is held: that read is cancelled', async () => {
      await proxy.configure({ stallMatching: escapeRegExp(large.bucket_location) })
      await dragZoom(page, chartCard(page, 'train/loss'), 0.4)
      await expect.poll(heldCount(large), { message: 'a zoom read is held' }).toBeGreaterThan(0)
      await navigateInApp(page, snapshotUrl(storage, newB))
      await expect
        .poll(heldCount(large), { message: 'the worker of large is gone, its read cancelled' })
        .toBe(0)
      await proxy.configure({ stallMatching: null })
      await expectLoggedCharts(page, [newB])
      const params = await staticParameters(page)
      expect(params).toEqual(stringValues(data.expected.experiments.new_b.static))
      expect(params).not.toEqual(largeParams)
      await expectNoTraceList(page)
    })
    const readsOfLarge = network.of(large).length

    await test.step('to traces_new: its traces and evals, no chart or params of new_b', async () => {
      await navigateInApp(page, snapshotUrl(storage, traces))
      await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
        timeout: 60_000,
      })
      await expectAverageScores(page, TRACES.averages)
      await expect(page.locator('[data-testid="metric-chart"]')).toHaveCount(0)
      await expect(page.locator('.parameters__item')).toHaveCount(0)
      expect(network.of(large).length, 'no read of large once it was left').toBe(readsOfLarge)
    })

    await test.step('back to new_b and large, forward to new_b', async () => {
      await page.goBack()
      await page.waitForURL(snapshotUrl(storage, newB))
      await expectLoggedCharts(page, [newB])
      await expectNoTraceList(page)
      await page.goBack()
      await page.waitForURL(snapshotUrl(storage, large))
      await expectLarge()
      expect(await staticParameters(page)).toEqual(largeParams)
      await page.goForward()
      await page.waitForURL(snapshotUrl(storage, newB))
      await expectLoggedCharts(page, [newB])
    })
    await network.settled()
    await runLeftTimers(page)
    await expectNoNotices(page)
  })

  test('changing the set of a comparison in place draws exactly the current set', async ({
    page,
  }) => {
    // The compare page stays mounted when only its query changes; it resets its provider and
    // opens the new set in the same worker (CompareView.vue).
    const newA = artifact('new_a')
    const newB = artifact('new_b')
    const old = artifact('old')
    await openCompare(page, storage, [newA, newB])
    await expectLoggedCharts(page, [newA, newB])
    for (const set of [
      [newA, newB, old],
      [newB, old],
    ]) {
      await test.step(`to ${set.map((item) => item.name).join(', ')}`, async () => {
        await navigateInApp(page, compareUrl(storage, set))
        await expectLoggedCharts(page, set)
        await expect(page.locator('.models .model')).toHaveText(set.map((item) => item.name))
      })
    }
    for (const item of [newA, newB, old]) expect(network.issuesOf(item), item.name).toBe(1)
    await expectNoNotices(page)
  })

  test('a comparison changed while an old-format download is held draws only the new set', async ({
    page,
  }) => {
    const old = artifact('old')
    const newA = artifact('new_a')
    const newB = artifact('new_b')
    await page.clock.install()
    await proxy.configure({ stallMatching: memberRead(old) })
    await openCompare(page, storage, [old, newA])
    await expect.poll(heldCount(old), { message: 'the download is held' }).toBeGreaterThan(0)
    await navigateInApp(page, compareUrl(storage, [newA, newB]))
    await expectLoggedCharts(page, [newA, newB])
    // The experiment taken out of the comparison is not needed any more.
    await expect
      .poll(heldCount(old), {
        message: 'the download of the experiment taken out is cancelled',
        timeout: 10_000,
      })
      .toBe(0)

    // Whatever was still on the way for the old set must not reopen it in the worker.
    await proxy.configure({ stallMatching: null })
    await network.settled()
    await runLeftTimers(page)
    expect(await drawnIds(page, 'train/loss')).toEqual([newA.id, newB.id].sort())
    const card = chartCard(page, 'train/loss')
    const levelBefore = await displayedLevel(card)
    await dragZoom(page, card, 0.4)
    await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
    await settledChart(page, 'train/loss', [newA.id, newB.id])
    expect(await drawnIds(page, 'train/loss')).toEqual([newA.id, newB.id].sort())
    await expect(page.locator('.models .model')).toHaveText([newA.name, newB.name])
    await expectNoNotices(page)
  })

  test('leaving a comparison while its reads are held shows no error', async ({ page }) => {
    // The worker opens the set once every old-format download is in, so old is let through and
    // the first reads of new_a are held.
    const compared = [artifact('old'), artifact('new_a')]
    const newA = compared[1]!
    await page.clock.install()
    await proxy.configure({ stallMatching: escapeRegExp(newA.bucket_location) })
    await openCompare(page, storage, compared)
    await leaveHeld(page, newA, () => toCollection(page, newA))
    await proxy.configure({ stallMatching: null })
    await page.goBack()
    await expectLoggedCharts(page, compared)
  })

  test('leaving an old-format experiment while its download is held shows no error', async ({
    page,
  }) => {
    const old = artifact('old')
    await page.clock.install()
    await proxy.configure({ stallMatching: memberRead(old) })
    await openSnapshot(page, storage, old)
    await leaveHeld(page, old, () => toCollection(page, old))
    await proxy.configure({ stallMatching: null })
    await page.goBack()
    await expectLoggedCharts(page, [old])
  })

  test('leaving while a span data read is held, then coming back, shows the span data', async ({
    page,
  }) => {
    // The trace dialog is modal: with it open the way out is the browser's back button.
    const traces = artifact('traces_new')
    const { large } = TRACES.big
    await page.clock.install()
    // Opened from the collection by a link: back is the collection, not another tab of the
    // artifact (a tab keeps the artifact's worker for when it comes back).
    await page.goto(collectionUrl(storage))
    // The app's first navigation must be over, or the link replaces it in the history.
    await expect(
      page.getByRole('row').filter({ has: page.getByText(traces.name, { exact: true }) }),
    ).toBeVisible()
    await navigateInApp(page, snapshotUrl(storage, traces))
    await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
      timeout: 60_000,
    })
    await sortLongestFirst(page, TRACES)
    await clickFirstTrace(page, TRACES.big.trace_id)
    const dialog = traceDialog(page)
    await expectVirtualisedTree(dialog, TRACES)
    await network.settled()
    await proxy.configure({ stallMatching: escapeRegExp(traces.bucket_location) })
    await spanRow(dialog, large.span).click()
    await leaveHeld(page, traces, async () => {
      await page.goBack()
      await expect
        .poll(() => page.url(), { message: 'back on the collection' })
        .toBe(collectionUrl(storage))
    })

    await proxy.configure({ stallMatching: null })
    await page.goForward()
    await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
      timeout: 60_000,
    })
    await expect(traceDialog(page)).toHaveCount(0)
    await sortLongestFirst(page, TRACES)
    await clickFirstTrace(page, TRACES.big.trace_id)
    await spanRow(traceDialog(page), large.span).click()
    await expectLargeValue(spanAttribute(traceDialog(page), large.key), large.chars!, large.start)
  })

  test('leaving while an evals read is held, then coming back, shows the evals', async ({
    page,
  }) => {
    // A search of the loaded evals is answered from the pages the worker has, so the read held
    // is one of the evals' first ones: the worker reads one page run at a time, the traces list
    // first (it mounts first), so held reads are let go one by one until the trace list is in.
    const traces = artifact('traces_new')
    await page.clock.install()
    await proxy.configure({ stallMatching: escapeRegExp(traces.bucket_location) })
    await openSnapshot(page, storage, traces)
    const traceIds = traceRows(page).locator('td:first-child')
    await expect
      .poll(
        async () => {
          if (await traceIds.count()) return true
          if ((await heldReads(traces)).length) await proxy.release()
          return false
        },
        { message: 'the trace list is in', intervals: [100], timeout: 60_000 },
      )
      .toBe(true)
    await expect(page.locator('.evals-table'), 'the evals are still loading').toHaveCount(0)
    await leaveHeld(page, traces, () => toCollection(page, traces))

    await proxy.configure({ stallMatching: null })
    await page.goBack()
    await expectAverageScores(page, TRACES.averages)
    const rows = await searchEval(page, 'eval-0003')
    expect(await rowCells(rows.first())).toEqual(
      expect.arrayContaining(scoreTexts(TRACES.evals['eval-0003']!.scores)),
    )
  })

  test('back and forward between the collection and an experiment, and reloads of deep links', async ({
    page,
  }) => {
    const newA = artifact('new_a')
    const traces = artifact('traces_new')
    await page.goto(collectionUrl(storage))
    await openFromCollection(page, newA)
    await expectLoggedCharts(page, [newA])

    await test.step('back to the overview and the collection, forward to the snapshot', async () => {
      await page.goBack()
      await page.waitForURL(`${collectionUrl(storage)}/artifacts/${newA.id}`)
      await expect(page.locator('[data-testid="metric-chart"]')).toHaveCount(0)
      await page.goBack()
      await page.waitForURL(collectionUrl(storage))
      await expect(
        page.getByRole('row').filter({ has: page.getByText(newA.name, { exact: true }) }),
      ).toBeVisible()
      await page.goForward()
      await page.goForward()
      await page.waitForURL(snapshotUrl(storage, newA))
      await expectLoggedCharts(page, [newA])
    })

    await test.step('a reload of the snapshot link', async () => {
      await page.reload()
      await expectLoggedCharts(page, [newA])
    })

    await test.step('an opened trace is not in the link: a reload shows the list', async () => {
      await navigateInApp(page, snapshotUrl(storage, traces))
      await openTrace(page, 'trace-0003')
      await expectRegularTrace(traceDialog(page), 3)
      expect(page.url()).toBe(snapshotUrl(storage, traces))
      await page.reload()
      await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
        timeout: 60_000,
      })
      await expectAverageScores(page, TRACES.averages)
      await expect(traceDialog(page)).toHaveCount(0)
    })
    await network.settled()
    await expectNoNotices(page)
  })

  test('an experiment opened again after another one shows its own data with no more reads', async ({
    page,
  }) => {
    const newA = artifact('new_a')
    const newB = artifact('new_b')
    await page.clock.install()
    await page.goto(collectionUrl(storage))
    await openFromCollection(page, newA)
    await expectLoggedCharts(page, [newA])
    await network.settled()
    const firstReads = network.of(newA).length
    await leaveExperiment(page, newA)
    await openFromCollection(page, newB)
    await expectLoggedCharts(page, [newB])
    await leaveExperiment(page, newB)

    await openFromCollection(page, newA)
    await expectLoggedCharts(page, [newA])
    expect(await staticParameters(page)).toEqual(
      stringValues(data.expected.experiments.new_a.static),
    )
    await network.settled()
    // A new worker reads the same pages again (nothing of the DB is kept between workers), so
    // the reopen reads what the first open read, no more; the presigned URL is kept by the
    // artifacts store for 30 minutes, so no second one is issued.
    expect(network.of(newA).length - firstReads).toBeLessThanOrEqual(firstReads)
    expect(network.issuesOf(newA)).toBe(1)
    await expectNoNotices(page)
  })

  test('a storage read that fails once at open is retried and the experiment opens', async ({
    page,
    errors,
  }) => {
    const newA = artifact('new_a')
    const firstRead = `${escapeRegExp(newA.bucket_location)}.* bytes=${newA.offset}-`
    errors.expect({ kind: 'response', status: 500, url: refusedRead(newA).url })
    await proxy.configure({ storageFailure: { matching: firstRead, status: 500, times: 1 } })
    await openSnapshot(page, storage, newA)
    await expectLoggedCharts(page, [newA])
    expect(memberReads(network, newA).filter((request) => request.status === 500)).toHaveLength(1)
    // The link is too young to renew, so the same one is used for the retry.
    expect(network.issuesOf(newA)).toBe(1)
    await expectNoNotices(page)
  })

  test('storage that keeps failing shows the read error, and a reload once it works opens the experiment', async ({
    page,
    errors,
  }) => {
    const newA = artifact('new_a')
    const firstRead = `${escapeRegExp(newA.bucket_location)}.* bytes=${newA.offset}-`
    errors.expect({ kind: 'response', status: 500, url: refusedRead(newA).url })
    errors.expect({
      kind: 'error state',
      text: /^new_a: The storage request failed\. Reload the page\. Its data is not shown\.$/,
    })
    await proxy.configure({ storageFailure: { matching: firstRead, status: 500, times: null } })
    await openSnapshot(page, storage, newA)
    const notice = page.getByTestId('experiment-status-notice')
    await expect(notice).toHaveText(/The storage request failed\. Reload the page\./, {
      timeout: 60_000,
    })
    await expect(page.locator('[data-testid="metric-chart"]')).toHaveCount(0)
    await network.settled()
    // The read and its one retry with the same link, which is too young to renew.
    expect(memberReads(network, newA).filter((request) => request.status === 500)).toHaveLength(2)
    expect(network.issuesOf(newA)).toBe(1)

    await proxy.configure({ storageFailure: null })
    await page.reload()
    await expectLoggedCharts(page, [newA])
    await expectNoNotices(page)
  })

  test('a comparison with an experiment whose storage fails draws the others and names it', async ({
    page,
    errors,
  }) => {
    const newA = artifact('new_a')
    const old = artifact('old')
    errors.expect({ kind: 'response', status: 500, url: refusedRead(old).url })
    errors.expect({
      kind: 'error state',
      text: /^old: The experiment could not be read\. Its data is not shown\.$/,
    })
    await proxy.configure({
      storageFailure: { matching: escapeRegExp(old.bucket_location), status: 500, times: null },
    })
    await openCompare(page, storage, [newA, old])
    await expectLoggedCharts(page, [newA])
    const notice = page.getByTestId('experiment-status-notice')
    await expect(notice).toHaveCount(1)
    await expect(notice).toHaveAttribute('data-code', 'read-failed')
    await network.settled()
    // The whole download (a zip this small has no directory read first) and its one retry with
    // the same link, which is too young to renew.
    expect(memberReads(network, old).filter((request) => request.status === 500)).toHaveLength(2)
    expect(network.issuesOf(old)).toBe(1)
    expect(network.issuesOf(newA)).toBe(1)
  })

  test('an experiment whose storage object is not found shows the read error with no retry', async ({
    page,
    errors,
  }) => {
    const newA = artifact('new_a')
    errors.expect({ kind: 'response', status: 404, url: refusedRead(newA).url })
    errors.expect({
      kind: 'error state',
      text: /^new_a: The storage request failed\. Reload the page\. Its data is not shown\.$/,
    })
    await proxy.configure({
      storageFailure: { matching: escapeRegExp(newA.bucket_location), status: 404, times: null },
    })
    await openSnapshot(page, storage, newA)
    await expect(page.getByTestId('experiment-status-notice')).toHaveText(
      /The storage request failed\. Reload the page\./,
      { timeout: 60_000 },
    )
    await expect(page.locator('[data-testid="metric-chart"]')).toHaveCount(0)
    await network.settled()
    const missing = memberReads(network, newA).filter((request) => request.status === 404)
    // A 404 is not a failure the same link can get past, and the link is too young to renew.
    expect(missing).toHaveLength(1)
    expect(network.issuesOf(newA)).toBe(1)
  })

  /**
   * Opens `large` and zooms its chart once; `beforeZoom` runs when the first view has its reads.
   * The reads of `large` from the zoom on.
   */
  async function zoomLarge(
    page: Page,
    log: NetworkLog,
    beforeZoom?: () => Promise<void>,
  ): Promise<StorageRequest[]> {
    const large = artifact('large')
    await openSnapshot(page, storage, large)
    await settledChart(page, 'train/loss', [large.id])
    await log.settled()
    const card = chartCard(page, 'train/loss')
    const levelBefore = await displayedLevel(card)
    const start = log.of(large).length
    await beforeZoom?.()
    await dragZoom(page, card, 0.4)
    // A finer level is shown once its buckets are in; a zoom that cannot read them shows an error.
    await expect
      .poll(
        async () =>
          (await card.getAttribute('data-state')) === 'error' ||
          (await displayedLevel(card)) < levelBefore,
        {
          message: 'the zoom drew or failed',
          timeout: 60_000,
        },
      )
      .toBe(true)
    await expect(card).not.toHaveAttribute('data-state', /loading|provisional/, { timeout: 60_000 })
    await log.settled()
    return log.of(large).slice(start)
  }

  const failingRead = (item: PublishedArtifact, times: number | null) =>
    proxy.configure({
      storageFailure: { matching: escapeRegExp(item.bucket_location), status: 500, times },
    })

  test('a zoom read that fails once is retried with the same link and the zoom draws', async ({
    page,
    browser,
    errors,
  }) => {
    const large = artifact('large')
    errors.expect({ kind: 'response', status: 500, url: refusedRead(large).url })
    // The same zoom with no failure, in a context of its own: the reads it takes.
    const baselineContext = await browser.newContext({
      storageState: BROWSER_STATE,
      viewport: { width: 1440, height: 1000 },
    })
    const baseline = await zoomLarge(
      await baselineContext.newPage(),
      new NetworkLog(baselineContext, storage.artifacts),
    )
    await baselineContext.close()

    const reads = await zoomLarge(page, network, () => failingRead(large, 1))
    await settledChart(page, 'train/loss', [large.id])
    const failed = reads.filter((request) => request.status === 500)
    expect(failed).toHaveLength(1)
    // One request more than without the failure: the failed read again, answered.
    expect(reads).toHaveLength(baseline.length + 1)
    expect(
      reads.filter((request) => request.status === 206).map((request) => request.range),
    ).toEqual(expect.arrayContaining([failed[0]!.range]))
    expect(network.issuesOf(large)).toBe(1)
    await expectNoNotices(page)
  })

  test('a zoom whose storage keeps failing shows the chart error, and the next zoom recovers', async ({
    page,
    errors,
  }) => {
    const large = artifact('large')
    errors.expect({ kind: 'response', status: 500, url: refusedRead(large).url })
    errors.expect({ kind: 'error state', text: /^chart train\/loss$/ })
    const reads = await zoomLarge(page, network, () => failingRead(large, null))
    const card = chartCard(page, 'train/loss')
    await expect(card).toHaveAttribute('data-state', 'error')
    await card.getByTestId('chart-error').hover()
    await expect(
      page.getByText(/large: The storage request failed\. Reload the page\./),
    ).toBeVisible()
    // The read and its one retry with the same link, which is too young to renew.
    expect(reads.filter((request) => request.status === 500)).toHaveLength(2)
    expect(reads).toHaveLength(2)
    expect(network.issuesOf(large)).toBe(1)
    // The other charts keep what they drew.
    for (const key of data.large.keys.filter((name) => name !== 'train/loss')) {
      await expect(chartCard(page, key)).toHaveAttribute('data-state', 'final')
      await expect(chartCard(page, key).getByTestId('chart-error')).toHaveCount(0)
    }

    await proxy.configure({ storageFailure: null })
    const levelBefore = await displayedLevel(card)
    await dragZoom(page, card, 0.6)
    await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
    const [line] = await settledChart(page, 'train/loss', [large.id])
    expect(line!.x.length).toBeGreaterThan(30)
    await expectNoNotices(page)
  })

  test('opening the filter editor and an eval of a new-format experiment reads a few pages', async ({
    page,
  }) => {
    const traces = artifact('traces_new')
    await openTraceSnapshot(page, storage, traces)
    await network.settled()
    const since = (start: number) => network.of(traces).slice(start)
    let start = network.of(traces).length

    await test.step('the filter editor', async () => {
      const fields = await traceFilterFields(page)
      expect(fields).toEqual(
        expect.arrayContaining(TRACES.attribute_keys.map((key) => `attributes.${key}`)),
      )
      await network.settled()
      // The keys are in the catalog the trace list read when it opened, so listing them reads
      // nothing more (an old-format DB would scan every span's attributes).
      expect(since(start)).toEqual([])
      start = network.of(traces).length
    })

    await test.step('an eval searched and opened with its trace', async () => {
      const evalId = 'eval-0003'
      const rows = await searchEval(page, evalId)
      await rows.first().getByRole('button', { name: evalId }).click()
      await page.getByRole('button', { name: 'Trace', exact: true }).click()
      await expectRegularTrace(traceDialog(page), TRACES.evals[evalId]!.index)
      await network.settled()
      // The eval's row and its trace's spans, each a lookup by an index: a read-ahead run or
      // two of 64 KiB chunks, however many evals and spans the experiment holds.
      const reads = since(start)
      expectWithinBudget(reads, EVAL_VIEW_BUDGET, 'eval view')
      expectNoPayloadRead(reads, traces)
    })
    expectRangeReads(network, traces)
  })
})

test.describe('Azure storage through its proxy', () => {
  const storage = data.proxied.azure!
  const proxy = PROXIES.azure

  test.afterEach(async () => {
    await proxy.reset()
  })

  test('a SAS URL that stopped working mid-session is renewed once', async ({
    page,
    context,
    errors,
  }) => {
    const network = new NetworkLog(context, storage.artifacts)
    const large = storage.artifacts.large!
    errors.expect(refusedRead(large))
    // The page's clock: a URL younger than the minimum renew age is not renewed.
    await page.clock.install()
    await openSnapshot(page, storage, large)
    await settledChart(page, 'train/loss', [large.id])
    expect(network.issuesOf(large)).toBe(1)
    await page.clock.fastForward(PRESIGNED_URL_MIN_RENEW_AGE_MS + 1_000)
    // The backend's SAS expiry has whole seconds, and the page clock does not move it: a renewal
    // in the same wall-clock second as the first URL is that URL again, refused too.
    await new Promise((resolve) => setTimeout(resolve, 1_050 - (Date.now() % 1_000)))

    // Azurite itself refuses the SAS signatures it served so far, as after a key rotation.
    await proxy.configure({ refuseSeen: true })
    const card = chartCard(page, 'train/loss')
    const levelBefore = await displayedLevel(card)
    const readsBefore = network.of(large).length
    await dragZoom(page, card, 0.6)
    await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
    const [line] = await settledChart(page, 'train/loss', [large.id])
    expect(line!.x.length).toBeGreaterThan(30)
    const later = network.of(large).slice(readsBefore)
    expect(later.filter((request) => request.status === 403)).toHaveLength(1)
    expect(later.filter((request) => request.status === 206).length).toBeGreaterThan(0)
    expect(network.issuesOf(large)).toBe(2)
    await expectNoNotices(page)
  })
})
