<template>
  <div class="item">
    <span class="label">Severity:</span>
    <SelectButton
      :model-value="filtersStore.severity"
      :options="SEVERITY_OPTIONS"
      option-label="label"
      option-value="value"
      :allow-empty="false"
      @update:model-value="filtersStore.setSeverity"
    />
  </div>
</template>

<script setup lang="ts">
import SelectButton from 'primevue/selectbutton'
import { useFiltersStore } from '@/store/filters'
import { SEVERITY_OPTIONS } from '@/constants/filters'

const filtersStore = useFiltersStore()
</script>

<style scoped>
.item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
