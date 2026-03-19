<template>
  <EvalsDatasetsList
    v-if="evalsStore.getProvider"
    :models-info="modelsInfo"
    loader-height="calc(100vh-250px)"
    empty-message="No evals found in this experiment"
  ></EvalsDatasetsList>
</template>

<script setup lang="ts">
import { useEvalsStore, EvalsDatasetsList, type ModelsInfo } from '@luml/experiments'
import { computed } from 'vue'
import { useExperimentStore } from '@/store/experiment'

const experimentStore = useExperimentStore()
const evalsStore = useEvalsStore()

const modelsInfo = computed<ModelsInfo>(() => {
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
