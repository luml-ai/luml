import { defineStore } from 'pinia'
import { computed, ref, toRaw } from 'vue'
import type {
  EvalsInfo,
  ExperimentSnapshotProvider,
  TraceSpan,
  BaseTraceInfo,
} from '@experiments/interfaces/interfaces'
import type { DatasetData } from '@experiments/components/evals/evals.interface'
import { INITIAL_PARAMS } from './evals.data'
import { useAnnotationsStore } from '../annotations'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@experiments/lib/primevue/data/toasts'
import { getErrorMessage } from '@experiments/helpers/helpers'

export const useEvalsStore = defineStore('evals', () => {
  const annotationsStore = useAnnotationsStore()
  const toast = useToast()

  const currentEvalData = ref<EvalsInfo[] | null>(null)
  const provider = ref<ExperimentSnapshotProvider | null>(null)
  const selectedEval = ref<{ datasetId: string; evalId: string } | undefined>(undefined)
  const selectedTrace = ref<(BaseTraceInfo & { artifactId: string }) | null>(null)
  const datasets = ref<DatasetData[] | null>(null)
  const loading = ref(false)

  const getProvider = computed(() => {
    if (!provider.value) throw new Error('Provider not found')
    return provider.value
  })

  function setProvider(newProvider: ExperimentSnapshotProvider) {
    provider.value = newProvider
  }

  function resetProvider() {
    provider.value = null
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

  function getSpansTimes(spans: Omit<TraceSpan, 'children'>[]) {
    return spans.reduce(
      (acc, span: Omit<TraceSpan, 'children'>) => ({
        minTime: Math.min(acc.minTime, span.start_time_unix_nano),
        maxTime: Math.max(acc.maxTime, span.end_time_unix_nano),
      }),
      { minTime: Infinity, maxTime: -Infinity },
    )
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

  async function initDatasets() {
    const datasetsIds = await getProvider.value.getUniqueDatasetsIds()
    const promises = datasetsIds.map((datasetId) => initDataset(datasetId))
    await Promise.all(promises)
  }

  async function initDataset(datasetId: string) {
    const columns = await getProvider.value.getEvalsColumns(datasetId)
    const params = {
      ...INITIAL_PARAMS,
      dataset_id: datasetId,
    }
    await getProvider.value.resetDatasetPage(datasetId)
    const data = await getProvider.value.getNextEvalsByDatasetId(params)
    await annotationsStore.getEvalsDatasetAnnotationsSummary(datasetId)
    setDatasetData({ columns, data, params })
  }

  async function getNextDatasetPage(datasetId: string, reset: boolean = false) {
    const dataset = datasets.value?.find((item) => item.params.dataset_id === datasetId)
    if (!dataset) throw new Error('Dataset not found')
    const params = toRaw(dataset.params)
    if (reset) await getProvider.value.resetDatasetPage(datasetId)
    const newData = await getProvider.value.getNextEvalsByDatasetId(params)
    dataset.data = reset ? newData : [...dataset.data, ...newData]
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function reset() {
    resetSelectedTrace()
    resetCurrentEvalData()
    resetDatasets()
    setLoading(false)
  }

  function resetCurrentEvalData() {
    currentEvalData.value = null
  }

  function resetSelectedTrace() {
    selectedTrace.value = null
  }

  function resetDatasets() {
    datasets.value = null
  }

  async function refresh() {
    if (loading.value) return
    setLoading(true)
    try {
      if (!datasets.value) return
      const paramsByDataset = datasets.value.map((item) => toRaw(item.params))
      const promises = paramsByDataset.map((item) =>
        getProvider.value.getFreshEvalsByDatasetId(item),
      )
      const data = await Promise.all(promises)
      datasets.value = datasets.value.map((item, index) => {
        if (!data[index]) return item
        return { ...item, data: data[index] }
      })
      const annotationsPromises = paramsByDataset.map((item) => {
        return annotationsStore.getEvalsDatasetAnnotationsSummary(item.dataset_id)
      })
      await Promise.all(annotationsPromises)
    } catch (error) {
      toast.add(simpleErrorToast(getErrorMessage(error)))
    } finally {
      setLoading(false)
    }
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
    resetProvider,
    getProvider,
    initDatasets,
    initDataset,
    datasets,
    getNextDatasetPage,
    loading,
    setLoading,
    refresh,
  }
})
