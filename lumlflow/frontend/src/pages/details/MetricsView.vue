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
import type { ExperimentMetricHistory } from '@/store/experiments/experiments.interface'
import type { ExperimentSnapshotDynamicMetric } from '../../../../../extras/js/packages/experiments/dist/interfaces/interfaces'
import { useRoute } from 'vue-router'
import { computed, onBeforeUnmount, ref } from 'vue'
import { apiService } from '@/api/api.service'
import { useExperimentStore } from '@/store/experiment'
import { DynamicMetrics } from '@luml/experiments'
import { useEvalsStore } from '@luml/experiments'

const abortController = ref<AbortController>(new AbortController())

const experimentStore = useExperimentStore()
// const route = useRoute()
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

// function prepareMetricData(data: ExperimentMetricHistory) {
//   const initialAcc: ExperimentSnapshotDynamicMetric = {
//     x: [],
//     y: [],
//     modelId: data.experiment_id,
//     aggregated: false,
//   }
//   return data.history.reduce((acc, point) => {
//     acc.x.push(point.step)
//     acc.y.push(point.value)
//     return acc
//   }, initialAcc)
// }

// async function getMetricData(name: string) {
//   const history = await apiService.getExperimentMetricHistory(
//     String(route.params.experimentId),
//     name,
//     1000,
//     abortController.value.signal,
//   )
//   const data = prepareMetricData(history)
//   return [data]
// }

onBeforeUnmount(() => {
  abortController.value.abort()
})
</script>

<style scoped></style>
