/**
 * Editing and running from the workbench.
 *
 * Three rules carry this suite. An edit carries the version it started from,
 * and a head that moved under it comes back as a choice — overwrite or fork —
 * with nothing written until the reader picks. A run states its closure
 * **before** the click and its stop states its scope after: leaving a run twenty
 * forks await is not cancelling it. And a failure's volume is **its author's**:
 * an agent iterating through a broken state is demoted to the card, a person's
 * failure is loud; both retain the card's one copy-context control.
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { Toast } from 'primevue'
import ToastService from 'primevue/toastservice'

import { FlowApiError } from '@/flow/api/client'
import type { CellDetail, CellSummary } from '@/flow/api/types'
import LiveCellCard from '@/flow/workbench/components/card/LiveCellCard.vue'
import LiveWorkbench from '@/flow/workbench/pages/LiveWorkbench.vue'
import {
  attach,
  cellDetail,
  cellSummary,
  flowStatus,
  FLOW,
  settle,
  storedPreview,
  transaction,
} from './fakes'
import type { Attached, Handlers } from './fakes'
import { editorIn } from './editor'

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
    cost_seconds: 312,
    created_step: 6,
  }),
]

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

function reads(overrides: Handlers = {}): Handlers {
  return {
    preflight: (params) => ({
      branch: String(params.branch),
      target: String(params.target ?? (params.targets as string[])?.join(', ')),
      cached: ['load_customers'],
      recompute: ['features'],
      unknown: [],
      estimate_seconds: 19,
    }),
    'cells.list': (params) => ({
      flow: 'churn',
      branch: String(params.branch),
      cells: SLICE,
    }),
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

// --- one card ----------------------------------------------------------------

interface Card {
  wrapper: VueWrapper
  live: Attached
}

async function card(
  options: { summary?: CellSummary; detail?: CellDetail; handlers?: Handlers } = {},
): Promise<Card> {
  const summary = options.summary ?? SLICE[0]
  const live = await attach({
    status: flowStatus({ cells: SLICE }),
    handlers: reads({
      'cells.show': () => options.detail ?? cellDetail('features', { ...summary, source: SOURCE }),
      ...options.handlers,
    }),
  })
  const wrapper = mount(LiveCellCard, {
    props: {
      session: live.session,
      stream: live.stream,
      branch: 'main',
      summary,
      density: 'canvas',
    },
  })
  await settle()
  return { wrapper, live }
}

async function clickText(wrapper: VueWrapper, label: string): Promise<void> {
  const button = wrapper.findAll('button').find((node) => node.text() === label)
  if (!button) throw new Error(`no button labelled "${label}" — saw ${labels(wrapper).join(', ')}`)
  await button.trigger('click')
  await settle()
}

function labels(wrapper: VueWrapper): string[] {
  return wrapper.findAll('button').map((node) => node.text())
}

/** Popovers, menus and dialogs are teleported: they land in the body, not in the wrapper. */
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

/**
 * Open the code tab and type new source into the editor it holds — one document
 * transaction, which is what any run of keystrokes amounts to.
 */
async function typeInto(wrapper: VueWrapper, source: string): Promise<void> {
  await wrapper
    .findAll('[role="tab"]')
    .find((tab) => tab.text() === 'code')
    ?.trigger('click')
  await settle()
  await clickText(wrapper, 'edit')
  const editor = await editorIn(wrapper)
  editor.view.dispatch({
    changes: { from: 0, to: editor.view.state.doc.length, insert: source },
  })
  await settle()
}

