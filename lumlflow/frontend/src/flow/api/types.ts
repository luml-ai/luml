
export type FlagCode =
  | 'dangling_ref'
  | 'ambiguous'
  | 'invalid'
  | 'incomplete'
  | 'divergent'
  | 'placeholder_slug'
  | 'hygiene'

export type DeclaredAssetType = 'model' | 'dataset' | 'experiment' | 'asset'
export type MaterializationState = 'running' | 'succeeded' | 'failed' | 'cancelled'
export type KindSource = 'declared' | 'matcher' | 'fallback'

export interface VersionFlag {
  code: FlagCode
  detail: string | null
}

export interface ConsumedRef {
  ref: string
  uid: string | null
  output: string | null
}

export interface OutputSpec {
  type: DeclaredAssetType
  kind: string | null
  persist: boolean
}

export interface CellManifest {
  classification: 'cell' | 'note'
  consumes: Record<string, ConsumedRef>
  produces: Record<string, OutputSpec>
  params: Record<string, unknown>
  volatility: string | null
  env_sensitive: boolean
}

export interface InputRef {
  uid: string
  output: string
  content_hash: string
  mat_id: string
}

export interface OutputRecord {
  content_hash: string
  kind: string
  kind_source: KindSource
  size: number
  preview_ref: string | null
  value_ref: string | null
  persisted: boolean
}

export interface FlowInitOp {
  op: 'flow_init'
  flow_id: string
  name: string
  language: 'python'
  schema_version: number
}

export interface CellAcceptedOp {
  op: 'cell_accepted'
  uid: string
  version_id: string
  slug: string
  definition_hash: string
  raw_source_ref: string
  bound_source_ref: string
  manifest: CellManifest
  parent_version_id: string | null
  copied_from: string | null
  author: string
  flags: VersionFlag[]
}

export interface CellRemovedOp {
  op: 'cell_removed'
  uid: string
  branch_id: string
}

export interface CellNotedOp {
  op: 'cell_noted'
  uid: string
  kind: 'projection_completed' | 'refresh_failed' | 'experiment_unclosed'
  sentence: string
  version_id: string | null
}

export interface SelectionSetOp {
  op: 'selection_set'
  branch_id: string
  uid: string
  version_id: string
  pinned: boolean
}

export interface BranchCreatedOp {
  op: 'branch_created'
  branch_id: string
  name: string
  parent_branch_id: string | null
  fork_step: number
}

export interface BranchArchivedOp {
  op: 'branch_archived'
  branch_id: string
}

export interface WorktreeBoundOp {
  op: 'worktree_bound'
  path: string
  branch_id: string
  actor: string | null
}

export interface RewoundOp {
  op: 'rewound'
  branch_id: string
  to_step: number
  selections: Record<string, string>
  baselines: Record<string, string>
}

export interface AdoptedOp {
  op: 'adopted'
  branch_id: string
  uid: string
  version_id: string
  from_branch_id: string
}

export interface RenamedOp {
  op: 'renamed'
  uid: string
  branch_id: string
  old_slug: string
  new_slug: string
}

export interface RunRecordedOp {
  op: 'run_recorded'
  mat_id: string
  uid: string
  version_id: string
  branch_id: string
  memo_key: string
  state: MaterializationState
  inputs: Record<string, InputRef>
  outputs: Record<string, OutputRecord>
  identity_dependent: boolean
  external: boolean
  env_lock_hash: string | null
  cost_seconds: number | null
  log_ref: string | null
  started_step: number
  finished_step: number | null
}

export interface MemoHitOp {
  op: 'memo_hit'
  branch_id: string
  uid: string
  version_id: string
  memo_key: string
  mat_id: string
}

export interface WorkspaceCodeChangedOp {
  op: 'workspace_code_changed'
  tree_hash: string
  previous_tree_hash: string | null
  changed_paths: string[]
  files: Record<string, string>
}

export interface EnvChangedOp {
  op: 'env_changed'
  lock_hash: string
  packages: Record<string, string>
  summary: string
}

