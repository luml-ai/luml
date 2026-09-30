<template>
  <apexchart type="bar" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { chartGridColor, chartTextColor, chartTooltipTheme } from '@/lib/theme'
import type { FeatureDistribution } from '@/api/types'

const props = withDefaults(
  defineProps<{ distribution: FeatureDistribution; height?: number | string }>(),
  { height: 230 },
)

const chartSeries = computed(() => [
  { name: 'Reference', data: props.distribution.bins.map((b) => b.reference ?? 0) },
  { name: 'Current', data: props.distribution.bins.map((b) => b.current ?? 0) },
])

const options = computed(() => ({
  chart: { toolbar: { show: false }, fontFamily: 'inherit', foreColor: chartTextColor.value },
  colors: ['#94a3b8', '#2673fd'],
  dataLabels: { enabled: false },
  legend: { position: 'top', horizontalAlign: 'right', fontSize: '12px' },
  plotOptions: { bar: { columnWidth: '68%', borderRadius: 3 } },
  grid: { borderColor: chartGridColor.value, strokeDashArray: 4 },
  xaxis: {
    categories: props.distribution.bins.map((b) => b.label),
    labels: {
      style: { colors: '#94a3b8', fontSize: '11px' },
      rotate: 0,
      hideOverlappingLabels: true,
    },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: {
    labels: {
      style: { colors: '#94a3b8', fontSize: '11px' },
      formatter: (value: number) => (value == null ? '' : `${(value * 100).toFixed(0)}%`),
    },
  },
  tooltip: { theme: chartTooltipTheme.value, y: { formatter: (value: number) => `${(value * 100).toFixed(1)}%` } },
}))
</script>
