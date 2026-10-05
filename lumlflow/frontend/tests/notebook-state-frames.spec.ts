/**
 * The notebook follows the daemon's state frames: hints for changes with no
 * journal transaction behind them. A move from elsewhere and an experiment
 * deleted under a cell on screen refetch the lane after the settle delay; a
 * removal on another lane and a `refreshing` hint change nothing.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { BranchRecord, CellSummary } from '@/api/slices/workspace/workspace.interface'
import type { StateName, StreamFrame } from '@/api/streams/flow'

vi.mock('@/api/slices/workspace/workspace.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/slices/workspace/workspace.api')>()),
  workspaceApi: {
    assetPreview: vi.fn(),
    tree: vi.fn(),
    cellsList: vi.fn(),
    journalSince: vi.fn(async () => ({ transactions: [] })),
  },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import NotebookOutput from '@/components/notebooks/cell/NotebookOutput.vue'
import CellOutputTabContent from '@/components/notebooks/cell/preview/CellOutputTabContent.vue'
import { useFlowStore } from '@/store/flow'
import { settle } from './fakes'

const FLOW = '/p/churn.flow'
const SETTLE_MS = 250

const mocked = workspaceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

function lane(branch: string, checkedOut: boolean): BranchRecord {
  return {
    branch,
    branch_id: `b-${branch}`,
    checked_out: checkedOut,
    head_step: 5,
    parent: null,
  } as unknown as BranchRecord
}

function summary(slug: string): CellSummary {
  return {
    slug,
    state: 'synced',
    primary: 'model',
    kinds: { model: 'model' },
    consumes: {},
    cost_seconds: 1,
    causes: [],
    reused: false,
    changed_step: 1,
    mat_id: `m-${slug}`,
  } as unknown as CellSummary
}

function state(name: StateName, extra: { lane?: string; cell?: string } = {}): StreamFrame {
  return { channel: 'journal', type: 'state', state: name, flow: FLOW, step: 5, ...extra }
}

let store: ReturnType<typeof useFlowStore>
let daemonOrder: string[]
let availability: string
let wrapper: VueWrapper | null

beforeEach(() => {
  vi.useFakeTimers()
  for (const fn of Object.values(mocked)) fn.mockClear()
  setActivePinia(createPinia())
  store = useFlowStore()
  store.branches = [lane('main', true), lane('sweep', false)]
  store.cells = [summary('score'), summary('report')]
  daemonOrder = ['score', 'report']
  availability = 'experiment available'
  wrapper = null

  mocked.tree.mockImplementation(async () => ({ branches: store.branches, agent_sessions: [] }))
  mocked.cellsList.mockImplementation(async () => ({ cells: daemonOrder.map(summary) }))
  mocked.assetPreview.mockImplementation(async () => ({
    preview: { blocks: [{ kind: 'text', text: availability }], truncated: false },
  }))
})

afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
})

async function afterSettleDelay(): Promise<void> {
  vi.advanceTimersByTime(SETTLE_MS)
  await settle()
}

describe('the notebook store on state frames', () => {
  it('refetches after a move from elsewhere and shows the new order', async () => {
    daemonOrder = ['report', 'score']
    store.receiveLiveFrame(state('order_changed'))
    await settle()
    expect(mocked.cellsList).not.toHaveBeenCalled()

    await afterSettleDelay()

    expect(mocked.cellsList).toHaveBeenCalledTimes(1)
    expect(store.cells.map((cell) => cell.slug)).toEqual(['report', 'score'])
  })

  it('refetches and reloads the open output panel on a removal on the lane on screen', async () => {
    wrapper = mount(NotebookOutput, { props: { slug: 'score', name: 'model' } })
    await settle()
    expect(mocked.assetPreview).toHaveBeenCalledTimes(1)

    availability = 'experiment removed'
    store.receiveLiveFrame(state('experiment_removed', { lane: 'main', cell: 'score' }))
    await afterSettleDelay()

    expect(mocked.cellsList).toHaveBeenCalledTimes(1)
    expect(mocked.assetPreview).toHaveBeenCalledTimes(2)
    expect(wrapper.findComponent(CellOutputTabContent).props('content')).toEqual({
      status: 'ready',
      blocks: [{ kind: 'text', text: 'experiment removed' }],
      truncated: false,
    })
  })

  it("leaves another cell's open output panel alone", async () => {
    wrapper = mount(NotebookOutput, { props: { slug: 'report', name: 'model' } })
    await settle()

    store.receiveLiveFrame(state('experiment_removed', { lane: 'main', cell: 'score' }))
    await afterSettleDelay()

    expect(mocked.assetPreview).toHaveBeenCalledTimes(1)
  })

  it('makes no request on a removal on another lane', async () => {
    wrapper = mount(NotebookOutput, { props: { slug: 'score', name: 'model' } })
    await settle()

    store.receiveLiveFrame(state('experiment_removed', { lane: 'sweep', cell: 'score' }))
    await afterSettleDelay()

    expect(mocked.tree).not.toHaveBeenCalled()
    expect(mocked.cellsList).not.toHaveBeenCalled()
    expect(mocked.assetPreview).toHaveBeenCalledTimes(1)
  })

  it('refetches once for a burst of moves within the settle delay', async () => {
    store.receiveLiveFrame(state('order_changed'))
    vi.advanceTimersByTime(SETTLE_MS / 2)
    store.receiveLiveFrame(state('order_changed'))
    vi.advanceTimersByTime(SETTLE_MS / 2)
    store.receiveLiveFrame(state('order_changed'))
    await afterSettleDelay()
    await afterSettleDelay()

    expect(mocked.tree).toHaveBeenCalledTimes(1)
    expect(mocked.cellsList).toHaveBeenCalledTimes(1)
  })

  it('ignores a refreshing hint', async () => {
    const before = {
      cells: store.cells,
      liveRuns: store.liveRuns,
      agentClaims: store.agentClaims,
      experimentRemovals: store.experimentRemovals,
    }

    store.receiveLiveFrame(state('refreshing', { lane: 'main', cell: 'score' }))
    await afterSettleDelay()

    expect(mocked.tree).not.toHaveBeenCalled()
    expect(mocked.cellsList).not.toHaveBeenCalled()
    expect({
      cells: store.cells,
      liveRuns: store.liveRuns,
      agentClaims: store.agentClaims,
      experimentRemovals: store.experimentRemovals,
    }).toEqual(before)
  })
})
