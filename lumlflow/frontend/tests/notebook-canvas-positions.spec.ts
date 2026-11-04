import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import type { BranchRecord, CellSummary } from '@/api/slices/workspace/workspace.interface'

const server = vi.hoisted(() => ({ cells: [] as unknown[] }))

vi.mock('@/api/slices/workspace/workspace.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/slices/workspace/workspace.api')>()),
  workspaceApi: {
    renameCell: vi.fn(async (slug: string, to: string) => {
      server.cells = server.cells.map((held) =>
        (held as { slug: string }).slug === slug ? { ...(held as object), slug: to } : held,
      )
      return { slug: to, renamed_from: slug, branch: 'main' }
    }),
    deleteCell: vi.fn(async (slug: string) => {
      server.cells = server.cells.filter((held) => (held as { slug: string }).slug !== slug)
      return {}
    }),
    cellsList: vi.fn(async () => ({ cells: server.cells })),
    forkBranch: vi.fn(async (name: string) => ({ branch: name })),
    tree: vi.fn(async () => ({ branches: [], agent_sessions: [] })),
    journalSince: vi.fn(async () => ({ transactions: [] })),
  },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ currentRoute: { value: { query: {} } } }),
}))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { useFlowStore } from '@/store/flow'

const mocked = workspaceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

const KEY = 'lumlflow:flow-canvas-positions'

const cell = (slug: string, consumes: Record<string, string> = {}) =>
  ({ slug, consumes }) as unknown as CellSummary

const lane = (branch: string, checkedOut: boolean) =>
  ({ branch, branch_id: `b-${branch}`, checked_out: checkedOut }) as unknown as BranchRecord

function stored(): unknown {
  return JSON.parse(window.localStorage.getItem(KEY) ?? 'null')
}

async function onLane(
  store: ReturnType<typeof useFlowStore>,
  branch: string,
  cells: CellSummary[],
): Promise<void> {
  store.branches = [lane('main', branch === 'main'), lane('side', branch === 'side')]
  server.cells = cells
  await store.fetchCells()
}

async function makeStore(): Promise<ReturnType<typeof useFlowStore>> {
  setActivePinia(createPinia())
  const store = useFlowStore()
  store.currentFlow = 'churn'
  await onLane(store, 'main', [cell('load'), cell('train')])
  return store
}

beforeEach(() => {
  window.localStorage.clear()
})

