/**
 * The live session layer: the cursor, the degraded states, and the ops.
 *
 * The socket and the daemon are both fakes here, which is the point — what is
 * asserted is the client's own contract. A reconnect must replay to the same
 * state a fresh load reaches; a dropped socket must not be reported as a daemon
 * that is gone; and every mutating verb must carry the intent the journal
 * requires of it.
 */

import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { effectScope, nextTick, ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import { DaemonUnreachable, FlowApi } from '@/flow/api/client'
import { LogRing } from '@/flow/api/logs'
import { FlowStream, WS_UNAUTHORIZED } from '@/flow/api/stream'
import { browserToken, resolveToken, TOKEN_STORAGE_KEY, tokenRejected } from '@/flow/api/token'
import type { CellSummary, LogFrame } from '@/flow/api/types'
import SessionBanners from '@/flow/workbench/components/session/SessionBanners.vue'
import { cursorKey, readCursor, writeCursor } from '@/flow/workbench/live/cursor'
import type { CursorStorage } from '@/flow/workbench/live/cursor'
import { degradedStates, flowState } from '@/flow/workbench/live/degraded'
import type { DegradedKind } from '@/flow/workbench/live/degraded'
import { selectSource } from '@/flow/workbench/live/source'
import { coalesceTransactions } from '@/flow/workbench/live/toasts'
import { useFlowOps } from '@/flow/workbench/live/useFlowOps'
import { useFlowSession } from '@/flow/workbench/live/useFlowSession'
import type { FlowSessionHandle } from '@/flow/workbench/live/useFlowSession'
import { useRunLogs } from '@/flow/workbench/live/useRunLogs'
import { useSelection } from '@/flow/workbench/live/useSelection'
import { useSlice } from '@/flow/workbench/live/useSlice'
import {
  attach,
  cellSummary,
  FakeSocket,
  fakeDaemon,
  FLOW,
  flowStatus,
  settle,
  settleJournal,
  transaction,
} from './fakes'

// --- fakes -------------------------------------------------------------------

function logFrame(seq: number, text: string, runId = 'run-1'): LogFrame {
  return { channel: 'logs', flow: FLOW, run_id: runId, seq, stream: 'stdout', text }
}

/** Everything a client is supposed to end up holding, whatever route it took. */
function stateOf(session: FlowSessionHandle) {
  return {
    steps: session.transactions.value.map((entry) => entry.step),
    intents: session.transactions.value.map((entry) => entry.intent),
    head: session.head.value,
    agent: session.agent.value,
    running: session.running.value,
    state: session.state.value,
  }
}

// --- the cursor --------------------------------------------------------------

describe('cursor handling', () => {
  it('subscribes from where it got to, and starts at zero on a first load', async () => {
    const { socket } = await attach()

    expect(socket.messages).toEqual([{ subscribe: 'journal', flow: FLOW, cursor: 0 }])
  })

  it('advances on transactions, kernel events, and the catch-up', async () => {
    const { socket, stream } = await attach()

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 4,
      transaction: transaction(4),
    })
    expect(stream.cursor(FLOW)).toBe(4)

    socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'started',
      step: 5,
      run_id: 'run-1',
      slug: 'train_model',
    })
    expect(stream.cursor(FLOW)).toBe(5)

    socket.deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 9, running: [] })
    expect(stream.cursor(FLOW)).toBe(9)
  })

  it('never walks the cursor backwards on an out-of-order frame', async () => {
    const { socket, stream } = await attach()

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 7,
      transaction: transaction(7),
    })
    socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'progress',
      step: 3,
      run_id: 'run-1',
    })

    expect(stream.cursor(FLOW)).toBe(7)
  })

  it('re-asks from the cursor when the daemon says this client fell behind', async () => {
    const { socket } = await attach()
    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 6,
      transaction: transaction(6),
    })
    socket.sent = []

    socket.deliver({ channel: 'journal', type: 'lagged' })

    // The remedy the daemon names for a lagged client is the replay it holds a
    // cursor for — asking again from zero would re-deliver the whole journal.
    expect(socket.messages).toEqual([{ subscribe: 'journal', flow: FLOW, cursor: 6 }])
  })
})

