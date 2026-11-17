import { BucketCache, type BucketCacheView } from './BucketCache'
import { MetricReadTimeoutError, toExperimentReadError } from './errors'
import { MAX_BUCKET_LEVEL } from './levels'
import {
  hasUnsafeSteps,
  planBucketRead,
  type BucketReadPlan,
  type BucketReadRequest,
  type PlannedFetch,
  type PlannedSeries,
  type PlannerOptions,
} from './planner'
import {
  READ_FAILED,
  type ExperimentMetricCatalog,
  type ExperimentReadError,
  type ExperimentResult,
  type ExperimentSnapshotStatus,
  type MetricBucket,
  type MetricBucketsRequest,
  type MetricBucketsResponse,
  type MetricCatalogEntry,
  type MetricCatalogsRequest,
} from './types'

/** The provider calls the store needs; every `ExperimentSnapshotProvider` has them. */
export interface MetricBucketSource {
  getExperimentStatuses(signal?: AbortSignal): Promise<ExperimentSnapshotStatus[]>
  getMetricCatalogs(
    request?: MetricCatalogsRequest,
    signal?: AbortSignal,
  ): Promise<ExperimentResult<ExperimentMetricCatalog>[]>
  getMetricBuckets(
    request: MetricBucketsRequest,
    signal?: AbortSignal,
  ): Promise<ExperimentResult<MetricBucketsResponse>[]>
}

export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000

export interface MetricBucketStoreOptions {
  /** Shared between stores to share fetched buckets; a new cache by default. */
  cache?: BucketCache
  planner?: Partial<PlannerOptions>
  /**
   * Delay before fetches start; a newer request within it replaces its chart's older one, and
   * fetches of all charts in it are merged per experiment, level and bucket range.
   */
  debounceMs?: number
  /**
   * The provider's experiments. Given, the first catalog load reads each one in its own call
   * with its own timeout, as refreshes do; otherwise all in one call.
   */
  modelIds?: string[]
  /**
   * A catalog load, refresh or bucket fetch without an answer after this fails with
   * `timed-out`, whether or not the provider honours the abort; 30 s by default.
   */
  requestTimeoutMs?: number
}

/** One metric of one experiment as the chart should draw it now. */
export interface ChartSeries {
  modelId: string
  key: string
  /** Bucket width is `4 ** level` steps. */
  level: number
  /** False while this is cached coarser data or earlier data standing in for the planned level. */
  final: boolean
  buckets: MetricBucket[]
}

export interface ChartError {
  modelId: string
  error: ExperimentReadError
}

/**
 * A chart's current data. Every emission is a new object; nothing in it is mutated later.
 * Series without any data to show yet are absent; series that are cached coarser data, or
 * the data shown before a new request or refresh, have `final: false` and are replaced by
 * later emissions. A failed fetch leaves such series in place next to its error.
 */
export interface ChartState {
  request: BucketReadRequest | null
  /** Null before the catalogs are loaded, or when there is nothing to show. */
  plan: BucketReadPlan | null
  /** True until every fetch of the plan has answered; false after any failure. */
  loading: boolean
  series: ChartSeries[]
  /** Per experiment; the other experiments' series are unaffected. */
  errors: ChartError[]
  /**
   * The cache bound is too small for this chart: some series are served from the chart's own
   * copy of its fetch answers, kept until its request changes.
   */
  cacheOverflow: boolean
}

export type ChartListener = (state: ChartState) => void

export interface SubscribeOptions {
  /** What the chart already shows (from an earlier subscription); kept until better data. */
  series?: ChartSeries[]
}

/**
 * One chart's link to the store. Usage: create with `store.subscribe(listener)`, call
 * `request()` on every change of the visible range, width, keys or experiments, and
 * `close()` when the chart unmounts. Each `request()` emits at once, keeping what the chart
 * shows (as `final: false`), then the best cached data (possibly coarser than planned), then
 * once per experiment as its fetch answers. Fetches of charts that request within one
 * debounce window are merged into one provider call per experiment, level and bucket range;
 * each chart still gets its own keys only. A newer `request()` supersedes the older one:
 * once the newer one has started its own fetches, the older one's are aborted unless a chart
 * (this one included) still needs them; late answers are cached but never emitted. Both
 * methods may be called from the listener. After `store.refreshCatalogs()` or
 * `store.reload()` changes a metric the chart shows, it re-plans by itself and emits again,
 * keeping what it shows until the new buckets arrive. The series of the current plan are
 * pinned in the cache while open. `store.dispose()` closes every subscription.
 */
export interface ChartSubscription {
  readonly state: ChartState
  request(request: BucketReadRequest): void
  close(): void
}

