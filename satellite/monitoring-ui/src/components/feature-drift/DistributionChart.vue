<template>
  <apexchart type="bar" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { chartGridColor, chartTextColor, chartSeriesColors, chartTooltipTheme } from '@/lib/theme'
import { formatChartNumber } from '@/lib/format'
import type { FeatureDistribution } from '@/api/types'

const props = withDefaults(
  defineProps<{ distribution: FeatureDistribution; height?: number | string }>(),
  { height: 230 },
)

const chartSeries = computed(() => [
  { name: 'Reference', data: props.distribution.bins.map((b) => b.reference ?? 0) },
  { name: 'Current', data: props.distribution.bins.map((b) => b.current ?? 0) },
])

function formatShare(value: number | null): string {
  return formatChartNumber(value, { percent: true })
}

const options = computed(() => ({
  chart: { toolbar: { show: false }, fontFamily: 'inherit', foreColor: chartTextColor.value },
  colors: [chartTextColor.value, chartSeriesColors.value[0]],
  dataLabels: { enabled: false },
  legend: { position: 'top', horizontalAlign: 'right', fontSize: '12px' },
  plotOptions: { bar: { columnWidth: '68%', borderRadius: 3 } },
  grid: { borderColor: chartGridColor.value, strokeDashArray: 4 },
  xaxis: {
    categories: props.distribution.bins.map(({ label }) => {
      if (props.distribution.kind !== 'numeric') return label
      const edges = label.split('–')
      if (edges.length !== 2 || edges.some((edge) => !edge.trim() || !Number.isFinite(Number(edge)))) {
        return label
      }
      return edges.map((edge) => formatChartNumber(Number(edge))).join('–')
    }),
    labels: {
      style: { colors: chartTextColor.value, fontSize: '11px' },
      rotate: 0,
      hideOverlappingLabels: true,
    },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: {
    labels: {
      style: { colors: chartTextColor.value, fontSize: '11px' },
      formatter: formatShare,
    },
  },
  tooltip: { theme: chartTooltipTheme.value, y: { formatter: formatShare } },
}))
</script>
