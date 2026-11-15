<template>
  <div class="item">
    <span class="label">Refresh:</span>
    <div class="controls">
      <SelectButton
        :model-value="filtersStore.autoRefresh"
        :options="AUTO_REFRESH_OPTIONS"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        @update:model-value="filtersStore.setAutoRefresh"
      />
      <Button
        class="refresh-button"
        severity="secondary"
        variant="outlined"
        aria-label="Refresh"
        @click="filtersStore.refresh"
      >
        <RotateCcw :size="16" />
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import SelectButton from 'primevue/selectbutton'
import Button from 'primevue/button'
import { RotateCcw } from 'lucide-vue-next'
import { useFiltersStore } from '@/store/filters'
import { AUTO_REFRESH_OPTIONS } from '@/constants/filters'

const filtersStore = useFiltersStore()
</script>

<style scoped>
.item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.refresh-button {
  padding: 10px;
  background-color: var(--p-surface-0);
  border-color: var(--p-surface-200);
  color: var(--p-surface-600);
}
</style>