/** The loaded catalogs; an experiment is in exactly one of the two maps. */
export interface MetricCatalogs {
  catalogs: Map<string, ExperimentMetricCatalog>
  errors: Map<string, ExperimentReadError>
  /** Experiments read from memory or through a server, exempt from the planner's row budget. */
  localModelIds: Set<string>
  /** Read after the catalogs (some fields come from them) and again with every refresh. */
  statuses: ExperimentSnapshotStatus[]
}

/** An inclusive step range. */
export interface StepInterval {
  first: number
  last: number
}

/** Each metric's union step range over the experiments (all loaded ones by default). */
export function metricStepRanges(
  catalogs: MetricCatalogs,
  modelIds?: Iterable<string>,
): Map<string, StepInterval> {
  const ranges = new Map<string, StepInterval>()
  for (const modelId of modelIds ?? catalogs.catalogs.keys()) {
    for (const metric of catalogs.catalogs.get(modelId)?.metrics ?? []) {
      const range = ranges.get(metric.key)
      if (!range) ranges.set(metric.key, { first: metric.first_step, last: metric.last_step })
      else {
        range.first = Math.min(range.first, metric.first_step)
        range.last = Math.max(range.last, metric.last_step)
      }
    }
  }
  return ranges
}

/** One metric's union step range over the experiments; null when none of them has it. */
export function metricStepRange(
  catalogs: MetricCatalogs,
  key: string,
  modelIds?: Iterable<string>,
): StepInterval | null {
  let range: StepInterval | null = null
  for (const modelId of modelIds ?? catalogs.catalogs.keys()) {
    const entry = catalogs.catalogs.get(modelId)?.metrics.find((metric) => metric.key === key)
    if (!entry) continue
    range = range
      ? {
          first: Math.min(range.first, entry.first_step),
          last: Math.max(range.last, entry.last_step),
        }
      : { first: entry.first_step, last: entry.last_step }
  }
  return range
}

const LOCAL_TRANSPORTS = new Set<ExperimentSnapshotStatus['transport']>([
  'zip-full',
  'raw-full',
  'api',
])

function localModelIdsOf(statuses: ExperimentSnapshotStatus[]): Set<string> {
  return new Set(
    statuses
      .filter((status) => LOCAL_TRANSPORTS.has(status.transport))
      .map((status) => status.modelId),
  )
}

/** Sets `unsafeMetricSteps` from the catalogs, whichever provider read them. */
function markUnsafeSteps(
  statuses: ExperimentSnapshotStatus[],
  catalogs: Map<string, ExperimentMetricCatalog>,
): ExperimentSnapshotStatus[] {
  return statuses.map((status) =>
    catalogs.get(status.modelId)?.metrics.some(hasUnsafeSteps)
      ? { ...status, unsafeMetricSteps: true }
      : status,
  )
}

/**
 * Keys whose catalog entry changed, with the step from which their cached buckets are stale:
 * the old last step when the metric only grew past it, else null (all of it is stale, as an
 * earlier step was written or overwritten, or the key is new or gone).
 */
function changedMetrics(
  before: ExperimentMetricCatalog | undefined,
  after: ExperimentMetricCatalog,
): Map<string, number | null> {
  const old = new Map<string, MetricCatalogEntry>(
    (before?.metrics ?? []).map((entry) => [entry.key, entry]),
  )
  const changed = new Map<string, number | null>()
  for (const entry of after.metrics) {
    const previous = old.get(entry.key)
    old.delete(entry.key)
    if (!previous) changed.set(entry.key, null)
    else if (entry.last_step > previous.last_step && entry.first_step === previous.first_step) {
      changed.set(entry.key, previous.last_step)
    } else if (
      entry.last_step !== previous.last_step ||
      entry.first_step !== previous.first_step ||
      entry.count !== previous.count ||
      entry.min !== previous.min ||
      entry.max !== previous.max
    ) {
      changed.set(entry.key, null)
    }
  }
  for (const key of old.keys()) changed.set(key, null)
  return changed
}

interface CatalogRead {
  result: ExperimentResult<ExperimentMetricCatalog>
  /** The call threw or timed out, rather than answering with this experiment's error. */
  failed: boolean
  error: unknown
}

interface FetchOutcome {
  result: ExperimentResult<MetricBucketsResponse>
  /** Keys whose answer the cache bound could not hold. */
  uncached: Set<string>
}

interface SharedFetch {
  modelId: string
  level: number
  firstBucket: number
  lastBucket: number
  keys: string[]
  promise: Promise<FetchOutcome>
  controller: AbortController
  waiters: number
}

interface JoinedFetch {
  id: number
  shared: SharedFetch
}

interface WantedFetch {
  modelId: string
  fetch: PlannedFetch
}

interface PendingJob {
  level: number
  fetches: WantedFetch[]
  /** Gets one joined fetch per entry of `fetches`, in order. */
  run(joined: JoinedFetch[]): void
}

const IDLE_STATE: ChartState = {
  request: null,
  plan: null,
  loading: false,
  series: [],
  errors: [],
  cacheOverflow: false,
}

