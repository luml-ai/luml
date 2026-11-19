// Checks of the platform specs that read what a view shows against the data that was logged:
// chart points against the logged series, CSV downloads, the table filter editor, and
// navigation inside the app.
import { expect, type Download, type Locator, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { parseCsv } from './csv'

/** What platform_expected.py records for an experiment of the suite. */
export interface LoggedExperiment {
  static: Record<string, unknown>
  metrics: Record<string, number[]>
}

interface PlotTrace {
  uid?: string
  x: (number | null)[]
  y: (number | null)[]
}

interface Bucket {
  first: number
  last: number
  low: number
  high: number
}

/** The line and band traces Plotly holds for one experiment of a chart card. */
async function plotTraces(card: Locator, modelId: string) {
  const traces = await card
    .getByTestId('metric-plot')
    .first()
    .evaluate((element) =>
      ((element as unknown as { data?: PlotTrace[] }).data ?? []).map((trace) => ({
        uid: String(trace.uid ?? ''),
        x: [...trace.x],
        y: [...trace.y],
      })),
    )
  return {
    line: traces.find((trace) => trace.uid === `${modelId}-line`),
    band: traces.find((trace) => trace.uid === `${modelId}-band`),
  }
}

/**
 * The buckets of a band trace (bucketTraces.ts): each run of buckets is one polygon, its upper
 * edge `(first, high), (last, high)` per bucket, then its lower edge back, `(last, low), (first,
 * low)`; runs are separated by nulls.
 */
function bandBuckets(band: PlotTrace): Bucket[] {
  const buckets: Bucket[] = []
  let start = 0
  while (start < band.x.length) {
    let end = band.x.indexOf(null, start)
    if (end === -1) end = band.x.length
    const count = (end - start) / 4
    expect(Number.isInteger(count), 'a band run has an upper and a lower edge').toBe(true)
    for (let index = 0; index < count; index++) {
      const top = start + index * 2
      const bottom = end - 2 - index * 2
      buckets.push({
        first: band.x[top] as number,
        last: band.x[top + 1] as number,
        high: band.y[top] as number,
        low: band.y[bottom] as number,
      })
      expect([band.x[bottom + 1], band.x[bottom]]).toEqual([band.x[top], band.x[top + 1]])
    }
    start = end + 1
  }
  return buckets
}

function expectClose(actual: number, expected: number, what: string) {
  const tolerance = 1e-9 * Math.max(1, Math.abs(expected))
  expect(Math.abs(actual - expected), `${what}: ${actual} against ${expected}`).toBeLessThanOrEqual(
    tolerance,
  )
}

/**
 * The chart of one experiment draws exactly what was logged: at level 0 every point; above it,
 * one bucket per run of consecutive steps that covers every step once, its band edges the min
 * and max and its line point the mean of the logged values in it. Returns the bucket count.
 */
export async function expectChartOfLoggedValues(
  card: Locator,
  modelId: string,
  values: number[],
): Promise<number> {
  const { line, band } = await plotTraces(card, modelId)
  expect(line, `${modelId}: a line`).toBeDefined()
  if (!band) {
    expect(line!.x).toEqual(values.map((_, step) => step))
    line!.y.forEach((value, step) => expectClose(value!, values[step]!, `step ${step}`))
    return values.length
  }
  const buckets = bandBuckets(band)
  expect(buckets.length, 'the band and the line have the same buckets').toBe(line!.x.length)
  expect(buckets[0]!.first).toBe(0)
  expect(buckets.at(-1)!.last).toBe(values.length - 1)
  buckets.forEach((bucket, index) => {
    if (index)
      expect(bucket.first, `bucket ${index} follows the last one`).toBe(
        buckets[index - 1]!.last + 1,
      )
    const logged = values.slice(bucket.first, bucket.last + 1)
    const where = `steps ${bucket.first} to ${bucket.last}`
    expectClose(bucket.low, Math.min(...logged), `min of ${where}`)
    expectClose(bucket.high, Math.max(...logged), `max of ${where}`)
    expect(line!.x[index]).toBe((bucket.first + bucket.last) / 2)
    const mean = logged.reduce((sum, value) => sum + value, 0) / logged.length
    expectClose(line!.y[index]!, mean, `mean of ${where}`)
  })
  return buckets.length
}

/** The CSV a toolbar's Export CSV button downloads, as records by its header. */
export async function exportedCsv(
  page: Page,
  toolbar: Locator,
  fileName: string,
): Promise<{ header: string[]; rows: Record<string, string>[] }> {
  const download: Promise<Download> = page.waitForEvent('download')
  await toolbar.getByRole('button', { name: 'Export CSV' }).click()
  const file = await download
  expect(file.suggestedFilename()).toBe(fileName)
  return parseCsv(readFileSync(await file.path(), 'utf-8'))
}

/** A feedback column's cell in a CSV export: its counts (tableCellToString). */
export function feedbackCsv(positive: number, negative: number): string {
  return `${positive} positive, ${negative} negative`
}

/** The toolbar of the traces or the evals table, by its search box. */
export function tableToolbar(page: Page, searchPlaceholder: string): Locator {
  return page.locator('.toolbar').filter({ has: page.getByPlaceholder(searchPlaceholder) })
}

/** Sets one filter in a table's filter editor and applies it, as a user does. */
export async function applyFilter(
  page: Page,
  toolbar: Locator,
  filter: { field: string; operator: string; value: string },
) {
  await toolbar.getByRole('button', { name: 'Filters' }).click()
  const popover = page.locator('.table-filter-popover')
  const field = popover.getByRole('combobox').nth(0)
  const operator = popover.getByRole('combobox').nth(1)
  await field.click()
  await popover.getByRole('option', { name: filter.field, exact: true }).click()
  await operator.click()
  await popover.getByRole('option', { name: filter.operator, exact: true }).click()
  await popover.locator('input#value').fill(filter.value)
  await popover.getByRole('button', { name: 'Apply' }).click()
  await expect(popover).toBeHidden()
}

/**
 * Navigates inside the app, as a link does (router.push): no page load, so the pages that stay
 * in the route keep their state. The app's router is reached through Vue's mount point.
 */
export async function navigateInApp(page: Page, url: string) {
  const target = new URL(url)
  await page.evaluate(async (path) => {
    const app = (
      document.querySelector('#app') as unknown as {
        __vue_app__: {
          config: { globalProperties: { $router: { push(to: string): Promise<unknown> } } }
        }
      }
    ).__vue_app__
    await app.config.globalProperties.$router.push(path)
  }, `${target.pathname}${target.search}`)
  await page.waitForURL(url)
}

/** The parameters of the "Model parameters" card, label to value. */
export async function staticParameters(page: Page): Promise<Record<string, string>> {
  const items = page.locator('.parameters__item')
  await expect(items.first()).toBeVisible({ timeout: 60_000 })
  const entries: [string, string][] = []
  for (const item of await items.all()) {
    entries.push([
      (await item.locator('.parameter__label').innerText()).trim(),
      (await item.locator('.parameter__value').innerText()).trim(),
    ])
  }
  return Object.fromEntries(entries)
}

/** The feedback cell text of a table row: "True\n(1)", "False\n(1)" or "-". */
export function feedbackText(value: boolean | null): string {
  return value === null ? '-' : `${value ? 'True' : 'False'} (1)`
}
