import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, nextTick } from 'vue'
import type { ConfirmationOptions } from 'primevue/confirmationoptions'
import type { WorkspaceListing } from '@/api/slices/workspace/workspace.interface'
import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import WorkspaceFolder from '@/components/workspace/folder/WorkspaceFolder.vue'
import { WorkspaceRefusedError, workspaceApi } from '@/api/slices/workspace/workspace.api'
import { useWorkspaceStore } from '@/store/workspace'
import { dateToText } from '@/helpers/date'
import { settle } from './fakes'

const { confirm, toast } = vi.hoisted(() => ({
  confirm: vi.fn<(question: ConfirmationOptions) => void>(),
  toast: vi.fn(),
}))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useConfirm: () => ({ require: confirm }),
  useToast: () => ({ add: toast }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: toast }) }))

const flow = {
  id: '/p/exp.flow',
  path: '/p/exp.flow',
  name: 'exp',
  entryName: 'exp.flow',
  type: 'flow',
  size: 0,
} as const
const file = {
  id: '/p/notes.md',
  path: '/p/notes.md',
  name: 'notes.md',
  type: 'file',
  size: 12,
  modified_at: '2026-02-04T12:09:00Z',
  is_symlink: true,
} as const
const folder = { id: '/p/plots', path: '/p/plots', name: 'plots', type: 'folder', size: 0 } as const

enableAutoUnmount(afterEach)
beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  useWorkspaceStore().currentDirectory = '/p'
  vi.spyOn(useWorkspaceStore(), 'refreshDirectory').mockResolvedValue()
})
afterEach(() => {
  vi.restoreAllMocks()
})

function component(
  items: IWorkspaceFolderItem[] = [flow, folder, file],
  beforeOperation?: (path: string) => Promise<boolean>,
) {
  return mount(WorkspaceFolder, {
    attachTo: document.body,
    props: { items, selectedPath: file.path, beforeOperation },
    global: { stubs: { RouterLink: true, CreateNewFlow: true } },
  })
}

async function click(text: string, selector = 'button') {
  const nodes = [...document.body.querySelectorAll<HTMLElement>(selector)]
  const node = nodes.find((el) => el.textContent?.trim() === text)
  expect(node, `expected ${selector} with label "${text}"`).toBeDefined()
  node!.click()
  await settle()
}

async function action(item: IWorkspaceFolderItem, label: string) {
  document
    .querySelector<HTMLButtonElement>(`button[aria-label="Actions for ${item.name}"]`)!
    .click()
  await nextTick()
  await click(label, '[role=menuitem] a')
}

function page(
  directory: string,
  folders: string[] = [],
  next_offset: number | null = null,
): WorkspaceListing {
  return {
    directory,
    folders: folders.map((name) => ({
      path: directory === '/' ? '/' + name : directory + '/' + name,
      name,
      is_symlink: false,
      modified_at: file.modified_at,
    })),
    flows: [],
    files: [],
    next_offset,
    total: folders.length,
  }
}

async function listFiles(names: Set<string>) {
  const store = useWorkspaceStore()
  vi.mocked(store.refreshDirectory).mockRestore()
  vi.spyOn(workspaceApi, 'openFlows').mockResolvedValue({
    directory: '/p',
    flows: [],
    totals: store.openFlowsTotals,
  })
  vi.spyOn(workspaceApi, 'listFlows').mockImplementation(async () => ({
    ...page('/p'),
    total: names.size,
    files: [...names].map((name) => ({ ...file, name, path: '/p/' + name, is_symlink: false })),
  }))
  await store.fetchDirectory('/p')
  return mount(
    defineComponent({
      components: { WorkspaceFolder },
      setup: () => ({ store }),
      template: '<WorkspaceFolder :items="store.sortedItems" />',
    }),
    { attachTo: document.body, global: { stubs: { CreateNewFlow: true } } },
  )
}

