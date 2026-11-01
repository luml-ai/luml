import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const { addToast, requireConfirm, runOptimization } = vi.hoisted(() => ({
  addToast: vi.fn(),
  requireConfirm: vi.fn(),
  runOptimization: vi.fn(),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: addToast }),
  useConfirm: () => ({ require: requireConfirm }),
}))
vi.mock('@vue-flow/core', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@vue-flow/core')>()),
  useVueFlow: () => ({ toObject: () => ({ nodes: [], edges: [] }) }),
}))
vi.mock('@/lib/promt-fusion/PromptFusionService', () => ({
  promptFusionService: {
    taskDescription: '',
    on: (_event: string, callback: (visible: boolean) => void) => callback(true),
    off: vi.fn(),
    prepareData: vi.fn(),
    checkIsOptimizationAvailable: vi.fn(),
    runOptimization,
  },
}))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: vi.fn() },
  AnalyticsTrackKeysEnum: { run_optimization: 'run_optimization' },
}))

import Optimization from '../index.vue'

describe('prompt fusion optimization errors', () => {
  it.each([
    [new Error('Worker crashed'), 'Worker crashed'],
    ['Worker unavailable', 'Worker unavailable'],
  ])('uses plain error text in the training toast for %s', async (error, detail) => {
    runOptimization.mockRejectedValueOnce(error)
    const wrapper = shallowMount(Optimization, {
      props: { disabled: false },
      global: {
        stubs: {
          Teleport: true,
          DButton: {
            props: ['label'],
            template: '<button><slot>{{ label }}</slot></button>',
          },
        },
      },
    })

    const runButton = wrapper
      .findAll('button')
      .find((button) => button.text() === 'Run optimization')!
    await runButton.trigger('click')
    await requireConfirm.mock.calls[0][0].accept()
    await flushPromises()

    expect(addToast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail }),
    )
    wrapper.unmount()
  })
})
