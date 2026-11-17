import { test, expect, type BrowserContext, type Locator, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { PRESIGNED_URL_MIN_RENEW_AGE_MS } from '../../src/lib/bucket-service/presigned-url-cache'

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
  storages: Record<string, StorageData>
}

interface StorageRequest {
  artifactId: string
  range: [number, number] | null
  status: number
  bytes: number
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
const STORAGE_PORTS = [env('E2E_MINIO_PORT'), env('E2E_AZURITE_PORT')]
const DOWNLOAD_URL = /\/artifacts\/([0-9a-f-]+)\/download-url/
// Chart reads of a 1M-point metric: the catalog, one level of buckets and the B-tree pages on
// the way, a few dozen pages of 16 KiB however large the DB is.
const MAX_RANGE_REQUESTS_PER_VIEW = 40
const MAX_FRACTION_PER_VIEW = 0.05

/** Every request to storage and to the download-url endpoint, by artifact, with sizes. */
class NetworkLog {
  storage: StorageRequest[] = []
  urlIssues: string[] = []

  constructor(
    context: BrowserContext,
    private readonly artifacts: Record<string, PublishedArtifact>,
  ) {
    context.on('response', async (response) => {
      const url = new URL(response.url())
      const issued = DOWNLOAD_URL.exec(url.pathname)
      if (issued && response.request().method() === 'GET') this.urlIssues.push(issued[1]!)
      if (!STORAGE_PORTS.includes(url.port) || response.request().method() !== 'GET') return
      const artifact = Object.values(this.artifacts).find((item) =>
        decodeURIComponent(url.pathname).endsWith(`/${item.bucket_location}`),
      )
      const header = (await response.request().allHeaders())['range']
      const match = header ? /^bytes=(\d+)-(\d+)$/.exec(header) : null
      const length = Number(response.headers()['content-length'] ?? NaN)
      this.storage.push({
        artifactId: artifact?.id ?? url.pathname,
        range: match ? [Number(match[1]), Number(match[2])] : null,
        status: response.status(),
        bytes: Number.isFinite(length) ? length : 0,
      })
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
}

/**
 * Requests that touch the snapshot DB member. The page also reads other small members of the
 * same object (a model's manifest, a 2-byte probe of the object's end); those are not DB reads.
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

/** A generation 1 DB (exp.db.zip) is downloaded whole, in one request for its member. */
function expectWholeDownload(network: NetworkLog, artifact: PublishedArtifact) {
  const requests = memberReads(network, artifact)
  expect(requests, `${artifact.name}: ${JSON.stringify(requests)}`).toHaveLength(1)
  expect(requests[0]!.bytes).toBe(artifact.size)
  expect(requests[0]!.range).toEqual([artifact.offset, artifact.offset + artifact.size - 1])
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

    if (storageName === 's3') {
      test('a presigned URL that stopped working mid-session is renewed once', async ({ page }) => {
        const large = artifact('large')
        await openSnapshot(page, storage, large)
        await settledChart(page, 'train/loss', [large.id])
        expect(network.issuesOf(large)).toBe(1)
        // A URL younger than this is not renewed.
        await page.waitForTimeout(PRESIGNED_URL_MIN_RENEW_AGE_MS)

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
