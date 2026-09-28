/**
 * The authoritative session state: one flow, one cursor, one socket.
 *
 * Everything live is a journal subscription. The daemon stamps every
 * transaction with the flow-global `step`, this holds the highest it has seen,
 * and a reconnect replays from it — so a dropped socket and a laptop opened the
 * next morning are the same code path, and reopening is a latency event rather
 * than a refetch. Transactions are keyed by step and applied idempotently,
 * which is what makes a replayed session equal to a freshly loaded one.
 *
 * Nothing here derives a verdict. Staleness, preflight costs and `settled`
 * arrive computed from the daemon; what this composable adds is the shape of
 * the connection itself — what is reachable, what is registered, what is
 * running, and how far behind the reader is.
 *
 * `request` is the door every other live composable calls through, so that
 * "lumlflow is not answering" is one fact this session holds rather than five
 * each surface discovers separately.
 */

import { computed, getCurrentScope, onScopeDispose, ref, shallowRef } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import { DaemonUnreachable, FlowApi } from '@/flow/api/client'
import type { FlowMethod, FlowMethods } from '@/flow/api/client'
import { FlowStream } from '@/flow/api/stream'
import type { StreamStatus } from '@/flow/api/stream'
import { rejectToken } from '@/flow/api/token'
import type { FlowStatus, StateFrame, StreamFrame, Transaction } from '@/flow/api/types'
import type { FlowState } from '../model/types'
import { degradedStates, flowState } from './degraded'
import type { DegradedKind, SessionFacts } from './degraded'

/** Enough history for the intent timeline; the journal itself is never pruned. */
export const KEPT_TRANSACTIONS = 200

/**
 * How long a run of transactions is given to finish before the reads that
 * depend on it go out again.
 *
 * The journal arrives one frame per transaction, and a reconnect replays every
 * one the client missed. Treating each frame as its own invalidation made the
 * cost of opening a flow scale with the length of its history: a hundred-step
 * journal meant a hundred slice reads, a hundred branch-tree reads, and every
 * card on screen dropping its source and its preview a hundred times before
 * the first of them finished arriving. A burst is one movement of the store,
 * and this is the quiet point that says so — the same shape as the daemon's own
 * watcher debounce, three orders of magnitude smaller because the burst here is
 * frames off a socket rather than a person typing.
 */
export const SETTLE_MS = 60

export interface RegisteredAgent {
  actor: string
  label: string
}

export interface RunningCell {
  run_id: string
  slug: string
  /** Branches waiting on this run: 1 is only the branch that asked for it. */
  awaiting: number
}

export interface FlowSessionOptions {
  api: FlowApi
  stream: FlowStream
  /** The flow to attach to. Omitted addresses a single-flow workspace. */
  flow?: string
  /**
   * Where this client got to last time, if it remembers. Absent, the first
   * catch-up is the baseline and a first load is never "behind".
   */
  seenStep?: number | null
  /** Identity the persisted catch-up marker was recorded under. */
  seenFlowId?: string
}

export interface FlowSessionHandle {
  brief: Ref<FlowStatus | null>
  stream: Ref<StreamStatus>
  reachable: Ref<boolean>
  /** The daemon's head step for this flow — what a cursor is measured against. */
  head: Ref<number>
  /**
   * The head once it has stopped moving — what a read re-runs against.
   *
   * Every surface that has to re-read when the store moves watches this rather
   * than `head`: `head` is the live position and answers "how far behind is
   * this reader", while a burst of transactions is one movement to re-read
   * after, not one per frame.
   */
  revision: Ref<number>
  cursor: ComputedRef<number>
  transactions: Ref<Transaction[]>
  running: Ref<RunningCell[]>
  /** Failed runs per cell since its last good one — the folded repair history. */
  attempts: Ref<Record<string, number>>
  agent: Ref<RegisteredAgent | null>
  changesBehind: ComputedRef<number>
  facts: ComputedRef<SessionFacts>
  state: ComputedRef<FlowState>
  degraded: ComputedRef<DegradedKind[]>
  /**
   * How the daemon addresses this flow: its path under the workspace, or its
   * own absolute path above it. Every frame is keyed by it, and every verb
   * names it — two flows can be called `sales` and only one is in here.
   */
  path: ComputedRef<string>
  /** Subscribe to live-only state hints for this flow. */
  onState: (handler: (frame: StateFrame) => void) => () => void
  attach: () => Promise<void>
  detach: () => void
  markSeen: () => void
  request: <M extends FlowMethod>(
    method: M,
    params: FlowMethods[M]['params'],
  ) => Promise<FlowMethods[M]['result']>
  downloadUrl: (branch: string, target: string) => string
}

