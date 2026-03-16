<template>
  <div class="flex flex-col gap-4">
    <DynamicMetrics
      :metrics-names="metrics"
      :models-info="modelsInfo"
      :provider="evalsStore.getProvider"
      :show-title="false"
    ></DynamicMetrics>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useExperimentStore } from '@/store/experiment'
import { DynamicMetrics } from '@luml/experiments'
import { useEvalsStore } from '@luml/experiments'

const experimentStore = useExperimentStore()
const evalsStore = useEvalsStore()

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

<style scoped></style>
