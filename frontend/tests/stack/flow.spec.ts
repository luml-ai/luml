import { test, expect, type Locator, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { SLOW_LINK, ThrottleProxy } from './proxy'
import {
  expectAverageScores,
  expectLargeValue,
  expectRegularTrace,
  expectVirtualisedTree,
  openTrace,
  rowCells,
  scoreTexts,
  searchEval,
  spanAttribute,
  spanRow,
  traceDialog,
  type TraceData,
} from './trace_view'

// Flow end to end: the real Flow server of this worktree with its web bundle built from this
// worktree, on one store holding an experiment of released luml-sdk 0.5.0 (old schema), one
// of this SDK (new schema) and a running one that another process appends to, plus the same
// traces and evals (trace_data.py) written once by each SDK.

interface FlowExperiment {
  id: string
  group_id: string
  steps?: number
  db?: string
  user_version?: number
  user_version_after_store_open?: number
}

interface FlowData {
  store: string
  new: FlowExperiment
  live: FlowExperiment
  old?: FlowExperiment
  traces: FlowExperiment
  traces_old?: FlowExperiment
  expected: TraceData
}

const env = (name: string): string => {
  const value = process.env[name]
  if (!value) throw new Error(`${name} is not set; run the suite through run.sh`)
  return value
}

const FLOW = env('E2E_FLOW_URL')
const PROXY = new ThrottleProxy(env('E2E_FLOW_PROXY_PORT'))
// Flow through its delaying proxy: every API call of the page goes over the slow link.
const SLOW_FLOW = `http://127.0.0.1:${PROXY.port}`
const FLOW_DIR = env('E2E_FLOW_DIR')
const data = JSON.parse(readFileSync(join(FLOW_DIR, 'flow.json'), 'utf-8')) as FlowData
const SDK_DIR = join(env('E2E_REPO'), 'sdk/python/sdk')
const KEY = 'train/loss'
const TRACES = data.expected

interface ApiCalls {
  catalog: string[]
  buckets: string[]
  fullHistory: string[]
}

function recordApi(page: Page): ApiCalls {
  const calls: ApiCalls = { catalog: [], buckets: [], fullHistory: [] }
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    const match = /\/api\/experiments\/([^/]+)\/(metric-catalog|metric-buckets|metrics\/)/.exec(
      path,
    )
    if (!match) return
    const id = match[1]!
    if (match[2] === 'metric-catalog') calls.catalog.push(id)
    else if (match[2] === 'metric-buckets') calls.buckets.push(id)
    else calls.fullHistory.push(id)
  })
  return calls
}

async function open(page: Page, path: string, base = FLOW) {
  await page.goto(`${base}${path}#session-token=${env('E2E_FLOW_TOKEN')}`)
}

function chartCard(page: Page, key: string): Locator {
  return page.locator(`[data-testid="metric-chart"][data-metric-key="${key}"]`)
}

function chartPlot(page: Page, key: string): Locator {
  return chartCard(page, key).getByTestId('metric-plot').first()
}

async function lastSteps(plot: Locator): Promise<Record<string, number>> {
  return plot.evaluate((element) => {
    const traces = (element as unknown as { data?: Record<string, unknown>[] }).data ?? []
    const result: Record<string, number> = {}
    for (const trace of traces) {
      const uid = String(trace.uid ?? '')
      const x = trace.x as number[]
      // The line trace's uid is `<experiment id>-line` (bucketTraces.ts); bands are separate.
      const match = /^(.*)[-:]line$/.exec(uid)
      if (match && x.length) result[match[1]!] = x.at(-1)!
    }
    return result
  })
}

async function drawn(page: Page, key: string, ids: string[]): Promise<Record<string, number>> {
  const plot = chartPlot(page, key)
  await plot.scrollIntoViewIfNeeded()
  await expect
    .poll(async () => Object.keys(await lastSteps(plot)), {
      message: `chart ${key} draws ${ids.join(', ')}`,
      timeout: 60_000,
    })
    .toEqual(expect.arrayContaining(ids))
  await expect(chartCard(page, key)).toHaveAttribute('data-state', 'final', { timeout: 60_000 })
  await expect(chartCard(page, key).getByTestId('chart-error')).toHaveCount(0)
  return lastSteps(plot)
}

function userVersion(db: string): number {
  const output = execFileSync(
    'uv',
    [
      'run',
      '--frozen',
      'python',
      '-c',
      'import sqlite3,sys; c=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); print(c.execute("PRAGMA user_version").fetchone()[0])',
      db,
    ],
    { cwd: SDK_DIR, encoding: 'utf-8' },
  )
  return Number(output.trim())
}

