<template>
  <!-- eslint-disable vue/no-mutating-props -- editor mutates the shared reactive node-data object in place -->
  <div class="sidebar">
    <header class="header">
      <div class="header-main">
        <div class="header-left">
          <component
            width="20"
            height="20"
            :is="PROMPT_NODES_ICONS[data.icon]"
            :color="data.iconColor"
          ></component>
          <input v-model="data.label" type="text" class="title-input" />
        </div>
        <d-button severity="secondary" rounded variant="text" @click="$emit('close')">
          <template #icon>
            <x width="16" height="16" color="var(--p-button-text-secondary-color)" />
          </template>
        </d-button>
      </div>
      <d-message v-if="duplicatedFieldsIds.length" severity="error"
        >A card cannot contain two fields with the same name.</d-message
      >
    </header>
    <div class="body">
      <CustomTextarea
        v-if="hintVisible"
        v-model="data.hint"
        fluid
        rows="1"
        placeholder="Hint"
        size="small"
        autoResize
        :maxHeight="75"
        class="hint"
      />
      <div class="all-fields">
        <div v-if="inputsVisible" class="inputs fields">
          <base-field
            v-for="field in inputFields"
            :key="field.id"
            :data="field"
            :is-duplicate="isDuplicate(field.id)"
            @delete="onDeleteField(field.id)"
          />
          <d-button
            label="Add input field"
            variant="text"
            size="small"
            class="add-button"
            @click="addField('input')"
          >
            <template #icon>
              <plus width="14" height="14" />
            </template>
          </d-button>
        </div>
        <div v-if="outputsVisible" class="outputs fields">
          <base-field
            v-for="field in outputFields"
            :key="field.id"
            :data="field"
            :is-duplicate="isDuplicate(field.id)"
            :type-label="props.data.type === NodeTypeEnum.gate ? 'input' : undefined"
            @delete="onDeleteField(field.id)"
          />
          <d-button
            v-if="availableAddOutput"
            :label="addOutputLabel"
            variant="text"
            size="small"
            class="add-button"
            @click="addField('output')"
          >
            <template #icon>
              <plus width="14" height="14" />
            </template>
          </d-button>
        </div>
        <div v-if="conditionsVisible" class="conditions fields">
          <h3 class="field-title">Conditions</h3>
          <condition-field
            v-for="(field, index) in conditionFields"
            :key="field.id"
            :data="field"
            :index="index + 1"
            @delete="onDeleteField(field.id)"
          />
          <d-button
            label="Add condition"
            variant="text"
            size="small"
            class="add-button"
            @click="addField('condition')"
          >
            <template #icon>
              <plus width="14" height="14" />
            </template>
          </d-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NodeData, FieldVariant, NodeField } from '../../interfaces'
import { computed } from 'vue'
import { PROMPT_NODES_ICONS, NodeTypeEnum } from '../../interfaces'
import { v4 as uuidv4 } from 'uuid'
import { Position } from '@vue-flow/core'
import { X, Plus } from 'lucide-vue-next'
import BaseField from './BaseField.vue'
import ConditionField from './ConditionField.vue'
import CustomTextarea from '@/components/ui/CustomTextarea.vue'
import { useVueFlow } from '@vue-flow/core'

const { getEdges, removeEdges } = useVueFlow()

type Props = {
  data: NodeData
}
type Emits = {
  close: []
}

const props = defineProps<Props>()
defineEmits<Emits>()

const inputFields = computed(() => props.data.fields.filter((field) => field.variant === 'input'))
const outputFields = computed(() => props.data.fields.filter((field) => field.variant === 'output'))
const conditionFields = computed(() =>
  props.data.fields.filter((field) => field.variant === 'condition'),
)
const hintVisible = computed(
  () => props.data.type === NodeTypeEnum.gate || props.data.type === NodeTypeEnum.processor,
)
const inputsVisible = computed(
  () => props.data.type === NodeTypeEnum.input || props.data.type === NodeTypeEnum.processor,
)
const outputsVisible = computed(
  () =>
    props.data.type === NodeTypeEnum.output ||
    props.data.type === NodeTypeEnum.processor ||
    props.data.type === NodeTypeEnum.gate,
)
const conditionsVisible = computed(() => props.data.type === NodeTypeEnum.gate)
const availableAddOutput = computed(
  () => !(props.data.type === NodeTypeEnum.gate) || outputFields.value.length === 0,
)
const addOutputLabel = computed(() =>
  props.data.type === NodeTypeEnum.gate ? 'Add input field' : 'Add output field',
)
const duplicatedFieldsIds = computed(() => {
  const inputDuplicates = inputFields.value.filter(
    (item, index, self) =>
      item.value &&
      self.find((searchedItem) => searchedItem.value === item.value && searchedItem.id !== item.id),
  )
  const outputDuplicates = inputFields.value.filter(
    (item, index, self) =>
      item.value &&
      self.find((searchedItem) => searchedItem.value === item.value && searchedItem.id !== item.id),
  )
  return [...inputDuplicates.map((item) => item.id), ...outputDuplicates.map((item) => item.id)]
})
const isDuplicate = computed(
  () => (id: string) => !!duplicatedFieldsIds.value.find((searchedId) => searchedId === id),
)

function onDeleteField(id: string) {
  const fieldEdges = getEdges.value.filter(
    (edge) => edge.targetHandle === id || edge.sourceHandle === id,
  )
  removeEdges(fieldEdges)
  // eslint-disable-next-line vue/no-mutating-props -- shared reactive node-data object is mutated in place by design
  props.data.fields = props.data.fields.filter((field) => field.id !== id)
}
function addField(variant: FieldVariant) {
  let handlePosition: Position.Left | Position.Right
  if (props.data.type === NodeTypeEnum.processor) {
    handlePosition = variant === 'output' ? Position.Right : Position.Left
  } else {
    handlePosition = variant === 'output' ? Position.Left : Position.Right
  }
  const field: NodeField = {
    id: uuidv4(),
    value: '',
    handlePosition,
    variant,
  }
  // eslint-disable-next-line vue/no-mutating-props -- shared reactive node-data object is mutated in place by design
  props.data.fields.push(field)
}
</script>

<style scoped>
.sidebar {
  max-width: 420px;
  padding: 24px 20px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
}
.header {
  margin-bottom: 20px;
  flex: 0 0 auto;
}
.header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-input {
  border: none;
  background-color: transparent;
  outline: none;
  font-size: 16px;
  font-weight: 500;
  text-transform: uppercase;
  font-family: 'Inter', sans-serif;
}
.body {
  margin-bottom: 8px;
  flex: 1 1 auto;
  overflow-y: auto;
}
.fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.field-title {
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
}
.hint {
  margin-bottom: 20px;
}
.inputs:not(:last-child),
.outputs:not(:last-child) {
  margin-bottom: 12px;
}
.conditions {
  padding-top: 12px;
  border-top: 1px solid var(--p-divider-border-color);
}
.outputs:not(:first-child) {
  padding-top: 12px;
  border-top: 1px solid var(--p-divider-border-color);
}
.add-button {
  align-self: flex-start;
}
</style>
