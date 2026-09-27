/**
 * Moving between branches, and within one.
 *
 * Three rules carry this suite. **Viewing and checking out are different
 * verbs**: the switcher re-scopes the screen with a store read and the URL
 * follows, while rebinding the files is a separate ask behind a sentence that
 * names what it moves — a dropdown that moved files as a side effect of
 * browsing would make looking dangerous. **A branch is created from the branch
 * you are on**, at its head, and the screen lands on the new one, because
 * minting a branch and then leaving the user looking at its parent is a state
 * with nothing to say which is which. And **a checkpoint is a marker, not a
 * snapshot and not a step**: the store already keeps every version the step
 * resolved to, so the only thing the gesture carries is the user's own
 * sentence — and the sentence goes on the current step, the way a commit
 * message rides on its commit, rather than adding a row to the timeline.
 */

import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ToastService from 'primevue/toastservice'

import { FlowApiError } from '@/flow/api/client'
import type { BranchRecord, CellSummary } from '@/flow/api/types'
import LiveWorkbench from '@/flow/workbench/pages/LiveWorkbench.vue'
import { attach, cellSummary, flowStatus, FLOW, settle, transaction } from './fakes'
import type { Attached, Handlers } from './fakes'

const MAIN: CellSummary[] = [
  cellSummary('features', { outputs: ['train_split'], primary: 'train_split', created_step: 4 }),
]

const SWEEP: CellSummary[] = [
  cellSummary('features', { outputs: ['train_split'], primary: 'train_split', created_step: 4 }),
]

function branchRecord(overrides: Partial<BranchRecord> & { branch: string }): BranchRecord {
  return {
    branch_id: `branch-${overrides.branch}`,
    parent: null,
    forked_at_step: 0,
    parent_step: null,
    archived: false,
    checked_out: false,
    cells: 1,
    states: { synced: 1 },
    checkpoint: null,
    head_step: overrides.last_intent?.step ?? 14,
    newest_step: overrides.last_intent?.step ?? 14,
    last_intent: {
      step: 14,
      ts: '2026-08-13T09:14:00Z',
      actor: 'user',
      intent: 'edited features',
      offline: false,
      settled: false,
    },
    agent: null,
    ...overrides,
  }
}

const BRANCHES: BranchRecord[] = [
  branchRecord({ branch: 'main', checked_out: true }),
  branchRecord({
    branch: 'exp/lr-sweep',
    parent: 'main',
    forked_at_step: 6,
    parent_step: 5,
    last_intent: {
      step: 10,
      ts: '2026-08-13T09:10:00Z',
      actor: 'user',
      intent: 'swept the learning rate',
      offline: false,
      settled: true,
    },
  }),
]

const SLICES: Record<string, CellSummary[]> = { main: MAIN, 'exp/lr-sweep': SWEEP }

const Empty = defineComponent({ template: '<div />' })

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/flow/:flowId', component: Empty },
      { path: '/flow/:flowId/notebook', component: Empty },
      { path: '/flow/:flowId/compare', component: Empty },
      { path: '/:pathMatch(.*)*', component: Empty },
    ],
  })
}

interface Bench {
  wrapper: VueWrapper
  live: Attached
}

async function workbench(options: { handlers?: Handlers; branches?: BranchRecord[] } = {}) {
  const tree = options.branches ?? BRANCHES
  const live = await attach({
    status: flowStatus({ cells: MAIN }),
    handlers: {
      tree: () => ({ flow: 'churn', branch: 'main', branches: tree }),
      'env.status': () => ({
        workspace: '/tmp/project',
        python: { path: '/tmp/project/.venv/bin/python', source: 'venv' },
        packages: [],
        flows: [],
      }),
      'cells.list': (params) => ({
        flow: 'churn',
        branch: String(params.branch),
        cells: SLICES[String(params.branch)] ?? [],
      }),
      'cells.logs': () => ({ flow: 'churn', branch: 'main', slug: '', state: null, logs: null }),
      switch: (params) => ({
        ...flowStatus({ branch: String(params.branch) }),
        projected: null,
      }),
      rewind: (params) => ({
        ...flowStatus(),
        rewound_branch: String(params.branch),
        to_step: Number(params.to_step),
        cells: MAIN.length,
        projected: null,
      }),
      ...options.handlers,
    },
  })
  const router = testRouter()
  await router.push(`/flow/${FLOW}`)
  await router.isReady()
  const wrapper = mount(LiveWorkbench, {
    props: { session: live.session, stream: live.stream },
    global: { plugins: [router, ToastService] },
  })
  await settle()
  return { wrapper, live } satisfies Bench
}

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

