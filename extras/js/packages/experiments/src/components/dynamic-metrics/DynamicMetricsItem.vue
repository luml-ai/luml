<template>
  <DynamicMetricsItemContent
    :title="metricName"
    :loading="status.loading"
    :aggregation-steps="status.level === null ? null : 4 ** status.level"
    :error="status.error"
    class="chart-wrapper"
    data-testid="metric-chart"
    :data-metric-key="metricName"
    :data-level="status.level ?? 0"
    :data-state="status.state"
  >
    <MetricBucketPlot
      :store="store"
      :metric-name="metricName"
      :model-ids="modelIds"
      :full-range="fullRange"
      :models-info="modelsInfo"
      height="200px"
      lazy
      @status="status = $event"
    />
    <template #scaled>
      <MetricBucketPlot
        :store="store"
        :metric-name="metricName"
        :model-ids="modelIds"
        :full-range="fullRange"
        :models-info="modelsInfo"
        height="calc(100vh - 100px)"
      />
    </template>
  </DynamicMetricsItemContent>
</template>

<script setup lang="ts">
import type { ModelInfo } from '@/interfaces/interfaces'
import type { MetricBucketStore } from '@/metric-buckets/MetricBucketStore'
import type { StepRange } from '@/lib/metric-charts/bucketTraces'
import { ref } from 'vue'
import DynamicMetricsItemContent from './DynamicMetricsItemContent.vue'
import type { PlotStatus } from './dynamic-metrics.interface'
import MetricBucketPlot from './MetricBucketPlot.vue'

type Props = {
  store: MetricBucketStore
  metricName: string
  modelIds: string[]
  fullRange: StepRange
  modelsInfo: Record<string, ModelInfo>
}

defineProps<Props>()

const status = ref<PlotStatus>({ level: null, loading: false, error: null, state: 'loading' })
</script>

<style scoped>
.chart-wrapper {
  height: 300px;
  overflow: hidden;
}
</style>
