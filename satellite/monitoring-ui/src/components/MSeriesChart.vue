<template>
  <MApexChart type="line" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import type { Series } from '@/api/monitoring/interfaces'
import { computed } from 'vue'
import { getLineChartOptions } from '@/lib/apex-charts'
import { useCssVariables } from '@/composables/useCssVariables'
import {
  CHART_HEIGHT,
  CHART_LEGEND_HEIGHT,
  COMPARED_PERIOD_LABEL,
  DEFAULT_CHART_COLOR,
  FLAT_ZERO_RATIO_MAX,
} from '@/constants/charts'
import {
  escapeChartLabel,
  formatChartValue,
  formatPreciseValue,
  getChartLegend,
  getMarkerSize,
  isFlatZero,
  toChartPoints,
} from '@/utils/charts'
import MApexChart from '@/components/MApexChart.vue'

interface Props {
  series: Series
  color?: string
  height?: number | string
  threshold?: number | null
}

const props = withDefaults(defineProps<Props>(), {
  color: DEFAULT_CHART_COLOR,
  height: CHART_HEIGHT,
  threshold: null,
})

const { values: cssValues, isDark } = useCssVariables(() => ({
  border: '--p-content-border-color',
  grid: '--p-datatable-row-background',
  text: '--p-text-muted-color',
  line: props.color,
}))

const hasBaseline = computed(() => (props.series.baseline?.length ?? 0) > 0)

const chartSeries = computed(() => {
  const main = {
    name: escapeChartLabel(props.series.label),
    data: toChartPoints(props.series.points),
  }
  if (!hasBaseline.value) return [main]
  return [main, { name: COMPARED_PERIOD_LABEL, data: toChartPoints(props.series.baseline ?? []) }]
})

const markerSize = computed(() => {
  const main = getMarkerSize(props.series.points)
  return hasBaseline.value ? [main, getMarkerSize(props.series.baseline ?? [])] : main
})

const isFlatZeroRatio = computed(
  () =>
    props.series.unit === 'ratio' &&
    isFlatZero([...props.series.points, ...(props.series.baseline ?? [])]),
)

const yRange = computed(() => {
  const threshold = props.threshold
  if (threshold == null) {
    return isFlatZeroRatio.value ? { min: 0, max: FLAT_ZERO_RATIO_MAX } : {}
  }
  if (isFlatZeroRatio.value) return { min: 0, max: Math.max(threshold, FLAT_ZERO_RATIO_MAX) }
  return {
    min: (min: number) => Math.min(min, threshold),
    max: (max: number) => Math.max(max, threshold),
  }
})

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
    legend: hasBaseline.value
      ? getChartLegend([props.series.label, COMPARED_PERIOD_LABEL])
      : base.legend,
    grid: hasBaseline.value
      ? { ...base.grid, padding: { ...base.grid?.padding, top: CHART_LEGEND_HEIGHT } }
      : base.grid,
    markers: { size: markerSize.value, strokeWidth: 0, hover: { sizeOffset: 2 } },
    yaxis: {
      ...base.yaxis,
      ...yRange.value,
      labels: { ...(Array.isArray(base.yaxis) ? {} : base.yaxis?.labels), formatter },
    },
    tooltip: {
      ...base.tooltip,
      y: { formatter: (value: number | null) => formatPreciseValue(value, props.series.unit) },
    },
    annotations: {
      yaxis:
        props.threshold == null
          ? []
          : [
              {
                y: props.threshold,
                borderColor: cssValues.value.text,
                strokeDashArray: 4,
                label: {
                  text: 'Threshold',
                  borderWidth: 0,
                  style: { color: cssValues.value.text, background: 'transparent' },
                },
              },
            ],
    },
  }
})
</script>
