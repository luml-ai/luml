/**
 * An open notebook panel shows the lane on screen and what that lane holds for
 * its cell now: the output and logs panels follow the result the lane
 * observed, the code panel follows the version. A refresh that changes
 * neither leaves the panel alone, and a draft outlives any reload.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { BranchRecord, CellSummary } from '@/api/slices/workspace/workspace.interface'

const toastAdd = vi.fn()

vi.mock('@/api/slices/workspace/workspace.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/slices/workspace/workspace.api')>()),
  workspaceApi: {
    assetPreview: vi.fn(),
    cellLogs: vi.fn(),
    cellSource: vi.fn(),
    editCell: vi.fn(),
    tree: vi.fn(),
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
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'
import NotebookOutput from '@/components/notebooks/cell/NotebookOutput.vue'
import CellOutputTabContent from '@/components/notebooks/cell/preview/CellOutputTabContent.vue'
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

function summary(overrides: Partial<CellSummary>): CellSummary {
  return {
    slug: 'train',
    state: 'synced',
    primary: 'model',
    kinds: { model: 'model' },
    consumes: {},
    cost_seconds: 1,
    causes: [],
    reused: false,
    changed_step: 1,
    mat_id: 'm-1',
    ...overrides,
  }
}

/** What the daemon holds for `train`, per lane: its result and its version. */
let results: Record<string, string>
let versions: Record<string, string>
let store: ReturnType<typeof useFlowStore>
let wrapper: VueWrapper

function onScreen(branch: string): void {
  store.branches = store.branches.map((record) => ({
    ...record,
    checked_out: record.branch === branch,
  }))
}

/** The cell list arriving from a refetch, a fresh object as the store would get. */
function cellListReports(overrides: Partial<CellSummary>): void {
  const current = store.cells.find((cell) => cell.slug === 'train')
  store.cells = [summary({ ...current, ...overrides })]
}

function shownPreview(): unknown {
  return wrapper.findComponent(CellOutputTabContent).props('content')
}

function readOnlySource(): string {
  const editor = wrapper.findAllComponents(UiCodeEditor).find((found) => found.props('readonly'))
  return editor?.props('modelValue' as never) as unknown as string
}

function draft(): string | undefined {
  const editor = wrapper.findAllComponents(UiCodeEditor).find((found) => !found.props('readonly'))
  return editor?.props('modelValue' as never) as unknown as string | undefined
}

async function click(label: string): Promise<void> {
  const button = wrapper.findAll('button').find((found) => found.text() === label)
  if (!button) throw new Error(`no ${label} button`)
  await button.trigger('click')
  await settle()
}

function preview(result: string) {
  return {
    preview: { blocks: [{ kind: 'text', text: result }], truncated: false },
  }
}

beforeEach(() => {
  for (const fn of Object.values(mocked)) fn.mockClear()
  toastAdd.mockClear()
  setActivePinia(createPinia())
  store = useFlowStore()
  store.branches = [lane('main', true), lane('sweep', false)]
  store.cells = [summary({})]
  results = { main: 'result m-1', sweep: 'result on sweep' }
  versions = { main: 'h-main-1', sweep: 'h-sweep-1' }

  mocked.assetPreview.mockImplementation(async (_target, _flow, branch: string) =>
    preview(results[branch] ?? ''),
  )
  mocked.cellLogs.mockImplementation(async (slug: string, _flow, branch: string) => ({
    slug,
    branch,
    logs: `logs of ${results[branch]}`,
  }))
  mocked.cellSource.mockImplementation(async (slug: string, _flow, branch: string) => ({
    slug,
    branch,
    definition_hash: versions[branch],
    source: `source of ${slug} on ${branch} at ${versions[branch]}`,
  }))
  mocked.editCell.mockImplementation(async (slug: string, _source, _flow, branch: string, edit) => {
    if (edit.base !== versions[branch] && !edit.force) {
      throw new WorkspaceRefusedError(`\`${slug}\` has a newer version`, 'EditConflict')
    }
    return { slug, branch, definition_hash: `${versions[branch]}+`, flags: [] }
  })
  mocked.tree.mockImplementation(async () => ({ branches: store.branches, agent_sessions: [] }))
})

afterEach(() => {
  wrapper.unmount()
  document.body.innerHTML = ''
})

