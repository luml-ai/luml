<template>
  <Form :initialValues="INITIAL_VALUES" :resolver="RESOLVER" @submit="onSubmit" class="form">
    <FormField name="type" class="form-field">
      <label for="type">Annotation type</label>
      <SelectButton
        name="type"
        id="type"
        :options="TYPE_OPTIONS"
        option-label="label"
        option-value="value"
      >
        <template #option="slotProps">
          <div class="option-item">
            <component
              v-if="TYPE_ICONS[slotProps.option.value as AnnotationType]"
              :is="TYPE_ICONS[slotProps.option.value as AnnotationType].icon"
              :color="TYPE_ICONS[slotProps.option.value as AnnotationType].iconColor"
              :size="16"
            />
            <span>{{ slotProps.option.label }}</span>
          </div>
        </template>
      </SelectButton>
    </FormField>
    <FormField name="name" class="form-field">
      <label for="name">Annotation name</label>
      <InputText name="name" id="name" placeholder="Enter an annotation name" />
    </FormField>
    <FormField name="dataType" class="form-field">
      <label for="dataType">Data type</label>
      <Select
        name="dataType"
        id="dataType"
        :options="DATA_TYPE_OPTIONS"
        option-label="label"
        option-value="value"
        disabled
      />
    </FormField>
    <FormField name="value" class="form-field">
      <label for="value">Value</label>
      <SelectButton
        name="value"
        id="value"
        :options="VALUE_OPTIONS"
        option-label="label"
        option-value="value"
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
    </FormField>
    <FormField name="rationale" class="form-field">
      <label for="rationale">Rationale</label>
      <InputText name="rationale" id="rationale" placeholder="Enter a rationale" />
    </FormField>
  </Form>
</template>

<script setup lang="ts">
import { Form, FormField } from '@primevue/forms'
import { SelectButton, InputText, Select } from 'primevue'
import {
  INITIAL_VALUES,
  RESOLVER,
  TYPE_OPTIONS,
  TYPE_ICONS,
  type AnnotationType,
  DATA_TYPE_OPTIONS,
  VALUE_OPTIONS,
  VALUE_ICONS,
} from './data'

interface Props {
  data: any | null
}

defineProps<Props>()

function onSubmit() {
  console.log('submit')
}
</script>

<style scoped>
.option-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
