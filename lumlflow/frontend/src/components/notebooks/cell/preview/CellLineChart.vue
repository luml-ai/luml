<template>
  <div ref="containerRef" class="chart"></div>
</template>

<script setup lang="ts">
import type { CellLineChartProps } from './preview.interface'
import { ref } from 'vue'
import { usePlotlyChart } from '@/composables/usePlotlyChart'
import { baseChartLayout, chartColor } from '@/plotly/plotly.const'

const props = defineProps<CellLineChartProps>()

const containerRef = ref<HTMLElement | null>(null)

usePlotlyChart(
  containerRef,
  () => [
    {
      type: 'scatter',
      mode: 'lines',
      name: props.block.name,
      line: { color: chartColor(0) },
      x: props.block.points.map(([index]) => index),
      y: props.block.points.map(([, value]) => value),
    },
  ],
  () => ({ ...baseChartLayout(), title: { text: props.block.name } }),
)
</script>

<style scoped>
.chart {
  height: 220px;
}
</style>