const DEFAULT_DEBOUNCE_MS = 50
// A window that keeps being extended by new requests still flushes after this many delays.
const MAX_WAIT_DEBOUNCES = 4

function disposedError(): Error {
  return new DOMException('The metric store was disposed', 'AbortError')
}

/**
 * Runs `start` with a signal that aborts when `parent` does or `timeoutMs` passes, and settles
 * then, whether or not the work honours the signal: a stalled provider call never blocks.
 */
function bounded<T>(
  start: (signal: AbortSignal) => Promise<T>,
  parent: AbortSignal,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController()
  return new Promise<T>((resolve, reject) => {
    const cleanup = () => {
      clearTimeout(timer)
      parent.removeEventListener('abort', onAbort)
    }
    const fail = (error: unknown) => {
      cleanup()
      controller.abort(error)
      reject(error)
    }
    const onAbort = () => fail(parent.reason ?? disposedError())
    const timer = setTimeout(() => fail(new MetricReadTimeoutError(timeoutMs)), timeoutMs)
    if (parent.aborted) {
      onAbort()
      return
    }
    parent.addEventListener('abort', onAbort)
    let work: Promise<T>
    try {
      work = start(controller.signal)
    } catch (error) {
      fail(error)
      return
    }
    work.then(
      (value) => {
        cleanup()
        resolve(value)
      },
      (error: unknown) => {
        cleanup()
        reject(error)
      },
    )
  })
}

function sameRequest(left: BucketReadRequest | null, right: BucketReadRequest): boolean {
  return (
    left !== null &&
    left.modelIds.join('\n') === right.modelIds.join('\n') &&
    left.keys.join('\n') === right.keys.join('\n') &&
    left.startStep === right.startStep &&
    left.endStep === right.endStep &&
    left.bucketBudget === right.bucketBudget
  )
}

function provisional(series: ChartSeries): ChartSeries {
  return series.final ? { ...series, final: false } : series
}

/**
 * Framework-free data layer for metric charts: loads the catalogs and statuses once, plans
 * every chart request, serves cached buckets at once and fetches only what is missing.
 */
export class MetricBucketStore {
  readonly cache: BucketCache
  private readonly ownsCache: boolean
  private readonly plannerOptions: Partial<PlannerOptions>
  readonly debounceMs: number
  readonly requestTimeoutMs: number
  readonly modelIds: readonly string[] | null
  private readonly lifetime = new AbortController()
  private catalogsPromise: Promise<MetricCatalogs> | null = null
  private readonly inFlight = new Map<number, SharedFetch>()
  private nextFetchId = 0
  private readonly subscriptions = new Set<StoreSubscription>()
  private readonly pendingJobs = new Map<StoreSubscription, PendingJob>()
  private batchTimer: ReturnType<typeof setTimeout> | null = null
  private batchStartedAt = 0
  // Bumped when a refresh drops a metric's buckets: answers of fetches started before it are
  // not cached for that metric, as they may hold the stale buckets just dropped.
  private readonly seriesVersions = new Map<string, number>()
  // Refreshes run one after another, so each starts from the catalogs the previous one left
  // and a slow earlier refresh never overwrites a later one.
  private refreshQueue: Promise<unknown> = Promise.resolve()

  constructor(
    private readonly source: MetricBucketSource,
    options: MetricBucketStoreOptions = {},
  ) {
    this.cache = options.cache ?? new BucketCache()
    this.ownsCache = !options.cache
    this.plannerOptions = options.planner ?? {}
    this.debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS
    this.requestTimeoutMs = options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS
    this.modelIds = options.modelIds ? [...options.modelIds] : null
  }

  get disposed(): boolean {
    return this.lifetime.signal.aborted
  }

  /**
   * Loads the catalogs, then the statuses, on first use; a failed or timed-out load is
   * retried by the next call. Rejects once the store is disposed.
   */
  loadCatalogs(): Promise<MetricCatalogs> {
    if (this.disposed) return Promise.reject(disposedError())
    if (!this.catalogsPromise) {
      const loading = this.readCatalogs().catch((error: unknown) => {
        if (this.catalogsPromise === loading) this.catalogsPromise = null
        throw error
      })
      this.catalogsPromise = loading
    }
    return this.catalogsPromise
  }

  private async readCatalogs(): Promise<MetricCatalogs> {
    const results = await this.readFirstCatalogs()
    const statuses = await this.readStatuses()
    const loaded: MetricCatalogs = {
      catalogs: new Map(),
      errors: new Map(),
      localModelIds: localModelIdsOf(statuses ?? []),
      statuses: statuses ?? [],
    }
    for (const result of results) {
      if (result.ok) loaded.catalogs.set(result.modelId, result.value)
      else loaded.errors.set(result.modelId, result.error)
    }
    loaded.statuses = markUnsafeSteps(loaded.statuses, loaded.catalogs)
    return loaded
  }