describe('an edit carries the version it started from', () => {
  it('sends the base hash and never prints it', async () => {
    const { wrapper, live } = await card()

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)
    await clickText(wrapper, 'save')

    const [edit] = asked(live, 'cells.edit')
    expect(edit.slug).toBe('features')
    expect(edit.base).toBe('def-hash')
    expect(edit.source).toContain('lr = 0.1')
    expect(labels(wrapper)).toContain('edit')
    expect(labels(wrapper)).not.toContain('save')
    // The base is a hash: it rides with the request and appears nowhere a
    // reader can see it.
    expect(wrapper.text()).not.toContain('def-hash')
    wrapper.unmount()
  })

  it('sends the version the editor opened on, not the one the head reached meanwhile', async () => {
    let served = 'def-hash'
    const { wrapper, live } = await card({
      handlers: {
        'cells.show': (params) =>
          cellDetail('features', {
            ...SLICE[0],
            source: SOURCE,
            branch: String(params.branch),
            definition_hash: served,
          }),
      },
    })

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)

    // The agent commits its own edit to this cell while the reader is typing.
    // The card re-reads the cell, so the head it now holds is the very version
    // the reader's edit was *not* written against.
    served = 'def-hash-2'
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: `${FLOW}`,
      step: 50,
      transaction: transaction(50, { actor: 'claude-1', intent: 'edited features' }),
    })
    await settle()

    await clickText(wrapper, 'save')

    // Sending the moved head would sail past the daemon's check and overwrite
    // the agent silently — the conflict exists precisely to be raised here.
    expect(asked(live, 'cells.edit')[0].base).toBe('def-hash')
    wrapper.unmount()
  })

  it('offers overwrite or fork when the head moved, and writes neither until told', async () => {
    const { wrapper, live } = await card({
      handlers: {
        'cells.edit': () => {
          throw new FlowApiError(
            '`features` has moved on since this edit started — overwrite it, ' +
              'or fork the edit onto a branch of your own',
            { kind: 'EditConflict', status: 409 },
          )
        },
      },
    })

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)
    await clickText(wrapper, 'save')

    expect(wrapper.text()).toContain('your edit is based on an older version')
    expect(labels(wrapper)).toContain('save to a new lane')
    // One attempt, refused. Nothing was written while the menu is up.
    expect(asked(live, 'cells.edit')).toHaveLength(1)
    wrapper.unmount()
  })

  it('overwrites only when that is the side picked, and says it is forcing', async () => {
    let refuse = true
    const { wrapper, live } = await card({
      handlers: {
        'cells.edit': () => {
          if (refuse) {
            refuse = false
            throw new FlowApiError('`features` has moved on since this edit started', {
              kind: 'EditConflict',
              status: 409,
            })
          }
          return {
            slug: 'features',
            branch: 'main',
            definition_hash: 'def-hash-2',
            written_to_files: true,
            flags: [],
          }
        },
      },
    })

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)
    await clickText(wrapper, 'save')
    await clickText(wrapper, 'overwrite')

    const attempts = asked(live, 'cells.edit')
    expect(attempts).toHaveLength(2)
    expect(attempts[1].force).toBe(true)
    // The draft survived the refusal — the second attempt is the same edit.
    expect(attempts[1].source).toContain('lr = 0.1')
    expect(attempts[1].intent).toBe('overwrote features')
    expect(wrapper.text()).not.toContain('your edit is based on an older version')
    wrapper.unmount()
  })

  it('opens the named-lane dialog when the reader forks instead of overwriting', async () => {
    const { wrapper, live } = await card({
      handlers: {
        'cells.edit': () => {
          throw new FlowApiError('`features` has moved on since this edit started', {
            kind: 'EditConflict',
            status: 409,
          })
        },
      },
    })

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)
    await clickText(wrapper, 'save')
    await clickText(wrapper, 'save to a new lane')

    const name = document.body.querySelector<HTMLInputElement>('input[aria-label="lane name"]')
    expect(name?.value).toBe('features-edit')
    expect((await editorIn(wrapper)).view.state.doc.toString()).toContain('lr = 0.1')
    expect(asked(live, 'cells.edit')).toHaveLength(1)
    wrapper.unmount()
  })

  it('leaves the unresolved edit behind on the branch it was typed against', async () => {
    const { wrapper, live } = await card({
      handlers: {
        'cells.edit': () => {
          throw new FlowApiError('`features` has moved on since this edit started', {
            kind: 'EditConflict',
            status: 409,
          })
        },
      },
    })

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)
    await clickText(wrapper, 'save')
    expect(labels(wrapper)).toContain('overwrite')

    // Viewing another branch is free and reuses this card. Carrying the menu
    // across would offer to force-write main's draft onto a branch nobody
    // edited, with the conflict check turned off.
    await wrapper.setProps({ branch: 'exp/lr-sweep' })
    await settle()

    expect(labels(wrapper)).not.toContain('overwrite')
    expect(wrapper.text()).not.toContain('your edit is based on an older version')
    expect(asked(live, 'cells.edit')).toHaveLength(1)
    wrapper.unmount()
  })

  it('keeps the draft when the fork the reader picked is refused', async () => {
    const { wrapper } = await card({
      handlers: {
        'cells.edit': () => {
          throw new FlowApiError('`features` has moved on since this edit started', {
            kind: 'EditConflict',
            status: 409,
          })
        },
      },
    })

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)
    await clickText(wrapper, 'save')
    await clickText(wrapper, 'save to a new lane')

    // The page owns forking and may be refused — the branch name may already be
    // taken. Until it reports back, the menu the draft was typed under stays up,
    // so overwrite is still on offer and nothing typed is lost.
    expect(wrapper.text()).toContain('your edit is based on an older version')
    expect(labels(wrapper)).toContain('overwrite')
    wrapper.unmount()
  })

  it('does not render a deferred-file state after an edit lands', async () => {
    const { wrapper } = await card({
      handlers: {
        'cells.edit': () => ({
          slug: 'features',
          branch: 'main',
          definition_hash: 'def-hash-2',
          written_to_files: false,
          flags: [],
        }),
      },
    })

    await typeInto(wrapper, `${SOURCE}    lr = 0.1\n`)
    await clickText(wrapper, 'save')

    expect(wrapper.text()).not.toContain('not yet written to files')
    wrapper.unmount()
  })

  it('offers the daemon’s suggestion as the repair, spelled the way it resolves', async () => {
    const flagged = cellSummary('features', {
      outputs: ['train_split'],
      primary: 'train_split',
      consumes: { rows: 'load_dat.rows' },
      flags: [
        {
          code: 'dangling_ref',
          detail: 'unknown reference `load_dat.rows`. did you mean `load_data.rows`?',
        },
      ],
    })
    const { wrapper, live } = await card({
      summary: flagged,
      detail: cellDetail('features', {
        ...flagged,
        source: 'class Features:\n    consumes = {"rows": "load_dat.rows"}\n',
      }),
      handlers: {
        'cells.edit': () => ({
          slug: 'features',
          branch: 'main',
          definition_hash: 'def-hash-2',
          written_to_files: true,
          flags: [],
        }),
      },
    })

    expect(wrapper.text()).toContain('did you mean')
    await clickText(wrapper, 'apply suggestion')

    const [edit] = asked(live, 'cells.edit')
    expect(edit.source).toContain('load_data.rows')
    wrapper.unmount()
  })
})

