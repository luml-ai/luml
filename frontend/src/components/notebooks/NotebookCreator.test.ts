import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import NotebookCreator from './NotebookCreator.vue'
import NotebookCreateUpdateForm from './NotebookCreateUpdateForm.vue'

const mocks = vi.hoisted(() => ({ create: vi.fn(), toastAdd: vi.fn() }))

vi.mock('@/stores/notebooks', () => ({ useNotebooksStore: () => ({ create: mocks.create }) }))
vi.mock('primevue', () => ({
  Button: { template: '<button @click="$emit(\'click\')">Create instance</button>' },
  Dialog: {
    props: ['visible'],
    template: '<div v-if="visible"><slot /></div>',
  },
  useToast: () => ({ add: mocks.toastAdd }),
}))

enableAutoUnmount(afterEach)
beforeEach(() => mocks.create.mockReset())

async function openCreator() {
  const wrapper = mount(NotebookCreator, {
    global: { stubs: { NotebookCreateUpdateForm: true } },
  })
  await wrapper.get('button').trigger('click')
  return wrapper
}

describe('NotebookCreator', () => {
  it('shows loading while creating and closes the dialog on success', async () => {
    let resolve!: () => void
    mocks.create.mockReturnValue(new Promise<void>((done) => (resolve = done)))
    const wrapper = await openCreator()
    const form = wrapper.getComponent(NotebookCreateUpdateForm)

    form.vm.$emit('submit', { fullname: 'Notebook' })
    await flushPromises()
    expect(form.props('loading')).toBe(true)
    expect(mocks.create).toHaveBeenCalledExactlyOnceWith({ fullname: 'Notebook' })

    resolve()
    await flushPromises()
    expect(wrapper.findComponent(NotebookCreateUpdateForm).exists()).toBe(false)
    expect(mocks.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success' }))
  })

  it.each([
    [new Error('quota exceeded'), 'quota exceeded'],
    [undefined, 'Something went wrong'],
  ])('reports a failed creation and permits a retry: %s', async (error, message) => {
    mocks.create.mockRejectedValueOnce(error).mockResolvedValueOnce(undefined)
    const wrapper = await openCreator()
    const form = wrapper.getComponent(NotebookCreateUpdateForm)

    form.vm.$emit('submit', { fullname: 'Notebook' })
    await flushPromises()

    expect(form.props('loading')).toBe(false)
    expect(wrapper.findComponent(NotebookCreateUpdateForm).exists()).toBe(true)
    expect(mocks.toastAdd).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: message }),
    )

    form.vm.$emit('submit', { fullname: 'Notebook' })
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledTimes(2)
    expect(wrapper.findComponent(NotebookCreateUpdateForm).exists()).toBe(false)
  })
})
