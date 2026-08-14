/**
 * The launch surface and the pairing door.
 *
 * Two rules are load-bearing here and both are asserted rather than described.
 * A flow is a **document**: the browser lists it as one entry, opens it, and
 * offers no way to walk into its cells or its store — the daemon refuses such a
 * listing, and this asserts the client never asks for one. And pairing is
 * **detected**: the panel flips because an `agent_begin` transaction arrived on
 * the journal, not because anything in the UI confirmed it.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, nextTick } from 'vue'
import { createMemoryHistory, createRouter, createWebHistory, type Router } from 'vue-router'

import { FlowApiError } from '@/flow/api/client'
import { browserToken, TOKEN_STORAGE_KEY } from '@/flow/api/token'
import { flowPath } from '@/flow/workbench/model/routes'
import AgentTaskLine from '@/flow/workbench/components/panel/AgentTaskLine.vue'
import { pairedAgent } from '@/flow/workbench/live/pairing'
import { KEPT_TRANSACTIONS } from '@/flow/workbench/live/useFlowSession'
import EmptyFlowState from '@/flow/workbench/pages/EmptyFlowState.vue'
import WorkspacePage from '@/flow/workbench/pages/WorkspacePage.vue'
import { attach, FLOW, fakeDaemon, flowStatus, settle, transaction } from './fakes'
import type { Daemon, Handlers } from './fakes'

const Empty = defineComponent({ template: '<div />' })

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/flow', component: Empty },
      { path: '/flow/:flowId', component: Empty },
      { path: '/:pathMatch(.*)*', component: Empty },
    ],
  })
}

const ROOT = '/home/dana/project'

const workspace = {
  root: ROOT,
  path: '',
  outside: false,
  parent: '/home/dana',
  entries: [
    { name: 'churn.flow', path: 'churn.flow', kind: 'flow' as const, size: null },
    { name: 'data', path: 'data', kind: 'dir' as const, size: null },
    { name: 'helpers.py', path: 'helpers.py', kind: 'file' as const, size: 2048 },
    { name: 'pyproject.toml', path: 'pyproject.toml', kind: 'file' as const, size: 412 },
  ],
}

const inside = {
  root: ROOT,
  path: 'data',
  outside: false,
  parent: ROOT,
  entries: [{ name: 'raw.csv', path: 'data/raw.csv', kind: 'file' as const, size: 1_048_576 }],
}

/** One directory up: a neighbouring project, and the workspace beside it. */
const above = {
  root: ROOT,
  path: '/home/dana',
  outside: true,
  parent: '/home',
  entries: [
    { name: 'sales.flow', path: '/home/dana/sales.flow', kind: 'flow' as const, size: null },
    { name: 'project', path: ROOT, kind: 'dir' as const, size: null },
    { name: 'notes.md', path: '/home/dana/notes.md', kind: 'file' as const, size: 96 },
  ],
}

const byPath: Record<string, typeof workspace> = {
  '': workspace,
  data: inside,
  '/home/dana': above,
  [ROOT]: workspace,
}

function listings(handlers: Handlers = {}): Daemon {
  return fakeDaemon({
    'workspace.list': (params) => byPath[String(params.path ?? '')] ?? workspace,
    ...handlers,
  })
}

/** Creating a flow is a once-per-project gesture and folds away behind a button. */
async function openNewFlow(wrapper: Awaited<ReturnType<typeof browse>>): Promise<void> {
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'New flow')
    ?.trigger('click')
  await settle()
}

/** The file-manager gesture, which is the only way out of the launch directory. */
function upArrow(wrapper: Awaited<ReturnType<typeof browse>>) {
  return wrapper
    .findAll('button')
    .find((button) => button.attributes('aria-label') === 'up one directory')
}

async function browse(daemon: Daemon) {
  vi.stubGlobal('fetch', daemon.transport)
  const router = testRouter()
  await router.push('/flow')
  await router.isReady()
  const wrapper = mount(WorkspacePage, { global: { plugins: [router] } })
  await settle()
  return wrapper
}

/** What `workspace.list` was asked to show, in order. */
function listed(daemon: Daemon): unknown[] {
  return daemon.calls.filter((call) => call.method === 'workspace.list').map((call) => call.params)
}

beforeEach(() => {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, 'the-token')
})

afterEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
})

