<template>
  <div class="item">
    <Button
      class="compare-button"
      :class="{ active: filtersStore.isCompareActive }"
      severity="secondary"
      variant="outlined"
      @click="comparePopover?.toggle($event)"
    >
      <Repeat :size="14" />
      <span>Compare</span>
    </Button>
    <Popover
      ref="comparePopover"
      :dt="{ content: { padding: '24px' } }"
      @hide="isCustomPending = false"
    >
      <div class="compare-body">
        <span class="compare-title">Select comparison mode</span>
        <SelectButton
          :model-value="selectedMode"
          :options="COMPARE_OPTIONS"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          fluid
          @update:model-value="onModeChange"
        />
        <MDateRangeForm
          v-if="selectedMode === Compare.CUSTOM"
          :start="filtersStore.compareStart"
          :end="filtersStore.compareEnd"
          @apply="onApply"
        />
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import SelectButton from 'primevue/selectbutton'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import { Repeat } from 'lucide-vue-next'
import { Compare } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import { COMPARE_OPTIONS } from '@/constants/filters'
import MDateRangeForm from './MDateRangeForm.vue'

const filtersStore = useFiltersStore()

const comparePopover = useTemplateRef<InstanceType<typeof Popover>>('comparePopover')

const isCustomPending = ref(false)

const selectedMode = computed(() => (isCustomPending.value ? Compare.CUSTOM : filtersStore.compare))

function onModeChange(value: Compare) {
  isCustomPending.value = value === Compare.CUSTOM
  if (value !== Compare.CUSTOM) filtersStore.setCompare(value)
}

function onApply({ start, end }: { start: Date; end: Date }) {
  filtersStore.setCompareRange(start, end)
  isCustomPending.value = false
  comparePopover.value?.hide()
}
</script>
<style scoped>
.item {
  display: flex;
  flex-direction: column;
}

.compare-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background-color: var(--p-surface-0);
  border-color: var(--p-surface-200);
  color: var(--p-surface-600);
}

.compare-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 290px;
}

.compare-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.compare-button.active {
  background: var(--p-button-outlined-secondary-active-background);
  border-color: var(--p-button-outlined-secondary-border-color);
  color: var(--p-button-outlined-secondary-color);
}
</style>
