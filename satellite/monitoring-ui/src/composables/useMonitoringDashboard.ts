import { computed, reactive, ref } from 'vue'
import * as monitoringApi from '@/api/monitoring'
import { SessionExpiredError } from '@/api/client'
import {
  Compare,
  ProfileStatus,
  SeverityFilter,
  Window,
  type DataQualityResponse,
  type Dimensions,
  type FeatureDriftResponse,
  type HeaderResponse,
  type OverviewResponse,
  type AlertsResponse,
  type WorkerHealthResponse,
  type ReferenceProfileResponse,
  type Series,
  type TraceDetail,
  type TracesResponse,
} from '@/api/types'

/** Posted to the Platform parent frame on a 401 so it can offer a re-launch. */
export const MONITORING_SESSION_EXPIRED_MESSAGE = 'monitoring:session-expired'

/** Page size for the local Traces panel (bounded by the Query API's max limit). */
export const TRACES_PAGE_SIZE = 20

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export const DASHBOARD_TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'traces', label: 'Traces' },
  { key: 'data-quality', label: 'Data quality' },
  { key: 'feature-drift', label: 'Feature drift' },
  { key: 'reference-profile', label: 'Reference profile' },
  { key: 'alerts', label: 'Alerts' },
] as const

export type TabKey = (typeof DASHBOARD_TABS)[number]['key']

export function useMonitoringDashboard() {
  const dimensions = reactive<Dimensions>({
    window: Window.H24,
    compare: Compare.REFERENCE,
    severity: SeverityFilter.ALL,
    feature: null,
  })

  const activeTab = ref<TabKey>('overview')
  const sessionExpired = ref(false)

  const header = ref<HeaderResponse | null>(null)
  const headerStatus = ref<LoadStatus>('idle')

  const overview = ref<OverviewResponse | null>(null)
  const overviewStatus = ref<LoadStatus>('idle')

  const dataQuality = ref<DataQualityResponse | null>(null)
  const dataQualityStatus = ref<LoadStatus>('idle')
  // The table request covers every feature; the history behind one feature's rates is a
  // second, narrower request made when its detail panel opens.
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
    // targetOrigin '*' is safe: the payload is a flag, and the Platform verifies the
    // message origin equals the Satellite origin on its side.
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
    return run(headerStatus, monitoringApi.getHeader, (value) => (header.value = value))
  }

  function loadOverview(): Promise<void> {
    // Whether monitoring itself is keeping up rides along with the tab that shows it;
    // a failure here must never keep the metrics from rendering.
    void monitoringApi
      .getWorkerHealth()
      .then((value) => (workerHealth.value = value))
      .catch(() => (workerHealth.value = null))
    return run(
      overviewStatus,
      () => monitoringApi.getOverview({ ...dimensions }),
      (value) => (overview.value = value),
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
  function acknowledgeAlert(metric: string): Promise<void> {
    return run(
      alertsStatus,
      () => monitoringApi.acknowledgeAlert({ ...dimensions }, metric),
      (value) => (alerts.value = value),
    )
  }

  function loadAlerts(): Promise<void> {
    return run(
      alertsStatus,
      () => monitoringApi.getAlerts({ ...dimensions }),
      (value) => (alerts.value = value),
    )
  }

  function loadTraces(offset = 0): Promise<void> {
    tracesOffset.value = offset
    return run(
      tracesStatus,
      () => monitoringApi.getTraces({ ...dimensions }, { limit: TRACES_PAGE_SIZE, offset }),
      (value) => (traces.value = value),
    )
  }

  function loadFeatureDrift(): Promise<void> {
    return run(
      featureDriftStatus,
      () => monitoringApi.getFeatureDrift({ ...dimensions }),
      (value) => (featureDrift.value = value),
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
    if (activeTab.value === 'traces') return loadTraces(0)
    if (activeTab.value === 'alerts') return loadAlerts()
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

  async function load(): Promise<void> {
    await Promise.all([loadHeader(), reloadActiveTab()])
  }

  function refresh(): Promise<void> {
    return load()
  }

  async function setWindow(next: Window): Promise<void> {
    if (dimensions.window === next) return
    dimensions.window = next
    await reloadActiveTab()
  }

  async function setCompare(next: Compare): Promise<void> {
    if (dimensions.compare === next) return
    dimensions.compare = next
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

  return {
    dimensions,
    activeTab,
    sessionExpired,
    header,
    headerStatus,
    overview,
    overviewStatus,
    dataQuality,
    dataQualityStatus,
    qualityTrends,
    qualityTrendsStatus,
    loadQualityTrends,
    profileDocument,
    profileDocumentStatus,
    alerts,
    alertsStatus,
    acknowledgeAlert,
    workerHealth,
    focusAlert,
    focusedFeature,
    traces,
    tracesStatus,
    tracesOffset,
    openTraceId,
    traceDetail,
    traceDetailStatus,
    openTrace,
    closeTrace,
    featureDrift,
    featureDriftStatus,
    referenceProfile,
    referenceProfileStatus,
    isPlaceholderProfile,
    load,
    refresh,
    setWindow,
    setCompare,
    setSeverity,
    setFeature,
    setTracesPage,
    setActiveTab,
  }
}