describe('reconnect replay', () => {
  it('reaches the state a fresh load reaches, over a drop and a re-delivery', async () => {
    const live = await attach()
    for (const step of [1, 2, 3]) {
      live.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step),
      })
    }

    live.socket.drop()
    expect(live.session.stream.value).toBe('dropped')
    expect(live.reconnects).toHaveLength(1)
    live.reconnects[0]()
    const reopened = live.sockets[1]
    reopened.open()

    // The daemon replays from the held cursor, and a tail it re-delivers has
    // to land once — this is the whole reason frames carry their step.
    expect(reopened.messages).toEqual([{ subscribe: 'journal', flow: FLOW, cursor: 3 }])
    for (const step of [3, 4]) {
      reopened.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step),
      })
    }
    reopened.deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 4, running: [] })

    const fresh = await attach()
    for (const step of [1, 2, 3, 4]) {
      fresh.socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step),
      })
    }
    fresh.socket.deliver({
      channel: 'journal',
      type: 'caught_up',
      flow: FLOW,
      step: 4,
      running: [],
    })

    expect(stateOf(live.session)).toEqual(stateOf(fresh.session))
    expect(live.session.transactions.value.map((entry) => entry.step)).toEqual([1, 2, 3, 4])
  })

  it('stops trying when the daemon refuses the token, and says so distinctly', async () => {
    const { socket, session, reconnects } = await attach()

    socket.drop(WS_UNAUTHORIZED)

    expect(session.stream.value).toBe('refused')
    expect(reconnects).toEqual([])
    expect(session.degraded.value).toContain('socket-refused')
  })

  /**
   * Restarting `lumlflow ui` under an open tab is the ordinary way to get here:
   * the socket drops while the old process is going down — which leaves the tab
   * believing the daemon is gone — and the new one refuses the key the old one
   * minted. A refusal is proof somebody answered, so the tab must stop saying
   * lumlflow is not running and start saying the thing that actually fixes it.
   */
  it('treats a refusal as proof the daemon is up, not as it being gone', async () => {
    const { socket, sockets, session, daemon, reconnects } = await attach()

    daemon.down.value = true
    socket.drop()
    await settle()
    expect(session.reachable.value).toBe(false)
    expect(session.degraded.value).toEqual(['daemon-down'])

    // The restarted daemon is listening again, and refuses the key its
    // predecessor minted for this tab.
    reconnects[0]()
    sockets[1].drop(WS_UNAUTHORIZED)
    await settle()

    expect(session.reachable.value).toBe(true)
    expect(session.degraded.value).toEqual(['socket-refused'])
    expect(session.degraded.value).not.toContain('daemon-down')
    // And the key it refused is dropped, so the page-level surface can offer
    // the address that mints a working one.
    expect(tokenRejected.value).toBe(true)
  })
})

// --- degraded states ---------------------------------------------------------

