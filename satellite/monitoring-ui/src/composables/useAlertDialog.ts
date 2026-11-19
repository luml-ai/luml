import { computed, ref, shallowRef } from 'vue'
import { useToast } from 'primevue'
import { api } from '@/api'
import type { AlertBanner } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import { useTabsStore } from '@/store/tabs'
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

  const selection = shallowRef<{ key: string; alert: AlertBanner } | null>(null)
  const opened = ref(false)
  const acknowledgingKey = shallowRef<string | null>(null)
  const pendingTarget = shallowRef<AlertBanner | null>(null)

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
    tabsStore.setActiveTab(tab)
  }

  async function acknowledge(alert: AlertBanner) {
    const key = getAlertKey(alert)
    acknowledgingKey.value = key
    try {
      try {
        await api.monitoring.acknowledgeAlert(filtersStore.dimensions, alert.metric)
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e))
        toast.add(simpleErrorToast(getErrorMessage(err), 'Could not acknowledge alert'))
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
