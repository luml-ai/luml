<template>
  <DynamicMetricsToolbar
    v-if="visibleMetricsNames.length > 0"
    :limit="METRICS_LIMIT"
    :total="metricsNames.length"
    @page-change="onPageChange"
  />
  <div class="charts">
    <DynamicMetricsItem
      v-for="name in visibleMetricsNames"
      :key="name"
      :metric-name="name"
      :data="metrics[name]"
      :models-info="modelsInfo"
    />
  </div>
</template>

<script setup lang="ts">
import type {
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  ModelInfo,
} from '../../interfaces/interfaces'
import type { PageState } from 'primevue'
import { onBeforeUnmount, ref, watch } from 'vue'
import DynamicMetricsItem from './DynamicMetricsItem.vue'
import DynamicMetricsToolbar from './DynamicMetricsToolbar.vue'

const METRICS_LIMIT = 50

type Props = {
  metricsNames: string[]
  provider: ExperimentSnapshotProvider
  modelsInfo: Record<string, ModelInfo>
}

const props = defineProps<Props>()

let dynamicMetricsController: AbortController | null = null

const page = ref(0)
const visibleMetricsNames = ref<string[]>([])
const metrics = ref<Record<string, ExperimentSnapshotDynamicMetric[]>>({})

function resetMetrics() {
  metrics.value = {}
}

async function getMetrics() {
  const metricsToFetch = visibleMetricsNames.value.filter((name) => !metrics.value[name])
  const results = await fetchMetrics(metricsToFetch)
  const rejectedMetrics: Record<string, any> = {}
  results.forEach((result, index) => {
    if (result.status === 'rejected') {
      rejectedMetrics[metricsToFetch[index]] = result.reason
    }
  })
  handleRejectedMetrics(rejectedMetrics)
}

function handleRejectedMetrics(rejectedMetrics: Record<string, any>) {
  Object.keys(rejectedMetrics).forEach((name) => {
    console.error(`Failed to load dynamic metric data for "${name}":`, rejectedMetrics[name])
  })
}

async function fetchMetrics(names: string[]) {
  dynamicMetricsController?.abort()
  dynamicMetricsController = new AbortController()
  return Promise.allSettled(
    names.map(async (name) => {
      const data = await props.provider.getDynamicMetricData(name, dynamicMetricsController?.signal)
      metrics.value[name] = data
    }),
  )
}

function onPageChange(event: PageState) {
  page.value = event.page
}

function setVisibleMetricsNames() {
  visibleMetricsNames.value = props.metricsNames.slice(
    page.value * METRICS_LIMIT,
    (page.value + 1) * METRICS_LIMIT,
  )
}

watch(
  page,
  () => {
    setVisibleMetricsNames()
    resetMetrics()
    getMetrics()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  dynamicMetricsController?.abort()
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