describe('degraded states', () => {
  it('separates a dropped socket from a daemon that is gone', async () => {
    const { socket, session, daemon } = await attach()

    socket.drop()
    await settle()

    // The probe answered, so the workbench is live and merely reconnecting.
    expect(daemon.calls.at(-1)?.method).toBe('ping')
    expect(session.reachable.value).toBe(true)
    expect(session.degraded.value).toEqual(['socket-dropped'])
    expect(session.state.value).toBe('unpaired')
  })

  it('reports the daemon down when the probe finds nobody home', async () => {
    const { socket, session, daemon } = await attach()

    daemon.down.value = true
    socket.drop()
    await settle()

    expect(session.reachable.value).toBe(false)
    // One cause, one banner: the socket dropping is how a dead daemon announces
    // itself, and saying both would be saying it twice.
    expect(session.degraded.value).toEqual(['daemon-down'])
    expect(session.state.value).toBe('daemon-down')
  })

  it('names the kernel as not started while everything else is live', async () => {
    const { session } = await attach({
      status: flowStatus({
        kernel: { state: 'stopped', restart_required: false, behind: [], sandbox: 'none' },
      }),
    })

    expect(session.degraded.value).toContain('kernel-not-started')
    expect(session.state.value).toBe('kernel-not-started')
  })

  /**
   * The kernel starts lazily, on the first gesture that needs one — so the
   * state the brief carried when the tab opened is `stopped` almost every time,
   * and a tab that never re-read it went on saying "kernel not started" after
   * watching a dozen runs go by. It is the daemon that says otherwise.
   */
  it('takes the kernel starting from the daemon rather than the brief it opened with', async () => {
    const { socket, session } = await attach({
      status: flowStatus({
        kernel: { state: 'stopped', restart_required: false, behind: [], sandbox: 'none' },
      }),
    })

    expect(session.state.value).toBe('kernel-not-started')

    socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'kernel_state',
      step: 4,
      kernel: 'running',
    })

    expect(session.brief.value?.kernel.state).toBe('running')
    expect(session.degraded.value).not.toContain('kernel-not-started')
    expect(session.state.value).toBe('unpaired')

    // And a kernel that dies is reported dead, rather than left running because
    // the last thing anybody heard was that it had started.
    socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'kernel_state',
      step: 5,
      kernel: 'stopped',
    })

    expect(session.state.value).toBe('kernel-not-started')
  })

  it('keeps the rest of the kernel report while its state moves', async () => {
    const { socket, session } = await attach({
      status: flowStatus({
        kernel: { state: 'stopped', restart_required: true, behind: ['numpy'], sandbox: 'none' },
      }),
    })

    socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'kernel_state',
      step: 2,
      kernel: 'running',
    })

    expect(session.brief.value?.kernel.behind).toEqual(['numpy'])
    expect(session.brief.value?.kernel.restart_required).toBe(true)
  })

  it('counts the changes since this client was last here', async () => {
    const daemon = fakeDaemon({ 'flow.open': () => flowStatus() })
    const sockets: FakeSocket[] = []
    const stream = new FlowStream({
      token: 'the-token',
      open: () => {
        const socket = new FakeSocket()
        sockets.push(socket)
        return socket
      },
      schedule: () => {},
    })
    const session = useFlowSession({ api: daemon.api, stream, flow: 'churn', seenStep: 8 })
    await session.attach()
    sockets[0].open()

    sockets[0].deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 20, running: [] })

    expect(session.changesBehind.value).toBe(12)
    expect(session.degraded.value).toContain('behind-cursor')

    session.markSeen()
    expect(session.changesBehind.value).toBe(0)
    expect(session.degraded.value).not.toContain('behind-cursor')
  })

  it('is never behind on a first load, having no earlier cursor to be behind', async () => {
    const { socket, session } = await attach()

    socket.deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 31, running: [] })

    expect(session.changesBehind.value).toBe(0)
    expect(session.degraded.value).toEqual([])
  })

  /**
   * "Since you were here" is about being away. A reader sitting in front of the
   * feed watching transactions land is here for every one of them — counting
   * those was how a tab someone was working in accumulated a marker offering to
   * catch them up on their own last ten minutes.
   */
  it('does not count what lands while the reader is watching it land', async () => {
    const { socket, session } = await attach()

    socket.deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 4, running: [] })
    for (const step of [5, 6, 7]) {
      socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step),
      })
    }

    expect(session.head.value).toBe(7)
    expect(session.changesBehind.value).toBe(0)
    expect(session.degraded.value).not.toContain('behind-cursor')
  })

  /**
   * The other half of the same fact: a socket that was away for a while comes
   * back to a catch-up, and the gap it measures then is a real one.
   */
  it('measures the gap a dropped socket left, and freezes it there', async () => {
    const { socket, sockets, session, reconnects } = await attach()

    socket.deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 4, running: [] })
    expect(session.changesBehind.value).toBe(0)

    socket.drop()
    await settle()
    reconnects[0]()
    sockets[1].open()
    sockets[1].deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 9, running: [] })

    expect(session.changesBehind.value).toBe(5)

    // Live again: what arrives now is watched, and does not deepen the gap.
    sockets[1].deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 10,
      transaction: transaction(10),
    })
    expect(session.changesBehind.value).toBe(5)

    session.markSeen()
    expect(session.changesBehind.value).toBe(0)
  })

  it('reads the five-valued indicator in the order a reader needs it', () => {
    const live = {
      reachable: true,
      stream: 'open',
      kernel: 'running',
      running: 0,
      paired: true,
      changesBehind: 0,
    } as const

    expect(flowState({ ...live, reachable: false, running: 3 })).toBe('daemon-down')
    expect(flowState({ ...live, running: 1 })).toBe('running')
    expect(flowState({ ...live, kernel: 'stopped' })).toBe('kernel-not-started')
    expect(flowState({ ...live, paired: false })).toBe('unpaired')
    expect(flowState(live)).toBe('idle')
  })

  it('reports every condition that holds, most severe first', () => {
    expect(
      degradedStates({
        reachable: false,
        stream: 'dropped',
        kernel: 'stopped',
        running: 0,
        paired: false,
        changesBehind: 4,
      }),
    ).toEqual(['daemon-down', 'behind-cursor'])
  })
})