describe('a run states its closure before the click', () => {
  it('asks the daemon for the closure when the popover opens, not on render', async () => {
    const { wrapper, live } = await card()

    // Twenty cards preflighting themselves on render is twenty plans nobody
    // asked for.
    expect(asked(live, 'preflight')).toHaveLength(0)

    const run = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()

    expect(asked(live, 'preflight')).toEqual([{ flow: FLOW, branch: 'main', target: 'features' }])
    // What is cached, what recomputes, and the total — before the click.
    expect(overlays()).toContain('load_customers')
    expect(overlays()).toContain('19')
    wrapper.unmount()
  })

  it('explains why a current producer has to run again', async () => {
    const { wrapper } = await card({
      handlers: {
        preflight: (params) => ({
          branch: String(params.branch),
          target: String(params.target),
          cached: [],
          recompute: ['evaluate', 'features'],
          unknown: [],
          estimate_seconds: 20,
          reasons: [
            '`evaluate` must run because its removed experiment `exp-1` is needed.',
          ],
        }),
      },
    })

    const run = wrapper
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()

    expect(overlays()).toContain('evaluate')
    expect(overlays()).toContain('removed experiment `exp-1`')
    wrapper.unmount()
  })

  it('turns memo hits back on for every run that did not ask to ignore them', async () => {
    const { wrapper, live } = await workbench()

    const run = cardFor(wrapper, 'features')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()
    await clickInBody('run 1 cell')

    // Force is a modifier the reader reaches for, never where the button starts:
    // a run that silently ignored the cache would recompute an afternoon.
    expect(asked(live, 'run')[0]).toMatchObject({ target: 'features', intent: 'run features' })
    expect(asked(live, 'run')[0].force).toBeFalsy()
    wrapper.unmount()
  })

  it('ignores the cache only when the modifier is ticked, and says that is what it did', async () => {
    const { wrapper, live } = await workbench()

    const run = cardFor(wrapper, 'features')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()

    const force = document.body.querySelector('input[type="checkbox"]') as HTMLInputElement
    force.click()
    await settle()

    // What was cached is now counted in, and the total is open-ended: a memo
    // hit's cost was never recorded, so it cannot be added up.
    await clickInBody('run 2 cells')

    expect(asked(live, 'run')[0]).toMatchObject({
      target: 'features',
      force: true,
      intent: 'force rerun features',
    })
    wrapper.unmount()
  })

  it('drops a closure the branch moved out from under while it was being costed', async () => {
    let commit: (() => void) | null = null
    const { wrapper, live } = await card({
      handlers: {
        preflight: (params) => {
          // The agent lands its own transaction while the daemon is still
          // costing this plan, so the answer describes a head that is gone.
          commit?.()
          return {
            branch: String(params.branch),
            target: String(params.target),
            cached: ['load_customers'],
            recompute: ['features'],
            unknown: [],
            estimate_seconds: 19,
          }
        },
      },
    })
    commit = () =>
      live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: `${FLOW}`,
        step: 60,
        transaction: transaction(60, { actor: 'claude-1' }),
      })

    const run = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()

    // Back to asking. A stale total under the run button is worse than none:
    // it is a number the reader would act on and the daemon never stood behind.
    expect(overlays()).toContain('estimating…')
    wrapper.unmount()
  })

  it('never fabricates a closure while the daemon is still working one out', async () => {
    const { wrapper } = await card({
      handlers: {
        preflight: () => {
          throw new FlowApiError('no cell named features on main', {
            kind: 'CellNotFound',
            status: 404,
          })
        },
      },
    })

    const run = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()

    expect(overlays()).toContain('estimating…')
    wrapper.unmount()
  })
})

