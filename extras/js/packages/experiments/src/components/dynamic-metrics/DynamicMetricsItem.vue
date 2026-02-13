<template>
  <DynamicMetricsItemContent
    :title="metricName"
    :loading="!data"
    :aggregated="isAggregated"
    class="chart-wrapper"
    @scale="setScaledChart"
  >
    <div ref="chartRef" style="height: 200px; width: 100%"></div>
    <template #scaled>
      <div ref="chartScaledRef" style="height: calc(100vh - 100px); width: 100%"></div>
    </template>
  </DynamicMetricsItemContent>
</template>

<script setup lang="ts">
import type { ExperimentSnapshotDynamicMetric, ModelInfo } from '@/interfaces/interfaces'
import { computed, nextTick, ref, watch } from 'vue'
import { useVariableValue } from '@/hooks/useVariableValue'
import { plotlyLineChartLayout } from '@/lib/plotly/layouts'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { plotlyService } from '@/services/PlotlyService'
import { useTheme } from '@/lib/theme/ThemeProvider'
import DynamicMetricsItemContent from './DynamicMetricsItemContent.vue'

const { getVariablesValues } = useVariableValue()
const theme = useTheme()

type Props = {
  metricName: string
  data: ExperimentSnapshotDynamicMetric[] | undefined
  modelsInfo: Record<string, ModelInfo>
}

const props = defineProps<Props>()

const chartRef = ref<HTMLDivElement | null>(null)
const chartScaledRef = ref<HTMLDivElement | null>(null)

const isAggregated = computed(() => {
  return !!props.data?.some((item) => item.aggregated)
})

const plotlyData = computed(() => {
  if (!props.data) return []
  const data: ExperimentSnapshotDynamicMetric[] = props.data.map((item) => ({
    modelId: item.modelId,
    x: [...item.x],
    y: [...item.y],
    aggregated: item.aggregated,
  }))
  return data
    .filter((item) => item.modelId)
    .map((item) => {
      const modelId = item.modelId
      const modelInfo = props.modelsInfo[modelId] as ModelInfo
      const color = getVariablesValues([modelInfo.color])[0]
      const modelName = getFormattedName(modelInfo.name)
      return {
        ...item,
        type: 'scatter',
        mode: item.x.length > 1 ? 'lines' : 'markers',
        name: props.metricName,
        line: { color: color, width: 2, shape: 'spline', smoothing: 1.2 },
        hovertemplate: '<b>Value:</b> %{y}<br>' + `<b>Model:</b> ${modelName}<extra></extra>`,
      }
    })
})

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

function getPlotlyLayout() {
  const [bgColor, borderColor, textColor, gridColor] = getVariablesValues([
    'var(--p-card-background)',
    'var(--p-content-border-color)',
    'var(--p-text-muted-color)',
    'var(--p-datatable-row-background)',
  ])

  return plotlyLineChartLayout({
    title: props.metricName,
    bgColor: bgColor as string,
    borderColor: borderColor as string,
    textColor: textColor as string,
    gridColor: gridColor as string,
  })
}

async function renderChart() {
  if (!props.data) return
  const layout = getPlotlyLayout()
  const Plotly = await plotlyService.getPlotly()
  Plotly.newPlot(chartRef.value, plotlyData.value, layout, {
    displayModeBar: false,
    responsive: true,
  })
}

watch(theme, async () => {
  const layout = getPlotlyLayout()
  const Plotly = await plotlyService.getPlotly()
  Plotly.relayout(chartRef.value, layout)
})

watch(
  () => props.data,
  () => {
    nextTick(() => {
      renderChart()
    })
  },
  { immediate: true },
)
</script>

<style scoped>
.charts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.chart-wrapper {
  height: 300px;
}
</style>