describe('the surfaces a degraded state drives', () => {
  const banners = (degraded: DegradedKind[], changesBehind = 0) =>
    mount(SessionBanners, { props: { degraded, changesBehind } })

  it('gives the daemon-down state the command that starts one', () => {
    expect(banners(['daemon-down']).text()).toContain('lumlflow ui')
  })

  it('promises the replay a dropped socket is owed, and nothing more', () => {
    const text = banners(['socket-dropped']).text()
    expect(text).toContain('reconnecting')
    expect(text).toContain('replays from cursor')
  })

  it('does not offer to reconnect a token the daemon will keep refusing', () => {
    const text = banners(['socket-refused']).text()
    expect(text).toContain('lumlflow ui')
    expect(text).not.toContain('reconnecting')
  })

  it('marks how far behind the reader is, and offers the feed at the cursor', async () => {
    const banner = banners(['behind-cursor'], 12)
    expect(banner.text()).toContain('12 changes since you were here')

    await banner.find('button').trigger('click')
    expect(banner.emitted('open-catchup')).toHaveLength(1)
  })

  it('raises no banner for a kernel that has not started', () => {
    // Browsing is the kernel-free tier by design; announcing it up front would
    // read as something being wrong. The hint belongs to the gesture instead.
    expect(banners(['kernel-not-started']).html()).toBe('<!--v-if-->')
  })

  it('shows nothing at all when nothing is wrong', () => {
    expect(banners([]).html()).toBe('<!--v-if-->')
  })
})

// --- pairing, runs, and the slice --------------------------------------------

describe('the session state a journal drives', () => {
  it('flips to paired on the agent_begin transaction, with no confirmation step', async () => {
    const { socket, session } = await attach()
    expect(session.agent.value).toBeNull()

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 2,
      transaction: transaction(2, {
        intent: 'session start',
        ops: [{ op: 'agent_begin', actor: 'claude-1', label: 'claude-1', worktree: true }],
      }),
    })

    expect(session.agent.value).toEqual({ actor: 'claude-1', label: 'claude-1', worktree: true })
    expect(session.state.value).toBe('idle')

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 3,
      transaction: transaction(3, {
        intent: 'session end',
        ops: [{ op: 'agent_end', actor: 'claude-1', label: 'claude-1' }],
      }),
    })

    expect(session.agent.value).toBeNull()
    expect(session.state.value).toBe('unpaired')
  })

  it('learns the runs in flight from the catch-up, not only from events', async () => {
    const { socket, session } = await attach()

    socket.deliver({
      channel: 'journal',
      type: 'caught_up',
      flow: FLOW,
      step: 12,
      running: [{ run_id: 'run-1', slug: 'train_model' }],
    })

    expect(session.state.value).toBe('running')

    socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'materialized',
      step: 13,
      run_id: 'run-1',
    })

    expect(session.running.value).toEqual([])
    expect(session.state.value).toBe('unpaired')
  })

  it('ignores frames for a flow this session is not watching', async () => {
    const { socket, session } = await attach()

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: 'other.flow',
      step: 99,
      transaction: transaction(99),
    })

    expect(session.transactions.value).toEqual([])
    expect(session.head.value).toBe(0)
  })
})

describe('a burst of transactions is one movement to re-read after', () => {
  /**
   * Subscribing replays every transaction the client missed, one frame each.
   * Treating each as its own invalidation made opening a flow cost a slice read
   * per step in its history — a journal is append-only, so that price only ever
   * goes up. What the reader is owed is the state at the end of the replay.
   */
  it('replays a long journal and reads the slice once, at the catch-up', async () => {
    const { session, socket, daemon } = await attach()
    const branch = ref<string | null>('main')
    const scope = effectScope()
    scope.run(() => useSlice(session, branch))
    await settle()

    const first = daemon.calls.filter((call) => call.method === 'cells.list').length
    for (let step = 1; step <= 40; step += 1) {
      socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step),
      })
    }
    await settle()
    // Nothing has gone out yet: the replay is still arriving.
    expect(daemon.calls.filter((call) => call.method === 'cells.list')).toHaveLength(first)

    socket.deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 40, running: [] })
    await settleJournal()

    expect(daemon.calls.filter((call) => call.method === 'cells.list')).toHaveLength(first + 1)
    expect(session.head.value).toBe(40)
    expect(session.revision.value).toBe(40)
    scope.stop()
  })

  it('coalesces a live burst that no catch-up ends', async () => {
    const { session, socket, daemon } = await attach()
    socket.deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 0, running: [] })
    const branch = ref<string | null>('main')
    const scope = effectScope()
    scope.run(() => useSlice(session, branch))
    await settleJournal()

    const before = daemon.calls.filter((call) => call.method === 'cells.list').length
    for (const step of [7, 8, 9, 10, 11]) {
      socket.deliver({
        channel: 'journal',
        type: 'transaction',
        flow: FLOW,
        step,
        transaction: transaction(step),
      })
    }
    await settleJournal()

    expect(daemon.calls.filter((call) => call.method === 'cells.list')).toHaveLength(before + 1)
    scope.stop()
  })
})

