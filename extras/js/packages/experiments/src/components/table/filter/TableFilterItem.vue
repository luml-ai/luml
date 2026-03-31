<template>
  <div class="row">
    <div>
      <label for="field" class="label">
        Field
        <InfoIcon
          v-if="errors?.global"
          v-tooltip="errors.global"
          :size="12"
          color="var(--p-message-error-color)"
        />
      </label>
      <Select
        v-model="modelValue.field"
        id="field"
        placeholder="Choose field"
        fluid
        size="small"
        :options="fieldOptions"
        option-label="label"
        option-value="value"
        :invalid="!!errors?.field"
      />
    </div>
    <div>
      <label for="operator" class="label">Operator</label>
      <Select
        v-model="modelValue.operator"
        id="operator"
        fluid
        size="small"
        :options="availableOperators"
        option-label="label"
        option-value="value"
        :invalid="!!errors?.operator"
      />
    </div>
    <div>
      <label for="value" class="label">Value</label>
      <Select
        v-if="fieldType === 'boolean'"
        v-model="modelValue.value"
        id="value"
        fluid
        size="small"
        :options="[
          { label: 'True', value: 'True' },
          { label: 'False', value: 'False' },
        ]"
        option-label="label"
        option-value="value"
        :invalid="!!errors?.value"
      />
      <InputText
        v-else
        v-model="modelValue.value as string"
        id="value"
        inputId="value"
        placeholder="Put value"
        fluid
        size="small"
        :invalid="!!errors?.value"
      />
    </div>
    <Button variant="text" severity="secondary" class="button" @click="$emit('remove')">
      <template #icon>
        <X :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import type { FilterItem, FilterItemEmits, FilterItemProps } from './filter.interface'
import { InputText, Select, Button } from 'primevue'
import { InfoIcon, X } from 'lucide-vue-next'
import { FILTER_OPERATORS } from './filter.const'
import { computed, watch } from 'vue'

const props = defineProps<FilterItemProps>()

const emit = defineEmits<FilterItemEmits>()

const modelValue = defineModel<FilterItem>('modelValue', { required: true })

const fieldOptions = computed(() => {
  return props.fields.map((field) => ({ label: field.name, value: field.name }))
})

const fieldType = computed(() => {
  if (!modelValue.value.field) return null
  return props.fields.find((field) => field.name === modelValue.value.field)?.type
})

const availableOperators = computed(() => {
  if (!fieldType.value) return []
  return FILTER_OPERATORS.filter((operator) =>
    operator.availableTypes.includes(fieldType.value as string),
  )
})

watch(fieldType, () => {
  modelValue.value.value = null
})

watch(availableOperators, (newOperators) => {
  const selectedOperator = modelValue.value.operator
  if (!selectedOperator) return
  const selectedOperatorAvailable = newOperators.find(
    (operator) => operator.value === selectedOperator,
  )
  if (selectedOperatorAvailable) return
  modelValue.value.operator = null
})

watch(
  modelValue,
  () => {
    emit('clear-errors')
  },
  {
    deep: true,
  },
)
</script>

<style scoped>
.row {
  display: grid;
  grid-template-columns: 180px 80px 180px 35px;
  gap: 13px;
  align-items: flex-end;
}

.label {
  font-size: 14px;
  margin-bottom: 7px;
  display: inline-block;
  display: flex;
  align-items: center;
  gap: 4px;
}

.button {
  width: 27px;
  height: 27px;
}
</style>
