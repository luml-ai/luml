/**
 * Handing work to the agent, reading what it did, and the ops that are not runs.
 *
 * Four rules carry this suite. A handoff payload is the **daemon's**: the
 * gesture goes over the wire and what comes back is what the reader hands over,
 * because the traceback of a run nobody opened is a fact only the store has.
 * The activity feed is **read-only and cursor-anchored** — a marker, not an
 * inbox — and the upload states in it are journal lines, so a publish waiting
 * out an offline window is visible rather than a spinner. The scratch REPL is a
 * **read of any branch**, including one whose files are nowhere, and it writes
 * no version. Env ops and the flow's settings go through the daemon and render
 * its answer, never a control that looks like it took a change and dropped it.
 */

import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { Toast } from 'primevue'
import ToastService from 'primevue/toastservice'

import { FlowApiError } from '@/flow/api/client'
import type { CellSummary, Transaction } from '@/flow/api/types'
import LiveCellCard from '@/flow/workbench/components/card/LiveCellCard.vue'
import PanelSettings from '@/flow/workbench/components/panel/PanelSettings.vue'
import LiveWorkbench from '@/flow/workbench/pages/LiveWorkbench.vue'
import {
  attach,
  cellDetail,
  cellSummary,
  clickMenuItem,
  flowStatus,
  FLOW,
  openCardMenu,
  openPanel,
  settle,
  settleJournal,
  storedPreview,
  transaction,
} from './fakes'
import type { Attached, Handlers } from './fakes'

const SOURCE = 'class Features:\n    """Engineer the features."""\n'

const SLICE: CellSummary[] = [
  cellSummary('features', {
    outputs: ['train_split'],
    kinds: { train_split: 'frame' },
    primary: 'train_split',
    created_step: 4,
  }),
  cellSummary('train_model', {
    consumes: { train: 'features.train_split' },
    outputs: ['run'],
    kinds: { run: 'experiment' },
    primary: 'run',
    created_step: 6,
  }),
]

const BRANCHES = [
  {
    branch_id: 'b-main',
    branch: 'main',
    parent: null,
    forked_at_step: 0,
    archived: false,
    checked_out: true,
    agent: null,
    last_intent: { step: 8, intent: 'ran features', actor: 'user', settled: true, ts: '' },
  },
  {
    branch_id: 'b-sweep',
    branch: 'sweep',
    parent: 'main',
    forked_at_step: 8,
    archived: false,
    checked_out: false,
    agent: null,
    last_intent: { step: 9, intent: 'forked sweep', actor: 'user', settled: false, ts: '' },
  },
]

const ENV = {
  workspace: '/tmp/project',
  python: { path: '/tmp/project/.venv/bin/python', source: 'venv' },
  packages: [{ name: 'pandas', version: '2.2.0' }],
  flows: [
    {
      flow: 'churn',
      kernel: 'running' as const,
      policy: 'ask' as const,
      restart_required: false,
      behind: [],
    },
  ],
}

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

/** The payload the daemon would have built, named so a test can spot it. */
function builtPayload(params: Record<string, unknown>): Record<string, unknown> {
  const gesture = String(params.gesture)
  return {
    gesture,
    flow: 'churn',
    branch: String(params.branch ?? 'main'),
    text:
      `Daemon-built ${gesture} payload.\n\n` +
      '```lumlflow-context\n' +
      `gesture: ${gesture}\n` +
      `branch: ${params.branch ?? 'main'}\n` +
      (params.slug ? `cell: ${params.slug}\n` : '') +
      (params.branches ? `comparing: ${(params.branches as string[]).join(', ')}\n` : '') +
      'traceback: |\n  ValueError: empty frame\n' +
      '```',
  }
}

/** The prompt the daemon would have built — the workspace's facts, not ours. */
const CONNECT_TEXT =
  'You are paired with the lumlflow flow `churn` in `/tmp/project`, on branch `main`.'