describe('the viewed slice', () => {
  const cell = cellSummary

  it('caches per branch, and refetches every branch once the journal moves', async () => {
    const slices: Record<string, CellSummary[]> = {
      main: [cell('features', { state: 'unsynced', causes: ['`helpers.py` changed'] })],
      sweep: [cell('features'), cell('plot', { transitive: true, upstream: ['features'] })],
    }
    const { session, socket, daemon } = await attach({
      handlers: {
        'cells.list': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: slices[String(params.branch)] ?? [],
        }),
      },
    })
    const branch = ref<string | null>('main')
    const scope = effectScope()
    const slice = scope.run(() => useSlice(session, branch))!
    await settle()

    expect(slice.cells.value.map((entry) => entry.slug)).toEqual(['features'])
    expect(slice.direct.value.map((entry) => entry.slug)).toEqual(['features'])

    branch.value = 'sweep'
    await settle()
    // The transitive view arrives computed — this client never re-derives it.
    expect(slice.transitive.value.map((entry) => entry.slug)).toEqual(['plot'])

    const before = daemon.calls.filter((call) => call.method === 'cells.list').length
    branch.value = 'main'
    await settle()
    expect(daemon.calls.filter((call) => call.method === 'cells.list')).toHaveLength(before)

    socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 5,
      transaction: transaction(5),
    })
    await settleJournal()
    expect(daemon.calls.filter((call) => call.method === 'cells.list').length).toBeGreaterThan(
      before,
    )
    scope.stop()
  })
})

// --- run logs ----------------------------------------------------------------

describe('run logs', () => {
  it('hands a late joiner the tail, then the live chunks after it', async () => {
    const { session, stream, socket } = await attach()
    // Buffered before anything asked for this console — the case the daemon's
    // own ring cannot cover, because this client was already connected.
    socket.deliver(logFrame(1, 'epoch 1\n'))
    socket.deliver(logFrame(2, 'epoch 2\n'))

    const runId = ref<string | null>('run-1')
    const scope = effectScope()
    const logs = scope.run(() => useRunLogs(session, stream, runId))!
    await nextTick()

    expect(logs.text.value).toBe('epoch 1\nepoch 2\n')

    socket.deliver(logFrame(3, 'epoch 3\n'))
    expect(logs.text.value).toBe('epoch 1\nepoch 2\nepoch 3\n')
    scope.stop()
  })

  it('drops a tail the daemon re-delivered after a reconnect', () => {
    const ring = new LogRing()

    expect(ring.append(logFrame(1, 'a'))).toBe(true)
    expect(ring.append(logFrame(2, 'b'))).toBe(true)
    expect(ring.append(logFrame(1, 'a'))).toBe(false)
    expect(ring.append(logFrame(2, 'b'))).toBe(false)
    expect(ring.append(logFrame(3, 'c'))).toBe(true)

    expect(ring.tail(FLOW, 'run-1').map((chunk) => chunk.text)).toEqual(['a', 'b', 'c'])
  })

  it('holds a tail and not a transcript, and only for the recent runs', () => {
    const ring = new LogRing(2, 2)
    for (const seq of [1, 2, 3]) ring.append(logFrame(seq, `${seq}`))
    expect(ring.tail(FLOW, 'run-1').map((chunk) => chunk.text)).toEqual(['2', '3'])

    ring.append(logFrame(1, 'x', 'run-2'))
    ring.append(logFrame(1, 'y', 'run-3'))
    expect(ring.tail(FLOW, 'run-1')).toEqual([])
    expect(ring.tail(FLOW, 'run-3').map((chunk) => chunk.text)).toEqual(['y'])
  })
})

// --- ops ---------------------------------------------------------------------

