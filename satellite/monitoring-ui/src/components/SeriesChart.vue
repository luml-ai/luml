<template>
  <apexchart type="area" height="180" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Series } from '@/api/types'

const props = withDefaults(defineProps<{ series: Series; color?: string }>(), { color: '#2673fd' })

const chartSeries = computed(() => [
  {
    name: props.series.label,
    data: props.series.points.map((point) => [new Date(point.t).getTime(), point.value]),
  },
])

const isRatio = computed(() => props.series.unit === 'ratio')

const options = computed(() => ({
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: 'inherit',
    sparkline: { enabled: false },
  },
  colors: [props.color],
  dataLabels: { enabled: false },
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
    labels: {
      style: { colors: '#94a3b8', fontSize: '11px' },
      formatter: (value: number) =>
        value == null
          ? ''
          : isRatio.value
            ? `${(value * 100).toFixed(1)}%`
            : `${Math.round(value)}`,
    },
  },
  tooltip: { x: { format: 'dd MMM HH:mm' } },
}))
</script>
