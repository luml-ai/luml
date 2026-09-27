/**
 * Handing work to the agent, reading what it did, and the ops that are not runs.
 *
 * Four rules carry this suite. A copied context is the **daemon's**: the cell
 * address goes over the wire and what comes back is what the reader copies,
 * because the traceback of a run nobody opened is a fact only the store has.
 * The activity feed is **read-only and cursor-anchored** — a marker, not an
 * inbox. The scratch REPL is a **read of any branch**, including one whose
 * files are nowhere, and it writes no version. Env ops and the flow's settings
 * go through the daemon and render its answer, never a control that looks like
 * it took a change and dropped it.
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
import leftPanelGallerySource from '@/flow/workbench/gallery/sections/LeftPanelSection.vue?raw'
import LiveWorkbench from '@/flow/workbench/pages/LiveWorkbench.vue'
import {
  attach,
  cellDetail,
  cellSummary,
  flowStatus,
  FLOW,
  openPanel,
  settle,
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
    head_step: 8,
    newest_step: 8,
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
    head_step: 9,
    newest_step: 9,
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
      restart_required: false,
      behind: [],
    },
  ],
}

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

const copied: string[] = []

Object.defineProperty(navigator, 'clipboard', {
  configurable: true,
  value: {
    writeText: (value: string) => {
      copied.push(value)
      return Promise.resolve()
    },
  },
})

/** The payload the daemon would have built, named so a test can spot it. */
function builtPayload(params: Record<string, unknown>): Record<string, unknown> {
  return {
    flow: 'churn',
    branch: String(params.branch ?? 'main'),
    slug: String(params.slug),
    text:
      'Daemon-built cell context.\n\n' +
      '```lumlflow-context\n' +
      `lane: ${params.branch ?? 'main'}\n` +
      `slug: ${params.slug}\n` +
      'step: 8\n' +
      '```',
  }
}