// --- the whole screen ---------------------------------------------------------

const Empty = defineComponent({ template: '<div />' })

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/flow/:flowId', component: Empty },
      { path: '/:pathMatch(.*)*', component: Empty },
    ],
  })
}

interface Bench {
  wrapper: VueWrapper
  live: Attached
}

async function workbench(options: { handlers?: Handlers; notebook?: boolean } = {}): Promise<Bench> {
  const live = await attach({
    status: flowStatus({ cells: SLICE }),
    handlers: reads({
      tree: () => ({ flow: 'churn', branch: 'main', branches: [] }),
      'env.status': () => ({
        workspace: '/tmp/project',
        python: { path: '/tmp/project/.venv/bin/python', source: 'venv' },
        packages: [],
        flows: [],
      }),
      ...options.handlers,
    }),
  })
  const router = testRouter()
  await router.push(`/flow/${FLOW}${options.notebook ? '?view=notebook' : ''}`)
  await router.isReady()
  // The app shell owns the toast outlet; a workbench mounted without one would
  // let every acknowledgement assertion pass by finding nothing.
  const host = defineComponent({
    components: { LiveWorkbench, Toast },
    props: { session: { type: Object, required: true }, stream: { type: Object, required: true } },
    template: '<div><Toast /><LiveWorkbench :session="session" :stream="stream" /></div>',
  })
  const wrapper = mount(host, {
    props: { session: live.session, stream: live.stream },
    global: { plugins: [router, ToastService] },
  })
  // Subscribing replays the journal and then says so, exactly as the daemon
  // does. Everything delivered after this is news; the replay before it is not.
  live.socket.deliver({
    channel: 'journal',
    type: 'caught_up',
    flow: `${FLOW}`,
    step: 10,
    running: [],
  })
  await settle()
  return { wrapper, live }
}

function cardFor(wrapper: VueWrapper, slug: string): VueWrapper {
  const card = wrapper
    .findAll('article')
    .find((node) => node.find('h3').text() === slug) as unknown as VueWrapper
  if (!card) throw new Error(`no card for ${slug}`)
  return card
}

/** Toasts render into the outlet the host mounts, which sits in the body. */
function toasts(): string {
  return Array.from(document.body.querySelectorAll('.p-toast-message'))
    .map((node) => node.textContent ?? '')
    .join(' ')
}

describe('rerunning a lane is one daemon request', () => {
  it('asks run for the viewed lane without sending client-derived leaves', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        run: (params) => ({
          branch: String(params.branch),
          target: 'train_model',
          targets: ['train_model'],
          executed: ['features', 'train_model'],
          cached: [],
          pruned: [],
          failed: null,
          failures: [],
          unplanned: [],
          abandoned: false,
        }),
      },
    })

    await clickText(wrapper, 'Rerun lane')
    await clickInBody('run 1 cell')

    expect(asked(live, 'run')).toEqual([
      {
        flow: FLOW,
        branch: 'main',
        force: false,
        intent: 'rerun main',
      },
    ])
    wrapper.unmount()
  })
})