/** The overlays — the switcher's panel, the timeline, the dialog — are teleported. */
function overlay(): string {
  return document.body.textContent ?? ''
}

async function clickOverlayButton(label: string): Promise<void> {
  const found = [...document.body.querySelectorAll('button')].find(
    (node) => (node.textContent ?? '').includes(label) || node.getAttribute('aria-label') === label,
  )
  expect(found, `no overlay button reading "${label}"`).toBeTruthy()
  found?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await settle()
}

/** The switcher is a `Select`: one combobox, opened the way a reader opens it. */
async function openSwitcher(wrapper: VueWrapper): Promise<void> {
  const trigger = wrapper.find('[data-pc-name="select"]')
  expect(trigger.exists(), 'no branch switcher in the bar').toBe(true)
  await trigger.trigger('click')
  await settle()
}

/** `Select` commits an option on mousedown, which is what a pointer sends first. */
async function pickBranch(name: string): Promise<void> {
  const option = [...document.body.querySelectorAll('[role="option"]')].find(
    (node) => node.getAttribute('aria-label') === name,
  )
  expect(option, `no option for ${name}`).toBeTruthy()
  option?.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
  await settle()
}

/** The timeline hangs off the step count in the branch identity block. */
async function openTimeline(wrapper: VueWrapper, branch = 'main'): Promise<void> {
  const steps = wrapper.find(`button[aria-label="Steps on ${branch}"]`)
  expect(steps.exists(), 'no step count to open the timeline from').toBe(true)
  await steps.trigger('click')
  await settle()
}