export interface FlagSetOp {
  op: 'flag_set'
  flag: string
  version_id: string | null
  detail: string | null
}

export interface AgentBeginOp {
  op: 'agent_begin'
  actor: string
  label: string
}

export interface AgentEndOp {
  op: 'agent_end'
  actor: string
  label: string | null
}

export interface CheckpointedOp {
  op: 'checkpointed'
  branch_id: string
  step?: number | null
}

export type FlowOp =
  | FlowInitOp
  | CellAcceptedOp
  | CellRemovedOp
  | CellNotedOp
  | SelectionSetOp
  | BranchCreatedOp
  | BranchArchivedOp
  | WorktreeBoundOp
  | RewoundOp
  | AdoptedOp
  | RenamedOp
  | RunRecordedOp
  | MemoHitOp
  | WorkspaceCodeChangedOp
  | EnvChangedOp
  | FlagSetOp
  | AgentBeginOp
  | AgentEndOp
  | CheckpointedOp

export interface Transaction {
  step: number
  ts: string
  actor: string
  intent: string
  offline: boolean
  settled: boolean
  branch: string | null
  ops: FlowOp[]
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

export interface AgentSessionRecord {
  actor: string
  label: string
  begun_step: number
  leased: boolean
}

export interface AgentsFrame {
  channel: 'journal'
  type: 'agents'
  flow: string
  step: number
  sessions: AgentSessionRecord[]
}

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

export interface AgentClaim {
  actor: string
  label: string
  slug: string
  branch: string
  branch_id: string
  since: number
  last: number
}

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

export type StaleState = 'synced' | 'unsynced' | 'unmaterialized' | 'failed'

export type TrackerExperimentState = 'ok' | 'missing' | 'unreachable'

export interface TrackerExperiment {
  id: string
  group: string
  state: TrackerExperimentState
  url: string | null
  store: string
  tags: string[]
  sentence: string
  recorded_step: number | null
}

export interface CellSummary {
  uid?: string
  slug: string
  state: StaleState
  causes: string[]
  upstream: string[]
  transitive: boolean
  outputs: string[]
  kinds: Record<string, string>
  primary: string | null
  consumes: Record<string, string>
  note: boolean
  external: boolean
  flags: { code: FlagCode; detail: string | null }[]
  cost_seconds: number | null
  older_env: boolean
  reused: boolean
  created_step: number
  order: string
  changed_step: number
  eager: boolean
  auto_declined: AutoDeclined | null
  tracker: TrackerExperiment | null
}

export interface AutoDeclined {
  reason:
    | 'blocked'
    | 'never-timed'
    | 'too-expensive'
    | 'dangling-experiment'
    | 'unresolvable-reference'
    | 'refresh-failed'
  estimate_seconds: number
  untimed: string[]
  detail?: string
}

export interface CellProvenance {
  created_by: string
  created_step: number
  last_edited_by: string
  step: number
  intent: string | null
  attribution_uncertain: boolean
}

export interface MaterializedOutput {
  name: string
  kind: string
  kind_source: KindSource
  declared: DeclaredAssetType
  size: number
  persisted: boolean
}

export interface CellDetail extends CellSummary {
  branch: string
  definition_hash: string
  source: string
  doc: string
  params: Record<string, unknown>
  author: string
  produces: Record<string, OutputSpec>
  materialized: MaterializedOutput[]
  sdk_version_warning: string | null
  error: string | null
  failed_by: string | null
  provenance: CellProvenance
}

/**
 * A stored preview, as it crosses the wire: a versioned envelope over blocks.
 *
 * `blocks` is deliberately untyped here. The version is the field that says a
 * payload may hold shapes this build has never seen, so a client that declared
 * them typed would be asserting exactly what the envelope exists to doubt —
 * `live/preview.ts` validates them into renderable ones and says so when it
 * cannot.
 */
export interface StoredPreview {
  schema: number
  kind: string
  blocks: unknown[]
  truncated?: boolean
}

export interface AssetView {
  flow: string
  branch: string
  slug: string
  output: string
  state: StaleState
  kind: string | null
  size: number | null
  persisted: boolean | null
  preview: StoredPreview | null
  tracker: TrackerExperiment | null
}

export interface AssetPage {
  slug: string
  output: string
  kind: string
  page: {
    columns: string[]
    dtypes: string[]
    rows: (string | number | boolean | null)[][]
    offset: number
    total_rows: number
    total_columns: number
  }
}

export interface PublishTarget {
  organization_id: string
  orbit_id: string
  collection_id: string
  artifact: { name: string; description?: string; tags?: string[] }
}

export interface PublishedAsset {
  flow: string
  branch: string
  slug: string
  output: string
  job_id: string
  flavor: string | null
  size: number | null
}

export interface CellLogs {
  flow: string
  branch: string
  slug: string
  state: MaterializationState | null
  logs: string | null
}

export interface DiffSide {
  branch: string
  state: StaleState
  cost_seconds: number | null
  outputs: MaterializedOutput[]
}

export interface DiffVersionSide extends DiffSide {
  slug: string
  author: string
  step: number
  flags: FlagCode[]
  params: Record<string, unknown>
}

export interface DefinitionDiff {
  slug: string
  versions: DiffVersionSide[]
}

export interface MaterializationDiff {
  slug: string
  results: DiffSide[]
}

export interface ShapelessDiff {
  slug: string
  branches: Record<string, string | null>
}

export interface IntegrityWarning {
  kind: 'divergent-pin'
  slug: string
  branches: string[]
  message: string
}

export interface BranchDiff {
  flow: string
  branches: string[]
  definition: DefinitionDiff[]
  materialization: MaterializationDiff[]
  shapeless: ShapelessDiff[]
  integrity: IntegrityWarning[]
}

export interface FlowExport {
  flow: string
  branch: string
  cells: string[]
  source: string
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
  states: Partial<Record<StaleState, number>>
  checkpoint: number | null
  head_step: number
  newest_step: number
  last_intent: TransactionSummary | null
  agent: string | null
}

export interface TransactionSummary {
  step: number
  ts: string
  actor: string
  intent: string
  offline: boolean
  settled: boolean
}

export interface KernelReport {
  state: 'running' | 'stopped'
  restart_required: boolean
  behind: string[]
  python?: string
  kinds?: string[]
}

export interface FlowSettingsReport {
  reactivity: 'lazy' | 'auto'
  eager_cost_threshold_s: number
}

export interface FlowBrief {
  flow: string
  flow_id: string
  path: string
  workspace: string
  branch: string
  checked_out: boolean
  agent: string | null
  agent_sessions: AgentSessionRecord[]
  kernel: KernelReport
  settings: FlowSettingsReport
}

export interface FlowStatus extends FlowBrief {
  cells: CellSummary[]
  disk_bytes: number
  hygiene: string[]
}

export interface WorkspaceStatus {
  workspace: string
  pid: number
  python: { path: string; source: string }
  flows: FlowStatus[]
}

export interface Preflight {
  branch: string
  target: string
  cached: string[]
  recompute: string[]
  unknown: string[]
  estimate_seconds: number
  reasons?: string[]
}

export interface RunOutcome {
  path?: string
  branch: string
  target: string
  targets?: string[]
  executed: string[]
  cached: string[]
  pruned: string[]
  failed: string | null
  failures?: string[]
  unplanned?: { target: string; error: string }[]
  abandoned: boolean
}

export type AgentHarnessState =
  | 'not set up'
  | 'set up'
  | 'out of date'
  | 'broken'
  | 'removed by you'

export interface AgentHarness {
  id: string
  display_name: string
  state: AgentHarnessState
  config_path: string
  snippet: string
  can_setup: boolean
  action: 'setup' | 'update' | null
  consent_required: boolean
  consent_prompt: string | null
  post_write_hint: string | null
  shell: boolean
  shell_hint: string | null
  error: string | null
}

export interface CellContextPayload {
  flow: string
  branch: string
  slug: string
  text: string
}

export interface JournalPage {
  flow: string
  path: string
  cursor: number
  transactions: Transaction[]
}
