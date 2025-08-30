<template>
  <div v-if="currentModel">
    <div class="title">Model details</div>
    <CollectionModelTabs
      :show-model-card="isModelCardAvailable"
      :show-experiment-snapshot="isExperimentSnapshotCardAvailable"
    ></CollectionModelTabs>
    <div class="view-wrapper">
      <RouterView></RouterView>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useModelsStore } from '@/stores/models'
import { computed, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import CollectionModelTabs from '@/components/orbits/tabs/registry/collection/model/CollectionModelTabs.vue'

const modelsStore = useModelsStore()
const route = useRoute()

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === +route.params.modelId)
})

const isModelCardAvailable = computed(() => {
  if (!currentModel.value) return false
  const fileIndex = currentModel.value.file_index
  const includeDataforceTag = FnnxService.getTypeTag(currentModel.value.manifest)
  return !!(includeDataforceTag || FnnxService.findHtmlCard(fileIndex))
})

const isExperimentSnapshotCardAvailable = computed(() => {
  if (!currentModel.value) return false
  const fileIndex = currentModel.value.file_index
  return !!FnnxService.findExperimentSnapshotArchiveName(fileIndex)
})

onUnmounted(() => {
  modelsStore.resetCurrentModelTag()
  modelsStore.resetCurrentModelMetadata()
  modelsStore.resetCurrentModelHtmlBlobUrl()
  modelsStore.resetExperimentSnapshotProvider()
})
</script>

<style scoped>
.title {
  margin-bottom: 20px;
}

.view-wrapper {
  padding-top: 20px;
}
</style>
