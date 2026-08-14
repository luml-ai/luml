<template>
  <div class="flex flex-col gap-1.5 py-1">
    <div class="flex items-baseline gap-2.5">
      <span
        class="font-medium tabular-nums leading-none"
        :class="density === 'drawer' ? 'text-4xl' : 'text-3xl'"
      >
        {{ formatMetric(preview.value) }}
      </span>
      <Tag
        v-if="preview.delta !== undefined"
        :severity="deltaSeverity"
        :value="deltaLabel"
        :pt="DELTA_PT"
      />
    </div>
    <span class="inline-flex items-center gap-1 text-sm text-muted-color">
      <component
        :is="preview.higherIsBetter ? ArrowUp : ArrowDown"
        v-tooltip.top="preview.higherIsBetter ? 'higher is better' : 'lower is better'"
        :size="14"
      />
      <span>{{ preview.name }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import { ArrowDown, ArrowUp } from 'lucide-vue-next'
import { formatMetric } from '../model/format'
import type { MetricPreview } from '../model/types'
import type { RenderDensity } from './shared'

const props = defineProps<{
  preview: MetricPreview
  density?: RenderDensity
}>()

const deltaLabel = computed(() => {
  const delta = props.preview.delta ?? 0
  return `${delta > 0 ? '+' : ''}${formatMetric(delta)}`
})

const DELTA_PT = { root: { class: 'px-1.5 py-0 text-sm font-normal' } }

// Coloured by whether the delta is an improvement, not by its sign.
const deltaSeverity = computed<'secondary' | 'success' | 'danger'>(() => {
  const delta = props.preview.delta ?? 0
  if (delta === 0) return 'secondary'
  return (props.preview.higherIsBetter ? delta > 0 : delta < 0) ? 'success' : 'danger'
})
</script>
