import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { forecastingSteps } from '@/constants/constants'
import { Tasks, WEBWORKER_ROUTES_ENUM } from '@/lib/data-processing/interfaces'

const {
  startTrainingMock,
  deallocateMock,
  toastAddMock,
  setSelectedColumnsMock,
  setFiltersMock,
  tableState,
} = vi.hoisted(() => ({
  startTrainingMock: vi.fn(),
  deallocateMock: vi.fn(),
  toastAddMock: vi.fn(),
  setSelectedColumnsMock: vi.fn(),
  setFiltersMock: vi.fn(),
  tableState: {
    columns: ['date', 'sales', 'promo'],
    rows: [] as Record<string, unknown>[],
  },
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
  const { computed, ref } = await import('vue')
  return {
    useDataTable: () => ({
      isTableExist: ref(true),
      fileData: ref({}),
      uploadDataErrors: ref({ size: false, columns: false, rows: false }),
      isUploadWithErrors: ref(false),
      columnsCount: computed(() => tableState.columns.length),
      rowsCount: computed(() => tableState.rows.length),
      getAllColumnNames: computed(() => tableState.columns),
      viewValues: computed(() => tableState.rows),
      selectedColumns: ref([]),
      getFilters: ref([]),
      columnTypes: ref({ date: 'string', sales: 'number', promo: 'number' }),
      onSelectFile: vi.fn(),
      onRemoveFile: vi.fn(),
      setSelectedColumns: setSelectedColumnsMock,
      downloadCSV: vi.fn(),
      setFilters: setFiltersMock,
      getDataForTraining: () =>
        Object.fromEntries(
          tableState.columns.map((column) => [column, tableState.rows.map((row) => row[column])]),
        ),
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
  ForecastSetup: {
    name: 'ForecastSetup',
    props: [
      'frequency',
      'aggregation',
      'previewEndDate',
      'hasKnownFuture',
      'lastHistoricalDate',
      'dateNotParseable',
      'previewDateInvalid',
    ],
    emits: ['update:frequency', 'update:aggregation', 'update:previewEndDate'],
    template: '<div />',
  },
  ForecastColumnHeader: {
    name: 'ForecastColumnHeader',
    props: ['column', 'columnType', 'role'],
    emits: ['setDate', 'setTarget', 'toggleAux', 'toggleKnownFuture'],
    template: '<div />',
  },
  TableView: {
    name: 'TableView',
    props: [
      'columnsCount',
      'rowsCount',
      'allColumns',
      'value',
      'target',
      'selectedColumns',
      'exportCallback',
      'filters',
      'columnTypes',
      'heightOffset',
      'showColumnHeaderMenu',
    ],
    emits: ['edit', 'changeFilters'],
    template: `
      <div data-testid="table-view">
        <slot v-for="column in allColumns" name="column-header" :column="column" />
      </div>
    `,
  },
  ForecastingEvaluate: {
    name: 'ForecastingEvaluate',
    template: '<div data-testid="forecasting-evaluate" />',
  },
}

const DButton = {
  name: 'DButton',
  props: ['label', 'disabled', 'severity'],
  emits: ['click'],
  template: `<button :disabled="disabled" @click="$emit('click')"><slot>{{ label }}</slot></button>`,
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

function headerFor(wrapper: VueWrapper, column: string) {
  const header = wrapper
    .findAllComponents({ name: 'ForecastColumnHeader' })
    .find((component) => component.props('column') === column)
  if (!header) throw new Error(`no header for column ${column}`)
  return header
}

describe('ForecastingWrapper', () => {
  beforeEach(() => {
    startTrainingMock.mockReset().mockResolvedValue(trainSuccess)
    deallocateMock.mockReset().mockResolvedValue([])
    toastAddMock.mockReset()
    setSelectedColumnsMock.mockReset()
    setFiltersMock.mockReset()
    tableState.columns = ['date', 'sales', 'promo']
    tableState.rows = [
      { date: '2020-01-01', sales: 10, promo: 0 },
      { date: '2020-02-01', sales: 11, promo: 1 },
    ]
  })

  it('shows the setup bar and the data table with role headers on step 2', async () => {
    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)

    expect(wrapper.findComponent({ name: 'ForecastSetup' }).exists()).toBe(true)
    const tableView = wrapper.findComponent({ name: 'TableView' })
    expect(tableView.exists()).toBe(true)
    expect(tableView.props('value')).toEqual(tableState.rows)

    expect(headerFor(wrapper, 'date').props('role')).toBe('date')
    expect(headerFor(wrapper, 'sales').props('role')).toBe('target')
    expect(headerFor(wrapper, 'promo').props('role')).toBeNull()
  })

  it('trains with the auto-detected roles and advances to evaluation', async () => {
    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)

    await wrapper.find('[data-testid="forecasting-train"]').trigger('click')
    await flushPromises()

    expect(startTrainingMock).toHaveBeenCalledWith(
      expect.objectContaining({
        date_col: 'date',
        target_col: 'sales',
        aux_cols: [],
        known_future_cols: [],
        frequency: 'month',
        preview_horizon: null,
      }),
      WEBWORKER_ROUTES_ENUM.FORECASTING_TRAIN,
    )
    expect(wrapper.find('[data-testid="forecasting-evaluate"]').exists()).toBe(true)
  })

  it('applies role changes made through the table column menus', async () => {
    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)

    await headerFor(wrapper, 'promo').vm.$emit('setTarget', 'promo')
    expect(headerFor(wrapper, 'promo').props('role')).toBe('target')
    expect(headerFor(wrapper, 'sales').props('role')).toBeNull()

    await headerFor(wrapper, 'sales').vm.$emit('toggleAux', 'sales')
    await headerFor(wrapper, 'sales').vm.$emit('toggleKnownFuture', 'sales')
    expect(wrapper.findComponent({ name: 'ForecastSetup' }).props('hasKnownFuture')).toBe(true)

    await wrapper.find('[data-testid="forecasting-train"]').trigger('click')
    await flushPromises()

    expect(startTrainingMock).toHaveBeenCalledWith(
      expect.objectContaining({
        date_col: 'date',
        target_col: 'promo',
        aux_cols: ['sales'],
        known_future_cols: ['sales'],
      }),
      WEBWORKER_ROUTES_ENUM.FORECASTING_TRAIN,
    )
  })

  it('does not train while the setup is invalid', async () => {
    tableState.columns = ['a', 'b']
    tableState.rows = [
      { a: 1, b: 2 },
      { a: 3, b: 4 },
    ]

    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)

    expect(wrapper.findComponent({ name: 'ForecastSetup' }).props('dateNotParseable')).toBe(true)
    await wrapper.find('[data-testid="forecasting-train"]').trigger('click')
    await flushPromises()

    expect(startTrainingMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="forecasting-evaluate"]').exists()).toBe(false)
  })

  it('forwards preview column edits and filters to the data table', async () => {
    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)

    const tableView = wrapper.findComponent({ name: 'TableView' })
    await tableView.vm.$emit('edit', ['date'])
    expect(setSelectedColumnsMock).toHaveBeenCalledWith(['date'])

    const filters = [{ column: 'sales', condition: 'more', value: '5' }]
    await tableView.vm.$emit('changeFilters', filters)
    expect(setFiltersMock).toHaveBeenCalledWith(filters)
  })

  it('reports a worker error via toast and stays on the setup step', async () => {
    startTrainingMock.mockResolvedValue({ status: 'error', error_message: 'not enough data' })

    const wrapper = mountWrapper()
    await reachSetupStep(wrapper)
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