interface TraceCalls {
  /** The query string and body size of each trace request (the span tree). */
  structure: { search: string; bytes: number }[]
  /** The span id of each span request. */
  spans: string[]
}

/** Trace and span requests the page sends for one experiment's traces. */
function recordTraceApi(page: Page, experimentId: string): TraceCalls {
  const calls: TraceCalls = { structure: [], spans: [] }
  page.on('response', async (response) => {
    const url = new URL(response.url())
    const match = /^\/api\/experiments\/([^/]+)\/traces\/([^/]+)(?:\/spans\/([^/]+))?$/.exec(
      url.pathname,
    )
    if (!match || match[1] !== experimentId || ['all', 'typed-columns'].includes(match[2]!)) return
    if (match[3]) calls.spans.push(decodeURIComponent(match[3]))
    else calls.structure.push({ search: url.search, bytes: (await response.body()).length })
  })
  return calls
}

/** The size of the full trace (with every payload), from the API the page no longer uses for it. */
async function fullTraceBytes(experimentId: string, traceId: string): Promise<number> {
  const response = await fetch(`${FLOW}/api/experiments/${experimentId}/traces/${traceId}`, {
    headers: { Authorization: `Bearer ${env('E2E_FLOW_TOKEN')}` },
  })
  expect(response.status).toBe(200)
  return (await response.arrayBuffer()).byteLength
}

test('the experiment page reads the catalog and buckets, never the full history', async ({
  page,
}) => {
  const calls = recordApi(page)
  await open(page, `/experiments/${data.new.group_id}/${data.new.id}/metrics`)
  const steps = await drawn(page, KEY, [data.new.id])
  expect(steps[data.new.id]).toBeGreaterThan(data.new.steps! * 0.99)
  expect(calls.catalog).toContain(data.new.id)
  expect(calls.buckets).toContain(data.new.id)
  expect(calls.fullHistory).toEqual([])
})

