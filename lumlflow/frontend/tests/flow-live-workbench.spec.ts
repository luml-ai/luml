/**
 * The two views and the left panel, on a live session.
 *
 * Three rules carry this suite. Staleness leads with the **direct cause** —
 * what is not current in its own right, named in words — while what merely sits
 * below it stays counted and one toggle away, and `unmaterialized` is neither
 * of those: no baseline exists to claim a change against. The canvas and the
 * notebook are **two densities over one slice**, so a cell on one is a cell on
 * the other and the notebook's column is pinned by effective order rather than by
 * name. And viewing another branch **re-scopes the whole screen** — panel,
 * views and URL — as the pure store read it is, with nothing checked out.
 */

import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { Toast } from 'primevue'
import ToastService from 'primevue/toastservice'

import { FlowApiError, type EnvReport } from '@/flow/api/client'
import type { AgentHarness, BranchRecord, CellSummary, TrackerExperiment } from '@/flow/api/types'
import LiveCellCard from '@/flow/workbench/components/card/LiveCellCard.vue'
import FlowCanvas from '@/flow/workbench/components/canvas/FlowCanvas.vue'
import EmptyFlowState from '@/flow/workbench/pages/EmptyFlowState.vue'
import LiveWorkbench from '@/flow/workbench/pages/LiveWorkbench.vue'
import AgentTaskLine from '@/flow/workbench/components/panel/AgentTaskLine.vue'
import {
  attach,
  cellDetail,
  cellSummary,
  flowStatus,
  FLOW,
  openPanel,
  settle,
  settleJournal,
  storedPreview,
  transaction,
} from './fakes'
import type { Attached, Handlers } from './fakes'
import { editorIn } from './editor'

// A churn flow, as the daemon reports it. `features` is not current in its own
// right; `train_model` is current and sits under it; `holdout_eval` has never
// run anywhere. `alpha_scan` is a second root written last — its name sorts it
// first and its effective key does not.
const MAIN: CellSummary[] = [
  cellSummary('load_customers', {
    outputs: ['customers'],
    kinds: { customers: 'dataset' },
    primary: 'customers',
    external: true,
    created_step: 2,
  }),
  cellSummary('features', {
    state: 'unsynced',
    causes: ['`helpers.py` changed'],
    consumes: { clean: 'load_customers.customers' },
    outputs: ['train_split'],
    kinds: { train_split: 'frame' },
    primary: 'train_split',
    created_step: 4,
  }),
  cellSummary('train_model', {
    transitive: true,
    upstream: ['features'],
    consumes: { train: 'features.train_split' },
    outputs: ['model', 'run'],
    kinds: { model: 'model', run: 'experiment' },
    primary: 'run',
    created_step: 6,
  }),
  cellSummary('holdout_eval', {
    state: 'unmaterialized',
    consumes: { model: 'train_model.model' },
    outputs: ['scores'],
    kinds: { scores: 'metric' },
    primary: 'scores',
    cost_seconds: null,
    created_step: 8,
  }),
  cellSummary('alpha_scan', {
    outputs: ['grid'],
    kinds: { grid: 'frame' },
    primary: 'grid',
    created_step: 12,
  }),
]

const SWEEP: CellSummary[] = [
  cellSummary('features', {
    consumes: {},
    outputs: ['train_split'],
    kinds: { train_split: 'frame' },
    primary: 'train_split',
    created_step: 4,
  }),
  cellSummary('sweep_notes', {
    note: true,
    outputs: [],
    kinds: {},
    primary: null,
    created_step: 9,
  }),
]

const BRANCHES: BranchRecord[] = [
  {
    branch: 'main',
    branch_id: 'branch-main',
    parent: null,
    forked_at_step: 0,
    parent_step: null,
    archived: false,
    checked_out: true,
    cells: MAIN.length,
    states: { synced: 3, unsynced: 1, unmaterialized: 1 },
    checkpoint: 6,
    head_step: 14,
    newest_step: 14,
    last_intent: {
      step: 14,
      ts: '2026-08-13T09:14:00Z',
      actor: 'claude-1',
      intent: 'edited features',
      offline: false,
      settled: false,
    },
    agent: 'claude-1',
  },
  {
    branch: 'exp/lr-sweep',
    branch_id: 'branch-sweep',
    parent: 'main',
    forked_at_step: 6,
    parent_step: 5,
    archived: false,
    checked_out: false,
    cells: SWEEP.length,
    states: { synced: 2 },
    checkpoint: 10,
    head_step: 10,
    newest_step: 10,
    last_intent: {
      step: 10,
      ts: '2026-08-13T09:10:00Z',
      actor: 'user',
      intent: 'swept the learning rate',
      offline: false,
      settled: true,
    },
    agent: null,
  },
]

const SLICES: Record<string, CellSummary[]> = { main: MAIN, 'exp/lr-sweep': SWEEP }

const ENV: EnvReport = {
  workspace: '/tmp/project',
  python: { path: '/tmp/project/.venv/bin/python', source: 'venv' },
  packages: [
    { name: 'pandas', version: '2.2.1' },
    { name: 'lightgbm', version: '4.5.0' },
  ],
  flows: [
    {
      flow: 'churn',
      kernel: 'running',
      restart_required: false,
      behind: [],
    },
  ],
}

const CLAUDE_HARNESS: AgentHarness = {
  id: 'claude-code',
  display_name: 'Claude Code',
  state: 'not set up',
  config_path: '/home/dana/.claude.json',
  snippet: '{"mcpServers":{"lumlflow":{"command":"lumlflow","args":["mcp"]}}}',
  can_setup: true,
  action: 'setup',
  consent_required: true,
  consent_prompt: 'Allow lumlflow to update /home/dana/.claude.json and keep its entry current?',
  post_write_hint: 'approve the server when Claude Code asks',
  shell: true,
  shell_hint: 'also works without setup: run `lumlflow guide` in it',
  error: null,
}