  /**
   * Each experiment in its own call when the experiments are known. When every call failed,
   * the load rejects, so the next call retries it.
   */
  private async readFirstCatalogs(): Promise<ExperimentResult<ExperimentMetricCatalog>[]> {
    if (!this.modelIds) {
      return this.bounded((signal) => this.source.getMetricCatalogs(undefined, signal))
    }
    const reads = await this.readCatalogsOneByOne(this.modelIds)
    const [firstFailure, ...otherFailures] = reads.filter((read) => read.failed)
    if (firstFailure && otherFailures.length + 1 === reads.length) throw firstFailure.error
    return reads.map((read) => read.result)
  }

  /**
   * One bounded call per experiment: a provider may wait for all its requests together (the
   * API provider does), and one slow experiment must not time out the others.
   */
  private readCatalogsOneByOne(
    modelIds: readonly string[],
    refresh = false,
  ): Promise<CatalogRead[]> {
    return Promise.all(
      modelIds.map(async (modelId): Promise<CatalogRead> => {
        const request: MetricCatalogsRequest = { modelIds: [modelId], ...(refresh && { refresh }) }
        try {
          const results = await this.bounded((signal) =>
            this.source.getMetricCatalogs(request, signal),
          )
          const result = results.find((item) => item.modelId === modelId) ?? {
            modelId,
            ok: false,
            error: { code: READ_FAILED, message: `No catalog for experiment '${modelId}'` },
          }
          return { result, failed: false, error: null }
        } catch (error) {
          if (this.disposed) throw error
          const result = { modelId, ok: false as const, error: toExperimentReadError(error) }
          return { result, failed: true, error }
        }
      }),
    )
  }

  /** Null when they could not be read: statuses only add notices and a budget exemption. */
  private async readStatuses(): Promise<ExperimentSnapshotStatus[] | null> {
    try {
      return await this.bounded((signal) => this.source.getExperimentStatuses(signal))
    } catch (error) {
      if (this.disposed) throw error
      return null
    }
  }

  private bounded<T>(start: (signal: AbortSignal) => Promise<T>): Promise<T> {
    return bounded(start, this.lifetime.signal, this.requestTimeoutMs)
  }

  subscribe(listener: ChartListener, options: SubscribeOptions = {}): ChartSubscription {
    const subscription = new StoreSubscription(this, listener, options.series ?? [])
    if (this.disposed) subscription.close()
    else this.subscriptions.add(subscription)
    return subscription
  }

  /**
   * Closes every subscription, aborts the catalog loads and fetches in flight and empties the
   * cache when the store created it. Every later call fails or does nothing.
   */
  dispose(): void {
    if (this.disposed) return
    this.lifetime.abort(disposedError())
    // A fetch is aborted when its last chart leaves, so closing them all aborts every fetch.
    for (const subscription of [...this.subscriptions]) subscription.close()
    if (this.batchTimer !== null) clearTimeout(this.batchTimer)
    this.batchTimer = null
    this.pendingJobs.clear()
    this.inFlight.clear()
    this.catalogsPromise = null
    if (this.ownsCache) this.cache.clear()
  }

  /**
   * Re-reads the catalogs (and statuses) of live experiments; the caller decides when (the
   * store runs no timers). A metric whose `last_step` grew loses its cached buckets from the
   * one holding its old `last_step` on, at every level; one whose `count`, `first_step`, `min`
   * or `max` changed otherwise (also when `last_step` grew too) loses all of them. Open charts
   * showing it re-plan and keep their current buckets until the new ones arrive. An overwrite
   * that changes none of these is not detectable; `reload()` covers it. A failed or timed-out
   * refresh keeps the old catalog and is returned per experiment. Refreshes run in call
   * order. Published snapshots never change, so refreshing them changes nothing.
   */
  refreshCatalogs(modelIds: string[]): Promise<Map<string, ExperimentReadError>> {
    return this.enqueueRefresh(modelIds, false)
  }

  /**
   * A manual reload: forgets every cached bucket of these experiments, re-reads their
   * catalogs and re-plans the charts showing them. Ordered with `refreshCatalogs()`.
   */
  reload(modelIds: string[]): Promise<Map<string, ExperimentReadError>> {
    return this.enqueueRefresh(modelIds, true)
  }

  private enqueueRefresh(
    modelIds: string[],
    dropAll: boolean,
  ): Promise<Map<string, ExperimentReadError>> {
    const refresh = this.refreshQueue.then(() => this.refreshNow(modelIds, dropAll))
    this.refreshQueue = refresh.catch(() => undefined)
    return refresh
  }

