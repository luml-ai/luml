<template>
  <div class="item">
    <span class="label">Window:</span>
    <div class="controls">
      <SelectButton
        :model-value="filtersStore.activeWindow"
        :options="WINDOW_OPTIONS"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        @update:model-value="filtersStore.setWindow"
      />
      <ToggleButton
        class="custom-button"
        :model-value="filtersStore.isCustomMode"
        :readonly="filtersStore.isCustomMode"
        @click="onCustomClick"
      >
        <CalendarDays :size="16" />
        <span>Custom</span>
      </ToggleButton>
      <Popover
        ref="rangePopover"
        :dt="{ content: { padding: '24px' } }"
        @hide="filtersStore.cancelCustomMode"
      >
        <div class="range">
          <span class="range-title">Select custom period</span>
          <MDateRangeForm
            :start="filtersStore.customStart"
            :end="filtersStore.customEnd"
            @apply="onApply"
          />
        </div>
      </Popover>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useTemplateRef } from 'vue'
import SelectButton from 'primevue/selectbutton'
import ToggleButton from 'primevue/togglebutton'
import Popover from 'primevue/popover'
import { CalendarDays } from 'lucide-vue-next'
import { useFiltersStore } from '@/store/filters'
import { WINDOW_OPTIONS } from '@/constants/filters'
import MDateRangeForm from './MDateRangeForm.vue'

const filtersStore = useFiltersStore()

const rangePopover = useTemplateRef<InstanceType<typeof Popover>>('rangePopover')

function onCustomClick(event: Event) {
  filtersStore.enableCustomMode()
  rangePopover.value?.show(event)
}

function onApply({ start, end }: { start: Date; end: Date }) {
  filtersStore.setCustomRange(start, end)
  rangePopover.value?.hide()
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

.range {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.range-title {
  font-size: 16px;
  font-weight: 500;
}
</style>