describe('Workspace listing and operations', () => {
  it('opens files and folders, marks the selection and links, and shows size and date', async () => {
    const wrapper = component()
    expect(wrapper.find('.selected').text()).toContain('notes.md')
    expect(wrapper.find('[aria-label="Symbolic link"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('12B')
    expect(wrapper.get('time').text()).toBe(dateToText(file.modified_at))
    await click('notes.md')
    await click('plots')
    expect(wrapper.emitted('open-file')).toEqual([[file.path]])
    expect(wrapper.emitted('navigate')).toEqual([[folder.path]])
  })

  it('shows the item count and requests the next page', async () => {
    const store = useWorkspaceStore()
    const more = vi.spyOn(store, 'loadMore').mockResolvedValue(undefined)
    vi.spyOn(workspaceApi, 'listFlows').mockResolvedValue({ ...page('/p', [], 2000), total: 4500 })
    vi.spyOn(workspaceApi, 'openFlows').mockResolvedValue({
      directory: '/p',
      totals: store.openFlowsTotals,
      flows: [],
    })
    await store.fetchDirectory('/p')
    const wrapper = component([file])
    expect(wrapper.text()).toContain('Showing 1 of 4,500 items')
    await click('Show more')
    expect(more).toHaveBeenCalledOnce()
  })

  it('keeps invalid create names and daemon collisions under the field, and opens the created file', async () => {
    const create = vi
      .spyOn(workspaceApi, 'createFile')
      .mockRejectedValueOnce(
        new WorkspaceRefusedError('"notes.md" already exists', 'AlreadyExists'),
      )
      .mockResolvedValueOnce({ path: '/p/new.md' })
    const wrapper = component()
    await click('New file')
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

  it('creates a folder in the current directory without changing the selected file', async () => {
    const mkdir = vi.spyOn(workspaceApi, 'createFolder').mockResolvedValue({ path: '/p/data' })
    const wrapper = component()
    await click('New folder')
    const form = new DOMWrapper(document.querySelector('#workspace-create-form')!)
    await form.get('input').setValue('data')
    await form.trigger('submit')
    await settle()
    expect(mkdir).toHaveBeenCalledWith('/p', 'data')
    expect(wrapper.emitted('created-file')).toBeUndefined()
    expect(useWorkspaceStore().refreshDirectory).toHaveBeenCalledOnce()
  })

  it('confirms only the link will be removed when deleting a directory symlink', async () => {
    const remove = vi.spyOn(workspaceApi, 'deleteFile')
    const link = { ...folder, is_symlink: true }
    component([link])
    await action(link, 'Delete')
    const question = confirm.mock.calls[0]![0]
    expect(question.message).toContain('Only the symbolic link is deleted.')
    question.reject!()
    await settle()
    expect(remove).not.toHaveBeenCalled()
  })

  it('navigates above the start folder and into another one before moving the file', async () => {
    const list = vi
      .spyOn(workspaceApi, 'listFlows')
      .mockResolvedValueOnce(page('/p'))
      .mockResolvedValueOnce(page('/', ['data']))
      .mockResolvedValueOnce(page('/data', ['runs']))
    const move = vi.spyOn(workspaceApi, 'moveFile').mockResolvedValue({ path: '/data/notes.md' })
    component()
    await action(file, 'Move to…')
    const button = document.querySelector<HTMLButtonElement>('button[form="workspace-move-form"]')!
    expect(button.disabled).toBe(true)
    expect(document.body.textContent).toContain(
      'Cells that read this file by path are not updated.',
    )
    for (const label of ['↑ Parent folder', 'data']) {
      document.querySelector<HTMLElement>('[role=combobox]')!.click()
      await nextTick()
      const option = document.querySelector<HTMLElement>(`[role="option"][aria-label="${label}"]`)
      expect(option).toBeTruthy()
      await new DOMWrapper(option!).trigger('mousedown')
      await vi.waitFor(() => expect(document.querySelector('[role=listbox]')).toBeNull())
    }
    expect(list.mock.calls.map((args) => args[0])).toEqual(['/p', '/', '/data'])
    expect(button.disabled).toBe(false)
    button.click()
    await settle()
    expect(move).toHaveBeenCalledWith(file.path, '/data', false)
  })

  it('asks to discard before beginning an operation and rechecks an edit made during inline rename', async () => {
    const guard = vi
      .fn()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(false)
    const rename = vi.spyOn(workspaceApi, 'renameFile')
    const wrapper = component([file], guard)
    await action(file, 'Delete')
    expect(guard).toHaveBeenCalledWith(file.path)
    expect(confirm).not.toHaveBeenCalled()
    await action(file, 'Rename')
    expect(wrapper.text()).toContain('Cells that read this file by path are not updated.')
    await wrapper.get('[aria-label="New name"]').setValue('saved.md')
    await wrapper.get('form').trigger('submit')
    await settle()
    expect(guard).toHaveBeenCalledTimes(3)
    expect(rename).not.toHaveBeenCalled()
  })

  it.each([true, false])(
    'retries folder deletion only when closing the open notebooks is accepted (%s)',
    async (accept) => {
      const deletion = vi
        .spyOn(workspaceApi, 'deleteFile')
        .mockRejectedValueOnce(
          new WorkspaceRefusedError('close first', 'FlowOpen', {
            flows: [{ name: 'exp', path: '/p/plots/exp.flow', session_id: 'first' }],
          }),
        )
        .mockResolvedValueOnce({ path: folder.path })
      component()
      await action(folder, 'Delete')
      expect(confirm.mock.calls[0]![0].message).toContain(
        'The folder and everything in it are deleted.',
      )
      confirm.mock.calls[0]![0].accept!()
      await settle()
      const close = confirm.mock.calls[1]![0]
      expect(close.message).toContain('1 open notebook will be closed: exp.')
      expect(close.acceptProps).toMatchObject({ label: 'Close and continue' })
      if (accept) close.accept!()
      else close.reject!()
      await settle()
      expect(deletion.mock.calls).toEqual(
        accept
          ? [
              [folder.path, false],
              [folder.path, ['first']],
            ]
          : [[folder.path, false]],
      )
      expect(useWorkspaceStore().refreshDirectory).toHaveBeenCalledTimes(accept ? 1 : 0)
    },
  )

  it('reports a collision in inline rename, then refreshes the listing on success', async () => {
    const names = new Set([file.name, 'taken.md'])
    const wrapper = await listFiles(names)
    const rename = vi.spyOn(workspaceApi, 'renameFile').mockImplementation(async (_path, name) => {
      if (names.has(name))
        throw new WorkspaceRefusedError(`"${name}" already exists`, 'AlreadyExists')
      names.delete(file.name)
      names.add(name)
      return { path: '/p/' + name }
    })
    await action(file, 'Rename')
    const form = wrapper.get('form')
    expect(form.text()).toContain('Cells that read this file by path are not updated.')
    expect(wrapper.text()).toContain('12B')
    expect(wrapper.find('[aria-label="Actions for notes.md"]').exists()).toBe(true)
    await form.get('input').setValue('taken.md')
    await form.trigger('submit')
    await settle()
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ detail: '"taken.md" already exists' }),
    )
    expect(wrapper.findAll('.row-link').map((row) => row.text())).toEqual(['taken.md'])
    await form.get('input').setValue('saved.md')
    await form.trigger('submit')
    await settle()
    expect(rename.mock.calls).toEqual([
      [file.path, 'taken.md', false],
      [file.path, 'saved.md', false],
    ])
    expect(wrapper.findAll('.row-link').map((row) => row.text())).toEqual(['taken.md', 'saved.md'])
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('retries the original notebook rename with consent for the displayed session', async () => {
    const rename = vi
      .spyOn(workspaceApi, 'renameFlow')
      .mockRejectedValueOnce(
        new WorkspaceRefusedError('close first', 'FlowOpen', {
          flows: [{ name: 'exp', path: flow.path, session_id: 'session' }],
        }),
      )
      .mockResolvedValueOnce({ renamed: 'other', path: '/p/other.flow', from: flow.path })
    const wrapper = component()
    await action(flow, 'Rename')
    const input = wrapper.get<HTMLInputElement>('[aria-label="New name"]')
    expect(input.element.value).toBe('exp.flow')
    await input.setValue('other.flow')
    await wrapper.get('form').trigger('submit')
    await settle()
    const question = confirm.mock.calls[0]![0]
    expect(question.message).toContain('1 open notebook will be closed: exp.')
    question.accept!()
    await settle()
    expect(rename.mock.calls).toEqual([
      [flow.path, 'other.flow', false],
      [flow.path, 'other.flow', ['session']],
    ])
    expect(useWorkspaceStore().refreshDirectory).toHaveBeenCalledOnce()
  })

  it.each([true, false])(
    'confirms permanent file deletion and reports the result (permitted=%s)',
    async (permitted) => {
      const names = new Set<string>([file.name])
      const wrapper = await listFiles(names)
      const remove = vi.spyOn(workspaceApi, 'deleteFile').mockImplementation(async (path) => {
        if (!permitted) throw new WorkspaceRefusedError('Permission denied', 'OsError')
        names.delete(file.name)
        return { path }
      })
      await action(file, 'Delete')
      const question = confirm.mock.calls[0]![0]
      expect(question.message).toContain('This action is permanent and cannot be undone.')
      expect(question.message).toContain(
        'Cells that read this file will fail the next time they run.',
      )
      expect(remove).not.toHaveBeenCalled()
      question.accept!()
      await settle()
      expect(remove).toHaveBeenCalledWith(file.path, false)
      expect(wrapper.findAll('.row-link').map((row) => row.text())).toEqual(
        permitted ? [] : [file.name],
      )
      if (!permitted)
        expect(toast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Permission denied' }))
    },
  )

  it('calls the notebook rename RPC and shows the OS refusal', async () => {
    const rename = vi
      .spyOn(workspaceApi, 'renameFlow')
      .mockRejectedValue(new WorkspaceRefusedError('Permission denied', 'OsError'))
    const wrapper = component()
    await action(flow, 'Rename')
    await wrapper.get('[aria-label="New name"]').setValue('other.flow')
    await wrapper.get('form').trigger('submit')
    await settle()
    expect(rename).toHaveBeenCalledWith(flow.path, 'other.flow', false)
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Permission denied' }))
  })
})
