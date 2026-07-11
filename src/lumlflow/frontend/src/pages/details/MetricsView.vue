<template>
  <div v-if="metrics.length" class="flex flex-col gap-4">
    <DynamicMetrics
      :metrics-names="metrics"
      :models-info="modelsInfo"
      :show-title="false"
    ></DynamicMetrics>
  </div>
  <div v-else class="empty-message">No metrics found in this experiment</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useExperimentStore } from '@/store/experiment'
import { DynamicMetrics } from '@luml/experiments'

const experimentStore = useExperimentStore()

const metrics = computed(() => {
  if (!experimentStore.experiment) return []
  return Object.keys(experimentStore.experiment.dynamic_params || {})
})

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
