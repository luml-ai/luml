import type { ExperimentSnapshotDynamicMetric } from '@experiments/interfaces/interfaces'
import axios from 'axios'
import { useEvalsStore } from '../evals'
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@experiments/lib/primevue/data/toasts'
import { METRICS_LIMIT } from './dynamic-metrics.data'

export const useDynamicMetricsStore = defineStore('dynamicMetrics', () => {
  const evalsStore = useEvalsStore()
  const toast = useToast()

  const abortController = ref<AbortController | null>(null)

  const metricsNames = ref<string[]>([])

  const page = ref(0)

  const metrics = ref<Record<string, ExperimentSnapshotDynamicMetric[]>>({})

  const currentMetricsNames = ref<string[]>([])

  function setCurrentMetricsNames() {
    const startIndex = page.value * METRICS_LIMIT
    const endIndex = (page.value + 1) * METRICS_LIMIT
    currentMetricsNames.value = metricsNames.value.slice(startIndex, endIndex)
  }

  async function getMetricsData() {
    const metricsToFetch = currentMetricsNames.value.filter((name) => !metrics.value[name])
    const results = await fetchMetrics(metricsToFetch)
    const rejectedMetrics: Record<string, any> = {}
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        const name = metricsToFetch[index]
        if (!name) return
        rejectedMetrics[name] = result.reason
      }
    })
    handleRejectedMetrics(rejectedMetrics)
  }

  function handleRejectedMetrics(rejectedMetrics: Record<string, any>) {
    Object.entries(rejectedMetrics).forEach(([name, reason]) => {
      const isCanceled = axios.isCancel(reason)
      if (isCanceled) return
      toast.add(simpleErrorToast(`Failed to load dynamic metric data for "${name}"`))
    })
  }

  async function fetchMetrics(names: string[]) {
    abortController.value?.abort()
    const controller = new AbortController()
    abortController.value = controller
    return Promise.allSettled(
      names.map(async (name) => {
        const data = await evalsStore.getProvider.getDynamicMetricData(name, controller.signal)
        metrics.value[name] = data
      }),
    )
  }

  function setMetricsNames(names: string[]) {
    metricsNames.value = names
    setCurrentMetricsNames()
    resetData()
    getMetricsData()
  }

  function setPage(value: number) {
    page.value = value
  }

  function resetData() {
    metrics.value = {}
  }

  function reset() {
    resetData()
    page.value = 0
    currentMetricsNames.value = []
    metricsNames.value = []
    abortController.value?.abort()
  }

  async function refresh() {
    currentMetricsNames.value.forEach((name) => {
      delete metrics.value[name]
    })
    await getMetricsData()
  }

  watch(
    page,
    () => {
      setCurrentMetricsNames()
      resetData()
      getMetricsData()
    },
    {
      immediate: true,
    },
  )

  return {
    metricsNames,
    metrics,
    reset,
    page,
    setPage,
    setMetricsNames,
    currentMetricsNames,
    refresh,
  }
})
