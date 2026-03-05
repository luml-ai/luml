<template>
  <EvalsDatasetsList
    v-if="evalsStore.getProvider"
    :models-info="modelsInfo"
    loader-height="calc(100vh-250px)"
    :dataset-table-height="tableHeight"
  ></EvalsDatasetsList>
</template>

<script setup lang="ts">
import { useEvalsStore, EvalsDatasetsList, type ModelsInfo } from '@luml/experiments'
import { computed } from 'vue'
import { useExperimentStore } from '@/store/experiment'
import { useWindowSize } from '@vueuse/core'

const experimentStore = useExperimentStore()
const evalsStore = useEvalsStore()
const { height: windowHeight } = useWindowSize()

const modelsInfo = computed<ModelsInfo>(() => {
  if (!experimentStore.experiment) return {}
  return {
    [experimentStore.experiment.id]: {
      name: experimentStore.experiment.name,
      color: 'var(--p-primary-color)',
    },
  }
})

const tableHeight = computed(() => {
  return `${windowHeight.value - 450}px`
})
</script>

<style scoped></style>
