<template>
  <EvalsScoresMultipleItemContent :title="data[0].scoreName" @scale="setScaledChart">
    <div ref="chartRef" style="height: 200px; width: 100%"></div>
    <template #scaled>
      <div ref="chartScaledRef" style="height: calc(100vh - 100px); width: 100%"></div>
    </template>
  </EvalsScoresMultipleItemContent>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import Plotly from 'plotly.js-dist'
import { useVariableValue } from '../../../../hooks/useVariableValue'
import { plotlyBarChartLayout } from '../../../../lib/plotly/layouts'
import EvalsScoresMultipleItemContent from './EvalsScoresMultipleItemContent.vue'

type Props = {
  data: { modelName: string; color: string; value: number | undefined; scoreName: string }[]
}

const props = defineProps<Props>()
const { getVariablesValues } = useVariableValue()

const chartRef = ref<HTMLDivElement[]>([])
const chartScaledRef = ref<HTMLDivElement[]>([])

const plotlyData = computed(() => {
  const x: string[] = []
  const y: number[] = []
  const color: string[] = []
  props.data.map((item) => {
    if (item.value === undefined) return
    x.push(item.modelName)
    y.push(item.value)
    color.push(item.color)
  })
  return [{ x, y, type: 'bar', marker: { color: getVariablesValues(color) } }]
})

const plotlyLayout = computed(() => {
  const [bgColor, textColor, gridColor] = getVariablesValues([
    'var(--p-card-background)',
    'var(--p-text-muted-color)',
    'var(--p-datatable-row-background)',
  ])

  return plotlyBarChartLayout({ title: props.data[0].scoreName, bgColor, textColor, gridColor })
})

function setScaledChart() {
  nextTick(() => {
    Plotly.newPlot(chartScaledRef.value, plotlyData.value, plotlyLayout.value, {
      displayModeBar: false,
      responsive: true,
    })
  })
}

onMounted(() => {
  Plotly.newPlot(chartRef.value, plotlyData.value, plotlyLayout.value, {
    displayModeBar: false,
    responsive: true,
  })
})
</script>

<style scoped>
.chart {
  height: 300px;
}
</style>
