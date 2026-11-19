<template>
  <DynamicMetricsItemContent
    :title="metricName"
    :loading="status.loading"
    :aggregation-steps="aggregationSteps(status)"
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
      <!-- The maximized dialog covers the card header, so its own plot's status shows here. -->
      <div class="scaled-status" data-testid="scaled-status">
        <PlotStatusIcons
          :aggregation-steps="aggregationSteps(scaledStatus)"
          :error="scaledStatus.error"
        />
        <ProgressSpinner v-if="scaledStatus.loading" class="scaled-spinner" stroke-width="6" />
      </div>
      <MetricBucketPlot
        :store="store"
        :metric-name="metricName"
        :model-ids="modelIds"
        :full-range="fullRange"
        :models-info="modelsInfo"
        height="calc(100vh - 124px)"
        @status="scaledStatus = $event"
      />
    </template>
  </DynamicMetricsItemContent>
</template>

<script setup lang="ts">
import type { ModelInfo } from '@/interfaces/interfaces'
import type { MetricBucketStore } from '@/metric-buckets/MetricBucketStore'
import type { StepRange } from '@/lib/metric-charts/bucketTraces'
import { ref } from 'vue'
import { ProgressSpinner } from 'primevue'
import DynamicMetricsItemContent from './DynamicMetricsItemContent.vue'
import type { PlotStatus } from './dynamic-metrics.interface'
import MetricBucketPlot from './MetricBucketPlot.vue'
import PlotStatusIcons from './PlotStatusIcons.vue'

type Props = {
  store: MetricBucketStore
  metricName: string
  modelIds: string[]
  fullRange: StepRange
  modelsInfo: Record<string, ModelInfo>
}

defineProps<Props>()

const status = ref<PlotStatus>({ level: null, loading: false, error: null, state: 'loading' })
const scaledStatus = ref<PlotStatus>({ ...status.value })

function aggregationSteps({ level }: PlotStatus): number | null {
  return level === null ? null : 4 ** level
}
</script>

<style scoped>
.chart-wrapper {
  height: 300px;
  overflow: hidden;
}

.scaled-status {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 24px;
}

.scaled-spinner {
  width: 16px;
  height: 16px;
}
</style>