function reads(overrides: Handlers = {}): Handlers {
  return {
    'agent.payload': builtPayload,
    tree: () => ({ flow: 'churn', branch: 'main', branches: BRANCHES }),
    'env.status': () => ENV,
    'settings.set': (params) => ({
      flow: 'churn',
      settings: {
        reactivity: params.reactivity ?? 'auto',
        eager_cost_threshold_s: params.eager_cost_threshold_s ?? 5,
      },
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

function overlays(): string {
  return document.body.textContent ?? ''
}

beforeEach(() => {
  document.body.innerHTML = ''
  copied.length = 0
})

// --- copied cell context -----------------------------------------------------

describe('one card gesture copies the daemon’s context', () => {
  it('leaves no retired branch-summary handoff in the gallery', () => {
    expect(leftPanelGallerySource).not.toContain('summarize-branch')
    expect(leftPanelGallerySource).not.toContain('onSummarize')
  })

  it('asks for cell context without a gesture and copies the daemon response', async () => {
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

    await wrapper.get('button[aria-label="copy context"]').trigger('click')
    await settle()

    expect(asked(live, 'agent.payload')).toEqual([{ flow: FLOW, branch: 'main', slug: 'features' }])
    expect(copied).toEqual([
      'Daemon-built cell context.\n\n```lumlflow-context\nlane: main\nslug: features\nstep: 8\n```',
    ])
    expect(wrapper.findAll('button[aria-label="copy context"]')).toHaveLength(1)
    expect(overlays()).not.toContain('copy the payload')
    wrapper.unmount()
  })

  it('uses the same single context gesture for a failed cell', async () => {
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

    await wrapper.get('button[aria-label="copy context"]').trigger('click')
    await settle()

    expect(asked(live, 'agent.payload')).toEqual([{ flow: FLOW, branch: 'main', slug: 'features' }])
    expect(copied).toHaveLength(1)
    expect(wrapper.text()).not.toContain('Fix this')
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
    await wrapper.get('button[aria-label="copy context"]').trigger('click')
    await settle()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 12,
      transaction: transaction(12, { ops: [] }),
    })
    await settle()
    await wrapper.get('button[aria-label="copy context"]').trigger('click')
    await settle()

    expect(asked(live, 'agent.payload')).toHaveLength(2)
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

  it('shows a projection-completion cell note in the activity feed', async () => {
    const sentence =
      "projection completed for `features`; use `rewind` to keep the file's bytes instead"
    const { wrapper } = await workbench({
      journal: [
        transaction(11, {
          actor: 'system',
          intent: sentence,
          ops: [
            {
              op: 'cell_noted',
              uid: 'cell-features',
              kind: 'projection_completed',
              sentence,
              version_id: 'version-features',
            },
          ],
        }),
      ],
      caughtUpAt: 11,
    })

    await openPanel(wrapper, 'activity')

    expect(wrapper.text()).toContain(sentence)
    wrapper.unmount()
  })

  it('shows a refresh-failure cell note as one activity line', async () => {
    const sentence = 'could not refresh: the workspace interpreter cannot start'
    const { wrapper } = await workbench({
      journal: [
        transaction(11, {
          actor: 'system',
          intent: sentence,
          ops: [
            {
              op: 'cell_noted',
              uid: 'cell-features',
              kind: 'refresh_failed',
              sentence,
              version_id: 'version-features',
            },
          ],
        }),
      ],
      caughtUpAt: 11,
    })

    await openPanel(wrapper, 'activity')
    const entry = wrapper.findAll('li').find((item) => item.text().includes(sentence))

    expect(entry, 'no refresh failure in the activity feed').toBeTruthy()
    expect(entry?.text().split(sentence)).toHaveLength(2)
    expect(entry?.find('p').exists()).toBe(false)
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

  it('renders the traceback of an expression that failed', async () => {
    const { wrapper } = await workbench({
      handlers: {
        eval: () => ({
          flow: 'churn',
          branch: 'main',
          repr: null,
          output: '',
          names: [],
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

// --- packages and the flow's settings -----------------------------------------

describe('the packages panel and settings', () => {
  it('names the interpreter and source in the folded packages header', async () => {
    const venv = await workbench()
    const venvHeader = venv.wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((header) => header.text().startsWith('packages'))!

    expect(venvHeader.text()).toContain('python /tmp/project/.venv/bin/python · source venv')
    venv.wrapper.unmount()

    const own = await workbench({
      handlers: {
        'env.status': () => ({
          ...ENV,
          python: { path: '/opt/lumlflow/bin/python', source: 'lumlflow' },
        }),
      },
    })
    const ownHeader = own.wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((header) => header.text().startsWith('packages'))!

    expect(ownHeader.text()).toContain(
      "python /opt/lumlflow/bin/python · source lumlflow's own interpreter",
    )
    own.wrapper.unmount()
  })

  it('lists packages without package-manager controls', async () => {
    const { wrapper, live } = await workbench()

    await openPanel(wrapper, 'packages')

    expect(wrapper.text()).toContain('pandas')
    expect(wrapper.find('input[aria-label="add packages"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="remove pandas"]').exists()).toBe(false)
    expect(asked(live, 'env.status')).toHaveLength(1)
    expect(asked(live, 'env.add')).toEqual([])
    expect(asked(live, 'env.remove')).toEqual([])
    wrapper.unmount()
  })

  it('names the absence of a uv-managed environment', async () => {
    const { wrapper } = await workbench({
      handlers: {
        'env.status': () => ({ ...ENV, packages: [] }),
      },
    })

    await openPanel(wrapper, 'packages')

    expect(wrapper.text()).toContain('no uv-managed environment here')
    wrapper.unmount()
  })

  it('writes reactivity and renders the daemon’s answer', async () => {
    const { wrapper, live } = await workbench()
    await openPanel(wrapper, 'settings')
    const settings = wrapper.findComponent(PanelSettings)
    expect(settings.props('settings')).toMatchObject({ reactivity: 'auto' })

    settings.vm.$emit('update', { ...settings.props('settings'), reactivity: 'lazy' })
    await settle()

    expect(asked(live, 'settings.set')).toEqual([
      {
        flow: FLOW,
        reactivity: 'lazy',
        eager_cost_threshold_s: 5,
      },
    ])
    expect(settings.props('settings')).toMatchObject({ reactivity: 'lazy' })
    expect(wrapper.text()).not.toContain('on env change')
    wrapper.unmount()
  })

  it('leaves the controls where they were when the daemon refuses the write', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'settings.set': () => {
          throw new FlowApiError('`lazy` was refused', { status: 400 })
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