test('an old-schema experiment of luml-sdk 0.5.0 is shown and not migrated', async ({ page }) => {
  test.skip(!data.old, 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
  const old = data.old!
  expect(old.user_version).toBe(2)
  expect(old.user_version_after_store_open).toBe(2)
  const calls = recordApi(page)
  await open(page, `/experiments/${old.group_id}/${old.id}/metrics`)
  const steps = await drawn(page, KEY, [old.id])
  expect(steps[old.id]).toBeGreaterThan(2_900)
  expect(calls.fullHistory).toEqual([])
  expect(userVersion(old.db!)).toBe(2)
})

test('the comparison page draws old, new and live experiments of one store', async ({ page }) => {
  const ids = [data.new.id, data.live.id, ...(data.old ? [data.old.id] : [])]
  const calls = recordApi(page)
  await open(page, `/experiments/comparison?${ids.map((id) => `ids=${id}`).join('&')}`)
  const steps = await drawn(page, KEY, ids)
  expect(Object.keys(steps).sort()).toEqual([...ids].sort())
  expect(new Set(calls.catalog)).toEqual(new Set(ids))
  expect(calls.fullHistory).toEqual([])
  if (data.old) expect(userVersion(data.old.db!)).toBe(2)
})

test('the refresh button picks up points another process appended', async ({ page }) => {
  const live = data.live
  const calls = recordApi(page)
  await open(page, `/experiments/${live.group_id}/${live.id}/metrics`)
  const before = (await drawn(page, KEY, [live.id]))[live.id]!

  await expectRefreshShowsAppended(page, calls, before)
})

for (const [format, key] of [
  ['new', 'traces'],
  ['old', 'traces_old'],
] as const) {
  test(`a trace of a ${format}-schema experiment: its structure, then each selected span once`, async ({
    page,
  }) => {
    test.skip(!data[key], 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const experiment = data[key]!
    const { large, medium, small, root } = TRACES.big
    const calls = recordTraceApi(page, experiment.id)
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`)
    await openTrace(page, TRACES.big.trace_id)
    const dialog = traceDialog(page)
    await expectVirtualisedTree(dialog, TRACES)
    expect(calls.structure.map((call) => call.search)).toEqual(['?payloads=false'])
    // The structure leaves every payload out, the two large values among them.
    const full = await fullTraceBytes(experiment.id, TRACES.big.trace_id)
    expect(full - calls.structure[0]!.bytes).toBeGreaterThan(large.chars! + medium.chars!)
    expect(calls.spans).toEqual([root.span_id])

    await spanRow(dialog, large.span).click()
    await expectLargeValue(spanAttribute(dialog, large.key), large.chars!, large.start)
    await spanRow(dialog, small.span).click()
    await expect(spanAttribute(dialog, small.key).locator('.content')).toHaveText(small.value!)
    await spanRow(dialog, large.span).click()
    await expectLargeValue(spanAttribute(dialog, large.key), large.chars!, large.start)
    expect(calls.spans).toEqual([root.span_id, large.span_id, small.span_id])
    expect(calls.structure).toHaveLength(1)
    if (experiment.db) expect(userVersion(experiment.db)).toBe(experiment.user_version)
  })

  test(`the evals of a ${format}-schema experiment: scores, rows and the eval's trace`, async ({
    page,
  }) => {
    test.skip(!data[key], 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const experiment = data[key]!
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/evals`)
    await expectAverageScores(page, TRACES.averages)
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
    if (experiment.db) expect(userVersion(experiment.db)).toBe(experiment.user_version)
  })
}

/** Another process appends to the live experiment; the refresh button shows the new points. */
async function expectRefreshShowsAppended(page: Page, calls: ApiCalls, before: number) {
  const appended = 1_000
  const lastStep = Number(
    execFileSync(
      'uv',
      [
        'run',
        '--frozen',
        'python',
        join(env('E2E_HERE'), 'append_live.py'),
        data.store,
        data.live.id,
        String(appended),
      ],
      { cwd: SDK_DIR, encoding: 'utf-8' },
    ).trim(),
  )
  expect(lastStep).toBeGreaterThan(before + appended / 2)
  const catalogsBefore = calls.catalog.length
  // The refresh button has no accessible name; it is the button with the rotate icon.
  await page.locator('button:has([class*="lucide-rotate-ccw"])').click()
  const plot = chartPlot(page, KEY)
  await expect
    .poll(async () => (await lastSteps(plot))[data.live.id] ?? 0, { timeout: 60_000 })
    .toBeGreaterThan(before + appended / 2)
  expect(calls.catalog.length).toBeGreaterThan(catalogsBefore)
  expect(calls.fullHistory).toEqual([])
}

/** A mouse drag over 2% of the plot's x axis from `start` (a fraction), as a user zooms. */
async function dragZoom(page: Page, key: string, start: number) {
  const box = (await chartPlot(page, key).locator('.nsewdrag').boundingBox())!
  const from = box.x + box.width * start
  await page.mouse.move(from, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(from + box.width * 0.02, box.y + box.height / 2, { steps: 5 })
  await page.mouse.up()
}

async function displayedLevel(page: Page, key: string): Promise<number> {
  return Number(await chartCard(page, key).getAttribute('data-level'))
}

/**
 * Opens a page while the proxy holds the bucket calls of `ids`, opens a chart's full-screen view
 * and closes it meanwhile, then lets the calls go: the page answers while its data is on the way.
 */
async function expectUsableWhileLoading(page: Page, ids: string[], path: string) {
  await PROXY.configure({ stallMatching: `^/api/experiments/(${ids.join('|')})/metric-buckets` })
  await open(page, path, SLOW_FLOW)
  const card = chartCard(page, KEY)
  await expect(card.locator('.p-progressspinner').first()).toBeVisible()
  await card.locator('.header-right').getByRole('button').click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  expect(Object.keys(await lastSteps(chartPlot(page, KEY)))).toEqual([])
  await PROXY.configure({ stallMatching: null })
}

/**
 * Every metric API call the proxy served took at least the link's latency, and nothing failed.
 * A call held by the proxy that the page gave up on (its dialog closed) was never answered.
 */
async function expectSlowedApi(ids: string[]) {
  const served = (await PROXY.requests()).filter(
    (request) =>
      ids.some((id) => request.path.startsWith(`/api/experiments/${id}/`)) &&
      !(request.stalled && request.status === 0),
  )
  expect(served.length).toBeGreaterThan(0)
  for (const request of served) {
    expect(request.status, JSON.stringify(request)).toBe(200)
    expect(request.firstByteAt - request.startedAt).toBeGreaterThanOrEqual(SLOW_LINK.latencyMs!)
  }
  return served
}

test.describe('slow network to Flow', () => {
  test.beforeEach(async () => {
    await PROXY.reset()
    // The API only: the web app's own files would take most of the run time at this rate.
    await PROXY.configure({ ...SLOW_LINK, throttleMatching: '^/api/' })
  })

  test.afterAll(async () => {
    await PROXY.reset()
  })

  test('a new-schema experiment draws, stays usable and zooms on a slow link', async ({ page }) => {
    const calls = recordApi(page)
    const timings: number[] = []
    page.on('requestfinished', (request) => {
      if (request.url().includes('/metric-buckets')) timings.push(request.timing().responseEnd)
    })
    await expectUsableWhileLoading(
      page,
      [data.new.id],
      `/experiments/${data.new.group_id}/${data.new.id}/metrics`,
    )
    const steps = await drawn(page, KEY, [data.new.id])
    expect(steps[data.new.id]).toBeGreaterThan(data.new.steps! * 0.99)
    const levelBefore = await displayedLevel(page, KEY)
    const bucketsBefore = calls.buckets.length

    await dragZoom(page, KEY, 0.4)
    await expect.poll(() => displayedLevel(page, KEY)).toBeLessThan(levelBefore)
    await drawn(page, KEY, [data.new.id])
    expect(calls.buckets.length).toBeGreaterThan(bucketsBefore)
    expect(calls.fullHistory).toEqual([])
    // The browser saw the delay too, on every bucket answer.
    expect(timings.length).toBeGreaterThan(0)
    for (const elapsed of timings) expect(elapsed).toBeGreaterThanOrEqual(SLOW_LINK.latencyMs! - 5)
    const served = await expectSlowedApi([data.new.id])
    // Far less than the points themselves (a step and a value, 8 bytes each).
    const bytes = served.reduce((sum, request) => sum + request.bytes, 0)
    expect(bytes).toBeLessThan(data.new.steps! * 16 * 0.1)
  })

  test('an old-schema experiment draws on a slow link and is not migrated', async ({ page }) => {
    test.skip(!data.old, 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const old = data.old!
    const calls = recordApi(page)
    await expectUsableWhileLoading(page, [old.id], `/experiments/${old.group_id}/${old.id}/metrics`)
    const steps = await drawn(page, KEY, [old.id])
    expect(steps[old.id]).toBeGreaterThan(2_900)
    expect(calls.fullHistory).toEqual([])
    await expectSlowedApi([old.id])
    expect(userVersion(old.db!)).toBe(2)
  })

  test('old, new and live experiments are compared on a slow link', async ({ page }) => {
    const ids = [data.new.id, data.live.id, ...(data.old ? [data.old.id] : [])]
    const calls = recordApi(page)
    await expectUsableWhileLoading(
      page,
      ids,
      `/experiments/comparison?${ids.map((id) => `ids=${id}`).join('&')}`,
    )
    const steps = await drawn(page, KEY, ids)
    expect(steps[data.new.id]).toBeGreaterThan(data.new.steps! * 0.99)
    // Buckets over the longest run's range: the old run's 3,000 steps end in a bucket of about
    // a thousand steps, drawn at its middle.
    if (data.old) expect(steps[data.old.id]).toBeGreaterThan(2_000)
    if (data.old) expect(steps[data.old.id]).toBeLessThan(3_000)
    expect(calls.fullHistory).toEqual([])
    await expectSlowedApi(ids)
  })

  test('the refresh button picks up appended points on a slow link', async ({ page }) => {
    const calls = recordApi(page)
    await open(page, `/experiments/${data.live.group_id}/${data.live.id}/metrics`, SLOW_FLOW)
    const before = (await drawn(page, KEY, [data.live.id]))[data.live.id]!
    await expectRefreshShowsAppended(page, calls, before)
    await expectSlowedApi([data.live.id])
  })
  test('a trace of a new-schema experiment on a slow link: its structure, then the selected span', async ({
    page,
  }) => {
    const experiment = data.traces
    const { large, root } = TRACES.big
    const calls = recordTraceApi(page, experiment.id)
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`, SLOW_FLOW)
    await openTrace(page, TRACES.big.trace_id)
    const dialog = traceDialog(page)
    await expectVirtualisedTree(dialog, TRACES)
    await spanRow(dialog, large.span).click()
    await expectLargeValue(spanAttribute(dialog, large.key), large.chars!, large.start)
    expect(calls.structure.map((call) => call.search)).toEqual(['?payloads=false'])
    expect(calls.spans).toEqual([root.span_id, large.span_id])
    const served = await expectSlowedApi([experiment.id])
    // The span with the 1 MiB value crosses the link at its rate.
    const span = served.find((request) => request.path.endsWith(`/spans/${large.span_id}`))!
    expect(span.endedAt - span.startedAt).toBeGreaterThanOrEqual(
      SLOW_LINK.latencyMs! + (large.chars! / SLOW_LINK.bytesPerSecond!) * 1000 * 0.9,
    )
  })
})