function reads(overrides: Handlers = {}): Handlers {
  return {
    'agent.payload': builtPayload,
    'agent.connect': () => ({
      flow: 'churn',
      workspace: '/tmp/project',
      command: '/tmp/project/.venv/bin/lumlflow',
      text: CONNECT_TEXT,
    }),
    tree: () => ({ flow: 'churn', branch: 'main', branches: BRANCHES }),
    'env.status': () => ENV,
    'settings.set': (params) => ({
      flow: 'churn',
      settings: {
        reactivity: params.reactivity ?? 'auto',
        eager_cost_threshold_s: params.eager_cost_threshold_s ?? 5,
        env_policy: params.env_policy ?? 'ask',
      },
    }),
    set_focus: (params) => ({
      flow: 'churn',
      branch: String(params.branch ?? 'main'),
      asset: (params.asset as string | null) ?? null,
      compare: (params.compare as string[]) ?? [],
    }),
    preflight: (params) => ({
      branch: String(params.branch),
      target: String(params.target ?? ''),
      cached: [],
      recompute: ['features'],
      unknown: [],
      estimate_seconds: 3,
    }),
    'cells.list': (params) => ({ flow: 'churn', branch: String(params.branch), cells: SLICE }),
    'cells.show': (params) => {
      const slug = String(params.slug)
      const summary = SLICE.find((cell) => cell.slug === slug) ?? cellSummary(slug)
      return cellDetail(slug, { ...summary, source: SOURCE, branch: String(params.branch) })
    },
    'cells.logs': () => ({ flow: 'churn', branch: 'main', slug: '', state: null, logs: null }),
    'asset.preview': (params) => ({
      flow: 'churn',
      branch: String(params.branch),
      slug: String(params.target).split('.')[0],
      output: String(params.target).split('.')[1],
      state: 'synced',
      kind: 'metric',
      size: 32,
      persisted: true,
      preview: storedPreview('metric', [{ block: 'kv', entries: { auc: 0.91 } }]),
    }),
    ...overrides,
  }
}

const Empty = defineComponent({ template: '<div />' })

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/flow', component: Empty },
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

async function workbench(
  options: {
    handlers?: Handlers
    at?: string
    journal?: Transaction[]
    /** Where this client got to last time — what makes a reopen behind. */
    seenStep?: number
    caughtUpAt?: number
  } = {},
): Promise<Bench> {
  const live = await attach({
    status: flowStatus({ cells: SLICE }),
    handlers: reads(options.handlers),
    seenStep: options.seenStep,
  })
  const router = testRouter()
  await router.push(options.at ?? `/flow/${FLOW}`)
  await router.isReady()
  const host = defineComponent({
    components: { LiveWorkbench, Toast },
    props: { session: { type: Object, required: true }, stream: { type: Object, required: true } },
    template: '<div><Toast /><LiveWorkbench :session="session" :stream="stream" /></div>',
  })
  const wrapper = mount(host, {
    props: { session: live.session, stream: live.stream },
    global: { plugins: [router, ToastService] },
  })
  for (const entry of options.journal ?? []) {
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: entry.step,
      transaction: entry,
    })
  }
  live.socket.deliver({
    channel: 'journal',
    type: 'caught_up',
    flow: FLOW,
    step: options.caughtUpAt ?? 10,
    running: [],
  })
  await settle()
  return { wrapper, live }
}

async function clickText(wrapper: VueWrapper, label: string): Promise<void> {
  const button = wrapper.findAll('button').find((node) => node.text() === label)
  if (!button) {
    throw new Error(
      `no button labelled "${label}" — saw ${wrapper
        .findAll('button')
        .map((node) => node.text())
        .join(' | ')}`,
    )
  }
  await button.trigger('click')
  await settle()
}

/** Popovers, menus, dialogs and drawers are teleported into the body. */
async function clickInBody(match: string): Promise<void> {
  const node = Array.from(document.body.querySelectorAll('button, .p-menu-item-link')).find(
    (found) => found.textContent?.trim().includes(match),
  )
  if (!node) throw new Error(`nothing in the overlay matching "${match}"`)
  ;(node as HTMLElement).click()
  await settle()
}

function overlays(): string {
  return document.body.textContent ?? ''
}

beforeEach(() => {
  document.body.innerHTML = ''
})

// --- payload builders --------------------------------------------------------

