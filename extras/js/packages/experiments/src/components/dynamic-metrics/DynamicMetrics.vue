<template>
  <DynamicMetricsLoader v-if="dynamicMetricsStore.loading" />
  <template v-else-if="bucketStore && dynamicMetricsStore.metricsNames.length > 0">
    <DynamicMetricsToolbar
      :limit="METRICS_LIMIT"
      :total="dynamicMetricsStore.filteredMetrics.length"
      :first="dynamicMetricsStore.page * METRICS_LIMIT"
      :filter="dynamicMetricsStore.filter"
      :show-title="showTitle"
      @page-change="onPageChange"
      @filter-change="dynamicMetricsStore.setFilter"
    />
    <div class="charts">
      <DynamicMetricsItem
        v-for="metric in dynamicMetricsStore.currentMetrics"
        :key="metric.key"
        :store="bucketStore"
        :metric-name="metric.key"
        :model-ids="dynamicMetricsStore.modelIds"
        :full-range="metric.range"
        :models-info="modelsInfo"
      />
    </div>
    <p v-if="dynamicMetricsStore.filteredMetrics.length === 0" class="empty-message">
      No metrics match the filter.
    </p>
  </template>
</template>

<script setup lang="ts">
import type { PageState } from 'primevue'
import type { DynamicMetricsProps } from './dynamic-metrics.interface'
import { computed, onBeforeUnmount, watch } from 'vue'
import { useDynamicMetricsStore } from '../../store/dynamic-metrics'
import { useEvalsStore } from '../../store/evals'
import { METRICS_LIMIT } from '@/store/dynamic-metrics/dynamic-metrics.data'
import DynamicMetricsItem from './DynamicMetricsItem.vue'
import DynamicMetricsToolbar from './DynamicMetricsToolbar.vue'
import DynamicMetricsLoader from './DynamicMetricsLoader.vue'
import { plotlyService } from '@/services/PlotlyService'

const dynamicMetricsStore = useDynamicMetricsStore()
const evalsStore = useEvalsStore()

withDefaults(defineProps<DynamicMetricsProps>(), {
  showTitle: true,
})

const bucketStore = computed(() => evalsStore.metricBucketStore)

function onPageChange(event: PageState) {
  dynamicMetricsStore.setPage(event.page)
}

// Plotly takes long to load and evaluate; fetch it while the catalogs load, not after.
plotlyService.preload()

watch(bucketStore, (store) => dynamicMetricsStore.load(store), { immediate: true })

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

.empty-message {
  font-size: 14px;
  color: var(--p-text-muted-color);
  text-align: center;
  padding: 20px;
}
</style>
