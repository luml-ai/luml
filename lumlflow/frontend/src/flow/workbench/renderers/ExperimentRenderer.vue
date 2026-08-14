<template>
  <div class="flex flex-col gap-2.5 min-w-0">
    <div class="flex items-baseline justify-between gap-3 flex-wrap">
      <span class="font-mono text-base truncate">{{ preview.runName }}</span>
      <a v-if="preview.trackerRef" class="link text-sm whitespace-nowrap" href="/experiments">
        {{ preview.trackerRef }}
      </a>
    </div>

    <div class="flex flex-col gap-1">
      <span
        class="font-medium tabular-nums leading-none"
        :class="density === 'drawer' ? 'text-4xl' : 'text-3xl'"
      >
        {{ formatMetric(preview.mainMetric.value) }}
      </span>
      <span class="inline-flex items-center gap-1 text-sm text-muted-color">
        <component
          :is="preview.mainMetric.higherIsBetter ? ArrowUp : ArrowDown"
          v-tooltip.top="preview.mainMetric.higherIsBetter ? 'higher is better' : 'lower is better'"
          :size="14"
        />
        <span>{{ preview.mainMetric.name }}</span>
      </span>
    </div>

    <div v-if="configChips.length" class="flex flex-wrap gap-1.5">
      <span
        v-for="chip in configChips"
        :key="chip"
        class="font-mono text-sm px-1.5 py-0.5 rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800"
      >
        {{ chip }}
      </span>
    </div>

    <MiniChart
      v-if="curveSeries.length"
      kind="line"
      :series="curveSeries"
      :height="chartHeight(density)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown, ArrowUp } from 'lucide-vue-next'
import { formatMetric } from '../model/format'
import type { ExperimentPreview } from '../model/types'
import MiniChart from './MiniChart.vue'
import { chartHeight, formatParam, type RenderDensity } from './shared'

const props = defineProps<{
  preview: ExperimentPreview
  density?: RenderDensity
}>()

const configChips = computed(() =>
  Object.entries(props.preview.config).map(([key, value]) => `${key}=${formatParam(value)}`),
)

const curveSeries = computed(() =>
  props.preview.curves
    .filter((curve) => curve.points.length > 0)
    .map((curve) => ({ label: curve.name, points: curve.points })),
)
</script>