describe('stop is honest about what it stopped', () => {
  async function running(awaiting: number): Promise<Bench> {
    const bench = await workbench({
      handlers: {
        cancel: (params) => ({
          branch: String(params.branch),
          left: 1,
          stopped: awaiting === 1,
          awaiting: awaiting - 1,
        }),
      },
    })
    bench.live.socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: `${FLOW}`,
      event: 'started',
      step: 20,
      run_id: 'run-1',
      slug: 'train_model',
      awaiting,
    })
    await settle()
    return bench
  }

  it('words the button as leaving when other branches still await the run', async () => {
    const { wrapper } = await running(3)

    const stop = cardFor(wrapper, 'train_model')
      .findAll('button')
      .find((node) => node.attributes('aria-label')?.startsWith('leave the run'))

    expect(stop?.attributes('aria-label')).toContain('2 other lanes still wait for it')
    wrapper.unmount()
  })

  it('words it as stopping when this branch is the only one waiting', async () => {
    const { wrapper } = await running(1)

    const labelled = cardFor(wrapper, 'train_model')
      .findAll('button')
      .map((node) => node.attributes('aria-label'))

    expect(labelled).toContain('stop the run')
    wrapper.unmount()
  })

  it('reports what leaving actually did rather than claiming a cancellation', async () => {
    const { wrapper, live } = await running(3)

    const stop = cardFor(wrapper, 'train_model')
      .findAll('button')
      .find((node) => node.attributes('aria-label')?.startsWith('leave the run'))
    await stop!.trigger('click')
    await settle()

    expect(asked(live, 'cancel')).toHaveLength(1)
    expect(toasts()).toContain('it keeps going for 2 other lanes')
    wrapper.unmount()
  })

  it('hands the agent a sentence to read, not a command this side does not have', async () => {
    const { wrapper } = await running(1)

    await clickText(wrapper, 'Stop session')

    // The daemon's half is the queue; the agent runs in the user's own terminal.
    expect(overlays()).toContain('cancels the run and drains the queue')
    expect(overlays()).toContain('cancelled the run on `main`. Stop working on it and move on')
    // Nothing offered here is typed at a shell: `lumlflow agent` has begin, end
    // and exec, so a copyable verb beside them would be one that errors out.
    expect(overlays()).not.toContain('lumlflow agent prompt')
    wrapper.unmount()
  })
})