describe('mutating ops', () => {
  it('carries an intent on every verb the workbench drives', async () => {
    const { session, daemon } = await attach()
    const ops = useFlowOps(session)

    await ops.run('train_model', { branch: 'main' })
    await ops.edit('features', 'class F: ...', { branch: 'main', base: 'H' })
    await ops.addCell({ branch: 'main', after: 'features' })
    await ops.deleteCell('plot', { branch: 'main' })
    await ops.rename('plot', 'roc_curve', { branch: 'main' })
    await ops.fork('sweep', 'main')
    await ops.checkout('sweep')
    await ops.rewind(4, { branch: 'main' })
    await ops.adopt('train_model', 'sweep', { branch: 'main' })
    await ops.archive('sweep')
    await ops.promote('train_model.run', 'main')
    await ops.addPackages(['lightgbm'])
    await ops.removePackages(['lightgbm'])

    const mutations = daemon.calls.filter((call) => call.method !== 'flow.open')
    expect(mutations).toHaveLength(13)
    for (const call of mutations) {
      expect(String(call.params.intent ?? '')).not.toBe('')
    }
    expect(mutations[0].params).toMatchObject({ target: 'train_model', intent: 'run train_model' })
    expect(mutations[1].params).toMatchObject({ base: 'H', intent: 'edited features' })
  })

  it('reads a force rerun as its own intent, never as an ordinary run', async () => {
    const { session, daemon } = await attach()

    await useFlowOps(session).run('train_model', { branch: 'main', force: true })

    expect(daemon.calls.at(-1)?.params).toMatchObject({
      force: true,
      intent: 'force rerun train_model',
    })
  })

  it('leaves the daemon reported as live when it refuses a verb', async () => {
    const transport = async (): Promise<Response> =>
      ({
        ok: false,
        status: 400,
        json: async () => ({
          error: { message: 'no cell named `nope` on `main`', kind: 'CellNotFound' },
        }),
      }) as unknown as Response
    const api = new FlowApi({ token: 't', fetch: transport })
    const stream = new FlowStream({ token: 't', open: () => new FakeSocket(), schedule: () => {} })
    const session = useFlowSession({ api, stream, flow: 'churn' })

    await expect(session.request('cells.show', { slug: 'nope' })).rejects.toThrow(
      'no cell named `nope` on `main`',
    )
    // A refusal it named is proof the daemon is there — only a transport
    // failure says otherwise.
    expect(session.reachable.value).toBe(true)
  })

  it('reports a transport failure as the daemon being unreachable', async () => {
    const api = new FlowApi({
      token: 't',
      fetch: async () => {
        throw new TypeError('failed to fetch')
      },
    })
    const stream = new FlowStream({ token: 't', open: () => new FakeSocket(), schedule: () => {} })
    const session = useFlowSession({ api, stream, flow: 'churn' })

    await expect(session.attach()).rejects.toBeInstanceOf(DaemonUnreachable)
    expect(session.reachable.value).toBe(false)
    expect(session.state.value).toBe('daemon-down')
  })
})

// --- selection and focus ------------------------------------------------------

describe('selection', () => {
  const route = (query: Record<string, string> = {}, path = `/flow/${FLOW}`) =>
    ({ path, query }) as unknown as RouteLocationNormalizedLoaded

  it('opens the notebook when the route is the notebook, without a parameter', async () => {
    const { session } = await attach()
    const scope = effectScope()
    const selection = scope.run(() =>
      useSelection(route({}, `/flow/${FLOW}/notebook`), {
        session,
        defaultBranch: ref('main'),
        report: false,
      }),
    )!

    expect(selection.view.value).toBe('notebook')
    selection.view.value = 'canvas'
    expect(selection.path()).toBe(`/flow/${FLOW}`)
    scope.stop()
  })

  it('reads the URL, mirrors it back, and reports the focus to the daemon', async () => {
    vi.useFakeTimers()
    try {
      const { session, daemon } = await attach()
      const scope = effectScope()
      const selection = scope.run(() =>
        useSelection(route({ asset: 'features', view: 'notebook', state: 'running' }), {
          session,
          defaultBranch: ref('main'),
        }),
      )!

      expect(selection.selectedSlug.value).toBe('features')
      expect(selection.view.value).toBe('notebook')
      expect(selection.viewedBranch.value).toBe('main')

      selection.viewedBranch.value = 'sweep'
      selection.compared.value = ['main', 'sweep']
      await nextTick()

      // Branch by name and cell by slug — the addressing story, in the URL.
      // `state=` survives: it is what keeps a gallery link on fixtures, and
      // losing it on the first click would change the data under the reader.
      expect(selection.query()).toBe(
        'asset=features&branch=sweep&compare=main%2Csweep&state=running',
      )
      // Which view is up is the route, so a notebook link opens the notebook.
      expect(selection.path()).toBe(`/flow/${FLOW}/notebook`)

      // Debounced: dragging across a canvas is one focus, not forty.
      expect(daemon.calls.filter((call) => call.method === 'set_focus')).toHaveLength(0)
      vi.advanceTimersByTime(300)
      await settle()
      const reports = daemon.calls.filter((call) => call.method === 'set_focus')
      expect(reports).toHaveLength(1)
      expect(reports[0].params).toMatchObject({
        branch: 'sweep',
        asset: 'features',
        compare: ['main', 'sweep'],
      })
      scope.stop()
    } finally {
      vi.useRealTimers()
    }
  })
})

// --- toasts ------------------------------------------------------------------

