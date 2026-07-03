import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { forecastingSteps } from '@/constants/constants'
import { Tasks, WEBWORKER_ROUTES_ENUM } from '@/lib/data-processing/interfaces'
import type { ForecastSetupState } from '@/lib/data-processing/forecasting-setup'

const { startTrainingMock, deallocateMock, toastAddMock } = vi.hoisted(() => ({
  startTrainingMock: vi.fn(),
  deallocateMock: vi.fn(),
  toastAddMock: vi.fn(),
}))

vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: toastAddMock }) }))
vi.mock('@/hooks/useRouteLeaveConfirm', () => ({
  useRouteLeaveConfirm: () => ({ setGuard: vi.fn() }),
}))
vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: {
    checkPyodideReady: vi.fn(),
    startTraining: startTrainingMock,
    deallocateModels: deallocateMock,
  },
}))
vi.mock('@/hooks/useDataTable', async () => {
  const { ref } = await import('vue')
  return {
    useDataTable: () => ({
      isTableExist: ref(true),
      fileData: ref({}),
      uploadDataErrors: ref({ size: false, columns: false, rows: false }),
      isUploadWithErrors: ref(false),
      getAllColumnNames: ref(['date', 'sales']),
      viewValues: ref([{ date: '2020-01-01', sales: 10 }]),
      onSelectFile: vi.fn(),
      onRemoveFile: vi.fn(),
      getDataForTraining: () => ({ date: ['2020-01-01'], sales: [10] }),
    }),
  }
})

import ForecastingWrapper from '../ForecastingWrapper.vue'

const passthrough = (name: string) => ({ name, template: '<div><slot /></div>' })

const stubs = {
  Stepper: {
    name: 'Stepper',
    props: ['value'],
    emits: ['update:value'],
    template: '<div><slot /></div>',
  },
  StepList: passthrough('StepList'),
  Step: passthrough('Step'),
  StepPanels: passthrough('StepPanels'),
  StepPanel: {
    name: 'StepPanel',
    props: ['value'],
    template: '<div><slot :activate-callback="() => {}" /></div>',
  },
  UploadData: true,
  UiTraining: true,
  ForecastSetup: { name: 'ForecastSetup', emits: ['change'], template: '<div />' },
}

const DButton = {
  name: 'DButton',
  props: ['label', 'disabled', 'severity'],
  emits: ['click'],
  template: `<button :disabled="disabled" @click="$emit('click')"><slot>{{ label }}</slot></button>`,
}

const validSetupState: ForecastSetupState = {
  config: {
    date_col: 'date',
    target_col: 'sales',
    aux_cols: [],
    known_future_cols: [],
    frequency: 'month',
    preview_horizon: null,
  },
  previewMode: 'whole',
  isValid: true,
}

const trainSuccess = {
  status: 'success' as const,
  model_id: 'model-1',
  train_metrics: { MAE: 1, RMSE: 1, MAPE: 0.1, R2: 0.8 },
  test_metrics: { MAE: 2, RMSE: 2, MAPE: 0.2, R2: 0.7, SC_SCORE: 0.7 },
  model_config: {},
  chart: { split_date: null, series: {} },
  model: { 0: 1, 1: 2, 2: 3 },
}

function mountWrapper() {
  return mount(ForecastingWrapper, {
    props: { steps: forecastingSteps, task: Tasks.FORECASTING },
    global: { components: { DButton }, stubs },
  })
}

async function reachSetupStep(wrapper: VueWrapper) {
  await wrapper.findComponent({ name: 'Stepper' }).vm.$emit('update:value', 2)
  await flushPromises()
}

describe('ForecastingWrapper', () => {
  beforeEach(() => {
    startTrainingMock.mockReset().mockResolvedValue(trainSuccess)
    deallocateMock.mockReset().mockResolvedValue([])
    toastAddMock.mockReset()
  })

  it('trains from a valid setup and advances to the evaluation step', async () => {
    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)

    expect(wrapper.findComponent({ name: 'ForecastSetup' }).exists()).toBe(true)
    expect(wrapper.find('[data-testid="forecasting-evaluate"]').exists()).toBe(false)

    await wrapper.findComponent({ name: 'ForecastSetup' }).vm.$emit('change', validSetupState)
    await wrapper.find('[data-testid="forecasting-train"]').trigger('click')
    await flushPromises()

    expect(startTrainingMock).toHaveBeenCalledWith(
      expect.objectContaining({
        data: { date: ['2020-01-01'], sales: [10] },
        date_col: 'date',
        target_col: 'sales',
        frequency: 'month',
      }),
      WEBWORKER_ROUTES_ENUM.FORECASTING_TRAIN,
    )
    expect(wrapper.find('[data-testid="forecasting-evaluate"]').exists()).toBe(true)
  })

  it('does not train while the setup is invalid', async () => {
    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)

    await wrapper
      .findComponent({ name: 'ForecastSetup' })
      .vm.$emit('change', { ...validSetupState, isValid: false })
    await wrapper.find('[data-testid="forecasting-train"]').trigger('click')
    await flushPromises()

    expect(startTrainingMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="forecasting-evaluate"]').exists()).toBe(false)
  })

  it('reports a worker error via toast and stays on the setup step', async () => {
    startTrainingMock.mockResolvedValue({ status: 'error', error_message: 'not enough data' })

    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)
    await wrapper.findComponent({ name: 'ForecastSetup' }).vm.$emit('change', validSetupState)
    await wrapper.find('[data-testid="forecasting-train"]').trigger('click')
    await flushPromises()

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'not enough data' }),
    )
    expect(wrapper.find('[data-testid="forecasting-evaluate"]').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'ForecastSetup' }).exists()).toBe(true)
  })

  it('deallocates trained models on unmount', async () => {
    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)
    await wrapper.findComponent({ name: 'ForecastSetup' }).vm.$emit('change', validSetupState)
    await wrapper.find('[data-testid="forecasting-train"]').trigger('click')
    await flushPromises()

    wrapper.unmount()
    await flushPromises()

    expect(deallocateMock).toHaveBeenCalledWith(
      ['model-1'],
      WEBWORKER_ROUTES_ENUM.FORECASTING_DEALLOCATE,
    )
  })
})