describe('a failure’s volume is its author’s', () => {
  function failed(actor: string, step = 30) {
    return transaction(step, {
      actor,
      intent: `${actor} ran train_model`,
      ops: [
        {
          op: 'run_recorded',
          mat_id: 'm1',
          uid: 'u1',
          version_id: 'v1',
          branch_id: 'branch-main',
          memo_key: 'k',
          state: 'failed',
          inputs: {},
          outputs: {},
          identity_dependent: false,
          external: false,
          env_lock_hash: null,
          cost_seconds: 2,
          log_ref: 'l1',
          started_step: 29,
          finished_step: 30,
        },
      ],
    })
  }

  it('does not interrupt for an agent’s failure', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: `${FLOW}`,
      step: 30,
      transaction: failed('claude-1'),
    })
    await settle()

    expect(toasts()).not.toContain('Run failed')
    wrapper.unmount()
  })

  it('does not greet a reopened workbench with yesterday’s failures', async () => {
    const live = await attach({
      status: flowStatus({ cells: SLICE }),
      handlers: reads({
        tree: () => ({ flow: 'churn', branch: 'main', branches: [] }),
        'env.status': () => ({
          workspace: '/tmp/project',
          python: { path: '/tmp/project/.venv/bin/python', source: 'venv' },
          packages: [],
          flows: [],
        }),
      }),
    })
    const router = testRouter()
    await router.push(`/flow/${FLOW}`)
    await router.isReady()
    const host = defineComponent({
      components: { LiveWorkbench, Toast },
      props: {
        session: { type: Object, required: true },
        stream: { type: Object, required: true },
      },
      template: '<div><Toast /><LiveWorkbench :session="session" :stream="stream" /></div>',
    })
    const wrapper = mount(host, {
      props: { session: live.session, stream: live.stream },
      global: { plugins: [router, ToastService] },
    })

    // Subscribing replays the journal from the client's cursor — the whole of
    // it on a first load — and only then reports the catch-up.
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: `${FLOW}`,
      step: 8,
      transaction: failed('user', 8),
    })
    live.socket.deliver({
      channel: 'journal',
      type: 'caught_up',
      flow: `${FLOW}`,
      step: 8,
      running: [],
    })
    await settle()

    // The replayed window is what the catch-up marker counts, not an inbox.
    expect(toasts()).not.toContain('Run failed')

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: `${FLOW}`,
      step: 30,
      transaction: failed('user'),
    })
    await settle()

    expect(toasts()).toContain('Run failed')
    wrapper.unmount()
  })

  it('says so for the user’s own', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: `${FLOW}`,
      step: 30,
      transaction: failed('user'),
    })
    await settle()

    expect(toasts()).toContain('Run failed')
    wrapper.unmount()
  })

  it('gives every failed cell the same single copy-context control', async () => {
    const broken = (author: string) =>
      cellDetail('features', {
        ...SLICE[0],
        state: 'failed',
        source: SOURCE,
        error: 'Traceback (most recent call last):\nValueError: threshold must be in (0, 1)',
        failed_by: author,
      })

    const mine = await card({
      summary: { ...SLICE[0], state: 'failed' },
      detail: broken('user'),
    })
    expect(mine.wrapper.text()).toContain('ValueError')
    expect(mine.wrapper.findAll('button[aria-label="copy context"]')).toHaveLength(1)
    mine.wrapper.unmount()

    const theirs = await card({
      summary: { ...SLICE[0], state: 'failed' },
      detail: broken('claude-1'),
    })
    expect(theirs.wrapper.findAll('button[aria-label="copy context"]')).toHaveLength(1)
    theirs.wrapper.unmount()
  })

  it('folds the attempts a session watched fail into the provenance line', async () => {
    const { wrapper, live } = await card({
      summary: { ...SLICE[0], state: 'failed' },
      detail: cellDetail('features', {
        ...SLICE[0],
        state: 'failed',
        source: SOURCE,
        error: "KeyError: 'p_churn'",
        failed_by: 'claude-1',
      }),
    })

    for (const run of ['run-1', 'run-2']) {
      live.socket.deliver({
        channel: 'journal',
        type: 'kernel',
        flow: `${FLOW}`,
        event: 'failed',
        step: 31,
        run_id: run,
        slug: 'features',
        state: 'failed',
      })
    }
    await settle()

    // The count is the glance; what it is a count of rides in the hover title,
    // beside the authorship the signature no longer spells out.
    expect(wrapper.text()).toContain('2 failed')
    const signature = wrapper
      .findAll('[title]')
      .map((node) => node.attributes('title') ?? '')
      .find((title) => title.includes('step '))
    expect(signature).toContain('created ')
    expect(signature).toContain('last edit ')
    expect(signature).toContain('2 failed attempts folded in')
    wrapper.unmount()
  })
})

describe('an agent session that ended leaving something outstanding', () => {
  it('says so under the cell it is about, and never diagnoses why it stopped', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: [{ ...SLICE[0], state: 'failed' as const }, SLICE[1]],
        }),
      },
    })

    for (const [step, op] of [
      [40, { op: 'agent_begin' as const, actor: 'claude-1', label: 'claude-1' }],
      [41, { op: 'agent_end' as const, actor: 'claude-1', label: 'claude-1' }],
    ] as const) {
      live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: `${FLOW}`,
        step,
        transaction: transaction(step, { actor: 'claude-1', ops: [op] }),
      })
    }
    await settle()

    const banner = wrapper.text()
    expect(banner).toContain('agent session ended')
    // A state, not a toast — and honest: a clean end and a killed process look
    // the same from here, so it says what is outstanding rather than why.
    expect(banner).toContain('a failed run on')
    expect(banner).not.toContain('crashed')
    expect(toasts()).not.toContain('the agent session ended')
    wrapper.unmount()
  })

  it('raises nothing when the session ended with the branch in order', async () => {
    const { wrapper, live } = await workbench()

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: `${FLOW}`,
      step: 41,
      transaction: transaction(41, {
        actor: 'claude-1',
        ops: [{ op: 'agent_end', actor: 'claude-1', label: 'claude-1' }],
      }),
    })
    await settle()

    expect(wrapper.text()).not.toContain('the agent session ended')
    wrapper.unmount()
  })
})

describe('a rename is one identity keeping its name history', () => {
  it('carries the old name on the card rather than reading as a new cell', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: [{ ...SLICE[0], slug: 'engineered' }, SLICE[1]],
        }),
      },
    })

    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: `${FLOW}`,
      step: 42,
      transaction: transaction(42, {
        ops: [
          {
            op: 'renamed',
            uid: 'u1',
            branch_id: 'branch-main',
            old_slug: 'features',
            new_slug: 'engineered',
          },
        ],
      }),
    })
    await settle()

    expect(cardFor(wrapper, 'engineered').text()).toContain('renamed from')
    expect(cardFor(wrapper, 'engineered').text()).toContain('features')
    wrapper.unmount()
  })
})