describe('coalesced toasts', () => {
  it('folds a burst sharing one intent into a single line', () => {
    const burst = Array.from({ length: 40 }, (_, index) =>
      transaction(index + 1, { intent: 'wire the feature pipeline' }),
    )

    const plans = coalesceTransactions(burst)

    expect(plans).toHaveLength(1)
    expect(plans[0].count).toBe(40)
    expect(plans[0].summary).toBe('wire the feature pipeline')
  })

  it('never folds the user’s failure, and labels a coarse offline transaction as one', () => {
    const plans = coalesceTransactions([
      transaction(1, { intent: 'train the model' }),
      transaction(2, {
        intent: 'train the model',
        actor: 'user',
        ops: [
          {
            op: 'run_recorded',
            mat_id: 'm1',
            uid: 'u1',
            version_id: 'v1',
            branch_id: 'b1',
            memo_key: 'k',
            state: 'failed',
            inputs: {},
            outputs: {},
            identity_dependent: false,
            external: false,
            env_lock_hash: null,
            cost_seconds: 2,
            log_ref: 'l1',
            started_step: 1,
            finished_step: 2,
          },
        ],
      }),
      transaction(3, { intent: 'offline edits: 4 cells changed', offline: true }),
    ])

    expect(plans.map((plan) => plan.severity)).toEqual(['secondary', 'error', 'warn'])
    expect(plans[2].summary).toBe('Edits made while lumlflow was stopped')
  })

  it('demotes an agent’s failure to the card rather than interrupting for it', () => {
    // The chip goes `failed` and the traceback fills the card's logs either
    // way. An agent iterating through a broken state is working, and a toast
    // per pass teaches the reader to dismiss the one that mattered.
    const failing = (actor: string) =>
      transaction(2, {
        actor,
        intent: `${actor} ran train_model`,
        ops: [
          {
            op: 'run_recorded',
            mat_id: 'm1',
            uid: 'u1',
            version_id: 'v1',
            branch_id: 'b1',
            memo_key: 'k',
            state: 'failed',
            inputs: {},
            outputs: {},
            identity_dependent: false,
            external: false,
            env_lock_hash: null,
            cost_seconds: 2,
            log_ref: 'l1',
            started_step: 1,
            finished_step: 2,
          },
        ],
      })

    expect(coalesceTransactions([failing('claude-1')])).toEqual([])
    expect(coalesceTransactions([failing('user')]).map((plan) => plan.summary)).toEqual([
      'Run failed',
    ])
  })

  it('folds reactivity’s own runs into one line however many cells it refreshed', () => {
    // Its intents are per-cell, so grouping by intent would greet every edit
    // with a stack of toasts for one thing that happened.
    const plans = coalesceTransactions([
      transaction(1, { actor: 'auto', intent: 'ran features' }),
      transaction(2, { actor: 'auto', intent: 'ran plot' }),
      transaction(3, { actor: 'auto', intent: 'ran summary' }),
    ])

    expect(plans).toHaveLength(1)
    expect(plans[0].summary).toBe('Refreshed automatically')
    expect(plans[0].detail).toBe('3 cells')
    expect(plans[0].severity).toBe('secondary')
  })

  it('never interrupts for a run reactivity failed — the card wears that', () => {
    const plans = coalesceTransactions([
      transaction(1, {
        actor: 'auto',
        intent: 'features failed',
        ops: [
          {
            op: 'run_recorded',
            mat_id: 'm1',
            uid: 'u1',
            version_id: 'v1',
            branch_id: 'b1',
            memo_key: 'k',
            state: 'failed',
            inputs: {},
            outputs: {},
            identity_dependent: false,
            external: false,
            env_lock_hash: null,
            cost_seconds: 2,
            log_ref: 'l1',
            started_step: 1,
            finished_step: 2,
          },
        ],
      }),
    ])

    expect(plans).toEqual([])
  })
})

// --- token and the source switch ----------------------------------------------

describe('the daemon token', () => {
  function storage(): Pick<Storage, 'getItem' | 'setItem'> & { held: Record<string, string> } {
    const held: Record<string, string> = {}
    return {
      held,
      getItem: (key: string) => held[key] ?? null,
      setItem: (key: string, value: string) => {
        held[key] = value
      },
    }
  }

  it('takes the token out of the URL and keeps it', () => {
    const kept = storage()
    const stripped: string[] = []

    const token = resolveToken({
      search: '?token=abc123&branch=sweep',
      storage: kept,
      strip: (url) => stripped.push(url),
    })

    expect(token).toBe('abc123')
    // Out of the address bar, so it never reaches a bookmark or a screenshot.
    expect(stripped).toEqual(['?branch=sweep'])
    expect(resolveToken({ search: '?branch=sweep', storage: kept })).toBe('abc123')
  })

  /** An open tab is not logged out by the build that moved where this lives. */
  it('adopts the token an earlier build left in the tab-scoped storage', () => {
    const kept = storage()
    const before = storage()
    before.held[TOKEN_STORAGE_KEY] = 'abc123'

    expect(resolveToken({ search: '', storage: kept, previous: before })).toBe('abc123')
    // Adopted, so the reads after it no longer depend on that storage at all.
    expect(kept.held[TOKEN_STORAGE_KEY]).toBe('abc123')
    expect(resolveToken({ search: '', storage: kept })).toBe('abc123')
  })

  it('answers with none when neither the URL nor storage holds one', () => {
    expect(resolveToken({ search: '', storage: storage(), previous: storage() })).toBeNull()
  })

  /**
   * The address `lumlflow ui` prints is whichever page it opens, and a click
   * from there to the workspace is a router navigation that carries no query.
   * So the key is banked wherever the tab entered, and everything else about
   * that address survives the strip.
   */
  it('banks the token from any entry route, keeping the rest of the address', () => {
    window.history.replaceState(null, '', '/experiments?token=abc123&sort=name#latest')

    expect(browserToken()).toBe('abc123')

    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('abc123')
    expect(window.location.pathname).toBe('/experiments')
    expect(window.location.search).toBe('?sort=name')
    expect(window.location.hash).toBe('#latest')
    // And the flow surfaces, reading it later from a route with no query.
    expect(browserToken()).toBe('abc123')

    window.localStorage.clear()
    window.history.replaceState(null, '', '/')
  })
})

