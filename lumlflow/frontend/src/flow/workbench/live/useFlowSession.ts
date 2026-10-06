import { computed, getCurrentScope, onScopeDispose, ref, shallowRef } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import { DaemonUnreachable, FlowApi } from '@/flow/api/client'
import type { FlowMethod, FlowMethods } from '@/flow/api/client'
import { FlowStream } from '@/flow/api/stream'
import type { StreamStatus } from '@/flow/api/stream'
import { rejectToken } from '@/flow/api/token'
import type {
  AgentActivity,
  AgentClaim,
  AgentSessionRecord,
  FlowStatus,
  StateFrame,
  StreamFrame,
  Transaction,
} from '@/flow/api/types'
import type { FlowState } from '../model/types'
import { degradedStates, flowState } from './degraded'
import type { DegradedKind, SessionFacts } from './degraded'

export const KEPT_TRANSACTIONS = 200

export const SETTLE_MS = 60

export interface RegisteredAgent {
  actor: string
  label: string
}

export interface RunningCell {
  run_id: string
  slug: string
  awaiting: number
}

export interface FlowSessionOptions {
  api: FlowApi
  stream: FlowStream
  flow?: string
  seenStep?: number | null
  seenFlowId?: string
}

export interface FlowSessionHandle {
  brief: Ref<FlowStatus | null>
  stream: Ref<StreamStatus>
  reachable: Ref<boolean>
  head: Ref<number>
  revision: Ref<number>
  cursor: ComputedRef<number>
  transactions: Ref<Transaction[]>
  running: Ref<RunningCell[]>
  attempts: Ref<Record<string, number>>
  agentSessions: Ref<AgentSessionRecord[]>
  agentActivity: Ref<AgentActivity[]>
  agentClaims: Ref<AgentClaim[]>
  agent: ComputedRef<RegisteredAgent | null>
  changesBehind: ComputedRef<number>
  facts: ComputedRef<SessionFacts>
  state: ComputedRef<FlowState>
  degraded: ComputedRef<DegradedKind[]>
  path: ComputedRef<string>
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
  const arrears = ref(0)
  const watching = ref(false)
  const transactions = ref<Transaction[]>([])
  const running = ref<RunningCell[]>([])
  const attempts = ref<Record<string, number>>({})
  const agentSessions = ref<AgentSessionRecord[]>([])
  const agentActivity = ref<AgentActivity[]>([])
  const agentClaims = ref<AgentClaim[]>([])
  const agent = computed<RegisteredAgent | null>(() => {
    const live = agentSessions.value.find((session) => session.leased)
    return live ? { actor: live.actor, label: live.label } : null
  })
  const stateSubscribers = new Set<(frame: StateFrame) => void>()
  let reachabilityEpoch = 0

  const path = computed(() => brief.value?.path ?? '')
  const cursor = computed(() => (path.value ? options.stream.cursor(path.value) : 0))

  let settling: ReturnType<typeof setTimeout> | null = null

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
    agentSessions.value = []
    agentActivity.value = []
    agentClaims.value = []
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
    // `agent_begin` and `agent_end` ops are not read here on purpose: a
    // registration says nothing about whether anybody is connected, and the
    // daemon's `agents` frame — which follows every one of them — does.
  }

  function receive(frame: StreamFrame): void {
    if (!('channel' in frame) || frame.channel !== 'journal') return
    if (frame.type === 'lagged') return
    if (frame.flow !== path.value) return
    if (frame.type === 'state') {
      for (const subscriber of [...stateSubscribers]) subscriber(frame)
      return
    }
    if (frame.type === 'agents') {
      agentSessions.value = frame.sessions
      return
    }
    if (frame.type === 'claims') {
      agentClaims.value = frame.claims
      return
    }
    if (frame.type === 'activity') {
      const others = agentActivity.value.filter((entry) => entry.actor !== frame.actor)
      agentActivity.value =
        frame.phase === 'started'
          ? [
              ...others,
              { actor: frame.actor, label: frame.label, tool: frame.tool, slug: frame.slug },
            ]
          : others
      return
    }
    head.value = Math.max(head.value, frame.step)
    settle()
    if (frame.type === 'transaction') {
      apply(frame.transaction)
      return
    }
    if (frame.type === 'caught_up') {
      running.value = frame.running.map((entry) => ({ ...entry, awaiting: entry.awaiting ?? 1 }))
      agentActivity.value = frame.activity ?? []
      agentClaims.value = frame.claims ?? []
      arrears.value = seen.value === null ? 0 : Math.max(0, frame.step - seen.value)
      seen.value = frame.step
      watching.value = true
      published()
      return
    }
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
    watching.value = false
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

  async function attach(): Promise<void> {
    const opened = await request('flow.open', { flow: options.flow })
    const previousFlowId = brief.value?.flow_id ?? options.seenFlowId
    if (previousFlowId !== undefined && previousFlowId !== opened.flow_id) resetFlowState()
    brief.value = opened
    agentSessions.value = opened.agent_sessions ?? []
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
    agentSessions,
    agentActivity,
    agentClaims,
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
    downloadUrl: (branch, target) => options.api.downloadUrl({ flow: path.value, branch, target }),
  }
}
