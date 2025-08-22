<template>
  <div>
    <ComparisonHeader></ComparisonHeader>
    <ComparisonModelsList
      :models-ids="modelIdsList"
      :models-list="modelsStore.modelsList"
    ></ComparisonModelsList>
    <div v-if="loading" class="loading-block">
      <ProgressSpinner></ProgressSpinner>
    </div>
    <ExperimentSnapshot
      v-else-if="modelsStore.experimentSnapshotProvider"
      :provider="modelsStore.experimentSnapshotProvider"
      :models-ids="modelIdsList"
      :models-names="modelsNames"
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
import { ProgressSpinner } from 'primevue'
import { ExperimentSnapshot } from '@/modules/experiment-snapshot'

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

const modelsNames = computed(() => {
  return modelsList.value.reduce((acc: Record<string, string>, model) => {
    acc[model.id] = model.model_name
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
