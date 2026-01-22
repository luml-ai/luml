<template>
  <div class="field" style="margin-bottom: 12px">
    <label for="modelId" class="label required">Model</label>
    <Select
      v-model="modelValue"
      id="modelId"
      name="modelId"
      placeholder="Select model"
      fluid
      :options="modelsList"
      option-label="model_name"
      option-value="id"
      :disabled="disabled"
      :virtualScrollerOptions="virtualScrollerOptions"
    >
      <template #header>
        <div class="dropdown-title">Available model</div>
      </template>
    </Select>
  </div>
</template>

<script setup lang="ts">
import { useModelsList } from '@/hooks/useModelsList'
import { Select } from 'primevue'
import { watch } from 'vue'
import { useModelsStore } from '@/stores/models'
import { getErrorMessage } from '@/helpers/helpers'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'

type Props = {
  disabled: boolean
  organizationId: string
  orbitId: string
  collectionId: string | null
  initialModelId?: string
}

const { setRequestInfo, getInitialPage, modelsList, reset, addModelsToList, onLazyLoad } =
  useModelsList(20, false)
const modelsStore = useModelsStore()
const toast = useToast()

const virtualScrollerOptions = {
  lazy: true,
  onLazyLoad: onLazyLoad,
  itemSize: 38,
}

const props = defineProps<Props>()

const modelValue = defineModel<string | null>('modelValue')

async function addInitialModelToList(modelId: string) {
  const model = await modelsStore.getModel(modelId)
  addModelsToList([model])
}

async function onRequestInfoChange() {
  try {
    reset()
    if (props.initialModelId) {
      addInitialModelToList(props.initialModelId)
    }
    if (!props.collectionId) return
    setRequestInfo({
      organizationId: props.organizationId,
      orbitId: props.orbitId,
      collectionId: props.collectionId,
    })
    await getInitialPage()
  } catch (e) {
    const message = getErrorMessage(e, 'Failed to load models')
    toast.add(simpleErrorToast(message))
  }
}

watch(() => [props.organizationId, props.orbitId, props.collectionId], onRequestInfoChange, {
  immediate: true,
  deep: true,
})
</script>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.dropdown-title {
  padding: 12px 16px 8px;
  font-size: 14px;
  font-weight: var(--p-select-option-group-font-weight);
  color: var(--p-select-option-group-color);
}
</style>
