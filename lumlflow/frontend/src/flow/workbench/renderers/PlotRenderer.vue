<template>
  <figure v-if="hasPoints" class="flex flex-col gap-1.5 min-w-0">
    <figcaption class="text-sm text-muted-color">{{ preview.title }}</figcaption>
    <MiniChart
      :kind="preview.kind"
      :series="preview.series"
      :x-label="preview.xLabel"
      :y-label="preview.yLabel"
      :height="chartHeight(density)"
    />
  </figure>
  <PreviewShell v-else state="empty" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PlotPreview } from '../model/types'
import MiniChart from './MiniChart.vue'
import PreviewShell from './PreviewShell.vue'
import { chartHeight, type RenderDensity } from './shared'

const props = defineProps<{
  preview: PlotPreview
  density?: RenderDensity
}>()

const hasPoints = computed(() => props.preview.series.some((entry) => entry.points.length > 0))
</script>
