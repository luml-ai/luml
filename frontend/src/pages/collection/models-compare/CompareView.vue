<template>
  <div>
    <ComparisonHeader></ComparisonHeader>
    <ComparisonModelsList
      :models-ids="modelIdsList"
      :models-list="modelsStore.modelsList"
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
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ComparisonHeader } from '@/modules/experiment-snapshot'
import { ComparisonModelsList } from '@/modules/experiment-snapshot'
import { useModelsStore } from '@/stores/models'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'
import { Skeleton } from 'primevue'
import { ExperimentSnapshot } from '@/modules/experiment-snapshot'
import { getModelColorByIndex } from '@/modules/experiment-snapshot/helpers/helpers'
import type { ModelsInfo } from '@/modules/experiment-snapshot/interfaces/interfaces'

const route = useRoute()
const modelsStore = useModelsStore()
const { init } = useExperimentSnapshotsDatabaseProvider()

const loading = ref(false)

const modelIdsList = computed(() => {
  if (typeof route.query.models !== 'object') return []
  return route.query.models?.filter((model) => model !== null).map((modelId) => +modelId) || []
})

const modelsList = computed(() =>
  modelIdsList.value
    .map((modelId) => modelsStore.modelsList.find((model) => model.id === modelId))
    .filter((model) => !!model),
)

const modelsInfo = computed(() => {
  return modelsList.value.reduce((acc: ModelsInfo, model, index) => {
    const name = model.model_name
    const color = getModelColorByIndex(index)
    acc[model.id] = { name, color }
    return acc
  }, {})
})

onMounted(async () => {
  if (modelsStore.experimentSnapshotProvider) return
  try {
    loading.value = true
    await init(modelsList.value)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  modelsStore.resetExperimentSnapshotProvider()
})
</script>

<style scoped>
.loading-block {
  min-height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
