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
        aria-label="Auto-refresh"
        @update:model-value="filtersStore.setAutoRefresh"
      />
      <Button
        class="refresh-button"
        severity="secondary"
        variant="outlined"
        aria-label="Refresh"
        @click="onRefresh"
      >
        <RotateCcw
          :size="16"
          class="refresh-icon"
          :class="{ spinning: isTurnInProgress }"
          @animationiteration="isTurnInProgress = filtersStore.isLoading"
        />
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import SelectButton from 'primevue/selectbutton'
import Button from 'primevue/button'
import { RotateCcw } from 'lucide-vue-next'
import { useFiltersStore } from '@/store/filters'
import { AUTO_REFRESH_OPTIONS } from '@/constants/filters'

const filtersStore = useFiltersStore()

const isTurnInProgress = ref(false)

function onRefresh() {
  isTurnInProgress.value = true
  filtersStore.refresh()
}
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
  background-color: var(--p-togglebutton-content-checked-background);
  border-color: var(--p-togglebutton-content-checked-border-color);
  color: var(--p-togglebutton-content-checked-color);
}

.refresh-icon.spinning {
  animation: refresh-spin 0.5s linear infinite;
}

@keyframes refresh-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(-360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .refresh-icon.spinning {
    animation: none;
  }
}
</style>
