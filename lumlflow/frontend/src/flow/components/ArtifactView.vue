<template>
  <div class="text-sm">
    <div v-if="value.type === 'frame'" class="overflow-x-auto">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-surface-200 dark:border-surface-700">
            <th
              v-for="(column, index) in value.columns"
              :key="column"
              class="py-1 pr-4 font-medium whitespace-nowrap"
            >
              {{ column }}
              <span class="block text-xs text-muted-color font-normal">{{ value.dtypes[index] }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, rowIndex) in value.rows"
            :key="rowIndex"
            class="border-b border-surface-100 dark:border-surface-800"
          >
            <td v-for="(cell, cellIndex) in row" :key="cellIndex" class="py-1 pr-4 whitespace-nowrap">
              {{ cell ?? '—' }}
            </td>
          </tr>
        </tbody>
      </table>
      <p class="text-xs text-muted-color mt-2">
        {{ value.rows.length }} of {{ value.totalRows.toLocaleString() }} rows
      </p>
    </div>

    <div v-else-if="value.type === 'plot'">
      <p class="text-xs text-muted-color mb-1">{{ value.title }}</p>
      <svg :viewBox="`0 0 ${plotWidth} ${plotHeight}`" class="w-full h-32">
        <line
          :x1="padding"
          :y1="plotHeight - padding"
          :x2="plotWidth - padding"
          :y2="plotHeight - padding"
          class="stroke-surface-300 dark:stroke-surface-600"
          stroke-width="1"
        />
        <template v-for="(series, seriesIndex) in value.series" :key="series.label">
          <polyline
            v-if="value.kind === 'line'"
            :points="polyline(series.points)"
            fill="none"
            :stroke="series.color ?? seriesColor(seriesIndex)"
            stroke-width="1.5"
          />
          <template v-else>
            <rect
              v-for="(point, pointIndex) in series.points"
              :key="pointIndex"
              :x="scaleX(point[0]) - barWidth(series.points.length) / 2"
              :y="scaleY(point[1])"
              :width="barWidth(series.points.length)"
              :height="Math.max(0, plotHeight - padding - scaleY(point[1]))"
              :fill="series.color ?? seriesColor(seriesIndex)"
              opacity="0.85"
            />
          </template>
        </template>
      </svg>
      <p class="text-xs text-muted-color">{{ value.xLabel }} · {{ value.yLabel }}</p>
    </div>

    <div v-else-if="value.type === 'note'" class="leading-relaxed whitespace-pre-wrap">
      {{ value.markdown }}
    </div>

    <dl v-else-if="value.type === 'model'" class="grid grid-cols-2 gap-x-4 gap-y-1">
      <dt class="text-muted-color">flavor</dt>
      <dd>{{ value.flavor }}</dd>
      <dt class="text-muted-color">parameters</dt>
      <dd>{{ value.paramCount.toLocaleString() }}</dd>
      <dt class="text-muted-color">size</dt>
      <dd>{{ (value.sizeBytes / 1024).toFixed(0) }} KB</dd>
      <dt class="text-muted-color">signature</dt>
      <dd class="font-mono text-xs">{{ value.signature }}</dd>
    </dl>

    <div v-else-if="value.type === 'experiment'" class="flex flex-col gap-4">
      <p class="font-medium">{{ value.runName }}</p>
      <div class="flex flex-wrap gap-x-8 gap-y-3">
        <div v-for="(metric, name) in value.finalMetrics" :key="name">
          <p class="text-2xl font-medium tabular-nums leading-tight">{{ metric.toFixed(3) }}</p>
          <p class="text-xs text-muted-color mt-0.5">{{ name }}</p>
        </div>
      </div>
      <div class="grid gap-x-6 gap-y-4" :class="value.curves.length > 1 ? 'grid-cols-2' : ''">
        <MetricCurve
          v-for="(series, index) in value.curves"
          :key="series.name"
          :name="series.name"
          :points="series.points"
          :color="seriesColor(index)"
        />
      </div>
    </div>

    <div v-else-if="value.type === 'eval'" class="flex flex-col gap-4">
      <div class="flex flex-wrap gap-x-8 gap-y-3">
        <div v-for="(score, name) in value.scores" :key="name">
          <p class="text-2xl font-medium tabular-nums leading-tight">{{ score.toFixed(3) }}</p>
          <p class="text-xs text-muted-color mt-0.5">{{ name }}</p>
        </div>
      </div>
      <p class="text-xs text-muted-color">
        {{ value.sampleCount.toLocaleString() }} samples · {{ value.datasetRef }}
      </p>
      <div v-if="value.traces.length" class="flex flex-col gap-2">
        <div
          v-for="trace in value.traces.slice(0, 3)"
          :key="trace.sampleId"
          class="rounded-lg border border-surface-200 dark:border-surface-700 px-3 py-2"
        >
          <p class="text-xs text-muted-color">{{ trace.prompt }}</p>
          <p class="text-xs mt-1">{{ trace.output }}</p>
          <p class="text-xs text-muted-color mt-1 tabular-nums">
            score {{ trace.score.toFixed(2) }} · {{ trace.latencyMs }} ms
          </p>
        </div>
      </div>
    </div>

    <div v-else-if="value.type === 'metric'">
      <p class="text-2xl font-medium tabular-nums leading-tight">{{ value.value.toFixed(4) }}</p>
      <p class="text-xs text-muted-color mt-0.5">{{ value.name }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MetricCurve from './MetricCurve.vue'
import type { ArtifactValue } from '../types'

const props = defineProps<{ value: ArtifactValue }>()

const plotWidth = 240
const plotHeight = 90
const padding = 8

const points = computed(() =>
  props.value.type === 'plot' ? props.value.series.flatMap((series) => series.points) : [],
)

const bounds = computed(() => {
  if (!points.value.length) return { minX: 0, maxX: 1, minY: 0, maxY: 1 }
  const xs = points.value.map((point) => point[0])
  const ys = points.value.map((point) => point[1])
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs) || 1,
    minY: Math.min(0, ...ys),
    maxY: Math.max(...ys) || 1,
  }
})

const scaleX = (x: number): number => {
  const { minX, maxX } = bounds.value
  const span = maxX - minX || 1
  return padding + ((x - minX) / span) * (plotWidth - padding * 2)
}

const scaleY = (y: number): number => {
  const { minY, maxY } = bounds.value
  const span = maxY - minY || 1
  return plotHeight - padding - ((y - minY) / span) * (plotHeight - padding * 2)
}

const polyline = (series: [number, number][]): string =>
  series.map(([x, y]) => `${scaleX(x)},${scaleY(y)}`).join(' ')

const barWidth = (count: number): number => Math.max(4, (plotWidth - padding * 2) / (count * 1.6))

// Fixed assignment order, validated for adjacent-pair CVD separation — do not
// reorder without re-running the palette check.
const palette = ['#2563eb', '#d97706', '#0d9488', '#dc2626', '#7c3aed']
const seriesColor = (index: number): string => palette[index % palette.length]
</script>
