import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import NotebookListActions from './NotebookListActions.vue'

const mocks = vi.hoisted(() => ({
  createBackup: vi.fn(),
  confirmRequire: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/stores/notebooks', () => ({
  useNotebooksStore: () => ({ createBackup: mocks.createBackup }),
}))
vi.mock('primevue', () => ({
  Button: { template: '<button><slot name="icon" /></button>' },
  Menu: {
    props: ['model'],
    template:
      '<div><button v-for="item in model" :key="item.label" :data-item="item.label" @click="item.command()">{{ item.label }}</button></div>',
  },
  Dialog: { props: ['visible'], template: '<div v-if="visible"><slot /></div>' },
  useConfirm: () => ({ require: mocks.confirmRequire }),
  useToast: () => ({ add: mocks.toastAdd }),
}))

const notebook = { name: 'jl_notebook', version: 1, fullname: 'Notebook', createdAt: 1, files: [] }

enableAutoUnmount(afterEach)
beforeEach(() => {
  mocks.createBackup.mockReset()
  mocks.confirmRequire.mockReset()
  mocks.toastAdd.mockReset()
})

async function confirmBackup() {
  const wrapper = mount(NotebookListActions, {
    props: { notebook },
    global: { stubs: { NotebookCreateUpdateForm: true } },
  })
  await wrapper.get('[data-item="Backup"]').trigger('click')
  expect(mocks.confirmRequire).toHaveBeenCalledOnce()
  await mocks.confirmRequire.mock.calls[0][0].accept()
  await flushPromises()
}

describe('NotebookListActions backup', () => {
  it('names the files that could not be added to the backup', async () => {
    mocks.createBackup.mockResolvedValue(['broken.luml', 'nested/broken.bin'])

    await confirmBackup()

    expect(mocks.createBackup).toHaveBeenCalledExactlyOnceWith('jl_notebook')
    expect(mocks.toastAdd).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        severity: 'warn',
        detail: expect.stringContaining('broken.luml, nested/broken.bin'),
      }),
    )
  })

  it('shows no toast when every file is in the backup', async () => {
    mocks.createBackup.mockResolvedValue([])

    await confirmBackup()

    expect(mocks.toastAdd).not.toHaveBeenCalled()
  })

  it('reports a failed backup', async () => {
    mocks.createBackup.mockRejectedValue(new Error('No files found to backup'))

    await confirmBackup()

    expect(mocks.toastAdd).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'No files found to backup' }),
    )
  })
})
