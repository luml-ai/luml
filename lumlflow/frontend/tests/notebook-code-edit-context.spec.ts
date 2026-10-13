
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { BranchRecord } from '@/api/slices/workspace/workspace.interface'

const toastAdd = vi.fn()

vi.mock('@/api/slices/workspace/workspace.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/slices/workspace/workspace.api')>()),
  workspaceApi: {
    cellSource: vi.fn(),
    editCell: vi.fn(),
    tree: vi.fn(),
    forkBranch: vi.fn(),
    switchBranch: vi.fn(),
    cellsList: vi.fn(async () => ({ cells: [] })),
    journalSince: vi.fn(async () => ({ transactions: [] })),
  },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: toastAdd }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: toastAdd }) }))

import { workspaceApi, WorkspaceRefusedError } from '@/api/slices/workspace/workspace.api'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import CreateLaneDialog from '@/components/notebooks/lanes/CreateLaneDialog.vue'
import UiCodeEditor from '@/components/ui/code-editor/UiCodeEditor.vue'
import { useFlowStore } from '@/store/flow'
import { settle } from './fakes'

const mocked = workspaceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

function lane(branch: string, checkedOut: boolean): BranchRecord {
  return {
    branch,
    branch_id: `b-${branch}`,
    checked_out: checkedOut,
    head_step: 5,
    newest_step: 5,
    parent: null,
    parent_step: null,
  } as unknown as BranchRecord
}

let lanes: BranchRecord[]
let heads: Record<string, string>
let store: ReturnType<typeof useFlowStore>
let wrapper: VueWrapper

function onScreen(branch: string): void {
  lanes = lanes.map((record) => ({ ...record, checked_out: record.branch === branch }))
  store.branches = lanes
}

function rewind(branch: string): void {
  lanes = lanes.map((record) =>
    record.branch === branch ? { ...record, head_step: record.newest_step - 2 } : record,
  )
}

function conflict(): WorkspaceRefusedError {
  return new WorkspaceRefusedError('`train` has a newer version', 'EditConflict')
}

function shownSource(): string {
  const editor = wrapper.findAllComponents(UiCodeEditor).find((found) => found.props('readonly'))
  return editor?.props('modelValue' as never) as unknown as string
}

function isEditing(): boolean {
  return wrapper.findAllComponents(UiCodeEditor).some((found) => !found.props('readonly'))
}

