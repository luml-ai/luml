<template>
  <div v-if="loading" class="loading-block">
    <ProgressSpinner></ProgressSpinner>
  </div>
  <ExperimentSnapshot
    v-if="modelsStore.experimentSnapshotProvider && currentModel"
    :provider="modelsStore.experimentSnapshotProvider"
    :models-ids="[currentModel.id]"
    :models-names="modelsNames"
  ></ExperimentSnapshot>
</template>

<script setup lang="ts">
import { ExperimentSnapshot } from '@/modules/experiment-snapshot'
import { computed, onMounted, ref } from 'vue'
import { useModelsStore } from '@/stores/models'
import { useRoute } from 'vue-router'
import { ProgressSpinner } from 'primevue'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'

const modelsStore = useModelsStore()
const route = useRoute()
const { init } = useExperimentSnapshotsDatabaseProvider()

const loading = ref(false)

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === +route.params.modelId)
})

const modelsNames = computed(() => {
  const names: Record<string, string> = {}
  if (currentModel.value) {
    names[currentModel.value.id] = currentModel.value.model_name
  }
  return names
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

<style scoped>
.loading-block {
  min-height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
