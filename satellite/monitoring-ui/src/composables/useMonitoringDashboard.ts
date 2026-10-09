import { computed, getCurrentScope, onScopeDispose, reactive, ref, watch } from 'vue'
import * as monitoringApi from '@/api/monitoring'
import { SessionExpiredError } from '@/api/client'
import {
  Compare,
  Granularity,
  ProfileStatus,
  SeverityFilter,
  Window,
  type DataQualityResponse,
  type Dimensions,
  type FeatureDriftResponse,
  type HeaderResponse,
  type OutputDriftResponse,
  type OverviewResponse,
  type AlertsResponse,
  type RuntimeResponse,
  type WorkerHealthResponse,
  type ReferenceProfileResponse,
  type Series,
  type SortOrder,
  type TraceSortKey,
  type TraceDetail,
  type TracesResponse,
} from '@/api/types'

/** Posted to the Platform parent frame on a 401 so it can offer a re-launch. */
export const MONITORING_SESSION_EXPIRED_MESSAGE = 'monitoring:session-expired'

/** Page size for the local Traces panel (bounded by the Query API's max limit). */
export const TRACES_PAGE_SIZE = 20

/** Auto-refresh cadences offered by the controls, in seconds; 0 is off. */
export const AUTO_REFRESH_OPTIONS = [0, 30, 60, 300] as const
export type AutoRefreshSeconds = (typeof AUTO_REFRESH_OPTIONS)[number]

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export const DASHBOARD_TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'runtime', label: 'Runtime' },
  { key: 'traces', label: 'Traces' },
  { key: 'data-quality', label: 'Data quality' },
  { key: 'feature-drift', label: 'Feature drift' },
  { key: 'output-drift', label: 'Output drift' },
  { key: 'reference-profile', label: 'Reference profile' },
  { key: 'alerts', label: 'Alerts' },
] as const

export type TabKey = (typeof DASHBOARD_TABS)[number]['key']

export const UNIVERSAL_TAB_KEYS: readonly TabKey[] = ['overview', 'runtime', 'traces', 'alerts']

