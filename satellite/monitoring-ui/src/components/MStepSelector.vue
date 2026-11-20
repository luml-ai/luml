<template>
  <div class="step-selector">
    <span class="label">Step:</span>
    <SelectButton
      :model-value="filtersStore.granularity"
      :options="GRANULARITY_OPTIONS"
      option-label="label"
      option-value="value"
      :allow-empty="false"
      @update:model-value="filtersStore.setGranularity"
    />
  </div>
</template>

<script setup lang="ts">
import SelectButton from 'primevue/selectbutton'
import { useFiltersStore } from '@/store/filters'
import { GRANULARITY_OPTIONS } from '@/constants/filters'

const filtersStore = useFiltersStore()
</script>

<style scoped>
.step-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 14px;
  line-height: 21px;
  color: var(--p-text-color);
}
</style>
