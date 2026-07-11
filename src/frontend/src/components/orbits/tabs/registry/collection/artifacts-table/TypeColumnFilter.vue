<template>
  <div v-for="type in ARTIFACT_TYPE_OPTIONS" :key="type.value" class="filter-checkbox">
    <Checkbox v-model="modelValue" name="type" :inputId="type.value" :value="type.value" />
    <label :for="type.value">{{ type.label }}</label>
    <component :is="type.icon" :size="12" :color="type.color" />
  </div>
</template>

<script setup lang="ts">
import { ARTIFACT_TYPE_OPTIONS } from './models-table.data'
import { Checkbox } from 'primevue'

const modelValue = defineModel<string[] | null>('modelValue', { default: [] })
</script>

<style scoped>
.filter-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
