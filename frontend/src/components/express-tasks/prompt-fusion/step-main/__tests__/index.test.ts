import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  interrupt: vi.fn(),
  endTraining: vi.fn(),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))
vi.mock('@vue-flow/core', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@vue-flow/core')>()),
  useVueFlow: () => ({ onNodeClick: vi.fn(), onPaneClick: vi.fn() }),
}))
vi.mock('@/hooks/useRouteLeaveConfirm', () => ({
  useRouteLeaveConfirm: () => ({ setGuard: vi.fn() }),
}))
vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: { interrupt: mocks.interrupt },
  WebworkerInterruptedError: class extends Error {},
}))
vi.mock('@/lib/promt-fusion/PromptFusionService', () => ({
  promptFusionService: { on: vi.fn(), off: vi.fn(), endTraining: mocks.endTraining },
}))

import UiTraining from '@/components/ui/UiTraining.vue'
import StepMain from '../index.vue'

function cancelTraining() {
  const wrapper = shallowMount(StepMain, { props: { initialNodes: [] } })
  wrapper.findComponent(UiTraining).vm.$emit('cancel')
  return flushPromises()
}

describe('prompt fusion training cancellation', () => {
  beforeEach(() => vi.resetAllMocks())

  it('interrupts the worker before closing the training dialog', async () => {
    let confirmInterrupted!: () => void
    mocks.interrupt.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        confirmInterrupted = resolve
      }),
    )
    await cancelTraining()
    expect(mocks.interrupt).toHaveBeenCalledOnce()
    expect(mocks.endTraining).not.toHaveBeenCalled()
    confirmInterrupted()
    await flushPromises()
    expect(mocks.endTraining).toHaveBeenCalledOnce()
    expect(mocks.toast).not.toHaveBeenCalled()
  })

  it('reports a failed interruption and keeps the training dialog open', async () => {
    mocks.interrupt.mockRejectedValueOnce(new Error('Worker is busy'))
    await cancelTraining()
    expect(mocks.endTraining).not.toHaveBeenCalled()
    expect(mocks.toast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Worker is busy' }),
    )
  })
})
