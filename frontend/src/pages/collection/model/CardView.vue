<template>
  <div v-if="modelsStore.currentModelMetadata && modelsStore.currentModelTag">
    <CollectionModelCardTabular
      v-if="isTabular && 'metrics' in modelsStore.currentModelMetadata"
      :metrics="modelsStore.currentModelMetadata.metrics"
      :tag="modelsStore.currentModelTag"
    ></CollectionModelCardTabular>
    <CollectionModelCardOptimization
      v-else-if="isOptimization && 'edges' in modelsStore.currentModelMetadata"
      :data="modelsStore.currentModelMetadata"
    ></CollectionModelCardOptimization>
    <div v-else class="card">
      <header class="card-header">
        <h3 class="card-title card-title--medium">Inputs and outputs</h3>
      </header>
      <div>{{ currentModel?.manifest.producer_tags }}</div>
    </div>
  </div>
  <CollectionModelCardHtml
    v-else-if="modelsStore.currentModelHtmlBlobUrl"
    :url="modelsStore.currentModelHtmlBlobUrl"
  >
  </CollectionModelCardHtml>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useModelsStore } from '@/stores/models'
import { useRoute } from 'vue-router'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import CollectionModelCardTabular from '@/components/orbits/tabs/registry/collection/model/CollectionModelCardTabular.vue'
import CollectionModelCardOptimization from '@/components/orbits/tabs/registry/collection/model/CollectionModelCardOptimization.vue'
import CollectionModelCardHtml from '@/components/orbits/tabs/registry/collection/model/CollectionModelCardHtml.vue'

const modelsStore = useModelsStore()
const route = useRoute()

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === +route.params.modelId)
})
const isTabular = computed(
  () => modelsStore.currentModelTag && FnnxService.isTabularTag(modelsStore.currentModelTag),
)
const isOptimization = computed(
  () => modelsStore.currentModelTag && FnnxService.isOptimizationTag(modelsStore.currentModelTag),
)
</script>

<style scoped>
.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 20px;
}

.card-title--medium {
  font-weight: 500;
}

.info-icon {
  color: var(--p-icon-muted-color);
}
</style>