describe('the kernel dying is a banner, not a traceback', () => {
  it('names the cell that was materializing and offers the restart', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        run: () => {
          throw new FlowApiError('the kernel stopped while `features` was running — killed', {
            kind: 'KernelError',
            status: 500,
          })
        },
        'kernel.restart': () => ({
          flow: 'churn',
          kernel: { state: 'running', restart_required: false, behind: [] },
        }),
      },
    })

    const run = cardFor(wrapper, 'features')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()
    await clickInBody('run 1 cell')

    expect(wrapper.text()).toContain('the kernel died')
    expect(wrapper.text()).toContain('features')
    // Nothing recorded is lost — and the restart is one click, not a refresh.
    await clickText(wrapper, 'restart kernel')
    expect(asked(live, 'kernel.restart')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('the kernel died')
    wrapper.unmount()
  })
})

describe('an unexpected HTTP failure stays actionable', () => {
  it('shows the daemon’s message in the workbench', async () => {
    const { wrapper } = await workbench({
      handlers: {
        run: () => {
          throw new FlowApiError('the store failed', { status: 500 })
        },
      },
    })

    const run = cardFor(wrapper, 'features')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'run')
    await run!.trigger('click')
    await settle()
    await clickInBody('run 1 cell')

    expect(toasts()).toContain('the store failed')
    wrapper.unmount()
  })
})