  private async refreshNow(
    modelIds: string[],
    dropAll: boolean,
  ): Promise<Map<string, ExperimentReadError>> {
    const current = await this.loadCatalogs()
    const results = (await this.readCatalogsOneByOne(modelIds, true)).map((read) => read.result)
    const statuses = await this.readStatuses()
    const next: MetricCatalogs = {
      catalogs: new Map(current.catalogs),
      errors: new Map(current.errors),
      localModelIds: statuses ? localModelIdsOf(statuses) : current.localModelIds,
      statuses: statuses ?? current.statuses,
    }
    const failures = new Map<string, ExperimentReadError>()
    const changed = new Map<string, Map<string, number | null>>()
    for (const result of results) {
      const before = current.catalogs.get(result.modelId)
      const keys = new Map<string, number | null>()
      if (dropAll) {
        const all = [...(before?.metrics ?? []), ...(result.ok ? result.value.metrics : [])]
        for (const entry of all) keys.set(entry.key, null)
      }
      if (result.ok) {
        for (const [key, fromStep] of changedMetrics(before, result.value)) {
          if (!keys.has(key)) keys.set(key, fromStep)
        }
        next.catalogs.set(result.modelId, result.value)
        next.errors.delete(result.modelId)
      } else {
        failures.set(result.modelId, result.error)
        if (!next.catalogs.has(result.modelId)) next.errors.set(result.modelId, result.error)
      }
      for (const [key, fromStep] of keys) this.dropMetric(result.modelId, key, fromStep)
      if (keys.size) changed.set(result.modelId, keys)
    }
    next.statuses = markUnsafeSteps(next.statuses, next.catalogs)
    this.catalogsPromise = Promise.resolve(next)
    const changedKeys = new Map(
      [...changed].map(([modelId, keys]) => [modelId, new Set(keys.keys())]),
    )
    for (const subscription of this.subscriptions) subscription.refreshed(changedKeys)
    return failures
  }

  /** Drops a metric's cached buckets from the one holding `fromStep` on, or all when null. */
  private dropMetric(modelId: string, key: string, fromStep: number | null): void {
    const id = JSON.stringify([modelId, key])
    this.seriesVersions.set(id, (this.seriesVersions.get(id) ?? 0) + 1)
    if (fromStep === null) this.cache.dropMetric(modelId, key)
    else this.cache.dropFrom(modelId, key, fromStep)
    // Later requests must not join a fetch whose answer will not be cached.
    for (const [fetchId, shared] of this.inFlight) {
      if (shared.modelId === modelId && shared.keys.includes(key)) this.inFlight.delete(fetchId)
    }
  }

  private versionOf(modelId: string, key: string): number {
    return this.seriesVersions.get(JSON.stringify([modelId, key])) ?? 0
  }

  /** @internal */
  unsubscribe(subscription: StoreSubscription): void {
    this.subscriptions.delete(subscription)
    this.pendingJobs.delete(subscription)
  }

  /**
   * @internal Plans the experiments together; when that throws, an experiment that cannot be
   * planned on its own is left out with its error, so it never fails the others.
   */
  plan(
    catalogs: MetricCatalogs,
    request: BucketReadRequest,
    overflow: BucketCache | null = null,
  ): { plan: BucketReadPlan | null; failures: ChartError[] } {
    try {
      return { plan: this.planTogether(catalogs, request, overflow), failures: [] }
    } catch (error) {
      const failures: ChartError[] = []
      const modelIds = request.modelIds.filter((modelId) => {
        try {
          this.planTogether(catalogs, { ...request, modelIds: [modelId] }, overflow)
          return true
        } catch (failure) {
          failures.push({ modelId, error: toExperimentReadError(failure) })
          return false
        }
      })
      if (!failures.length) throw error
      return { plan: this.planTogether(catalogs, { ...request, modelIds }, overflow), failures }
    }
  }

  /** `overflow`: a chart's own answers, which count as fetched for its plan. */
  private planTogether(
    catalogs: MetricCatalogs,
    request: BucketReadRequest,
    overflow: BucketCache | null,
  ): BucketReadPlan | null {
    const shared = this.cache
    const view: BucketCacheView = overflow
      ? {
          missing: (modelId, key, level, first, last) =>
            overflow.covers(modelId, key, level, first, last)
              ? []
              : shared.missing(modelId, key, level, first, last),
        }
      : shared
    return planBucketRead(catalogs.catalogs, request, view, {
      ...this.plannerOptions,
      localModelIds: catalogs.localModelIds,
    })
  }

