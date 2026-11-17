import type { BucketCacheView } from './BucketCache'
import type { Interval } from './IntervalSet'
import {
  bucketOf,
  bucketStepRange,
  chooseBucketLevel,
  MAX_BUCKET_LEVEL,
  MAX_RETURNED_BUCKETS,
} from './levels'
import type { ExperimentMetricCatalog, MetricCatalogEntry } from './types'

/** One chart's data need: every listed metric of every listed experiment over one step range. */
export interface BucketReadRequest {
  modelIds: string[]
  keys: string[]
  /**
   * Visible inclusive step range; a null, omitted or NaN side is the union of the series'
   * ranges. Fractional bounds are rounded inward and infinite ones clamped to safe integers.
   */
  startStep?: number | null
  endStep?: number | null
  /**
   * Buckets the chart can show across the visible range, usually its width in pixels;
   * rounded down, and at least 1.
   */
  bucketBudget: number
}

export interface PlannerOptions {
  /** A plan reading more rows than this is moved to a coarser level when one is cheaper. */
  maxCostRows: number
  /**
   * Experiments whose reads are local (an in-memory database, or a server that reads its own
   * disk): their rows do not count against `maxCostRows`.
   */
  localModelIds: ReadonlySet<string>
}

export const DEFAULT_PLANNER_OPTIONS: PlannerOptions = {
  maxCostRows: 250_000,
  localModelIds: new Set(),
}

export type BucketReadSource = 'bucket-table' | 'coarse-aggregate' | 'raw-group-by'

export interface ReadCost {
  rows: number
  bytes: number
}

/**
 * One provider query: these keys over whole buckets `[firstBucket, lastBucket]`, the request's
 * range or the part of it the cache lacks, never clipped to a key's own data.
 */
export interface PlannedFetch {
  keys: string[]
  firstBucket: number
  lastBucket: number
  startStep: number
  endStep: number
}

/**
 * A requested key the experiment has points for, with the plan's bucket range clipped to the
 * key's own range (empty, `firstBucket > lastBucket`, when no point is visible).
 */
export interface PlannedSeries {
  key: string
  firstBucket: number
  lastBucket: number
}

export interface ExperimentReadPlan {
  modelId: string
  source: BucketReadSource
  series: PlannedSeries[]
  /** Empty when the cache already holds everything. */
  fetches: PlannedFetch[]
  cost: ReadCost
}

export interface BucketReadPlan {
  level: number
  /** The level the bucket budget asks for; `level` is coarser when the plan was degraded. */
  requestedLevel: number
  degraded: boolean
  /** No level brings the cost under `maxCostRows`; the cheapest one is planned. */
  overBudget: boolean
  startStep: number
  endStep: number
  firstBucket: number
  lastBucket: number
  experiments: ExperimentReadPlan[]
  cost: ReadCost
}

const POINT_ROW_BYTES = 32
const BUCKET_ROW_BYTES = 64

export function sourceForLevel(catalog: ExperimentMetricCatalog, level: number): BucketReadSource {
  const { bucket_min_level: min, bucket_max_level: max } = catalog
  if (min === null || max === null || level < min) return 'raw-group-by'
  return level <= max ? 'bucket-table' : 'coarse-aggregate'
}

const isSafeStep = (step: number) => Math.abs(step) <= Number.MAX_SAFE_INTEGER

/**
 * Whether an entry has a step beyond +-(2^53 - 1). Such steps arrive rounded (int64 read as a
 * double, or a JSON number), so the planner works on the part inside that range only.
 */
export function hasUnsafeSteps(entry: MetricCatalogEntry): boolean {
  return !isSafeStep(entry.first_step) || !isSafeStep(entry.last_step)
}

/** The entry clipped to +-(2^53 - 1); null when none of its steps is inside. */
function safeEntry(entry: MetricCatalogEntry): MetricCatalogEntry | null {
  if (!hasUnsafeSteps(entry)) return entry
  const first = Math.max(entry.first_step, -Number.MAX_SAFE_INTEGER)
  const last = Math.min(entry.last_step, Number.MAX_SAFE_INTEGER)
  if (!(isSafeStep(first) && isSafeStep(last) && first <= last)) return null
  return { ...entry, first_step: first, last_step: last }
}

