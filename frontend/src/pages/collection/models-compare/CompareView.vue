<template>
  <div>
    <ComparisonHeader></ComparisonHeader>
    <ComparisonModelsList
      :models-ids="modelIdsList"
      :models-list="modelsList"
      :models-info="modelsInfo"
    ></ComparisonModelsList>
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
      v-else-if="modelsStore.experimentSnapshotProvider"
      :provider="modelsStore.experimentSnapshotProvider"
      :models-ids="modelIdsList"
      :models-info="modelsInfo"
    ></ExperimentSnapshot>
  </div>
</template>

<script setup lang="ts">
import type { ModelsInfo } from '@/modules/experiment-snapshot/interfaces/interfaces'
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ComparisonHeader } from '@/modules/experiment-snapshot'
import { ComparisonModelsList } from '@/modules/experiment-snapshot'
import { useModelsStore } from '@/stores/models'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'
import { Skeleton } from 'primevue'
import { ExperimentSnapshot } from '@/modules/experiment-snapshot'
import { getModelColorByIndex } from '@/modules/experiment-snapshot/helpers/helpers'

const route = useRoute()
const modelsStore = useModelsStore()
const { init } = useExperimentSnapshotsDatabaseProvider()

const loading = ref(false)

const modelIdsList = computed(() => {
  if (!route.query.models) return []
  if (Array.isArray(route.query.models)) {
    return route.query.models.filter((model) => model !== null).map(String)
  }
  return [String(route.query.models)]
})

const modelsList = ref<MlModel[]>([])

const modelsInfo = computed(() => {
  return modelsList.value.reduce((acc: ModelsInfo, model, index) => {
    const name = model.model_name
    const color = getModelColorByIndex(index)
    acc[model.id] = { name, color }
    return acc
  }, {})
})

async function onModelIdsChange(newModelIds: string[]) {
  try {
    loading.value = true
    modelsStore.resetExperimentSnapshotProvider()
    modelsList.value = []
    const promises = await Promise.allSettled(
      newModelIds.map((modelId) => modelsStore.getModel(modelId)),
    )
    const models = promises
      .map((promise) => (promise.status === 'fulfilled' ? promise.value : null))
      .filter((model) => !!model)
    modelsList.value = models
    await init(modelsList.value)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onUnmounted(() => {
  modelsStore.resetExperimentSnapshotProvider()
})

watch(modelIdsList, onModelIdsChange, { immediate: true, deep: true })
</script>

<style scoped>
.loading-block {
  min-height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
