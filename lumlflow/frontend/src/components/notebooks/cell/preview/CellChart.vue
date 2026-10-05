<template>
  <div class="cell-chart">
    <p v-if="!shown.length" class="empty">No metrics selected</p>
    <div v-else ref="containerRef" class="chart"></div>
  </div>
</template>

<script setup lang="ts">
import type { CellChartProps } from './preview.interface'
import { computed, ref } from 'vue'
import { usePlotlyChart } from '@/composables/usePlotlyChart'
import { baseChartLayout, chartColor } from '@/plotly/plotly.const'

const props = defineProps<CellChartProps>()

const containerRef = ref<HTMLElement | null>(null)

/** Every metric this chart can draw, with the colour it keeps when others hide. */
const metrics = computed(() =>
  props.section.kind === 'lines'
    ? props.section.series.map((series, index) => ({ name: series.name, color: chartColor(index) }))
    : props.section.entries.map(([name], index) => ({ name, color: chartColor(index) })),
)

const shown = computed(() =>
  metrics.value
    .map((metric, index) => ({ ...metric, index }))
    .filter(({ index }) => !props.hidden.has(index)),
)

usePlotlyChart(
  containerRef,
  () => {
    const section = props.section
    if (section.kind === 'lines') {
      return shown.value.map(({ index, color }) => {
        const series = section.series[index]
        return {
          type: 'scatter',
          mode: 'lines',
          name: series?.name,
          line: { color },
          x: series?.points.map(([at]) => at) ?? [],
          y: series?.points.map(([, value]) => value) ?? [],
        }
      })
    }
    return [
      {
        type: 'bar',
        x: shown.value.map(({ name }) => name),
        y: shown.value.map(({ index }) => section.entries[index]?.[1] ?? null),
        marker: { color: shown.value.map(({ color }) => color) },
      },
    ]
  },
  () => ({ ...baseChartLayout(), barcornerradius: 4 }),
)

</script>

<style scoped>
@reference "@/assets/css/index.css";

.chart {
  height: 220px;
}
.empty {
  @apply text-sm text-muted-color py-8 text-center;
}
</style>
