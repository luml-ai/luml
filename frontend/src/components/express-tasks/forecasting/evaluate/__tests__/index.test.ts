import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { nextTick } from 'vue'
import type {
  ForecastPredictedRecord,
  ForecastingModelConfig,
} from '@/lib/data-processing/interfaces'

const { downloadMock } = vi.hoisted(() => ({ downloadMock: vi.fn() }))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/helpers/helpers', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, downloadFileFromBlob: downloadMock }
})

import Evaluate from '../index.vue'

const baseConfig: ForecastingModelConfig = {
  frequency: 'month',
  seasonal_period: 12,
  date_col: 'date',
  target_col: 'sales',
  aux_cols: [],
  known_future_cols: [],
  min_history: 15,
  series: {
    sales: { order: [1, 1, 1], seasonal_order: [0, 1, 0, 12], trend: 'n', min_history: 15 },
  },
}

const baseChart = {
  split_date: '2020-03-01',
  series: {
    sales: {
      actuals: [
        { date: '2020-01-01', value: 10 },
        { date: '2020-02-01', value: 12 },
        { date: '2020-03-01', value: 14 },
      ],
    },
  },
}

const baseHistory = [
  { date: '2020-01-01', sales: 10 },
  { date: '2020-02-01', sales: 12 },
  { date: '2020-03-01', sales: 14 },
]

const baseForecast: ForecastPredictedRecord[] = [
  { date: '2020-04-01', predicted_sales: 20, predicted_sales_lower: 18, predicted_sales_upper: 22 },
  { date: '2020-05-01', predicted_sales: 21, predicted_sales_lower: 19, predicted_sales_upper: 23 },
  { date: '2020-06-01', predicted_sales: 22, predicted_sales_lower: 20, predicted_sales_upper: 24 },
]

const DButton = {
  name: 'DButton',
  props: ['label', 'disabled', 'severity'],
  emits: ['click'],
  template: `<button :disabled="disabled" @click="$emit('click')"><slot>{{ label }}</slot></button>`,
}

const modelStub = (name: string) => ({
  name,
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div />',
})

const stubs = {
  apexchart: true,
  DatePicker: modelStub('DatePicker'),
  SelectButton: modelStub('SelectButton'),
  ForecastChart: {
    name: 'ForecastChart',
    props: ['chart', 'targetCol', 'knownFutureCols', 'prediction', 'supplied'],
    template: '<div data-testid="forecast-chart" />',
  },
  FutureValuesEditor: {
    name: 'FutureValuesEditor',
    props: ['dates', 'columns', 'dateCol', 'frequency'],
    emits: ['change'],
    template: '<div data-testid="future-editor" />',
  },
}

type Overrides = {
  modelConfig?: ForecastingModelConfig
  history?: Record<string, string | number>[]
  testMetrics?: Record<string, number | null>
  forecast?: ForecastPredictedRecord[]
  failPredict?: boolean
}

function mountEvaluate(over: Overrides = {}) {
  const predict = vi
    .fn()
    .mockResolvedValue(
      over.failPredict ? undefined : { status: 'success', forecast: over.forecast ?? baseForecast },
    )
  const downloadModel = vi.fn()
  const wrapper = mount(Evaluate, {
    props: {
      totalScore: 70,
      testMetrics: over.testMetrics ?? { MAE: 2, RMSE: 3, MAPE: null, R2: 0.7, SC_SCORE: 0.7 },
      trainMetrics: { MAE: 1, RMSE: 2, MAPE: 0.1, R2: 0.8 },
      modelConfig: over.modelConfig ?? baseConfig,
      chart: baseChart,
      history: over.history ?? baseHistory,
      modelId: 'model-1',
      predict,
      downloadModel,
    },
    global: { components: { DButton }, stubs },
  })
  return { wrapper, predict, downloadModel }
}

async function setEndDate(wrapper: VueWrapper, date: Date) {
  wrapper.findComponent({ name: 'DatePicker' }).vm.$emit('update:modelValue', date)
  await nextTick()
}

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob)
  })
}

describe('Forecasting evaluate — metrics & config', () => {
  it('renders metric cards, showing MAPE as an em dash when null', () => {
    const { wrapper } = mountEvaluate()
    const text = wrapper.text()
    expect(text).toContain('MAE')
    expect(text).toContain('MAPE')
    expect(text).toContain('—')
  })

  it('renders the read-only model configuration with min history and detected orders', () => {
    const { wrapper } = mountEvaluate()
    const config = wrapper.find('[data-testid="model-config"]')
    expect(wrapper.find('[data-testid="min-history"]').text()).toContain('15')
    expect(config.text()).toContain('(1, 1, 1)')
    expect(config.text()).toContain('month')
  })

  it('names the known-future columns in the config', () => {
    const config: ForecastingModelConfig = {
      ...baseConfig,
      aux_cols: ['promo'],
      known_future_cols: ['promo'],
    }
    const { wrapper } = mountEvaluate({ modelConfig: config })
    expect(wrapper.find('[data-testid="known-future"]').text()).toContain('promo')
  })
})

