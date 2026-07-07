import { computed, reactive, ref } from 'vue'
import * as monitoringApi from '@/api/monitoring'
import { SessionExpiredError } from '@/api/client'
import {
  Compare,
  ProfileStatus,
  SeverityFilter,
  Window,
  type Dimensions,
  type HeaderResponse,
  type OverviewResponse,
} from '@/api/types'

/** Posted to the Platform parent frame on a 401 so it can offer a re-launch. */
export const MONITORING_SESSION_EXPIRED_MESSAGE = 'monitoring:session-expired'

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

  const isPlaceholderProfile = computed(
    () =>
      header.value?.profile_status === ProfileStatus.PLACEHOLDER ||
      overview.value?.profile_status === ProfileStatus.PLACEHOLDER,
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

  /** Reload the window-scoped data for whichever tab is active (header is window-independent). */
  function reloadActiveTab(): Promise<void> {
    if (activeTab.value === 'overview') return loadOverview()
    return Promise.resolve()
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
    isPlaceholderProfile,
    load,
    refresh,
    setWindow,
    setCompare,
    setSeverity,
    setActiveTab,
  }
}
