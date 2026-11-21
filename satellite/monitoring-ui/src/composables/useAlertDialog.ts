import { computed, getCurrentScope, onScopeDispose, ref, shallowRef } from 'vue'
import { useToast } from 'primevue'
import { api } from '@/api'
import { SectionState, type AlertBanner } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import { useTabsStore } from '@/store/tabs'
import { useDataQualityStore } from '@/store/data-quality'
import { TabKey } from '@/types/tabs'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { findAlert, getAlertKey, getAlertName, getAlertTargetTab } from '@/utils/alerts'
import { getErrorMessage } from '@/utils/errors'

export function useAlertDialog(
  alerts: () => AlertBanner[],
  reload: () => Promise<unknown>,
  reloadError: () => Error | null,
) {
  const toast = useToast()
  const filtersStore = useFiltersStore()
  const tabsStore = useTabsStore()
  const dataQualityStore = useDataQualityStore()

  const selection = shallowRef<{ key: string; alert: AlertBanner } | null>(null)
  const opened = ref(false)
  const acknowledgingKey = shallowRef<string | null>(null)
  const pendingTarget = shallowRef<AlertBanner | null>(null)
  let disposed = false

  if (getCurrentScope()) onScopeDispose(() => (disposed = true))

  const currentAlert = computed(() => findAlert(alerts(), selection.value?.key ?? null))

  const alert = computed(() => currentAlert.value ?? selection.value?.alert ?? null)

  const visible = computed({
    get: () => opened.value && currentAlert.value !== null,
    set: (value) => {
      if (!value) opened.value = false
    },
  })

  const acknowledging = computed(
    () => acknowledgingKey.value !== null && acknowledgingKey.value === selection.value?.key,
  )

  function open(alert: AlertBanner) {
    selection.value = { key: getAlertKey(alert), alert }
    opened.value = true
  }

  function clear() {
    opened.value = false
    selection.value = null
    const target = pendingTarget.value
    pendingTarget.value = null
    if (target) navigateTo(target)
  }

  function navigateTo(alert: AlertBanner) {
    const tab = getAlertTargetTab(alert)
    if (!tab) return
    if (tab === TabKey.FEATURE_DRIFT) filtersStore.setFeature(alert.feature ?? null)
    if (tab === TabKey.DATA_QUALITY) dataQualityStore.inspect(alert.feature ?? null)
    tabsStore.setActiveTab(tab)
  }

  async function acknowledge(alert: AlertBanner) {
    const key = getAlertKey(alert)
    acknowledgingKey.value = key
    try {
      try {
        const response = await api.monitoring.acknowledgeAlert(
          filtersStore.dimensions,
          alert.metric,
        )
        if (response.state === SectionState.UNAVAILABLE) {
          toast.add(
            simpleErrorToast(
              'The monitoring store is unavailable. Please try again.',
              'Could not acknowledge alert',
            ),
          )
          return
        }
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e))
        toast.add(simpleErrorToast(getErrorMessage(err), 'Could not acknowledge alert'))
        return
      }
      if (disposed) {
        filtersStore.refresh()
        toast.add(simpleSuccessToast(getAlertName(alert), 'Alert acknowledged'))
        return
      }
      await reload()
      const err = reloadError()
      if (err) {
        toast.add(simpleErrorToast(getErrorMessage(err), 'Alert acknowledged, but refresh failed'))
      } else {
        toast.add(simpleSuccessToast(getAlertName(alert), 'Alert acknowledged'))
      }
    } finally {
      if (acknowledgingKey.value === key) acknowledgingKey.value = null
    }
  }

  function showInTab(alert: AlertBanner) {
    if (!getAlertTargetTab(alert)) return
    pendingTarget.value = alert
    opened.value = false
  }

  return { alert, visible, acknowledging, open, clear, acknowledge, showInTab }
}
