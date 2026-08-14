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
 * snapshot**: the store already keeps every version the step resolved to, so
 * the only thing the gesture carries is the user's own sentence.
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
    archived: false,
    checked_out: false,
    cells: 1,
    states: { synced: 1 },
    checkpoint: null,
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
      set_focus: (params) => ({
        flow: 'churn',
        branch: String(params.branch ?? 'main'),
        asset: null,
        compare: [],
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
    (node) =>
      (node.textContent ?? '').includes(label) || node.getAttribute('aria-label') === label,
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

  it('offers force only while an agent holds the files', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 18,
      transaction: transaction(18, {
        intent: 'session start',
        ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1', worktree: true }],
      }),
    })
    await settle()

    await openSwitcher(wrapper)
    await pickBranch('exp/lr-sweep')
    await openSwitcher(wrapper)
    await clickOverlayButton('use here anyway')

    expect(asked(live, 'switch')).toEqual([
      expect.objectContaining({ branch: 'exp/lr-sweep', force: true }),
    ])
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

    await wrapper.findAll('button').find((node) => node.text().includes('new lane'))?.trigger(
      'click',
    )
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
    const { wrapper, live } = await withHistory()

    await openTimeline(wrapper)
    await clickOverlayButton('step 12 · added features')

    expect(overlay()).toContain('restores the cells')
    expect(overlay()).toContain('rewrites the files to match')
    expect(asked(live, 'rewind')).toEqual([])

    await clickOverlayButton('rewind to step 12')

    expect(asked(live, 'rewind')).toEqual([
      expect.objectContaining({ branch: 'main', to_step: 12 }),
    ])
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

describe('a checkpoint is a marker with the user words on it', () => {
  it('marks the point under the sentence typed for it', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        checkpoint: (params) => ({
          branch: 'main',
          step: 15,
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
      expect.objectContaining({ branch: 'main', intent: 'before I rewrite the scorer' }),
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

  it('reads a marked step back as a flagged row in the timeline', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 15,
      transaction: transaction(15, {
        branch: 'branch-main',
        actor: 'user',
        intent: 'before I rewrite the scorer',
        ops: [{ op: 'checkpointed', branch_id: 'branch-main' }],
      }),
    })
    await settle()

    await openTimeline(wrapper)

    expect(overlay()).toContain('before I rewrite the scorer')
    expect(overlay()).toContain('step 15')
    wrapper.unmount()
  })
})
