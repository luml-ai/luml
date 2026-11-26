<template>
  <MApexChart type="rangeArea" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ApexOptions } from 'apexcharts'
import type { Series } from '@/api/monitoring/interfaces'
import { getLineChartOptions } from '@/lib/apex-charts'
import { useCssVariables } from '@/composables/useCssVariables'
import { CHART_HEIGHT, CHART_LEGEND_HEIGHT } from '@/constants/charts'
import { PREDICTION_BAND_LABEL, PREDICTION_TREND_KEYS } from '@/constants/output-drift'
import {
  escapeChartLabel,
  formatChartValue,
  formatPreciseValue,
  getChartLegend,
  getMarkerSize,
} from '@/utils/charts'
import { findTrendSeries } from '@/utils/output-drift'
import MApexChart from '@/components/MApexChart.vue'

interface Props {
  trend: Series[]
  height?: number | string
}

const props = withDefaults(defineProps<Props>(), {
  height: CHART_HEIGHT,
})

const { values: cssValues, isDark } = useCssVariables({
  border: '--p-content-border-color',
  grid: '--p-datatable-row-background',
  text: '--p-text-muted-color',
  primary: '--p-primary-color',
})

const band = computed(() => {
  const p05 = findTrendSeries(props.trend, PREDICTION_TREND_KEYS.p05)
  const p95 = findTrendSeries(props.trend, PREDICTION_TREND_KEYS.p95)
  if (!p05 || !p95) return null
  const upper = new Map(p95.points.map((point) => [point.t, point.value]))
  return p05.points.flatMap((point) => {
    const high = upper.get(point.t)
    return point.value == null || high == null
      ? []
      : [{ x: new Date(point.t).getTime(), y: [point.value, high] }]
  })
})

const lines = computed(() =>
  [PREDICTION_TREND_KEYS.median, PREDICTION_TREND_KEYS.mean]
    .map((key) => findTrendSeries(props.trend, key))
    .filter((entry): entry is Series => entry !== undefined),
)

const chartSeries = computed(() => [
  ...(band.value ? [{ name: PREDICTION_BAND_LABEL, type: 'rangeArea', data: band.value }] : []),
  ...lines.value.map((entry) => ({
    name: escapeChartLabel(entry.label),
    type: 'line',
    data: entry.points.map((point) => ({ x: new Date(point.t).getTime(), y: point.value })),
  })),
])

const labels = computed(() => [
  ...(band.value ? [PREDICTION_BAND_LABEL] : []),
  ...lines.value.map((entry) => entry.label),
])

const options = computed<ApexOptions>(() => {
  const base = getLineChartOptions({
    borderColor: cssValues.value.border,
    gridColor: cssValues.value.grid,
    textColor: cssValues.value.text,
    isDark: isDark.value,
  })
  const formatter = (value: number | null) => formatChartValue(value)
  const bandOffset = band.value ? 1 : 0
  const lineColors = [cssValues.value.primary, cssValues.value.text]
  return {
    ...base,
    colors: [
      ...(band.value ? [cssValues.value.primary] : []),
      ...lines.value.map((_, index) => lineColors[index] ?? cssValues.value.text),
    ],
    stroke: {
      curve: 'straight',
      width: labels.value.map((_, index) => (index < bandOffset ? 0 : 2)),
      dashArray: labels.value.map((_, index) => (index > bandOffset ? 4 : 0)),
    },
    fill: { opacity: labels.value.map((_, index) => (index < bandOffset ? 0.25 : 1)) },
    legend: getChartLegend(labels.value),
    grid: { ...base.grid, padding: { ...base.grid?.padding, top: CHART_LEGEND_HEIGHT } },
    markers: {
      size: [
        ...(band.value ? [0] : []),
        ...lines.value.map((entry) => getMarkerSize(entry.points)),
      ],
      strokeWidth: 0,
      hover: { sizeOffset: 2 },
    },
    yaxis: {
      ...base.yaxis,
      labels: { ...(Array.isArray(base.yaxis) ? {} : base.yaxis?.labels), formatter },
    },
    tooltip: {
      ...base.tooltip,
      y: { formatter: (value: number | null) => formatPreciseValue(value) },
    },
  }
})
</script>
