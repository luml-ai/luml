import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { CellSummary, RanLane } from '@/api/slices/workspace/workspace.interface'

const added = vi.fn()

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: added }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: added }) }))

import NotebookToolbar from '@/components/notebooks/NotebookToolbar.vue'
import { useFlowStore } from '@/store/flow'

function summary(slug: string, order: string): CellSummary {
  return {
    slug,
    state: 'synced',
    primary: null,
    kinds: {},
    consumes: {},
    cost_seconds: null,
    causes: [],
    reused: false,
    changed_step: 1,
    order,
    mat_id: null,
  }
}

function ranLane(overrides: Partial<RanLane>): RanLane {
  return {
    path: '/p/churn.flow',
    branch: 'main',
    target: 'train',
    targets: ['train'],
    executed: [],
    cached: [],
    pruned: [],
    failed: null,
    failures: [],
    unplanned: [],
    abandoned: false,
    ...overrides,
  }
}

async function rerun(result: RanLane): Promise<{ severity: string; detail: string }> {
  const store = useFlowStore()
  vi.spyOn(store, 'ensureOnLaneHead').mockReturnValue(true)
  vi.spyOn(store, 'runLane').mockResolvedValue(result)
  const wrapper = mount(NotebookToolbar, {
    global: { stubs: { NotebookCellCreator: true } },
  })
  const button = wrapper.findAll('button').find((node) => node.text().includes('Rerun lane'))
  await button!.trigger('click')
  await flushPromises()
  return added.mock.calls.at(-1)![0]
}

beforeEach(() => {
  added.mockClear()
  setActivePinia(createPinia())
})

describe('notebook cell order', () => {
  it('follows the saved order rather than the slug order', () => {
    const store = useFlowStore()
    store.cells = [summary('alpha', '3'), summary('beta', '1'), summary('gamma', '1.5')]

    expect(store.notebookCells.map((cell) => cell.name)).toEqual(['beta', 'gamma', 'alpha'])
  })
})

describe('rerun lane toast', () => {
  it('reports the planning error when a target could not be planned', async () => {
    const toast = await rerun(
      ranLane({ unplanned: [{ target: 'train', error: 'no cell named rows on main' }] }),
    )

    expect(toast.severity).toBe('error')
    expect(toast.detail).toContain('no cell named rows on main')
  })

  it('does not report success when the run was stopped', async () => {
    const toast = await rerun(ranLane({ abandoned: true }))

    expect(toast.detail).not.toContain('Reran lane')
  })

  it('reports success when every target ran', async () => {
    const toast = await rerun(ranLane({ executed: ['train'] }))

    expect(toast.severity).toBe('success')
    expect(toast.detail).toBe('Reran lane: 1 executed, 0 cached')
  })
})
