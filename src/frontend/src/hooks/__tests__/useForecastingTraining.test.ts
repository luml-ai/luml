import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import type { ForecastingTrainingData } from '@/lib/data-processing/interfaces'

const { toastAddMock, downloadMock } = vi.hoisted(() => ({
  toastAddMock: vi.fn(),
  downloadMock: vi.fn(),
}))

vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: toastAddMock }) }))
vi.mock('@/helpers/helpers', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, downloadFileFromBlob: downloadMock }
})
vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: {
    startTraining: vi.fn(),
    startPredict: vi.fn(),
    deallocateModels: vi.fn().mockResolvedValue([]),
  },
}))

import { useForecastingTraining } from '../useForecastingTraining'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { WEBWORKER_ROUTES_ENUM } from '@/lib/data-processing/interfaces'

const startTrainingMock = vi.mocked(DataProcessingWorker.startTraining)
const startPredictMock = vi.mocked(DataProcessingWorker.startPredict)
const deallocateMock = vi.mocked(DataProcessingWorker.deallocateModels)

const trainingData: ForecastingTrainingData = {
  status: 'success',
  model_id: 'model-1',
  train_metrics: { MAE: 1, RMSE: 2, MAPE: 0.1, R2: 0.8 },
  test_metrics: { MAE: 2, RMSE: 3, MAPE: null, R2: 0.7, SC_SCORE: 0.7 },
  model_config: {
    frequency: 'month',
    seasonal_period: 12,
    aggregation: 'mean',
    date_col: 'date',
    target_col: 'sales',
    aux_cols: [],
    known_future_cols: [],
    min_history: 15,
    series: {},
  },
  chart: { split_date: null, series: {} },
  model: {},
}

const trainPayload = {
  data: { date: ['2020-01-01'], sales: [1] },
  date_col: 'date',
  target_col: 'sales',
  aux_cols: [],
  known_future_cols: [],
  frequency: 'month' as const,
  preview_horizon: null,
  aggregation: 'mean' as const,
}

function setupHook() {
  let hook!: ReturnType<typeof useForecastingTraining>
  const Host = defineComponent({
    setup() {
      hook = useForecastingTraining()
      return () => null
    },
  })
  const wrapper = mount(Host)
  return { hook, wrapper }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useForecastingTraining metric rows', () => {
  it('formats [MAE, RMSE, MAPE, R2] rows, with an em dash for null values', () => {
    const { hook } = setupHook()
    hook.trainingData.value = trainingData

    expect(hook.getTestMetrics.value).toEqual(['2.00', '3.00', '—', '0.70'])
    expect(hook.getTrainingMetrics.value).toEqual(['1.00', '2.00', '0.10', '0.80'])
    expect(hook.getTotalScore.value).toBe(70)
  })

  it('returns empty rows before any training', () => {
    const { hook } = setupHook()
    expect(hook.getTestMetrics.value).toEqual([])
    expect(hook.getTrainingMetrics.value).toEqual([])
  })
})

describe('useForecastingTraining startTraining', () => {
  it('stores the result and builds the model blob on success', async () => {
    startTrainingMock.mockResolvedValue({ ...trainingData, model: { 0: 1, 1: 2, 2: 3 } })
    const { hook } = setupHook()

    await hook.startTraining(trainPayload)

    expect(startTrainingMock).toHaveBeenCalledWith(
      trainPayload,
      WEBWORKER_ROUTES_ENUM.FORECASTING_TRAIN,
    )
    expect(hook.isTrainingSuccess.value).toBe(true)
    expect(hook.isLoading.value).toBe(false)
    expect(hook.trainingModelId.value).toBe('model-1')
    expect(hook.trainingData.value?.model_id).toBe('model-1')
    expect(hook.modelBlob.value?.size).toBe(3)
    expect(toastAddMock).not.toHaveBeenCalled()
  })

  it('raises an error toast and stays unsuccessful on a worker error payload', async () => {
    startTrainingMock.mockResolvedValue({
      status: 'error',
      error_message: 'Not enough data to train',
    })
    const { hook } = setupHook()

    await hook.startTraining(trainPayload)

    expect(hook.isTrainingSuccess.value).toBe(false)
    expect(hook.isLoading.value).toBe(false)
    expect(hook.trainingData.value).toBeNull()
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'Not enough data to train' }),
    )
  })
})

describe('useForecastingTraining startPredict', () => {
  const request = { model_id: 'model-1', history: [{ date: '2020-01-01', sales: 1 }], horizon: 2 }

  it('returns the forecast without toggling the training modal', async () => {
    startPredictMock.mockResolvedValue({ status: 'success', forecast: [{ date: '2020-02-01' }] })
    const { hook } = setupHook()

    const result = await hook.startPredict(request)

    expect(startPredictMock).toHaveBeenCalledWith(
      request,
      WEBWORKER_ROUTES_ENUM.FORECASTING_PREDICT,
    )
    expect(result?.forecast).toHaveLength(1)
    expect(hook.isLoading.value).toBe(false)
  })

  it('swallows a worker error into a toast and resolves undefined', async () => {
    startPredictMock.mockResolvedValue({ status: 'error', error_message: 'future is missing' })
    const { hook } = setupHook()

    const result = await hook.startPredict(request)

    expect(result).toBeUndefined()
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'future is missing' }),
    )
  })
})

describe('useForecastingTraining model download & cleanup', () => {
  it('downloads the trained model blob as a .luml file', async () => {
    startTrainingMock.mockResolvedValue({ ...trainingData, model: { 0: 1 } })
    const { hook } = setupHook()
    await hook.startTraining(trainPayload)

    hook.downloadModel()

    expect(downloadMock).toHaveBeenCalledWith(
      hook.modelBlob.value,
      expect.stringMatching(/^forecasting_\d+\.luml$/),
    )
  })

  it('throws when there is no model to download', () => {
    const { hook } = setupHook()
    expect(() => hook.downloadModel()).toThrow('no model')
  })

  it('deallocates every trained model, including on unmount', async () => {
    startTrainingMock.mockResolvedValue({ ...trainingData, model: {} })
    const { hook, wrapper } = setupHook()
    await hook.startTraining(trainPayload)

    await hook.deleteModels()
    expect(deallocateMock).toHaveBeenCalledWith(
      ['model-1'],
      WEBWORKER_ROUTES_ENUM.FORECASTING_DEALLOCATE,
    )

    deallocateMock.mockClear()
    wrapper.unmount()
    expect(deallocateMock).toHaveBeenCalledWith(
      ['model-1'],
      WEBWORKER_ROUTES_ENUM.FORECASTING_DEALLOCATE,
    )
  })

  it('skips deallocation when nothing was trained', async () => {
    const { hook } = setupHook()
    await hook.deleteModels()
    expect(deallocateMock).not.toHaveBeenCalled()
  })
})
