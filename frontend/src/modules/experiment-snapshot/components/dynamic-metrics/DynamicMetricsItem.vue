<template>
  <DynamicMetricsItemContent :title="metricName" class="chart-wrapper" @scale="setScaledChart">
    <div ref="chartRef" style="height: 200px; width: 100%"></div>
    <template #scaled>
      <div ref="chartScaledRef" style="height: calc(100vh - 100px); width: 100%"></div>
    </template>
  </DynamicMetricsItemContent>
</template>

<script setup lang="ts">
import type { ExperimentSnapshotDynamicMetric, ModelInfo } from '../../interfaces/interfaces'
import { computed, nextTick, onMounted, ref } from 'vue'
import Plotly from 'plotly.js-dist'
import DynamicMetricsItemContent from './DynamicMetricsItemContent.vue'
import { useVariableValue } from '../../hooks/useVariableValue'
import { plotlyLineChartLayout } from '../../lib/plotly/layouts'

const { getVariablesValues } = useVariableValue()

type Props = {
  metricName: string
  data: ExperimentSnapshotDynamicMetric[]
  modelsInfo: Record<string, ModelInfo>
}

const props = defineProps<Props>()

const chartRef = ref<HTMLDivElement[]>([])
const chartScaledRef = ref<HTMLDivElement[]>([])

const plotlyData = computed(() => {
  return props.data
    .filter((item) => item.modelId)
    .map((data) => {
      const color = getVariablesValues([props.modelsInfo[data.modelId]?.color])[0]
      return {
        ...data,
        type: 'scatter',
        mode: 'lines',
        name: props.metricName,
        line: { color: color, width: 3 },
        hovertemplate:
          '<b>Value:</b> %{y}<br>' +
          `<b>Model:</b> ${props.modelsInfo[data.modelId]?.name}<extra></extra>`,
      }
    })
})

const plotlyLayout = computed(() => {
  const [bgColor, borderColor, textColor, gridColor] = getVariablesValues([
    'var(--p-card-background)',
    'var(--p-content-border-color)',
    'var(--p-text-muted-color)',
    'var(--p-datatable-row-background)',
  ])

  return plotlyLineChartLayout({
    title: props.metricName,
    bgColor,
    borderColor,
    textColor,
    gridColor,
  })
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
.charts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.chart-wrapper {
  height: 300px;
}
</style>
