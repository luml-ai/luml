/**
 * The notebooks page's live states: what is happening to a cell right now, as
 * opposed to what its stored state says it last was.
 *
 * None of it is journaled. A run's lifecycle and an agent's call arrive as
 * frames and in the catch-up, and the store is the only place that remembers
 * them — so the card reads them off the store, and the pairing tag says what
 * the agent is inside of.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import { Workflow } from 'lucide-vue-next'

import type { CellSummary } from '@/api/slices/workspace/workspace.interface'
import type { BranchRecord } from '@/api/slices/workspace/workspace.interface'
import type { StreamFrame } from '@/api/streams/flow'

vi.mock('@/api/slices/workspace/workspace.api', () => ({
  workspaceApi: {
    tree: vi.fn(),
    cellsList: vi.fn(async () => ({ flow: 'churn', branch: 'main', cells: [] })),
    journalSince: vi.fn(async () => ({
      flow: 'churn',
      path: '/p/churn.flow',
      cursor: 0,
      transactions: [],
    })),
    agentHarnesses: vi.fn(async () => ({ harnesses: [] })),
  },
}))

const toasts: unknown[] = []
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: (toast: unknown) => toasts.push(toast) }),
}))
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: (toast: unknown) => toasts.push(toast) }),
}))

import NotebookCell from '@/components/notebooks/cell/NotebookCell.vue'
import NotebookPairAgent from '@/components/notebooks/NotebookPairAgent.vue'
import { AGENT_FOCUS_MS, useFlowStore } from '@/store/flow'

const FLOW = '/p/churn.flow'

const MAIN: BranchRecord = {
  branch: 'main',
  parent: null,
  cells: 2,
  checked_out: true,
  archived: false,
  last_intent: null,
  fork_step: 0,
  head_step: 4,
  position_step: 4,
  behind: 0,
} as unknown as BranchRecord

function summary(slug: string): CellSummary {
  return {
    slug,
    state: 'synced',
    primary: null,
    kinds: {},
    causes: [],
    reused: false,
    cost_seconds: 1.5,
  } as unknown as CellSummary
}

function kernel(
  event: 'started' | 'awaiting' | 'materialized' | 'failed',
  run_id: string,
  slug: string,
  awaiting?: number,
): StreamFrame {
  return { channel: 'journal', type: 'kernel', flow: FLOW, step: 4, event, run_id, slug, awaiting }
}

function activity(phase: 'started' | 'ended', tool: string, slug: string | null): StreamFrame {
  return {
    channel: 'journal',
    type: 'activity',
    flow: FLOW,
    step: 4,
    phase,
    actor: 'codex-7',
    label: 'Codex',
    tool,
    slug,
  }
}

let store: ReturnType<typeof useFlowStore>
const mounted: VueWrapper[] = []

function card(slug: string, state: CellSummary['state'] = 'synced'): VueWrapper {
  const wrapper = mount(NotebookCell, {
    props: {
      title: slug,
      icon: Workflow,
      costSeconds: 1.5,
      state,
      causes: [],
      reused: false,
      cell: summary(slug),
    },
    global: {
      plugins: [ToastService, ConfirmationService],
      stubs: { NotebookCode: true, NotebookLogs: true },
    },
  })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  const pinia = createPinia()
  setActivePinia(pinia)
  store = useFlowStore()
  store.branches = [MAIN]
  store.agentSessions = [{ actor: 'codex-7', label: 'Codex', begun_step: 2, leased: true }]
})

afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount()
})

describe('live cell states in the store', () => {
  it('follows a run from queued, through running, to its end', () => {
    store.receiveLiveFrame(kernel('awaiting', 'run-1', 'train', 1))
    expect(store.cellLiveStates.train).toEqual({ kind: 'queued', run_id: 'run-1' })

    store.receiveLiveFrame(kernel('started', 'run-1', 'train'))
    expect(store.cellLiveStates.train).toEqual({ kind: 'running', run_id: 'run-1' })
    expect(store.isAnythingRunning).toBe(true)

    store.receiveLiveFrame(kernel('materialized', 'run-1', 'train'))
    expect(store.cellLiveStates.train).toBeUndefined()
    expect(store.isAnythingRunning).toBe(false)
  })

  it('lets go of a queued run everybody stopped waiting on', () => {
    store.receiveLiveFrame(kernel('awaiting', 'run-2', 'score', 1))
    store.receiveLiveFrame(kernel('awaiting', 'run-2', 'score', 0))
    expect(store.cellLiveStates.score).toBeUndefined()
  })

  it('takes the runs in flight from the catch-up, and drops them when the kernel stops', () => {
    store.receiveLiveFrame({
      channel: 'journal',
      type: 'caught_up',
      flow: FLOW,
      step: 4,
      running: [{ run_id: 'run-3', slug: 'load' }],
      activity: [{ actor: 'codex-7', label: 'Codex', tool: 'cells.edit', slug: 'train' }],
    })
    expect(store.cellLiveStates.load).toEqual({ kind: 'running', run_id: 'run-3' })
    expect(store.cellLiveStates.train?.kind).toBe('agent')

    store.receiveLiveFrame({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      step: 4,
      event: 'kernel_state',
      kernel: 'stopped',
    })
    expect(store.cellLiveStates.load).toBeUndefined()
    expect(store.cellLiveStates.train?.kind).toBe('agent')
  })

  it('keeps the cell an agent call named after the call, until the agent moves on', () => {
    store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
    expect(store.cellLiveStates.train).toEqual({
      kind: 'agent',
      actor: 'codex-7',
      label: 'Codex',
      tool: 'cells.edit',
      inCall: true,
    })

    // The call lasted milliseconds; the agent is still on the cell.
    store.receiveLiveFrame(activity('ended', 'cells.edit', 'train'))
    expect(store.cellLiveStates.train?.kind).toBe('agent')
    expect(store.cellLiveStates.train).toMatchObject({ inCall: false })
    // Looking around names no cell and moves nothing.
    store.receiveLiveFrame(activity('started', 'context', null))
    store.receiveLiveFrame(activity('ended', 'context', null))
    expect(store.cellLiveStates.train?.kind).toBe('agent')

    // Naming another cell does.
    store.receiveLiveFrame(activity('started', 'cells.show', 'score'))
    store.receiveLiveFrame(activity('ended', 'cells.show', 'score'))
    expect(store.cellLiveStates.train).toBeUndefined()
    expect(store.cellLiveStates.score?.kind).toBe('agent')
  })

  it('lets go of the cell when the agent goes quiet, or its lease drops', () => {
    vi.useFakeTimers()
    try {
      store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
      store.receiveLiveFrame(activity('ended', 'cells.edit', 'train'))
      vi.advanceTimersByTime(AGENT_FOCUS_MS - 10_000)
      expect(store.cellLiveStates.train?.kind).toBe('agent')
      vi.advanceTimersByTime(15_000)
      expect(store.cellLiveStates.train).toBeUndefined()
      expect(store.currentActivity).toBeNull()

      store.receiveLiveFrame(activity('started', 'cells.edit', 'score'))
      store.receiveLiveFrame(activity('ended', 'cells.edit', 'score'))
      expect(store.cellLiveStates.score?.kind).toBe('agent')
      store.receiveLiveFrame({
        channel: 'journal',
        type: 'agents',
        flow: FLOW,
        step: 5,
        sessions: [{ actor: 'codex-7', label: 'Codex', begun_step: 2, leased: false }],
      })
      expect(store.cellLiveStates.score).toBeUndefined()
    } finally {
      vi.useRealTimers()
    }
  })

  it('lets a run the agent asked for win over the call that asked', () => {
    store.receiveLiveFrame(activity('started', 'run', 'train'))
    store.receiveLiveFrame(kernel('started', 'run-4', 'train'))
    expect(store.cellLiveStates.train?.kind).toBe('running')
    // A call that names no cell marks nothing on a card; the tag still says.
    store.receiveLiveFrame(activity('started', 'context', null))
    expect(Object.keys(store.cellLiveStates)).toEqual(['train'])
    expect(store.currentActivity?.tool).toBe('context')
  })
})

describe('the card', () => {
  it('shows nothing live by default', () => {
    const wrapper = card('train')
    expect(wrapper.attributes('data-live')).toBeUndefined()
    expect(wrapper.find('.live-strip').exists()).toBe(false)
  })

  it('says it is running, then returns to rest', async () => {
    const wrapper = card('train', 'unsynced')
    store.receiveLiveFrame(kernel('started', 'run-1', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.attributes('data-live')).toBe('running')
    expect(wrapper.find('.live-strip').text()).toContain('Running')
    expect(wrapper.find('footer button').attributes('disabled')).toBeDefined()

    store.receiveLiveFrame(kernel('failed', 'run-1', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.attributes('data-live')).toBeUndefined()
  })

  it('dims under the agent and names what it is doing', async () => {
    const wrapper = card('train')
    const other = card('score')
    store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.attributes('data-live')).toBe('agent')
    expect(wrapper.find('.live-strip').text()).toBe('Codex is editing this cell…')
    expect(other.attributes('data-live')).toBeUndefined()
  })
})

describe('the pairing tag', () => {
  it('names the call the agent is inside of', async () => {
    const wrapper = mount(NotebookPairAgent, {
      global: { plugins: [ToastService] },
    })
    mounted.push(wrapper)
    expect(wrapper.text()).toContain('Codex paired')
    store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Codex · editing train')
    store.receiveLiveFrame(activity('ended', 'cells.edit', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Codex · working on train')
  })
})