  /**
   * @internal Data per series: the planned level when it covers the range (from `overflow`,
   * the chart's own answers the cache could not hold, first), else what `previous` showed if
   * it is finer than the best coarser cached level, else that coarser level.
   */
  cachedSeries(
    plan: BucketReadPlan,
    previous: ChartSeries[] | null = null,
    overflow: BucketCache | null = null,
  ): ChartSeries[] {
    const series: ChartSeries[] = []
    for (const experiment of plan.experiments) {
      for (const planned of experiment.series) {
        const cached =
          (overflow && planned.firstBucket <= planned.lastBucket
            ? readCovered(overflow, experiment.modelId, planned, plan.level)
            : null) ?? this.bestCached(experiment.modelId, planned, plan.level)
        const kept = cached?.final
          ? undefined
          : previous?.find(
              (item) => item.modelId === experiment.modelId && item.key === planned.key,
            )
        const shown = kept && (!cached || kept.level < cached.level) ? kept : cached
        if (shown) series.push(shown)
      }
    }
    return series
  }

  private bestCached(
    modelId: string,
    planned: PlannedSeries,
    plannedLevel: number,
  ): ChartSeries | null {
    if (planned.firstBucket > planned.lastBucket) {
      return { modelId, key: planned.key, level: plannedLevel, final: true, buckets: [] }
    }
    for (let level = plannedLevel; level <= MAX_BUCKET_LEVEL; level++) {
      const shown = readCovered(this.cache, modelId, planned, plannedLevel, level)
      if (shown) return shown
    }
    return null
  }

  /** @internal */
  pinSeries(plan: BucketReadPlan, pin: boolean): void {
    for (const experiment of plan.experiments) {
      for (const { key } of experiment.series) {
        if (pin) this.cache.pin(experiment.modelId, key, plan.level)
        else this.cache.unpin(experiment.modelId, key, plan.level)
      }
    }
  }

  /**
   * @internal Queues a chart's fetches for the current debounce window; a chart's newer job
   * replaces its older one. The window is extended by each new job, up to a bound.
   */
  schedule(subscription: StoreSubscription, job: PendingJob): void {
    if (this.disposed) return
    this.pendingJobs.delete(subscription)
    this.pendingJobs.set(subscription, job)
    const now = Date.now()
    if (this.batchTimer === null) this.batchStartedAt = now
    else clearTimeout(this.batchTimer)
    const deadline = this.batchStartedAt + MAX_WAIT_DEBOUNCES * this.debounceMs
    this.batchTimer = setTimeout(
      () => this.flush(),
      Math.max(0, Math.min(this.debounceMs, deadline - now)),
    )
  }

  /** @internal */
  unschedule(subscription: StoreSubscription): void {
    this.pendingJobs.delete(subscription)
  }

  /** Merges the window's fetches per experiment, level and bucket range, then starts them. */
  private flush(): void {
    this.batchTimer = null
    const jobs = [...this.pendingJobs.values()]
    this.pendingJobs.clear()
    const merged = new Map<string, PlannedFetch>()
    const groupOf = (level: number, { modelId, fetch }: WantedFetch) =>
      JSON.stringify([modelId, level, fetch.firstBucket, fetch.lastBucket])
    for (const job of jobs) {
      for (const wanted of job.fetches) {
        const id = groupOf(job.level, wanted)
        const group = merged.get(id)
        if (!group) merged.set(id, { ...wanted.fetch, keys: [...wanted.fetch.keys] })
        else
          for (const key of wanted.fetch.keys) if (!group.keys.includes(key)) group.keys.push(key)
      }
    }
    for (const job of jobs) {
      const joined = job.fetches.map((wanted) => {
        const fetch = merged.get(groupOf(job.level, wanted)) ?? wanted.fetch
        return this.joinFetch(wanted.modelId, job.level, fetch)
      })
      job.run(joined)
    }
  }

  /**
   * Joins a fetch in flight of the same experiment, level and bucket range that covers these
   * keys, or starts one; the answer is cached either way. It is aborted only when every
   * chart that joined it has left.
   */
  private joinFetch(modelId: string, level: number, fetch: PlannedFetch): JoinedFetch {
    for (const [id, shared] of this.inFlight) {
      if (
        shared.modelId === modelId &&
        shared.level === level &&
        shared.firstBucket === fetch.firstBucket &&
        shared.lastBucket === fetch.lastBucket &&
        fetch.keys.every((key) => shared.keys.includes(key))
      ) {
        shared.waiters++
        return { id, shared }
      }
    }
    const id = this.nextFetchId++
    const controller = new AbortController()
    const started: SharedFetch = {
      modelId,
      level,
      firstBucket: fetch.firstBucket,
      lastBucket: fetch.lastBucket,
      keys: fetch.keys,
      promise: this.fetchAndCache(modelId, level, fetch, controller.signal).finally(() => {
        if (this.inFlight.get(id) === started) this.inFlight.delete(id)
      }),
      controller,
      waiters: 1,
    }
    this.inFlight.set(id, started)
    return { id, shared: started }
  }

  /** @internal */
  leaveFetch({ id, shared }: JoinedFetch): void {
    shared.waiters--
    if (shared.waiters > 0) return
    // A fetch a refresh detached from `inFlight` can gain no waiter, so it is aborted too.
    if (this.inFlight.get(id) === shared) this.inFlight.delete(id)
    shared.controller.abort()
  }

