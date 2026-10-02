<template>
  <apexchart type="area" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { chartGridColor, chartTooltipTheme } from '@/lib/theme'
import { formatChartNumber } from '@/lib/format'
import type { Series } from '@/api/types'

const props = withDefaults(
  defineProps<{ series: Series; color?: string; threshold?: number; height?: number | string }>(),
  { color: '#2673fd', threshold: undefined, height: 180 },
)

const hasBaseline = computed(() => (props.series.baseline?.length ?? 0) > 0)

const chartSeries = computed(() => {
  const main = {
    name: props.series.label,
    data: props.series.points.map((point) => [new Date(point.t).getTime(), point.value]),
  }
  if (!hasBaseline.value) return [main]
  // The comparison period, already shifted onto this window's axis by the server.
  return [
    main,
    {
      name: 'Compared period',
      data: (props.series.baseline ?? []).map((point) => [new Date(point.t).getTime(), point.value]),
    },
  ]
})

const isRatio = computed(() => props.series.unit === 'ratio')

// Mostly-null series with isolated points render blank without markers —
// "no data" instead of "one data point".
const measured = computed(() => props.series.points.filter((point) => point.value != null).length)

/**
 * Whether any measurement stands alone, with no measured neighbour to draw a line to.
 *
 * Counting the measurements is not enough: a busy series can still be all gaps — traffic
 * that arrives in short bursts leaves a measured bucket between two empty ones, and each
 * such point is drawn as a line of zero length, which is to say nothing at all.
 */
const hasIsolatedPoints = computed(() => {
  const points = props.series.points
  return points.some(
    (point, index) =>
      point.value != null &&
      points[index - 1]?.value == null &&
      points[index + 1]?.value == null,
  )
})

/**
 * The dot grows with the canvas; the line does not.
 *
 * A line keeps its shape at any size, so 2px reads the same on a card and on the
 * full-screen stage. A dot has no shape to read — it is only as visible as it is big, so it
 * gains a little on a taller canvas. Only a little: what makes an isolated point invisible
 * is not being drawn at all, and past a point a dot stops marking a value and covers it.
 */
const CARD_HEIGHT = 180
const CARD_MARKER_SIZE = 4
const MAX_MARKER_SIZE = 6

const renderedHeight = computed(() => {
  const value = typeof props.height === 'number' ? props.height : parseFloat(props.height)
  return Number.isFinite(value) ? value : CARD_HEIGHT
})

const markerSize = computed(() => {
  if (measured.value === 0) return 0
  if (measured.value > 3 && !hasIsolatedPoints.value) return 0
  const scaled = (CARD_MARKER_SIZE * renderedHeight.value) / CARD_HEIGHT
  return Math.min(MAX_MARKER_SIZE, Math.max(CARD_MARKER_SIZE, Math.round(scaled)))
})

// ApexCharts invents a range for an all-zero series (a flat line labelled up to 200%);
// pin such charts to 0…1%.
const flatZero = computed(
  () =>
    isRatio.value &&
    measured.value > 0 &&
    props.series.points.every((point) => point.value == null || point.value === 0),
)

function formatTick(value: number | null): string {
  return formatChartNumber(value, { percent: isRatio.value })
}

const options = computed(() => ({
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: 'inherit',
    sparkline: { enabled: false },
  },
  colors: hasBaseline.value ? [props.color, '#94a3b8'] : [props.color],
  dataLabels: { enabled: false },
  markers: { size: markerSize.value, strokeWidth: 0, hover: { sizeOffset: 3 } },
  // Baseline: dashed, grey, no fill.
  stroke: hasBaseline.value
    ? { curve: 'smooth', width: [2, 2], dashArray: [0, 5] }
    : { curve: 'smooth', width: 2 },
  fill: hasBaseline.value
    ? { type: ['gradient', 'solid'], gradient: { opacityFrom: 0.25, opacityTo: 0.02 }, opacity: [1, 0] }
    : { type: 'gradient', gradient: { opacityFrom: 0.25, opacityTo: 0.02 } },
  grid: { borderColor: chartGridColor.value, strokeDashArray: 4 },
  xaxis: {
    type: 'datetime',
    axisBorder: { show: false },
    axisTicks: { show: false },
    labels: { style: { colors: '#94a3b8', fontSize: '11px' } },
  },
  yaxis: {
    min: flatZero.value ? 0 : undefined,
    max: flatZero.value ? 0.01 : undefined,
    labels: {
      style: { colors: '#94a3b8', fontSize: '11px' },
      formatter: (value: number) => formatTick(value),
    },
  },
  // Tooltip uses the axis formatting: 0.2%, never 0.200000000000000011.
  tooltip: {
    theme: chartTooltipTheme.value,
    x: { format: 'dd MMM HH:mm' },
    y: { formatter: (value: number | null) => formatTick(value) },
  },
  // The line the metric had to cross to raise its alert.
  annotations: props.threshold
    ? {
        yaxis: [
          {
            y: props.threshold,
            borderColor: '#94a3b8',
            strokeDashArray: 4,
            label: {
              text: 'threshold',
              style: { fontSize: '10px', color: '#64748b', background: 'transparent' },
            },
          },
        ],
      }
    : {},
}))
</script>