function buttonNamed(label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

async function click(label: string): Promise<void> {
  const button = buttonNamed(label)
  if (!button) throw new Error(`no ${label} button`)
  await button.trigger('click')
  await settle()
}

async function edit(draft: string): Promise<void> {
  await click('Edit')
  const editor = wrapper.findAllComponents(UiCodeEditor).find((found) => !found.props('readonly'))
  editor?.vm.$emit('update:modelValue', draft)
  await settle()
}

function forkPromptOpen(): boolean {
  return document.body.querySelector('[role="dialog"]') !== null
}

async function answerForkPrompt(name: string): Promise<void> {
  const input = document.body.querySelector<HTMLInputElement>('[role="dialog"] input')
  if (!input) throw new Error('no fork prompt')
  input.value = name
  input.dispatchEvent(new Event('input'))
  await settle()
  document.body.querySelector<HTMLFormElement>('[role="dialog"] form')?.requestSubmit()
  await settle()
  await settle()
}

beforeEach(async () => {
  for (const fn of Object.values(mocked)) fn.mockClear()
  toastAdd.mockClear()
  setActivePinia(createPinia())
  store = useFlowStore()
  lanes = [lane('main', true), lane('sweep', false)]
  heads = { main: 'h-main-1', sweep: 'h-sweep-1' }
  store.branches = lanes

  mocked.cellSource.mockImplementation(async (slug: string, _flow?: string, branch?: string) => ({
    slug,
    branch,
    definition_hash: heads[branch ?? 'main'],
    source: `source of ${slug} on ${branch} at ${heads[branch ?? 'main']}`,
  }))
  mocked.editCell.mockImplementation(async (slug: string, _source, _flow, branch: string) => {
    heads[branch] = `${heads[branch]}+`
    return { slug, branch, definition_hash: heads[branch], written_to_files: true, flags: [] }
  })
  mocked.tree.mockImplementation(async () => ({ branches: lanes, agent_sessions: [] }))
  mocked.forkBranch.mockImplementation(async (name: string, from: string) => {
    lanes = [...lanes, lane(name, false)]
    heads[name] = heads[from]
    return { branch: name, from_branch: from }
  })
  mocked.switchBranch.mockImplementation(async (branch: string) => {
    lanes = lanes.map((record) => ({ ...record, checked_out: record.branch === branch }))
    return {}
  })

  wrapper = mount(NotebookCode, {
    props: { slug: 'train' },
    attachTo: document.body,
  })
  await settle()
})

afterEach(() => {
  wrapper.unmount()
  document.body.innerHTML = ''
})

describe('the edit context a save carries', () => {
  it('sends the hash the source was read at as the base, on the lane it was read on', async () => {
    await edit('new source')
    await click('Save')

    expect(mocked.editCell).toHaveBeenCalledWith('train', 'new source', undefined, 'main', {
      base: 'h-main-1',
      force: undefined,
    })
  })

  it('bases a second save on the version the first one wrote', async () => {
    await edit('first')
    await click('Save')
    await edit('second')
    await click('Save')

    expect(mocked.editCell).toHaveBeenCalledTimes(2)
    expect(mocked.editCell.mock.calls[1]?.[4]).toEqual({ base: 'h-main-1+', force: undefined })
    expect(wrapper.find('[data-testid="edit-conflict"]').exists()).toBe(false)
    expect(isEditing()).toBe(false)
  })

  it('saves on the lane the edit began on and then shows the lane on screen', async () => {
    await edit('new source')
    onScreen('sweep')
    await click('Save')

    expect(mocked.editCell.mock.calls[0]?.[3]).toBe('main')
    expect(shownSource()).toBe('source of train on sweep at h-sweep-1')
  })
})

describe('a conflict with a newer version', () => {
  beforeEach(async () => {
    mocked.editCell.mockRejectedValueOnce(conflict())
    await edit('my draft')
    await click('Save')
  })

  it('keeps the draft and offers Overwrite and Keep theirs', () => {
    expect(wrapper.find('[data-testid="edit-conflict"]').exists()).toBe(true)
    expect(buttonNamed('Overwrite')).toBeDefined()
    expect(buttonNamed('Keep theirs')).toBeDefined()
    expect(isEditing()).toBe(true)
  })

  it('sends the same edit with force on Overwrite and shows the saved source', async () => {
    await click('Overwrite')

    expect(mocked.editCell).toHaveBeenCalledTimes(2)
    expect(mocked.editCell.mock.calls[1]).toEqual([
      'train',
      'my draft',
      undefined,
      'main',
      { base: 'h-main-1', force: true },
    ])
    expect(isEditing()).toBe(false)
    expect(shownSource()).toBe('source of train on main at h-main-1+')
  })

  it('drops the draft on Keep theirs and reloads for the lane on screen', async () => {
    heads.main = 'h-main-agent'
    onScreen('sweep')
    await click('Keep theirs')

    expect(mocked.editCell).toHaveBeenCalledTimes(1)
    expect(isEditing()).toBe(false)
    expect(wrapper.find('[data-testid="edit-conflict"]').exists()).toBe(false)
    expect(mocked.cellSource).toHaveBeenLastCalledWith('train', undefined, 'sweep')
    expect(shownSource()).toBe('source of train on sweep at h-sweep-1')
  })
})

describe('a refusal that is not a conflict', () => {
  it('shows a plain error, keeps the draft, and offers no conflict choices', async () => {
    mocked.editCell.mockRejectedValueOnce(
      new WorkspaceRefusedError('`train` cannot be edited with empty source', 'FlowError'),
    )
    await edit('my draft')
    await click('Save')

    expect(toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        detail: '`train` cannot be edited with empty source',
      }),
    )
    expect(isEditing()).toBe(true)
    expect(buttonNamed('Overwrite')).toBeUndefined()
    expect(buttonNamed('Keep theirs')).toBeUndefined()
  })
})

describe('a save after the edit lane was rewound', () => {
  it('forks the lane first, then saves the draft there with the base it began from', async () => {
    await edit('my draft')
    rewind('main')
    await click('Save')

    expect(forkPromptOpen()).toBe(true)
    expect(mocked.editCell).not.toHaveBeenCalled()

    await answerForkPrompt('sweep2')

    expect(mocked.forkBranch).toHaveBeenCalledWith('sweep2', 'main', undefined)
    expect(mocked.switchBranch).toHaveBeenCalledWith('sweep2', expect.any(String), undefined)
    expect(store.currentBranch?.branch).toBe('sweep2')
    expect(mocked.editCell).toHaveBeenCalledWith('train', 'my draft', undefined, 'sweep2', {
      base: 'h-main-1',
      force: undefined,
    })
  })

  it('keeps the screen where it is when the edit lane is not on screen', async () => {
    await edit('my draft')
    onScreen('sweep')
    rewind('main')
    await click('Save')
    await answerForkPrompt('tune')

    expect(mocked.forkBranch).toHaveBeenCalledWith('tune', 'main', undefined)
    expect(mocked.switchBranch).not.toHaveBeenCalled()
    expect(store.currentBranch?.branch).toBe('sweep')
    expect(mocked.editCell.mock.calls[0]?.[3]).toBe('tune')
  })

  it('keeps the draft on the original lane when the prompt is dismissed', async () => {
    await edit('my draft')
    rewind('main')
    await click('Save')
    wrapper.findComponent(CreateLaneDialog).vm.$emit('update:visible', false)
    await settle()

    expect(mocked.editCell).not.toHaveBeenCalled()
    expect(mocked.forkBranch).not.toHaveBeenCalled()
    expect(isEditing()).toBe(true)
    expect(wrapper.findComponent(CreateLaneDialog).props('from')).toBe('main')
  })
})
