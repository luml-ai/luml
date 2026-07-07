<template>
  <apexchart type="bar" height="230" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeatureDistribution } from '@/api/types'

const props = defineProps<{ distribution: FeatureDistribution }>()

const chartSeries = computed(() => [
  { name: 'Reference', data: props.distribution.bins.map((b) => b.reference ?? 0) },
  { name: 'Current', data: props.distribution.bins.map((b) => b.current ?? 0) },
])

const options = computed(() => ({
  chart: { toolbar: { show: false }, fontFamily: 'inherit' },
  colors: ['#94a3b8', '#2673fd'],
  dataLabels: { enabled: false },
  legend: { position: 'top', horizontalAlign: 'right', fontSize: '12px' },
  plotOptions: { bar: { columnWidth: '68%', borderRadius: 3 } },
  grid: { borderColor: '#e2e8f0', strokeDashArray: 4 },
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
  tooltip: { y: { formatter: (value: number) => `${(value * 100).toFixed(1)}%` } },
}))
</script>