interface Bench {
  wrapper: VueWrapper
  live: Attached
  router: Router
}

const Empty = defineComponent({ template: '<div />' })
const WorkbenchHost = defineComponent({
  components: { LiveWorkbench, Toast },
  props: { session: { type: Object, required: true }, stream: { type: Object, required: true } },
  template: '<div><Toast /><LiveWorkbench :session="session" :stream="stream" /></div>',
})

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

async function workbench(
  options: { handlers?: Handlers; at?: string; branch?: string; withToasts?: boolean } = {},
): Promise<Bench> {
  const live = await attach({
    status: flowStatus({ cells: MAIN, ...(options.branch ? { branch: options.branch } : {}) }),
    handlers: {
      tree: () => ({ flow: 'churn', branch: 'main', branches: BRANCHES }),
      'env.status': () => ENV,
      'cells.list': (params) => ({
        flow: 'churn',
        branch: String(params.branch),
        cells: SLICES[String(params.branch)] ?? [],
      }),
      'cells.show': (params) => {
        const slug = String(params.slug)
        const summary =
          (SLICES[String(params.branch)] ?? MAIN).find((cell) => cell.slug === slug) ??
          cellSummary(slug)
        return cellDetail(slug, { ...summary, branch: String(params.branch) })
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
      switch: (params) => ({
        ...flowStatus({ branch: String(params.branch) }),
        projected: null,
      }),
      ...options.handlers,
    },
  })
  const router = testRouter()
  await router.push(options.at ?? `/flow/${FLOW}`)
  await router.isReady()
  const wrapper = mount(options.withToasts ? WorkbenchHost : LiveWorkbench, {
    props: { session: live.session, stream: live.stream },
    global: { plugins: [router, ToastService] },
  })
  await settle()
  return { wrapper, live, router }
}

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

function toasts(): string {
  return Array.from(document.body.querySelectorAll('.p-toast-message'))
    .map((node) => node.textContent ?? '')
    .join(' ')
}

/** The slugs on screen, in the order the view drew them. */
function drawn(wrapper: VueWrapper): string[] {
  return wrapper.findAll('article h3').map((heading) => heading.text())
}

function liveCard(wrapper: VueWrapper, slug: string): VueWrapper {
  const card = wrapper
    .findAllComponents(LiveCellCard)
    .find((candidate) => candidate.props('summary').slug === slug)
  expect(card, `no live card for "${slug}"`).toBeTruthy()
  return card!
}

async function startDraft(wrapper: VueWrapper, slug: string, source: string): Promise<void> {
  const card = liveCard(wrapper, slug)
  await card
    .findAll('[role="tab"]')
    .find((tab) => tab.text() === 'code')
    ?.trigger('click')
  await settle()
  await clickText(card, 'button', 'edit')
  const editor = await editorIn(card)
  editor.view.dispatch({
    changes: { from: 0, to: editor.view.state.doc.length, insert: source },
  })
  await settle()
}

/**
 * One inventory lens of the left panel, addressed by the label on its
 * disclosure. Every lens but `cells` starts collapsed and its rows are not
 * rendered until it is opened, so reading one opens it first.
 */
async function lens(wrapper: VueWrapper, label: string): Promise<string> {
  await openPanel(wrapper, label)
  const header = wrapper
    .findAll('[data-pc-name="accordionheader"]')
    .find((node) => node.text().startsWith(label))
  return header?.element.closest('[data-pc-name="accordionpanel"]')?.textContent ?? ''
}

/** Lens labels the panel offers at all — a lens with no rows is not one. */
function lensLabels(wrapper: VueWrapper): string[] {
  return wrapper
    .findAll('[data-pc-name="accordionheader"]')
    .map((node) => node.text().split(/\s+/)[0])
}

async function clickText(wrapper: VueWrapper, selector: string, text: string): Promise<void> {
  const found = wrapper.findAll(selector).find((node) => node.text().includes(text))
  expect(found, `no ${selector} reading "${text}"`).toBeTruthy()
  await found?.trigger('click')
  await settle()
}

/** The overlay is a dialog: teleported to the body, outside the wrapper. */
async function clickInOverlay(text: string): Promise<void> {
  const found = [...document.body.querySelectorAll('button')].find((node) =>
    (node.textContent ?? '').includes(text),
  )
  expect(found, `no overlay button reading "${text}"`).toBeTruthy()
  found?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await settle()
}

/**
 * A row in the overlay is addressed by the branch it names, and its verbs by
 * their labels.
 */
async function clickBranchVerb(branch: string, verb: string): Promise<void> {
  const row = [...document.body.querySelectorAll('li')].find((node) =>
    (node.textContent ?? '').includes(branch),
  )
  expect(row, `no branch row for "${branch}"`).toBeTruthy()
  const button = [...(row?.querySelectorAll('button') ?? [])].find((node) =>
    (node.textContent ?? '').includes(verb),
  )
  expect(button, `no "${verb}" on the row for "${branch}"`).toBeTruthy()
  button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await settle()
}

describe('agent setup', () => {
  it('detects agents whenever the section is opened directly', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'agents.harnesses': () => ({ harnesses: [CLAUDE_HARNESS] }),
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: [],
        }),
      },
    })

    await openPanel(wrapper, 'agents')

    expect(asked(live, 'agents.harnesses')).toEqual([{}])
    expect(wrapper.text()).toContain('Claude Code')

    const header = wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((node) => node.text().startsWith('agents'))
    await header?.trigger('click')
    await settle()
    await header?.trigger('click')
    await settle()

    expect(asked(live, 'agents.harnesses')).toEqual([{}, {}])
    wrapper.unmount()
  })

  it('opens the Agents section from the empty-flow pairing button', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'agents.harnesses': () => ({ harnesses: [CLAUDE_HARNESS] }),
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: [],
        }),
      },
    })

    const empty = wrapper.getComponent(EmptyFlowState)
    const pair = empty.findAll('button').find((button) => button.text() === 'pair an agent')
    expect(pair, 'no pair link on the empty flow').toBeTruthy()
    await pair?.trigger('click')
    await settle()

    const agentsHeader = wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((node) => node.text().startsWith('agents'))
    expect(agentsHeader?.attributes('aria-expanded')).toBe('true')
    expect(asked(live, 'agents.harnesses')).toEqual([{}])
    wrapper.unmount()
  })

  it('goes from detected to set up and shows the label when the agent connects', async () => {
    let listed = CLAUDE_HARNESS
    const { wrapper, live } = await workbench({
      handlers: {
        'agents.harnesses': () => ({ harnesses: [listed] }),
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: [],
        }),
        'agents.setup': () => {
          listed = {
            ...CLAUDE_HARNESS,
            state: 'set up',
            action: null,
            consent_required: false,
            consent_prompt: null,
          }
          return listed
        },
      },
    })

    await clickText(wrapper, 'button', 'pair an agent')

    expect(asked(live, 'agents.harnesses')).toEqual([{}])
    expect(wrapper.text()).toContain('Claude Code')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await clickText(wrapper, 'button', 'Set up')
    await clickInOverlay('Allow and set up')

    expect(asked(live, 'agents.setup')).toEqual([{ harness: 'claude-code', consent: true }])
    expect(wrapper.text()).toContain('approve the server when Claude Code asks')

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 3,
      transaction: transaction(3, {
        actor: 'claude-code-1',
        intent: 'Claude Code started working',
        ops: [{ op: 'agent_begin', actor: 'claude-code-1', label: 'Claude Code agent' }],
      }),
    })
    await settle()

    expect(wrapper.text()).toContain('Claude Code agent')
    wrapper.unmount()
  })
})

