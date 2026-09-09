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
