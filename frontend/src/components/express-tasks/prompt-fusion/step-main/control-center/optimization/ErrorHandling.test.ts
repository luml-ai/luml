import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { WebworkerInterruptedError } from '@/lib/data-processing/DataProcessingWorker'
import Optimization from './index.vue'

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  confirm: vi.fn(),
  run: vi.fn(),
  prepare: vi.fn(),
  on: vi.fn(),
}))
vi.mock('@/lib/promt-fusion/PromptFusionService', () => ({
  promptFusionService: {
    taskDescription: '',
    prepareData: mocks.prepare,
    checkIsOptimizationAvailable: vi.fn(),
    endTraining: vi.fn(),
    runOptimization: mocks.run,
    on: mocks.on,
    off: vi.fn(),
  },
}))
vi.mock('@vue-flow/core', () => ({ useVueFlow: () => ({ toObject: () => ({}) }) }))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: vi.fn() },
  AnalyticsTrackKeysEnum: {},
}))
vi.mock('primevue', () => ({
  useToast: () => ({ add: mocks.toast }),
  useConfirm: () => ({ require: mocks.confirm }),
}))
enableAutoUnmount(afterEach)
beforeEach(() => vi.resetAllMocks())

async function openOptimization() {
  const wrapper = mount(Optimization, {
    props: { disabled: false },
    global: {
      stubs: {
        teleport: true,
        'd-button': {
          props: ['label'],
          emits: ['click'],
          template: '<button @click="$emit(\'click\')">{{ label }}<slot /></button>',
        },
        ModelSelect: true,
        EvaluationMetrics: true,
        CustomTextarea: true,
      },
    },
  })
  mocks.on.mock.calls.find(([event]) => event === 'CHANGE_OPTIMIZATION_STATE')?.[1](true)
  await flushPromises()
  const runButton = wrapper.findAll('button').find((button) => button.text() === 'Run optimization')
  if (!runButton) throw new Error('Run optimization button not found')
  await runButton.trigger('click')
  return wrapper
}
it.each([new Error('Training failed'), { response: { status: 500 } }])(
  'uses a string message for an optimization rejection',
  async (error) => {
    mocks.run.mockRejectedValueOnce(error)
    await openOptimization()
    await mocks.confirm.mock.calls[0][0].accept()
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        detail: 'Training failed',
      }),
    )
  },
)
it('shows no toast when the user cancelled the training', async () => {
  mocks.run.mockRejectedValueOnce(new WebworkerInterruptedError('Execution interrupted by user'))
  await openOptimization()
  await mocks.confirm.mock.calls[0][0].accept()
  expect(mocks.toast).not.toHaveBeenCalled()
})
it('uses a useful fallback for a non-Error preparation rejection', async () => {
  mocks.prepare.mockImplementationOnce(() => {
    throw { status: 500 }
  })
  await openOptimization()
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({ severity: 'error', detail: 'Training failed' }),
  )
  expect(mocks.confirm).not.toHaveBeenCalled()
})