  private async fetchAndCache(
    modelId: string,
    level: number,
    fetch: PlannedFetch,
    signal: AbortSignal,
  ): Promise<FetchOutcome> {
    const request: MetricBucketsRequest = {
      modelIds: [modelId],
      keys: fetch.keys,
      start_step: fetch.startStep,
      end_step: fetch.endStep,
      level,
    }
    const versions = new Map(fetch.keys.map((key) => [key, this.versionOf(modelId, key)]))
    let result: ExperimentResult<MetricBucketsResponse>
    try {
      // Bound by the timeout and `dispose()` only: when every chart left (`signal`), a provider
      // that ignores the abort still answers, and its answer is cached for the next request.
      const results = await this.bounded((bound) =>
        this.source.getMetricBuckets(request, AbortSignal.any([signal, bound])),
      )
      result = results.find((item) => item.modelId === modelId) ?? {
        modelId,
        ok: false,
        error: { code: READ_FAILED, message: `No answer for experiment '${modelId}'` },
      }
    } catch (error) {
      result = { modelId, ok: false, error: toExperimentReadError(error) }
    }
    const uncached = new Set<string>()
    if (result.ok && !this.disposed) {
      for (const series of result.value.series) {
        if (versions.get(series.key) !== this.versionOf(modelId, series.key)) continue
        const kept = this.cache.write(
          modelId,
          series.key,
          level,
          fetch.firstBucket,
          fetch.lastBucket,
          series.buckets,
        )
        if (!kept) uncached.add(series.key)
      }
    }
    return { result, uncached }
  }
}

/** The series from `cache` at `level` when it covers the planned range there, else null. */
function readCovered(
  cache: BucketCache,
  modelId: string,
  { key, firstBucket, lastBucket }: PlannedSeries,
  plannedLevel: number,
  level = plannedLevel,
): ChartSeries | null {
  const width = 4 ** (level - plannedLevel)
  const first = Math.floor(firstBucket / width)
  const last = Math.floor(lastBucket / width)
  if (!cache.covers(modelId, key, level, first, last)) return null
  const buckets = cache.read(modelId, key, level, first, last)
  return { modelId, key, level, final: level === plannedLevel, buckets }
}

class StoreSubscription implements ChartSubscription {
  state: ChartState
  private generation = 0
  private closed = false
  private joined: JoinedFetch[] = []
  // Fetches of a superseded request stay joined until the newer request has joined its own,
  // so a fetch both need is shared instead of aborted and started again.
  private superseded: JoinedFetch[] = []
  private pinnedPlan: BucketReadPlan | null = null
  // Answers the shared cache could not hold, with what it held of those series; kept while
  // the request stays the same, so repeating it fetches nothing.
  private overflow: BucketCache | null = null
  private overflowRequest: BucketReadRequest | null = null

  constructor(
    private readonly store: MetricBucketStore,
    private readonly listener: ChartListener,
    shown: ChartSeries[],
  ) {
    this.state = { ...IDLE_STATE, series: shown.map(provisional) }
  }

  request(request: BucketReadRequest): void {
    const modelIds = new Set(request.modelIds)
    const keys = new Set(request.keys)
    const kept = this.state.series
      .filter((series) => modelIds.has(series.modelId) && keys.has(series.key))
      .map(provisional)
    this.begin(request, kept, true)
  }

  /** @internal Re-plans when a refresh changed a metric this chart shows. */
  refreshed(changed: Map<string, Set<string>>): void {
    const { request } = this.state
    if (!request || this.closed) return
    const affected = request.modelIds.some((modelId) =>
      request.keys.some((key) => changed.get(modelId)?.has(key)),
    )
    if (!affected) return
    for (const [modelId, keys] of changed) {
      for (const key of keys) this.overflow?.dropMetric(modelId, key)
    }
    // What is shown may now be stale, so it is not final until its re-fetch lands.
    this.begin(request, this.state.series.map(provisional), false)
  }

  /** `previous`: series to keep showing until their planned level is cached again. */
  private begin(request: BucketReadRequest, previous: ChartSeries[], emitFirst: boolean): void {
    if (this.closed) return
    this.store.unschedule(this)
    this.superseded.push(...this.joined)
    this.joined = []
    const generation = ++this.generation
    if (emitFirst) this.emit({ ...IDLE_STATE, request, loading: true, series: previous })
    if (this.isStale(generation)) return
    this.store.loadCatalogs().then(
      (catalogs) => {
        if (!this.isStale(generation)) this.start(catalogs, request, generation, previous)
      },
      (error: unknown) => {
        if (this.isStale(generation)) return
        this.fail(request, error)
      },
    )
  }

