<template>
  <DynamicMetricsToolbar
    v-if="dynamicMetricsStore.currentMetricsNames.length > 0"
    :limit="METRICS_LIMIT"
    :total="metricsNames.length"
    :show-title="showTitle"
    @page-change="onPageChange"
  />
  <div class="charts">
    <DynamicMetricsItem
      v-for="name in dynamicMetricsStore.currentMetricsNames"
      :key="name"
      :metric-name="name"
      :data="dynamicMetricsStore.metrics[name]"
      :models-info="modelsInfo"
    />
  </div>
</template>

<script setup lang="ts">
import type { PageState } from 'primevue'
import type { DynamicMetricsProps } from './dynamic-metrics.interface'
import { onBeforeUnmount, watch } from 'vue'
import { useDynamicMetricsStore } from '../../store/dynamic-metrics'
import { METRICS_LIMIT } from '@/store/dynamic-metrics/dynamic-metrics.data'
import DynamicMetricsItem from './DynamicMetricsItem.vue'
import DynamicMetricsToolbar from './DynamicMetricsToolbar.vue'

const dynamicMetricsStore = useDynamicMetricsStore()

const props = withDefaults(defineProps<DynamicMetricsProps>(), {
  showTitle: true,
})

function onPageChange(event: PageState) {
  dynamicMetricsStore.setPage(event.page)
}

watch(
  () => props.metricsNames,
  () => {
    dynamicMetricsStore.setMetricsNames(props.metricsNames)
  },
  {
    immediate: true,
  },
)

onBeforeUnmount(() => {
  dynamicMetricsStore.reset()
})
</script>

<style scoped>
.charts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.chart-wrapper {
  height: 300px;
}
</style>
