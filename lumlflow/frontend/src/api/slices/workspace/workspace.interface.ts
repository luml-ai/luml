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

export type FlowReactivity = 'lazy' | 'auto'

export interface FlowSettingsReport {
  reactivity: FlowReactivity
  eager_cost_threshold_s: number
}

export interface SavedSettings {
  flow: string
  settings: FlowSettingsReport
}

export interface OpenedFlow {
  flow: string
  flow_id: string
  path: string
}

export interface TableBlock {
  block: 'table'
  columns: string[]
  dtypes: string[]
  rows: (string | number | boolean | null)[][]
  total_rows: number
  total_columns: number
}

export interface SeriesBlock {
  block: 'series'
  name: string
  points: [number, number | null][]
  total_points: number
}

export interface ImageBlock {
  block: 'image'
  mime: string
  data: string
}

export interface MarkdownBlock {
  block: 'markdown'
  text: string
}

export interface KvBlock {
  block: 'kv'
  entries: Record<string, string | number | boolean | null>
}

export interface FileBlock {
  block: 'file'
  name: string
  size: number
  content_type: string
}

export type PreviewBlock = TableBlock | SeriesBlock | ImageBlock | MarkdownBlock | KvBlock | FileBlock

export interface StoredPreview {
  schema: number
  kind: string
  blocks: PreviewBlock[]
  truncated: boolean
}

export interface AssetPreview {
  flow: string
  branch: string
  slug: string
  output: string
  state: CellStaleState
  kind: string | null
  size: number | null
  persisted: boolean | null
  preview: StoredPreview | null
}

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

export interface EditedCellFlag {
  code: string
  detail: string | null
}

export interface EditedCell {
  slug: string
  branch: string
  definition_hash: string
  written_to_files: boolean
  flags: EditedCellFlag[]
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

export interface EvalError {
  type: string
  message: string
  traceback: string
}

export interface EvalResult {
  flow: string
  branch: string
  repr: string | null
  output: string
  names: string[]
  error: EvalError | null
}