export function useMonitoringDashboard() {
  const dimensions = reactive<Dimensions>({
    window: Window.H24,
    compare: Compare.OFF,
    severity: SeverityFilter.ALL,
    granularity: Granularity.AUTO,
    feature: null,
    start: null,
    end: null,
    compareStart: null,
    compareEnd: null,
  })

  const activeTab = ref<TabKey>('overview')
  const sessionExpired = ref(false)

  const header = ref<HeaderResponse | null>(null)
  const headerStatus = ref<LoadStatus>('idle')

  const overview = ref<OverviewResponse | null>(null)
  const overviewStatus = ref<LoadStatus>('idle')

  const runtime = ref<RuntimeResponse | null>(null)
  const runtimeStatus = ref<LoadStatus>('idle')

  const dataQuality = ref<DataQualityResponse | null>(null)
  const dataQualityStatus = ref<LoadStatus>('idle')
  // One feature's history is a second, narrower request made when its panel opens.
  const qualityTrends = ref<Series[]>([])
  const qualityTrendsStatus = ref<LoadStatus>('idle')
  const profileDocument = ref<ReferenceProfileResponse | null>(null)
  const profileDocumentStatus = ref<LoadStatus>('idle')
  const alerts = ref<AlertsResponse | null>(null)
  const alertsStatus = ref<LoadStatus>('idle')
  const workerHealth = ref<WorkerHealthResponse | null>(null)

  const traces = ref<TracesResponse | null>(null)
  const tracesStatus = ref<LoadStatus>('idle')
  const tracesOffset = ref(0)

  // Non-null while a trace is open: drives the detail dialog over the traces table.
  const openTraceId = ref<string | null>(null)
  const traceDetail = ref<TraceDetail | null>(null)
  const traceDetailStatus = ref<LoadStatus>('idle')

  const featureDrift = ref<FeatureDriftResponse | null>(null)
  const featureDriftStatus = ref<LoadStatus>('idle')

  const outputDrift = ref<OutputDriftResponse | null>(null)
  const outputDriftStatus = ref<LoadStatus>('idle')

  const referenceProfile = ref<ReferenceProfileResponse | null>(null)
  const referenceProfileStatus = ref<LoadStatus>('idle')

  const isPlaceholderProfile = computed(() =>
    [
      header.value?.profile_status,
      overview.value?.profile_status,
      dataQuality.value?.profile_status,
      featureDrift.value?.profile_status,
      referenceProfile.value?.profile_status,
    ].includes(ProfileStatus.PLACEHOLDER),
  )

  function reportSessionExpired(): void {
    if (sessionExpired.value) return
    sessionExpired.value = true
    // targetOrigin '*' is safe: the payload is a flag and the Platform checks the origin.
    window.parent?.postMessage({ type: MONITORING_SESSION_EXPIRED_MESSAGE }, '*')
  }

  async function run<T>(
    status: { value: LoadStatus },
    load: () => Promise<T>,
    assign: (value: T) => void,
  ): Promise<void> {
    status.value = 'loading'
    try {
      assign(await load())
      status.value = 'ready'
    } catch (error) {
      if (error instanceof SessionExpiredError) {
        reportSessionExpired()
        return
      }
      status.value = 'error'
    }
  }

  function loadHeader(): Promise<void> {
    // Worker health must never keep the metrics from rendering.
    void monitoringApi
      .getWorkerHealth()
      .then((value) => (workerHealth.value = value))
      .catch(() => (workerHealth.value = null))
    return run(headerStatus, monitoringApi.getHeader, (value) => (header.value = value))
  }

  function loadOverview(): Promise<void> {
    return run(
      overviewStatus,
      () => monitoringApi.getOverview({ ...dimensions }),
      (value) => (overview.value = value),
    )
  }

  function loadRuntime(): Promise<void> {
    return run(
      runtimeStatus,
      () => monitoringApi.getRuntime({ ...dimensions }),
      (value) => (runtime.value = value),
    )
  }

  function loadDataQuality(): Promise<void> {
    // The table shows every feature; the selected feature only scopes Feature drift.
    return run(
      dataQualityStatus,
      () => monitoringApi.getDataQuality({ ...dimensions, feature: null }),
      (value) => (dataQuality.value = value),
    )
  }

  function loadQualityTrends(feature: string | null): Promise<void> {
    if (feature === null) {
      qualityTrends.value = []
      qualityTrendsStatus.value = 'idle'
      return Promise.resolve()
    }
    return run(
      qualityTrendsStatus,
      () => monitoringApi.getDataQuality({ ...dimensions, feature }),
      (value) => (qualityTrends.value = value.trends ?? []),
    )
  }

  /** The dashboard's only write: mark an alert as seen and take the refreshed list back. */
  async function acknowledgeAlert(metric: string): Promise<void> {
    await run(
      alertsStatus,
      () => monitoringApi.acknowledgeAlert({ ...dimensions }, metric),
      // Not an anchor: acknowledging one alert is not "I saw the new ones too".
      applyAlerts,
    )
    // Each section carries its own banner copy and hides acknowledged ones —
    // refetch the visible tab now.
    if (activeTab.value === 'overview') await loadOverview()
    else if (activeTab.value === 'runtime') await loadRuntime()
    else if (activeTab.value === 'data-quality') await loadDataQuality()
    else if (activeTab.value === 'feature-drift') await loadFeatureDrift()
    else if (activeTab.value === 'output-drift') await loadOutputDrift()
  }

  /**
   * Alerts that fired while the tab sat on an auto-refresh cadence.
   *
   * A deliberate load anchors "seen" to whatever it shows — the reader is looking at
   * it. Ticks then compare against that anchor: newly firing alerts are counted and
   * highlighted until the reader dismisses the notice, surviving intermediate ticks
   * (and acknowledges) so a glance away doesn't swallow the news.
   */
  const alertsNewCount = ref(0)
  const alertsFreshKeys = ref<Set<string>>(new Set())
  let alertsSeenKeys: Set<string> | null = null

  function alertKeys(response: AlertsResponse): string[] {
    return (response.groups ?? []).flatMap((group) => group.alerts.map((alert) => alert.metric))
  }

  function anchorAlerts(response: AlertsResponse): void {
    alertsSeenKeys = new Set(alertKeys(response))
    alertsNewCount.value = 0
    alertsFreshKeys.value = new Set()
  }

  function applyAlerts(response: AlertsResponse): void {
    alerts.value = response
    if (alertsSeenKeys === null) {
      anchorAlerts(response)
      return
    }
    const fresh = alertKeys(response).filter((key) => !alertsSeenKeys!.has(key))
    alertsFreshKeys.value = new Set(fresh)
    alertsNewCount.value = fresh.length
  }

  function markAlertsSeen(): void {
    if (alerts.value) anchorAlerts(alerts.value)
  }

  function loadAlerts(): Promise<void> {
    return run(
      alertsStatus,
      () => monitoringApi.getAlerts({ ...dimensions }),
      (value) => {
        alerts.value = value
        anchorAlerts(value)
      },
    )
  }

  function autoReloadAlerts(): Promise<void> {
    return run(alertsStatus, () => monitoringApi.getAlerts({ ...dimensions }), applyAlerts)
  }

  /** How the traces table is ordered; a header click flows through here. */
  const tracesSort = ref<{ key: TraceSortKey; order: SortOrder }>({ key: 'ts', order: 'desc' })

  function setTracesSort(key: TraceSortKey): Promise<void> {
    const current = tracesSort.value
    // Clicking the active column flips it; a new column starts descending.
    tracesSort.value =
      current.key === key
        ? { key, order: current.order === 'desc' ? 'asc' : 'desc' }
        : { key, order: 'desc' }
    return loadTraces(0)
  }

  function loadTraces(offset = 0): Promise<void> {
    tracesOffset.value = offset
    return run(
      tracesStatus,
      () =>
        monitoringApi.getTraces(
          { ...dimensions },
          {
            limit: TRACES_PAGE_SIZE,
            offset,
            sort: tracesSort.value.key,
            order: tracesSort.value.order,
          },
        ),
      (value) => {
        traces.value = value
        // Any deliberate load re-anchors "new since": what's on screen is now seen.
        // The anchor only means "newest" under time ordering, so only then is it set.
        if (offset === 0 && tracesSort.value.key === 'ts' && tracesSort.value.order === 'desc') {
          tracesTopEventId = value.rows[0]?.event_id ?? null
        }
        tracesNewCount.value = 0
      },
    )
  }

  /**
   * Traces arriving while the reader is away from the newest page.
   *
   * The newest page live-tails on the auto-refresh tick. A deeper page must hold
   * still — offset pagination over a growing list would slide rows under the
   * reader — so the tick peeks at the newest page instead and counts what arrived
   * since the reader last saw it; the panel offers a jump. Page-capped: past a
   * full page of arrivals the count reads "20+", which is all a human needs.
   */
  const tracesNewCount = ref(0)
  let tracesTopEventId: string | null = null

  async function peekNewTraces(): Promise<void> {
    let page: TracesResponse
    try {
      page = await monitoringApi.getTraces(
        { ...dimensions },
        { limit: TRACES_PAGE_SIZE, offset: 0, sort: 'ts', order: 'desc' },
      )
    } catch (error) {
      if (error instanceof SessionExpiredError) reportSessionExpired()
      return
    }
    const index = page.rows.findIndex((row) => row.event_id === tracesTopEventId)
    tracesNewCount.value = index === -1 ? page.rows.length : index
  }

  function showLatestTraces(): Promise<void> {
    return loadTraces(0)
  }

  function loadFeatureDrift(): Promise<void> {
    return run(
      featureDriftStatus,
      () => monitoringApi.getFeatureDrift({ ...dimensions }),
      (value) => (featureDrift.value = value),
    )
  }

  function loadOutputDrift(): Promise<void> {
    return run(
      outputDriftStatus,
      () => monitoringApi.getOutputDrift({ ...dimensions }),
      (value) => (outputDrift.value = value),
    )
  }

  function loadReferenceProfile(): Promise<void> {
    return run(
      referenceProfileStatus,
      () => monitoringApi.getReferenceProfile({ ...dimensions }),
      (value) => (referenceProfile.value = value),
    )
  }

  /** The profile document itself, unscoped — what the Reference profile tab shows. */
  function loadProfileDocument(): Promise<void> {
    return run(
      profileDocumentStatus,
      () => monitoringApi.getReferenceProfile({ ...dimensions, feature: null }),
      (value) => (profileDocument.value = value),
    )
  }

  /** Reload the window-scoped data for whichever tab is active (header is window-independent). */
  function reloadActiveTab(): Promise<void> {
    // An open trace belongs to the window it was opened from; the reload invalidates it.
    closeTrace()
    if (activeTab.value === 'overview') return loadOverview()
    if (activeTab.value === 'runtime') return loadRuntime()
    if (activeTab.value === 'traces') return loadTraces(0)
    if (activeTab.value === 'alerts') return loadAlerts()
    if (activeTab.value === 'output-drift') return loadOutputDrift()
    if (activeTab.value === 'reference-profile') return loadProfileDocument()
    if (activeTab.value === 'data-quality') {
      // the open panel described the previous window
      qualityTrends.value = []
      return loadDataQuality()
    }
    return Promise.all([loadFeatureDrift(), loadReferenceProfile()])
      .then(() => selectTopFeature())
      .then(() => undefined)
  }

  /**
   * Open the Feature drift tab on its most drifted feature.
   *
   * The detail panel and the reference profile are scoped to a feature, so with none
   * chosen the right-hand side of the tab is an empty prompt even when the ranking is
   * full. The list is sorted by PSI, so the first row is the one worth looking at.
   */
  function selectTopFeature(): Promise<void> {
    if (dimensions.feature !== null) return Promise.resolve()
    const top = featureDrift.value?.features?.[0]?.feature
    return top ? setFeature(top) : Promise.resolve()
  }

  /**
   * Settings survive a reload.
   *
   * Everything a reader dials in — window (custom range included), compare mode and
   * its periods, severity, series step, auto-refresh cadence, active tab, traces
   * sort — is written to localStorage keyed by deployment id (the storage is
   * per-Satellite-origin, and one Satellite hosts many deployments), restored before
   * the first fetch so the page comes back exactly as it was left. Anything that
   * fails validation on the way back is dropped field by field, so a stale or
   * hand-edited blob degrades to defaults instead of breaking the boot.
   */
  const SETTINGS_VERSION = 1

  function settingsKey(deploymentId: string): string {
    return `monitoring-settings:${deploymentId}`
  }

  function persistSettings(): void {
    if (persistKey === null) return
    const blob = {
      v: SETTINGS_VERSION,
      window: dimensions.window,
      start: dimensions.start,
      end: dimensions.end,
      compare: dimensions.compare,
      compareStart: dimensions.compareStart,
      compareEnd: dimensions.compareEnd,
      severity: dimensions.severity,
      granularity: dimensions.granularity,
      tab: activeTab.value,
      autoRefreshSeconds: autoRefreshSeconds.value,
      tracesSort: tracesSort.value,
    }
    try {
      localStorage.setItem(persistKey, JSON.stringify(blob))
    } catch {
      // storage can be unavailable in strict embeds; the dashboard still works
    }
  }

  let persistKey: string | null = null

  function restoreSettings(deploymentId: string): void {
    persistKey = settingsKey(deploymentId)
    let raw: string | null = null
    try {
      raw = localStorage.getItem(persistKey)
    } catch {
      return
    }
    if (!raw) return
    let blob: Record<string, unknown>
    try {
      blob = JSON.parse(raw) as Record<string, unknown>
    } catch {
      return
    }
    if (blob.v !== SETTINGS_VERSION) return
    const oneOf = <T,>(value: unknown, allowed: readonly T[]): T | null =>
      allowed.includes(value as T) ? (value as T) : null
    const iso = (value: unknown): string | null =>
      typeof value === 'string' && !Number.isNaN(Date.parse(value)) ? value : null

    dimensions.window = oneOf(blob.window, Object.values(Window)) ?? dimensions.window
    dimensions.severity = oneOf(blob.severity, Object.values(SeverityFilter)) ?? dimensions.severity
    dimensions.granularity =
      oneOf(blob.granularity, Object.values(Granularity)) ?? dimensions.granularity
    const start = iso(blob.start)
    const end = iso(blob.end)
    if (start && end) {
      dimensions.start = start
      dimensions.end = end
    }
    const compare = oneOf(blob.compare, Object.values(Compare))
    const compareStart = iso(blob.compareStart)
    const compareEnd = iso(blob.compareEnd)
    if (compare === Compare.CUSTOM) {
      if (compareStart && compareEnd) {
        dimensions.compare = compare
        dimensions.compareStart = compareStart
        dimensions.compareEnd = compareEnd
      }
    } else if (compare !== null) {
      dimensions.compare = compare
    }
    const tab = oneOf(blob.tab, DASHBOARD_TABS.map((one) => one.key))
    if (tab !== null) activeTab.value = tab
    const auto = oneOf(blob.autoRefreshSeconds, AUTO_REFRESH_OPTIONS)
    if (auto !== null && auto !== 0) setAutoRefresh(auto)
    const sortRaw = blob.tracesSort as { key?: unknown; order?: unknown } | undefined
    const sortKey = oneOf(sortRaw?.key, ['ts', 'latency', 'status'] as const)
    const sortOrder = oneOf(sortRaw?.order, ['asc', 'desc'] as const)
    if (sortKey !== null && sortOrder !== null) {
      tracesSort.value = { key: sortKey, order: sortOrder }
    }
  }

  async function load(): Promise<void> {
    // Settings restore before the first fetch, so the first load already uses them.
    try {
      const info = await monitoringApi.getSessionInfo()
      restoreSettings(info.deployment_id)
    } catch {
      // no session info, no restore — the defaults still stand
    }
    await Promise.all([loadHeader(), reloadActiveTab()])
  }

  function refresh(): Promise<void> {
    return load()
  }

  const autoRefreshSeconds = ref<AutoRefreshSeconds>(0)
  let autoRefreshTimer: number | null = null
  let autoRefreshInFlight = false

  function setAutoRefresh(seconds: AutoRefreshSeconds): void {
    autoRefreshSeconds.value = seconds
    if (autoRefreshTimer !== null) {
      window.clearInterval(autoRefreshTimer)
      autoRefreshTimer = null
    }
    if (seconds > 0) {
      autoRefreshTimer = window.setInterval(() => void autoRefreshTick(), seconds * 1000)
    }
  }

  /**
   * A timer tick reloads the header and the active section's data — and nothing else.
   *
   * A manual refresh may reset what the user is doing; a background one must not: the
   * Traces page stays where it is and an open trace stays open, the Data quality tab
   * keeps its trends panel, the reference profile is a static document and is skipped.
   * A hidden dashboard skips the network entirely, and an expired session stops the
   * timer for good — polling a dead session would just spam 401s.
   */
  async function autoRefreshTick(): Promise<void> {
    if (document.hidden || autoRefreshInFlight) return
    if (sessionExpired.value) {
      setAutoRefresh(0)
      return
    }
    autoRefreshInFlight = true
    try {
      await Promise.all([loadHeader(), autoReloadActiveSection()])
    } finally {
      autoRefreshInFlight = false
    }
  }

  function autoReloadActiveSection(): Promise<void> {
    switch (activeTab.value) {
      case 'overview':
        return loadOverview()
      case 'runtime':
        return loadRuntime()
      case 'traces':
        // The newest page tails live; a deeper page holds still and counts arrivals.
        return tracesOffset.value === 0 ? loadTraces(0) : peekNewTraces()
      case 'alerts':
        return autoReloadAlerts()
      case 'output-drift':
        return loadOutputDrift()
      case 'data-quality':
        return loadDataQuality()
      case 'reference-profile':
        return Promise.resolve()
      default:
        return loadFeatureDrift()
    }
  }

  // App.vue owns the only instance; the guard keeps out-of-component test calls warning-free.
  if (getCurrentScope()) onScopeDispose(() => setAutoRefresh(0))

  async function setWindow(next: Window): Promise<void> {
    if (dimensions.window === next && dimensions.start === null) return
    dimensions.window = next
    // a preset click leaves custom-range mode
    dimensions.start = null
    dimensions.end = null
    await reloadActiveTab()
  }

  /**
   * Custom comparison of two hand-picked periods: the first becomes the page's
   * window, the second the baseline — set together so the tab reloads once.
   */
  async function setComparePeriods(
    start: string,
    end: string,
    compareStart: string,
    compareEnd: string,
  ): Promise<void> {
    dimensions.start = start
    dimensions.end = end
    dimensions.compare = Compare.CUSTOM
    dimensions.compareStart = compareStart
    dimensions.compareEnd = compareEnd
    await reloadActiveTab()
  }

  /** Absolute range from the calendar; both ISO timestamps, or both null to leave. */
  async function setCustomRange(start: string | null, end: string | null): Promise<void> {
    if (dimensions.start === start && dimensions.end === end) return
    dimensions.start = start
    dimensions.end = end
    await reloadActiveTab()
  }

  async function setGranularity(next: Granularity): Promise<void> {
    if (dimensions.granularity === next) return
    dimensions.granularity = next
    await reloadActiveTab()
  }

  /**
   * Enter, change or leave compare mode.
   *
   * PREVIOUS derives its period from the current window; CUSTOM carries the chosen
   * one; OFF drops the baseline everywhere.
   */
  async function setCompare(
    next: Compare,
    compareStart: string | null = null,
    compareEnd: string | null = null,
  ): Promise<void> {
    if (
      dimensions.compare === next &&
      dimensions.compareStart === compareStart &&
      dimensions.compareEnd === compareEnd
    )
      return
    dimensions.compare = next
    dimensions.compareStart = next === Compare.CUSTOM ? compareStart : null
    dimensions.compareEnd = next === Compare.CUSTOM ? compareEnd : null
    await reloadActiveTab()
  }

  async function setSeverity(next: SeverityFilter): Promise<void> {
    if (dimensions.severity === next) return
    dimensions.severity = next
    await reloadActiveTab()
  }

  /** Select (or clear) the feature that scopes the Feature drift detail and reference profile. */
  async function setFeature(next: string | null): Promise<void> {
    if (dimensions.feature === next) return
    dimensions.feature = next
    await Promise.all([loadFeatureDrift(), loadReferenceProfile()])
  }

  function setTracesPage(offset: number): Promise<void> {
    closeTrace()
    return loadTraces(Math.max(0, offset))
  }

  /** Open one call from the traces table and fetch its full payloads. */
  function openTrace(eventId: string): Promise<void> {
    openTraceId.value = eventId
    traceDetail.value = null
    return run(
      traceDetailStatus,
      () => monitoringApi.getTraceDetail({ ...dimensions }, eventId),
      (value) => (traceDetail.value = value.trace),
    )
  }

  function closeTrace(): void {
    openTraceId.value = null
    traceDetail.value = null
    traceDetailStatus.value = 'idle'
  }

  /**
   * Follow an alert to the tab that explains it, with its feature already selected.
   *
   * Data-quality alerts are about one feature's checks, drift alerts about its
   * distribution — both tabs can open on a named feature, so the jump lands on the row
   * the alert is complaining about instead of the top of a list.
   */
  async function focusAlert(alert: { group: string; feature?: string | null }): Promise<void> {
    const tab: TabKey = alert.group === 'data_quality' ? 'data-quality' : 'feature-drift'
    if (alert.feature) dimensions.feature = alert.feature
    focusedFeature.value = alert.feature ?? null
    await setActiveTab(tab)
  }

  /** The feature a jump asked to open, consumed by the tab that lands on it. */
  const focusedFeature = ref<string | null>(null)

  async function setActiveTab(next: TabKey): Promise<void> {
    if (activeTab.value === next) return
    activeTab.value = next
    await reloadActiveTab()
  }

  /** The tabs this deployment gets, decided by what kind of model it serves. */
  const visibleTabs = computed(() =>
    header.value?.model_kind === 'tabular'
      ? DASHBOARD_TABS
      : DASHBOARD_TABS.filter((tab) => UNIVERSAL_TAB_KEYS.includes(tab.key)),
  )

  // A restored tab may not exist for this model kind (known once the header arrives) —
  // land on Overview.
  watch(visibleTabs, (tabs) => {
    if (!tabs.some((tab) => tab.key === activeTab.value)) {
      void setActiveTab('overview')
    }
  })

  // Registered last, after every piece of state it watches exists.
  watch([dimensions, activeTab, autoRefreshSeconds, tracesSort], persistSettings, { deep: true })

  return {
    dimensions,
    activeTab,
    visibleTabs,
    sessionExpired,
    header,
    headerStatus,
    overview,
    overviewStatus,
    runtime,
    runtimeStatus,
    dataQuality,
    dataQualityStatus,
    qualityTrends,
    qualityTrendsStatus,
    loadQualityTrends,
    profileDocument,
    profileDocumentStatus,
    alerts,
    alertsStatus,
    alertsNewCount,
    alertsFreshKeys,
    markAlertsSeen,
    acknowledgeAlert,
    workerHealth,
    focusAlert,
    focusedFeature,
    traces,
    tracesStatus,
    tracesOffset,
    tracesNewCount,
    showLatestTraces,
    tracesSort,
    setTracesSort,
    openTraceId,
    traceDetail,
    traceDetailStatus,
    openTrace,
    closeTrace,
    featureDrift,
    featureDriftStatus,
    outputDrift,
    outputDriftStatus,
    referenceProfile,
    referenceProfileStatus,
    isPlaceholderProfile,
    autoRefreshSeconds,
    setAutoRefresh,
    load,
    refresh,
    setWindow,
    setCustomRange,
    setComparePeriods,
    setGranularity,
    setCompare,
    setSeverity,
    setFeature,
    setTracesPage,
    setActiveTab,
  }
}
