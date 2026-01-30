<template>
  <EvalsScoresMultipleItemContent :title="data[0]?.scoreName || ''" @scale="setScaledChart">
    <div ref="chartRef" style="height: 200px; width: 100%"></div>
    <template #scaled>
      <div ref="chartScaledRef" style="height: calc(100vh - 100px); width: 100%"></div>
    </template>
  </EvalsScoresMultipleItemContent>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useVariableValue } from '@/hooks/useVariableValue'
import { plotlyBarChartLayout } from '@/lib/plotly/layouts'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { plotlyService } from '@/services/PlotlyService'
import { useTheme } from '@/lib/theme/ThemeProvider'
import EvalsScoresMultipleItemContent from './EvalsScoresMultipleItemContent.vue'

type Props = {
  data: { modelName: string; color: string; value: number | undefined; scoreName: string }[]
}

const props = defineProps<Props>()
const { getVariablesValues } = useVariableValue()
const theme = useTheme()

const chartRef = ref<HTMLDivElement[]>([])
const chartScaledRef = ref<HTMLDivElement[]>([])

const plotlyData = computed(() => {
  const x: string[] = []
  const y: number[] = []
  const color: string[] = []
  props.data.map((item) => {
    if (item.value === undefined) return
    x.push(getFormattedName(item.modelName))
    y.push(item.value)
    color.push(item.color)
  })
  return [
    {
      x,
      y,
      type: 'bar',
      marker: { color: getVariablesValues(color) },
      hovertemplate: '<b>Model:</b> %{x}<br>' + '<b>Value:</b> %{y}<extra></extra>',
    },
  ]
})

function getPlotlyLayout() {
  const [bgColor, textColor, gridColor] = getVariablesValues([
    'var(--p-card-background)',
    'var(--p-text-muted-color)',
    'var(--p-datatable-row-background)',
  ])

  return plotlyBarChartLayout({
    title: props.data[0]?.scoreName || 'Unknown score',
    bgColor: bgColor as string,
    textColor: textColor as string,
    gridColor: gridColor as string,
  })
}

function setScaledChart() {
  nextTick(async () => {
    const layout = getPlotlyLayout()
    const Plotly = await plotlyService.getPlotly()
    Plotly.newPlot(chartScaledRef.value, plotlyData.value, layout, {
      displayModeBar: false,
      responsive: true,
    })
  })
}

function getFormattedName(name: string | undefined) {
  if (!name) return ''
  if (name.length > 24) {
    return cutStringOnMiddle(name, 24)
  }
  return name
}

watch(theme, async () => {
  const layout = getPlotlyLayout()
  const Plotly = await plotlyService.getPlotly()
  Plotly.relayout(chartRef.value, layout)
})

onMounted(async () => {
  const Plotly = await plotlyService.getPlotly()
  const layout = getPlotlyLayout()
  Plotly.newPlot(chartRef.value, plotlyData.value, layout, {
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