describe('the stored canvas positions', () => {
  it('follow a cell when it is renamed', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 0, y: 0 }, train: { x: 300, y: 500 } })
    await store.renameCell('train', 'fit')
    expect(store.canvasPositions).toEqual({ load: { x: 0, y: 0 }, fit: { x: 300, y: 500 } })
  })

  it('give a new cell under a renamed cell’s old name no place of its own', async () => {
    const store = await makeStore()
    await onLane(store, 'main', [cell('load_data'), cell('train', { frame: 'load_data.frame' })])
    store.saveCanvasPositions({ load_data: { x: 900, y: -300 }, train: { x: 900, y: 400 } })
    await store.renameCell('load_data', 'load_data_2')
    server.cells = [...server.cells, cell('load_data')]
    await store.fetchCells()
    expect(store.canvasPositions).toEqual({
      load_data_2: { x: 900, y: -300 },
      train: { x: 900, y: 400 },
    })
    expect(store.canvasLayout.get('load_data')).not.toEqual({ x: 900, y: -300 })
  })

  it('drop cells the lane no longer has, however they went', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 0, y: 0 }, train: { x: 300, y: 500 } })
    server.cells = [cell('load'), cell('fit')]
    await store.fetchCells()
    expect(store.canvasPositions).toEqual({ load: { x: 0, y: 0 } })
  })

  it('ignore a cell list that comes back after a newer one', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 0, y: 0 }, train: { x: 300, y: 500 } })
    let answerStale: (() => void) | null = null
    mocked.cellsList!.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          const stale = server.cells
          answerStale = () => resolve({ cells: stale })
        }),
    )
    const stale = store.fetchCells()
    await store.renameCell('train', 'fit')
    answerStale!()
    await stale
    expect(store.cells.map((held) => held.slug)).toEqual(['load', 'fit'])
    expect(store.canvasPositions).toEqual({ load: { x: 0, y: 0 }, fit: { x: 300, y: 500 } })
  })

  it('keep the layout when the lane briefly lists no cells', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 0, y: 0 } })
    server.cells = []
    await store.fetchCells()
    expect(store.canvasPositions).toEqual({ load: { x: 0, y: 0 } })
  })

  it('stay with the lane the cells on screen came from while another lane loads', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 1, y: 2 } })
    store.branches = [lane('main', false), lane('side', true)]
    expect(store.canvasPositions).toEqual({ load: { x: 1, y: 2 } })
    store.saveCanvasPositions({ train: { x: 3, y: 4 } })
    server.cells = [cell('load'), cell('train')]
    await store.fetchCells()
    expect(store.canvasPositions).toEqual({})
  })

  it('already hold the new name while the rename is in flight', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 0, y: 0 }, train: { x: 300, y: 500 } })
    let seenDuringRename: unknown
    mocked.renameCell!.mockImplementationOnce(async (slug: string, to: string) => {
      server.cells = [cell('load'), cell(to)]
      await store.fetchCells()
      seenDuringRename = store.canvasLayout.get(to)
      return { slug: to, renamed_from: slug, branch: 'main' }
    })
    await store.renameCell('train', 'fit')
    expect(seenDuringRename).toEqual({ x: 300, y: 500 })
    expect(store.canvasPositions).toEqual({ load: { x: 0, y: 0 }, fit: { x: 300, y: 500 } })
  })

  it('hold the whole canvas still while the rename rewires the cells below', async () => {
    const store = await makeStore()
    await onLane(store, 'main', [
      cell('load'),
      cell('train', { frame: 'load.frame' }),
      cell('report', { model: 'train.model' }),
    ])
    const before = Object.fromEntries(store.canvasLayout)
    const seen: Record<string, unknown>[] = []
    mocked.renameCell!.mockImplementationOnce(async (slug: string, to: string) => {
      server.cells = [
        cell('load'),
        cell(to, { frame: 'load.frame' }),
        cell('report', { model: 'train.model' }),
      ]
      await store.fetchCells()
      seen.push(Object.fromEntries(store.canvasLayout))
      server.cells = [
        cell('load'),
        cell(to, { frame: 'load.frame' }),
        cell('report', { model: `${to}.model` }),
      ]
      return { slug: to, renamed_from: slug, branch: 'main' }
    })
    await store.renameCell('train', 'fit')
    const expected = { load: before.load, fit: before.train, report: before.report }
    for (const layout of seen) expect(layout).toEqual(expected)
    expect(Object.fromEntries(store.canvasLayout)).toEqual(expected)
    expect(store.hasCanvasLayout).toBe(false)
  })

  it('follow the name the backend settled on', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ train: { x: 300, y: 500 } })
    mocked.renameCell!.mockImplementationOnce(async () => {
      server.cells = [cell('load'), cell('fit_model')]
      return { slug: 'fit_model', renamed_from: 'train', branch: 'main' }
    })
    await store.renameCell('train', 'Fit model')
    expect(store.canvasPositions).toEqual({ fit_model: { x: 300, y: 500 } })
  })

  it('stay as they were when the rename is refused', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ train: { x: 300, y: 500 } })
    mocked.renameCell!.mockRejectedValueOnce(new Error('taken'))
    await expect(store.renameCell('train', 'fit')).rejects.toThrow('taken')
    expect(store.canvasPositions).toEqual({ train: { x: 300, y: 500 } })
  })

  it('are forgotten for a deleted cell', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 0, y: 0 }, train: { x: 300, y: 500 } })
    await store.deleteCell('train')
    expect(store.canvasPositions).toEqual({ load: { x: 0, y: 0 } })
  })

  it('are kept per lane', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 1, y: 2 } })
    await onLane(store, 'side', [cell('load'), cell('train')])
    expect(store.canvasPositions).toEqual({})
    expect(store.hasCanvasLayout).toBe(false)
    store.saveCanvasPositions({ load: { x: 3, y: 4 } })
    await onLane(store, 'main', [cell('load'), cell('train')])
    expect(store.canvasPositions).toEqual({ load: { x: 1, y: 2 } })
  })

  it('are handed to a lane forked from this one', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 1, y: 2 } })
    await store.createLane('side')
    await onLane(store, 'side', [cell('load'), cell('train')])
    expect(store.canvasPositions).toEqual({ load: { x: 1, y: 2 } })
  })

  it('replace whatever a former lane of the same name left behind on fork', async () => {
    const store = await makeStore()
    await onLane(store, 'side', [cell('load'), cell('train')])
    store.saveCanvasPositions({ load: { x: 9, y: 9 } })
    await onLane(store, 'main', [cell('load'), cell('train')])
    await store.createLane('side')
    await onLane(store, 'side', [cell('load'), cell('train')])
    expect(store.canvasPositions).toEqual({})
  })

  it('are reset for the lane on screen only', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 0, y: 0 } })
    await onLane(store, 'side', [cell('load'), cell('train')])
    store.saveCanvasPositions({ load: { x: 5, y: 5 } })
    store.resetCanvasLayout()
    expect(store.canvasPositions).toEqual({})
    expect(store.hasCanvasLayout).toBe(false)
    await onLane(store, 'main', [cell('load'), cell('train')])
    expect(store.canvasPositions).toEqual({ load: { x: 0, y: 0 } })
  })

  it('leave other flows alone', async () => {
    const store = await makeStore()
    store.saveCanvasPositions({ load: { x: 1, y: 2 } })
    store.currentFlow = 'other'
    store.saveCanvasPositions({ load: { x: 3, y: 4 } })
    await nextTick()
    expect(stored()).toEqual({
      churn: { main: { load: { x: 1, y: 2 } } },
      other: { main: { load: { x: 3, y: 4 } } },
    })
  })

  it.each([
    ['null', 'null'],
    ['a list', '[1, 2]'],
    ['a string', '"oops"'],
    ['positions saved per flow only', '{"churn": {"load": {"x": 1, "y": 2}}}'],
  ])('survive %s stored under the key', async (_, raw) => {
    window.localStorage.setItem(KEY, raw)
    const store = await makeStore()
    expect(store.canvasPositions).toEqual({})
    expect(store.hasCanvasLayout).toBe(false)
    store.saveCanvasPositions({ load: { x: 1, y: 2 } })
    expect(store.canvasPositions).toEqual({ load: { x: 1, y: 2 } })
  })

  it('drop entries that are not positions', async () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        churn: { main: { load: { x: 1, y: 2 }, train: { x: 'a', y: 2 }, bad: null }, side: 3 },
        broken: 5,
      }),
    )
    const store = await makeStore()
    expect(store.canvasPositions).toEqual({ load: { x: 1, y: 2 } })
  })
})
