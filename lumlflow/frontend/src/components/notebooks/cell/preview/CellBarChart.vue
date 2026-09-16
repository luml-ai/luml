<template>
  <div ref="containerRef" class="chart"></div>
</template>

<script setup lang="ts">
import type { CellBarChartProps } from './preview.interface'
import { ref } from 'vue'
import { usePlotlyChart } from '@/composables/usePlotlyChart'
import { baseChartLayout, chartPalette } from '@/plotly/plotly.const'

const props = defineProps<CellBarChartProps>()

const containerRef = ref<HTMLElement | null>(null)

usePlotlyChart(
  containerRef,
  () => [
    {
      type: 'bar',
      x: props.entries.map(([name]) => name),
      y: props.entries.map(([, value]) => value),
      marker: { color: chartPalette(props.entries.length) },
    },
  ],
  () => ({ ...baseChartLayout(), barcornerradius: 4 }),
)
</script>

<style scoped>
.chart {
  height: 220px;
}
</style>