describe('Forecasting evaluate — re-forecast', () => {
  it('blocks the forecast until a future end date is chosen', () => {
    const { wrapper } = mountEvaluate()
    expect(wrapper.find('[data-testid="run-forecast"]').attributes('disabled')).toBeDefined()
  })

  it('sends history + horizon (no future) and overlays the normalized result', async () => {
    const { wrapper, predict } = mountEvaluate()
    await setEndDate(wrapper, new Date('2020-06-01'))

    expect(wrapper.find('[data-testid="run-forecast"]').attributes('disabled')).toBeUndefined()
    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()

    expect(predict).toHaveBeenCalledWith(
      expect.objectContaining({ model_id: 'model-1', history: baseHistory, horizon: 3 }),
    )
    expect(predict.mock.calls[0][0].future).toBeUndefined()

    const chart = wrapper.findComponent({ name: 'ForecastChart' })
    expect(chart.props('prediction')?.sales).toHaveLength(3)
    expect(
      wrapper.find('[data-testid="download-predictions"]').attributes('disabled'),
    ).toBeUndefined()
  })

  it('requires a filled future grid before forecasting a known-future model', async () => {
    const config: ForecastingModelConfig = {
      ...baseConfig,
      aux_cols: ['promo'],
      known_future_cols: ['promo'],
    }
    const { wrapper, predict } = mountEvaluate({ modelConfig: config })
    await setEndDate(wrapper, new Date('2020-06-01'))

    const editor = wrapper.findComponent({ name: 'FutureValuesEditor' })
    expect(editor.exists()).toBe(true)
    expect(editor.props('dates')).toEqual(['2020-04-01', '2020-05-01', '2020-06-01'])
    expect(wrapper.find('[data-testid="run-forecast"]').attributes('disabled')).toBeDefined()

    editor.vm.$emit('change', {
      complete: true,
      future: [
        { date: '2020-04-01', promo: 1 },
        { date: '2020-05-01', promo: 1 },
        { date: '2020-06-01', promo: 1 },
      ],
    })
    await nextTick()

    expect(wrapper.find('[data-testid="run-forecast"]').attributes('disabled')).toBeUndefined()
    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()

    expect(predict.mock.calls[0][0].future).toHaveLength(3)
    expect(wrapper.findComponent({ name: 'ForecastChart' }).props('supplied')?.promo).toHaveLength(
      3,
    )
  })

  it('displays and exports only the final date in single-date mode', async () => {
    const { wrapper } = mountEvaluate()
    await setEndDate(wrapper, new Date('2020-06-01'))
    wrapper.findComponent({ name: 'SelectButton' }).vm.$emit('update:modelValue', 'single')
    await nextTick()

    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()

    // engine forecast all 3 periods, but the overlay shows only the last
    expect(
      wrapper.findComponent({ name: 'ForecastChart' }).props('prediction')?.sales,
    ).toHaveLength(1)

    downloadMock.mockClear()
    await wrapper.find('[data-testid="download-predictions"]').trigger('click')
    const blob = downloadMock.mock.calls[0][0] as Blob
    const csv = await readBlob(blob)
    expect(csv).toContain('2020-06-01')
    expect(csv).not.toContain('2020-04-01')
  })

  it('stays on the evaluate step with no overlay when the re-forecast fails', async () => {
    // startPredict swallows the worker error into a toast and resolves undefined
    const { wrapper } = mountEvaluate({ failPredict: true })
    await setEndDate(wrapper, new Date('2020-06-01'))
    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ForecastChart' }).props('prediction')).toBeNull()
    expect(
      wrapper.find('[data-testid="download-predictions"]').attributes('disabled'),
    ).toBeDefined()
    expect(wrapper.find('[data-testid="forecasting-evaluate"]').exists()).toBe(true)
  })

  it('invalidates a stale forecast when the horizon changes', async () => {
    const { wrapper } = mountEvaluate()
    await setEndDate(wrapper, new Date('2020-06-01'))
    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ForecastChart' }).props('prediction')).not.toBeNull()

    await setEndDate(wrapper, new Date('2020-09-01'))
    expect(wrapper.findComponent({ name: 'ForecastChart' }).props('prediction')).toBeNull()
    expect(
      wrapper.find('[data-testid="download-predictions"]').attributes('disabled'),
    ).toBeDefined()
  })
})

describe('Forecasting evaluate — downloads', () => {
  it('downloads the .luml via the provided callback', async () => {
    const { wrapper, downloadModel } = mountEvaluate()
    await wrapper.find('[data-testid="download-luml"]').trigger('click')
    expect(downloadModel).toHaveBeenCalled()
  })

  it('downloads a predictions CSV including the target bounds', async () => {
    const { wrapper } = mountEvaluate()
    await setEndDate(wrapper, new Date('2020-06-01'))
    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()

    downloadMock.mockClear()
    await wrapper.find('[data-testid="download-predictions"]').trigger('click')
    const blob = downloadMock.mock.calls[0][0] as Blob
    const csv = await readBlob(blob)
    expect(csv).toContain('predicted_sales_lower')
    expect(csv).toContain('predicted_sales_upper')
  })
})