describe('a handoff payload is the daemon’s, per gesture', () => {
  it('asks for the explain payload when the card’s popover opens, and shows that one', async () => {
    const live = await attach({
      status: flowStatus({ cells: SLICE }),
      handlers: reads(),
    })
    const wrapper = mount(LiveCellCard, {
      props: {
        session: live.session,
        stream: live.stream,
        branch: 'main',
        summary: SLICE[0],
        density: 'canvas',
      },
    })
    await settle()

    await openCardMenu(wrapper)
    await clickMenuItem('send to agent')

    expect(asked(live, 'agent.payload')).toEqual([
      { flow: FLOW, branch: 'main', gesture: 'explain', slug: 'features', branches: undefined },
    ])
    // The daemon's payload, not the one this surface could have assembled.
    expect(overlays()).toContain('Daemon-built explain payload.')
    wrapper.unmount()
  })

  it('asks for the fix payload from a failure the reader authored', async () => {
    const failing = cellSummary('features', { state: 'failed', primary: 'train_split' })
    const live = await attach({
      status: flowStatus({ cells: [failing] }),
      handlers: reads({
        'cells.show': () =>
          cellDetail('features', {
            ...failing,
            source: SOURCE,
            author: 'user',
            failed_by: 'user',
            error: 'Traceback (most recent call last):\nValueError: empty frame',
          }),
      }),
    })
    const wrapper = mount(LiveCellCard, {
      props: {
        session: live.session,
        stream: live.stream,
        branch: 'main',
        summary: failing,
        density: 'canvas',
      },
    })
    await settle()

    await clickText(wrapper, 'Fix this')

    expect(asked(live, 'agent.payload').map((params) => params.gesture)).toEqual(['fix'])
    expect(overlays()).toContain('Daemon-built fix payload.')
    wrapper.unmount()
  })

  it('summarizes a branch as a payload the agent turns into a note cell', async () => {
    const { wrapper, live } = await workbench()

    await openPanel(wrapper, 'activity')
    await clickText(wrapper, 'Summarize lane')

    // A branch-wide ask names no cell: it is about the branch, not one card.
    expect(asked(live, 'agent.payload')).toEqual([
      { flow: FLOW, branch: 'main', gesture: 'summarize', slug: undefined, branches: undefined },
    ])
    expect(overlays()).toContain('Daemon-built summarize payload.')
    // The UI hands it over; writing the note is the agent's.
    expect(asked(live, 'cells.new')).toEqual([])
    wrapper.unmount()
  })

  it('re-asks after the journal moves rather than quoting the previous run', async () => {
    const live = await attach({
      status: flowStatus({ cells: SLICE }),
      handlers: reads(),
    })
    const wrapper = mount(LiveCellCard, {
      props: {
        session: live.session,
        stream: live.stream,
        branch: 'main',
        summary: SLICE[0],
        density: 'canvas',
      },
    })
    await settle()
    await openCardMenu(wrapper)
    await clickMenuItem('send to agent')

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 12,
      transaction: transaction(12, { ops: [] }),
    })
    await settle()
    await openCardMenu(wrapper)
    await clickMenuItem('send to agent')

    expect(asked(live, 'agent.payload')).toHaveLength(2)
    wrapper.unmount()
  })
})

// --- pairing -----------------------------------------------------------------

/**
 * Pairing is a prompt the reader hands their agent, and the agent connects back
 * over it — so the prompt is the workspace's to build for the same reason a
 * handoff payload is: it names where the workspace is, which branch the files
 * hold, and which `lumlflow` a config can actually spawn.
 */
describe('the connect prompt is the daemon’s, and flow-scoped', () => {
  it('asks the workspace for it whenever the pairing link is used', async () => {
    const { wrapper, live } = await workbench()

    await clickText(wrapper, 'pair an agent')

    // No branch and no gesture: an agent connects to the workspace.
    expect(asked(live, 'agent.connect')).toEqual([{ flow: FLOW }])
    expect(overlays()).toContain(CONNECT_TEXT)
    // Nothing here runs the agent, so nothing here is a command to run one.
    expect(overlays()).not.toContain('agent exec')

    // Asked again rather than quoting the branch the files used to hold.
    await clickText(wrapper, 'pair an agent')
    expect(asked(live, 'agent.connect')).toHaveLength(2)
    wrapper.unmount()
  })
})

// --- the activity feed -------------------------------------------------------

