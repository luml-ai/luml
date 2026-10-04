<template>
  <apexchart type="rangeArea" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { chartGridColor, chartTextColor, chartSeriesColors, chartTooltipTheme } from '@/lib/theme'
import { formatChartNumber } from '@/lib/format'
import { CHART_HEIGHT, CHART_LEGEND, CHART_GRID_PADDING } from '@/lib/charts'
import type { Series } from '@/api/types'

/**
 * The prediction trend the design draws: the median line inside its p05–p95 band.
 *
 * A range-area series carries the band, plain lines carry the median and the mean —
 * one chart, so the eye reads "where predictions sit and how wide they spread" at once.
 */
const props = withDefaults(defineProps<{ trend: Series[]; height?: number | string }>(), {
  height: CHART_HEIGHT,
})

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

function formatTick(value: number | null): string {
  return formatChartNumber(value, { compact: true })
}

const options = computed(() => ({
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: 'inherit',
    foreColor: chartTextColor.value,
  },
  colors: [chartSeriesColors.value[0], chartSeriesColors.value[0], chartTextColor.value],
  dataLabels: { enabled: false },
  // the band must stay 'straight': a smoothed range can cross its own bounds
  stroke: { curve: ['straight', 'smooth', 'smooth'], width: [0, 2, 2], dashArray: [0, 0, 4] },
  fill: { opacity: [0.55, 1, 1] },
  legend: CHART_LEGEND,
  grid: { borderColor: chartGridColor.value, strokeDashArray: 4, padding: CHART_GRID_PADDING },
  xaxis: {
    type: 'datetime',
    axisBorder: { show: false },
    axisTicks: { show: false },
    labels: { style: { colors: chartTextColor.value, fontSize: '11px' } },
  },
  yaxis: {
    labels: {
      style: { colors: chartTextColor.value, fontSize: '11px' },
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