async function typeInto(label: string, value: string): Promise<void> {
  const field = document.body.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`)
  expect(field, `no field labelled "${label}"`).toBeTruthy()
  field!.value = value
  field!.dispatchEvent(new Event('input', { bubbles: true }))
  await settle()
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('the branch switcher is a shortcut, not a checkout', () => {
  it('lists every branch with where it stands, and marks the one on disk', async () => {
    const { wrapper } = await workbench()

    await openSwitcher(wrapper)

    expect(overlay()).toContain('main')
    expect(overlay()).toContain('exp/lr-sweep')
    // Steps, so a branch is picked by where it stands rather than by name alone.
    expect(overlay()).toContain('14 steps')
    expect(overlay()).toContain('on disk')
    wrapper.unmount()
  })

  it('says what it opens, and opens it from the keyboard', async () => {
    const { wrapper } = await workbench()

    const combobox = wrapper.find('[role="combobox"]')
    expect(combobox.attributes('aria-label')).toBe('viewed lane')
    expect(combobox.attributes('aria-haspopup')).toBe('listbox')
    expect(combobox.attributes('aria-expanded')).toBe('false')
    expect(combobox.attributes('aria-controls')).toBeTruthy()

    await combobox.trigger('keydown', { code: 'ArrowDown' })
    await settle()

    expect(wrapper.find('[role="combobox"]').attributes('aria-expanded')).toBe('true')
    expect(document.body.querySelectorAll('[role="option"]').length).toBe(2)
    wrapper.unmount()
  })

  it('re-scopes the screen as a pure store read, rebinding nothing', async () => {
    const { wrapper, live } = await workbench()

    await openSwitcher(wrapper)
    await pickBranch('exp/lr-sweep')

    expect(window.location.search).toContain('branch=exp%2Flr-sweep')
    expect(asked(live, 'cells.list').map((params) => params.branch)).toContain('exp/lr-sweep')
    // Browsing never moves files. This is the whole reason the switcher exists.
    expect(asked(live, 'switch')).toEqual([])
    wrapper.unmount()
  })

  it('keeps checking out one gesture deeper, behind the sentence that names it', async () => {
    const { wrapper, live } = await workbench()

    await openSwitcher(wrapper)
    await pickBranch('exp/lr-sweep')
    await openSwitcher(wrapper)
    await clickOverlayButton('use exp/lr-sweep here')

    // The confirm states what moves; nothing has been asked of the daemon yet.
    expect(overlay()).toContain('rewrites the files')
    expect(asked(live, 'switch')).toEqual([])

    await clickOverlayButton('use here')

    expect(asked(live, 'switch').map((params) => params.branch)).toEqual(['exp/lr-sweep'])
    wrapper.unmount()
  })

  it('keeps lane checkout available while an agent is paired', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 18,
      transaction: transaction(18, {
        intent: 'session start',
        ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1' }],
      }),
    })
    await settle()

    await openSwitcher(wrapper)
    await pickBranch('exp/lr-sweep')
    await openSwitcher(wrapper)
    expect(overlay()).not.toContain('use here anyway')
    await clickOverlayButton('use exp/lr-sweep here')
    await clickOverlayButton('use here')

    expect(asked(live, 'switch')).toEqual([expect.objectContaining({ branch: 'exp/lr-sweep' })])
    expect(asked(live, 'switch')[0]).not.toHaveProperty('force')
    wrapper.unmount()
  })
})

describe('a branch is created from the one being viewed', () => {
  it('forks at the head from the switcher and lands on the new branch', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        fork: (params) => ({
          branch: String(params.name),
          from_branch: String(params.from_branch),
          forked_at_step: 15,
          cells: 1,
        }),
      },
    })

    await openSwitcher(wrapper)
    await clickOverlayButton('new lane')
    await typeInto('lane name', 'exp/deeper')
    await clickOverlayButton('create lane')

    expect(asked(live, 'fork')).toEqual([
      expect.objectContaining({ name: 'exp/deeper', from_branch: 'main', branch: 'main' }),
    ])
    // The screen follows the branch it just made.
    expect(window.location.search).toContain('branch=exp%2Fdeeper')
    wrapper.unmount()
  })

  it('offers the same gesture from the branch identity block', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        fork: (params) => ({
          branch: String(params.name),
          from_branch: 'main',
          forked_at_step: 15,
          cells: 1,
        }),
      },
    })

    await wrapper
      .findAll('button')
      .find((node) => node.text().includes('new lane'))
      ?.trigger('click')
    await settle()
    await typeInto('lane name', 'exp/from-panel')
    await clickOverlayButton('create lane')

    expect(asked(live, 'fork').map((params) => params.name)).toEqual(['exp/from-panel'])
    wrapper.unmount()
  })

  it('names a refused branch in the field the user is standing in', async () => {
    const { wrapper } = await workbench({
      handlers: {
        fork: () => {
          throw new FlowApiError('a branch named exp/lr-sweep already exists', {
            kind: 'BranchAlreadyExists',
            status: 400,
          })
        },
      },
    })

    await openSwitcher(wrapper)
    await clickOverlayButton('new lane')
    await typeInto('lane name', 'exp/lr-sweep')
    await clickOverlayButton('create lane')

    expect(overlay()).toContain('already exists')
    // The dialog stays open over the name that has to change.
    expect(document.body.querySelector('input[aria-label="lane name"]')).toBeTruthy()
    wrapper.unmount()
  })
})

describe('the step timeline is where a branch moves through its own history', () => {
  const HISTORY = [
    transaction(12, { branch: 'branch-main', actor: 'user', intent: 'added features' }),
    transaction(13, { branch: 'branch-main', actor: 'claude-1', intent: 'ran features' }),
    transaction(14, { branch: 'branch-main', actor: 'user', intent: 'edited features' }),
  ]

  async function withHistory(handlers: Handlers = {}) {
    const bench = await workbench({ handlers })
    for (const entry of HISTORY) {
      bench.live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step: entry.step,
        transaction: entry,
      })
    }
    await settle()
    return bench
  }

  it('opens from the step count and says which step the branch is on', async () => {
    const { wrapper } = await withHistory()

    const steps = wrapper.find('button[aria-label="Steps on main"]')
    expect(steps.attributes('aria-haspopup')).toBe('dialog')
    expect(steps.attributes('aria-expanded')).toBe('false')

    await openTimeline(wrapper)

    expect(wrapper.find('button[aria-label="Steps on main"]').attributes('aria-expanded')).toBe(
      'true',
    )
    expect(overlay()).toContain('step 12')
    expect(overlay()).toContain('added features')
    // Its head is where it stands; the rest are places it can go.
    expect(overlay()).toContain('current')
    wrapper.unmount()
  })

  it('confirms what a rewind moves before asking the daemon for one', async () => {
    const { wrapper, live } = await withHistory({
      rewind: () => ({
        flow: 'churn',
        path: FLOW,
        branch: 'main',
        checked_out: true,
        agent: 'claude-1',
        kernel: { state: 'stopped', restart_required: true, behind: ['pandas'] },
        settings: { reactivity: 'lazy', eager_cost_threshold_s: 30 },
        rewound_branch: 'main',
        to_step: 12,
        cells: 1,
        projected: { written: ['features'], removed: [] },
      }),
    })

    await openTimeline(wrapper)
    await clickOverlayButton('step 12 · added features')

    expect(overlay()).toContain('stands at step 12 with the cells')
    expect(overlay()).toContain('the files are rewritten to match')
    expect(asked(live, 'rewind')).toEqual([])

    await clickOverlayButton('rewind to step 12')

    expect(asked(live, 'rewind')).toEqual([
      expect.objectContaining({ branch: 'main', to_step: 12 }),
    ])
    expect(live.session.brief.value).toMatchObject({
      branch: 'main',
      agent: 'claude-1',
      kernel: { state: 'stopped', restart_required: true, behind: ['pandas'] },
      settings: { reactivity: 'lazy', eager_cost_threshold_s: 30 },
      cells: MAIN,
    })
    wrapper.unmount()
  })

  it('never offers to rewind to the step the branch is already on', async () => {
    const { wrapper, live } = await withHistory()

    await openTimeline(wrapper)
    await clickOverlayButton('step 14 · edited features')

    expect(overlay()).not.toContain('rewind to step 14')
    expect(asked(live, 'rewind')).toEqual([])
    wrapper.unmount()
  })
})

describe('a lane fork is visible from both sides', () => {
  const TREE = [
    branchRecord({ branch: 'main', checked_out: true }),
    branchRecord({
      branch: 'exp/lr-sweep',
      parent: 'main',
      forked_at_step: 13,
      parent_step: 12,
      last_intent: {
        step: 13,
        ts: '2026-08-13T09:13:00Z',
        actor: 'user',
        intent: 'started the learning-rate sweep',
        offline: false,
        settled: false,
      },
    }),
    branchRecord({
      branch: 'exp/b',
      parent: 'main',
      forked_at_step: 15,
      parent_step: 12,
      last_intent: {
        step: 15,
        ts: '2026-08-13T09:15:00Z',
        actor: 'user',
        intent: 'started another experiment',
        offline: false,
        settled: false,
      },
    }),
    branchRecord({
      branch: 'exp/head',
      parent: 'main',
      forked_at_step: 16,
      parent_step: 14,
      last_intent: {
        step: 16,
        ts: '2026-08-13T09:16:00Z',
        actor: 'user',
        intent: 'started from the head',
        offline: false,
        settled: false,
      },
    }),
    branchRecord({
      branch: 'exp/lr-sweep-2',
      parent: 'exp/lr-sweep',
      forked_at_step: 17,
      parent_step: 13,
      last_intent: {
        step: 17,
        ts: '2026-08-13T09:17:00Z',
        actor: 'user',
        intent: 'continued the sweep',
        offline: false,
        settled: false,
      },
    }),
  ]

  const HISTORY = [
    transaction(12, { branch: 'branch-main', actor: 'user', intent: 'added features' }),
    transaction(13, {
      branch: 'branch-exp/lr-sweep',
      actor: 'user',
      intent: 'started the learning-rate sweep',
      ops: [
        {
          op: 'branch_created',
          branch_id: 'branch-exp/lr-sweep',
          name: 'exp/lr-sweep',
          parent_branch_id: 'branch-main',
          fork_step: 13,
        },
      ],
    }),
    transaction(14, { branch: 'branch-main', actor: 'user', intent: 'edited features' }),
  ]

  async function withForkHistory(): Promise<Bench> {
    const bench = await workbench({ branches: TREE })
    for (const entry of HISTORY) {
      bench.live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step: entry.step,
        transaction: entry,
      })
    }
    await settle()
    return bench
  }

  function stepRow(step: number): Element | undefined {
    return [...document.body.querySelectorAll('[data-testid="step-row"]')].find((row) =>
      row.getAttribute('aria-label')?.startsWith(`step ${step} ·`),
    )
  }

  it("quotes the parent's own step in the child's header", async () => {
    const { wrapper } = await withForkHistory()

    await openSwitcher(wrapper)
    await pickBranch('exp/lr-sweep')

    expect(wrapper.text()).toContain('started from main · step 12 · 1 step ago')
    wrapper.unmount()
  })

  it('marks every direct child that started from the same parent row', async () => {
    const { wrapper } = await withForkHistory()

    await openTimeline(wrapper)

    expect(stepRow(12)?.querySelector('[data-testid="started-here"]')?.textContent).toContain(
      'exp/lr-sweep, exp/b started here',
    )
    expect(
      [...document.body.querySelectorAll('[data-testid="started-here"]')].filter((marker) =>
        marker.textContent?.includes('exp/lr-sweep'),
      ),
    ).toHaveLength(1)
    expect(stepRow(13)).toBeUndefined()
    wrapper.unmount()
  })

  it("shows a grandchild only on its direct parent's timeline", async () => {
    const { wrapper } = await withForkHistory()

    await openTimeline(wrapper)
    expect(overlay()).not.toContain('exp/lr-sweep-2 started here')
    await wrapper.find('button[aria-label="Steps on main"]').trigger('click')
    await settle()

    await openSwitcher(wrapper)
    await pickBranch('exp/lr-sweep')
    await openTimeline(wrapper, 'exp/lr-sweep')

    expect(stepRow(13)?.querySelector('[data-testid="started-here"]')?.textContent).toContain(
      'exp/lr-sweep-2 started here',
    )
    wrapper.unmount()
  })

  it('rewinds a marked row exactly like any other row', async () => {
    const { wrapper, live } = await withForkHistory()

    await openTimeline(wrapper)
    await clickOverlayButton('step 12 · added features')
    expect(overlay()).toContain('stands at step 12 with the cells')
    await clickOverlayButton('rewind to step 12')

    expect(asked(live, 'rewind')).toEqual([
      expect.objectContaining({ branch: 'main', to_step: 12 }),
    ])
    wrapper.unmount()
  })

  it('marks the current row without offering a no-op rewind', async () => {
    const { wrapper, live } = await withForkHistory()

    await openTimeline(wrapper)
    expect(stepRow(14)?.textContent).toContain('current')
    expect(stepRow(14)?.querySelector('[data-testid="started-here"]')?.textContent).toContain(
      'exp/head started here',
    )
    await clickOverlayButton('step 14 · edited features')

    expect(overlay()).not.toContain('rewind to step 14')
    expect(asked(live, 'rewind')).toEqual([])
    wrapper.unmount()
  })
})

describe('a checkpoint is words on the current step, not a step of its own', () => {
  /** `main`'s own steps as the stream served them, before anything was marked. */
  const OWN = [
    transaction(12, { branch: 'branch-main', actor: 'user', intent: 'added features' }),
    transaction(14, { branch: 'branch-main', actor: 'user', intent: 'edited features' }),
  ]

  async function withOwnSteps(
    options: { handlers?: Handlers } = {},
  ): Promise<{ wrapper: VueWrapper; live: Attached }> {
    const bench = await workbench(options)
    for (const entry of OWN) {
      bench.live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step: entry.step,
        transaction: entry,
      })
    }
    await settle()
    return bench
  }

  function stepRow(step: number): Element | null {
    return (
      [...document.body.querySelectorAll('[data-testid="step-row"]')].find((row) =>
        row.getAttribute('aria-label')?.startsWith(`step ${step} ·`),
      ) ?? null
    )
  }

  /** The stream's line for a mark: it names the step, and its intent is the words. */
  function markLine(step: number, onStep: number, intent: string) {
    return {
      channel: 'journal' as const,
      type: 'transaction' as const,
      flow: FLOW,
      step,
      transaction: transaction(step, {
        branch: 'branch-main',
        actor: 'user',
        intent,
        ops: [{ op: 'checkpointed' as const, branch_id: 'branch-main', step: onStep }],
      }),
    }
  }

  it('marks the current step from the lane identifier and reads the words back on that row', async () => {
    const intent = 'before I rewrite the scorer'
    const { wrapper, live } = await withOwnSteps({
      handlers: {
        checkpoint: (params) => ({
          branch: 'main',
          step: Number(params.step),
          intent: String(params.intent),
          ts: '2026-08-13T09:15:00Z',
          settled: false,
        }),
      },
    })

    const mark = wrapper.find('button[aria-label="Mark this point on main"]')
    expect(mark.exists()).toBe(true)
    await mark.trigger('click')
    await settle()
    expect(overlay()).toContain('step 14')
    expect(overlay()).toContain('adds no step')
    await typeInto('what this point is', intent)
    await clickOverlayButton('mark this point')

    // The current step is what gets the words.
    expect(asked(live, 'checkpoint')).toEqual([
      expect.objectContaining({ branch: 'main', intent, step: 14 }),
    ])

    live.socket.deliver(markLine(15, 14, intent))
    await settle()
    await openTimeline(wrapper)

    // No row for step 15: the words sit on step 14, which reads under them and
    // keeps what it did underneath.
    expect(stepRow(15)).toBeNull()
    const row = stepRow(14)
    expect(row?.getAttribute('aria-label')).toBe(`step 14 · ${intent}`)
    expect(row?.querySelector('[data-testid="step-mark"]')?.textContent).toBe(intent)
    expect(row?.textContent).toContain('edited features')
    expect(row?.querySelector('.lucide-flag')).toBeTruthy()
    wrapper.unmount()
  })

  it('marks the viewed lane without moving the files onto it', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        checkpoint: (params) => ({
          branch: String(params.branch),
          step: Number(params.step),
          intent: String(params.intent),
          ts: '2026-08-13T09:15:00Z',
          settled: false,
        }),
      },
    })

    await openSwitcher(wrapper)
    await pickBranch('exp/lr-sweep')
    const mark = wrapper.find('button[aria-label="Mark this point on exp/lr-sweep"]')
    expect(mark.exists()).toBe(true)
    await mark.trigger('click')
    await settle()
    await typeInto('what this point is', 'baseline')
    await clickOverlayButton('mark this point')

    expect(asked(live, 'checkpoint')).toEqual([
      expect.objectContaining({ branch: 'exp/lr-sweep', intent: 'baseline', step: 10 }),
    ])
    expect(asked(live, 'switch')).toEqual([])
    wrapper.unmount()
  })

  it('disables and does not submit a blank marker from the lane identifier', async () => {
    const { wrapper, live } = await workbench()

    const mark = wrapper.find('button[aria-label="Mark this point on main"]')
    expect(mark.exists()).toBe(true)
    await mark.trigger('click')
    await settle()
    await typeInto('what this point is', '   ')

    const field = document.body.querySelector<HTMLInputElement>(
      'input[aria-label="what this point is"]',
    )
    const confirm = [...(field?.parentElement?.querySelectorAll('button') ?? [])].find((button) =>
      button.textContent?.includes('mark this point'),
    )
    expect(confirm).toBeInstanceOf(HTMLButtonElement)
    expect((confirm as HTMLButtonElement).disabled).toBe(true)

    await clickOverlayButton('mark this point')

    expect(asked(live, 'checkpoint')).toEqual([])
    wrapper.unmount()
  })

  it('marks the point under the sentence typed for it', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        checkpoint: (params) => ({
          branch: 'main',
          step: Number(params.step),
          intent: String(params.intent),
          ts: '2026-08-13T09:15:00Z',
          settled: false,
        }),
      },
    })

    await openTimeline(wrapper)
    await clickOverlayButton('mark this point')
    await typeInto('what this point is', 'before I rewrite the scorer')
    await clickOverlayButton('mark this point')

    expect(asked(live, 'checkpoint')).toEqual([
      expect.objectContaining({ branch: 'main', intent: 'before I rewrite the scorer', step: 14 }),
    ])
    wrapper.unmount()
  })

  it('never journals a marker with nothing on it', async () => {
    const { wrapper, live } = await workbench()

    await openTimeline(wrapper)
    await clickOverlayButton('mark this point')
    await typeInto('what this point is', '   ')
    await clickOverlayButton('mark this point')

    expect(asked(live, 'checkpoint')).toEqual([])
    wrapper.unmount()
  })

  it('reads a mark on an older step back on that row, and the newest words win', async () => {
    const { wrapper, live } = await withOwnSteps()

    live.socket.deliver(markLine(15, 14, 'first words'))
    live.socket.deliver(markLine(16, 14, 'before I rewrite the scorer'))
    await settle()

    await openTimeline(wrapper)

    expect(stepRow(15)).toBeNull()
    expect(stepRow(16)).toBeNull()
    expect(stepRow(14)?.querySelector('[data-testid="step-mark"]')?.textContent).toBe(
      'before I rewrite the scorer',
    )
    expect(overlay()).not.toContain('first words')
    // Still the current step: the marking added nothing after it.
    expect(stepRow(14)?.textContent).toContain('current')
    wrapper.unmount()
  })

  it('rewinds to a marked step by clicking its row', async () => {
    const { wrapper, live } = await withOwnSteps()

    live.socket.deliver(markLine(15, 12, 'the one that scored'))
    await settle()

    await openTimeline(wrapper)
    await clickOverlayButton('step 12 · the one that scored')
    expect(overlay()).toContain('stands at step 12 with the cells')
    await clickOverlayButton('rewind to step 12')

    expect(asked(live, 'rewind')).toEqual([
      expect.objectContaining({ branch: 'main', to_step: 12 }),
    ])
    wrapper.unmount()
  })
})

describe('a rewound lane stands behind its newest step', () => {
  const HISTORY = [
    transaction(12, { branch: 'branch-main', actor: 'user', intent: 'added features' }),
    transaction(13, { branch: 'branch-main', actor: 'claude-1', intent: 'ran features' }),
    transaction(14, { branch: 'branch-main', actor: 'user', intent: 'edited features' }),
  ]

  /** `main` moved back to step 12; steps 13 and 14 are still its history. */
  const REWOUND: BranchRecord[] = [
    branchRecord({
      branch: 'main',
      checked_out: true,
      head_step: 12,
      newest_step: 14,
      last_intent: {
        step: 12,
        ts: '2026-08-13T09:12:00Z',
        actor: 'user',
        intent: 'added features',
        offline: false,
        settled: false,
      },
    }),
  ]

  async function behind(handlers: Handlers = {}) {
    const bench = await workbench({
      branches: REWOUND,
      handlers: {
        fork: (params) => ({
          branch: String(params.name),
          from_branch: String(params.from_branch),
          forked_at_step: 15,
          parent_step: 12,
          cells: 1,
        }),
        'cells.new': (params) => ({
          slug: 'untitled_1',
          branch: String(params.branch),
          definition_hash: 'def-new',
          written_to_files: true,
          flags: [],
        }),
        ...handlers,
      },
    })
    for (const entry of HISTORY) {
      bench.live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step: entry.step,
        transaction: entry,
      })
    }
    await settle()
    return bench
  }

  function dialog(): string {
    return document.body.querySelector('[role="dialog"]')?.textContent ?? ''
  }

  it('says so in the lane identifier and reads the later steps as ahead', async () => {
    const { wrapper, live } = await behind()
    // The line that moved it is in the journal, and is not a position.
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 15,
      transaction: transaction(15, {
        branch: 'branch-main',
        actor: 'user',
        intent: 'rewound main to step 12',
        ops: [
          {
            op: 'rewound',
            branch_id: 'branch-main',
            to_step: 12,
            selections: {},
            baselines: {},
          },
        ],
      }),
    })
    await settle()

    expect(wrapper.find('[data-testid="behind"]').text()).toContain('at step 12 · 2 steps ahead')
    await openTimeline(wrapper)

    const rows = [...document.body.querySelectorAll('[data-testid="step-row"]')]
    const byStep = (step: number) =>
      rows.find((row) => row.getAttribute('aria-label')?.startsWith(`step ${step} ·`))
    expect(byStep(12)?.textContent).toContain('current')
    expect(byStep(13)?.querySelector('[data-testid="ahead"]')).toBeTruthy()
    expect(byStep(14)?.querySelector('[data-testid="ahead"]')).toBeTruthy()
    expect(byStep(12)?.querySelector('[data-testid="ahead"]')).toBeNull()
    expect(byStep(15)).toBeUndefined()
    wrapper.unmount()
  })

  it('does not read what reactivity did on its own as a step', async () => {
    const { wrapper, live } = await behind()
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 17,
      transaction: transaction(17, {
        branch: 'branch-main',
        actor: 'auto',
        intent: 'reused a cached features',
        ops: [
          {
            op: 'memo_hit',
            branch_id: 'branch-main',
            uid: 'uid-features',
            version_id: 'v2',
            memo_key: 'k',
            mat_id: 'mat-1',
          },
        ],
      }),
    })
    await settle()

    await openTimeline(wrapper)

    const labels = [...document.body.querySelectorAll('[data-testid="step-row"]')].map((row) =>
      row.getAttribute('aria-label'),
    )
    expect(labels).not.toContain('step 17 · reused a cached features')
    wrapper.unmount()
  })

  it('does not read a checkout after the rewind as a step ahead', async () => {
    const { wrapper, live } = await behind()
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 16,
      transaction: transaction(16, {
        branch: 'branch-main',
        actor: 'user',
        intent: 'put main on disk',
        ops: [
          {
            op: 'worktree_bound',
            path: '/tmp/churn.flow',
            branch_id: 'branch-main',
            actor: 'user',
          },
        ],
      }),
    })
    await settle()

    await openTimeline(wrapper)

    const labels = [...document.body.querySelectorAll('[data-testid="step-row"]')].map((row) =>
      row.getAttribute('aria-label'),
    )
    expect(labels).toEqual([
      'step 14 · edited features',
      'step 13 · ran features',
      'step 12 · added features',
    ])
    wrapper.unmount()
  })

  it('offers to go forward to a step ahead, under the same confirm', async () => {
    const { wrapper, live } = await behind()

    await openTimeline(wrapper)
    await clickOverlayButton('step 14 · edited features')
    expect(overlay()).toContain('stands at step 14 with the cells')
    expect(overlay()).not.toContain('rewind to step 14')
    await clickOverlayButton('go to step 14')

    expect(asked(live, 'rewind')).toEqual([
      expect.objectContaining({ branch: 'main', to_step: 14 }),
    ])
    wrapper.unmount()
  })

  it('asks where a change should go, and lands it on a lane started from here', async () => {
    const { wrapper, live } = await behind()

    const add = wrapper.findAll('button').find((button) => button.text() === 'add a cell')
    expect(add).toBeTruthy()
    await add?.trigger('click')
    await settle()

    // Nothing lands until the reader answers.
    expect(dialog()).toContain('main stands at step 12')
    expect(dialog()).toContain('behind its newest step 14')
    expect(asked(live, 'cells.new')).toEqual([])

    const field = document.body.querySelector<HTMLInputElement>('input[aria-label="lane name"]')
    expect(field?.value).toBe('main-at-12')
    await clickOverlayButton('new lane from here')
    await settle()

    expect(asked(live, 'fork')).toEqual([
      expect.objectContaining({ name: 'main-at-12', from_branch: 'main' }),
    ])
    expect(asked(live, 'cells.new')).toEqual([expect.objectContaining({ branch: 'main-at-12' })])
    expect(dialog()).toBe('')
    wrapper.unmount()
  })

  it('lands the change on the lane itself when told to continue', async () => {
    const { wrapper, live } = await behind()

    const add = wrapper.findAll('button').find((button) => button.text() === 'add a cell')
    await add?.trigger('click')
    await settle()
    await clickOverlayButton('continue on main')
    await settle()

    expect(asked(live, 'fork')).toEqual([])
    expect(asked(live, 'cells.new')).toEqual([expect.objectContaining({ branch: 'main' })])
    wrapper.unmount()
  })

  it('drops the change quietly when the reader steps back', async () => {
    const { wrapper, live } = await behind()

    const add = wrapper.findAll('button').find((button) => button.text() === 'add a cell')
    await add?.trigger('click')
    await settle()
    await clickOverlayButton('cancel')
    await settle()

    expect(asked(live, 'fork')).toEqual([])
    expect(asked(live, 'cells.new')).toEqual([])
    expect(dialog()).toBe('')
    expect(document.body.textContent).not.toContain('lumlflow refused this')
    wrapper.unmount()
  })

  it('asks nothing on a lane standing on its newest step', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'cells.new': (params) => ({
          slug: 'untitled_1',
          branch: String(params.branch),
          definition_hash: 'def-new',
          written_to_files: true,
          flags: [],
        }),
      },
    })

    const add = wrapper.findAll('button').find((button) => button.text() === 'add a cell')
    await add?.trigger('click')
    await settle()

    expect(dialog()).toBe('')
    expect(asked(live, 'cells.new')).toEqual([expect.objectContaining({ branch: 'main' })])
    wrapper.unmount()
  })
})
