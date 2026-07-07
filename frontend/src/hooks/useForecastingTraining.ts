import {
  WEBWORKER_ROUTES_ENUM,
  type ForecastingChart,
  type ForecastingMetrics,
  type ForecastingModelConfig,
  type ForecastingPredictRequest,
  type ForecastingPredictResponse,
  type ForecastingPredictSuccess,
  type ForecastingTrainMetrics,
  type ForecastingTrainPayload,
  type ForecastingTrainingData,
  type ForecastingTrainResponse,
} from '@/lib/data-processing/interfaces'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { predictErrorToast, trainingErrorToast } from '@/lib/primevue/data/toasts'
import { downloadFileFromBlob, getFormattedMetric, toPercent } from '@/helpers/helpers'

export const useForecastingTraining = () => {
  const toast = useToast()

  const isLoading = ref(false)
  const isTrainingSuccess = ref(false)
  const trainingData = ref<ForecastingTrainingData | null>(null)
  const modelsIdList = ref<string[]>([])
  const trainingModelId = ref<string | null>(null)
  const modelBlob = ref<Blob | null>(null)

  const getTotalScore = computed(() =>
    trainingData.value ? toPercent(trainingData.value.test_metrics.SC_SCORE) : 0,
  )
  // Formatted [MAE, RMSE, MAPE, R2] rows matching getMetricsCards(forecasting_v1) titles.
  const getTestMetrics = computed<string[]>(() =>
    formatMetricsRow(trainingData.value?.test_metrics ?? null),
  )
  const getTrainingMetrics = computed<string[]>(() =>
    formatMetricsRow(trainingData.value?.train_metrics ?? null),
  )
  const getModelConfig = computed<ForecastingModelConfig | null>(
    () => trainingData.value?.model_config ?? null,
  )
  const getChart = computed<ForecastingChart | null>(() => trainingData.value?.chart ?? null)

  function formatMetricsRow(
    metrics: ForecastingMetrics | ForecastingTrainMetrics | null,
  ): string[] {
    if (!metrics) return []
    return [metrics.MAE, metrics.RMSE, metrics.MAPE, metrics.R2].map((value) =>
      value === null || value === undefined ? '—' : getFormattedMetric(value),
    )
  }

  async function startTraining(payload: ForecastingTrainPayload) {
    isLoading.value = true
    isTrainingSuccess.value = false
    try {
      const result = await DataProcessingWorker.startTraining<ForecastingTrainResponse>(
        JSON.parse(JSON.stringify(payload)),
        WEBWORKER_ROUTES_ENUM.FORECASTING_TRAIN,
      )

      if (result.status === 'success') {
        trainingData.value = result
        trainingModelId.value = result.model_id
        modelsIdList.value.push(result.model_id)
        saveModel(result.model)
        isTrainingSuccess.value = true
      } else {
        throw new Error(result?.error_message || 'Unknown error')
      }
    } catch (error) {
      isTrainingSuccess.value = false
      toast.add(trainingErrorToast(error instanceof Error ? error.message : String(error)))
    } finally {
      isLoading.value = false
    }
  }

  async function startPredict(
    request: ForecastingPredictRequest,
  ): Promise<ForecastingPredictSuccess | undefined> {
    // Re-forecast is a fixed-parameter predict, not training — it must not raise
    // the shared `isLoading` training modal. Callers show their own light status.
    try {
      const result = await DataProcessingWorker.startPredict<ForecastingPredictResponse>(
        JSON.parse(JSON.stringify(request)),
        WEBWORKER_ROUTES_ENUM.FORECASTING_PREDICT,
      )

      if (result.status === 'success') {
        return result
      } else {
        throw new Error(result?.error_message || 'Unknown error')
      }
    } catch (error) {
      toast.add(predictErrorToast(error instanceof Error ? error.message : String(error)))
    }
  }

  function saveModel(model: object) {
    const modelBytes = new Uint8Array(Object.values(model))
    modelBlob.value = new Blob([modelBytes])
  }

  function downloadModel() {
    if (!modelBlob.value) throw new Error('There is no model to download')

    const filename = `forecasting_${Date.now()}.luml`
    downloadFileFromBlob(modelBlob.value, filename)
  }

  async function deleteModels() {
    if (!modelsIdList.value.length) return
    await DataProcessingWorker.deallocateModels(
      modelsIdList.value,
      WEBWORKER_ROUTES_ENUM.FORECASTING_DEALLOCATE,
    )
  }

  onBeforeUnmount(() => {
    deleteModels()
  })

  return {
    isLoading,
    isTrainingSuccess,
    trainingData,
    trainingModelId,
    modelBlob,
    getTotalScore,
    getTestMetrics,
    getTrainingMetrics,
    getModelConfig,
    getChart,
    startTraining,
    startPredict,
    downloadModel,
    deleteModels,
  }
}
