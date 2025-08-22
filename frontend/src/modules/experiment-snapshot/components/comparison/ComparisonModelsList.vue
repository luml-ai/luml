<template>
  <div class="models">
    <div v-for="model in models" class="model">
      <div
        class="model-circle"
        :style="{
          backgroundColor: model.color,
        }"
      ></div>
      <div>{{ model.name }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { getModelColorByIndex } from '../../helpers/helpers'
import { computed } from 'vue'

type Props = {
  modelsIds: number[]
  modelsList: MlModel[]
}

const props = defineProps<Props>()

const models = computed(() => {
  return props.modelsIds.map((modelId, index) => {
    const model = props.modelsList.find((model) => model.id === modelId)
    const name = model?.model_name || 'Unknown model'
    return { name, color: getModelColorByIndex(index) }
  })
})
</script>

<style scoped>
.models {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 20px;
}
.model {
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  border: 1px solid var(--p-content-border-color);
  background: var(--p-card-background);
  border-radius: 8px;
}
.model-circle {
  width: 12px;
  height: 12px;
  flex: 0 0 auto;
  border-radius: 50%;
}
</style>