describe('the workspace browser', () => {
  it('lists what the daemon says is there, rooted at the launch directory', async () => {
    const daemon = listings()

    const wrapper = await browse(daemon)

    expect(listed(daemon)).toEqual([{ path: '' }])
    expect(wrapper.text()).toContain('/home/dana/project')
    for (const name of ['churn.flow', 'data', 'helpers.py', 'pyproject.toml']) {
      expect(wrapper.text()).toContain(name)
    }
    wrapper.unmount()
  })

  it('renders a flow as one document that opens, never as a folder to walk into', async () => {
    const daemon = listings()

    const wrapper = await browse(daemon)

    // One entry, one gesture: the workbench. Nothing offers its internals, and
    // no listing is ever asked for a path inside it — cells and the store are
    // the document's insides, not this workspace's files.
    const links = wrapper.findAll('a')
    expect(links).toHaveLength(1)
    expect(links[0].attributes('href')).toBe('/flow/churn.flow')
    expect(links[0].text()).toContain('churn.flow')

    expect(links[0].findAll('button')).toHaveLength(0)

    await links[0].trigger('click')
    await settle()
    expect(listed(daemon)).toEqual([{ path: '' }])
    expect(wrapper.findAll('a')).toHaveLength(1)
    wrapper.unmount()
  })

  it('walks into a plain directory and lists its files as context, without viewers', async () => {
    const daemon = listings()
    const wrapper = await browse(daemon)

    const folder = wrapper.findAll('button').find((button) => button.text() === 'data')
    await folder?.trigger('click')
    await settle()

    expect(listed(daemon)).toEqual([{ path: '' }, { path: 'data' }])
    expect(wrapper.text()).toContain('raw.csv')
    expect(wrapper.text()).toContain('1.0 MB')
    // A workspace file is listed, never opened: viewers are not v1, and the
    // store versions none of this.
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(wrapper.findAll('button').some((button) => button.text().includes('raw.csv'))).toBe(
      false,
    )
    wrapper.unmount()
  })

  it('climbs above the launch directory rather than dead-ending at it', async () => {
    const daemon = listings()
    const wrapper = await browse(daemon)

    await upArrow(wrapper)?.trigger('click')
    await settle()

    expect(listed(daemon)).toEqual([{ path: '' }, { path: '/home/dana' }])
    // The address is shown whole: above the workspace there is no root-relative
    // trail to draw, and the entries are the same three renderings as ever.
    expect(wrapper.text()).toContain('/home/dana')
    for (const name of ['sales.flow', 'project', 'notes.md']) {
      expect(wrapper.text()).toContain(name)
    }
    // Creating a flow stays in the workspace — "here" is not one up there.
    expect(wrapper.text()).not.toContain('new flow')
    expect(wrapper.text()).toContain('flows are created in')
    wrapper.unmount()
  })

  it('opens a flow outside the workspace on a link that carries where it is', async () => {
    const daemon = listings()
    const wrapper = await browse(daemon)
    await upArrow(wrapper)?.trigger('click')
    await settle()

    const link = wrapper.findAll('a')[0]

    // One segment, percent-encoded: `:flowId` matches one, and a literal `../`
    // would be resolved away by the browser before the router ever saw it.
    expect(wrapper.findAll('a')).toHaveLength(1)
    expect(link.attributes('href')).toBe('/flow/%2Fhome%2Fdana%2Fsales.flow')
    expect(link.text()).toContain('sales.flow')
    wrapper.unmount()
  })

  it('walks back down into the workspace, which is one of the entries up there', async () => {
    const daemon = listings()
    const wrapper = await browse(daemon)
    await upArrow(wrapper)?.trigger('click')
    await settle()

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'project')
      ?.trigger('click')
    await settle()

    expect(listed(daemon)).toEqual([{ path: '' }, { path: '/home/dana' }, { path: ROOT }])
    // Home again: the crumb trail is back and so is the way to create a flow.
    expect(wrapper.findAll('button').map((button) => button.text())).toContain('New flow')
    expect(wrapper.findAll('a')[0].attributes('href')).toBe('/flow/churn.flow')
    wrapper.unmount()
  })

  it('offers `back to workspace` from anywhere above it', async () => {
    const daemon = listings()
    const wrapper = await browse(daemon)
    await upArrow(wrapper)?.trigger('click')
    await settle()

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'back to workspace')
      ?.trigger('click')
    await settle()

    expect(listed(daemon)).toEqual([{ path: '' }, { path: '/home/dana' }, { path: '' }])
    wrapper.unmount()
  })

  it('init here scaffolds through the daemon and checks main out into it', async () => {
    const created = { flow: 'sweep', path: 'sweep.flow', branch: 'main', warnings: [] }
    const daemon = listings({ 'flow.init': () => created, 'flow.checkout': () => created })
    const wrapper = await browse(daemon)

    await openNewFlow(wrapper)
    await wrapper.find('input').setValue('sweep')
    await wrapper.find('form').trigger('submit')
    await settle()

    const ops = daemon.calls.filter((call) => call.method.startsWith('flow.'))
    expect(ops.map((call) => call.method)).toEqual(['flow.init', 'flow.checkout'])
    expect(ops[0].params).toEqual({ name: 'sweep' })
    // A bare init leaves the flow unbound; the browser's door owes the checkout
    // that makes the directory a worktree on `main`.
    expect(ops[1].params.flow).toBe('sweep.flow')
    expect(ops[1].params.branch).toBe('main')
    expect(ops[1].params.intent).toBeTruthy()
    // And the listing is re-read, so the new document shows up where it landed.
    expect(listed(daemon)).toEqual([{ path: '' }, { path: '' }])
    wrapper.unmount()
  })

  it('inits into the directory being browsed, not the root', async () => {
    const created = { flow: 'sweep', path: 'data/sweep.flow', branch: 'main', warnings: [] }
    const daemon = listings({ 'flow.init': () => created, 'flow.checkout': () => created })
    const wrapper = await browse(daemon)

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'data')
      ?.trigger('click')
    await settle()
    await openNewFlow(wrapper)
    await wrapper.find('input').setValue('sweep')
    await wrapper.find('form').trigger('submit')
    await settle()

    const init = daemon.calls.find((call) => call.method === 'flow.init')
    expect(init?.params).toEqual({ name: 'data/sweep' })
    wrapper.unmount()
  })

  it('shows the flow the scaffold created even when the checkout refuses', async () => {
    const created = {
      flow: 'sweep',
      path: 'sweep.flow',
      branch: 'main',
      warnings: ['cloud-synced folder'],
    }
    const daemon = listings({
      'flow.init': () => created,
      'flow.checkout': () => {
        throw new FlowApiError('`main` is held by claude-1', { status: 409 })
      },
    })
    const wrapper = await browse(daemon)

    await openNewFlow(wrapper)
    await wrapper.find('input').setValue('sweep')
    await wrapper.find('form').trigger('submit')
    await settle()

    // The flow is on disk the moment `flow.init` returns. A listing that does
    // not show it leaves the user unable to open it and unable to create it
    // again, so the re-read is owed whether or not the checkout landed.
    expect(listed(daemon)).toEqual([{ path: '' }, { path: '' }])
    // And the refusal is still the sentence on screen, not swallowed by the
    // fresh listing that followed it.
    expect(wrapper.text()).toContain('held by claude-1')
    expect(wrapper.text()).toContain('cloud-synced folder')
    // Something answered, so this is not the not-running state.
    expect(wrapper.text()).not.toContain('lumlflow is not running')
    wrapper.unmount()
  })

  it('stops claiming lumlflow is stopped once it names a refusal', async () => {
    const daemon = listings({
      'workspace.list': () => {
        throw new FlowApiError('`churn.flow` is a flow — open it rather than browsing it', {
          status: 400,
        })
      },
    })
    daemon.down.value = true
    const wrapper = await browse(daemon)
    expect(wrapper.text()).toContain('lumlflow is not running')

    // It came back, and what it came back with is a refusal — which is proof it
    // is there. Reporting that as "not running" would name the wrong failure.
    daemon.down.value = false
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'workspace')
      ?.trigger('click')
    await settle()

    expect(wrapper.text()).toContain('open it rather than browsing it')
    expect(wrapper.text()).not.toContain('lumlflow is not running')
    wrapper.unmount()
  })

  it('says nobody is answering rather than showing an empty workspace', async () => {
    const daemon = listings()
    daemon.down.value = true

    const wrapper = await browse(daemon)

    expect(wrapper.text()).toContain('lumlflow is not running')
    expect(wrapper.text()).toContain('lumlflow ui')
    expect(wrapper.text()).not.toContain('nothing here yet')
    // Never the word for the thing behind it: what the user runs is `lumlflow ui`.
    expect(wrapper.text().toLowerCase()).not.toContain('daemon')
    wrapper.unmount()
  })

  /**
   * A tab that never presented a token has learned nothing about who would have
   * answered it — reporting that as a stopped server names a failure that has
   * not happened, and sends the user to restart something already running.
   */
  it('separates a tab with no token from a server that is not answering', async () => {
    window.localStorage.clear()
    const daemon = listings()

    const wrapper = await browse(daemon)

    expect(daemon.calls).toEqual([])
    expect(wrapper.text()).toContain('this tab is not connected')
    expect(wrapper.text()).not.toContain('lumlflow is not running')
    // The remedy is the address, and nothing here claims the server is down.
    expect(wrapper.text()).toContain('lumlflow ui')
    expect(wrapper.text().toLowerCase()).not.toContain('daemon')
    wrapper.unmount()
  })

  /**
   * A restarted `lumlflow ui` mints another key, and the one this tab banked
   * stops being one. That is not a refusal about the request — it is the tab
   * holding nothing that opens the door — so it gets the same surface as never
   * having had a key, and the dead one is dropped rather than presented again.
   */
  it('reports a key the server refuses as a tab that is not connected', async () => {
    const daemon = listings({
      'workspace.list': () => {
        throw new FlowApiError(
          "this workspace's key is required — open the address `lumlflow ui` prints",
          { status: 401 },
        )
      },
    })

    const wrapper = await browse(daemon)

    expect(wrapper.text()).toContain('this tab is not connected')
    expect(wrapper.text()).toContain('lumlflow ui')
    expect(wrapper.text()).not.toContain('lumlflow is not running')
    // Said once: the refusal's own sentence under the notice would send the
    // reader to the same address twice.
    expect(wrapper.text()).not.toContain('key is required')
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
    expect(wrapper.text().toLowerCase()).not.toContain('daemon')
    wrapper.unmount()
  })

  /**
   * `lumlflow ui` opens the address it prints, and that address is a tracker
   * page as often as a flow. The key is banked when the tab enters, wherever it
   * enters — the click through to the workspace is a router navigation, and a
   * router navigation carries no query for a later page to read.
   */
  it('connects on a key the tab entered on another route holding', async () => {
    window.localStorage.clear()
    window.history.replaceState(null, '', '/?token=the-token&view=table')

    // What boot runs before the first navigation resolves.
    browserToken()
    expect(window.location.search).toBe('?view=table')

    const daemon = listings()
    const wrapper = await browse(daemon)

    expect(listed(daemon)).toEqual([{ path: '' }])
    expect(wrapper.text()).not.toContain('this tab is not connected')
    wrapper.unmount()
  })

  /** The tab that was open when this moved storages stays connected. */
  it('connects on a key only the tab-scoped storage still holds', async () => {
    window.localStorage.clear()
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, 'the-token')

    const daemon = listings()
    const wrapper = await browse(daemon)

    expect(listed(daemon)).toEqual([{ path: '' }])
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('the-token')
    expect(wrapper.text()).not.toContain('this tab is not connected')
    wrapper.unmount()
  })

  it('leaks no internals and offers no kernel plumbing', async () => {
    const wrapper = await browse(listings())

    const text = wrapper.text()
    expect(text).not.toMatch(/\buid\b/i)
    expect(text).not.toMatch(/memo key/i)
    expect(text).not.toMatch(/\b[0-9a-f]{16,}\b/i)
    // Opening a flow attaches the session; there is no picker, no connect
    // dialog, and nothing anywhere that names a kernel.
    expect(text).not.toMatch(/kernel|connect/i)
    wrapper.unmount()
  })
})

