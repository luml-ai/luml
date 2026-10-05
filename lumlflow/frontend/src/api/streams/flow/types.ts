import type { AgentSessionRecord } from '@/flow/api/types'

export type MaterializationState = 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface Transaction {
  step: number
  ts: string
  actor: string
  intent: string
  offline: boolean
  settled: boolean
  branch: string | null
  ops: unknown[]
}

export interface TransactionFrame {
  channel: 'journal'
  type: 'transaction'
  flow: string
  step: number
  transaction: Transaction
}

export interface KernelFrame {
  channel: 'journal'
  type: 'kernel'
  flow: string
  event: 'started' | 'progress' | 'materialized' | 'failed' | 'awaiting' | 'kernel_state'
  step: number
  run_id?: string
  slug?: string
  state?: MaterializationState
  cost_seconds?: number
  awaiting?: number
  kernel?: 'running' | 'stopped'
}

export type StateName = 'experiment_removed' | 'refreshing' | 'order_changed'

export interface StateFrame {
  channel: 'journal'
  type: 'state'
  state: StateName
  flow: string
  step: number
  lane?: string
  cell?: string
}

/**
 * Who is registered on the flow, and who is really connected. Pushed whenever
 * a registration commits or a leased connection drops; never replayed.
 */
export interface AgentsFrame {
  channel: 'journal'
  type: 'agents'
  flow: string
  step: number
  sessions: AgentSessionRecord[]
}

/**
 * A leased agent is inside a daemon call, or just left it. `tool` is the
 * daemon method and `slug` the cell it named, if it named one. One entry per
 * actor; never replayed, a late joiner reads the same off the catch-up.
 */
export interface AgentActivity {
  actor: string
  label: string
  tool: string
  slug: string | null
}

export interface ActivityFrame extends AgentActivity {
  channel: 'journal'
  type: 'activity'
  flow: string
  step: number
  phase: 'started' | 'ended'
}

/**
 * One agent holding one cell of one lane: the cell its last call named. Other
 * agents cannot change or run it until the holder names another cell,
 * disconnects, the lane is rewound, or `last` is `idle_after_s` behind.
 * `since` and `last` are epoch milliseconds.
 */
export interface AgentClaim {
  actor: string
  label: string
  slug: string
  branch: string
  branch_id: string
  since: number
  last: number
}

/** Every claim on the flow, whole. Replaces, never merges; never replayed. */
export interface ClaimsFrame {
  channel: 'journal'
  type: 'claims'
  flow: string
  step: number
  claims: AgentClaim[]
  idle_after_s: number
}

export interface CaughtUpFrame {
  channel: 'journal'
  type: 'caught_up'
  flow: string
  step: number
  running: { run_id: string; slug: string; awaiting?: number }[]
  activity?: AgentActivity[]
  claims?: AgentClaim[]
  claim_idle_s?: number
}

export interface LaggedFrame {
  channel: 'journal'
  type: 'lagged'
}

export interface LogFrame {
  channel: 'logs'
  flow: string
  run_id: string
  seq: number
  stream: 'stdout' | 'stderr'
  text: string
}

export interface StreamErrorFrame {
  type: 'error'
  message: string
}

export type StreamFrame =
  | TransactionFrame
  | KernelFrame
  | StateFrame
  | AgentsFrame
  | ActivityFrame
  | ClaimsFrame
  | CaughtUpFrame
  | LaggedFrame
  | LogFrame
  | StreamErrorFrame
