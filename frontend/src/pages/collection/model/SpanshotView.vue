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
    v-if="modelsStore.experimentSnapshotProvider && currentModel"
    :provider="modelsStore.experimentSnapshotProvider"
    :models-ids="[currentModel.id]"
    :models-info="modelsInfo"
  ></ExperimentSnapshot>
</template>

<script setup lang="ts">
import { ExperimentSnapshot } from '@/modules/experiment-snapshot'
import { computed, onMounted, ref } from 'vue'
import { useModelsStore } from '@/stores/models'
import { useRoute } from 'vue-router'
import { Skeleton } from 'primevue'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'
import type { ModelInfo } from '@/modules/experiment-snapshot/interfaces/interfaces'
import { getModelColorByIndex } from '@/modules/experiment-snapshot/helpers/helpers'

const modelsStore = useModelsStore()
const route = useRoute()
const { init } = useExperimentSnapshotsDatabaseProvider()

const loading = ref(false)

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === +route.params.modelId)
})

const modelsInfo = computed(() => {
  const data: Record<string, ModelInfo> = {}
  if (currentModel.value) {
    data[currentModel.value.id] = {
      name: currentModel.value.model_name,
      color: getModelColorByIndex(0),
    }
  }
  return data
})

onMounted(async () => {
  if (modelsStore.experimentSnapshotProvider) return
  try {
    loading.value = true
    if (!currentModel.value) throw new Error('Current model does not exist')
    await init([currentModel.value])
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
