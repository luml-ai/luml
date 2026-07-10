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
  type ReferenceProfileResponse,
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
  { key: 'data-quality', label: 'Data quality' },
  { key: 'feature-drift', label: 'Feature drift' },
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

  /** Reload the window-scoped data for whichever tab is active (header is window-independent). */
  function reloadActiveTab(): Promise<void> {
    // An open trace belongs to the window it was opened from; the reload invalidates it.
    closeTrace()
    if (activeTab.value === 'overview') return loadOverview()
    if (activeTab.value === 'data-quality') {
      return Promise.all([loadDataQuality(), loadTraces(0)]).then(() => undefined)
    }
    return Promise.all([loadFeatureDrift(), loadReferenceProfile()]).then(() => undefined)
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
