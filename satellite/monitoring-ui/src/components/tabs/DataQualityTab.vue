<template>
  <div>
    <DataQualityLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="data-quality">
      <MAlerts v-if="data.alerts?.length" :alerts="data.alerts" />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <DataQualityTable v-else :features="data.features" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { getDataQualityEmptyState } from '@/utils/data-quality'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MAlerts from '@/components/MAlerts.vue'
import DataQualityLoader from '@/components/data-quality/DataQualityLoader.vue'
import DataQualityTable from '@/components/data-quality/DataQualityTable.vue'

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getDataQuality(dims),
)

const emptyState = computed(() => (data.value ? getDataQualityEmptyState(data.value) : null))
</script>

<style scoped>
.data-quality {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