describe('staleness leads with the direct cause', () => {
  it('names what is unsynced, counts what sits below it, and keeps the two apart', async () => {
    const { wrapper } = await workbench()

    // One line in the bar, not a page-wide field: the three counts are the
    // whole of it, and each is a different claim.
    const summary = wrapper.get('[data-testid="stale-summary"]').text()
    expect(summary).toContain('1 stale')
    expect(cardFor(wrapper, 'features')).toContain('helpers.py changed')
    // What sits below it is counted, never folded into the number above.
    expect(summary).toContain('1 downstream')
    // And a cell nobody ever ran is neither — its own state, its own count.
    expect(summary).toContain('1 never materialized')
    expect(wrapper.text()).toContain('unmaterialized')

    // Off by default: the downstream cell reads as what it is on its own facts.
    expect(cardFor(wrapper, 'train_model')).not.toContain('stale')
    expect(cardFor(wrapper, 'features')).toContain('stale')
    wrapper.unmount()
  })

  it('shows downstream staleness when the filter asks for it, subdued and labelled', async () => {
    const { wrapper } = await workbench()

    // The lens rides in the summary's popover — the count is the fact on
    // screen, and the view over it is what a reader asks for next.
    await wrapper.get('[data-testid="stale-summary"]').trigger('click')
    await settle()
    const toggle = (): HTMLInputElement => {
      const input = document.body.querySelector<HTMLInputElement>(
        '[data-pc-name="toggleswitch"] input',
      )
      expect(input, 'no downstream toggle in the summary popover').toBeTruthy()
      return input as HTMLInputElement
    }

    toggle().click()
    await settle()

    // The chip says which view is talking: stale, downstream, and why.
    expect(cardFor(wrapper, 'train_model')).toContain('stale · downstream')
    expect(cardFor(wrapper, 'train_model')).toContain('upstream features is not current')
    // Turning it off puts the cell back to its own verdict.
    toggle().click()
    await settle()
    expect(cardFor(wrapper, 'train_model')).not.toContain('downstream')
    wrapper.unmount()
  })

  it('never claims a change against a baseline that does not exist', async () => {
    const { wrapper } = await workbench()

    expect(cardFor(wrapper, 'holdout_eval')).toContain('unmaterialized')
    expect(cardFor(wrapper, 'holdout_eval')).not.toContain('stale')
    wrapper.unmount()
  })
})

