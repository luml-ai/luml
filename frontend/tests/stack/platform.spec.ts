import {
  test,
  expect,
  type BrowserContext,
  type Locator,
  type Page,
  type Request,
  type Response,
} from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { PRESIGNED_URL_MIN_RENEW_AGE_MS } from '../../src/lib/bucket-service/presigned-url-cache'
import { SLOW_LINK, ThrottleProxy, VERY_SLOW_LINK, type ProxyConfig } from './proxy'
import {
  expectAverageScores,
  expectLargeValue,
  expectRegularTrace,
  expectTraceRow,
  expectVirtualisedTree,
  openTrace,
  rowCells,
  scoreTexts,
  searchEval,
  spanAttribute,
  spanRow,
  traceDialog,
  traceFilterFields,
  traceRows,
  type TraceData,
} from './trace_view'

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
// Chart reads of a 1M-point metric: the catalog, one level of buckets and the B-tree pages on
// the way, a few dozen pages of 16 KiB however large the DB is.
const MAX_RANGE_REQUESTS_PER_VIEW = 40
const MAX_FRACTION_PER_VIEW = 0.05

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

function collectionUrl(storage: StorageData) {
  return `${FRONTEND}/organization/${data.organization_id}/orbit/${storage.orbit_id}/collection/${storage.collection_id}`
}

async function openSnapshot(page: Page, storage: StorageData, artifact: PublishedArtifact) {
  await page.goto(`${collectionUrl(storage)}/artifacts/${artifact.id}/experiment-snapshot`)
}

