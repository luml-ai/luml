// The traces and evals views of @luml/experiments, as the platform and Flow both show them, and
// the data trace_data.py logs into the experiments under test.
import { expect, type Locator, type Page } from '@playwright/test'

interface TraceExpectation {
  index: number
  span_count: number
  execution_time_ns: number
  state: string
  eval_id: string
}

interface SpanExpectation {
  span: string
  span_id: string
  key: string
  chars?: number
  start?: string
  value?: string
}

/** Traces the viewer reads a page (the `limit` of its trace store's first request). */
const TRACES_PAGE_SIZE = 20

/** What trace_data.py's `expected()` says the views show. */
export interface TraceData {
  dataset: string
  trace_count: number
  traces: Record<string, TraceExpectation>
  big: {
    trace_id: string
    span_count: number
    execution_time_ns: number
    state: string
    first_rows: string[]
    root: { span_id: string; key: string; value: string }
    large: SpanExpectation
    medium: SpanExpectation
    small: SpanExpectation
  }
  eval_count: number
  evals: Record<string, { index: number; trace_id: string; scores: Record<string, unknown> }>
  averages: Record<string, number>
  attribute_keys: string[]
}

/** The duration text of the viewer (getFormattedExecutionTime) for milliseconds and seconds. */
export function durationText(ns: number): string {
  return ns < 1e9 ? `${Math.round(ns / 1e6)}ms` : `${(ns / 1e9).toFixed(2)}s`
}

/** The line under a large value's preview (largeValue.ts), for an ASCII value. */
export function previewLine(chars: number): string {
  const mib = 1024 * 1024
  const size = chars >= mib ? `${(chars / mib).toFixed(1)} MB` : `${(chars / 1024).toFixed(1)} KB`
  return `First 2,000 characters of ${size}.`
}

export function traceRows(page: Page): Locator {
  return page.locator('.traces-table tbody tr')
}

export async function rowCells(row: Locator): Promise<string[]> {
  return (await row.locator('td').allInnerTexts()).map((text) => text.trim())
}

/** ID, execution time, state and span count, the first four columns of the traces table. */
export async function expectTraceRow(
  row: Locator,
  traceId: string,
  expected: { span_count: number; execution_time_ns: number; state: string },
  evalId: string | null,
) {
  await expect(row.locator('td').first()).toHaveText(traceId)
  expect((await rowCells(row)).slice(0, 4)).toEqual([
    traceId,
    durationText(expected.execution_time_ns),
    expected.state,
    String(expected.span_count),
  ])
  const evals = row.getByRole('button', { name: /^eval-/ })
  if (evalId) await expect(evals).toHaveText([evalId])
  else await expect(evals).toHaveCount(0)
}

/**
 * Sorts the traces table by execution time (no two traces share one) both ways, then scrolls it
 * to a trace on its second page.
 */
export async function expectTracesSortedAndPaged(page: Page, data: TraceData) {
  // trace_data.py: a regular trace takes (10 + index) ms and the big one is the longest, so
  // shortest first a regular trace sits at its index, and longest first after the big one.
  const regular = Object.entries(data.traces).sort(([, a], [, b]) => a.index - b.index)
  const longestFirstPosition = (index: number) => data.trace_count - 1 - index
  const duration = page.getByRole('columnheader', { name: 'execution time' })
  await duration.click()
  for (const [id, expected] of regular.slice(0, 3)) {
    await expectTraceRow(traceRows(page).nth(expected.index), id, expected, expected.eval_id)
  }
  await duration.click()
  await expectTraceRow(traceRows(page).first(), data.big.trace_id, data.big, null)
  const [longestId, longest] = regular.at(-1)!
  expect(longestFirstPosition(longest.index)).toBe(1)
  await expectTraceRow(traceRows(page).nth(1), longestId, longest, longest.eval_id)

  // The table asks for the next page when it is scrolled to its end.
  const onSecondPage = regular.filter(
    ([, trace]) => Math.floor(longestFirstPosition(trace.index) / TRACES_PAGE_SIZE) === 1,
  )
  expect(onSecondPage).toHaveLength(1)
  const paged = onSecondPage[0]![0]
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
  const expected = data.traces[paged]!
  await expectTraceRow(row, paged, expected, expected.eval_id)
}