function catalogEntries(
  catalog: ExperimentMetricCatalog,
  keys: string[],
): Map<string, MetricCatalogEntry> {
  const wanted = new Set(keys)
  const entries = new Map<string, MetricCatalogEntry>()
  for (const entry of catalog.metrics) {
    const safe = wanted.has(entry.key) ? safeEntry(entry) : null
    if (safe) entries.set(entry.key, safe)
  }
  return entries
}

const stepOrNull = (step: number | null | undefined) =>
  step === null || step === undefined || Number.isNaN(step) ? null : step

const clampSafe = (step: number) =>
  Math.min(Math.max(step, -Number.MAX_SAFE_INTEGER), Number.MAX_SAFE_INTEGER)

/** The integer steps of the visible range, or null when it holds none. */
function visibleRange(
  catalogs: ReadonlyMap<string, ExperimentMetricCatalog>,
  request: BucketReadRequest,
): Interval | null {
  const requestedStart = stepOrNull(request.startStep)
  const requestedEnd = stepOrNull(request.endStep)
  let start = requestedStart === null ? null : clampSafe(Math.ceil(requestedStart))
  let end = requestedEnd === null ? null : clampSafe(Math.floor(requestedEnd))
  if (start === null || end === null) {
    let dataStart = Infinity
    let dataEnd = -Infinity
    for (const modelId of request.modelIds) {
      const catalog = catalogs.get(modelId)
      if (!catalog) continue
      for (const entry of catalogEntries(catalog, request.keys).values()) {
        dataStart = Math.min(dataStart, entry.first_step)
        dataEnd = Math.max(dataEnd, entry.last_step)
      }
    }
    start ??= dataStart
    end ??= dataEnd
  }
  return Number.isFinite(start) && Number.isFinite(end) && start <= end ? [start, end] : null
}

/** Estimated rows one key's fetch reads, assuming points spread evenly over the key's range. */
function fetchRows(
  entry: MetricCatalogEntry,
  source: BucketReadSource,
  level: number,
  topLevel: number,
  [startStep, endStep]: Interval,
): number {
  const overlapStart = Math.max(startStep, entry.first_step)
  const overlapEnd = Math.min(endStep, entry.last_step)
  if (overlapStart > overlapEnd) return 0
  const span = entry.last_step - entry.first_step + 1
  // A legacy catalog has no count: assume a dense metric.
  const count = entry.count ?? span
  const points = Math.min(count, Math.ceil((count / span) * (overlapEnd - overlapStart + 1)))
  if (source === 'raw-group-by') return points
  const readLevel = source === 'bucket-table' ? level : topLevel
  const buckets = bucketOf(overlapEnd, readLevel) - bucketOf(overlapStart, readLevel) + 1
  return Math.min(points, buckets)
}

function intervalsId(intervals: Interval[]): string {
  return intervals.map(([start, end]) => `${start}:${end}`).join(',')
}

function planExperiment(
  modelId: string,
  catalog: ExperimentMetricCatalog,
  keys: string[],
  level: number,
  [firstBucket, lastBucket]: Interval,
  cache: BucketCacheView,
): ExperimentReadPlan {
  const source = sourceForLevel(catalog, level)
  const entries = catalogEntries(catalog, keys)
  const series: PlannedSeries[] = []
  const groups = new Map<string, { keys: string[]; missing: Interval[] }>()
  for (const key of new Set(keys)) {
    const entry = entries.get(key)
    if (!entry) continue
    const first = Math.max(firstBucket, bucketOf(entry.first_step, level))
    const last = Math.min(lastBucket, bucketOf(entry.last_step, level))
    series.push({ key, firstBucket: first, lastBucket: last })
    if (first > last) continue
    // Missing ranges are taken over the request's range, not the key's own, so keys of
    // different lengths share one query; buckets exist only where points are, so the wider
    // range reads nothing more. A range with none of the key's data is not fetched.
    const missing = cache
      .missing(modelId, key, level, firstBucket, lastBucket)
      .filter(([start, end]) => end >= first && start <= last)
    if (!missing.length) continue
    const id = intervalsId(missing)
    const group = groups.get(id) ?? { keys: [], missing }
    group.keys.push(key)
    groups.set(id, group)
  }
  const fetches: PlannedFetch[] = []
  let rows = 0
  const topLevel = catalog.bucket_max_level ?? level
  for (const group of groups.values()) {
    for (const [first, last] of group.missing) {
      const steps = bucketStepRange(first, last, level)
      fetches.push({
        keys: group.keys,
        firstBucket: first,
        lastBucket: last,
        startStep: steps[0],
        endStep: steps[1],
      })
      for (const key of group.keys) {
        const entry = entries.get(key)
        if (entry) rows += fetchRows(entry, source, level, topLevel, steps)
      }
    }
  }
  const rowBytes = source === 'raw-group-by' ? POINT_ROW_BYTES : BUCKET_ROW_BYTES
  return { modelId, source, series, fetches, cost: { rows, bytes: rows * rowBytes } }
}

