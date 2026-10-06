
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
    tree: vi.fn(async () => ({
      flow: 'churn',
      branches: [{ branch: 'main', branch_id: 'b-main', checked_out: true, head_step: 2 }],
      agent_sessions: [{ actor: 'codex-7', label: 'Codex', begun_step: 2, leased: true }],
    })),
    rewindBranch: vi.fn(async () => ({})),
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
import { AGENT_ACTIVE_MS, AGENT_COLORS, useFlowStore } from '@/store/flow'
import { settle } from './fakes'

const FLOW = '/p/churn.flow'

const MAIN: BranchRecord = {
  branch: 'main',
  branch_id: 'b-main',
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

function activity(
  phase: 'started' | 'ended',
  tool: string,
  slug: string | null,
  actor = 'codex-7',
  label = 'Codex',
): StreamFrame {
  return {
    channel: 'journal',
    type: 'activity',
    flow: FLOW,
    step: 4,
    phase,
    actor,
    label,
    tool,
    slug,
  }
}

function held(slug: string, actor = 'codex-7', label = 'Codex', branch_id = 'b-main') {
  const now = Date.now()
  return { actor, label, slug, branch: 'main', branch_id, since: now, last: now }
}

function claims(...entries: ReturnType<typeof held>[]): StreamFrame {
  return {
    channel: 'journal',
    type: 'claims',
    flow: FLOW,
    step: 4,
    claims: entries,
    idle_after_s: 180,
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

  it('takes runs and holds from the catch-up, and drops the runs when the kernel stops', () => {
    store.receiveLiveFrame({
      channel: 'journal',
      type: 'caught_up',
      flow: FLOW,
      step: 4,
      running: [{ run_id: 'run-3', slug: 'load' }],
      activity: [{ actor: 'codex-7', label: 'Codex', tool: 'cells.edit', slug: 'train' }],
      claims: [held('train')],
      claim_idle_s: 180,
    })
    expect(store.cellLiveStates.load).toEqual({ kind: 'running', run_id: 'run-3' })
    expect(store.cellLiveStates.train).toMatchObject({ kind: 'agent', inCall: true })

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

  it('shows the cell the daemon says an agent holds, and what it is doing on it', () => {
    store.receiveLiveFrame(claims(held('train')))
    expect(store.cellLiveStates.train).toEqual({
      kind: 'agent',
      actor: 'codex-7',
      label: 'Codex',
      tool: null,
      inCall: false,
      active: true,
      color: AGENT_COLORS[0],
    })

    store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
    expect(store.cellLiveStates.train).toMatchObject({ tool: 'cells.edit', inCall: true })
    store.receiveLiveFrame(activity('ended', 'cells.edit', 'train'))
    expect(store.cellLiveStates.train).toMatchObject({ tool: null, inCall: false })

    store.receiveLiveFrame(activity('started', 'cells.show', 'score'))
    expect(store.cellLiveStates.train).toMatchObject({ inCall: false })
    expect(store.cellLiveStates.score).toBeUndefined()

    store.receiveLiveFrame(claims())
    expect(store.cellLiveStates.train).toBeUndefined()
  })

  it('gives each connected agent its own colour, oldest first', () => {
    store.agentSessions = [
      { actor: 'claude-3', label: 'claude-code', begun_step: 5, leased: true },
      { actor: 'codex-7', label: 'Codex', begun_step: 2, leased: true },
    ]
    store.receiveLiveFrame(claims(held('train'), held('score', 'claude-3', 'claude-code')))
    expect(store.cellLiveStates.train).toMatchObject({ color: AGENT_COLORS[0] })
    expect(store.cellLiveStates.score).toMatchObject({ color: AGENT_COLORS[1] })
    expect(store.pairedAgents.map((agent) => [agent.label, agent.slug])).toEqual([
      ['Codex', 'train'],
      ['claude-code', 'score'],
    ])
  })

  it('lets a hold lapse on time, and drops it when the lease does', () => {
    vi.useFakeTimers()
    try {
      store.receiveLiveFrame(claims(held('train')))
      vi.advanceTimersByTime(170_000)
      expect(store.cellLiveStates.train?.kind).toBe('agent')
      vi.advanceTimersByTime(15_000)
      expect(store.cellLiveStates.train).toBeUndefined()

      store.receiveLiveFrame(claims(held('score')))
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

  it('shows only the holds on the lane on screen', () => {
    store.receiveLiveFrame(claims(held('train', 'codex-7', 'Codex', 'b-other')))
    expect(store.cellLiveStates.train).toBeUndefined()
  })

  it('lets a run the agent asked for win over its hold', () => {
    store.receiveLiveFrame(claims(held('train')))
    store.receiveLiveFrame(activity('started', 'run', 'train'))
    store.receiveLiveFrame(kernel('started', 'run-4', 'train'))
    expect(store.cellLiveStates.train?.kind).toBe('running')
  })
})

describe('when the lane is moved under the agent', () => {
  function rewound(branchId: string): StreamFrame {
    return {
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 9,
      transaction: {
        step: 9,
        ts: '2026-10-05T10:00:00Z',
        actor: 'user',
        intent: 'moved main to step 2',
        offline: false,
        settled: false,
        branch: branchId,
        ops: [{ op: 'rewound', branch_id: branchId, to_step: 2 }],
      },
    }
  }

  it('lets go of the cell the agent held when somebody rewinds this lane', () => {
    store.receiveLiveFrame(claims(held('train')))
    store.receiveLiveFrame(rewound('b-main'))
    expect(store.cellLiveStates.train).toBeUndefined()
  })

  it('leaves the hold alone when another lane is rewound', () => {
    store.receiveLiveFrame(claims(held('train')))
    store.receiveLiveFrame(rewound('b-other'))
    expect(store.cellLiveStates.train?.kind).toBe('agent')
  })

  it('lets go of it when this tab rewinds the lane itself', async () => {
    store.receiveLiveFrame(claims(held('train')))
    await store.rewindBranch(2)
    expect(store.cellLiveStates.train).toBeUndefined()
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

  it('takes the colour of the agent holding it and says what it is doing', async () => {
    const wrapper = card('train')
    const other = card('score')
    store.receiveLiveFrame(claims(held('train')))
    store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.attributes('data-live')).toBe('agent')
    expect(wrapper.attributes('style')).toContain(`--agent-color: ${AGENT_COLORS[0]}`)
    expect(wrapper.find('.live-strip').text()).toBe('Codex is editing this cell…')
    expect(wrapper.find('.live-strip').attributes('title')).toContain(
      "Other agents can't change or run this cell until Codex",
    )
    expect(other.attributes('data-live')).toBeUndefined()

    store.receiveLiveFrame(activity('ended', 'cells.edit', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.live-strip').text()).toBe('Codex is working on this cell')
  })
})

describe('a card an agent holds but has stopped working on', () => {
  it('reads as worked on just after a call, then only as held', () => {
    vi.useFakeTimers()
    try {
      store.receiveLiveFrame(claims(held('train')))
      expect(store.cellLiveStates.train).toMatchObject({ kind: 'agent', active: true })
      vi.advanceTimersByTime(AGENT_ACTIVE_MS + 5_000)
      expect(store.cellLiveStates.train).toMatchObject({ kind: 'agent', active: false })
      store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
      expect(store.cellLiveStates.train).toMatchObject({ active: true, inCall: true })
    } finally {
      vi.useRealTimers()
    }
  })

  it('shows a held card quietly, undimmed, and never closes it to the person', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = card('train')
      store.receiveLiveFrame(claims(held('train')))
      await wrapper.vm.$nextTick()
      expect(wrapper.classes()).toContain('card--agent')

      vi.advanceTimersByTime(AGENT_ACTIVE_MS + 5_000)
      await wrapper.vm.$nextTick()
      expect(wrapper.classes()).toContain('card--held')
      expect(wrapper.classes()).not.toContain('card--agent')
      expect(wrapper.find('.live-strip').exists()).toBe(false)
      expect(wrapper.find('.held-note').text()).toBe('Held by Codex')
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('the pairing line', () => {
  function line(): VueWrapper {
    const wrapper = mount(NotebookPairAgent, {
      attachTo: document.body,
      global: { plugins: [ToastService] },
    })
    mounted.push(wrapper)
    return wrapper
  }

  it('reads one agent in full, with the cell it is on', async () => {
    const wrapper = line()
    expect(wrapper.find('.agents-trigger').text()).toBe('Codex paired')

    store.receiveLiveFrame(claims(held('train')))
    store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.agents-trigger').text()).toBe('Codex · editing train')
  })

  it('folds several agents into one count, however many there are', async () => {
    store.agentSessions = [
      { actor: 'codex-7', label: 'Codex', begun_step: 2, leased: true },
      { actor: 'claude-3', label: 'claude-code', begun_step: 5, leased: true },
      { actor: 'codex-9', label: 'Codex 2', begun_step: 6, leased: true },
    ]
    const wrapper = line()
    expect(wrapper.findAll('.agents-trigger')).toHaveLength(1)
    expect(wrapper.find('.agents-trigger').text()).toBe('3 agents')
    expect(wrapper.findAll('.agents-trigger .agent-dot')).toHaveLength(3)

    store.agentSessions = Array.from({ length: 10 }, (_, at) => ({
      actor: `codex-${at}`,
      label: at ? `codex ${at + 1}` : 'codex',
      begun_step: at,
      leased: true,
    }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.agents-trigger').text()).toBe('10 agents')
    expect(wrapper.findAll('.agents-trigger .agent-dot')).toHaveLength(4)
    expect(document.body.querySelectorAll('.agents-row')).toHaveLength(0)
  })

  it('lists every agent and the cell it holds on click, and goes to that cell', async () => {
    store.agentSessions = [
      { actor: 'codex-7', label: 'Codex', begun_step: 2, leased: true },
      { actor: 'claude-3', label: 'claude-code', begun_step: 5, leased: true },
    ]
    store.receiveLiveFrame(claims(held('train')))
    store.receiveLiveFrame(activity('started', 'cells.edit', 'train'))
    const wrapper = line()

    await wrapper.find('.agents-trigger').trigger('click')
    await settle()
    const rows = [...document.body.querySelectorAll<HTMLElement>('.agents-row')]
    expect(rows.map((row) => row.dataset.agent)).toEqual(['codex-7', 'claude-3'])
    expect(rows[0]?.textContent).toContain('editing')
    expect(rows[0]?.textContent).toContain('train')
    expect(rows[1]?.textContent).toContain('idle')

    rows[0]?.querySelector<HTMLButtonElement>('.agents-row-cell')?.click()
    expect(store.selectedCellId).toBe('train')
  })

  it('says unpaired when nobody is connected', () => {
    store.agentSessions = []
    const wrapper = line()
    expect(wrapper.text()).toContain('Unpaired')
    expect(wrapper.find('.agents-trigger').exists()).toBe(false)
  })
})
