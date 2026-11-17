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
