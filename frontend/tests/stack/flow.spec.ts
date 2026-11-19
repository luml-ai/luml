import type { Locator, Page, Request } from '@playwright/test'
import { execFileSync, spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { ERROR_TOAST, expect, test } from './error_guard'
import { parseCsv } from './flow_csv'
import { SLOW_LINK, ThrottleProxy } from './proxy'
import {
  clickFirstTrace,
  evalRows,
  expectAverageScores,
  expectLargeValue,
  expectNextPageAfterHeldReload,
  expectRegularTrace,
  expectTracesSortedAndPaged,
  expectVirtualisedTree,
  openTrace,
  rowCells,
  runLeftTimers,
  scoreTexts,
  scrollToEndOnce,
  searchEval,
  sortLongestFirst,
  spanAttribute,
  spanRow,
  traceDialog,
  traceRows,
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
  seed?: number
}

interface OtherExperiment extends FlowExperiment {
  steps: number
  dataset: string
  trace_ids: string[]
  evals: Record<string, number>
  averages: Record<string, number>
}

interface FlowData {
  store: string
  new: FlowExperiment
  live: FlowExperiment
  old?: FlowExperiment
  traces: FlowExperiment
  traces_old?: FlowExperiment
  fractional?: FlowExperiment
  other: OtherExperiment
  eval_search: { search: string; ids: string[]; averages: Record<string, number> }
  large_sha256: string
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
// trace_data.py: the regular traces, `trace-0000` up, and the big one.
const REGULAR_TRACE_IDS = Array.from({ length: TRACES.trace_count - 1 }, (_, index) =>
  traceIdOf(index),
)
const ALL_TRACE_IDS = [...REGULAR_TRACE_IDS, TRACES.big.trace_id]

function traceIdOf(index: number): string {
  return `trace-${String(index).padStart(4, '0')}`
}

// The raw metric history (GET /api/experiments/{id}/metrics/{key}) is the read the buckets
// replaced: no view of the web UI may ask for it, whatever the test looks at.
const RAW_HISTORY = /^\/api\/experiments\/[^/]+\/metrics\//
let rawHistoryReads: string[] = []

test.beforeEach(({ page }) => {
  rawHistoryReads = []
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (RAW_HISTORY.test(path)) rawHistoryReads.push(path)
  })
})

test.afterEach(() => {
  expect(rawHistoryReads, 'raw metric history reads').toEqual([])
})

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

/** One trace request, without payloads; its entry is recorded once its body has arrived. */
async function expectStructureRead(calls: TraceCalls) {
  await expect.poll(() => calls.structure.map((call) => call.search)).toEqual(['?payloads=false'])
}

/** The size of the full trace (with every payload), from the API the page no longer uses for it. */
async function fullTraceBytes(experimentId: string, traceId: string): Promise<number> {
  const response = await fetch(`${FLOW}/api/experiments/${experimentId}/traces/${traceId}`, {
    headers: { Authorization: `Bearer ${env('E2E_FLOW_TOKEN')}` },
  })
  expect(response.status).toBe(200)
  return (await response.arrayBuffer()).byteLength
}

function sha256(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex')
}

interface ExperimentReads {
  /** Requests by their path after `/api/experiments/<id>/`, without the query string. */
  counts: Record<string, number>
  pending: number
}

/** The evals and annotation requests one experiment's page sends, counted by endpoint. */
function recordEvalsApi(page: Page, experimentId: string): ExperimentReads {
  const reads: ExperimentReads = { counts: {}, pending: 0 }
  const prefix = `/api/experiments/${experimentId}/`
  const endpoint = (request: Request) => {
    const path = new URL(request.url()).pathname
    return path.startsWith(prefix) && /evals|annotations/.test(path)
      ? path.slice(prefix.length)
      : null
  }
  page.on('request', (request) => {
    const name = endpoint(request)
    if (name === null) return
    reads.counts[name] = (reads.counts[name] ?? 0) + 1
    reads.pending++
  })
  const ended = (request: Request) => {
    if (endpoint(request) !== null) reads.pending--
  }
  page.on('requestfinished', ended)
  page.on('requestfailed', ended)
  return reads
}

const EVALS_VIEW_READS = {
  'evals/dataset-ids': 1,
  'evals/typed-columns': 1,
  // The first page, then the next one, which the table reads ahead as its view nears the end.
  evals: 2,
  'evals/average-scores': 1,
  'evals/annotations/summary': 1,
}

/** Clicks the table's Export CSV button and reads the file it saves. */
async function exportCsv(page: Page) {
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  return parseCsv(readFileSync(await (await download).path(), 'utf-8'))
}

/** The text of each row's first button: the trace or eval id. */
async function firstButtons(rows: Locator): Promise<string[]> {
  return rows.evaluateAll((items) =>
    items.map((item) => item.querySelector('button')?.textContent?.trim() ?? ''),
  )
}

/** One filter in the traces toolbar's filter editor, applied. */
async function applyTraceFilter(page: Page, field: string, operator: string, value: string) {
  const toolbar = page.locator('.toolbar').filter({ has: page.getByPlaceholder('Search traces') })
  await toolbar.getByRole('button', { name: 'Filters' }).click()
  const popover = page.locator('.table-filter-popover')
  await popover.getByRole('combobox', { name: 'Choose field' }).last().click()
  await popover.getByRole('option', { name: field, exact: true }).click()
  await popover.locator('#operator').click()
  await popover.getByRole('option', { name: operator, exact: true }).click()
  await popover.getByPlaceholder('Put value').fill(value)
  await popover.getByRole('button', { name: 'Apply' }).click()
  await expect(popover).toBeHidden()
}

