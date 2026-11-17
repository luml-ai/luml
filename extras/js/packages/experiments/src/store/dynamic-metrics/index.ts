import type { ExperimentReadError, ExperimentSnapshotStatus } from '@/metric-buckets/types'
import type { MetricBucketStore, MetricCatalogs } from '@/metric-buckets/MetricBucketStore'
import { useEvalsStore } from '../evals'
import { defineStore } from 'pinia'
import { computed, markRaw, ref, shallowRef } from 'vue'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { catalogMetricEntries } from '@/lib/metric-charts/bucketTraces'
import { METRICS_LIMIT } from './dynamic-metrics.data'

export const useDynamicMetricsStore = defineStore('dynamicMetrics', () => {
  const evalsStore = useEvalsStore()
  const toast = useToast()

  const catalogs = shallowRef<MetricCatalogs | null>(null)
  const loading = ref(false)
  const filter = ref('')
  const page = ref(0)
  let loadedFrom: MetricBucketStore | null = null

  const entries = computed(() => (catalogs.value ? catalogMetricEntries(catalogs.value) : []))

  /**
   * Loaded with the catalogs and refreshed with them. An experiment whose catalog failed is
   * left out of the charts, so its status carries that failure when it has none of its own.
   */
  const statuses = computed<ExperimentSnapshotStatus[]>(() => {
    const loaded = catalogs.value
    if (!loaded) return []
    return loaded.statuses.map((status) => {
      const catalogError = loaded.errors.get(status.modelId)
      return status.error || !catalogError ? status : { ...status, error: catalogError }
    })
  })

  const lowerCaseKeys = computed(() => entries.value.map((entry) => entry.key.toLowerCase()))

  const metricsNames = computed(() => entries.value.map((entry) => entry.key))

  const filteredMetrics = computed(() => {
    const query = filter.value.trim().toLowerCase()
    if (!query) return entries.value
    return entries.value.filter((_, index) => lowerCaseKeys.value[index]?.includes(query))
  })

  const currentMetrics = computed(() =>
    filteredMetrics.value.slice(page.value * METRICS_LIMIT, (page.value + 1) * METRICS_LIMIT),
  )

  const currentMetricsNames = computed(() => currentMetrics.value.map((entry) => entry.key))

  const modelIds = computed(() => (catalogs.value ? [...catalogs.value.catalogs.keys()] : []))

  async function load(store: MetricBucketStore | null) {
    loadedFrom = store
    catalogs.value = null
    page.value = 0
    loading.value = !!store
    if (!store) return
    try {
      const loaded = await store.loadCatalogs()
      if (loadedFrom === store) catalogs.value = markRaw(loaded)
    } catch {
      if (loadedFrom === store) toast.add(simpleErrorToast('Failed to load dynamic metrics'))
    } finally {
      if (loadedFrom === store) loading.value = false
    }
  }

  /** Re-reads the catalogs of live experiments; open charts re-read only what changed. */
  async function refresh(
    ids: string[] = modelIds.value,
  ): Promise<Map<string, ExperimentReadError>> {
    const store = evalsStore.metricBucketStore
    if (!store || store.disposed) return new Map()
    const failures = await store.refreshCatalogs(ids)
    const refreshed = await store.loadCatalogs()
    if (loadedFrom === store) catalogs.value = markRaw(refreshed)
    return failures
  }

  function setFilter(value: string) {
    filter.value = value
    page.value = 0
  }

  function setPage(value: number) {
    page.value = value
  }

  function reset() {
    loadedFrom = null
    catalogs.value = null
    loading.value = false
    filter.value = ''
    page.value = 0
  }

  return {
    catalogs,
    statuses,
    loading,
    filter,
    page,
    metricsNames,
    filteredMetrics,
    currentMetrics,
    currentMetricsNames,
    modelIds,
    load,
    refresh,
    setFilter,
    setPage,
    reset,
  }
})
