<template>
  <EvalsScoresMultipleItemContent :title="data[0]?.scoreName || ''" @scale="setScaledChart">
    <div ref="chartRef" style="height: 200px; width: 100%"></div>
    <template #scaled>
      <div ref="chartScaledRef" style="height: calc(100vh - 100px); width: 100%"></div>
    </template>
  </EvalsScoresMultipleItemContent>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useVariableValue } from '@/hooks/useVariableValue'
import { plotlyBarChartLayout } from '@/lib/plotly/layouts'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { plotlyService } from '@/services/PlotlyService'
import { useTheme } from '@/lib/theme/ThemeProvider'
import EvalsScoresMultipleItemContent from './EvalsScoresMultipleItemContent.vue'

type Props = {
  data: {
    modelId: string
    modelName: string
    color: string
    value: number | undefined
    scoreName: string
  }[]
}

const props = defineProps<Props>()
const { getVariablesValues } = useVariableValue()
const theme = useTheme()

const chartRef = ref<HTMLDivElement | null>(null)
const chartScaledRef = ref<HTMLDivElement | null>(null)

const plotlyData = computed(() => {
  const x: string[] = []
  const y: number[] = []
  const color: string[] = []
  const customdata: string[] = []
  props.data.map((item) => {
    if (item.value === undefined) return
    x.push(item.modelId)
    y.push(item.value)
    color.push(item.color)
    customdata.push(getFormattedName(item.modelName))
  })
  return [
    {
      x,
      y,
      customdata,
      type: 'bar',
      marker: { color: getVariablesValues(color) },
      hovertemplate: '<b>Model:</b> %{customdata}<br>' + '<b>Value:</b> %{y}<extra></extra>',
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

async function renderChart() {
  if (!chartRef.value) return
  const Plotly = await plotlyService.getPlotly()
  const layout = getPlotlyLayout()
  Plotly.react(chartRef.value, plotlyData.value, layout, {
    displayModeBar: false,
    responsive: true,
  })
}

function setScaledChart() {
  nextTick(async () => {
    if (!chartScaledRef.value) return
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
  if (!chartRef.value) return
  const layout = getPlotlyLayout()
  const Plotly = await plotlyService.getPlotly()
  Plotly.relayout(chartRef.value, layout)
})

watch(
  () => props.data,
  () => {
    nextTick(() => renderChart())
  },
  { immediate: true },
)

onBeforeUnmount(async () => {
  const Plotly = await plotlyService.getPlotly()
  if (chartRef.value) Plotly.purge(chartRef.value)
  if (chartScaledRef.value) Plotly.purge(chartScaledRef.value)
})
</script>

<style scoped>
.chart {
  height: 300px;
}
</style>
