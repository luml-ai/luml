<template>
  <div class="models">
    <TracesModel
      v-for="item in uniqueModelsIds"
      :key="item"
      :id="item"
      :name="modelsInfo[item]?.name || 'Unknown model'"
    ></TracesModel>
  </div>
</template>

<script setup lang="ts">
import type { ModelsInfo } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import { computed } from 'vue'
import TracesModel from './TracesModel.vue'

type Props = {
  modelsInfo: ModelsInfo
}

defineProps<Props>()

const evalsStore = useEvalsStore()

const uniqueModelsIds = computed(() => {
  if (!evalsStore.currentEvalData) return []
  const idsSet = evalsStore.currentEvalData.reduce((acc, item) => {
    acc.add(item.modelId)
    return acc
  }, new Set<string>())
  return Array.from(idsSet)
})
</script>

<style scoped>
.models {
  display: flex;
}
</style>
