import { chromium } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

// What the specs open. A missing one would leave a loop over no items or a comparison of fewer
// experiments, passing; so setup fails instead. Old-SDK data is only optional locally.
const PLATFORM_LABELS = [
  'large',
  'new_a',
  'new_b',
  'short',
  'gen2_full',
  'twin_gen1',
  'twin_gen2',
  'model_gen2',
  'model_gen1',
  'old',
  'traces_new',
  'rev0',
  'sdk_0_1_0',
]
const OLD_SDK_PLATFORM_LABELS = ['fallback', 'traces_old']
const PROXIED_LABELS = { s3: ['large', 'old', 'new_a', 'new_b', 'traces_new'], azure: ['large'] }
const OLD_SDK_PROXIED_LABELS = { s3: ['traces_old'] }
const FLOW_EXPERIMENTS = ['new', 'live', 'traces', 'other']
const OLD_SDK_FLOW_EXPERIMENTS = ['old', 'traces_old', 'fractional']

interface Collection {
  artifacts: Record<string, { id?: string }>
}

interface TraceData {
  trace_count: number
  traces: object
  big: { first_rows: unknown[] }
  evals: object
  averages: object
  attribute_keys: unknown[]
}

function readJson<T>(path: string): T {
  if (!existsSync(path)) throw new Error(`${path} is missing: the prepare step did not finish`)
  return JSON.parse(readFileSync(path, 'utf-8')) as T
}

function missingTraceData(data: TraceData | undefined, where: string): string[] {
  if (!data) return [`${where}: no expected trace data`]
  const empty = [
    ['traces', Object.keys(data.traces ?? {}).length && data.trace_count],
    ['big trace rows', data.big?.first_rows?.length],
    ['evals', Object.keys(data.evals ?? {}).length],
    ['average scores', Object.keys(data.averages ?? {}).length],
    ['attribute keys', data.attribute_keys?.length],
  ] as const
  return empty.filter(([, count]) => !count).map(([name]) => `${where}: no ${name}`)
}

function checkPlatformData(workDir: string, strict: boolean) {
  const data = readJson<{
    storages: Record<string, Collection>
    proxied: Record<string, Collection>
    traces: TraceData
    old_source: string
  }>(join(workDir, 'platform.json'))
  const storages = (process.env.E2E_STORAGES ?? 's3,azure').split(',')
  const missing = missingTraceData(data.traces, 'platform')
  const labels = [...PLATFORM_LABELS, ...(strict ? OLD_SDK_PLATFORM_LABELS : [])]
  for (const storage of storages) {
    for (const label of labels) {
      if (!data.storages?.[storage]?.artifacts?.[label]?.id) missing.push(`${storage}: ${label}`)
    }
  }
  const proxiedLabels = Object.entries(PROXIED_LABELS).map(([storage, proxied]) => [
    storage,
    [...proxied, ...(strict ? (OLD_SDK_PROXIED_LABELS[storage as 's3'] ?? []) : [])],
  ]) as [string, string[]][]
  for (const [storage, proxied] of proxiedLabels) {
    for (const label of proxied) {
      if (!data.proxied?.[storage]?.artifacts?.[label]?.id)
        missing.push(`${storage} proxied: ${label}`)
    }
  }
  if (strict && data.old_source !== 'luml-sdk 0.5.0')
    missing.push(`the old-format experiment comes from ${data.old_source}`)
  return missing
}

function checkFlowData(flowDir: string, strict: boolean) {
  const data = readJson<
    Record<string, { id?: string; group_id?: string }> & { expected: TraceData }
  >(join(flowDir, 'flow.json'))
  const missing = missingTraceData(data.expected, 'Flow')
  for (const name of [...FLOW_EXPERIMENTS, ...(strict ? OLD_SDK_FLOW_EXPERIMENTS : [])]) {
    if (!data[name]?.id || !data[name]?.group_id) missing.push(`Flow: ${name}`)
  }
  return missing
}

/**
 * Checks the prepared data, then signs in once for the platform suite and saves the session for
 * every test: the backend rate-limits sign-in attempts per account, so a sign-in per test would
 * trip it.
 */
export default async function globalSetup(): Promise<void> {
  const strict = process.env.E2E_STRICT === '1'
  const workDir = process.env.E2E_WORK_DIR
  const frontend = process.env.E2E_FRONTEND_URL
  const missing = [
    ...(frontend && workDir ? checkPlatformData(workDir, strict) : []),
    ...(process.env.E2E_FLOW_DIR ? checkFlowData(process.env.E2E_FLOW_DIR, strict) : []),
  ]
  if (missing.length) throw new Error(`prepared data is incomplete:\n  ${missing.join('\n  ')}`)
  if (!frontend || !workDir) return
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage()
    await page.goto(`${frontend}/sign-in`)
    await page.getByLabel('Email').fill(process.env.DEV_ADMIN_EMAIL ?? '')
    await page.locator('#password input').fill(process.env.DEV_ADMIN_PASSWORD ?? '')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.waitForURL((url) => !url.pathname.startsWith('/sign-in'), { timeout: 60_000 })
    await page.context().storageState({ path: join(workDir, 'browser-state.json') })
  } finally {
    await browser.close()
  }
}
