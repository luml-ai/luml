<template>
  <div>
    <AlertsLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <template v-else-if="data">
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <AlertsTable v-else :groups="data.groups" @select="openAlert" />
    </template>
    <AlertDialog
      v-model:visible="dialogVisible"
      :alert="dialogAlert"
      :acknowledging="acknowledgingKey !== null && acknowledgingKey === selection?.key"
      @acknowledge="acknowledge"
      @show="showInTab"
      @hidden="clearSelection"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { useToast } from 'primevue'
import { api } from '@/api'
import type { AlertBanner } from '@/api/monitoring/interfaces'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useFiltersStore } from '@/store/filters'
import { useTabsStore } from '@/store/tabs'
import { TabKey } from '@/types/tabs'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import {
  findAlert,
  getAlertKey,
  getAlertName,
  getAlertTargetTab,
  getAlertsEmptyState,
} from '@/utils/alerts'
import { getErrorMessage } from '@/utils/errors'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import AlertsLoader from '@/components/alerts/AlertsLoader.vue'
import AlertsTable from '@/components/alerts/AlertsTable.vue'
import AlertDialog from '@/components/alerts/AlertDialog.vue'

const toast = useToast()

const filtersStore = useFiltersStore()

const tabsStore = useTabsStore()

const { data, loading, error, reload } = useMonitoringData((dims) => api.monitoring.getAlerts(dims))

const selection = shallowRef<{ key: string; alert: AlertBanner } | null>(null)

const opened = ref(false)

const acknowledgingKey = shallowRef<string | null>(null)

const emptyState = computed(() => (data.value ? getAlertsEmptyState(data.value) : null))

const currentAlert = computed(() =>
  findAlert(data.value?.groups ?? [], selection.value?.key ?? null),
)

const dialogAlert = computed(() => currentAlert.value ?? selection.value?.alert ?? null)

const dialogVisible = computed({
  get: () => opened.value && currentAlert.value !== null,
  set: (value) => {
    if (!value) opened.value = false
  },
})

function openAlert(alert: AlertBanner) {
  selection.value = { key: getAlertKey(alert), alert }
  opened.value = true
}

function clearSelection() {
  opened.value = false
  selection.value = null
}

async function acknowledge(alert: AlertBanner) {
  const key = getAlertKey(alert)
  acknowledgingKey.value = key
  try {
    await api.monitoring.acknowledgeAlert(filtersStore.dimensions, alert.metric)
    toast.add(simpleSuccessToast(getAlertName(alert), 'Alert acknowledged'))
    await reload()
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e))
    toast.add(simpleErrorToast(getErrorMessage(err), 'Could not acknowledge alert'))
  } finally {
    if (acknowledgingKey.value === key) acknowledgingKey.value = null
  }
}

function showInTab(alert: AlertBanner) {
  const tab = getAlertTargetTab(alert)
  if (!tab) return
  if (tab === TabKey.FEATURE_DRIFT) filtersStore.setFeature(alert.feature ?? null)
  clearSelection()
  tabsStore.setActiveTab(tab)
}
</script>
