<template>
  <VueApexCharts type="line" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import type { Series } from '@/api/monitoring/interfaces'
import { computed } from 'vue'
import { getLineChartOptions } from '@/lib/apex-charts'
import { useCssVariables } from '@/composables/useCssVariables'
import { CHART_HEIGHT, DEFAULT_CHART_COLOR } from '@/constants/charts'
import { countMeasuredPoints, formatChartValue, toChartPoints } from '@/utils/charts'
import VueApexCharts from 'vue3-apexcharts'

interface Props {
  series: Series
  color?: string
  height?: number | string
}

const props = withDefaults(defineProps<Props>(), {
  color: DEFAULT_CHART_COLOR,
  height: CHART_HEIGHT,
})

const { values: cssValues, isDark } = useCssVariables(() => ({
  border: '--p-content-border-color',
  grid: '--p-datatable-row-background',
  text: '--p-text-muted-color',
  line: props.color,
}))

const hasBaseline = computed(() => (props.series.baseline?.length ?? 0) > 0)

const chartSeries = computed(() => {
  const main = { name: props.series.label, data: toChartPoints(props.series.points) }
  if (!hasBaseline.value) return [main]
  return [main, { name: 'Compared period', data: toChartPoints(props.series.baseline ?? []) }]
})

const markerSize = computed(() => (countMeasuredPoints(props.series.points) > 1 ? 0 : 4))

const options = computed(() => {
  const base = getLineChartOptions({
    borderColor: cssValues.value.border,
    gridColor: cssValues.value.grid,
    textColor: cssValues.value.text,
    isDark: isDark.value,
  })
  const formatter = (value: number | null) => formatChartValue(value, props.series.unit)
  return {
    ...base,
    colors: hasBaseline.value
      ? [cssValues.value.line, cssValues.value.text]
      : [cssValues.value.line],
    stroke: hasBaseline.value ? { ...base.stroke, width: [2, 2], dashArray: [0, 5] } : base.stroke,
    markers: { size: markerSize.value, strokeWidth: 0, hover: { sizeOffset: 2 } },
    yaxis: {
      ...base.yaxis,
      labels: { ...(Array.isArray(base.yaxis) ? {} : base.yaxis?.labels), formatter },
    },
    tooltip: { ...base.tooltip, y: { formatter } },
  }
})
</script>
