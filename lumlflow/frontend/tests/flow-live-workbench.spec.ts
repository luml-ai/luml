/**
 * The two views and the left panel, on a live session.
 *
 * Three rules carry this suite. Staleness leads with the **direct cause** —
 * what is not current in its own right, named in words — while what merely sits
 * below it stays counted and one toggle away, and `unmaterialized` is neither
 * of those: no baseline exists to claim a change against. The canvas and the
 * notebook are **two densities over one slice**, so a cell on one is a cell on
 * the other and the notebook's column is pinned by mint order rather than by
 * name. And viewing another branch **re-scopes the whole screen** — panel,
 * views and URL — as the pure store read it is, with nothing checked out.
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ToastService from 'primevue/toastservice'

import type { EnvReport } from '@/flow/api/client'
import type { BranchRecord, CellSummary } from '@/flow/api/types'
import LiveWorkbench from '@/flow/workbench/pages/LiveWorkbench.vue'
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

// A churn flow, as the daemon reports it. `features` is not current in its own
// right; `train_model` is current and sits under it; `holdout_eval` has never
// run anywhere. `alpha_scan` is a second root written last — its name sorts it
// first and its mint step does not.
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
    archived: false,
    checked_out: true,
    cells: MAIN.length,
    states: { synced: 3, unsynced: 1, unmaterialized: 1 },
    checkpoint: 6,
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
    archived: false,
    checked_out: false,
    cells: SWEEP.length,
    states: { synced: 2 },
    checkpoint: 10,
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
      policy: 'ask',
      restart_required: false,
      behind: [],
    },
  ],
}

interface Bench {
  wrapper: VueWrapper
  live: Attached
  router: Router
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

async function workbench(
  options: { handlers?: Handlers; at?: string; branch?: string } = {},
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
      set_focus: (params) => ({
        flow: 'churn',
        branch: String(params.branch ?? 'main'),
        asset: (params.asset as string | null) ?? null,
        compare: (params.compare as string[]) ?? [],
      }),
      ...options.handlers,
    },
  })
  const router = testRouter()
  await router.push(options.at ?? `/flow/${FLOW}`)
  await router.isReady()
  const wrapper = mount(LiveWorkbench, {
    props: { session: live.session, stream: live.stream },
    global: { plugins: [router, ToastService] },
  })
  await settle()
  return { wrapper, live, router }
}

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

/** The slugs on screen, in the order the view drew them. */
function drawn(wrapper: VueWrapper): string[] {
  return wrapper.findAll('article h3').map((heading) => heading.text())
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

describe('canvas and notebook are two densities over one slice', () => {
  it('draws the same cells either way, in mint order down the notebook', async () => {
    const { wrapper } = await workbench()

    const canvas = drawn(wrapper)
    expect(new Set(canvas)).toEqual(new Set(MAIN.map((cell) => cell.slug)))

    const notebook = await workbench({ at: `/flow/${FLOW}?view=notebook` })
    const column = drawn(notebook.wrapper)
    expect(new Set(column)).toEqual(new Set(canvas))
    // Topological: a producer is above its consumer.
    expect(column.indexOf('features')).toBeLessThan(column.indexOf('train_model'))
    expect(column.indexOf('train_model')).toBeLessThan(column.indexOf('holdout_eval'))
    // Ties break on the mint step, so the cell written last stays last — the
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

  it('checks a branch out through the daemon, and follows the files there', async () => {
    const { wrapper, live } = await workbench()

    await clickText(wrapper, 'button[aria-label^="Open the lane map"]', '')
    await clickBranchVerb('exp/lr-sweep', 'use here')

    expect(asked(live, 'switch').map((params) => params.branch)).toEqual(['exp/lr-sweep'])
    expect(drawn(wrapper)).toEqual(['features', 'sweep_notes'])
    wrapper.unmount()
  })

  it('waits on the agent for the files, and forces only when told to', async () => {
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

    // The notice states the reason rather than leaving a dead button.
    expect(wrapper.text()).toContain('claude-1 holds the files')
    await clickText(wrapper, 'button[aria-label^="Open the lane map"]', '')
    await clickBranchVerb('exp/lr-sweep', 'force')

    expect(asked(live, 'switch')).toEqual([
      expect.objectContaining({ branch: 'exp/lr-sweep', force: true }),
    ])
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
    // A per-flow policy is set once and read back rarely: it is folded away
    // until someone asks for it, and asking is one click with a name on it.
    const toggle = auto.wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((header) => header.text() === 'settings')!
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(auto.wrapper.text()).not.toContain('ask to restart')

    await toggle.trigger('click')
    await settle()
    expect(toggle.attributes('aria-expanded')).toBe('true')
    // The default: auto below a threshold, and the threshold is editable.
    const body = auto.wrapper.text()
    expect(body).toContain('auto below')
    expect(body).toContain('ask to restart')
    auto.wrapper.unmount()

    const { wrapper } = await workbench({
      handlers: {
        'flow.open': () =>
          flowStatus({
            cells: MAIN,
            settings: { reactivity: 'lazy', eager_cost_threshold_s: 30, env_policy: 'never' },
          }),
      },
    })

    const lazyToggle = wrapper.findAll('button').find((button) => button.text() === 'settings')!
    await lazyToggle.trigger('click')
    const lazyBody = wrapper.find(`#${lazyToggle.attributes('aria-controls')}`)
    // Lazy marks and waits, so there is no threshold to show.
    expect(lazyBody.text()).not.toContain('auto below')
    expect(lazyBody.text()).toContain('nothing runs until you ask for it')
    expect(lazyBody.text()).toContain('never')
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
        ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1', worktree: true }],
      }),
    })
    await settle()

    expect(wrapper.text()).not.toContain('not paired')
    expect(wrapper.text()).toContain('claude-1')
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
