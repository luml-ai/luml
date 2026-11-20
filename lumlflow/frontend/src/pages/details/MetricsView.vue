<template>
  <div class="flex flex-col gap-4">
    <ExperimentStatusNotices :statuses="dynamicMetricsStore.statuses" :models-info="modelsInfo" />
    <DynamicMetrics :models-info="modelsInfo" :show-title="false"></DynamicMetrics>
  </div>
  <div v-if="empty" class="empty-message">No metrics found in this experiment</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useExperimentStore } from '@/store/experiment'
import { DynamicMetrics, ExperimentStatusNotices, useDynamicMetricsStore } from '@luml/experiments'

const experimentStore = useExperimentStore()
const dynamicMetricsStore = useDynamicMetricsStore()

// The catalog, not `dynamic_params`, says which metrics exist: it is read with the charts.
const empty = computed(
  () =>
    !dynamicMetricsStore.loading &&
    dynamicMetricsStore.catalogs !== null &&
    dynamicMetricsStore.catalogs.errors.size === 0 &&
    dynamicMetricsStore.metricsNames.length === 0,
)

const modelsInfo = computed(() => {
  if (!experimentStore.experiment) return {}
  return {
    [experimentStore.experiment.id]: {
      name: experimentStore.experiment.name,
      color: 'var(--p-primary-color)',
    },
  }
})
</script>

<style scoped>
.empty-message {
  font-size: 16px;
  color: var(--p-form-field-float-label-color);
  text-align: center;
  padding: 20px;
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
