<template>
  <div class="charts">
    <DynamicMetricsItem
      v-for="name in uniqueMetrics"
      :key="name"
      :metric-name="name"
      :data="metricsRecord[name]"
      :models-info="modelsInfo"
    />
  </div>
</template>

<script setup lang="ts">
import type {
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotDynamicMetrics,
  ModelInfo,
} from '../../interfaces/interfaces'
import { computed } from 'vue'
import DynamicMetricsItem from './DynamicMetricsItem.vue'

type Props = {
  metricsList: ExperimentSnapshotDynamicMetrics[]
  modelsInfo: Record<string, ModelInfo>
}

const props = defineProps<Props>()

const { uniqueMetrics, metricsRecord } = computed(() => {
  const keysSet = new Set<string>()
  const record: Record<string, ExperimentSnapshotDynamicMetric[]> = {}

  props.metricsList.forEach((modelData, modelIdx) => {
    Object.entries(modelData).forEach(([metricName, value]) => {
      keysSet.add(metricName)

      if (!record[metricName]) {
        record[metricName] = []
      }
      record[metricName][modelIdx] = value
    })
  })

  for (const metric of keysSet) {
    record[metric] ??= []
    for (let i = 0; i < props.metricsList.length; i++) {
      record[metric][i] = record[metric][i] || []
    }
  }

  return {
    uniqueMetrics: [...keysSet].sort((a, b) =>
      a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }),
    ),
    metricsRecord: record,
  }
}).value
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
