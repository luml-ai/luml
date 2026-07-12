import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { nextTick } from 'vue'
import type {
  ForecastPredictedRecord,
  ForecastingModelConfig,
} from '@/lib/data-processing/interfaces'

const { downloadMock, trackMock } = vi.hoisted(() => ({
  downloadMock: vi.fn(),
  trackMock: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/helpers/helpers', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, downloadFileFromBlob: downloadMock }
})
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: null }),
}))
vi.mock('@/lib/analytics/AnalyticsService', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, AnalyticsService: { track: trackMock } }
})

import Evaluate from '../index.vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'

const baseConfig: ForecastingModelConfig = {
  frequency: 'month',
  seasonal_period: 12,
  aggregation: 'mean',
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
  SplitButton: {
    name: 'SplitButton',
    props: ['label', 'model', 'severity'],
    emits: ['click'],
    template: `<button data-testid="export-model" @click="$emit('click')">{{ label }}</button>`,
  },
  ModelTabularPerformance: {
    name: 'ModelTabularPerformance',
    props: ['totalScore', 'testMetrics', 'trainingMetrics', 'tag'],
    template: '<div data-testid="performance" />',
  },
  ModelUpload: {
    name: 'ModelUpload',
    props: ['modelBlob', 'currentTask', 'visible'],
    template: '<div data-testid="model-upload" />',
  },
  ForecastChart: {
    name: 'ForecastChart',
    props: ['chart', 'targetCol', 'prediction', 'supplied'],
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
      testMetrics: ['2.00', '3.00', '—', '0.70'],
      trainingMetrics: ['1.00', '2.00', '0.10', '0.80'],
      modelConfig: over.modelConfig ?? baseConfig,
      chart: baseChart,
      history: over.history ?? baseHistory,
      modelId: 'model-1',
      modelBlob: new Blob(['model']),
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
  it('renders the shared performance card with the forecasting producer tag', () => {
    const { wrapper } = mountEvaluate()
    const performance = wrapper.findComponent({ name: 'ModelTabularPerformance' })
    expect(performance.props('totalScore')).toBe(70)
    expect(performance.props('testMetrics')).toEqual(['2.00', '3.00', '—', '0.70'])
    expect(performance.props('trainingMetrics')).toEqual(['1.00', '2.00', '0.10', '0.80'])
    expect(performance.props('tag')).toBe(FNNX_PRODUCER_TAGS_MANIFEST_ENUM.forecasting_v1)
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

  it('displays and exports the whole forecast period', async () => {
    const { wrapper } = mountEvaluate()
    await setEndDate(wrapper, new Date('2020-06-01'))

    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()

    // engine forecasts all 3 periods and the overlay shows every one of them
    expect(
      wrapper.findComponent({ name: 'ForecastChart' }).props('prediction')?.sales,
    ).toHaveLength(3)

    downloadMock.mockClear()
    await wrapper.find('[data-testid="download-predictions"]').trigger('click')
    const blob = downloadMock.mock.calls[0][0] as Blob
    const csv = await readBlob(blob)
    expect(csv).toContain('2020-04-01')
    expect(csv).toContain('2020-06-01')
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

  it('invalidates a stale forecast when a future value is edited', async () => {
    const config: ForecastingModelConfig = {
      ...baseConfig,
      aux_cols: ['promo'],
      known_future_cols: ['promo'],
    }
    const { wrapper } = mountEvaluate({ modelConfig: config })
    await setEndDate(wrapper, new Date('2020-06-01'))

    const editor = wrapper.findComponent({ name: 'FutureValuesEditor' })
    const future = [
      { date: '2020-04-01', promo: 1 },
      { date: '2020-05-01', promo: 1 },
      { date: '2020-06-01', promo: 1 },
    ]
    editor.vm.$emit('change', { complete: true, future })
    await nextTick()
    await wrapper.find('[data-testid="run-forecast"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ForecastChart' }).props('prediction')).not.toBeNull()

    editor.vm.$emit('change', {
      complete: true,
      future: future.map((row) => ({ ...row, promo: 2 })),
    })
    await nextTick()

    expect(wrapper.findComponent({ name: 'ForecastChart' }).props('prediction')).toBeNull()
    expect(wrapper.findComponent({ name: 'ForecastChart' }).props('supplied')).toBeNull()
    expect(
      wrapper.find('[data-testid="download-predictions"]').attributes('disabled'),
    ).toBeDefined()
    expect(wrapper.find('[data-testid="run-forecast"]').attributes('disabled')).toBeUndefined()
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
  it('downloads the model from the export split button and tracks the event', async () => {
    const { wrapper, downloadModel } = mountEvaluate()
    trackMock.mockClear()
    await wrapper.find('[data-testid="export-model"]').trigger('click')
    expect(downloadModel).toHaveBeenCalled()
    expect(trackMock).toHaveBeenCalledWith('download', { task: 'forecasting' })
  })

  it('offers a registry upload entry in the export menu', () => {
    const { wrapper } = mountEvaluate()
    const items = wrapper.findComponent({ name: 'SplitButton' }).props('model') as Array<{
      label: string
    }>
    expect(items.map((item) => item.label)).toEqual(['Upload to Registry', 'Download model'])
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
