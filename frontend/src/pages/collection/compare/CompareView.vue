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
      v-else-if="artifactsStore.experimentSnapshotProvider"
      :provider="artifactsStore.experimentSnapshotProvider"
      :models-ids="modelIdsList"
      :models-info="modelsInfo"
      :theme="themeStore.getCurrentTheme"
    ></ExperimentSnapshot>
  </div>
</template>

<script setup lang="ts">
import type { ModelsInfo } from '@luml/experiments'
import { ComparisonHeader, ComparisonModelsList, ExperimentSnapshot } from '@luml/experiments'
import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useArtifactsStore } from '@/stores/artifacts'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'
import { Skeleton } from 'primevue'
import { getModelColorByIndex } from '@/helpers/helpers'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const themeStore = useThemeStore()
const artifactsStore = useArtifactsStore()
const { init } = useExperimentSnapshotsDatabaseProvider()

const loading = ref(false)

const modelIdsList = computed(() => {
  if (!route.query.models) return []
  if (Array.isArray(route.query.models)) {
    return route.query.models.filter((model) => model !== null).map(String)
  }
  return [String(route.query.models)]
})

const modelsList = ref<ModelArtifact[]>([])

const modelsInfo = computed(() => {
  return modelsList.value.reduce((acc: ModelsInfo, model, index) => {
    const name = model.name
    const color = getModelColorByIndex(index)
    acc[model.id] = { name, color }
    return acc
  }, {})
})

async function onModelIdsChange(newModelIds: string[]) {
  try {
    loading.value = true
    artifactsStore.resetExperimentSnapshotProvider()
    modelsList.value = []
    const promises = await Promise.allSettled(
      newModelIds.map((modelId) => artifactsStore.getArtifact(modelId)),
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
  artifactsStore.resetExperimentSnapshotProvider()
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