test('the experiment page reads the catalog and buckets, never the full history', async ({
  page,
}) => {
  const calls = recordApi(page)
  await open(page, `/experiments/${data.new.group_id}/${data.new.id}/metrics`)
  const steps = await drawn(page, KEY, [data.new.id])
  expect(steps[data.new.id]).toBeGreaterThan(data.new.steps! * 0.99)
  // One experiment with one metric: its catalog once, then one bucket read draws the whole run.
  expect(calls.catalog).toEqual([data.new.id])
  expect(calls.buckets).toEqual([data.new.id])
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

  // The experiments by name, and their static parameters: only the old one logged its seed.
  const names = ['flow_new', 'flow_live', ...(data.old ? ['old'] : [])]
  for (const name of names)
    await expect(page.getByText(name, { exact: true }).first()).toBeVisible()
  if (!data.old) return
  const parameters = page.locator('table').filter({ has: page.getByText('Parameters') })
  expect((await parameters.locator('thead th').allInnerTexts()).map((text) => text.trim())).toEqual(
    ['Parameters', ...names],
  )
  expect(await rowCells(parameters.locator('tbody tr').filter({ hasText: 'seed' }))).toEqual([
    'seed',
    '-',
    '-',
    String(data.old.seed),
  ])
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
    expect(experiment.user_version).toBe(format === 'new' ? 3 : 2)
    const { large, medium, small, root } = TRACES.big
    const calls = recordTraceApi(page, experiment.id)
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`)
    await openTrace(page, TRACES.big.trace_id)
    const dialog = traceDialog(page)
    await expectVirtualisedTree(dialog, TRACES)
    await expectStructureRead(calls)
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

    await test.step('the large value in full: shown, copied and downloaded', async () => {
      await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
      const largeValue = spanAttribute(dialog, large.key)
      await largeValue.getByRole('button', { name: 'Show all' }).click()
      const viewer = page.getByRole('dialog', { name: large.key })
      await expect(viewer.locator('.line').first()).toHaveText(new RegExp(`^${large.start} `))
      await viewer.getByRole('button', { name: 'Copy' }).click()
      const copied = await page.evaluate(() => navigator.clipboard.readText())
      expect(sha256(copied), 'the copied value').toBe(data.large_sha256)
      // Escape closes the viewer only; the trace stays open under it.
      await page.keyboard.press('Escape')
      await expect(viewer).toBeHidden()
      await expect(dialog).toBeVisible()
      const download = page.waitForEvent('download')
      await largeValue.getByRole('button', { name: 'Download' }).click()
      const saved = readFileSync(await (await download).path())
      expect(sha256(saved), 'the downloaded value').toBe(data.large_sha256)
      // Shown, copied and saved from the span read before: no more reads.
      expect(calls.spans).toEqual([root.span_id, large.span_id, small.span_id])
    })
  })

  test(`the traces of a ${format}-schema experiment are listed, sorted and paged`, async ({
    page,
  }) => {
    test.skip(!data[key], 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const experiment = data[key]!
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`)
    await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
      timeout: 60_000,
    })
    await expectTracesSortedAndPaged(page, TRACES)
    if (experiment.db) expect(userVersion(experiment.db)).toBe(experiment.user_version)
  })

  test(`the evals of a ${format}-schema experiment: scores, rows and the eval's trace`, async ({
    page,
  }) => {
    test.skip(!data[key], 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const experiment = data[key]!
    expect(experiment.user_version).toBe(format === 'new' ? 3 : 2)
    const reads = recordEvalsApi(page, experiment.id)
    const traceCalls = recordTraceApi(page, experiment.id)
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/evals`)
    await expectAverageScores(page, TRACES.averages)
    await expect(evalRows(page).first()).toBeVisible()
    await expect.poll(() => reads.pending).toBe(0)
    // One dataset: the dataset ids once, then for it its columns, two pages of rows, its score
    // averages and its annotation summary; a read per dataset more would be a reload.
    expect(reads.counts).toEqual(EVALS_VIEW_READS)

    await test.step('the evals exported as CSV', async () => {
      const { header, rows } = await exportCsv(page)
      expect(header).toEqual(
        expect.arrayContaining([
          'id',
          'inputs.question',
          'outputs.answer',
          'scores.accuracy',
          'scores.passed',
          'scores.tokens',
        ]),
      )
      expect(rows.map((row) => row.id).sort()).toEqual(
        Array.from(
          { length: TRACES.eval_count },
          (_, index) => `eval-${String(index).padStart(4, '0')}`,
        ),
      )
      for (const [id, item] of Object.entries(TRACES.evals)) {
        const row = rows.find((candidate) => candidate.id === id)!
        expect(row['inputs.question']).toBe(`Question ${item.index}?`)
        expect(row['outputs.answer']).toBe(`Answer ${item.index}`)
        for (const [name, value] of Object.entries(item.scores)) {
          expect(row[`scores.${name}`], `${id} ${name}`).toBe(String(value))
        }
      }
    })

    await test.step('the score averages of searched evals', async () => {
      const searched = data.eval_search
      await page.getByPlaceholder('Search evals').fill(searched.search)
      await expect(evalRows(page)).toHaveCount(searched.ids.length, { timeout: 60_000 })
      expect((await firstButtons(evalRows(page))).sort()).toEqual(searched.ids)
      await expectAverageScores(page, searched.averages)
    })

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
    // The eval's trace: its structure once, then its root span, selected first, once.
    await expectStructureRead(traceCalls)
    expect(traceCalls.spans).toEqual([`${expected.trace_id}-root`])
    if (experiment.db) expect(userVersion(experiment.db)).toBe(experiment.user_version)
  })

  test(`the traces of a ${format}-schema experiment exported as CSV, then filtered by an attribute`, async ({
    page,
  }) => {
    test.skip(!data[key], 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const experiment = data[key]!
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`)
    await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
      timeout: 60_000,
    })
    const all = await exportCsv(page)
    expect(all.header.slice(0, 4)).toEqual(['trace_id', 'execution_time', 'state', 'span_count'])
    expect(all.rows.map((row) => row.trace_id).sort()).toEqual([...ALL_TRACE_IDS].sort())
    const expectedRows: [string, { execution_time_ns: number; span_count: number }, string][] = [
      ...Object.entries(TRACES.traces).map(
        ([id, trace]) => [id, trace, trace.eval_id] as [string, typeof trace, string],
      ),
      [TRACES.big.trace_id, TRACES.big, ''],
    ]
    for (const [id, trace, evalId] of expectedRows) {
      const row = all.rows.find((candidate) => candidate.trace_id === id)!
      expect([row.execution_time, row.span_count, row.evals], id).toEqual([
        String(trace.execution_time_ns),
        String(trace.span_count),
        evalId,
      ])
    }

    // trace_data.py: a regular trace's `user.tier` is "pro" at odd indexes; the big one has none.
    const pro = REGULAR_TRACE_IDS.filter((_, index) => index % 2 === 1)
    await applyTraceFilter(page, 'attributes.user.tier', '=', '"pro"')
    await expect(
      page.locator('.traces-table tbody tr[data-p-index] td:first-child').first(),
    ).toHaveText(/^trace-/)
    await expect
      .poll(
        async () => {
          const listed = await page
            .locator('.traces-table tbody tr[data-p-index] td:first-child')
            .allInnerTexts()
          return listed.length > 0 && listed.every((id) => pro.includes(id.trim()))
        },
        { message: 'only "pro" traces are listed' },
      )
      .toBe(true)
    const filtered = await exportCsv(page)
    expect(filtered.rows.map((row) => row.trace_id).sort()).toEqual(pro)
    if (experiment.db) expect(userVersion(experiment.db)).toBe(experiment.user_version)
  })
}

