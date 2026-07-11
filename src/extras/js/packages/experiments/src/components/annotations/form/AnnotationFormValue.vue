<template>
  <FormField name="value" class="form-field">
    <label for="value">Value</label>
    <SelectButton
      v-if="type === AnnotationValueType.BOOL"
      name="value"
      id="value"
      :options="VALUE_OPTIONS"
      option-label="label"
      option-value="value"
      :allow-empty="false"
    >
      <template #option="slotProps">
        <div class="option-item">
          <component
            v-if="VALUE_ICONS[slotProps.option.value as 'true' | 'false']"
            :is="VALUE_ICONS[slotProps.option.value as 'true' | 'false'].icon"
            :color="VALUE_ICONS[slotProps.option.value as 'true' | 'false'].iconColor"
            :size="16"
          />
          <span>{{ slotProps.option.label }}</span>
        </div>
      </template>
    </SelectButton>
    <InputText
      v-else-if="type === AnnotationValueType.STRING"
      name="value"
      id="value"
      placeholder="Enter a value"
    />
    <InputNumber
      v-else-if="type === AnnotationValueType.INT"
      name="value"
      id="value"
      placeholder="Enter a value"
    />
  </FormField>
</template>

<script setup lang="ts">
import { AnnotationValueType } from '../annotations.interface'
import { FormField } from '@primevue/forms'
import { SelectButton, InputText, InputNumber } from 'primevue'
import { VALUE_OPTIONS, VALUE_ICONS } from './data'

interface Props {
  type: AnnotationValueType
  value: any
}

defineProps<Props>()
</script>

<style scoped>
.option-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
