import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { Button, SplitButton } from 'primevue'
import type { WorkspaceListing } from '@/api/slices/workspace/workspace.interface'
import { WorkspaceRefusedError, workspaceApi } from '@/api/slices/workspace/workspace.api'
import WorkspaceCreateMenu from '@/components/workspace/WorkspaceCreateMenu.vue'
import { useWorkspaceStore } from '@/store/workspace'
import { settle } from './fakes'

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => ({ add: toast }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: toast }) }))

function listing(flows: WorkspaceListing['flows'] = []): WorkspaceListing {
  return { directory: '/p', flows, folders: [], files: [], next_offset: null, total: flows.length }
}

async function openDirectory(page: WorkspaceListing) {
  const store = useWorkspaceStore()
  vi.spyOn(workspaceApi, 'listFlows').mockResolvedValue(page)
  vi.spyOn(workspaceApi, 'openFlows').mockResolvedValue({
    directory: '/p',
    flows: [],
    totals: store.openFlowsTotals,
  })
  await store.fetchDirectory('/p')
  vi.spyOn(store, 'refreshDirectory').mockResolvedValue()
}

function component() {
  return mount(WorkspaceCreateMenu, { attachTo: document.body })
}

function buttons() {
  return [...document.body.querySelectorAll<HTMLButtonElement>('button')]
}

async function openMenuItem(label: string) {
  const chevron = document.body.querySelector<HTMLButtonElement>('.p-splitbutton-dropdown')
  expect(chevron).not.toBeNull()
  chevron!.click()
  await settle()
  const items = [...document.body.querySelectorAll<HTMLElement>('[role=menuitem]')]
  expect(items.map((item) => item.textContent?.trim())).toEqual(['New folder', 'New file'])
  items
    .find((item) => item.textContent?.trim() === label)!
    .querySelector('a')!
    .click()
  await settle()
}

enableAutoUnmount(afterEach)
beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('Workspace create menu', () => {
  it('opens the notebook dialog from the primary button', async () => {
    await openDirectory(listing())
    const wrapper = component()
    expect(wrapper.getComponent(SplitButton).props('size')).toBe('small')
    expect(document.body.textContent).not.toContain('CREATE NEW NOTEBOOK')
    buttons()
      .find((button) => button.textContent?.trim() === 'New notebook')!
      .click()
    await settle()
    expect(document.body.textContent).toContain('CREATE NEW NOTEBOOK')
    expect(document.querySelector('#create-flow-form')).not.toBeNull()
  })

  it('keeps invalid create names and daemon collisions under the field, and opens the created file', async () => {
    await openDirectory(listing())
    const create = vi
      .spyOn(workspaceApi, 'createFile')
      .mockRejectedValueOnce(
        new WorkspaceRefusedError('"notes.md" already exists', 'AlreadyExists'),
      )
      .mockResolvedValueOnce({ path: '/p/new.md' })
    const wrapper = component()
    await openMenuItem('New file')
    const form = new DOMWrapper(document.querySelector('#workspace-create-form')!)
    await form.get('input').setValue('../bad')
    await form.trigger('submit')
    expect(form.text()).toContain('single name')
    expect(create).not.toHaveBeenCalled()
    await form.get('input').setValue('notes.md')
    await form.trigger('submit')
    await settle()
    expect(form.text()).toContain('"notes.md" already exists')
    await form.get('input').setValue('new.md')
    await form.trigger('submit')
    await settle()
    expect(wrapper.emitted('created-file')).toEqual([['/p/new.md']])
    expect(useWorkspaceStore().refreshDirectory).toHaveBeenCalledOnce()
  })

  it('creates a folder in the current directory without opening it', async () => {
    await openDirectory(listing())
    const mkdir = vi.spyOn(workspaceApi, 'createFolder').mockResolvedValue({ path: '/p/data' })
    const wrapper = component()
    await openMenuItem('New folder')
    const form = new DOMWrapper(document.querySelector('#workspace-create-form')!)
    await form.get('input').setValue('data')
    await form.trigger('submit')
    await settle()
    expect(mkdir).toHaveBeenCalledWith('/p', 'data')
    expect(wrapper.emitted('created-file')).toBeUndefined()
    expect(useWorkspaceStore().refreshDirectory).toHaveBeenCalledOnce()
  })

  it('offers only a new notebook when a notebook lists itself', async () => {
    await openDirectory(
      listing([{ name: 'analysis', path: '/p', relative_path: '.', is_symlink: false }]),
    )
    const wrapper = component()
    expect(buttons().map((button) => button.textContent?.trim())).toEqual(['New notebook'])
    expect(wrapper.getComponent(Button).props('size')).toBe('small')
    expect(document.body.querySelector('.p-splitbutton')).toBeNull()
  })

  it('shows nothing until a directory is listed', async () => {
    const wrapper = component()
    expect(wrapper.find('button').exists()).toBe(false)
    useWorkspaceStore().currentDirectory = '/p'
    useWorkspaceStore().isDirectoryLoading = true
    await nextTick()
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