// "Shows no error": the error guard fails these on any error toast or error left behind.
test.describe('leaving an experiment in Flow', () => {
  test.beforeEach(async () => {
    await PROXY.reset()
  })

  test.afterEach(async () => {
    await PROXY.reset()
  })

  test('leaving an experiment while a trace read is held shows no error', async ({ page }) => {
    const experiment = data.traces
    const traceRead = `/api/experiments/${experiment.id}/traces/${TRACES.big.trace_id}`
    await page.clock.install()
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`, SLOW_FLOW)
    await sortLongestFirst(page, TRACES)
    await PROXY.configure({ stallMatching: `^${traceRead}\\?` })
    const isTraceRead = (request: Request) => new URL(request.url()).pathname === traceRead
    const browserDone = Promise.race([
      page.waitForEvent('requestfinished', isTraceRead),
      page.waitForEvent('requestfailed', isTraceRead),
    ])
    await clickFirstTrace(page, TRACES.big.trace_id)
    const held = async () =>
      (await PROXY.requests()).filter((request) => request.path === traceRead && request.stalled)
    await expect.poll(async () => (await held()).length, { message: 'the read is held' }).toBe(1)

    // The breadcrumbs, inside the app as a user leaves (a reload would take the toast host too).
    await page.getByRole('link', { name: 'Groups', exact: true }).click()
    await page.waitForURL((url) => !url.pathname.includes(experiment.id))
    await expect(page.getByText('e2e', { exact: true }).first()).toBeVisible()
    await expect(traceRows(page)).toHaveCount(0)
    await PROXY.configure({ stallMatching: null })
    // Answered now, or cancelled by the page before: either way the page has handled it.
    await expect.poll(async () => (await held())[0]!.endedAt).toBeGreaterThan(0)
    await browserDone
    await runLeftTimers(page)

    // Back in the app's history: the experiment opens again and lists its traces.
    await page.goBack()
    await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
      timeout: 60_000,
    })
    // The trace answered after the close opens no dialog by itself.
    await expect(traceDialog(page)).toHaveCount(0)
  })

  for (const { tab, list, nextShown } of [
    {
      tab: 'traces',
      list: 'traces',
      nextShown: (page: Page) => page.getByText('No traces found...'),
    },
    {
      tab: 'evals',
      list: 'evals',
      nextShown: (page: Page) => page.getByText('No evals found in this experiment'),
    },
  ]) {
    test(`the ${tab} read of a left experiment does not reach the next experiment's list`, async ({
      page,
    }) => {
      // Only the left experiment has traces and evals, so any row in the next one is a leak.
      const left = data.traces
      const next = data.new
      const listRead = `/api/experiments/${left.id}/${list}`
      await page.clock.install()
      await PROXY.configure({ stallMatching: `^${listRead}\\?` })
      const held = async () =>
        (await PROXY.requests()).filter((request) => request.path === listRead && request.stalled)
      await open(page, `/experiments/${left.group_id}/${left.id}/${tab}`, SLOW_FLOW)
      await expect.poll(async () => (await held()).length, { message: 'the read is held' }).toBe(1)

      await page.getByRole('link', { name: 'Groups', exact: true }).click()
      await page.waitForURL((url) => !url.pathname.includes(left.id))
      await navigateInApp(page, `/experiments/${next.group_id}/${next.id}/${tab}`)
      await expect(nextShown(page)).toBeVisible({ timeout: 60_000 })

      const isListRead = (request: Request) => new URL(request.url()).pathname === listRead
      const browserDone = page.waitForEvent('requestfinished', isListRead)
      await PROXY.release()
      await expect.poll(async () => (await held())[0]!.endedAt).toBeGreaterThan(0)
      await browserDone
      await runLeftTimers(page)
      await expect(nextShown(page)).toBeVisible()
      // An empty table has one row, for its empty message.
      await expect(traceRows(page).getByRole('button', { name: /^trace-/ })).toHaveCount(0)
      await expect(evalRows(page)).toHaveCount(0)
    })
  }
})

/**
 * The trace ids of the traces table's first `count` rows, by their place in the list: the
 * virtual scroller draws only the rows in view, so it is scrolled down from the top.
 */
async function listedTraceIds(page: Page, count: number): Promise<string[]> {
  return page.locator('.traces-table .p-virtualscroller').evaluate(async (element, count) => {
    const ids: string[] = []
    const frame = () => new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve)))
    element.scrollTo(0, 0)
    for (let step = 0; step < 100 && ids.filter(Boolean).length < count; step++) {
      await frame()
      for (const row of element.querySelectorAll('tbody tr[data-p-index]')) {
        const index = Number(row.getAttribute('data-p-index'))
        if (index < count) ids[index] = row.querySelector('td')?.textContent?.trim() ?? ''
      }
      element.scrollBy(0, element.clientHeight / 2)
    }
    return ids
  }, count)
}