// --- addressing a flow outside the workspace ---------------------------------

/**
 * The one mechanism this feature rests on, asserted end to end rather than
 * described: a flow above the launch directory is addressed by where it is,
 * and where it is has separators in it.
 */
describe('a flow outside the workspace has a shareable address', () => {
  function history(): Router {
    return createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/flow/:flowId', component: Empty },
        { path: '/flow/:flowId/notebook', component: Empty },
        { path: '/:pathMatch(.*)*', component: Empty },
      ],
    })
  }

  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('survives the history API and comes back out of the router as the path', async () => {
    const flow = '/home/dana/sales.flow'
    const router = history()

    await router.push(flowPath(flow))
    await router.isReady()

    // One segment. A literal `../` is resolved away by the browser before the
    // router sees it, and so is `%2E%2E` — an address, not a route to walk.
    expect(flowPath(flow)).toBe('/flow/%2Fhome%2Fdana%2Fsales.flow')
    expect(window.location.pathname).toBe('/flow/%2Fhome%2Fdana%2Fsales.flow')
    expect(router.currentRoute.value.params.flowId).toBe(flow)
    // The workbench mirrors `route.path` into the URL on every selection, so
    // the encoding has to be what the route itself carries.
    expect(`${router.currentRoute.value.path}/notebook`).toBe(
      '/flow/%2Fhome%2Fdana%2Fsales.flow/notebook',
    )
  })

  it('opens the same flow when the address is loaded cold', async () => {
    const flow = '/home/dana/sales.flow'
    await history().push(flowPath(flow))

    // What a reload, a bookmark or a pasted link starts from: the address bar
    // alone, resolved by a router that saw none of the navigation.
    const opened = history().resolve(window.location.pathname)

    expect(opened.params.flowId).toBe(flow)
  })

  it('leaves the addresses inside the workspace exactly as they were', () => {
    expect(flowPath('churn.flow')).toBe('/flow/churn.flow')
    expect(flowPath('churn.flow', '/compare')).toBe('/flow/churn.flow/compare')
  })

  /**
   * Two flows can be called `sales` and only one of them is in this workspace,
   * so the session addresses the daemon by the path it answered with rather
   * than by the flow's name — which is also the key every frame carries.
   */
  it('watches the flow under the address the daemon keys its frames by', async () => {
    const outside = '/home/dana/sales.flow'
    const { session, socket } = await attach({
      status: flowStatus({ flow: 'sales', path: outside }),
    })

    expect(session.path.value).toBe(outside)
    expect(socket.messages).toContainEqual(
      expect.objectContaining({ subscribe: 'journal', flow: outside }),
    )
  })
})