describe('reactivity state and gates', () => {
  it('shows refreshing from the state frame until the run starts', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'state',
      state: 'refreshing',
      flow: FLOW,
      lane: 'main',
      cell: 'features',
      step: 14,
    })
    await settle()

    expect(cardFor(wrapper, 'features')).toContain('refreshing')
    expect(cardFor(wrapper, 'features')).not.toContain('running')

    live.socket.deliver({
      channel: 'journal',
      type: 'kernel',
      event: 'started',
      flow: FLOW,
      run_id: 'run-features',
      slug: 'features',
      step: 14,
    })
    await settle()

    expect(cardFor(wrapper, 'features')).toContain('running')
    expect(cardFor(wrapper, 'features')).not.toContain('refreshing')
    wrapper.unmount()
  })

  it('renders each gate on its card and counts gates in the top bar', async () => {
    const gated = [
      cellSummary('first_run', {
        state: 'unmaterialized',
        cost_seconds: null,
        auto_declined: {
          reason: 'never-timed',
          estimate_seconds: 0,
          untimed: ['first_run'],
        },
      }),
      cellSummary('untimed', {
        state: 'unsynced',
        causes: ['`untimed` was edited'],
        auto_declined: {
          reason: 'never-timed',
          estimate_seconds: 0,
          untimed: ['untimed'],
        },
      }),
      cellSummary('threshold', {
        state: 'unsynced',
        causes: ['`threshold` was edited'],
        auto_declined: {
          reason: 'too-expensive',
          estimate_seconds: 600,
          untimed: [],
        },
      }),
      cellSummary('blocked', {
        state: 'unsynced',
        causes: ['parent `failed_parent` rematerialized'],
        auto_declined: {
          reason: 'blocked',
          estimate_seconds: 0,
          untimed: [],
          detail:
            'blocked by failed parent `failed_parent`. edit `failed_parent` to unblock auto-refresh.',
        },
      }),
      cellSummary('refresh_failed', {
        state: 'unsynced',
        causes: ['`refresh_failed` was edited'],
        auto_declined: {
          reason: 'refresh-failed',
          estimate_seconds: 0,
          untimed: [],
          detail: 'could not refresh: the workspace interpreter cannot start',
        },
      }),
    ]
    const { wrapper } = await workbench({
      handlers: {
        'cells.list': () => ({ flow: 'churn', branch: 'main', cells: gated }),
      },
    })

    expect(cardFor(wrapper, 'first_run')).toContain(
      'never run yet — run it once to enable auto-refresh',
    )
    expect(cardFor(wrapper, 'untimed')).toContain('never run here, so its cost is unknown')
    expect(cardFor(wrapper, 'threshold')).toContain('too expensive to refresh on its own')
    expect(cardFor(wrapper, 'blocked')).toContain('edit `failed_parent` to unblock auto-refresh')
    expect(cardFor(wrapper, 'refresh_failed')).toContain(
      'could not refresh: the workspace interpreter cannot start',
    )

    const summary = wrapper.get('[data-testid="stale-summary"]').text()
    expect(summary).toContain('1 waiting on threshold')
    expect(summary).toContain('1 never timed')
    expect(summary).toContain('1 blocked by a failure')
    expect(summary).toContain('1 could not refresh')
    wrapper.unmount()
  })
})

describe('canvas and notebook are two densities over one slice', () => {
  it('draws the same cells either way, in effective order down the notebook', async () => {
    const { wrapper } = await workbench()

    const canvas = drawn(wrapper)
    expect(new Set(canvas)).toEqual(new Set(MAIN.map((cell) => cell.slug)))

    const notebook = await workbench({ at: `/flow/${FLOW}?view=notebook` })
    const column = drawn(notebook.wrapper)
    expect(new Set(column)).toEqual(new Set(canvas))
    // Topological: a producer is above its consumer.
    expect(column.indexOf('features')).toBeLessThan(column.indexOf('train_model'))
    expect(column.indexOf('train_model')).toBeLessThan(column.indexOf('holdout_eval'))
    // With no explicit map, effective order falls back to creation step, so the
    // cell written last stays last — the
    // alphabet would have put `alpha_scan` at the top of the column, and a
    // layered walk would have hoisted it over everything with a parent.
    expect(column[column.length - 1]).toBe('alpha_scan')

    wrapper.unmount()
    notebook.wrapper.unmount()
  })

  it('crosses from one view to the other carrying the cell and the URL', async () => {
    const { wrapper } = await workbench()

    // Selecting is one gesture and switching view is another: the card carries
    // no jump button, because the selection already survives the switch.
    await clickText(wrapper, '[data-testid="lens-row"]', 'features')
    await clickText(wrapper, '[role="group"][aria-label="view"] button', 'notebook')

    // The view is the route and the cell rides the query — the link is the
    // whole address, so the other view opens on the same card.
    expect(window.location.pathname).toBe(`/flow/${FLOW}/notebook`)
    expect(window.location.search).toContain('asset=features')
    expect(drawn(wrapper)).toEqual([
      'load_customers',
      'features',
      'train_model',
      'holdout_eval',
      'alpha_scan',
    ])
    wrapper.unmount()
  })

  it('keeps the canvas layout for the session across view switches', async () => {
    const { wrapper } = await workbench()
    const firstCanvas = wrapper.getComponent(FlowCanvas).element

    await clickText(wrapper, '[role="group"][aria-label="view"] button', 'notebook')
    await clickText(wrapper, '[role="group"][aria-label="view"] button', 'canvas')

    const restored = wrapper.getComponent(FlowCanvas)
    const state = restored.props('state')
    expect(restored.element).not.toBe(firstCanvas)
    expect(state).toBeDefined()
    expect(Object.keys(state!.layout.positions)).toEqual(
      expect.arrayContaining(MAIN.map((cell) => cell.slug)),
    )
    wrapper.unmount()
  })

  for (const view of ['canvas', 'notebook'] as const) {
    it(`${view} selects a card control once without reporting focus or rewriting its URL twice`, async () => {
      const at =
        view === 'notebook'
          ? `/flow/${FLOW}?view=notebook&asset=features`
          : `/flow/${FLOW}?asset=features`
      const { wrapper, live } = await workbench({ at })
      const replaceState = vi.spyOn(window.history, 'replaceState')
      replaceState.mockClear()
      const calls = live.daemon.calls.length
      const card = liveCard(wrapper, 'train_model')
      const more = card.find('button[aria-label="more"]')

      await more.trigger('pointerdown')
      await more.trigger('click')
      await settle()

      expect(window.location.search).toContain('asset=train_model')
      expect(replaceState).toHaveBeenCalledTimes(1)
      expect(live.daemon.calls).toHaveLength(calls)
      expect(document.body.querySelector('[role="menu"]')).toBeTruthy()

      await more.trigger('pointerdown')
      await more.trigger('click')
      await settle()

      expect(replaceState).toHaveBeenCalledTimes(1)
      expect(live.daemon.calls).toHaveLength(calls)
      replaceState.mockRestore()
      wrapper.unmount()
    })
  }
})