/** Sorted longest first, so the big trace is the first row without a search (which reads). */
export async function sortLongestFirst(page: Page, data: TraceData) {
  const duration = page.getByRole('columnheader', { name: 'execution time' })
  const firstId = traceRows(page).first().locator('td').first()
  await duration.click()
  await expect(firstId).toHaveText('trace-0000')
  await duration.click()
  await expect(firstId).toHaveText(data.big.trace_id)
}

export async function clickFirstTrace(page: Page, traceId: string) {
  await traceRows(page).first().getByRole('button', { name: traceId, exact: true }).click()
}

/** PrimeVue's error toast, in the toast host of the platform and of Flow. */
const ERROR_TOAST = '.p-toast-message-error'

export function errorToasts(page: Page): Locator {
  return page.locator(ERROR_TOAST)
}

/**
 * Records, from the page's first script on, every error toast shown (a toast goes after 3 s, so
 * one shown and gone before the check still counts), every uncaught error and unhandled
 * rejection, and console errors about the snapshot worker. Call before the page is opened.
 */
export async function recordErrors(page: Page): Promise<() => Promise<string[]>> {
  const seenByNode: string[] = []
  page.on('pageerror', (error) => seenByNode.push(`page error: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error' && /worker|terminated/i.test(message.text()))
      seenByNode.push(`console error: ${message.text()}`)
  })
  await page.addInitScript((selector) => {
    // Toasts are kept as elements and read when checked: their text may come after insertion.
    const seen: (string | Element)[] = []
    Object.assign(window, { __e2eErrors: seen })
    window.addEventListener('unhandledrejection', (event) =>
      seen.push(`unhandled rejection: ${String(event.reason)}`),
    )
    new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (!(node instanceof Element)) continue
          const toasts = node.matches(selector) ? [node] : [...node.querySelectorAll(selector)]
          for (const toast of toasts) {
            // Vue's TransitionGroup adds and removes an empty, hidden clone of each toast that
            // moves when another one comes or goes.
            if (toast.classList.contains('p-toast-message-move') || seen.includes(toast)) continue
            seen.push(toast)
          }
        }
      }
    }).observe(document, { childList: true, subtree: true })
  }, ERROR_TOAST)
  return async () => [
    ...seenByNode,
    ...(await page.evaluate(() =>
      ((window as unknown as { __e2eErrors?: (string | Element)[] }).__e2eErrors ?? []).map(
        (item) => (typeof item === 'string' ? item : `toast: ${item.textContent?.trim()}`),
      ),
    )),
  ]
}

/**
 * Runs the timers a closed view left behind at once, as time would run them (the traces table
 * reloads 500 ms after its parameters change, and they are reset when it closes). The page's
 * clock must be installed before the page opened.
 */
export async function runLeftTimers(page: Page) {
  await page.clock.runFor(2_000)
}

/** Narrows the traces table to one trace by its search box and opens it. */
export async function openTrace(page: Page, traceId: string) {
  await page.getByPlaceholder('Search traces').fill(traceId)
  await expect(traceRows(page)).toHaveCount(1, { timeout: 60_000 })
  await expect(traceRows(page).first().locator('td').first()).toHaveText(traceId)
  await traceRows(page).first().getByRole('button', { name: traceId, exact: true }).click()
}

/** The trace dialog: its span tree on the left, the selected span on the right. */
export function traceDialog(page: Page): Locator {
  return page
    .getByRole('dialog')
    .filter({ has: page.locator('.label', { hasText: /^\s*Trace\s+\(\d+ items\)\s*$/ }) })
}

export function spanRow(dialog: Locator, name: string): Locator {
  return dialog
    .locator('.row')
    .filter({ has: dialog.page().getByRole('heading', { name, exact: true }) })
}

/** One attribute of the selected span, by its key. */
export function spanAttribute(dialog: Locator, key: string): Locator {
  return dialog
    .locator('.body .item')
    .filter({ has: dialog.page().getByRole('heading', { name: key, exact: true }) })
}

/** A value over 2,000 characters shows its start, its size and the Show all and Download buttons. */
export async function expectLargeValue(item: Locator, chars: number, start?: string) {
  await expect(item.getByText(previewLine(chars), { exact: true })).toBeVisible({
    timeout: 60_000,
  })
  await expect(item.getByRole('button', { name: 'Show all' })).toBeVisible()
  await expect(item.getByRole('button', { name: 'Download' })).toBeVisible()
  if (start)
    await expect(item.locator('.content > div').first()).toHaveText(new RegExp(`^${start} `))
}

/** The span tree shows the trace's first rows and keeps only the rows in view in the DOM. */
export async function expectVirtualisedTree(dialog: Locator, data: TraceData) {
  await expect(dialog.locator('.label').first()).toHaveText(
    new RegExp(`^\\s*Trace\\s+\\(${data.big.span_count} items\\)\\s*$`),
    { timeout: 60_000 },
  )
  const names = dialog.locator('.row h4')
  await expect
    .poll(async () => (await names.allInnerTexts()).slice(0, data.big.first_rows.length), {
      timeout: 60_000,
    })
    .toEqual(data.big.first_rows)
  const rendered = await dialog.locator('.row').count()
  expect(rendered).toBeGreaterThan(data.big.first_rows.length)
  expect(rendered, 'span rows in the DOM').toBeLessThan(60)
  await expect(
    spanRow(dialog, data.big.large.span).locator('[class*="lucide-message-square-more"]'),
  ).toHaveCount(1)
  await expect(
    spanRow(dialog, data.big.medium.span).locator('[class*="lucide-wrench"]'),
  ).toHaveCount(1)
  // The root span is selected first; its payload is the only one read with the tree.
  await expect(spanAttribute(dialog, data.big.root.key).locator('.content')).toHaveText(
    data.big.root.value,
    { timeout: 60_000 },
  )
}

/** The average score chips of a dataset shown for one experiment. */
export async function expectAverageScores(page: Page, averages: Record<string, number>) {
  for (const [name, value] of Object.entries(averages)) {
    await expect(page.locator('.scores .score').filter({ hasText: name }).first()).toHaveText(
      new RegExp(`^\\s*${name}\\s*${value.toFixed(3)}\\s*$`),
      { timeout: 60_000 },
    )
  }
}

export function evalRows(page: Page): Locator {
  return page.locator('.evals-table tbody tr')
}

/** Narrows the evals table to one eval by its search box; resolves to its rows. */
export async function searchEval(page: Page, evalId: string, models = 1): Promise<Locator> {
  await page.getByPlaceholder('Search evals').fill(evalId)
  await expect(evalRows(page)).toHaveCount(models, { timeout: 60_000 })
  await expect(evalRows(page).first().getByRole('button').first()).toHaveText(evalId)
  return evalRows(page)
}

/** The eval's cells hold its scores as the table writes them. */
export function scoreTexts(scores: Record<string, unknown>): string[] {
  return Object.values(scores).map(String)
}

/** The field names the traces filter editor offers, read from its field list. */
export async function traceFilterFields(page: Page): Promise<string[]> {
  const toolbar = page.locator('.toolbar').filter({ has: page.getByPlaceholder('Search traces') })
  await toolbar.getByRole('button', { name: 'Filters' }).click()
  const popover = page.locator('.table-filter-popover')
  await popover.getByRole('button', { name: 'Add filter' }).click()
  await popover.getByRole('combobox', { name: 'Choose field' }).last().click()
  const options = popover.getByRole('option')
  await expect(options.first()).toBeVisible()
  const fields = await options.allInnerTexts()
  await page.keyboard.press('Escape')
  await expect(options).toHaveCount(0)
  await toolbar.getByRole('button', { name: 'Filters' }).click()
  await expect(popover).toBeHidden()
  return fields
}

/** The root span of a regular trace is selected first; its attributes name the trace. */
export async function expectRegularTrace(dialog: Locator, index: number) {
  await expect(dialog.locator('.body .header-left h4')).toHaveText('request')
  await expect(spanAttribute(dialog, 'request.index').locator('.content')).toHaveText(
    String(index),
    { timeout: 60_000 },
  )
}