export function useFlowSession(options: FlowSessionOptions): FlowSessionHandle {
  const brief = shallowRef<FlowStatus | null>(null)
  const stream = ref<StreamStatus>('connecting')
  const reachable = ref(true)
  const head = ref(0)
  const revision = ref(0)
  const seen = ref<number | null>(options.seenStep ?? null)
  /** How far behind this client was when it caught up. Frozen until dismissed. */
  const arrears = ref(0)
  /** Past the catch-up and watching live — what makes a frame "seen". */
  const watching = ref(false)
  const transactions = ref<Transaction[]>([])
  const running = ref<RunningCell[]>([])
  const attempts = ref<Record<string, number>>({})
  const agent = ref<RegisteredAgent | null>(null)
  const stateSubscribers = new Set<(frame: StateFrame) => void>()
  let reachabilityEpoch = 0

  const path = computed(() => brief.value?.path ?? '')
  const cursor = computed(() => (path.value ? options.stream.cursor(path.value) : 0))

  let settling: ReturnType<typeof setTimeout> | null = null

  /**
   * The head has moved. Announce it once the frames stop coming — a replay and
   * an agent's edit burst both arrive as a run of them, and each is one thing
   * that happened to the store.
   *
   * The timer is the floor, not the mechanism: a subscription cycle ends with a
   * catch-up frame, and that is the exact end of a replay, so the common case
   * publishes on the frame rather than on the clock. The debounce is what
   * covers a client that is fed transactions without one and an edit burst
   * arriving live, where nothing announces the end but the quiet.
   */
  function settle(): void {
    if (settling !== null) clearTimeout(settling)
    settling = setTimeout(published, SETTLE_MS)
  }

  function published(): void {
    if (settling !== null) clearTimeout(settling)
    settling = null
    revision.value = head.value
  }

  function resetFlowState(): void {
    if (settling !== null) clearTimeout(settling)
    settling = null
    head.value = 0
    revision.value = 0
    seen.value = 0
    arrears.value = 0
    watching.value = false
    transactions.value = []
    running.value = []
    attempts.value = {}
    agent.value = null
  }

  async function request<M extends FlowMethod>(
    method: M,
    params: FlowMethods[M]['params'],
  ): Promise<FlowMethods[M]['result']> {
    const epoch = reachabilityEpoch
    try {
      const answer = await options.api.call(method, params)
      if (epoch === reachabilityEpoch) reachable.value = true
      return answer
    } catch (failure) {
      // Only a transport failure says anything about the daemon. A refusal it
      // named is proof it is very much there.
      if (epoch === reachabilityEpoch) {
        reachable.value = !(failure instanceof DaemonUnreachable)
      }
      throw failure
    }
  }

  function apply(transaction: Transaction): void {
    head.value = Math.max(head.value, transaction.step)
    settle()
    // Watched as it lands, so this client has seen it — but only once the
    // catch-up is past. A replay arrives as transactions too, and those are
    // precisely the ones the reader was away for: marking them seen on the way
    // in is marking the gap seen before anyone has been shown it.
    if (watching.value) seen.value = head.value
    const held = transactions.value
    // Keyed by step: a replay re-delivers what this client already has, and
    // applying it twice is what would make a reconnected session differ from a
    // fresh one.
    const at = held.findIndex((entry) => entry.step === transaction.step)
    if (at >= 0) {
      held[at] = transaction
    } else {
      held.push(transaction)
      held.sort((left, right) => left.step - right.step)
      if (held.length > KEPT_TRANSACTIONS) held.splice(0, held.length - KEPT_TRANSACTIONS)
    }
    transactions.value = [...held]
    for (const op of transaction.ops) {
      if (op.op === 'agent_begin') {
        agent.value = { actor: op.actor, label: op.label }
      } else if (op.op === 'agent_end' && agent.value?.actor === op.actor) {
        agent.value = null
      }
    }
  }

  function receive(frame: StreamFrame): void {
    if (!('channel' in frame) || frame.channel !== 'journal') return
    if (frame.type === 'lagged') return
    if (frame.flow !== path.value) return
    if (frame.type === 'state') {
      for (const subscriber of [...stateSubscribers]) subscriber(frame)
      return
    }
    head.value = Math.max(head.value, frame.step)
    settle()
    if (frame.type === 'transaction') {
      apply(frame.transaction)
      return
    }
    if (frame.type === 'caught_up') {
      // The runs in flight arrive here rather than as events, because a
      // lifecycle nobody journaled is a lifecycle no cursor replays.
      running.value = frame.running.map((entry) => ({ ...entry, awaiting: entry.awaiting ?? 1 }))
      // The gap this client was away for, fixed at the moment it caught up. It
      // is the whole meaning of the marker — "since you were here" — so it must
      // not keep growing afterwards, while the reader is here watching the feed
      // fill in. A first-ever load was never away and is never behind.
      arrears.value = seen.value === null ? 0 : Math.max(0, frame.step - seen.value)
      seen.value = frame.step
      watching.value = true
      // The replay is over, and this frame says so — the reads that depend on
      // the journal go out now rather than after the debounce that was only
      // ever standing in for this.
      published()
      return
    }
    // The kernel process starting or stopping. The brief carries the state it
    // had when this tab opened, and a kernel starts on the first gesture that
    // needs one — so without this the workbench says "kernel not started" for
    // the rest of the session, however many runs it has watched go by.
    if (frame.event === 'kernel_state') {
      const held = brief.value
      if (held && frame.kernel) {
        brief.value = { ...held, kernel: { ...held.kernel, state: frame.kernel } }
      }
      return
    }
    if (frame.event === 'started' && frame.run_id) {
      running.value = [
        ...running.value.filter((entry) => entry.run_id !== frame.run_id),
        { run_id: frame.run_id, slug: frame.slug ?? '', awaiting: frame.awaiting ?? 1 },
      ]
    } else if (frame.event === 'awaiting' && frame.run_id) {
      // Branches join and leave a run while it executes, and the stop gesture's
      // wording turns on how many are left — so the count is followed, not read
      // once when the run started.
      const at = frame.run_id
      running.value = running.value.map((entry) =>
        entry.run_id === at ? { ...entry, awaiting: frame.awaiting ?? entry.awaiting } : entry,
      )
    } else if (frame.event === 'materialized' || frame.event === 'failed') {
      const ending = running.value.find((entry) => entry.run_id === frame.run_id)
      tally(frame.slug ?? ending?.slug, frame.event === 'failed')
      running.value = running.value.filter((entry) => entry.run_id !== frame.run_id)
    }
  }

  /**
   * Failed runs of a cell since its last good one. An agent iterating through a
   * broken state is demoted rather than announced, and this is what lets the
   * card fold those attempts into a line instead of losing them: the store
   * records each failure as a materialization, but which of them the reader has
   * already watched go by is only knowable from here.
   */
  function tally(slug: string | undefined, failed: boolean): void {
    if (!slug) return
    const held = { ...attempts.value }
    if (failed) held[slug] = (held[slug] ?? 0) + 1
    else delete held[slug]
    attempts.value = held
  }

  function watchStatus(next: StreamStatus): void {
    stream.value = next
    if (next === 'open') {
      reachabilityEpoch += 1
      reachable.value = true
    }
    // Every status change opens a new subscription cycle, and a replay is on
    // its way through it. Whatever that replay carries is what this client was
    // away for, however briefly — the catch-up at the end of it is what says
    // the reader is watching again.
    watching.value = false
    // A drop is not a verdict about the server; one round-trip is. Without this
    // probe the workbench would either cry "not running" at every hiccup or
    // never say it at all.
    if (next === 'dropped') void request('ping', {}).catch(() => {})
    // A refusal is the opposite of silence: something answered, and what it
    // refused was this tab's key. Left as unreachable — which is where a drop
    // just before the refusal leaves it — the tab would tell a reader lumlflow
    // is not running while it is, and offer the one remedy that cannot help.
    // The socket's 4401 is the 401 door in another spelling, so the token goes
    // the same way and the surface says what actually fixes this.
    if (next === 'refused') {
      reachabilityEpoch += 1
      reachable.value = true
      rejectToken()
    }
  }

  const unlisten = [options.stream.onFrame(receive), options.stream.onStatus(watchStatus)]

  /**
   * Opening the flow is what attaches the session — there is no connect verb
   * anywhere, and the kernel still waits for the first gesture that needs one.
   */
  async function attach(): Promise<void> {
    const opened = await request('flow.open', { flow: options.flow })
    const previousFlowId = brief.value?.flow_id ?? options.seenFlowId
    if (previousFlowId !== undefined && previousFlowId !== opened.flow_id) resetFlowState()
    brief.value = opened
    options.stream.connect()
    options.stream.watchJournal(opened.path, opened.flow_id)
  }

  function detach(): void {
    for (const stop of unlisten.splice(0)) stop()
    stateSubscribers.clear()
    if (settling !== null) clearTimeout(settling)
    settling = null
    options.stream.close()
  }

  const changesBehind = computed(() => arrears.value)

  const facts = computed<SessionFacts>(() => ({
    reachable: reachable.value,
    stream: stream.value,
    kernel: brief.value?.kernel.state ?? 'stopped',
    running: running.value.length,
    paired: agent.value !== null,
    changesBehind: changesBehind.value,
  }))

  if (getCurrentScope()) onScopeDispose(detach)

  return {
    brief,
    stream,
    reachable,
    head,
    revision,
    cursor,
    transactions,
    running,
    attempts,
    agent,
    changesBehind,
    facts,
    state: computed(() => flowState(facts.value)),
    degraded: computed(() => degradedStates(facts.value)),
    path,
    onState: (handler) => {
      stateSubscribers.add(handler)
      return () => {
        stateSubscribers.delete(handler)
      }
    },
    attach,
    detach,
    markSeen: () => {
      seen.value = head.value
      arrears.value = 0
    },
    request,
    downloadUrl: (branch, target) =>
      options.api.downloadUrl({ flow: path.value, branch, target }),
  }
}