// --- pairing -----------------------------------------------------------------

const BEGAN_AT = '2026-08-13T09:03:00Z'

function beganPairing(step = 3) {
  return transaction(step, {
    ts: BEGAN_AT,
    actor: 'claude-1',
    intent: 'claude-1 started working',
    ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1', worktree: true }],
  })
}

/** The line bound to the session, so only a journal frame can move it. */
function pairHarness(session: Parameters<typeof pairedAgent>[0], now: number) {
  return defineComponent({
    components: { AgentTaskLine },
    setup: () => ({ paired: computed(() => pairedAgent(session, now)) }),
    template: '<AgentTaskLine :paired="paired" viewed-branch="main" />',
  })
}

describe('pairing is detected, not declared', () => {
  it('flips from the pairing prompt to the agent on an agent_begin transaction', async () => {
    const { session, socket } = await attach()
    const wrapper = mount(pairHarness(session, Date.parse(BEGAN_AT) + 5_000))

    // Unpaired is one line and one link; the prompt is behind the link.
    expect(wrapper.text()).toContain('not paired')
    const pair = wrapper.findAll('button').find((node) => node.text() === 'pair an agent')
    expect(pair, 'no pair link while unpaired').toBeTruthy()
    expect(wrapper.text()).not.toContain('mcpServers')

    await pair?.trigger('click')
    await nextTick()
    // One prompt, one way to take it — said once, in the overlay.
    expect(
      document.body.querySelectorAll('button[aria-label="copy the connect prompt"]'),
    ).toHaveLength(1)
    expect(document.body.textContent).toContain('mcpServers')

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 3,
      transaction: beganPairing(),
    })
    await nextTick()

    expect(wrapper.text()).toContain('claude-1')
    expect(wrapper.text()).toContain('claude-1 started working')
    // Nothing to confirm: no control of any kind survives the flip.
    expect(wrapper.findAll('button')).toHaveLength(0)
    wrapper.unmount()
  })

  it('reads a quiet agent as idle with the time since its last transaction', async () => {
    const { session, socket } = await attach()
    const wrapper = mount(pairHarness(session, Date.parse(BEGAN_AT) + 300_000))

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 3,
      transaction: beganPairing(),
    })
    await nextTick()

    expect(wrapper.text()).toContain('idle')
    expect(wrapper.text()).toContain('5m 0s')
    wrapper.unmount()
  })

  it('never claims work it has no transaction for', async () => {
    const { session, socket } = await attach()

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 3,
      transaction: beganPairing(),
    })
    await nextTick()

    // The registration survives; the transaction that carried it is pushed out
    // of the kept window by a long burst from somebody else. "Working" here
    // would be a fabricated status — and worse, a transition *backwards* out of
    // idle, since a moment ago the panel was reading the real elapsed time.
    expect(pairedAgent(session, Date.parse(BEGAN_AT) + 300_000)).toMatchObject({
      state: 'idle',
      idleFor: '5m 0s',
    })

    for (let step = 4; step < 4 + KEPT_TRANSACTIONS; step += 1) {
      socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step, { actor: 'user', intent: 'edited a cell' }),
      })
    }
    await nextTick()

    expect(session.agent.value?.label).toBe('claude-1')
    expect(session.transactions.value.some((entry) => entry.actor === 'claude-1')).toBe(false)
    const paired = pairedAgent(session, Date.parse(BEGAN_AT) + 300_000)
    expect(paired?.state).toBe('idle')
    // Idle without a duration: how long is exactly what is no longer known.
    expect(paired?.idleFor).toBeUndefined()
    expect(paired?.task).toBeUndefined()
  })

  it('goes back to unpaired when the session ends, which is a working state', async () => {
    const { session, socket } = await attach()
    const wrapper = mount(pairHarness(session, Date.parse(BEGAN_AT) + 5_000))

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 3,
      transaction: beganPairing(),
    })
    await nextTick()
    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 4,
      transaction: transaction(4, {
        ts: BEGAN_AT,
        actor: 'claude-1',
        intent: 'claude-1 stopped',
        ops: [{ op: 'agent_end', actor: 'claude-1', label: 'claude-1' }],
      }),
    })
    await nextTick()

    // Unpaired is a working state, not an error: the line goes back to the link
    // that pairs one rather than to anything that reads as a failure.
    expect(wrapper.text()).toContain('not paired')
    const pair = wrapper.findAll('button').find((node) => node.text() === 'pair an agent')
    expect(pair, 'no pair link after the session ended').toBeTruthy()
    wrapper.unmount()
  })
})

