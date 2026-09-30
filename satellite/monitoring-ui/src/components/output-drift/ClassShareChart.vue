<template>
  <apexchart type="line" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { chartGridColor, chartTooltipTheme } from '@/lib/theme'
import { formatChartNumber } from '@/lib/format'
import type { Series } from '@/api/types'

/** Each drifted class's live share across the windows — one line per class. */
const props = withDefaults(
  defineProps<{ series: Series[]; height?: number | string }>(),
  { height: 230 },
)

// Isolated points need markers, same as the runtime series.
const measured = computed(() =>
  Math.max(0, ...props.series.map((entry) => entry.points.filter((p) => p.value != null).length)),
)
const markerSize = computed(() => (measured.value > 0 && measured.value <= 3 ? 4 : 0))

const chartSeries = computed(() =>
  props.series.map((entry) => ({
    name: entry.label,
    data: entry.points.map((point) => ({
      x: new Date(point.t).getTime(),
      y: point.value,
    })),
  })),
)

function formatShare(value: number | null): string {
  return formatChartNumber(value, { percent: true })
}

const options = computed(() => ({
  chart: { toolbar: { show: false }, zoom: { enabled: false }, fontFamily: 'inherit' },
  colors: ['#2673fd', '#f97316', '#a855f7', '#059669', '#e11d48', '#64748b'],
  dataLabels: { enabled: false },
  stroke: { curve: 'smooth', width: 2 },
  markers: { size: markerSize.value, strokeWidth: 0, hover: { sizeOffset: 3 } },
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
      formatter: formatShare,
    },
  },
  tooltip: {
    theme: chartTooltipTheme.value,
    x: { format: 'dd MMM HH:mm' },
    y: { formatter: formatShare },
  },
}))
</script>
