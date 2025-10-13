<template>
  <component
    v-if="component"
    :is="component"
    :model="model"
    :current-tag="currentTag"
    :model-id="modelId"
  />
  <div v-else class="placeholder">
    <h2 class="title">Incorrect model</h2>
    <d-button @click="$emit('exit')">Go back</d-button>
  </div>
</template>

<script setup lang="ts">
import type { Model } from '@fnnx/web'
import { computed } from 'vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import TabularTask from './tabular/index.vue'
import RuntimeDashboardPromptOptimization from './prompt-optimization/RuntimeDashboardPromptOptimization.vue'

type Props = {
  currentTag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM
  model: Model
  modelId: string | null
}
type Emits = {
  exit: void
}

const props = defineProps<Props>()
defineEmits<Emits>()

const component = computed(() => {
  if (
    [
      FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1,
      FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1,
    ].includes(props.currentTag)
  ) {
    return TabularTask
  } else if ([FNNX_PRODUCER_TAGS_MANIFEST_ENUM.prompt_optimization_v1].includes(props.currentTag)) {
    return RuntimeDashboardPromptOptimization
  }
  return null
})
</script>

<style scoped>
.placeholder {
  display: flex;
  flex-direction: column;
  gap: 15px;
  align-items: flex-start;
  padding: 15px;
}
</style>
