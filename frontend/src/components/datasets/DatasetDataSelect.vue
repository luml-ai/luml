<template>
  <div class="wrapper">
    <Select
      v-model="modelValue"
      :options="options"
      :placeholder="heading"
      :pt="{
        root: 'select-wrapper',
      }"
      fluid
      optionLabel="label"
      optionValue="value"
    >
      <template #value>
        <span>{{ heading }}</span>
      </template>
    </Select>
    <div class="footer">
      <div class="name">{{ name }}</div>
      <div class="text">{{ text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DatasetDataSelectProps } from './interfaces'
import { Select } from 'primevue'

const props = defineProps<DatasetDataSelectProps>()

const modelValue = defineModel<string | null>('modelValue')
</script>

<style scoped>
:deep(.p-select) {
  border: none;
  box-shadow: none;
  background-color: transparent;
}

:deep(.p-select-label) {
  padding: 0;
  color: var(--p-text-color) !important;
}

.wrapper {
  padding: 12px;
}

.footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
}

.name {
  color: var(--p-primary-color);
  font-weight: 600;
}

.text {
  line-height: 1.5;
}

.text::before {
  content: '•';
  margin-left: 10px;
  margin-right: 10px;
}
</style>
