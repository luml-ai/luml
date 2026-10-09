import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { removeModel, deinit, requireConfirm, addToast } = vi.hoisted(() => ({
  removeModel: vi.fn(),
  deinit: vi.fn(),
  requireConfirm: vi.fn(),
  addToast: vi.fn(),
}))

vi.mock('primevue/useconfirm', () => ({ useConfirm: () => ({ require: requireConfirm }) }))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: addToast }) }))
vi.mock('@/hooks/useFnnxModel', () => ({
  useFnnxModel: () => ({
    currentTag: ref('prompt_optimization'),
    getModel: ref({}),
    modelId: ref('model'),
    createModelFromFile: vi.fn(),
    removeModel,
    deinit,
  }),
}))
vi.mock('@/components/runtime/UploadData.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/runtime/dashboard/RuntimeDashboard.vue', () => ({
  default: { template: '<div />' },
}))

import RuntimePage from './RuntimePage.vue'
import UploadData from '@/components/runtime/UploadData.vue'
import RuntimeDashboard from '@/components/runtime/dashboard/RuntimeDashboard.vue'

beforeEach(() => {
  removeModel.mockResolvedValue(undefined)
  deinit.mockResolvedValue(undefined)
})

describe('runtime cleanup', () => {
  it('removes the runtime model when a user confirms exit', async () => {
    const wrapper = mount(RuntimePage)
    wrapper.getComponent(UploadData).vm.$emit('continue')
    await flushPromises()
    wrapper.getComponent(RuntimeDashboard).vm.$emit('exit')
    expect(removeModel).not.toHaveBeenCalled()
    await requireConfirm.mock.calls[0][0].accept()
    await flushPromises()
    expect(removeModel).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent(UploadData).exists()).toBe(true)
    wrapper.unmount()
    expect(deinit).toHaveBeenCalledTimes(1)
  })

  it('reports exit cleanup failure and keeps the dashboard available for retry', async () => {
    removeModel.mockRejectedValueOnce(new Error('Cleanup failed'))
    const wrapper = mount(RuntimePage)
    wrapper.getComponent(UploadData).vm.$emit('continue')
    await flushPromises()
    wrapper.getComponent(RuntimeDashboard).vm.$emit('exit')
    await requireConfirm.mock.calls[0][0].accept()
    await flushPromises()
    expect(wrapper.findComponent(RuntimeDashboard).exists()).toBe(true)
    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Cleanup failed' }))
    wrapper.unmount()
  })

  it('reports cleanup failures on page unmount', async () => {
    deinit.mockRejectedValueOnce(new Error('Cleanup failed'))
    const wrapper = mount(RuntimePage)
    wrapper.unmount()
    await flushPromises()
    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Cleanup failed' }))
  })
})
