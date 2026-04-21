<template>
  <div class="model">
    <h3 class="model-title">{{ title }}</h3>
    <div class="model-description">{{ description }}</div>
    <d-select
      v-model="selectedModel"
      :options="options"
      optionValue="id"
      optionLabel="label"
      optionGroupLabel="label"
      optionGroupChildren="items"
      placeholder="Select a model"
      filter
      fluid
      size="small"
      filterPlaceholder="Search model"
    >
      <template #option="slotProps">
        <div class="option">
          <img :alt="slotProps.option.label" :src="slotProps.option.icon" />
          <div>{{ slotProps.option.label }}</div>
        </div>
      </template>
      <template #footer>
        <div class="footer">
          <d-button
            class="settings-button"
            variant="text"
            size="small"
            @click="promptFusionService.openSettings()"
          >
            Model provider settings
            <bolt :size="14" />
          </d-button>
        </div>
      </template>
    </d-select>
  </div>
</template>

<script setup lang="ts">
import {
  ModelTypeEnum,
  ProviderModelsEnum,
  type ProviderWithModels,
} from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { computed, onBeforeMount, onBeforeUnmount, ref, watch } from 'vue'
import { Bolt } from 'lucide-vue-next'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'

type Props = {
  title: string
  description: string
  modelType: ModelTypeEnum
}

const props = defineProps<Props>()

const options = ref(promptFusionService.availableModels)
const selectedModel = ref<ProviderModelsEnum | null>(null)

const isTeacherModel = computed(() => props.modelType === ModelTypeEnum.teacher)

function changeOptions(models: ProviderWithModels[]) {
  options.value = models
}

watch(selectedModel, (value) => {
  const modelInService = isTeacherModel.value
    ? promptFusionService.teacherModel
    : promptFusionService.studentModel
  if (value !== modelInService) {
    isTeacherModel.value
      ? promptFusionService.updateTeacherModel(value)
      : promptFusionService.updateStudentModel(value)
  }
})

onBeforeMount(() => {
  selectedModel.value = isTeacherModel.value
    ? promptFusionService.teacherModel
    : promptFusionService.studentModel
  promptFusionService.on('CHANGE_AVAILABLE_MODELS', changeOptions)
})
onBeforeUnmount(() => {
  promptFusionService.off('CHANGE_AVAILABLE_MODELS', changeOptions)
})
</script>

<style scoped>
.model {
  padding: 8px;
  border-radius: 8px;
  background-color: var(--p-badge-secondary-background);
}
.model-title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
}
.model-description {
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
.option {
  display: flex;
  gap: 4px;
  align-items: center;
}
.option img {
  flex: 0 0 auto;
}
.footer {
  margin: 0 8px;
  padding: 4px 0;
  border-top: 1px solid var(--p-divider-border-color);
}
.settings-button {
  display: flex;
  align-items: center;
  gap: 7px;
}
.model-title::after {
  content: ' *';
  color: var(--p-badge-warn-background);
}
</style>
