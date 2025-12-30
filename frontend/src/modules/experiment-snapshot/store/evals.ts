import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { EvalsDatasets, EvalsInfo, ExperimentSnapshotProvider } from '../interfaces/interfaces'

export const useEvalsStore = defineStore('evals', () => {
  const evals = ref<EvalsDatasets | null>(null)
  const currentEvalData = ref<EvalsInfo[] | null>(null)
  const provider = ref<ExperimentSnapshotProvider | null>(null)
  const currentDatasetId = ref<string | null>(null)
  const currentEvalId = ref<string | null>(null)
  const minSpanTime = ref<number | null>(null)
  const maxSpanTime = ref<number | null>(null)
  const spansCount = ref<number | null>(null)

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
    currentDatasetId.value = datasetId
    currentEvalId.value = evalId
    currentEvalData.value = evals.value[datasetId]?.filter((item) => item.id === evalId)
  }

  function resetCurrentEvalData() {
    currentEvalData.value = null
  }

  function reset() {
    evals.value = null
    minSpanTime.value = null
    maxSpanTime.value = null
    spansCount.value = null
  }

  function getTraceId(modelId: string) {
    if (!currentEvalData.value || !currentDatasetId.value || !currentEvalId.value) return null
    return getProvider.value.getTraceId({
      modelId,
      datasetId: currentDatasetId.value,
      evalId: currentEvalId.value,
    })
  }

  async function getSpansTree(modelId: string) {
    if (!currentEvalData.value || !currentDatasetId.value || !currentEvalId.value) return []
    const spansList = await getProvider.value.getSpansList({
      modelId,
      datasetId: currentDatasetId.value,
      evalId: currentEvalId.value,
    })
    if (!spansList) return []
    spansCount.value = spansList.length
    let minTime: number | null = null
    let maxTime: number | null = null
    spansList.forEach((span) => {
      if (minTime === null) {
        minTime = span.start_time_unix_nano
      } else {
        minTime = Math.min(minTime, span.start_time_unix_nano)
      }
      if (maxTime === null) {
        maxTime = span.end_time_unix_nano
      } else {
        maxTime = Math.max(maxTime, span.end_time_unix_nano)
      }
    })
    minSpanTime.value = minTime
    maxSpanTime.value = maxTime
    return getProvider.value.buildSpanTree(spansList)
  }

  return {
    evals,
    currentEvalData,
    minSpanTime,
    maxSpanTime,
    spansCount,
    setProvider,
    setEvals,
    setCurrentEvalData,
    resetCurrentEvalData,
    getSpansTree,
    reset,
    getTraceId,
  }
})