test.describe('paging while a list reloads in Flow', () => {
  test.beforeEach(async () => {
    await PROXY.reset()
  })

  test.afterEach(async () => {
    await PROXY.reset()
  })

  test('the traces list asked for its next page during a reload loads it once the reload ends', async ({
    page,
  }) => {
    const experiment = data.traces
    // The reload shows its rows, then reads the annotation summary with the list still loading.
    const summaryRead = `/api/experiments/${experiment.id}/traces/annotations/summary`
    const requests = async () =>
      (await PROXY.requests()).filter((item) => item.path === summaryRead)
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`, SLOW_FLOW)
    await expect(traceRows(page).first().locator('td').first()).toHaveText(/^trace-/, {
      timeout: 60_000,
    })
    await expectNextPageAfterHeldReload(page, TRACES, {
      hold: async () => {
        // The summary read of the shortest-first reload has its answer.
        await expect
          .poll(async () => (await requests()).filter((item) => item.endedAt === 0).length)
          .toBe(0)
        await PROXY.configure({ stallMatching: `^${summaryRead}` })
      },
      isHeld: async () => (await requests()).some((item) => item.stalled && item.endedAt === 0),
      release: () => PROXY.configure({ stallMatching: null }),
    })
  })

  test('the traces list scrolled to its end after a failed sort reload loads again in the new order', async ({
    page,
    errors,
  }) => {
    const experiment = data.traces
    const listRead = `/api/experiments/${experiment.id}/traces`
    const reads = async () => (await PROXY.requests()).filter((item) => item.path === listRead)
    errors.expect({ kind: 'response', status: 500, url: new RegExp(`${listRead}$`) })
    errors.expect({ kind: 'toast', text: /Failed on purpose by the test proxy/ })
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/traces`, SLOW_FLOW)
    const row = (index: number) =>
      page.locator(`.traces-table tbody tr[data-p-index="${index}"]`).locator('td').first()
    await expect(row(0)).toHaveText(/^trace-/, { timeout: 60_000 })
    const firstBefore = await row(0).innerText()
    await expect.poll(async () => (await reads()).some((item) => item.endedAt === 0)).toBe(false)

    // The shortest-first reload fails: the rows stay in the old order.
    await PROXY.configure({ failMatching: `^${listRead}\\?` })
    await page.getByRole('columnheader', { name: 'execution time' }).click()
    await expect
      .poll(async () => (await reads()).filter((item) => item.status === 500).length, {
        message: 'the reload failed',
      })
      .toBe(1)
    await PROXY.configure({ failMatching: null })
    await expect(page.locator(`.${ERROR_TOAST}`)).toHaveCount(1)
    await expect(row(0)).toHaveText(firstBefore)

    await scrollToEndOnce(page.locator('.traces-table .p-virtualscroller'))
    // trace_data.py: shortest first, a regular trace sits at its index.
    await expect(row(20), 'the second page, with no more scrolling').toHaveText('trace-0020')
    await expect.poll(async () => (await reads()).some((item) => item.endedAt === 0)).toBe(false)
    expect(await listedTraceIds(page, 40)).toEqual(
      Array.from({ length: 40 }, (_, index) => `trace-${String(index).padStart(4, '0')}`),
    )
  })

  test('the evals list asked for its next page during a reload loads it once, after the reload', async ({
    page,
  }) => {
    const experiment = data.traces
    // A sort reloads the dataset's rows by this read, with the list loading until it ends.
    const listRead = `/api/experiments/${experiment.id}/evals`
    const reads = async () => (await PROXY.requests()).filter((item) => item.path === listRead)
    await open(page, `/experiments/${experiment.group_id}/${experiment.id}/evals`, SLOW_FLOW)
    await expectAverageScores(page, TRACES.averages)
    await expect.poll(async () => (await reads()).some((item) => item.endedAt === 0)).toBe(false)
    await PROXY.configure({ stallMatching: `^${listRead}\\?` })
    await page.getByRole('columnheader', { name: 'accuracy' }).click()
    await expect
      .poll(
        async () => (await reads()).filter((item) => item.stalled && item.endedAt === 0).length,
        {
          message: 'the reload is held',
        },
      )
      .toBe(1)
    await scrollToEndOnce(page.locator('.evals-table .p-virtualscroller'))
    await PROXY.configure({ stallMatching: null })
    const rows = evalRows(page)
    await expect(
      rows.and(page.locator('[data-p-index="20"]')),
      'the second page, with no more scrolling',
    ).toHaveCount(1)
    await expect.poll(async () => (await reads()).some((item) => item.endedAt === 0)).toBe(false)
    // Each eval once: a request let through during the reload would add a page twice.
    const ids = await rows.evaluateAll((items) =>
      items.map((item) => item.querySelector('button')?.textContent?.trim() ?? ''),
    )
    expect(ids.length).toBeGreaterThan(1)
    expect(new Set(ids).size, ids.join(' ')).toBe(ids.length)
  })
})

/** In the running app, as its links go: its stores keep what the left experiment put there. */
async function navigateInApp(page: Page, path: string) {
  await page.evaluate((target) => {
    history.pushState(null, '', target)
    dispatchEvent(new PopStateEvent('popstate'))
  }, path)
  await page.waitForURL((url) => url.pathname === path)
}

/** Appends `count` points to an experiment's `train/loss` with this SDK; the new last step. */
function appendWithThisSdk(experimentId: string, count: number): number {
  const output = execFileSync(
    'uv',
    [
      'run',
      '--frozen',
      'python',
      join(env('E2E_HERE'), 'append_live.py'),
      data.store,
      experimentId,
      String(count),
    ],
    { cwd: SDK_DIR, encoding: 'utf-8' },
  )
  return Number(output.trim())
}

/** The refresh button has no accessible name; it is the button with the rotate icon. */
function refreshButton(page: Page): Locator {
  return page.locator('button:has([class*="lucide-rotate-ccw"])')
}

/** Another process appends to the live experiment; the refresh button shows the new points. */
async function expectRefreshShowsAppended(page: Page, calls: ApiCalls, before: number) {
  const appended = 1_000
  const lastStep = appendWithThisSdk(data.live.id, appended)
  expect(lastStep).toBeGreaterThan(before + appended / 2)
  const catalogsBefore = calls.catalog.length
  await refreshButton(page).click()
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
    await expectStructureRead(calls)
    expect(calls.spans).toEqual([root.span_id, large.span_id])
    const served = await expectSlowedApi([experiment.id])
    // The span with the 1 MiB value crosses the link at its rate.
    const span = served.find((request) => request.path.endsWith(`/spans/${large.span_id}`))!
    expect(span.endedAt - span.startedAt).toBeGreaterThanOrEqual(
      SLOW_LINK.latencyMs! + (large.chars! / SLOW_LINK.bytesPerSecond!) * 1000 * 0.9,
    )
  })
})

