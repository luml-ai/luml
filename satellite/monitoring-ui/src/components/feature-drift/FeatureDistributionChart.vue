<template>
  <MApexChart type="bar" :height="height" :options="options" :series="series" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ApexOptions } from 'apexcharts'
import MApexChart from '@/components/MApexChart.vue'
import type { FeatureDistribution } from '@/api/monitoring/interfaces'
import { getBaseChartOptions } from '@/lib/apex-charts'
import { useCssVariables } from '@/composables/useCssVariables'
import { CHART_HEIGHT } from '@/constants/charts'
import { formatPercent } from '@/utils/format'
import { getDistributionCategories, getDistributionSeries } from '@/utils/drift'

interface Props {
  distribution: FeatureDistribution
  height?: number | string
}

const props = withDefaults(defineProps<Props>(), {
  height: CHART_HEIGHT,
})

const { values: cssValues, isDark } = useCssVariables({
  border: '--p-content-border-color',
  grid: '--p-datatable-row-background',
  text: '--p-text-muted-color',
  reference: '--p-surface-400',
  current: '--p-primary-color',
})

const series = computed(() => getDistributionSeries(props.distribution))

const formatter = (value: number | null) => (value == null ? '—' : formatPercent(value))

const options = computed<ApexOptions>(() => {
  const base = getBaseChartOptions()
  return {
    ...base,
    chart: { ...base.chart, animations: { enabled: false }, foreColor: cssValues.value.text },
    colors: [cssValues.value.reference, cssValues.value.current],
    plotOptions: { bar: { columnWidth: '68%', borderRadius: 3 } },
    legend: { show: true, position: 'top', horizontalAlign: 'right', fontSize: '12px' },
    grid: {
      borderColor: cssValues.value.grid,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
      padding: { top: 0, right: 8, bottom: 0, left: 8 },
    },
    xaxis: {
      categories: getDistributionCategories(props.distribution),
      axisBorder: { show: true, color: cssValues.value.border, height: 2 },
      axisTicks: { show: false },
      labels: {
        rotate: 0,
        hideOverlappingLabels: true,
        trim: true,
        style: { colors: cssValues.value.text, fontSize: '12px' },
      },
    },
    yaxis: {
      labels: { style: { colors: cssValues.value.text, fontSize: '12px' }, formatter },
    },
    tooltip: {
      shared: true,
      intersect: false,
      theme: isDark.value ? 'dark' : 'light',
      y: { formatter },
    },
  }
})
</script>