describe('drafts survive run and fork transitions', () => {
  const draft = 'class Features:\n    """Engineer the features."""\n    threshold = 0.7\n'

  it('keeps the source editor and its draft open when the cell starts running', async () => {
    const { wrapper, live } = await workbench({ at: `/flow/${FLOW}?view=notebook` })
    await startDraft(wrapper, 'features', draft)

    live.socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'started',
      step: 15,
      run_id: 'run-features',
      slug: 'features',
    })
    await settle()

    const card = liveCard(wrapper, 'features')
    expect(card.find('[role="tab"][aria-selected="true"]').text()).toContain('code')
    expect((await editorIn(card)).view.state.doc.toString()).toBe(draft)
    wrapper.unmount()
  })

  it('prefills the fork dialog, accepts another name, and lands the draft there', async () => {
    let firstEdit = true
    const { wrapper, live } = await workbench({
      at: `/flow/${FLOW}?view=notebook`,
      handlers: {
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: MAIN,
        }),
        'cells.edit': (params) => {
          if (firstEdit) {
            firstEdit = false
            throw new FlowApiError('`features` moved', { kind: 'EditConflict', status: 409 })
          }
          return {
            slug: 'features',
            branch: String(params.branch),
            definition_hash: 'forked-hash',
            written_to_files: true,
            flags: [],
          }
        },
        fork: (params) => {
          if (params.name === 'features-edit') {
            throw new FlowApiError('a lane named features-edit already exists', {
              kind: 'BranchAlreadyExists',
              status: 400,
            })
          }
          return {
            branch: String(params.name),
            from_branch: String(params.from_branch),
            forked_at_step: 14,
            cells: MAIN.length,
          }
        },
      },
    })
    await startDraft(wrapper, 'features', draft)
    await clickText(liveCard(wrapper, 'features'), 'button', 'save')
    await clickText(liveCard(wrapper, 'features'), 'button', 'save to a new lane')

    const name = document.body.querySelector<HTMLInputElement>('input[aria-label="lane name"]')
    expect(name?.value).toBe('features-edit')
    await clickInOverlay('create lane')
    expect(document.body.textContent).toContain('already exists')

    name!.value = 'features-review'
    name!.dispatchEvent(new Event('input', { bubbles: true }))
    await settle()
    await clickInOverlay('create lane')

    expect(asked(live, 'fork').map((params) => params.name)).toEqual([
      'features-edit',
      'features-review',
    ])
    expect(asked(live, 'cells.edit').at(-1)).toMatchObject({
      branch: 'features-review',
      slug: 'features',
      source: draft,
    })
    expect(window.location.search).toContain('branch=features-review')
    wrapper.unmount()
  })

  it('shows the new lane and keeps the draft when its edit is refused', async () => {
    let editAttempt = 0
    const { wrapper } = await workbench({
      at: `/flow/${FLOW}?view=notebook`,
      handlers: {
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: MAIN,
        }),
        'cells.edit': () => {
          editAttempt += 1
          if (editAttempt === 1) {
            throw new FlowApiError('`features` moved', { kind: 'EditConflict', status: 409 })
          }
          throw new FlowApiError('the forked edit was refused', {
            kind: 'FlowError',
            status: 400,
          })
        },
        fork: (params) => ({
          branch: String(params.name),
          from_branch: String(params.from_branch),
          forked_at_step: 14,
          cells: MAIN.length,
        }),
      },
    })
    await startDraft(wrapper, 'features', draft)
    await clickText(liveCard(wrapper, 'features'), 'button', 'save')
    await clickText(liveCard(wrapper, 'features'), 'button', 'save to a new lane')
    await clickInOverlay('create lane')

    expect(window.location.search).toContain('branch=features-edit')
    const card = liveCard(wrapper, 'features')
    expect(card.text()).toContain('the forked edit was refused')
    expect((await editorIn(card)).view.state.doc.toString()).toBe(draft)
    wrapper.unmount()
  })
})

