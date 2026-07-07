<template>
  <apexchart type="scatter" height="260" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PcaPoint } from '@/api/types'

const props = defineProps<{ reference: PcaPoint[]; current: PcaPoint[] }>()

function toXy(points: PcaPoint[]): [number, number][] {
  return points.map((p) => [p.x, p.y])
}

const chartSeries = computed(() => [
  { name: 'Reference (training)', data: toXy(props.reference) },
  { name: 'Logged (current window)', data: toXy(props.current) },
])

const options = computed(() => ({
  chart: { toolbar: { show: false }, zoom: { enabled: false }, fontFamily: 'inherit' },
  colors: ['#94a3b8', '#2673fd'],
  legend: { position: 'top', horizontalAlign: 'right', fontSize: '12px' },
  grid: { borderColor: '#e2e8f0', strokeDashArray: 4 },
  markers: { size: 5, strokeWidth: 0, fillOpacity: 0.7 },
  xaxis: {
    type: 'numeric',
    tickAmount: 6,
    title: { text: 'PC1', style: { color: '#94a3b8', fontSize: '11px', fontWeight: 400 } },
    labels: {
      style: { colors: '#94a3b8', fontSize: '11px' },
      formatter: (value: number) => (value == null ? '' : Number(value).toFixed(1)),
    },
  },
  yaxis: {
    title: { text: 'PC2', style: { color: '#94a3b8', fontSize: '11px', fontWeight: 400 } },
    labels: {
      style: { colors: '#94a3b8', fontSize: '11px' },
      formatter: (value: number) => (value == null ? '' : Number(value).toFixed(1)),
    },
  },
}))
</script>
