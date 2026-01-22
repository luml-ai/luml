<template>
  <div v-if="loading">
    <Skeleton style="height: 210px; margin-bottom: 20px"></Skeleton>
    <div
      style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px"
    >
      <Skeleton style="height: 300px; width: 100%"></Skeleton>
      <Skeleton style="height: 300px; width: 100%"></Skeleton>
    </div>
    <Skeleton style="height: 210px; margin-bottom: 20px"></Skeleton>
  </div>
  <ExperimentSnapshot
    v-if="modelsStore.experimentSnapshotProvider && modelsStore.currentModel"
    :provider="modelsStore.experimentSnapshotProvider"
    :models-ids="[String(modelsStore.currentModel.id)]"
    :models-info="modelsInfo"
  ></ExperimentSnapshot>
</template>

<script setup lang="ts">
import type { ModelInfo } from '@/modules/experiment-snapshot/interfaces/interfaces'
import { ExperimentSnapshot } from '@/modules/experiment-snapshot'
import { computed, onMounted, ref } from 'vue'
import { useModelsStore } from '@/stores/models'
import { Skeleton } from 'primevue'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'
import { getModelColorByIndex } from '@/modules/experiment-snapshot/helpers/helpers'

const modelsStore = useModelsStore()
const { init } = useExperimentSnapshotsDatabaseProvider()

const loading = ref(false)

const modelsInfo = computed(() => {
  const data: Record<string, ModelInfo> = {}
  if (modelsStore.currentModel) {
    data[modelsStore.currentModel.id] = {
      name: modelsStore.currentModel.model_name,
      color: getModelColorByIndex(0),
    }
  }
  return data
})

onMounted(async () => {
  if (modelsStore.experimentSnapshotProvider) return
  try {
    loading.value = true
    if (!modelsStore.currentModel) throw new Error('Current model does not exist')
    await init([modelsStore.currentModel])
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