describe('the output panel', () => {
  beforeEach(async () => {
    wrapper = mount(NotebookOutput, { props: { slug: 'train', name: 'model' } })
    await settle()
  })

  it('reloads and shows the new result after a rerun', async () => {
    results.main = 'result m-2'
    cellListReports({ mat_id: 'm-2' })
    await settle()

    expect(mocked.assetPreview).toHaveBeenCalledTimes(2)
    expect(shownPreview()).toEqual({
      status: 'ready',
      blocks: [{ kind: 'text', text: 'result m-2' }],
      truncated: false,
    })
  })

  it('makes no new request when a refresh changes neither version nor result', async () => {
    cellListReports({ state: 'synced', causes: [] })
    await settle()

    expect(mocked.assetPreview).toHaveBeenCalledTimes(1)
  })

  it('keeps the latest reload when an earlier one answers last', async () => {
    let answerEarlier: () => void = () => {}
    mocked.assetPreview.mockImplementationOnce(
      () => new Promise((resolve) => (answerEarlier = () => resolve(preview('result m-2')))),
    )
    cellListReports({ mat_id: 'm-2' })
    await settle()
    results.main = 'result m-3'
    cellListReports({ mat_id: 'm-3' })
    await settle()
    answerEarlier()
    await settle()

    expect(shownPreview()).toEqual({
      status: 'ready',
      blocks: [{ kind: 'text', text: 'result m-3' }],
      truncated: false,
    })
  })

  it('drops the failure of a superseded reload', async () => {
    let failEarlier: () => void = () => {}
    mocked.assetPreview.mockImplementationOnce(
      () => new Promise((_resolve, reject) => (failEarlier = () => reject(new Error('gone')))),
    )
    cellListReports({ mat_id: 'm-2' })
    await settle()
    results.main = 'result m-3'
    cellListReports({ mat_id: 'm-3' })
    await settle()
    failEarlier()
    await settle()

    expect(shownPreview()).toMatchObject({ status: 'ready' })
  })
})

describe('the logs panel', () => {
  beforeEach(async () => {
    results.main = 'result m-2'
    store.cells = [summary({ mat_id: 'm-2' })]
    wrapper = mount(NotebookLogs, { props: { slug: 'train' } })
    await settle()
  })

  it('shows the logs of the restored result after a rewind', async () => {
    expect(wrapper.text()).toContain('logs of result m-2')

    results.main = 'result m-1'
    cellListReports({ mat_id: 'm-1' })
    await settle()

    expect(wrapper.text()).toContain('logs of result m-1')
    expect(wrapper.text()).not.toContain('m-2')
  })

  it('follows a lane switch', async () => {
    onScreen('sweep')
    await settle()

    expect(mocked.cellLogs).toHaveBeenLastCalledWith('train', undefined, 'sweep')
    expect(wrapper.text()).toContain('logs of result on sweep')
  })

  it('does not reload when only the version changes', async () => {
    cellListReports({ changed_step: 7 })
    await settle()

    expect(mocked.cellLogs).toHaveBeenCalledTimes(1)
  })
})

describe('the code panel', () => {
  beforeEach(async () => {
    wrapper = mount(NotebookCode, { props: { slug: 'train' }, attachTo: document.body })
    await settle()
  })

  it("shows the other lane's source after a lane switch", async () => {
    expect(readOnlySource()).toBe('source of train on main at h-main-1')

    onScreen('sweep')
    cellListReports({ changed_step: 3, mat_id: 'm-sweep' })
    await settle()

    expect(readOnlySource()).toBe('source of train on sweep at h-sweep-1')
  })

  it('reloads on a new version and not on a new result', async () => {
    cellListReports({ mat_id: 'm-2' })
    await settle()
    expect(mocked.cellSource).toHaveBeenCalledTimes(1)

    versions.main = 'h-main-2'
    cellListReports({ changed_step: 2 })
    await settle()

    expect(mocked.cellSource).toHaveBeenCalledTimes(2)
    expect(readOnlySource()).toBe('source of train on main at h-main-2')
  })

  it('keeps a draft and its edit context when a newer version arrives', async () => {
    await click('Edit')
    wrapper
      .findAllComponents(UiCodeEditor)
      .find((found) => !found.props('readonly'))
      ?.vm.$emit('update:modelValue', 'my draft')
    await settle()

    versions.main = 'h-main-agent'
    cellListReports({ changed_step: 2 })
    await settle()

    expect(mocked.cellSource).toHaveBeenCalledTimes(2)
    expect(draft()).toBe('my draft')

    await click('Save')

    expect(mocked.editCell).toHaveBeenCalledWith('train', 'my draft', undefined, 'main', {
      base: 'h-main-1',
      force: undefined,
    })
    expect(wrapper.find('[data-testid="edit-conflict"]').exists()).toBe(true)
    expect(draft()).toBe('my draft')
  })
})
