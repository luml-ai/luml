<template>
  <div>
    <AlertsLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <template v-else-if="data">
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <AlertsTable
        v-else
        :groups="data.groups"
        :fresh-keys="freshKeys"
        @select="alertDialog?.open($event)"
        @seen="markSeen"
      />
    </template>
    <AlertDialogHost ref="alertDialog" :alerts="alerts" :reload="reload" :error="error" />
  </div>
</template>

<script setup lang="ts">
import { computed, shallowRef, useTemplateRef, watch } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useFiltersStore } from '@/store/filters'
import {
  getAlertKeys,
  getAlertsEmptyState,
  getFreshAlertKeys,
  getSortedAlerts,
} from '@/utils/alerts'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import AlertsLoader from '@/components/alerts/AlertsLoader.vue'
import AlertsTable from '@/components/alerts/AlertsTable.vue'
import AlertDialogHost from '@/components/alerts/AlertDialogHost.vue'

const { data, loading, error, reload } = useMonitoringData((dims) => api.monitoring.getAlerts(dims))

const emptyState = computed(() => (data.value ? getAlertsEmptyState(data.value) : null))

const alerts = computed(() => getSortedAlerts(data.value?.groups ?? [], null, 1))

const filtersStore = useFiltersStore()

const seenKeys = shallowRef<Set<string> | null>(null)

const freshKeys = computed(() => getFreshAlertKeys(alerts.value, seenKeys.value))

const alertDialog = useTemplateRef('alertDialog')

function markSeen() {
  seenKeys.value = getAlertKeys(alerts.value)
}

watch(alerts, (value) => {
  if (data.value && seenKeys.value === null) seenKeys.value = getAlertKeys(value)
})

watch(
  () => filtersStore.dimensions,
  () => (seenKeys.value = null),
)
</script>
