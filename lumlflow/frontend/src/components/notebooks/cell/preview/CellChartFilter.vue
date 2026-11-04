<template>
  <Button
    v-tooltip.top="'Choose metrics'"
    variant="outlined"
    severity="secondary"
    class="section-action"
    aria-label="Choose metrics"
    @click="open"
  >
    <template #icon>
      <Settings2 :size="14" />
    </template>
  </Button>
  <Popover ref="popover" :pt="POPOVER_WITHOUT_ARROW_PT" class="nowheel nodrag">
    <div class="filter">
      <ul class="filter-list">
        <li v-for="(metric, index) in metrics" :key="index" class="filter-row">
          <ToggleSwitch
            :model-value="!draft.has(index)"
            :input-id="`metric-${uid}-${index}`"
            @update:model-value="(on: boolean) => toggle(index, on)"
          />
          <span class="filter-dot" :style="{ background: metric.color }" />
          <label :for="`metric-${uid}-${index}`" class="filter-name">{{ metric.name }}</label>
        </li>
      </ul>
      <Button
        label="Apply"
        size="small"
        class="filter-apply"
        :disabled="draft.size === metrics.length"
        @click="apply"
      />
    </div>
  </Popover>
</template>

<script setup lang="ts">
import type { CellChartFilterProps } from './preview.interface'
import { ref, useId, useTemplateRef } from 'vue'
import { Button, Popover, ToggleSwitch } from 'primevue'
import { Settings2 } from 'lucide-vue-next'
import { POPOVER_WITHOUT_ARROW_PT } from '@/prime-vue/pass-through/popover.pt'

defineProps<CellChartFilterProps>()

const hidden = defineModel<Set<number>>('hidden', { required: true })

const uid = useId()
const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')

const draft = ref(new Set<number>())

function open(event: Event) {
  draft.value = new Set(hidden.value)
  popover.value?.toggle(event)
}

function toggle(index: number, on: boolean) {
  const next = new Set(draft.value)
  if (on) next.delete(index)
  else next.add(index)
  draft.value = next
}

function apply() {
  hidden.value = new Set(draft.value)
  popover.value?.hide()
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.filter {
  @apply flex flex-col gap-3 min-w-48 max-w-72;
}
.filter-list {
  @apply flex flex-col gap-2 max-h-60 overflow-y-auto pr-1;
}
.filter-row {
  @apply flex items-center gap-2 text-sm;
}
.filter-dot {
  @apply w-2 h-2 rounded-full shrink-0;
}
.filter-name {
  @apply truncate cursor-pointer;
}
.filter-apply {
  @apply self-end;
}
</style>