/** In the running app, as its links go, to a path that may carry a query string. */
async function goInApp(page: Page, target: string) {
  await page.evaluate((path) => {
    history.pushState(null, '', path)
    dispatchEvent(new PopStateEvent('popstate'))
  }, target)
  await page.waitForURL((url) => `${url.pathname}${url.search}` === target)
}

/** Lets the page run what a response it just received starts: two frames and a task. */
async function settle(page: Page) {
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve))),
      ),
  )
}

function comparisonPath(ids: string[]): string {
  return `/experiments/comparison?${ids.map((id) => `ids=${id}`).join('&')}`
}

function experimentPath(experiment: FlowExperiment, tab: string): string {
  return `/experiments/${experiment.group_id}/${experiment.id}/${tab}`
}

async function heldRequests(path: string | RegExp): Promise<number> {
  return (await PROXY.requests()).filter(
    (request) =>
      (typeof path === 'string' ? request.path === path : path.test(request.path)) &&
      request.stalled &&
      request.endedAt === 0,
  ).length
}

const EVAL_IDS = Array.from(
  { length: TRACES.eval_count },
  (_, index) => `eval-${String(index).padStart(4, '0')}`,
)

const KNOWN_IDS = [
  data.new,
  data.live,
  data.traces,
  data.other,
  data.old,
  data.traces_old,
  data.fractional,
]
  .filter((item): item is FlowExperiment => !!item)
  .map((item) => item.id)

/** Every API request of the page that names a known experiment, with the ids it names. */
function recordExperimentRequests(page: Page): { path: string; ids: string[] }[] {
  const requests: { path: string; ids: string[] }[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (!url.pathname.startsWith('/api/')) return
    const ids = KNOWN_IDS.filter((id) => `${url.pathname}${url.search}`.includes(id))
    if (ids.length) requests.push({ path: url.pathname, ids })
  })
  return requests
}

/** The score averages, and rows of these evals only. */
async function expectEvalsOf(page: Page, ids: string[], averages: Record<string, number>) {
  await expectAverageScores(page, averages)
  await expect(evalRows(page)).toHaveCount(Math.min(ids.length, 20), { timeout: 60_000 })
  const shown = await firstButtons(evalRows(page))
  expect(
    shown.every((id) => ids.includes(id)),
    shown.join(' '),
  ).toBe(true)
}

/** Rows of these traces only. */
async function expectTracesOf(page: Page, ids: string[]) {
  const firstCells = page.locator('.traces-table tbody tr[data-p-index] td:first-child')
  await expect(firstCells.first()).toHaveText(new RegExp(`^(${ids.join('|')})$`), {
    timeout: 60_000,
  })
  const shown = (await firstCells.allInnerTexts()).map((text) => text.trim())
  expect(
    shown.every((id) => ids.includes(id)),
    shown.join(' '),
  ).toBe(true)
}

async function expectOnlyLine(page: Page, id: string) {
  const steps = await drawn(page, KEY, [id])
  expect(Object.keys(steps)).toEqual([id])
}

async function leaveByBreadcrumb(page: Page, experimentId: string) {
  await page.getByRole('link', { name: 'Groups', exact: true }).click()
  await page.waitForURL((url) => !url.pathname.includes(experimentId))
  await expect(page.getByText('e2e', { exact: true }).first()).toBeVisible()
}