async function openCompare(page: Page, storage: StorageData, artifacts: PublishedArtifact[]) {
  const query = artifacts.map((item) => `artifacts=${item.id}`).join('&')
  await page.goto(`${collectionUrl(storage)}/compare?${query}`)
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

const TRACES = data.traces
// traces_new is about 3 MB. Its trace list reads the summary table and its span tree the
// covering index, in read-ahead chunks of 64 KiB: well under 1 MiB each. The 1 MiB value of one
// span alone is more than either view may read, and a chunk that holds a page next to that value
// may touch a few of its pages, never more than 5% of it.
const MAX_TRACE_VIEW_BYTES = TRACES.big.large.chars!
const MAX_PAYLOAD_TOUCHED = 0.05
// Selecting the span reads its value and the row page around it, in read-ahead chunks.
const MAX_PAYLOAD_READ_EXTRA = 512 * 1024
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
    expect(bytesWithin(requests, region), `bytes of the ${name} value read`).toBeLessThan(
      regionSize(region) * MAX_PAYLOAD_TOUCHED,
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
      expect(network.of(large).length).toBeLessThanOrEqual(MAX_RANGE_REQUESTS_PER_VIEW)
      expect(network.bytesOf(large), `fetched of ${large.size}`).toBeLessThan(
        large.size * MAX_FRACTION_PER_VIEW,
      )
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
      const readsBefore = network.of(large).length
      const bytesBefore = network.bytesOf(large)

      await dragZoom(page, card, 0.4)

      await expect.poll(() => displayedLevel(card)).toBeLessThan(levelBefore)
      const [after] = await settledChart(page, 'train/loss', [large.id])
      const span = after!.x.at(-1)! - after!.x[0]!
      expect(span).toBeLessThan(before!.x.at(-1)! * 0.2)
      const zoomReads = network.of(large).slice(readsBefore)
      expect(zoomReads.length).toBeGreaterThan(0)
      expect(zoomReads.length).toBeLessThanOrEqual(MAX_RANGE_REQUESTS_PER_VIEW)
      expect(network.bytesOf(large) - bytesBefore).toBeLessThan(large.size * MAX_FRACTION_PER_VIEW)
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
        for (const item of compared) {
          if (item.generation === 2) expectRangeReads(network, item)
          else expectWholeDownload(network, item)
          expect(network.issuesOf(item), item.name).toBe(1)
        }
        if (labels.includes('large')) {
          const large = artifact('large')
          expect(network.bytesOf(large)).toBeLessThan(large.size * MAX_FRACTION_PER_VIEW)
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

      test(`the traces of a ${format}-format experiment are listed, sorted and paged`, async ({
        page,
      }) => {
        skipWithoutOldSdk()
        const traces = traceArtifact()
        await openTraceSnapshot(page, storage, traces)
        expectReads(traces)
        if (traces.generation === 2) {
          expect(network.bytesOf(traces), `read of ${traces.size}`).toBeLessThan(
            MAX_TRACE_VIEW_BYTES,
          )
        }

        const duration = page.getByRole('columnheader', { name: 'execution time' })
        await duration.click()
        for (const [position, id] of ['trace-0000', 'trace-0001', 'trace-0002'].entries()) {
          const expected = TRACES.traces[id]!
          await expectTraceRow(traceRows(page).nth(position), id, expected, expected.eval_id)
        }
        await duration.click()
        await expectTraceRow(traceRows(page).first(), TRACES.big.trace_id, TRACES.big, null)
        const longest = TRACES.traces['trace-0299']!
        await expectTraceRow(traceRows(page).nth(1), 'trace-0299', longest, longest.eval_id)

        // 20 traces a page: the table asks for the next one when it is scrolled to its end.
        const paged = 'trace-0262'
        const row = traceRows(page).filter({
          has: page.getByRole('button', { name: paged, exact: true }),
        })
        const scroller = page.locator('.traces-table .p-virtualscroller')
        await expect
          .poll(
            async () => {
              await scroller.evaluate((element) => element.scrollTo(0, element.scrollHeight))
              return row.count()
            },
            { message: `${paged} on the second page`, timeout: 30_000 },
          )
          .toBe(1)
        const expected = TRACES.traces[paged]!
        await expectTraceRow(row, paged, expected, expected.eval_id)
        expectReads(traces)
        await expectNoNotices(page)
      })

      test(`the big trace of a ${format}-format experiment: a virtualised tree, payloads on select`, async ({
        page,
      }) => {
        skipWithoutOldSdk()
        const traces = traceArtifact()
        const { large, medium, small } = TRACES.big
        await openTraceSnapshot(page, storage, traces)
        let reads = network.of(traces).length
        await openTrace(page, TRACES.big.trace_id)
        const dialog = traceDialog(page)
        await expectVirtualisedTree(dialog, TRACES)
        const treeReads = network.of(traces).slice(reads)
        if (traces.generation === 2) {
          expect(sumBytes(treeReads)).toBeLessThan(MAX_TRACE_VIEW_BYTES)
          expectNoPayloadRead(treeReads, traces)
        } else expect(treeReads).toEqual([])

        reads = network.of(traces).length
        await spanRow(dialog, large.span).click()
        const largeValue = spanAttribute(dialog, large.key)
        await expectLargeValue(largeValue, large.chars!, large.start)
        const payloadReads = network.of(traces).slice(reads)
        if (traces.generation === 2) {
          const region = traces.payload_region!
          expect(bytesWithin(payloadReads, region)).toBeGreaterThanOrEqual(
            regionSize(region) * (1 - MAX_PAYLOAD_TOUCHED),
          )
          expect(sumBytes(payloadReads)).toBeLessThan(regionSize(region) + MAX_PAYLOAD_READ_EXTRA)
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
            regionSize(region) * (1 - MAX_PAYLOAD_TOUCHED),
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

      test(`the evals of a ${format}-format experiment: scores, rows, filter keys and the eval's trace`, async ({
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
      test('a presigned URL that stopped working mid-session is renewed once', async ({ page }) => {
        const large = artifact('large')
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
    expect(network.bytesOf(large)).toBeLessThan(large.size * MAX_FRACTION_PER_VIEW)

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
    expect(network.bytesOf(large)).toBeLessThan(large.size * MAX_FRACTION_PER_VIEW)
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
  }) => {
    test.setTimeout(240_000)
    const large = artifact('large')
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
      ((regionSize(region) * (1 - MAX_PAYLOAD_TOUCHED)) / SLOW_LINK.bytesPerSecond!) * 1000 * 0.9,
    )
    await expectNoNotices(page)
  })

  test('a span payload read that fails says so, and selecting the span again loads it', async ({
    page,
  }) => {
    const traces = artifact('traces_new')
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
})

test.describe('Azure storage through its proxy', () => {
  const storage = data.proxied.azure!
  const proxy = PROXIES.azure

  test.afterEach(async () => {
    await proxy.reset()
  })

  test('a SAS URL that stopped working mid-session is renewed once', async ({ page, context }) => {
    const network = new NetworkLog(context, storage.artifacts)
    const large = storage.artifacts.large!
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
