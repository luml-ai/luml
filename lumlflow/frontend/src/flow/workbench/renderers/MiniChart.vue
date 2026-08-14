<template>
  <div class="flex flex-col gap-1 min-w-0">
    <svg :viewBox="`0 0 ${WIDTH} ${height}`" class="w-full" role="img">
      <line
        v-for="tick in yTicks"
        :key="`grid-${tick}`"
        :x1="padLeft"
        :x2="WIDTH - PAD_R"
        :y1="scaleY(tick)"
        :y2="scaleY(tick)"
        class="stroke-surface-200 dark:stroke-surface-700"
        stroke-width="1"
      />
      <line
        :x1="padLeft"
        :x2="WIDTH - PAD_R"
        :y1="height - padBottom"
        :y2="height - padBottom"
        class="stroke-surface-300 dark:stroke-surface-600"
        stroke-width="1"
      />
      <line
        :x1="padLeft"
        :x2="padLeft"
        :y1="PAD_T"
        :y2="height - padBottom"
        class="stroke-surface-300 dark:stroke-surface-600"
        stroke-width="1"
      />

      <text
        v-for="tick in yTicks"
        :key="`ylab-${tick}`"
        :x="padLeft - 5"
        :y="scaleY(tick) + 3"
        text-anchor="end"
        class="text-sm text-muted-color"
        fill="currentColor"
      >
        {{ formatMetric(tick) }}
      </text>
      <text
        :x="padLeft"
        :y="height - padBottom + 11"
        text-anchor="start"
        class="text-sm text-muted-color"
        fill="currentColor"
      >
        {{ formatMetric(bounds.minX) }}
      </text>
      <text
        :x="WIDTH - PAD_R"
        :y="height - padBottom + 11"
        text-anchor="end"
        class="text-sm text-muted-color"
        fill="currentColor"
      >
        {{ formatMetric(bounds.maxX) }}
      </text>

      <text
        v-if="xLabel"
        :x="padLeft + plotWidth / 2"
        :y="height - 3"
        text-anchor="middle"
        class="text-sm text-muted-color"
        fill="currentColor"
      >
        {{ xLabel }}
      </text>
      <text
        v-if="yLabel"
        :transform="`rotate(-90 9 ${PAD_T + plotHeight / 2})`"
        x="9"
        :y="PAD_T + plotHeight / 2"
        text-anchor="middle"
        class="text-sm text-muted-color"
        fill="currentColor"
      >
        {{ yLabel }}
      </text>

      <template v-for="(entry, seriesIndex) in series" :key="entry.label">
        <polyline
          v-if="kind === 'line'"
          :points="polyline(entry.points)"
          fill="none"
          :stroke="colorOf(entry, seriesIndex)"
          stroke-width="1.8"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
        <template v-else-if="kind === 'scatter'">
          <circle
            v-for="(point, pointIndex) in entry.points"
            :key="pointIndex"
            :cx="scaleX(point[0])"
            :cy="scaleY(point[1])"
            r="2.5"
            :fill="colorOf(entry, seriesIndex)"
            opacity="0.85"
          />
        </template>
        <template v-else>
          <rect
            v-for="(point, pointIndex) in entry.points"
            :key="pointIndex"
            :x="barX(point[0], seriesIndex)"
            :y="Math.min(scaleY(point[1]), scaleY(0))"
            :width="barWidth"
            :height="Math.abs(scaleY(point[1]) - scaleY(0))"
            :fill="colorOf(entry, seriesIndex)"
            opacity="0.85"
          />
        </template>
      </template>
    </svg>

    <div v-if="series.length > 1" class="flex flex-wrap gap-x-4 gap-y-1 pl-1">
      <span
        v-for="(entry, seriesIndex) in series"
        :key="entry.label"
        class="inline-flex items-center gap-1.5 text-sm text-muted-color"
      >
        <span
          class="w-2.5 h-1 rounded-full shrink-0"
          :style="{ background: colorOf(entry, seriesIndex) }"
        />
        <span class="font-mono">{{ entry.label }}</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatMetric } from '../model/format'
import { seriesColor } from './shared'

interface ChartSeries {
  label: string
  points: [number, number][]
  color?: string
}

const props = defineProps<{
  kind: 'line' | 'scatter' | 'bar' | 'hist'
  series: ChartSeries[]
  xLabel?: string
  yLabel?: string
  height?: number
}>()

const WIDTH = 420
const PAD_R = 10
const PAD_T = 10

const height = computed(() => props.height ?? 150)
const padLeft = computed(() => (props.yLabel ? 46 : 36))
const padBottom = computed(() => (props.xLabel ? 32 : 22))
const plotWidth = computed(() => WIDTH - padLeft.value - PAD_R)
const plotHeight = computed(() => height.value - PAD_T - padBottom.value)

const isBars = computed(() => props.kind === 'bar' || props.kind === 'hist')

const pointCount = computed(() => Math.max(...props.series.map((entry) => entry.points.length), 1))

const bounds = computed(() => {
  const points = props.series.flatMap((entry) => entry.points)
  if (!points.length) return { minX: 0, maxX: 1, minY: 0, maxY: 1 }
  const xs = points.map(([x]) => x)
  const ys = points.map(([, y]) => y)
  const minX = Math.min(...xs)
  let maxX = Math.max(...xs)
  let minY = Math.min(...ys)
  let maxY = Math.max(...ys)
  if (isBars.value) minY = Math.min(0, minY)
  if (minX === maxX) maxX = minX + 1
  if (minY === maxY) maxY = minY + 1
  return { minX, maxX, minY, maxY }
})

// Bars are centered on their x value, so the domain grows by half a slot on
// each side to keep edge bars inside the plot.
const xDomain = computed(() => {
  const { minX, maxX } = bounds.value
  if (!isBars.value) return { minX, maxX }
  const step = pointCount.value > 1 ? (maxX - minX) / (pointCount.value - 1) : 1
  return { minX: minX - step / 2, maxX: maxX + step / 2 }
})

const scaleX = (x: number): number => {
  const { minX, maxX } = xDomain.value
  return padLeft.value + ((x - minX) / (maxX - minX || 1)) * plotWidth.value
}

const scaleY = (y: number): number => {
  const { minY, maxY } = bounds.value
  return height.value - padBottom.value - ((y - minY) / (maxY - minY || 1)) * plotHeight.value
}

const yTicks = computed(() => {
  const { minY, maxY } = bounds.value
  return [minY, (minY + maxY) / 2, maxY]
})

const barWidth = computed(() => {
  const slot = plotWidth.value / pointCount.value
  const groupWidth = slot * (props.kind === 'hist' ? 0.96 : 0.7)
  return Math.max(1.5, groupWidth / props.series.length)
})

const barX = (x: number, seriesIndex: number): number =>
  scaleX(x) - (barWidth.value * props.series.length) / 2 + seriesIndex * barWidth.value

const polyline = (points: [number, number][]): string =>
  points.map(([x, y]) => `${scaleX(x)},${scaleY(y)}`).join(' ')

const colorOf = (entry: ChartSeries, index: number): string => entry.color ?? seriesColor(index)
</script>
