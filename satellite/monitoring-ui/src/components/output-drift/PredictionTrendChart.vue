<template>
  <apexchart type="rangeArea" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { chartGridColor, chartTextColor, chartTooltipTheme } from '@/lib/theme'
import type { Series } from '@/api/types'

/**
 * The prediction trend the design draws: the median line inside its p05–p95 band.
 *
 * A range-area series carries the band, plain lines carry the median and the mean —
 * one chart, so the eye reads "where predictions sit and how wide they spread" at once.
 */
const props = withDefaults(
  defineProps<{ trend: Series[]; height?: number | string }>(),
  { height: 230 },
)

function series(key: string): Series | undefined {
  return props.trend.find((entry) => entry.key === `prediction_${key}`)
}

const chartSeries = computed(() => {
  const p05 = series('p05')
  const p95 = series('p95')
  const median = series('median')
  const mean = series('mean')
  const result: object[] = []
  if (p05 && p95) {
    result.push({
      name: 'p05–p95',
      type: 'rangeArea',
      data: p05.points.map((point, index) => ({
        x: new Date(point.t).getTime(),
        y: [point.value, p95.points[index]?.value ?? null],
      })),
    })
  }
  for (const [entry, name] of [
    [median, 'Median'],
    [mean, 'Mean'],
  ] as const) {
    if (entry) {
      result.push({
        name,
        type: 'line',
        // {x, y} objects: ApexCharts refuses tuples mixed with range data in one combo chart.
        data: entry.points.map((point) => ({
          x: new Date(point.t).getTime(),
          y: point.value,
        })),
      })
    }
  }
  return result
})

/** Axis labels the eye can read: large predictions compact, small ones trimmed. */
function formatTick(value: number | null): string {
  if (value == null) return ''
  const magnitude = Math.abs(value)
  if (magnitude >= 10000) {
    return new Intl.NumberFormat('en-US', { notation: 'compact' }).format(value)
  }
  if (Number.isInteger(value)) return String(value)
  if (magnitude >= 1) return value.toFixed(1)
  return value.toFixed(3)
}

const options = computed(() => ({
  chart: { toolbar: { show: false }, zoom: { enabled: false }, fontFamily: 'inherit', foreColor: chartTextColor.value },
  colors: ['#bfdbfe', '#2673fd', '#94a3b8'],
  dataLabels: { enabled: false },
  // the band must stay 'straight': a smoothed range can cross its own bounds
  stroke: { curve: ['straight', 'smooth', 'smooth'], width: [0, 2, 2], dashArray: [0, 0, 4] },
  fill: { opacity: [0.55, 1, 1] },
  legend: { position: 'top', horizontalAlign: 'right', fontSize: '12px' },
  grid: { borderColor: chartGridColor.value, strokeDashArray: 4 },
  xaxis: {
    type: 'datetime',
    axisBorder: { show: false },
    axisTicks: { show: false },
    labels: { style: { colors: '#94a3b8', fontSize: '11px' } },
  },
  yaxis: {
    labels: {
      style: { colors: '#94a3b8', fontSize: '11px' },
      formatter: (value: number) => formatTick(value),
    },
  },
  tooltip: {
    theme: chartTooltipTheme.value,
    x: { format: 'dd MMM HH:mm' },
    y: { formatter: (value: number | null) => formatTick(value) },
  },
}))
</script>