describe('the left panel is scoped to the viewed branch', () => {
  it('lists the branch, its cells, and the lenses over what they declare', async () => {
    const { wrapper } = await workbench()

    expect(wrapper.text()).toContain('root lane')
    // The step count is the timeline's handle rather than a caption: the
    // branch's position is a thing you move, not just a number you read.
    expect(wrapper.find('button[aria-label="Steps on main"]').text()).toContain('14 steps')
    // The lenses group on what the outputs are, before any preview is read.
    expect(await lens(wrapper, 'models')).toContain('train_model.model')
    // A dataset output, plus the cells that read outside the store — which is
    // what "input" honestly means once something is running.
    expect(await lens(wrapper, 'data')).toContain('load_customers.customers')
    expect(await lens(wrapper, 'data')).toContain('external')
    // Docs is note cells, and this branch wrote none — a lens with nothing on
    // the branch is not rendered at all, not a heading saying zero.
    expect(lensLabels(wrapper)).not.toContain('docs')
    wrapper.unmount()
  })

  it('lists the viewed branch note cells under docs', async () => {
    const { wrapper } = await workbench()

    await clickText(wrapper, 'button[aria-label^="Open the lane map"]', '')
    await clickBranchVerb('exp/lr-sweep', 'view')

    // The branch that has prose shows it; re-scoping brought its notes along.
    expect(await lens(wrapper, 'docs')).toContain('sweep_notes')
    expect(await lens(wrapper, 'cells')).toContain('features')
    wrapper.unmount()
  })

  it('lists a memo-hit experiment with its recording lane and reacts to deletion', async () => {
    let trackerState: TrackerExperiment['state'] = 'ok'
    const tracker = (): TrackerExperiment => ({
      id: 'experiment-main',
      group: 'churn',
      state: trackerState,
      url: trackerState === 'ok' ? '/experiments/group-1/experiment-main' : null,
      store: '/tmp/experiments',
      tags: ['main', 'evaluate'],
      sentence:
        trackerState === 'ok'
          ? ''
          : 'experiment `experiment-main` was removed from tracker store `/tmp/experiments`.',
      recorded_step: 14,
    })
    const trackedCell = (branch: string): CellSummary =>
      cellSummary('evaluate', {
        outputs: ['metrics'],
        kinds: { metrics: 'experiment' },
        primary: 'metrics',
        reused: branch !== 'main',
        tracker: tracker(),
      })
    const handlers: Handlers = {
      'cells.list': (params) => {
        const branch = String(params.branch)
        return { flow: 'churn', branch, cells: [trackedCell(branch)] }
      },
      'cells.show': (params) => {
        const branch = String(params.branch)
        return cellDetail('evaluate', {
          ...trackedCell(branch),
          branch,
          produces: { metrics: { type: 'experiment', kind: null, persist: true } },
          materialized: [
            {
              name: 'metrics',
              kind: 'experiment',
              kind_source: 'declared',
              declared: 'experiment',
              size: 256,
              persisted: true,
            },
          ],
        })
      },
      'asset.preview': (params) => ({
        flow: 'churn',
        branch: String(params.branch),
        slug: 'evaluate',
        output: 'metrics',
        state: 'synced',
        kind: 'experiment',
        size: 256,
        persisted: true,
        preview: storedPreview('experiment', [
          { block: 'markdown', text: '**metrics**' },
          { block: 'kv', entries: { rmse: 0.22 } },
        ]),
        tracker: tracker(),
      }),
    }

    const main = await workbench({ handlers })
    const mainBefore = await lens(main.wrapper, 'experiments')
    expect(mainBefore.match(/evaluate\.metrics/g)).toHaveLength(1)
    expect(mainBefore).toContain('main')
    expect(mainBefore).toContain('ok')
    main.wrapper.unmount()

    const memoHit = await workbench({
      at: `/flow/${FLOW}?branch=exp%2Flr-sweep`,
      handlers,
    })
    const hitBefore = await lens(memoHit.wrapper, 'experiments')
    expect(hitBefore.match(/evaluate\.metrics/g)).toHaveLength(1)
    expect(hitBefore).toContain('main')
    expect(hitBefore).toContain('ok')

    trackerState = 'missing'
    memoHit.live.socket.deliver({
      channel: 'journal',
      type: 'state',
      flow: FLOW,
      lane: 'exp/lr-sweep',
      cell: 'evaluate',
      state: 'experiment_removed',
      step: 14,
    })
    await settle()

    const hitAfter = await lens(memoHit.wrapper, 'experiments')
    expect(hitAfter.match(/evaluate\.metrics/g)).toHaveLength(1)
    expect(hitAfter).toContain('main')
    expect(hitAfter).toContain('removed')
    expect(cardFor(memoHit.wrapper, 'evaluate')).toContain('removed')
    expect(liveCard(memoHit.wrapper, 'evaluate').find('.opacity-60').exists()).toBe(true)
    memoHit.wrapper.unmount()

    const mainAfterDelete = await workbench({ handlers })
    const mainAfter = await lens(mainAfterDelete.wrapper, 'experiments')
    expect(mainAfter.match(/evaluate\.metrics/g)).toHaveLength(1)
    expect(mainAfter).toContain('main')
    expect(mainAfter).toContain('removed')
    mainAfterDelete.wrapper.unmount()
  })

  it('shows the intents of the viewed branch, and the workspace ones under it', async () => {
    const { wrapper, live } = await workbench()

    for (const line of [
      transaction(15, { branch: 'branch-main', intent: 'edited features' }),
      transaction(16, { branch: 'branch-sweep', intent: 'swept the learning rate' }),
      transaction(17, {
        branch: null,
        actor: 'user',
        intent: 'installed lightgbm',
        ops: [{ op: 'env_changed', lock_hash: 'x', packages: {}, summary: 'lightgbm 4.5.0 added' }],
      }),
    ]) {
      live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step: line.step,
        transaction: line,
      })
    }
    await settle()

    await openPanel(wrapper, 'activity')
    const panel = wrapper.text()
    expect(panel).toContain('edited features')
    // Another branch's work is another branch's; the env change is everyone's.
    expect(panel).not.toContain('swept the learning rate')
    expect(panel).toContain('installed lightgbm')
    wrapper.unmount()
  })

  it('opens on the branch the worktree is bound to, not on a name it assumed', async () => {
    // Reopening is durable store state: the files are on `exp/lr-sweep`, so
    // that is what the screen comes up scoped to. A `main` default would be a
    // preference overruling the branch the session is actually standing on.
    // Opened at `/flow/:flowId` with no branch in the query, so the only thing
    // that could have scoped it is the session's own answer.
    const { wrapper, live } = await workbench({ branch: 'exp/lr-sweep' })

    expect(drawn(wrapper)).toEqual(['features', 'sweep_notes'])
    expect(wrapper.text()).toContain('started from main')
    // Reading where the files already are rebinds nothing.
    expect(asked(live, 'switch')).toEqual([])
    wrapper.unmount()
  })

  it('re-scopes to another branch as a pure read, checking nothing out', async () => {
    const { wrapper, live } = await workbench()

    await clickText(wrapper, 'button[aria-label^="Open the lane map"]', '')
    await clickBranchVerb('exp/lr-sweep', 'view')

    // The slice, the cards and the panel all followed.
    expect(drawn(wrapper)).toEqual(['features', 'sweep_notes'])
    expect(wrapper.text()).toContain('started from main')
    expect(window.location.search).toContain('branch=exp%2Flr-sweep')
    // Viewing is a store read: nothing rebound the worktree.
    expect(asked(live, 'switch')).toEqual([])
    expect(asked(live, 'cells.list').map((params) => params.branch)).toContain('exp/lr-sweep')
    wrapper.unmount()
  })

  it('checks a branch out through the daemon, refreshes the brief, and follows the files there', async () => {
    const { wrapper, live } = await workbench({
      at: `/flow/${FLOW}?branch=exp%2Flr-sweep`,
      handlers: {
        switch: () => ({
          flow: 'churn',
          path: FLOW,
          branch: 'exp/lr-sweep',
          checked_out: true,
          agent: 'claude-1',
          kernel: { state: 'stopped', restart_required: true, behind: ['pandas'] },
          settings: { reactivity: 'lazy', eager_cost_threshold_s: 30 },
          projected: { written: ['features', 'sweep_notes'], removed: [] },
        }),
      },
    })

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 18,
      transaction: transaction(18, {
        ts: '2999-08-13T09:18:00Z',
        intent: 'working on the checked-out lane',
        ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1' }],
      }),
    })
    await settle()

    expect(wrapper.findComponent(AgentTaskLine).text()).toContain('main')
    await clickText(wrapper, 'button[aria-label^="Open the lane map"]', '')
    await clickBranchVerb('exp/lr-sweep', 'use here')

    expect(asked(live, 'switch').map((params) => params.branch)).toEqual(['exp/lr-sweep'])
    expect(live.session.brief.value).toMatchObject({
      branch: 'exp/lr-sweep',
      agent: 'claude-1',
      kernel: { state: 'stopped', restart_required: true, behind: ['pandas'] },
      settings: { reactivity: 'lazy', eager_cost_threshold_s: 30 },
      cells: MAIN,
    })
    expect(window.location.search).not.toContain('branch=')
    expect(wrapper.get('[role="combobox"]').text()).toContain('on disk')
    expect(wrapper.find('[role="combobox"] .lucide-eye').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('viewing · the files stay on main')
    expect(wrapper.findComponent(AgentTaskLine).text()).toContain('exp/lr-sweep')
    await clickText(wrapper, 'button', 'Stop session')
    expect(document.body.textContent).toContain('cancelled the run on `exp/lr-sweep`')
    expect(drawn(wrapper)).toEqual(['features', 'sweep_notes'])
    wrapper.unmount()
  })

  it('lets a paired agent and a lane checkout coexist', async () => {
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

    expect(wrapper.text()).not.toContain('holds the files')
    await clickText(wrapper, 'button[aria-label^="Open the lane map"]', '')
    await clickBranchVerb('exp/lr-sweep', 'use here')

    expect(asked(live, 'switch')).toEqual([expect.objectContaining({ branch: 'exp/lr-sweep' })])
    expect(asked(live, 'switch')[0]).not.toHaveProperty('force')
    wrapper.unmount()
  })

  it('carries a 2–5 selection from the graph into the comparison link', async () => {
    const { wrapper, router } = await workbench()

    await clickText(wrapper, 'button[aria-label^="Open the lane map"]', '')
    // One at a time: each tick is a selection the list has to have applied
    // before the next reads it.
    for (const box of document.body.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')) {
      box.checked = true
      box.dispatchEvent(new Event('change', { bubbles: true }))
      await settle()
    }
    await clickInOverlay('Compare 2 lanes')

    // Branches by name, in the URL: a comparison is a link, not a visit.
    expect(router.currentRoute.value.path).toBe(`/flow/${FLOW}/compare`)
    expect(router.currentRoute.value.query.compare).toBe('main,exp/lr-sweep')
    wrapper.unmount()
  })

  it('hosts the restart banner over the packages the kernel is behind', async () => {
    const { wrapper } = await workbench({
      handlers: {
        'env.status': () => ({
          ...ENV,
          flows: [{ ...ENV.flows[0], restart_required: true, behind: ['lightgbm'] }],
        }),
      },
    })

    // The header flags the drift while the section is folded; the banner and
    // the packages it names live inside it.
    expect(wrapper.find('[aria-label="env mismatch"]').exists()).toBe(true)
    await openPanel(wrapper, 'packages')
    const panel = wrapper.text()
    expect(panel).toContain('restart kernel to apply')
    expect(panel).toContain('lightgbm')
    // Never a claim that anything was invalidated — nothing was.
    expect(panel).not.toContain('env mismatch')
    wrapper.unmount()
  })

  it('renders the flow settings the daemon reports, not a default it invented', async () => {
    const auto = await workbench()
    const toggle = auto.wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((header) => header.text() === 'settings')!
    expect(toggle.attributes('aria-expanded')).toBe('false')

    await toggle.trigger('click')
    await settle()
    expect(toggle.attributes('aria-expanded')).toBe('true')
    // The default: auto below a threshold, and the threshold is editable.
    const body = auto.wrapper.text()
    expect(body).toContain('auto below')
    expect(body).not.toContain('on env change')
    auto.wrapper.unmount()

    const { wrapper } = await workbench({
      handlers: {
        'flow.open': () =>
          flowStatus({
            cells: MAIN,
            settings: { reactivity: 'lazy', eager_cost_threshold_s: 30 },
          }),
      },
    })

    const lazyToggle = wrapper.findAll('button').find((button) => button.text() === 'settings')!
    await lazyToggle.trigger('click')
    const lazyBody = wrapper.find(`#${lazyToggle.attributes('aria-controls')}`)
    // Lazy marks and waits, so there is no threshold to show.
    expect(lazyBody.text()).not.toContain('auto below')
    expect(lazyBody.text()).toContain('nothing runs until you ask for it')
    wrapper.unmount()
  })

  it('carries the daemon’s reason for leaving a stale cell alone onto its card', async () => {
    // End to end through the live path: the threshold and the closure's cost
    // are the daemon's, and the card is not allowed a second opinion.
    const { wrapper } = await workbench({
      handlers: {
        'cells.list': () => ({
          flow: 'churn',
          branch: 'main',
          cells: MAIN.map((cell) =>
            cell.slug === 'features'
              ? {
                  ...cell,
                  auto_declined: {
                    reason: 'too-expensive' as const,
                    estimate_seconds: 615,
                    untimed: [],
                  },
                }
              : cell,
          ),
        }),
      },
    })

    expect(wrapper.text()).toContain('too expensive to refresh on its own')
    wrapper.unmount()
  })
})