test.describe('moving between experiments in Flow', () => {
  test.beforeEach(async () => {
    await PROXY.reset()
  })

  test.afterEach(async () => {
    await PROXY.reset()
  })

  test('switching from one experiment straight to another reads and shows only the second one', async ({
    page,
  }) => {
    // trace_data.py's traces and evals, and the other experiment's own: no id is in both.
    const first = data.traces
    const second = data.other
    const requests = recordExperimentRequests(page)
    const switchTo = async (
      target: FlowExperiment,
      tab: string,
      move: () => Promise<unknown>,
      shown: () => Promise<void>,
    ) => {
      // The destination's own read is held: the page has switched while it knows only the URL.
      const experimentRead = `/api/experiments/${target.id}`
      await PROXY.configure({ stallMatching: `^${experimentRead} ` })
      const since = requests.length
      await move()
      await page.waitForURL((url) => url.pathname === experimentPath(target, tab))
      await expect
        .poll(() => heldRequests(experimentRead), { message: 'the experiment read is held' })
        .toBe(1)
      await PROXY.configure({ stallMatching: null })
      await shown()
      const after = requests.slice(since)
      expect(after.length).toBeGreaterThan(1)
      expect(
        after.filter((request) => request.ids.some((id) => id !== target.id)),
        'requests for another experiment after the switch',
      ).toEqual([])
    }
    const firstEvals = () => expectEvalsOf(page, EVAL_IDS, TRACES.averages)
    const secondEvals = () => expectEvalsOf(page, second.trace_ids, second.averages)

    await open(page, experimentPath(first, 'evals'), SLOW_FLOW)
    await firstEvals()
    await test.step('evals: a link, back and forward', async () => {
      await switchTo(
        second,
        'evals',
        () => navigateInApp(page, experimentPath(second, 'evals')),
        secondEvals,
      )
      await switchTo(first, 'evals', () => page.goBack(), firstEvals)
      await switchTo(second, 'evals', () => page.goForward(), secondEvals)
    })
    await test.step('traces: a link and back', async () => {
      await page.getByRole('tab', { name: 'Traces' }).click()
      await expectTracesOf(page, second.trace_ids)
      await switchTo(
        first,
        'traces',
        () => navigateInApp(page, experimentPath(first, 'traces')),
        () => expectTracesOf(page, ALL_TRACE_IDS),
      )
      await switchTo(
        second,
        'traces',
        () => page.goBack(),
        () => expectTracesOf(page, second.trace_ids),
      )
    })
    await test.step('metrics: a link and back', async () => {
      await page.getByRole('tab', { name: 'Metrics' }).click()
      await expectOnlyLine(page, second.id)
      await switchTo(
        data.new,
        'metrics',
        () => navigateInApp(page, experimentPath(data.new, 'metrics')),
        () => expectOnlyLine(page, data.new.id),
      )
      await switchTo(
        second,
        'metrics',
        () => page.goBack(),
        () => expectOnlyLine(page, second.id),
      )
    })
  })

  test('two traces clicked one after the other, the first answering last: the dialog shows the second', async ({
    page,
  }) => {
    const experiment = data.traces
    const [first, second] = [traceIdOf(0), traceIdOf(1)]
    const firstRead = `/api/experiments/${experiment.id}/traces/${first}`
    await open(page, experimentPath(experiment, 'traces'), SLOW_FLOW)
    // Shortest first: trace_data.py's first two traces are the first two rows.
    await page.getByRole('columnheader', { name: 'execution time' }).click()
    await expect(traceRows(page).nth(1).locator('td').first()).toHaveText(second, {
      timeout: 60_000,
    })
    await PROXY.configure({ stallMatching: `^${firstRead}\\?` })
    const firstAnswered = page.waitForEvent(
      'requestfinished',
      (request) => new URL(request.url()).pathname === firstRead,
    )
    await traceRows(page).nth(0).getByRole('button', { name: first, exact: true }).click()
    await expect.poll(() => heldRequests(firstRead), { message: 'the first read is held' }).toBe(1)
    await traceRows(page).nth(1).getByRole('button', { name: second, exact: true }).click()
    const dialog = traceDialog(page)
    await expectRegularTrace(dialog, 1)

    await PROXY.configure({ stallMatching: null })
    await firstAnswered
    await settle(page)
    await expect(
      spanAttribute(dialog, 'request.index').locator('.content'),
      'the dialog still shows the second trace',
    ).toHaveText('1', { timeout: 5_000 })
  })

  test('leaving the evals and the comparison while their reads are held, then coming back, loads them', async ({
    page,
  }) => {
    const experiment = data.traces
    const evalsRead = `/api/experiments/${experiment.id}/evals`
    await page.clock.install()
    await test.step('the evals', async () => {
      await PROXY.configure({ stallMatching: `^${evalsRead}\\?` })
      await open(page, experimentPath(experiment, 'evals'), SLOW_FLOW)
      await expect.poll(() => heldRequests(evalsRead), { message: 'the read is held' }).toBe(1)
      await leaveByBreadcrumb(page, experiment.id)
      const answered = page.waitForEvent(
        'requestfinished',
        (request) => new URL(request.url()).pathname === evalsRead,
      )
      await PROXY.configure({ stallMatching: null })
      await answered
      await runLeftTimers(page)
      await page.goBack()
      await expectEvalsOf(page, EVAL_IDS, TRACES.averages)
    })
    await test.step('the comparison', async () => {
      const ids = [data.new.id, data.live.id, ...(data.old ? [data.old.id] : [])]
      const bucketReads = new RegExp(`^/api/experiments/(${ids.join('|')})/metric-buckets$`)
      await PROXY.configure({
        stallMatching: `^/api/experiments/(${ids.join('|')})/metric-buckets`,
      })
      await goInApp(page, comparisonPath(ids))
      await expect
        .poll(() => heldRequests(bucketReads), { message: 'the reads are held' })
        .toBe(ids.length)
      await page.goBack()
      await page.waitForURL((url) => url.pathname.endsWith('/evals'))
      await expectAverageScores(page, TRACES.averages)
      await PROXY.configure({ stallMatching: null })
      await expect.poll(() => heldRequests(bucketReads)).toBe(0)
      await runLeftTimers(page)
      await page.goForward()
      const steps = await drawn(page, KEY, ids)
      expect(Object.keys(steps).sort()).toEqual([...ids].sort())
    })
  })

  test('a reload on a deep link shows its view again; back and forward cross experiment, list and comparison', async ({
    page,
  }) => {
    const experiment = data.traces
    const base = `/experiments/${experiment.group_id}/${experiment.id}`
    const metrics = experimentPath(data.new, 'metrics')
    const compared = [data.new.id, data.live.id]
    // The session token stays in the browser after the first open, so later links have none.
    await open(page, '/')
    await expect(page.getByText('e2e', { exact: true }).first()).toBeVisible()
    await test.step('reloads', async () => {
      const views: [string, () => Promise<unknown>][] = [
        [base, () => expect(page.getByRole('heading', { name: 'flow_traces' })).toBeVisible()],
        [`${base}/traces`, () => expectTracesOf(page, ALL_TRACE_IDS)],
        [`${base}/evals`, () => expectEvalsOf(page, EVAL_IDS, TRACES.averages)],
        [metrics, () => expectOnlyLine(page, data.new.id)],
        [comparisonPath(compared), () => drawn(page, KEY, compared)],
      ]
      for (const [path, shown] of views) {
        await page.goto(`${FLOW}${path}`)
        await shown()
        await page.reload()
        const url = new URL(page.url())
        expect(`${url.pathname}${url.search}`).toBe(path)
        await shown()
      }
    })
    await test.step('an open trace is not in the URL', async () => {
      await page.goto(`${FLOW}${base}/traces`)
      const before = page.url()
      await openTrace(page, traceIdOf(2))
      await expectRegularTrace(traceDialog(page), 2)
      expect(page.url()).toBe(before)
    })
    await test.step('back and forward', async () => {
      await page.goto(`${FLOW}/`)
      await expect(page.getByText('e2e', { exact: true }).first()).toBeVisible()
      await goInApp(page, metrics)
      await expectOnlyLine(page, data.new.id)
      await goInApp(page, comparisonPath(compared))
      await drawn(page, KEY, compared)
      await page.goBack()
      await expectOnlyLine(page, data.new.id)
      await page.goBack()
      await expect(page.getByText('e2e', { exact: true }).first()).toBeVisible()
      await page.goForward()
      await expectOnlyLine(page, data.new.id)
      await page.goForward()
      const steps = await drawn(page, KEY, compared)
      expect(Object.keys(steps).sort()).toEqual([...compared].sort())
    })
  })

  test("opening one experiment, another, then the first again shows the first one's data again", async ({
    page,
  }) => {
    const first = data.traces
    const second = data.other
    const showFirst = async () => {
      await expectTracesOf(page, ALL_TRACE_IDS)
      await page.getByRole('tab', { name: 'Evals' }).click()
      await expectEvalsOf(page, EVAL_IDS, TRACES.averages)
    }
    await open(page, experimentPath(first, 'traces'))
    await showFirst()
    await leaveByBreadcrumb(page, first.id)
    await navigateInApp(page, experimentPath(second, 'traces'))
    await expectTracesOf(page, second.trace_ids)
    await page.getByRole('tab', { name: 'Evals' }).click()
    await expectEvalsOf(page, second.trace_ids, second.averages)
    await leaveByBreadcrumb(page, second.id)
    await navigateInApp(page, experimentPath(first, 'traces'))
    await showFirst()
  })
})

