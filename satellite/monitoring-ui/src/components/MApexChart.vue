<template>
  <div ref="root" class="apex-chart" />
</template>

<script setup lang="ts">
import ApexCharts from 'apexcharts'
import type { ApexOptions } from 'apexcharts'
import { onBeforeUnmount, onMounted, shallowRef, useTemplateRef, watch } from 'vue'

type ChartType = NonNullable<NonNullable<ApexOptions['chart']>['type']>

interface Props {
  type: ChartType
  options: ApexOptions
  series: ApexOptions['series']
  height?: number | string
}

const props = withDefaults(defineProps<Props>(), {
  height: 'auto',
})

const root = useTemplateRef<HTMLDivElement>('root')
const chart = shallowRef<ApexCharts | null>(null)

function buildOptions(): ApexOptions {
  return {
    ...props.options,
    chart: { ...props.options.chart, type: props.type, height: props.height },
    series: props.series,
  }
}

onMounted(() => {
  if (!root.value) return
  chart.value = new ApexCharts(root.value, buildOptions())
  chart.value.render()
})

watch(
  () => [props.options, props.type, props.height],
  () => {
    chart.value?.updateOptions(buildOptions(), false, false)
  },
)

watch(
  () => props.series,
  (series) => {
    if (series) chart.value?.updateSeries(series, false)
  },
  { deep: true },
)

onBeforeUnmount(() => {
  chart.value?.destroy()
  chart.value = null
})
</script>

<style scoped>
.apex-chart {
  height: 100%;
}
</style>
