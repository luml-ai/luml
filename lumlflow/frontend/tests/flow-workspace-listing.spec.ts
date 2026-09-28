/** The launch-directory listing, path addressing, pairing, and empty state. */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, nextTick } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, createWebHistory, type Router } from 'vue-router'

import MainHeader from '@/components/layout/header/MainHeader.vue'
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
  directory: ROOT,
  flows: [
    {
      name: 'churn',
      path: `${ROOT}/churn.flow`,
      relative_path: 'churn.flow',
    },
    {
      name: 'sweep',
      path: `${ROOT}/experiments/sweep.flow`,
      relative_path: 'experiments/sweep.flow',
    },
  ],
}

function listings(handlers: Handlers = {}): Daemon {
  return fakeDaemon({
    'workspace.list': (params) => ({
      ...workspace,
      directory: String(params.directory ?? ROOT),
    }),
    ...handlers,
  })
}

/** Creating a flow is a once-per-project gesture and folds away behind a button. */
async function openNewFlow(wrapper: Awaited<ReturnType<typeof landing>>): Promise<void> {
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'New flow')
    ?.trigger('click')
  await settle()
}

async function landing(daemon: Daemon, directory = ROOT) {
  vi.stubGlobal('fetch', daemon.transport)
  const router = testRouter()
  await router.push({ path: '/flow', query: { directory } })
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

describe('the workspace listing', () => {
  it('lists only the flows beneath the directory in the address', async () => {
    const daemon = listings()

    const wrapper = await landing(daemon)

    expect(listed(daemon)).toEqual([{ directory: ROOT }])
    expect(wrapper.text()).toContain(ROOT)
    for (const name of ['churn.flow', 'experiments/sweep.flow']) {
      expect(wrapper.text()).toContain(name)
    }
    wrapper.unmount()
  })

  it('opens absolute flow paths and offers no directory browser', async () => {
    const daemon = listings()

    const wrapper = await landing(daemon)

    const links = wrapper.findAll('a')
    expect(links).toHaveLength(2)
    expect(links[0].attributes('href')).toBe(
      '/flow/%2Fhome%2Fdana%2Fproject%2Fchurn.flow?directory=/home/dana/project',
    )
    expect(links[0].text()).toContain('churn.flow')
    expect(wrapper.find('[aria-label="up one directory"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('back to workspace')
    wrapper.unmount()
  })

  it('keeps the launch-directory view in top-level navigation', async () => {
    const router = testRouter()
    await router.push({ path: flowPath(`${ROOT}/churn.flow`), query: { directory: ROOT } })
    await router.isReady()
    const wrapper = mount(MainHeader, {
      global: {
        plugins: [router, createPinia()],
        stubs: { ApiKeyButton: true, ThemeToggle: true },
      },
    })

    const workspaceLink = wrapper.findAll('a').find((link) => link.text() === 'Workspace')
    expect(workspaceLink?.attributes('href')).toBe('/flow?directory=/home/dana/project')

    const experimentsLink = wrapper.findAll('a').find((link) => link.text() === 'Experiments')
    await experimentsLink?.trigger('click')
    await nextTick()
    expect(router.currentRoute.value.query).toEqual({ directory: ROOT })
    wrapper.unmount()
  })

  it('offers New flow when the launch directory contains no flows', async () => {
    const daemon = listings({
      'workspace.list': (params) => ({
        directory: params.directory,
        flows: [],
      }),
    })

    const wrapper = await landing(daemon)

    expect(wrapper.text()).toContain('no flows here yet')
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(wrapper.findAll('button').map((button) => button.text())).toContain('New flow')
    wrapper.unmount()
  })

  it('init here scaffolds through the daemon and checks main out into it', async () => {
    const created = {
      flow: 'sweep',
      path: `${ROOT}/sweep.flow`,
      branch: 'main',
      warnings: [],
    }
    const daemon = listings({ 'flow.init': () => created, 'flow.checkout': () => created })
    const wrapper = await landing(daemon)

    await openNewFlow(wrapper)
    await wrapper.find('input').setValue('sweep')
    await wrapper.find('form').trigger('submit')
    await settle()

    const ops = daemon.calls.filter((call) => call.method.startsWith('flow.'))
    expect(ops.map((call) => call.method)).toEqual(['flow.init', 'flow.checkout'])
    expect(ops[0].params).toEqual({ name: 'sweep', directory: ROOT })
    expect(ops[1].params.flow).toBe(`${ROOT}/sweep.flow`)
    expect(ops[1].params.branch).toBe('main')
    expect(ops[1].params.intent).toBeTruthy()
    // And the listing is re-read, so the new document shows up where it landed.
    expect(listed(daemon)).toEqual([{ directory: ROOT }, { directory: ROOT }])
    wrapper.unmount()
  })

  it('uses the launch directory from the address, not the daemon start directory', async () => {
    const other = '/home/dana/other'
    const created = {
      flow: 'sweep',
      path: `${other}/sweep.flow`,
      branch: 'main',
      warnings: [],
    }
    const daemon = listings({ 'flow.init': () => created, 'flow.checkout': () => created })
    const wrapper = await landing(daemon, other)

    await openNewFlow(wrapper)
    await wrapper.find('input').setValue('sweep')
    await wrapper.find('form').trigger('submit')
    await settle()

    const init = daemon.calls.find((call) => call.method === 'flow.init')
    expect(listed(daemon)[0]).toEqual({ directory: other })
    expect(init?.params).toEqual({ name: 'sweep', directory: other })
    wrapper.unmount()
  })

  it('shows the flow the scaffold created even when the checkout refuses', async () => {
    const created = {
      flow: 'sweep',
      path: `${ROOT}/sweep.flow`,
      branch: 'main',
      warnings: ['cloud-synced folder'],
    }
    const daemon = listings({
      'flow.init': () => created,
      'flow.checkout': () => {
        throw new FlowApiError('`main` is held by claude-1', { status: 409 })
      },
    })
    const wrapper = await landing(daemon)

    await openNewFlow(wrapper)
    await wrapper.find('input').setValue('sweep')
    await wrapper.find('form').trigger('submit')
    await settle()

    // The flow is on disk the moment `flow.init` returns. A listing that does
    // not show it leaves the user unable to open it and unable to create it
    // again, so the re-read is owed whether or not the checkout landed.
    expect(listed(daemon)).toEqual([{ directory: ROOT }, { directory: ROOT }])
    // And the refusal is still the sentence on screen, not swallowed by the
    // fresh listing that followed it.
    expect(wrapper.text()).toContain('held by claude-1')
    expect(wrapper.text()).toContain('cloud-synced folder')
    // Something answered, so this is not the not-running state.
    expect(wrapper.text()).not.toContain('lumlflow is not running')
    wrapper.unmount()
  })

  it('renders a listing refusal without claiming lumlflow is stopped', async () => {
    const daemon = listings({
      'workspace.list': () => {
        throw new FlowApiError('the launch directory cannot be read', { status: 400 })
      },
    })
    const wrapper = await landing(daemon)

    expect(wrapper.text()).toContain('the launch directory cannot be read')
    expect(wrapper.text()).not.toContain('lumlflow is not running')
    wrapper.unmount()
  })

  it('says nobody is answering rather than showing an empty workspace', async () => {
    const daemon = listings()
    daemon.down.value = true

    const wrapper = await landing(daemon)

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

    const wrapper = await landing(daemon)

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

    const wrapper = await landing(daemon)

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
   * The key is banked before routing, so the directory query remains available
   * to the landing page after the key is removed from the address bar.
   */
  it('connects on a key the tab entered on another route holding', async () => {
    window.localStorage.clear()
    window.history.replaceState(null, '', '/?token=the-token&view=table')

    // What boot runs before the first navigation resolves.
    browserToken()
    expect(window.location.search).toBe('?view=table')

    const daemon = listings()
    const wrapper = await landing(daemon)

    expect(listed(daemon)).toEqual([{ directory: ROOT }])
    expect(wrapper.text()).not.toContain('this tab is not connected')
    wrapper.unmount()
  })

  /** The tab that was open when this moved storages stays connected. */
  it('connects on a key only the tab-scoped storage still holds', async () => {
    window.localStorage.clear()
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, 'the-token')

    const daemon = listings()
    const wrapper = await landing(daemon)

    expect(listed(daemon)).toEqual([{ directory: ROOT }])
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('the-token')
    expect(wrapper.text()).not.toContain('this tab is not connected')
    wrapper.unmount()
  })

  it('leaks no internals and offers no kernel plumbing', async () => {
    const wrapper = await landing(listings())

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
    ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1' }],
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
  it('flips from the Agents-section link to the agent on an agent_begin transaction', async () => {
    const { session, socket } = await attach()
    const wrapper = mount(pairHarness(session, Date.parse(BEGAN_AT) + 5_000))

    // Unpaired is one line and one link into the Agents section.
    expect(wrapper.text()).toContain('not paired')
    const pair = wrapper.findAll('button').find((node) => node.text() === 'pair an agent')
    expect(pair, 'no pair link while unpaired').toBeTruthy()

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
  const ways = ['add one here', 'pair an agent', 'agent guide', 'notebook view']

  it('offers every way in on one line, with the command copyable', () => {
    const wrapper = mount(EmptyFlowState)

    const labels = wrapper.findAll('button').map((button) => button.text())
    for (const way of ways) expect(labels).toContain(way)
    expect(labels).not.toContain('AGENTS.md')
    // The one command an empty flow is about is on screen; harness setup lives
    // in the panel rather than taking over the empty surface.
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
    for (const way of ['add one here', 'agent guide', 'notebook view']) {
      expect(labels).toContain(way)
    }
    wrapper.unmount()
  })

  it('hands the create, cheatsheet and notebook ways to the page that owns them', async () => {
    const wrapper = mount(EmptyFlowState)

    const buttons = wrapper.findAll('button')
    await buttons.find((button) => button.text() === 'add one here')?.trigger('click')
    await buttons.find((button) => button.text() === 'agent guide')?.trigger('click')
    await buttons.find((button) => button.text() === 'notebook view')?.trigger('click')

    expect(wrapper.emitted('create')).toHaveLength(1)
    expect(wrapper.emitted('cheatsheet')).toHaveLength(1)
    expect(wrapper.emitted('notebook')).toHaveLength(1)
    wrapper.unmount()
  })

  it('hands the pairing link to the page that opens the Agents section', async () => {
    const wrapper = mount(EmptyFlowState)

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'pair an agent')
      ?.trigger('click')
    await nextTick()

    expect(wrapper.emitted('pair')).toHaveLength(1)
    expect(document.body.textContent).not.toContain('mcpServers')
    wrapper.unmount()
  })
})