  close(): void {
    this.store.unschedule(this)
    this.superseded.push(...this.joined)
    this.joined = []
    this.releaseSuperseded()
    this.pin(null)
    this.overflow = null
    this.closed = true
    this.store.unsubscribe(this)
  }

  /** A newer request or `close()`, possibly from inside the listener, replaced this one. */
  private isStale(generation: number): boolean {
    return generation !== this.generation || this.closed
  }

  private start(
    catalogs: MetricCatalogs,
    request: BucketReadRequest,
    generation: number,
    previous: ChartSeries[],
  ): void {
    let plan: BucketReadPlan | null
    let fetches: WantedFetch[]
    let state: ChartState
    try {
      const errors: ChartError[] = request.modelIds.flatMap((modelId) => {
        const error =
          catalogs.errors.get(modelId) ??
          (catalogs.catalogs.has(modelId)
            ? null
            : { code: READ_FAILED, message: `Experiment '${modelId}' is not loaded` })
        return error ? [{ modelId, error }] : []
      })
      if (!sameRequest(this.overflowRequest, request)) this.overflow = null
      this.overflowRequest = request
      const planned = this.store.plan(catalogs, request, this.overflow)
      plan = planned.plan
      errors.push(...planned.failures)
      fetches = (plan?.experiments ?? []).flatMap((experiment) =>
        experiment.fetches.map((fetch) => ({ modelId: experiment.modelId, fetch })),
      )
      state = {
        request,
        plan,
        loading: fetches.length > 0,
        series: plan ? this.store.cachedSeries(plan, previous, this.overflow) : [],
        errors,
        cacheOverflow: this.overflow !== null,
      }
    } catch (error) {
      this.fail(request, error)
      return
    }
    this.pin(plan)
    if (!fetches.length) this.releaseSuperseded()
    this.emit(state)
    if (!plan || !fetches.length || this.isStale(generation)) return
    const planned = plan
    this.store.schedule(this, {
      level: plan.level,
      fetches,
      run: (joined) => this.run(planned, fetches, joined, generation, previous),
    })
  }

  private run(
    plan: BucketReadPlan,
    fetches: WantedFetch[],
    joined: JoinedFetch[],
    generation: number,
    previous: ChartSeries[],
  ): void {
    this.joined.push(...joined)
    let pending = fetches.length
    for (const [index, { modelId, fetch }] of fetches.entries()) {
      joined[index]?.shared.promise.then(({ result, uncached }) => {
        if (this.isStale(generation)) return
        pending--
        if (result.ok) this.keepUncached(modelId, plan.level, fetch, result.value, uncached)
        const known = this.state.errors.some((item) => item.modelId === modelId)
        const errors =
          result.ok || known
            ? this.state.errors
            : [...this.state.errors, { modelId, error: result.error }]
        this.emit({
          ...this.state,
          loading: pending > 0,
          series: this.store.cachedSeries(plan, previous, this.overflow),
          errors,
          cacheOverflow: this.overflow !== null,
        })
      })
    }
    this.releaseSuperseded()
  }

  /**
   * Holds answers of this chart's keys the cache could not, together with the cache's own
   * (pinned, so stable) buckets of those series, so the chart shows them whole.
   */
  private keepUncached(
    modelId: string,
    level: number,
    fetch: PlannedFetch,
    response: MetricBucketsResponse,
    uncached: Set<string>,
  ): void {
    for (const series of response.series) {
      if (!uncached.has(series.key) || !fetch.keys.includes(series.key)) continue
      this.overflow ??= new BucketCache({ maxBuckets: Infinity })
      for (const [first, last] of this.store.cache.coverage(modelId, series.key, level)) {
        const cached = this.store.cache.read(modelId, series.key, level, first, last)
        this.overflow.write(modelId, series.key, level, first, last, cached)
      }
      this.overflow.write(
        modelId,
        series.key,
        level,
        fetch.firstBucket,
        fetch.lastBucket,
        series.buckets,
      )
    }
  }

  private fail(request: BucketReadRequest, error: unknown): void {
    this.releaseSuperseded()
    this.pin(null)
    const readError = toExperimentReadError(error)
    const errors = request.modelIds.map((modelId) => ({ modelId, error: readError }))
    this.emit({ ...IDLE_STATE, request, series: this.state.series.map(provisional), errors })
  }

  /** Pins the series of `plan` and unpins the previous plan's. */
  private pin(plan: BucketReadPlan | null): void {
    if (plan) this.store.pinSeries(plan, true)
    if (this.pinnedPlan) this.store.pinSeries(this.pinnedPlan, false)
    this.pinnedPlan = plan
  }

  private releaseSuperseded(): void {
    for (const joined of this.superseded) this.store.leaveFetch(joined)
    this.superseded = []
  }

  private emit(state: ChartState): void {
    if (this.closed) return
    this.state = state
    this.listener(state)
  }
}
