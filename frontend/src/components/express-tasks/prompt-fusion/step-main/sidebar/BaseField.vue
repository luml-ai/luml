<template>
  <!-- eslint-disable vue/no-mutating-props -- editor mutates the shared reactive node-field object in place -->
  <div class="field">
    <header class="field-header">
      <h4 class="field-type">{{ typeLabel ? typeLabel : data.variant }}</h4>
      <div class="field-actives">
        <d-button
          :severity="data.variadic ? 'primary' : 'secondary'"
          rounded
          variant="text"
          v-tooltip.top="'Set as List'"
          class="filed-actives-button"
          @click="onVariadicClick"
        >
          <template #icon>
            <brackets width="14" height="14" />
          </template>
        </d-button>
        <span class="divider"></span>
        <d-button
          severity="secondary"
          rounded
          variant="text"
          class="filed-actives-button"
          @click="onTrashClick"
        >
          <template #icon>
            <trash width="14" height="14" />
          </template>
        </d-button>
      </div>
    </header>
    <div class="field-body">
      <d-select
        v-model="data.type"
        :options="options"
        option-label="name"
        option-value="value"
        size="small"
        placeholder="Data type"
        class="select"
      />
      <div class="input-wrapper">
        <d-input-text
          v-model="data.value"
          placeholder="Field name"
          size="small"
          class="input"
          :invalid="isDuplicate"
        />
        <d-message v-if="isDuplicate" severity="error" size="small" variant="simple" class="error"
          >Not a unique name</d-message
        >
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Brackets, Trash } from 'lucide-vue-next'
import { PromptFieldTypeEnum, type NodeField } from '../../interfaces'

type Props = {
  data: NodeField
  typeLabel?: string
  isDuplicate: boolean
}
type Emits = {
  delete: []
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const options = [
  { name: PromptFieldTypeEnum.string, value: 'string' },
  { name: PromptFieldTypeEnum.integer, value: 'integer' },
  { name: PromptFieldTypeEnum.float, value: 'float' },
]

function onVariadicClick() {
  // eslint-disable-next-line vue/no-mutating-props -- shared reactive node-field object is mutated in place by design
  props.data.variadic = !props.data.variadic
}
function onTrashClick() {
  emit('delete')
}
</script>

<style scoped>
.field {
  padding: 8px;
  border-radius: 8px;
  background-color: var(--p-badge-secondary-background);
}
.field-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.field-type {
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 500;
}
.field-actives {
  display: flex;
  gap: 8px;
  align-items: center;
}
.p-button.filed-actives-button {
  width: 16px;
  height: 16px;
  padding: 0;
}
.divider {
  width: 1px;
  flex: 0 0 1px;
  height: 16px;
  background-color: var(--p-divider-border-color);
}
.field-body {
  display: flex;
  align-items: flex-start;
  gap: 4px;
}
.select {
  flex: 0 0 111px;
}
.input-wrapper {
  flex: 1 1 auto;
}
.input {
  width: 100%;
}
.error {
  font-size: 12px;
  padding-top: 7px;
  line-height: 1.75;
}
</style>
