<template>
  <div>
    <AlertsLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <template v-else-if="data">
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <AlertsTable v-else :groups="data.groups" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { getAlertsEmptyState } from '@/utils/alerts'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import AlertsLoader from '@/components/alerts/AlertsLoader.vue'
import AlertsTable from '@/components/alerts/AlertsTable.vue'

const { data, loading, error, reload } = useMonitoringData((dims) => api.monitoring.getAlerts(dims))

const emptyState = computed(() => (data.value ? getAlertsEmptyState(data.value) : null))
</script>