describe('the session is a journal subscription', () => {
  it('re-reads the slice when a transaction lands and renders the new verdict', async () => {
    const { wrapper, live } = await workbench()

    SLICES.main = MAIN.map((cell) =>
      cell.slug === 'features'
        ? cellSummary('features', { ...cell, state: 'synced', causes: [] })
        : cell,
    )
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 15,
      transaction: transaction(15, { intent: 'ran features' }),
    })
    await settleJournal()

    expect(wrapper.text()).not.toContain('1 stale')
    await openPanel(wrapper, 'activity')
    expect(wrapper.text()).toContain('ran features')
    SLICES.main = MAIN
    wrapper.unmount()
  })

  /**
   * The restart banner is about drift, and drift is what moves after a tab
   * opens: an install raises it, and a kernel starting is what clears it. Read
   * off the brief — a snapshot of the moment the tab opened — the banner could
   * do neither, so it never appeared for this session's install and never went
   * away once the restart it asked for had happened.
   */
  it('takes the env drift from the daemon rather than the brief it opened with', async () => {
    const drifted = {
      ...ENV,
      flows: [{ ...ENV.flows[0], restart_required: true, behind: ['pandas'] }],
    }
    let env: typeof ENV = drifted
    const { wrapper, live } = await workbench({ handlers: { 'env.status': () => env } })

    // The brief says nothing is pending — it was true when the tab opened.
    expect(live.session.brief.value?.kernel.restart_required).toBe(false)
    await openPanel(wrapper, 'packages')
    expect(wrapper.text()).toContain('restart kernel to apply')
    expect(wrapper.text()).toContain('pandas')

    // The kernel restarts, which is what takes the new env; the daemon says so
    // both by announcing the process and by answering with no drift.
    env = ENV
    live.socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'kernel_state',
      step: 15,
      kernel: 'running',
    })
    await settle()

    expect(wrapper.text()).not.toContain('restart kernel to apply')
    wrapper.unmount()
  })

  it('flips to the paired agent the moment its registration arrives', async () => {
    const { wrapper, live } = await workbench()

    expect(wrapper.text()).toContain('not paired')
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 16,
      transaction: transaction(16, {
        actor: 'claude-1',
        intent: 'session start',
        ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1' }],
      }),
    })
    await settle()

    expect(wrapper.text()).not.toContain('not paired')
    expect(wrapper.text()).toContain('claude-1')
    wrapper.unmount()
  })

  it('keeps a reconnected replay of 150 transactions quiet', async () => {
    const { wrapper, live } = await workbench({ withToasts: true })

    live.socket.deliver({
      channel: 'journal',
      type: 'caught_up',
      flow: FLOW,
      step: 10,
      running: [],
    })
    live.socket.drop()
    live.reconnects[0]()
    const reopened = live.sockets[1]
    reopened.open()
    for (let step = 11; step <= 160; step += 1) {
      reopened.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step, { intent: 'agent worked while the tab slept' }),
      })
    }
    reopened.deliver({
      channel: 'journal',
      type: 'caught_up',
      flow: FLOW,
      step: 160,
      running: [],
    })
    await settle()

    expect(toasts()).toBe('')
    wrapper.unmount()
  })

  it('counts only stale cells changed before an agent session ended', async () => {
    const stale = [
      {
        ...cellSummary('score', {
          state: 'unsynced',
          causes: ['score changed'],
          created_step: 2,
        }),
        changed_step: 12,
      },
      {
        ...cellSummary('report', {
          state: 'unsynced',
          causes: ['report changed'],
          created_step: 4,
        }),
        changed_step: 16,
      },
    ]
    const { wrapper, live } = await workbench({
      handlers: {
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: stale,
        }),
      },
    })

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 14,
      transaction: transaction(14, {
        ops: [{ op: 'agent_end', actor: 'claude-1', label: 'claude-1' }],
      }),
    })
    await settleJournal()

    expect(wrapper.text()).toContain('agent session ended · 1 stale asset')

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 18,
      transaction: transaction(18, {
        ops: [{ op: 'agent_end', actor: 'claude-1', label: 'claude-1' }],
      }),
    })
    await settleJournal()

    expect(wrapper.text()).toContain('agent session ended · 2 stale assets')
    wrapper.unmount()
  })
})

describe('no internals reach the workbench', () => {
  it('addresses cells by slug and branches by name, and prints no key', async () => {
    const { wrapper } = await workbench()
    const text = wrapper.text()

    expect(text).not.toMatch(/\buid\b/i)
    expect(text).not.toMatch(/memo key/i)
    expect(text).not.toContain('branch-sweep')
    expect(text).not.toContain('def-hash')
    wrapper.unmount()
  })
})

/** The rendered card for one cell, or '' when the view is not drawing it. */
function cardFor(wrapper: VueWrapper, slug: string): string {
  const card = wrapper.findAll('article').find((node) => node.find('h3').text() === slug)
  return card?.text() ?? ''
}