describe('the activity feed is read-only and opens at the cursor', () => {
  /**
   * A reopen, which is the only thing the marker is about: this client last
   * saw step 10, three transactions landed while it was gone, and the catch-up
   * is where it finds that out. Transactions it watches arrive afterwards are
   * not "since you were here" — it is here.
   */
  it('opens on the marker, divides at where the reader left off, and clears it', async () => {
    const { wrapper } = await workbench({
      seenStep: 10,
      journal: [11, 12, 13].map((step) => transaction(step, { intent: `agent edit ${step}` })),
      caughtUpAt: 13,
    })

    expect(wrapper.text()).toContain('3 changes since you were here')

    await clickText(wrapper, 'open at cursor')

    // The marker's destination is the panel's activity section — the journal
    // has one home, and the marker sends the reader to it rather than to a
    // second copy of the same feed in a drawer.
    const activity = wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((node) => node.text().startsWith('activity'))
    expect(activity?.attributes('aria-expanded')).toBe('true')
    expect(wrapper.text()).toContain('since you were here')
    expect(wrapper.text()).toContain('agent edit 13')
    // The marker is spent by looking at it, and nothing about the feed writes.
    expect(wrapper.text()).not.toContain('changes since you were here')
    wrapper.unmount()
  })

  it('renders the upload states the journal recorded, queued through recorded', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 11,
      transaction: transaction(11, {
        intent: 'promoted train_model.run',
        ops: [
          {
            op: 'upload_state_changed',
            mat_id: 'm-1',
            output: 'run',
            state: 'queued',
            attempts: 0,
          },
        ],
      }),
    })
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 12,
      transaction: transaction(12, {
        intent: 'publishing train_model.run',
        ops: [
          {
            op: 'upload_state_changed',
            mat_id: 'm-1',
            output: 'run',
            state: 'failed',
            attempts: 2,
          },
        ],
      }),
    })
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 13,
      transaction: transaction(13, {
        intent: 'published train_model.run',
        ops: [
          {
            op: 'upload_recorded',
            mat_id: 'm-1',
            output: 'run',
            ref: {
              collection: 'churn-models',
              artifact_id: 'art-1',
              version: 'v1',
              digest: 'sha',
            },
          },
        ],
      }),
    })
    await settleJournal()

    await openPanel(wrapper, 'activity')

    const feed = wrapper.text()
    expect(feed).toContain('upload queued')
    expect(feed).toContain('upload failed · 2 attempts')
    expect(feed).toContain('uploaded to churn-models')
    wrapper.unmount()
  })
})

// --- promote -----------------------------------------------------------------

describe('promote publishes an output the cell declared inline', () => {
  it('names the output and reports the state the daemon put it in', async () => {
    const live = await attach({
      status: flowStatus({ cells: SLICE }),
      handlers: reads({
        promote: (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          slug: 'features',
          output: 'train_split',
          state: 'queued',
        }),
      }),
    })
    const wrapper = mount(LiveCellCard, {
      props: {
        session: live.session,
        stream: live.stream,
        branch: 'main',
        summary: SLICE[0],
        density: 'canvas',
      },
    })
    await settle()

    const more = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'more')!
    await more.trigger('click')
    await settle()
    await clickInBody('promote to LUML')

    expect(asked(live, 'promote')).toEqual([
      {
        flow: FLOW,
        branch: 'main',
        target: 'features.train_split',
        intent: 'promoted features.train_split',
      },
    ])
    // Offline is a state, not a failure: the queue entry is what was reported.
    expect(wrapper.text()).toContain('train_split · upload queued')
    wrapper.unmount()
  })
})

// --- the scratch REPL --------------------------------------------------------