function planAtLevel(
  catalogs: ReadonlyMap<string, ExperimentMetricCatalog>,
  request: BucketReadRequest,
  cache: BucketCacheView,
  [startStep, endStep]: Interval,
  level: number,
  requestedLevel: number,
): BucketReadPlan {
  const bucketRange: Interval = [bucketOf(startStep, level), bucketOf(endStep, level)]
  const experiments: ExperimentReadPlan[] = []
  for (const modelId of new Set(request.modelIds)) {
    const catalog = catalogs.get(modelId)
    if (catalog) {
      experiments.push(planExperiment(modelId, catalog, request.keys, level, bucketRange, cache))
    }
  }
  const cost = experiments.reduce(
    (total, plan) => ({ rows: total.rows + plan.cost.rows, bytes: total.bytes + plan.cost.bytes }),
    { rows: 0, bytes: 0 },
  )
  return {
    level,
    requestedLevel,
    degraded: level !== requestedLevel,
    overBudget: false,
    startStep,
    endStep,
    firstBucket: bucketRange[0],
    lastBucket: bucketRange[1],
    experiments,
    cost,
  }
}

/**
 * Whether a coarser level reads fewer rows of this experiment. One without stored bucket
 * levels (revisions 0-2) reads every point in range at any level, so counting it in the cost
 * that picks the level would only push the plan to where the other experiments cost least.
 */
function degradable(
  catalogs: ReadonlyMap<string, ExperimentMetricCatalog>,
  modelId: string,
): boolean {
  const catalog = catalogs.get(modelId)
  return !!catalog && catalog.bucket_min_level !== null && catalog.bucket_max_level !== null
}

/**
 * Decides how to read a chart's buckets; pure, no I/O. All experiments are planned at one
 * level so their bucket boundaries line up. Returns null when there is nothing to show
 * (no visible range given and none of the series has points).
 */
export function planBucketRead(
  catalogs: ReadonlyMap<string, ExperimentMetricCatalog>,
  request: BucketReadRequest,
  cache: BucketCacheView,
  options: Partial<PlannerOptions> = {},
): BucketReadPlan | null {
  const { maxCostRows, localModelIds } = { ...DEFAULT_PLANNER_OPTIONS, ...options }
  const range = visibleRange(catalogs, request)
  if (!range) return null
  const wholeBudget = Number.isNaN(request.bucketBudget) ? 1 : Math.floor(request.bucketBudget)
  // An unaligned range spans one bucket more than its width, which must stay under the cap.
  const budget = Math.min(Math.max(wholeBudget, 1), MAX_RETURNED_BUCKETS - 1)
  const requestedLevel = chooseBucketLevel(range[0], range[1], budget)
  const remoteRows = (plan: BucketReadPlan, onlyDegradable: boolean) =>
    plan.experiments.reduce(
      (total, experiment) =>
        localModelIds.has(experiment.modelId) ||
        (onlyDegradable && !degradable(catalogs, experiment.modelId))
          ? total
          : total + experiment.cost.rows,
      0,
    )
  let cheapest: { plan: BucketReadPlan; rows: number } | null = null
  for (let level = requestedLevel; level <= MAX_BUCKET_LEVEL; level++) {
    const plan = planAtLevel(catalogs, request, cache, range, level, requestedLevel)
    const rows = remoteRows(plan, true)
    if (rows <= maxCostRows) return { ...plan, overBudget: remoteRows(plan, false) > maxCostRows }
    if (!cheapest || rows < cheapest.rows) cheapest = { plan, rows }
  }
  return cheapest && { ...cheapest.plan, overBudget: true }
}
