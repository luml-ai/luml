<template>
  <div class="content">
    <header class="header">
      <h3 class="title">
        <CircleArrowDown :size="16" color="var(--p-primary-color)"></CircleArrowDown>
        <span>Inputs</span>
      </h3>
      <div class="header-right">
        <Select
          v-if="showSelect"
          v-model="selectedModel"
          :options="currentModels"
          option-label="name"
          option-value="id"
          size="small"
          placeholder="Model name"
          class="select"
        ></Select>
        <HelpCircle :size="16" color="var(--p-button-text-secondary-color)"></HelpCircle>
      </div>
    </header>
    <div class="list">
      <UiMultiTypeText
        v-for="input in inputsList"
        :key="input[0]"
        :title="input[0]"
        :text="input[1]"
      ></UiMultiTypeText>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CircleArrowDown, HelpCircle } from 'lucide-vue-next'
import { Select } from 'primevue'
import { computed, ref, watch } from 'vue'
import UiMultiTypeText from '../../../ui/UiMultiTypeText.vue'
import { useEvalsStore } from '@/modules/experiment-snapshot/store/evals'
import type { ModelsInfo } from '@/modules/experiment-snapshot/interfaces/interfaces'

type Props = {
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const evalsStore = useEvalsStore()

const selectedModel = ref<number>()

const uniqueModelsIds = computed(() => {
  if (!evalsStore.currentEvalData) return []
  const idsSet = evalsStore.currentEvalData.reduce((acc, item) => {
    acc.add(item.modelId)
    return acc
  }, new Set<number>())
  return Array.from(idsSet)
})

const currentModels = computed(() => {
  return uniqueModelsIds.value.map((id) => {
    return { id, name: props.modelsInfo[id]?.name || 'Unknown model' }
  })
})

const showSelect = computed(() => currentModels.value.length > 1)

const inputsList = computed(() => {
  if (!selectedModel.value) return []
  const inputs =
    evalsStore.currentEvalData?.find((item) => item.modelId === selectedModel.value)?.inputs || {}
  return Object.entries(inputs)
})

watch(
  currentModels,
  () => {
    if (currentModels.value && currentModels.value[0]) {
      selectedModel.value = currentModels.value[0].id
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.content {
  width: 380px;
  border-right: 1px solid var(--p-divider-border-color);
  flex: 0 0 auto;
  overflow: hidden;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 0 20px;
  min-height: 43px;
}
.title {
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}
.header-right {
  display: flex;
  gap: 8px;
  align-items: center;
}
.select {
  width: 120px;
}
.list {
  padding: 0 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  overflow-y: auto;
}

@media (max-width: 992px) {
  .content {
    width: 300px;
  }
}
</style>
