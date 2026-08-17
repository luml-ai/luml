<template>
  <apexchart type="area" height="180" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Series } from '@/api/types'

const props = withDefaults(
  defineProps<{ series: Series; color?: string; threshold?: number }>(),
  { color: '#2673fd', threshold: undefined },
)

const chartSeries = computed(() => [
  {
    name: props.series.label,
    data: props.series.points.map((point) => [new Date(point.t).getTime(), point.value]),
  },
])

const isRatio = computed(() => props.series.unit === 'ratio')

// A bucket with no requests has no latency or error rate, so those series are mostly nulls
// and an isolated measurement has no neighbour to draw a line to. Without a marker such a
// series renders as a blank chart, which reads as "no data" rather than "one data point".
const measured = computed(() => props.series.points.filter((point) => point.value != null).length)
const markerSize = computed(() => (measured.value > 0 && measured.value <= 3 ? 5 : 0))

// A rate that stayed at zero all window has nothing to auto-scale against, and ApexCharts
// then invents a range — a flat "no problems" line came out labelled up to 200%. Pin such
// a chart to 0…1% so it reads as zero, and leave every other series to scale itself.
const flatZero = computed(
  () =>
    isRatio.value &&
    measured.value > 0 &&
    props.series.points.every((point) => point.value == null || point.value === 0),
)

/**
 * Axis labels the eye can read: a rate as a percentage, a count as an integer, and a
 * score like PSI with just enough decimals. Rounding everything to integers collapsed
 * PSI 0.26 to "0"; printing it raw gave 0.29999999999999999.
 */
function formatTick(value: number | null): string {
  if (value == null) return ''
  if (isRatio.value) return `${(value * 100).toFixed(1)}%`
  if (Number.isInteger(value)) return String(value)
  const magnitude = Math.abs(value)
  if (magnitude >= 100) return value.toFixed(0)
  if (magnitude >= 1) return trim(value.toFixed(2))
  return trim(value.toFixed(3))
}

/** 0.250 -> 0.25, 1.50 -> 1.5 */
function trim(text: string): string {
  return text.includes('.') ? text.replace(/0+$/, '').replace(/\.$/, '') : text
}

const options = computed(() => ({
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: 'inherit',
    sparkline: { enabled: false },
  },
  colors: [props.color],
  dataLabels: { enabled: false },
  markers: { size: markerSize.value, strokeWidth: 0, hover: { sizeOffset: 2 } },
  stroke: { curve: 'smooth', width: 2 },
  fill: { type: 'gradient', gradient: { opacityFrom: 0.25, opacityTo: 0.02 } },
  grid: { borderColor: '#e2e8f0', strokeDashArray: 4 },
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
  tooltip: { x: { format: 'dd MMM HH:mm' } },
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
