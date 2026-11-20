<template>
  <MApexChart type="line" :height="height" :options="options" :series="chartSeries" />
</template>

<script setup lang="ts">
import type { Series } from '@/api/monitoring/interfaces'
import { computed } from 'vue'
import { getLineChartOptions } from '@/lib/apex-charts'
import { useCssVariables } from '@/composables/useCssVariables'
import { CHART_HEIGHT, DEFAULT_CHART_COLOR } from '@/constants/charts'
import {
  escapeChartLabel,
  formatChartValue,
  hasIsolatedPoints,
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
  return [main, { name: 'Compared period', data: toChartPoints(props.series.baseline ?? []) }]
})

const markerSize = computed(() => (hasIsolatedPoints(props.series.points) ? 4 : 0))

const thresholdRange = computed(() => {
  const threshold = props.threshold
  if (threshold == null) return {}
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
    markers: { size: markerSize.value, strokeWidth: 0, hover: { sizeOffset: 2 } },
    yaxis: {
      ...base.yaxis,
      ...thresholdRange.value,
      labels: { ...(Array.isArray(base.yaxis) ? {} : base.yaxis?.labels), formatter },
    },
    tooltip: { ...base.tooltip, y: { formatter } },
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