describe('the scratch REPL reads the viewed branch', () => {
  it('evaluates against a branch nobody checked out and writes nothing', async () => {
    const { wrapper, live } = await workbench({
      at: `/flow/${FLOW}?branch=sweep`,
      handlers: {
        eval: (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          repr: '(1200, 8)',
          output: '',
          names: ['train_df'],
          mutated: [],
          error: null,
        }),
      },
    })

    await clickText(wrapper, 'scratch')
    await wrapper.find('textarea').setValue('train_df.shape')
    await settle()
    await clickText(wrapper, 'evaluate')

    expect(asked(live, 'eval')).toEqual([{ flow: FLOW, branch: 'sweep', code: 'train_df.shape' }])
    expect(wrapper.text()).toContain('(1200, 8)')
    // The worktree stays where it was: reading a branch is not checking it out.
    expect(asked(live, 'switch')).toEqual([])
    expect(asked(live, 'cells.edit')).toEqual([])
    expect(asked(live, 'run')).toEqual([])
    wrapper.unmount()
  })

  it('says a mutation hit the copy, because the stored value did not move', async () => {
    const { wrapper } = await workbench({
      handlers: {
        eval: () => ({
          flow: 'churn',
          branch: 'main',
          repr: '1150',
          output: '',
          names: ['train_df'],
          mutated: ['train_df'],
          error: null,
        }),
      },
    })

    await clickText(wrapper, 'scratch')
    await wrapper.find('textarea').setValue('train_df.dropna(inplace=True); len(train_df)')
    await settle()
    await clickText(wrapper, 'evaluate')

    expect(wrapper.text()).toContain('mutated the copy of `train_df`')
    expect(wrapper.text()).toContain('the stored value is unchanged')
    wrapper.unmount()
  })

  it('renders the traceback of an expression that failed', async () => {
    const { wrapper } = await workbench({
      handlers: {
        eval: () => ({
          flow: 'churn',
          branch: 'main',
          repr: null,
          output: '',
          names: [],
          mutated: [],
          error: {
            type: 'NameError',
            message: "name 'nope' is not defined",
            traceback: "NameError: name 'nope' is not defined",
          },
        }),
      },
    })

    await clickText(wrapper, 'scratch')
    await wrapper.find('textarea').setValue('nope')
    await settle()
    await clickText(wrapper, 'evaluate')

    expect(wrapper.text()).toContain("NameError: name 'nope' is not defined")
    wrapper.unmount()
  })
})

// --- env ops and the flow's settings ------------------------------------------

describe('the packages panel drives the workspace env', () => {
  it('adds through the daemon and re-reads what the lockfile now pins', async () => {
    const { wrapper, live } = await workbench()

    await openPanel(wrapper, 'packages')
    await wrapper.find('input[aria-label="add packages"]').setValue('lightgbm')
    await settle()
    await clickText(wrapper, 'add')

    expect(asked(live, 'env.add')).toEqual([
      {
        flow: FLOW,
        packages: ['lightgbm'],
        intent: 'added lightgbm to the workspace env',
      },
    ])
    // Re-read after the install: once at mount, once because it moved.
    expect(asked(live, 'env.status')).toHaveLength(2)
    wrapper.unmount()
  })

  it('removes the package the row names', async () => {
    const { wrapper, live } = await workbench()

    await openPanel(wrapper, 'packages')
    const remove = wrapper
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'remove pandas')!
    await remove.trigger('click')
    await settle()

    expect(asked(live, 'env.remove')).toEqual([
      {
        flow: FLOW,
        packages: ['pandas'],
        intent: 'removed pandas from the workspace env',
      },
    ])
    wrapper.unmount()
  })

  it('writes the env-change policy and renders the daemon’s answer', async () => {
    const { wrapper, live } = await workbench()
    await openPanel(wrapper, 'settings')
    // Driven through the panel's own contract: what a PrimeVue overlay does to
    // a click is its business, and the settings the panel emits are the page's.
    const settings = wrapper.findComponent(PanelSettings)
    expect(settings.props('settings')).toMatchObject({ onEnvChange: 'ask' })

    settings.vm.$emit('update', { ...settings.props('settings'), onEnvChange: 'restart' })
    await settle()

    // The panel says "restart automatically"; `flow.yaml` calls it `auto`.
    expect(asked(live, 'settings.set')).toEqual([
      {
        flow: FLOW,
        reactivity: 'auto',
        eager_cost_threshold_s: 5,
        env_policy: 'auto',
      },
    ])
    // Rendered back off the daemon's answer, not off the click.
    expect(settings.props('settings')).toMatchObject({ onEnvChange: 'restart' })
    expect(wrapper.text()).toContain('restart automatically')
    wrapper.unmount()
  })

  it('leaves the controls where they were when the daemon refuses the write', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'settings.set': () => {
          throw new FlowApiError('`restart` is not an env policy', { status: 400 })
        },
      },
    })
    await openPanel(wrapper, 'settings')
    const settings = wrapper.findComponent(PanelSettings)

    settings.vm.$emit('update', { ...settings.props('settings'), reactivity: 'lazy' })
    await settle()

    expect(asked(live, 'settings.set')).toHaveLength(1)
    expect(settings.props('settings')).toMatchObject({ reactivity: 'auto' })
    wrapper.unmount()
  })
})
