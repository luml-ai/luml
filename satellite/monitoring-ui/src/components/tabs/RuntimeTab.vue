<template>
  <div>
    <RuntimeLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="runtime">
      <MAlerts v-if="data.alerts?.length" :alerts="data.alerts" />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <template v-else>
        <RuntimeCards :data="data" />
        <MStepSelector />
        <MSeriesCharts v-if="data.series?.length" :series="data.series" />
        <RuntimeStatusBreakdown :rows="data.status_breakdown ?? []" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import RuntimeLoader from '@/components/runtime/RuntimeLoader.vue'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MAlerts from '@/components/MAlerts.vue'
import RuntimeCards from '@/components/runtime/RuntimeCards.vue'
import MStepSelector from '@/components/MStepSelector.vue'
import MSeriesCharts from '@/components/MSeriesCharts.vue'
import RuntimeStatusBreakdown from '@/components/runtime/RuntimeStatusBreakdown.vue'
import { getRuntimeEmptyState } from '@/utils/runtime'

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getRuntime(dims),
)

const emptyState = computed(() => (data.value ? getRuntimeEmptyState(data.value) : null))
</script>

<style scoped>
.runtime {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
