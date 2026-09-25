<template>
  <div
    class="flex flex-col gap-2.5 min-w-0"
    :class="preview.tracker && preview.tracker.state !== 'ok' ? 'opacity-60' : ''"
  >
    <div class="flex items-baseline justify-between gap-3 flex-wrap">
      <span class="font-mono text-base truncate">{{ preview.runName }}</span>
      <span v-if="preview.tracker?.url" class="flex items-center gap-2 whitespace-nowrap">
        <RouterLink class="link text-sm" :to="preview.tracker.url">open in Experiments</RouterLink>
        <!-- Upload takes the tracker record straight from the card; no detour through Experiments. -->
        <TrackerUploadLink
          v-if="preview.tracker.state === 'ok'"
          :experiment-id="preview.tracker.id"
        />
      </span>
      <TrackerStateBadge v-else-if="preview.tracker" :state="preview.tracker.state" />
    </div>

    <div v-if="preview.mainMetric" class="flex flex-col gap-1">
      <span class="text-sm text-muted-color">metrics</span>
      <span
        class="font-medium tabular-nums leading-none"
        :class="density === 'drawer' ? 'text-4xl' : 'text-3xl'"
      >
        {{ formatMetric(preview.mainMetric.value) }}
      </span>
      <span class="text-sm text-muted-color">{{ preview.mainMetric.name }}</span>
    </div>
    <p v-else class="text-sm text-muted-color">no metrics recorded</p>

    <div v-if="preview.metrics.length" class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
      <template v-for="metric in preview.metrics" :key="metric.name">
        <span class="font-mono text-muted-color">{{ metric.name }}</span>
        <span class="font-mono tabular-nums">{{ formatMetric(metric.value) }}</span>
      </template>
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
import { RouterLink } from 'vue-router'
import { formatMetric } from '../model/format'
import type { ExperimentPreview } from '../model/types'
import TrackerStateBadge from '../ui/TrackerStateBadge.vue'
import MiniChart from './MiniChart.vue'
import TrackerUploadLink from '../ui/TrackerUploadLink.vue'
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