interface OldSdkRound {
  id: string
  group_id?: string
  last_step: number | null
  trace_ids: string[]
  evals: Record<string, number>
}

/** Runs flow_old_live.py with the luml-sdk 0.5.0 venv: a training process on that release. */
function writeWithOldSdk(args: string[]): OldSdkRound {
  const output = execFileSync(
    env('E2E_OLD_SDK_PYTHON'),
    ['-I', join(env('E2E_HERE'), 'flow_old_live.py'), ...args],
    { encoding: 'utf-8' },
  )
  return JSON.parse(output) as OldSdkRound
}

/** The x values of one experiment's line in a chart. */
async function lineSteps(page: Page, key: string, id: string): Promise<number[]> {
  return chartPlot(page, key).evaluate((element, id) => {
    const traces = (element as unknown as { data?: Record<string, unknown>[] }).data ?? []
    const line = traces.find((trace) => new RegExp(`^${id}[-:]line$`).test(String(trace.uid)))
    return (line?.x as number[] | undefined) ?? []
  }, id)
}

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

test.describe('Flow functions on a store', () => {
  test.beforeEach(async () => {
    await PROXY.reset()
  })

  test.afterEach(async () => {
    await PROXY.reset()
  })

  test('a live experiment of luml-sdk 0.5.0: what it appends is shown, also after this SDK writes a metric to it', async ({
    page,
  }) => {
    test.skip(!data.old, 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    // A new experiment for each run of the test: this SDK's metric write migrates it.
    const started = writeWithOldSdk([
      'start',
      data.store,
      `live_old_${test.info().repeatEachIndex}`,
    ])
    const experiment = { id: started.id, group_id: started.group_id! }
    const db = join(data.store, experiment.id, 'exp.db')
    const traceIds = [...started.trace_ids]
    const scores = { ...started.evals }
    const expectAll = async () => {
      await page.getByRole('tab', { name: 'Traces' }).click()
      await expectTracesOf(page, traceIds)
      await expect(page.locator('.traces-table tbody tr[data-p-index]')).toHaveCount(
        traceIds.length,
      )
      await page.getByRole('tab', { name: 'Evals' }).click()
      await expectEvalsOf(page, Object.keys(scores), { accuracy: mean(Object.values(scores)) })
    }
    expect(userVersion(db)).toBe(2)
    await open(page, experimentPath(experiment, 'metrics'))
    let lastDrawn = (await drawn(page, KEY, [experiment.id]))[experiment.id]!
    expect(lastDrawn).toBeGreaterThan(started.last_step! / 2)

    await test.step('luml-sdk 0.5.0 appends metric points, spans and evals', async () => {
      const round = writeWithOldSdk(['append', data.store, experiment.id, '1'])
      traceIds.push(...round.trace_ids)
      Object.assign(scores, round.evals)
      await refreshButton(page).click()
      await expect
        .poll(async () => (await lastSteps(chartPlot(page, KEY)))[experiment.id] ?? 0, {
          timeout: 60_000,
        })
        .toBeGreaterThan((lastDrawn + round.last_step!) / 2)
      lastDrawn = (await drawn(page, KEY, [experiment.id]))[experiment.id]!
      expect(userVersion(db)).toBe(2)
      await expectAll()
    })

    await test.step('this SDK writes a metric point, which migrates the store', async () => {
      const lastStep = appendWithThisSdk(experiment.id, 100)
      expect(userVersion(db)).toBe(3)
      await page.getByRole('tab', { name: 'Metrics' }).click()
      await drawn(page, KEY, [experiment.id])
      await refreshButton(page).click()
      await expect
        .poll(async () => (await lastSteps(chartPlot(page, KEY)))[experiment.id] ?? 0, {
          timeout: 60_000,
        })
        .toBeGreaterThan((lastDrawn + lastStep) / 2)
    })

    await test.step('luml-sdk 0.5.0 appends spans and evals to the migrated store', async () => {
      await page.getByRole('tab', { name: 'Evals' }).click()
      await expectEvalsOf(page, Object.keys(scores), { accuracy: mean(Object.values(scores)) })
      const round = writeWithOldSdk(['append', data.store, experiment.id, '2', 'no-metrics'])
      traceIds.push(...round.trace_ids)
      Object.assign(scores, round.evals)
      await refreshButton(page).click()
      await expect(evalRows(page)).toHaveCount(Object.keys(scores).length)
      expect((await firstButtons(evalRows(page))).sort()).toEqual(Object.keys(scores).sort())
      // The averages shown with the refreshed rows; a fresh view reads them again below.
      await expect
        .soft(
          page.locator('.scores .score').filter({ hasText: 'accuracy' }).first(),
          'the score averages after the refresh',
        )
        .toHaveText(new RegExp(`^\\s*accuracy\\s*${mean(Object.values(scores)).toFixed(3)}\\s*$`), {
          timeout: 10_000,
        })
      await expectAll()
      expect(userVersion(db)).toBe(3)
    })

    await test.step('a metric point of luml-sdk 0.5.0 is refused by the migrated store', async () => {
      // The PR's promise ends here: SDK 0.5 shares a store until 0.6 first writes a metric.
      const refused = spawnSync(
        env('E2E_OLD_SDK_PYTHON'),
        ['-I', join(env('E2E_HERE'), 'flow_old_live.py'), 'append', data.store, experiment.id, '3'],
        { encoding: 'utf-8' },
      )
      expect(refused.status).not.toBe(0)
      expect(refused.stderr).toContain('this experiment uses schema revision 3')
      await page.getByRole('tab', { name: 'Metrics' }).click()
      await drawn(page, KEY, [experiment.id])
    })
  })

  test('an old-schema experiment with a fractional and a text step: the integer steps are drawn, a notice says points are left out', async ({
    page,
  }) => {
    test.skip(!data.fractional, 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const experiment = data.fractional!
    // old_sdk_experiment.py `legacy`: steps 0 up to `steps`, then one at 2.5 and one at 'oops'.
    await open(page, experimentPath(experiment, 'metrics'))
    await drawn(page, 'loss', [experiment.id])
    expect(await lineSteps(page, 'loss', experiment.id)).toEqual(
      Array.from({ length: experiment.steps! }, (_, step) => step),
    )
    const notice = page.getByTestId('experiment-status-notice')
    await expect(notice).toHaveAttribute('data-code', 'skipped-rows')
    await expect(notice).toHaveText(
      /Some metric points are not shown because their steps are not integers\./,
    )
    expect(userVersion(experiment.db!)).toBe(experiment.user_version)
  })

  test('a span data read that fails shows its error, and selecting the span again loads it', async ({
    page,
    errors,
  }) => {
    const experiment = data.traces
    const { small, root } = TRACES.big
    const spanRead = `/api/experiments/${experiment.id}/traces/${TRACES.big.trace_id}/spans/${small.span_id}`
    errors.expect({ kind: 'response', status: 500, url: new RegExp(`${spanRead}$`) })
    const calls = recordTraceApi(page, experiment.id)
    await open(page, experimentPath(experiment, 'traces'), SLOW_FLOW)
    await openTrace(page, TRACES.big.trace_id)
    const dialog = traceDialog(page)
    await expectVirtualisedTree(dialog, TRACES)

    await PROXY.configure({ failMatching: `^${spanRead}$` })
    await spanRow(dialog, small.span).click()
    await expect(dialog.locator('.body').getByText('Cannot load span data.').first()).toBeVisible()
    await PROXY.configure({ failMatching: null })
    await spanRow(dialog, small.span).click()
    await expect(spanAttribute(dialog, small.key).locator('.content')).toHaveText(small.value!)
    // The structure once; the span that failed twice (the failure, then the retry).
    await expectStructureRead(calls)
    expect(calls.spans).toEqual([root.span_id, small.span_id, small.span_id])
  })

  test('annotations of an old-schema experiment: the logged ones are shown, a written one is kept and the store is not migrated', async ({
    page,
  }) => {
    test.skip(!data.traces_old, 'no luml-sdk 0.5.0 venv: E2E_OLD_SDK_PYTHON is not set')
    const experiment = data.traces_old!
    // trace_data.py: `helpful` (true) on trace-0000's root span, `correct` on the first evals,
    // true at even indexes.
    const name = `written-${test.info().repeatEachIndex}`
    const evalId = 'eval-0001'
    const annotationsButton = (scope: Locator) =>
      scope
        .locator('.header-right')
        .getByRole('button')
        .filter({ has: page.locator('.lucide-pencil-icon') })

    await test.step('the logged span annotation', async () => {
      await open(page, experimentPath(experiment, 'traces'))
      await openTrace(page, traceIdOf(0))
      await expect(traceRows(page).first()).toContainText(/True\s*\(1\)/)
      const dialog = traceDialog(page)
      await expectRegularTrace(dialog, 0)
      await expect(annotationsButton(dialog.locator('.body'))).toHaveText('1')
      await annotationsButton(dialog.locator('.body')).click()
      const view = dialog.locator('.annotations-view')
      await expect(view).toContainText('Annotations (1)')
      await expect(view).toContainText('helpful')
      await page.keyboard.press('Escape')
      await expect(dialog).toBeHidden()
    })

    await test.step('the logged eval annotation, and one written to it', async () => {
      await page.getByRole('tab', { name: 'Evals' }).click()
      const rows = await searchEval(page, evalId)
      await expect(rows.first()).toContainText(/False\s*\(1\)/)
      await rows.first().getByRole('button', { name: evalId }).click()
      const evalDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByRole('button', { name: 'Trace', exact: true }) })
      // The logged one, and those earlier runs of this test wrote on this store.
      await expect(annotationsButton(evalDialog)).toHaveText(/^\d+\s*$/)
      const before = Number((await annotationsButton(evalDialog).innerText()).trim())
      expect(before).toBeGreaterThanOrEqual(1)
      await annotationsButton(evalDialog).click()
      await expect(evalDialog).toContainText('correct')
      await evalDialog.getByRole('button', { name: 'Add annotation' }).last().click()
      const addDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByRole('heading', { name: 'ADD ANNOTATION' }) })
      await addDialog.getByPlaceholder('Enter an annotation name').fill(name)
      await addDialog.getByRole('button', { name: 'Add annotation' }).click()
      await expect(page.getByText('Annotation added successfully')).toBeVisible()
      await expect(addDialog).toBeHidden()
      await expect(evalDialog).toContainText(`Annotations (${before + 1})`)
      await expect(evalDialog).toContainText(name)
      await page.keyboard.press('Escape')
      await expect(evalDialog).toBeHidden()
      // The search box still says eval-0001, so the table must still be narrowed to it.
      await expect.soft(evalRows(page), 'the searched eval only, after the write').toHaveCount(1, {
        timeout: 5_000,
      })
      expect(userVersion(experiment.db!), 'the annotation write left the store as it was').toBe(2)
    })

    await test.step('the written annotation after a reload', async () => {
      await page.reload()
      const rows = await searchEval(page, evalId)
      await expect(page.locator('.evals-table thead')).toContainText(name)
      await expect(rows.first()).toContainText(/False\s*\(1\)/)
      await expect(rows.first()).toContainText(/True\s*\(1\)/)
      expect(userVersion(experiment.db!)).toBe(2)
    })
  })
})
