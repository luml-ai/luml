export interface WorkspaceFlow {
  name: string
  path: string
  relative_path: string
}

export interface WorkspaceListing {
  directory: string
  flows: WorkspaceFlow[]
}

export interface CreatedFlow {
  flow: string
  path: string
  warnings: string[]
}

export interface RenamedFlow {
  renamed: string
  path: string
  from: string
}

export interface DeletedFlow {
  deleted: string
  path: string
}

export interface DuplicatedFlow {
  flow: string
  path: string
}

export interface BranchLastIntent {
  ts: string
  step: number
}

export interface BranchRecord {
  branch: string
  branch_id: string
  parent: string | null
  forked_at_step: number
  parent_step: number | null
  archived: boolean
  checked_out: boolean
  cells: number
  last_intent: BranchLastIntent | null
  agent: string | null
}

export interface BranchTree {
  flow: string
  branch: string
  branches: BranchRecord[]
}

export interface SwitchedBranch {
  branch: string
}

export interface ForkedBranch {
  branch: string
  from_branch: string
}

export interface AgentSession {
  flow: string
  actor: string
  label: string
  leased: boolean
}

export interface EndedAgentSession {
  flow: string
  actor: string
  label: string
}

export interface UnplannedRunTarget {
  target: string
  error: string
}

export interface RanLane {
  path: string
  branch: string
  target: string
  targets: string[]
  executed: string[]
  cached: string[]
  pruned: string[]
  failed: string | null
  failures: string[]
  unplanned: UnplannedRunTarget[]
  abandoned: boolean
}

export interface CancelledRun {
  branch: string
  left: number
  stopped: boolean
  awaiting: number
}

export interface RanCell {
  path: string
  branch: string
  target: string
  executed: string[]
  cached: string[]
  pruned: string[]
  failed: string | null
  abandoned: boolean
}

export type CellStaleState = 'synced' | 'unsynced' | 'unmaterialized' | 'failed'

export interface CellSummary {
  slug: string
  state: CellStaleState
  primary: string | null
  kinds: Record<string, string>
  consumes: Record<string, string>
  cost_seconds: number | null
  causes: string[]
  reused: boolean
}

export interface CellsPage {
  flow: string
  branch: string
  cells: CellSummary[]
}

export interface RenamedCell {
  slug: string
  renamed_from: string
  branch: string
}

export interface CellDetail {
  slug: string
  source: string
}

export interface CellLogs {
  flow: string
  branch: string
  slug: string
  state: CellStaleState | null
  logs: string | null
}

export interface NewCell {
  slug: string
  branch: string
}

export interface DeletedCell {
  slug: string
  branch: string
}

export interface JournalTransactionOp {
  op: string
}

export interface JournalTransaction {
  step: number
  ts: string
  actor: string
  intent: string
  offline: boolean
  settled: boolean
  branch: string | null
  ops: JournalTransactionOp[]
}

export interface JournalPage {
  flow: string
  path: string
  cursor: number
  transactions: JournalTransaction[]
}
