import { describe, it, expect, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import type { ForecastingTrainingData } from '@/lib/data-processing/interfaces'

vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: {
    startTraining: vi.fn(),
    startPredict: vi.fn(),
    deallocateModels: vi.fn().mockResolvedValue([]),
  },
}))

import { useForecastingTraining } from '../useForecastingTraining'

const trainingData: ForecastingTrainingData = {
  status: 'success',
  model_id: 'model-1',
  train_metrics: { MAE: 1, RMSE: 2, MAPE: 0.1, R2: 0.8 },
  test_metrics: { MAE: 2, RMSE: 3, MAPE: null, R2: 0.7, SC_SCORE: 0.7 },
  model_config: {
    frequency: 'month',
    seasonal_period: 12,
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

function setupHook() {
  let hook!: ReturnType<typeof useForecastingTraining>
  const Host = defineComponent({
    setup() {
      hook = useForecastingTraining()
      return () => null
    },
  })
  mount(Host)
  return hook
}

describe('useForecastingTraining metric rows', () => {
  it('formats [MAE, RMSE, MAPE, R2] rows, with an em dash for null values', () => {
    const hook = setupHook()
    hook.trainingData.value = trainingData

    expect(hook.getTestMetrics.value).toEqual(['2.00', '3.00', '—', '0.70'])
    expect(hook.getTrainingMetrics.value).toEqual(['1.00', '2.00', '0.10', '0.80'])
    expect(hook.getTotalScore.value).toBe(70)
  })

  it('returns empty rows before any training', () => {
    const hook = setupHook()
    expect(hook.getTestMetrics.value).toEqual([])
    expect(hook.getTrainingMetrics.value).toEqual([])
  })
})
