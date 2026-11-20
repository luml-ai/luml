<template>
  <MApexChart type="line" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ApexOptions } from 'apexcharts'
import type { Series } from '@/api/monitoring/interfaces'
import { getLineChartOptions } from '@/lib/apex-charts'
import { useCssVariables } from '@/composables/useCssVariables'
import { CHART_HEIGHT, MULTI_SERIES_CHART_COLORS } from '@/constants/charts'
import {
  escapeChartLabel,
  formatChartValue,
  hasIsolatedPoints,
  toChartPoints,
} from '@/utils/charts'
import MApexChart from '@/components/MApexChart.vue'

interface Props {
  series: Series[]
  height?: number | string
}

const props = withDefaults(defineProps<Props>(), {
  height: CHART_HEIGHT,
})

const colorVariables = Object.fromEntries(
  MULTI_SERIES_CHART_COLORS.map((variable, index) => [`color${index}`, variable]),
)

const { values: cssValues, isDark } = useCssVariables({
  border: '--p-content-border-color',
  grid: '--p-datatable-row-background',
  text: '--p-text-muted-color',
  ...colorVariables,
})

const chartSeries = computed(() =>
  props.series.map((entry) => ({
    name: escapeChartLabel(entry.label),
    data: toChartPoints(entry.points),
  })),
)

const unit = computed(() => props.series[0]?.unit ?? null)

const markerSize = computed(() =>
  props.series.some((entry) => hasIsolatedPoints(entry.points)) ? 4 : 0,
)

const options = computed<ApexOptions>(() => {
  const base = getLineChartOptions({
    borderColor: cssValues.value.border,
    gridColor: cssValues.value.grid,
    textColor: cssValues.value.text,
    isDark: isDark.value,
  })
  const formatter = (value: number | null) => formatChartValue(value, unit.value)
  const values = cssValues.value as Record<string, string>
  return {
    ...base,
    colors: MULTI_SERIES_CHART_COLORS.map((_, index) => values[`color${index}`]),
    legend: { show: true, position: 'top', horizontalAlign: 'right', fontSize: '12px' },
    markers: { size: markerSize.value, strokeWidth: 0, hover: { sizeOffset: 2 } },
    yaxis: {
      ...base.yaxis,
      labels: { ...(Array.isArray(base.yaxis) ? {} : base.yaxis?.labels), formatter },
    },
    tooltip: { ...base.tooltip, y: { formatter } },
  }
})
</script>