// --- the empty flow ----------------------------------------------------------

describe('the empty state is a heading and one line, not a void', () => {
  const ways = ['add one here', 'pair an agent', 'AGENTS.md', 'notebook view']

  it('offers every way in on one line, with the command copyable', () => {
    const wrapper = mount(EmptyFlowState)

    const labels = wrapper.findAll('button').map((button) => button.text())
    for (const way of ways) expect(labels).toContain(way)
    // The one command an empty flow is about is on screen; the pairing prompt
    // is behind its link, because it is not what an empty flow needs first.
    expect(wrapper.text()).toContain('lumlflow cells new load_data')
    expect(wrapper.text()).not.toContain('mcpServers')
    // No grid of cards and no outline around the emptiness.
    expect(wrapper.find('.border-dashed').exists()).toBe(false)
    wrapper.unmount()
  })

  it('drops the pairing link once an agent is paired', () => {
    const wrapper = mount(EmptyFlowState, {
      props: { paired: { label: 'claude-1', branch: 'main', state: 'working' as const } },
    })

    const labels = wrapper.findAll('button').map((button) => button.text())
    expect(labels).not.toContain('pair an agent')
    for (const way of ['add one here', 'AGENTS.md', 'notebook view']) {
      expect(labels).toContain(way)
    }
    wrapper.unmount()
  })

  it('hands the create, cheatsheet and notebook ways to the page that owns them', async () => {
    const wrapper = mount(EmptyFlowState)

    const buttons = wrapper.findAll('button')
    await buttons.find((button) => button.text() === 'add one here')?.trigger('click')
    await buttons.find((button) => button.text() === 'AGENTS.md')?.trigger('click')
    await buttons.find((button) => button.text() === 'notebook view')?.trigger('click')

    expect(wrapper.emitted('create')).toHaveLength(1)
    expect(wrapper.emitted('cheatsheet')).toHaveLength(1)
    expect(wrapper.emitted('notebook')).toHaveLength(1)
    wrapper.unmount()
  })

  /**
   * The door an empty flow offers pairing through. Opening it is the ask a page
   * answers with the workspace's own prompt — and with no page behind it, the
   * fixture arm still hands over a whole one rather than an empty popover.
   */
  it('opens the pairing prompt and says so, on the fixture arm too', async () => {
    const wrapper = mount(EmptyFlowState)

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'pair an agent')
      ?.trigger('click')
    await nextTick()

    expect(wrapper.emitted('pair')).toHaveLength(1)
    expect(
      document.body.querySelectorAll('button[aria-label="copy the connect prompt"]'),
    ).toHaveLength(1)
    expect(document.body.textContent).toContain('mcpServers')
    wrapper.unmount()
  })
})
