import { defineStore } from 'pinia'
import { computed, markRaw, ref, shallowRef, toRaw } from 'vue'
import type {
  EvalsInfo,
  ExperimentSnapshotProvider,
  TraceSpan,
  BaseTraceInfo,
  SpanPayload,
} from '@/interfaces/interfaces'
import type { DatasetData } from '@/components/evals/evals.interface'
import { INITIAL_PARAMS } from './evals.data'
import { useAnnotationsStore } from '../annotations'
import { useToast } from 'primevue'
import { showReadErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { MetricBucketStore } from '@/metric-buckets/MetricBucketStore'

export function getSpansTimes(spans: Omit<TraceSpan, 'children'>[]): {
  minTime: number | null
  maxTime: number | null
} {
  if (!spans.length) return { minTime: null, maxTime: null }
  return spans.reduce(
    (acc, span) => ({
      minTime: Math.min(acc.minTime, span.start_time_unix_nano),
      maxTime: Math.max(acc.maxTime, span.end_time_unix_nano),
    }),
    { minTime: Infinity, maxTime: -Infinity },
  )
}

// Payloads can be megabytes each: keep only the most recently loaded ones.
const SPAN_PAYLOAD_CACHE_SIZE = 100

function sameModelIds(left: readonly string[] | null, right: readonly string[] | null): boolean {
  if (!left || !right) return left === right
  return left.length === right.length && left.every((modelId, index) => modelId === right[index])
}

export const useEvalsStore = defineStore('evals', () => {
  const annotationsStore = useAnnotationsStore()
  const toast = useToast()

  const currentEvalData = ref<EvalsInfo[] | null>(null)
  const provider = ref<ExperimentSnapshotProvider | null>(null)
  // One per provider: charts share its catalogs and bucket cache; replaced with the provider.
  const metricBucketStore = shallowRef<MetricBucketStore | null>(null)
  const selectedEval = ref<{ datasetId: string; evalId: string } | undefined>(undefined)
  const selectedTrace = ref<(BaseTraceInfo & { artifactId: string }) | null>(null)
  const datasets = ref<DatasetData[] | null>(null)
  const loading = ref(false)
  const evalsIdsList = ref<string[]>([])
  const currentEvalDataLoading = ref(false)
  // Bumped when a refresh replaced the rows: values a dataset reads apart from them, such as
  // its average scores, follow.
  const refreshedVersion = ref(0)
  const spanPayloads = new Map<string, SpanPayload>()
  const spanPayloadRequests = new Map<string, Promise<SpanPayload>>()
  // Bumped when the payloads are forgotten, so an open span reads its payload again.
  const spanPayloadsVersion = ref(0)
  // Bumped on reset and on a provider change. The store outlives its view and Flow does not
  // cancel reads, so an answer to a read that started before must be dropped.
  let datasetsVersion = 0
  // The parameters each dataset's rows were read with. A failed reload leaves rows for older
  // ones, and a next page would append the new parameters' first page to them.
  const listedParamsJson = new Map<string, string>()

  const getProvider = computed(() => {
    if (!provider.value) throw new Error('Provider not found')
    return provider.value
  })

  // For cleanup on close: the next view may have reset the provider already.
  const hasProvider = computed(() => !!provider.value)

  const currentEvalId = computed(() => {
    return selectedEval.value?.evalId ?? ''
  })

  /**
   * `modelIds`: the provider's experiments. A provider initialised again with others (the
   * same worker proxy for another comparison) gets a new store, as its catalogs changed.
   */
  function setProvider(newProvider: ExperimentSnapshotProvider, modelIds?: string[]) {
    const rawProvider = toRaw(newProvider)
    const store = metricBucketStore.value
    if (
      provider.value &&
      toRaw(provider.value) === rawProvider &&
      store &&
      sameModelIds(store.modelIds, modelIds ?? null)
    ) {
      return
    }
    datasetsVersion++
    provider.value = newProvider
    clearSpanPayloads()
    store?.dispose()
    metricBucketStore.value = markRaw(new MetricBucketStore(rawProvider, { modelIds }))
  }

  /** Frees the store's cached buckets; the next `setProvider` creates a new one. */
  function disposeMetricBucketStore() {
    metricBucketStore.value?.dispose()
    metricBucketStore.value = null
  }

  function resetProvider() {
    datasetsVersion++
    provider.value = null
    clearSpanPayloads()
    disposeMetricBucketStore()
  }

  function spanPayloadKey(modelId: string, traceId: string, spanId: string) {
    return JSON.stringify([modelId, traceId, spanId])
  }

  function getCachedSpanPayload(
    modelId: string,
    traceId: string,
    spanId: string,
  ): SpanPayload | undefined {
    return spanPayloads.get(spanPayloadKey(modelId, traceId, spanId))
  }

  /** Concurrent calls for one span share a request; a failed request is not cached. */
  function loadSpanPayload(modelId: string, traceId: string, spanId: string) {
    const key = spanPayloadKey(modelId, traceId, spanId)
    const cached = spanPayloads.get(key)
    if (cached) return Promise.resolve(cached)
    const pending = spanPayloadRequests.get(key)
    if (pending) return pending
    const request = getProvider.value.getSpanPayload(modelId, traceId, spanId).then(
      (payload) => {
        if (spanPayloadRequests.get(key) === request) {
          spanPayloadRequests.delete(key)
          rememberSpanPayload(key, payload)
        }
        return payload
      },
      (error: unknown) => {
        if (spanPayloadRequests.get(key) === request) spanPayloadRequests.delete(key)
        throw error
      },
    )
    spanPayloadRequests.set(key, request)
    return request
  }

  function rememberSpanPayload(key: string, payload: SpanPayload) {
    spanPayloads.set(key, payload)
    if (spanPayloads.size <= SPAN_PAYLOAD_CACHE_SIZE) return
    const oldest = spanPayloads.keys().next().value
    if (oldest !== undefined) spanPayloads.delete(oldest)
  }

  /** A live store can replace a span with the same ids, so a refresh forgets the payloads. */
  function clearSpanPayloads() {
    spanPayloads.clear()
    spanPayloadRequests.clear()
    spanPayloadsVersion.value++
  }

  function setCurrentEvalData(data: EvalsInfo[]) {
    if (!data[0]) return
    selectedEval.value = { datasetId: data[0].dataset_id, evalId: data[0].id }
    currentEvalData.value = data
  }

  function getTraceId(modelId: string, datasetId: string, evalId: string) {
    return getProvider.value.getTraceId({ modelId, datasetId, evalId })
  }

  async function getEvalSpansTree(
    modelId: string,
    datasetId: string,
    evalId: string,
  ): Promise<BaseTraceInfo> {
    const traceId = await getTraceId(modelId, datasetId, evalId)
    if (!traceId) return { count: 0, minTime: null, maxTime: null, tree: [], traceId: '' }
    return getTraceSpansTree(modelId, traceId)
  }

  async function getTraceSpansTree(modelId: string, traceId: string): Promise<BaseTraceInfo> {
    const spansList = await getProvider.value.getTraceSpans(modelId, traceId)
    if (!spansList) return { count: 0, minTime: null, maxTime: null, tree: [], traceId }
    const count = spansList.length
    const { minTime, maxTime } = getSpansTimes(spansList)
    const tree = await getProvider.value.buildSpanTree(spansList)
    return { count, minTime, maxTime, tree, traceId }
  }

  function setSelectedTrace(trace: BaseTraceInfo, artifactId: string) {
    selectedTrace.value = { ...trace, artifactId }
  }

  function setDatasetData(value: DatasetData) {
    if (!datasets.value) {
      datasets.value = [value]
      return
    }
    const existingDatasetIndex = datasets.value.findIndex(
      (item) => item.params.dataset_id === value.params.dataset_id,
    )
    if (existingDatasetIndex !== -1) {
      datasets.value[existingDatasetIndex] = value
    } else {
      datasets.value.push(value)
    }
  }

  async function initDatasets(limit?: number) {
    const version = datasetsVersion
    const datasetsIds = await getProvider.value.getUniqueDatasetsIds()
    if (version !== datasetsVersion) return
    const promises = datasetsIds.map((datasetId) => initDataset(datasetId, limit))
    await Promise.all(promises)
  }

  async function initDataset(datasetId: string, limit?: number) {
    const version = datasetsVersion
    const isCurrent = () => version === datasetsVersion
    const columns = await getProvider.value.getEvalsColumns(datasetId)
    if (!isCurrent()) return
    const existing = datasets.value?.find((item) => item.params.dataset_id === datasetId)
    const effectiveLimit = limit ?? existing?.params.limit ?? INITIAL_PARAMS.limit
    // A reload after an annotation change keeps the dataset's search, filters and sort.
    const params = {
      ...INITIAL_PARAMS,
      ...(existing && toRaw(existing.params)),
      dataset_id: datasetId,
      limit: effectiveLimit,
    }
    await getProvider.value.resetDatasetPage(datasetId)
    if (!isCurrent()) return
    const data = await getProvider.value.getNextEvalsByDatasetId(params)
    if (!isCurrent()) return
    await annotationsStore.getEvalsDatasetAnnotationsSummary(datasetId)
    if (!isCurrent()) return
    setDatasetData({ columns, data, params })
    listedParamsJson.set(datasetId, JSON.stringify(params))
  }

  function isDatasetCurrent(datasetId: string) {
    const dataset = datasets.value?.find((item) => item.params.dataset_id === datasetId)
    return !!dataset && listedParamsJson.get(datasetId) === JSON.stringify(toRaw(dataset.params))
  }

  async function getNextDatasetPage(datasetId: string, reset: boolean = false) {
    const dataset = datasets.value?.find((item) => item.params.dataset_id === datasetId)
    if (!dataset) throw new Error('Dataset not found')
    const version = datasetsVersion
    const params = toRaw(dataset.params)
    const paramsJson = JSON.stringify(params)
    // Rows for older sort or filters are dropped: the reload for the current ones follows.
    const isCurrent = () =>
      version === datasetsVersion && paramsJson === JSON.stringify(toRaw(dataset.params))
    if (reset) {
      listedParamsJson.delete(datasetId)
      await getProvider.value.resetDatasetPage(datasetId)
    }
    if (!isCurrent()) return
    const newData = await getProvider.value.getNextEvalsByDatasetId(params)
    if (!isCurrent()) return
    dataset.data = reset ? newData : [...dataset.data, ...newData]
    if (reset) listedParamsJson.set(datasetId, paramsJson)
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function reset() {
    datasetsVersion++
    resetSelectedTrace()
    resetCurrentEvalData()
    resetDatasets()
    setLoading(false)
  }

  function resetCurrentEvalData() {
    currentEvalData.value = null
    resetEvalsIdsList()
    setCurrentEvalDataLoading(false)
  }

  function resetSelectedTrace() {
    selectedTrace.value = null
  }

  function resetDatasets() {
    datasets.value = null
    listedParamsJson.clear()
  }

  async function refresh() {
    clearSpanPayloads()
    if (loading.value) return
    const version = datasetsVersion
    setLoading(true)
    try {
      if (!datasets.value) return
      const paramsByDataset = datasets.value.map((item) => toRaw(item.params))
      const promises = paramsByDataset.map((item) =>
        getProvider.value.getFreshEvalsByDatasetId(item),
      )
      const data = await Promise.all(promises)
      if (version !== datasetsVersion || !datasets.value) return
      datasets.value = datasets.value.map((item, index) => {
        if (!data[index]) return item
        return { ...item, data: data[index] }
      })
      refreshedVersion.value++
      const annotationsPromises = paramsByDataset.map((item) => {
        return annotationsStore.getEvalsDatasetAnnotationsSummary(item.dataset_id)
      })
      await Promise.all(annotationsPromises)
    } catch (error) {
      showReadErrorToast(toast, error, getErrorMessage(error))
    } finally {
      // After a reset the loading flag belongs to the next experiment's view.
      if (version === datasetsVersion) setLoading(false)
    }
  }

  function getDatasetFilters(datasetId: string) {
    const info = datasets.value?.find((item) => item.params.dataset_id === datasetId)
    return info?.params?.filters ?? []
  }

  function setEvalsIdsList(evalsIds: string[]) {
    evalsIdsList.value = evalsIds
  }

  function resetEvalsIdsList() {
    evalsIdsList.value = []
  }

  function setCurrentEvalDataLoading(value: boolean) {
    currentEvalDataLoading.value = value
  }

  return {
    currentEvalData,
    setProvider,
    setCurrentEvalData,
    resetCurrentEvalData,
    reset,
    getTraceId,
    selectedEval,
    getEvalSpansTree,
    setSelectedTrace,
    resetSelectedTrace,
    selectedTrace,
    getTraceSpansTree,
    getCachedSpanPayload,
    loadSpanPayload,
    clearSpanPayloads,
    spanPayloadsVersion,
    resetProvider,
    disposeMetricBucketStore,
    getProvider,
    hasProvider,
    metricBucketStore,
    initDatasets,
    initDataset,
    datasets,
    getNextDatasetPage,
    isDatasetCurrent,
    loading,
    setLoading,
    refresh,
    refreshedVersion,
    getDatasetFilters,
    setEvalsIdsList,
    evalsIdsList,
    currentEvalId,
    currentEvalDataLoading,
    setCurrentEvalDataLoading,
  }
})
