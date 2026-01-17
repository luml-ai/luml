import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type {
  EvalsDatasets,
  EvalsInfo,
  ExperimentSnapshotProvider,
  TraceSpan,
  BaseTraceInfo,
} from '../interfaces/interfaces'

export const useEvalsStore = defineStore('evals', () => {
  const evals = ref<EvalsDatasets | null>(null)
  const currentEvalData = ref<EvalsInfo[] | null>(null)
  const provider = ref<ExperimentSnapshotProvider | null>(null)
  const selectedEval = ref<{ datasetId: string; evalId: string } | undefined>(undefined)
  const selectedTrace = ref<BaseTraceInfo | null>(null)

  const getProvider = computed(() => {
    if (!provider.value) throw new Error('Provider not found')
    return provider.value
  })

  function setProvider(newProvider: ExperimentSnapshotProvider) {
    provider.value = newProvider
  }

  async function setEvals(signal?: AbortSignal) {
    evals.value = await getProvider.value.getEvalsList(signal)
  }

  function setCurrentEvalData(datasetId: string, evalId: string) {
    if (!evals.value) return
    selectedEval.value = { datasetId, evalId }
    currentEvalData.value = evals.value[datasetId]?.filter((item) => item.id === evalId)
  }

  function resetCurrentEvalData() {
    currentEvalData.value = null
  }

  function reset() {
    evals.value = null
    resetSelectedTrace()
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

  function setSelectedTrace(trace: BaseTraceInfo) {
    selectedTrace.value = trace
  }

  function resetSelectedTrace() {
    selectedTrace.value = null
  }

  async function getUniqueTraceIds(modelId: string) {
    return getProvider.value.getUniqueTraceIds(modelId)
  }

  return {
    evals,
    currentEvalData,
    setProvider,
    setEvals,
    setCurrentEvalData,
    resetCurrentEvalData,
    reset,
    getTraceId,
    selectedEval,
    getEvalSpansTree,
    setSelectedTrace,
    resetSelectedTrace,
    selectedTrace,
    getUniqueTraceIds,
    getTraceSpansTree,
  }
})