describe('adding, renaming and deleting a cell', () => {
  it('anchors a downstream add on the card the gesture came from', async () => {
    const { wrapper, live } = await workbench({
      notebook: true,
      handlers: {
        'cells.new': (params) => ({
          slug: 'untitled_1',
          branch: String(params.branch),
          definition_hash: 'def-new',
          written_to_files: true,
          flags: [{ code: 'placeholder_slug', detail: 'name it' }],
        }),
      },
    })

    const more = cardFor(wrapper, 'features')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'more')
    await more!.trigger('click')
    await settle()
    await clickInBody('add cell downstream')

    expect(asked(live, 'cells.new')).toEqual([
      expect.objectContaining({
        after: 'features',
        anchor: 'features',
        intent: 'added a cell downstream of features',
      }),
    ])
    wrapper.unmount()
  })

  it('anchors a blank add on the selected cell', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'cells.new': (params) => ({
          slug: 'untitled_1',
          branch: String(params.branch),
          definition_hash: 'def-new',
          written_to_files: true,
          flags: [{ code: 'placeholder_slug', detail: 'name it' }],
        }),
      },
    })

    await cardFor(wrapper, 'features').trigger('click')
    await settle()
    await clickText(wrapper, 'add a cell')

    expect(asked(live, 'cells.new')).toHaveLength(1)
    expect(asked(live, 'cells.new')[0].intent).toBe('added a cell')
    expect(asked(live, 'cells.new')[0].anchor).toBe('features')
    expect(toasts()).toContain('Added untitled_1')
    wrapper.unmount()
  })

  it('moves a legal neighbour and applies the reply before any journal change', async () => {
    const orderedSlice = [
      cellSummary('features', { created_step: 4, order: '4' }),
      cellSummary('notes', {
        note: true,
        outputs: [],
        kinds: {},
        primary: null,
        created_step: 5,
        order: '5',
      }),
      cellSummary('train_model', {
        consumes: { train: 'features.train_split' },
        created_step: 6,
        order: '6',
      }),
    ]
    const { wrapper, live } = await workbench({
      notebook: true,
      handlers: {
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: orderedSlice,
        }),
        'cells.reorder': (params) => ({
          slug: String(params.slug),
          uid: 'uid-notes',
          branch: String(params.branch),
          order: '7',
        }),
      },
    })

    const more = cardFor(wrapper, 'notes')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'more')
    await more!.trigger('click')
    await settle()
    await clickInBody('move down')

    expect(asked(live, 'cells.reorder')).toEqual([
      expect.objectContaining({ slug: 'notes', branch: 'main', after: 'train_model' }),
    ])
    expect(wrapper.findAll('article').map((card) => card.find('h3').text())).toEqual([
      'features',
      'train_model',
      'notes',
    ])
    expect(live.session.head.value).toBe(10)
    wrapper.unmount()
  })

  it('disables moving a consumer above its producer', async () => {
    const { wrapper, live } = await workbench({ notebook: true })
    const more = cardFor(wrapper, 'train_model')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'more')
    await more!.trigger('click')
    await settle()

    const moveUp = Array.from(document.body.querySelectorAll('[role="menuitem"]')).find(
      (node) => node.textContent?.trim() === 'move up',
    )
    expect(moveUp?.getAttribute('aria-disabled')).toBe('true')
    ;(moveUp as HTMLElement).click()
    await settle()
    expect(asked(live, 'cells.reorder')).toEqual([])
    wrapper.unmount()
  })

  it('renames through the daemon and names what was rewired', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        rename: (params) => ({
          slug: String(params.to),
          renamed_from: String(params.slug),
          branch: String(params.branch),
          rewired: ['train_model'],
          projected: { written: ['cells/train_split.py'], removed: ['cells/features.py'] },
        }),
      },
    })

    // The menu is where rename lives; the dialog is what collects the name.
    const more = cardFor(wrapper, 'features')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'more')
    await more!.trigger('click')
    await settle()
    await clickInBody('rename')

    const field = document.body.querySelector('input[aria-label="new name"]') as HTMLInputElement
    field.value = 'engineered'
    field.dispatchEvent(new Event('input'))
    await settle()
    await clickInBody('rename')

    expect(asked(live, 'rename')[0]).toMatchObject({ slug: 'features', to: 'engineered' })
    expect(toasts()).toContain('train_model rewired')
    wrapper.unmount()
  })

  it('duplicates the body and says the copy keeps the original inputs', async () => {
    const { wrapper, live } = await workbench({
      handlers: {
        'cells.new': (params) => ({
          slug: String(params.slug),
          branch: String(params.branch),
          definition_hash: 'def-copy',
          written_to_files: true,
          flags: [],
        }),
      },
    })

    const more = cardFor(wrapper, 'features')
      .findAll('button')
      .find((node) => node.attributes('aria-label') === 'more')
    await more!.trigger('click')
    await settle()
    await clickInBody('duplicate')

    // The slice a card lays out from carries no source, so a duplicate that
    // read one off it would scaffold an empty cell under a name promising a copy.
    const [added] = asked(live, 'cells.new')
    expect(added.slug).toBe('features_copy')
    expect(added.source).toBe(SOURCE)
    expect(added.intent).toBe('duplicated a cell as features_copy')
    expect(toasts()).toContain("keeps the original's inputs")
    wrapper.unmount()
  })

  it('opts one asset out of the cost threshold without journalling an intent', async () => {
    const { wrapper, live } = await card({
      handlers: {
        'cells.eager': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          slug: String(params.slug),
          eager: params.eager as boolean,
        }),
      },
    })

    const more = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'more')
    await more!.trigger('click')
    await settle()
    await clickInBody('eager materialization')

    // Reactivity, not a run: nothing is materialized by ticking it, and the
    // journal records no transaction for a setting.
    const [set] = asked(live, 'cells.eager')
    expect(set).toMatchObject({ slug: 'features', branch: 'main', eager: true })
    expect(set.intent).toBeUndefined()
    expect(wrapper.text()).toContain('rematerializes on change whatever it costs')
    wrapper.unmount()
  })

  it('deletes from this branch only, and names the consumers left pointing at nothing', async () => {
    const { wrapper, live } = await card({
      handlers: {
        'cells.delete': (params) => ({
          slug: String(params.slug),
          branch: String(params.branch),
          dangling: ['train_model'],
          projected: null,
        }),
      },
    })

    const more = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'more')
    await more!.trigger('click')
    await settle()
    const item = Array.from(document.body.querySelectorAll('.p-menu-item-link')).find((node) =>
      node.textContent?.includes('delete from this lane'),
    )
    ;(item as HTMLElement).click()
    await settle()

    // The confirm names the branch and says the others keep it.
    const confirm = Array.from(document.body.querySelectorAll('button')).find(
      (node) => node.textContent?.trim() === 'delete from this lane',
    )
    expect(document.body.textContent).toContain('other lanes keep it')
    confirm!.click()
    await settle()

    expect(asked(live, 'cells.delete')[0]).toMatchObject({ slug: 'features', branch: 'main' })
    expect(asked(live, 'cells.delete')[0].intent).toBe('deleted features from main')
    expect(wrapper.text()).toContain('train_model now point at nothing on main')
    wrapper.unmount()
  })
})