/**
 * The cursor is the other half of the catch-up marker: without one kept across
 * reopens, a tab catches up from zero every time and is by construction never
 * behind — which is how "N changes since you were here" came to never appear
 * in the one case it exists for.
 */
describe('the reopen cursor', () => {
  function storage(): CursorStorage & { held: Record<string, string> } {
    const held: Record<string, string> = {}
    return {
      held,
      getItem: (key: string) => held[key] ?? null,
      setItem: (key: string, value: string) => {
        held[key] = value
      },
    }
  }

  it('remembers where a flow got to, per flow', () => {
    const kept = storage()

    writeCursor('churn.flow', 42, kept)
    writeCursor('sales.flow', 7, kept)

    expect(readCursor('churn.flow', kept)).toBe(42)
    expect(readCursor('sales.flow', kept)).toBe(7)
    expect(readCursor('never-opened.flow', kept)).toBeNull()
  })

  /** A browser that holds nothing costs a marker, never the workbench. */
  it('reads as a first load wherever storage is unavailable or nonsense', () => {
    expect(readCursor('churn.flow', null)).toBeNull()

    const kept = storage()
    kept.held[cursorKey('churn.flow')] = 'not a step'
    expect(readCursor('churn.flow', kept)).toBeNull()

    const refuses: CursorStorage = {
      getItem: () => {
        throw new Error('this origin holds nothing')
      },
      setItem: () => {
        throw new Error('this origin holds nothing')
      },
    }
    expect(readCursor('churn.flow', refuses)).toBeNull()
    expect(() => writeCursor('churn.flow', 3, refuses)).not.toThrow()
  })

  /** End to end: what one session banked is the gap the next one measures. */
  it('turns a step banked by one session into the next session’s marker', async () => {
    const kept = storage()
    writeCursor(FLOW, 8, kept)

    const daemon = fakeDaemon({ 'flow.open': () => flowStatus() })
    const sockets: FakeSocket[] = []
    const stream = new FlowStream({
      token: 'the-token',
      open: () => {
        const socket = new FakeSocket()
        sockets.push(socket)
        return socket
      },
      schedule: () => {},
    })
    const session = useFlowSession({
      api: daemon.api,
      stream,
      flow: 'churn',
      seenStep: readCursor(FLOW, kept),
    })
    await session.attach()
    sockets[0].open()
    sockets[0].deliver({ channel: 'journal', type: 'caught_up', flow: FLOW, step: 20, running: [] })

    expect(session.changesBehind.value).toBe(12)
  })
})

describe('the fixture-vs-live switch', () => {
  it('stays on fixtures for the gallery variants, which ask for them outright', () => {
    expect(selectSource({ query: { state: 'running' } }, 'abc')).toBe('fixture')
    expect(selectSource({ query: { source: 'fixture' } }, 'abc')).toBe('fixture')
    expect(selectSource({ query: { source: 'fixture' } }, null)).toBe('fixture')
  })

  it('goes live when a token is in hand', () => {
    expect(selectSource({ query: {} }, 'abc')).toBe('live')
    expect(selectSource({ query: { source: 'live' } }, 'abc')).toBe('live')
  })

  // A tab with no token cannot have a live session, and standing it on the
  // fixture would put another flow's cells on screen under this one's name.
  it('is unconnected without a token, rather than quietly showing the fixture', () => {
    expect(selectSource({ query: {} }, null)).toBe('unconnected')
    expect(selectSource({ query: { source: 'live' } }, null)).toBe('unconnected')
  })
})
