import { test, expect, type Locator, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

// Flow end to end: the real Flow server of this worktree with its web bundle built from this
// worktree, on one store holding an experiment of released luml-sdk 0.5.0 (old schema), one
// of this SDK (new schema) and a running one that another process appends to.

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
}

const env = (name: string): string => {
  const value = process.env[name]
  if (!value) throw new Error(`${name} is not set; run the suite through run.sh`)
  return value
}

const FLOW = env('E2E_FLOW_URL')
const FLOW_DIR = env('E2E_FLOW_DIR')
const data = JSON.parse(readFileSync(join(FLOW_DIR, 'flow.json'), 'utf-8')) as FlowData
const SDK_DIR = join(env('E2E_REPO'), 'sdk/python/sdk')
const KEY = 'train/loss'

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

async function open(page: Page, path: string) {
  await page.goto(`${FLOW}${path}#session-token=${env('E2E_FLOW_TOKEN')}`)
}

function chartPlot(page: Page, key: string): Locator {
  return page
    .locator(`[data-testid="metric-chart"][data-metric-key="${key}"]`)
    .getByTestId('metric-plot')
    .first()
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
  await expect(
    page.locator(`[data-testid="metric-chart"][data-metric-key="${key}"]`),
  ).toHaveAttribute('data-state', 'final', { timeout: 60_000 })
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
        live.id,
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
    .poll(async () => (await lastSteps(plot))[live.id] ?? 0, { timeout: 60_000 })
    .toBeGreaterThan(before + appended / 2)
  expect(calls.catalog.length).toBeGreaterThan(catalogsBefore)
  expect(calls.fullHistory).toEqual([])
})
