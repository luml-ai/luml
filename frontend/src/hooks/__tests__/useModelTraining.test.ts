import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { train, deallocate, addToast } = vi.hoisted(() => ({
  train: vi.fn(),
  deallocate: vi.fn(),
  addToast: vi.fn(),
}))

vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: addToast }) }))
vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: { startTraining: train, deallocateModels: deallocate },
}))

import { useModelTraining } from '../useModelTraining'
import { Tasks, WEBWORKER_ROUTES_ENUM } from '@/lib/data-processing/interfaces'

beforeEach(() => {
  train.mockResolvedValue({ status: 'success', model_id: 'trained', model: { 0: 1 } })
  deallocate.mockResolvedValue([])
})

describe('training model cleanup', () => {
  it.each([
    ['tabular', WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE],
    ['prompt_optimization', WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE],
  ] as const)('uses the correct route when unmounting %s training', async (service, route) => {
    let hook!: ReturnType<typeof useModelTraining>
    const wrapper = mount(
      defineComponent({
        setup() {
          hook = useModelTraining(service)
          return () => null
        },
      }),
    )
    await hook.startTraining({ data: {}, target: 'y', task: Tasks.TABULAR_REGRESSION })
    wrapper.unmount()
    await flushPromises()
    expect(deallocate).toHaveBeenCalledWith(['trained'], route)
  })

  it('reports unmount cleanup failures', async () => {
    deallocate.mockRejectedValue(new Error('Cleanup failed'))
    const wrapper = mount(
      defineComponent({
        setup() {
          useModelTraining('tabular')
          return () => null
        },
      }),
    )
    wrapper.unmount()
    await flushPromises()
    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Cleanup failed' }))
  })
})
