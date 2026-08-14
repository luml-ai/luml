/**
 * The wire the workspace daemon speaks, as TypeScript.
 *
 * Two halves. The **op vocabulary** is the journal's closed, discriminated set
 * — one line per transaction, one entry per op — mirrored here field for field
 * so a client reading history never guesses at a shape. The **frames** are what
 * the two WebSocket channels carry: channel 1 is journal transactions plus the
 * kernel's run lifecycle, each stamped with the flow-global `step` a client
 * holds as its cursor; channel 2 is a live run's log chunks, keyed by `run_id`
 * and durable nowhere.
 *
 * Field names are the wire's, snake_case and all. Translating them here would
 * put a second vocabulary between the daemon and the surfaces that render it,
 * and the view model in `workbench/model/types.ts` is already that layer.
 *
 * Verdicts arrive computed — staleness, preflight costs, divergence kinds and
 * `settled` are the daemon's facts, and nothing in this file is derived from
 * another field in it.
 */

// ---------------------------------------------------------------------------
// The op vocabulary — `lumlflow/flow/store/models.py`
// ---------------------------------------------------------------------------

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
export type UploadState = 'queued' | 'uploading' | 'failed'
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

export interface LumlRef {
  collection: string
  artifact_id: string
  version: string
  digest: string
}

export interface OutputRecord {
  content_hash: string
  kind: string
  kind_source: KindSource
  size: number
  preview_ref: string | null
  value_ref: string | null
  luml_ref: LumlRef | null
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

export interface UploadStateChangedOp {
  op: 'upload_state_changed'
  mat_id: string
  output: string
  state: UploadState
  attempts: number
}

export interface UploadRecordedOp {
  op: 'upload_recorded'
  mat_id: string
  output: string
  ref: LumlRef
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
  /** A worktree-attached session edits files and holds the lock; MCP never does. */
  worktree: boolean
}

export interface AgentEndOp {
  op: 'agent_end'
  actor: string
  label: string | null
}

export interface SecretRefAddedOp {
  op: 'secret_ref_added'
  name: string
}

/**
 * A point somebody marked on purpose. It carries no state of its own — the
 * step, the intent and the actor are the transaction's, which is the whole
 * reason a marker costs one line and copies nothing.
 */
export interface CheckpointedOp {
  op: 'checkpointed'
  branch_id: string
}

export type FlowOp =
  | FlowInitOp
  | CellAcceptedOp
  | CellRemovedOp
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
  | UploadStateChangedOp
  | UploadRecordedOp
  | FlagSetOp
  | AgentBeginOp
  | AgentEndOp
  | SecretRefAddedOp
  | CheckpointedOp

/**
 * One journal line. `branch` is a branch **id**, not a name: the store keys on
 * ids so a rename costs nothing, and a client that wants the name asks `tree`.
 */
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

// ---------------------------------------------------------------------------
// Stream frames — `lumlflow/flow/daemon/stream.py`
// ---------------------------------------------------------------------------

export interface TransactionFrame {
  channel: 'journal'
  type: 'transaction'
  flow: string
  step: number
  transaction: Transaction
}

/**
 * A run's lifecycle, and the kernel process's own.
 *
 * Neither is journaled, so no cursor replays either. `kernel_state` is what
 * keeps a tab from reporting the kernel it was handed when it opened: the
 * kernel starts lazily, so that first answer is almost always `stopped` and
 * would stay so for the life of the tab.
 */
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
  /** Branches waiting on this run — it moves while the run is in flight. */
  awaiting?: number
  /** `kernel_state` only: whether a kernel process is up on this flow. */
  kernel?: 'running' | 'stopped'
}

/**
 * The end of a catch-up. `running` is how a tab that opened mid-run learns
 * which console it can still ask for — an event it was not there for.
 */
export interface CaughtUpFrame {
  channel: 'journal'
  type: 'caught_up'
  flow: string
  step: number
  running: { run_id: string; slug: string; awaiting?: number }[]
}

/** This client stopped reading long enough to be dropped. Replay from cursor. */
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

/** A subscription the daemon refused — this connection's other flows stand. */
export interface StreamErrorFrame {
  type: 'error'
  message: string
}

export type StreamFrame =
  | TransactionFrame
  | KernelFrame
  | CaughtUpFrame
  | LaggedFrame
  | LogFrame
  | StreamErrorFrame

// ---------------------------------------------------------------------------
// Read-side payloads — `lumlflow/flow/daemon/queries.py`
// ---------------------------------------------------------------------------

/** `unmaterialized` is its own state: no baseline exists to claim a change against. */
export type StaleState = 'synced' | 'unsynced' | 'unmaterialized' | 'failed'

/** One card's worth of facts. Causes are sentences, never bare enum values. */
export interface CellSummary {
  slug: string
  state: StaleState
  causes: string[]
  /** The cells above this one that are not current, by slug. */
  upstream: string[]
  /** Current on its own facts, sitting below something that is not. */
  transitive: boolean
  outputs: string[]
  /**
   * What each output reads as — the declared word where there is one, else
   * what the value turned out to be. A lens over the slice groups on this.
   */
  kinds: Record<string, string>
  primary: string | null
  consumes: Record<string, string>
  note: boolean
  /** Reads something the store does not version, so it never memoizes. */
  external: boolean
  flags: { code: FlagCode; detail: string | null }[]
  cost_seconds: number | null
  older_env: boolean
  /** Computed on another branch and read here — nothing ran for this one. */
  reused: boolean
  /** The step the cell was minted at — the notebook column's tiebreak. */
  created_step: number
  /** Opted out of the cost threshold: rematerializes on change regardless. */
  eager: boolean
  /**
   * Why reactivity is *not* refreshing this cell, when it is on and the cell is
   * out of date. Null covers three silences that need no sentence: reactivity
   * is off, the cell is current, or it is about to refresh itself.
   */
  auto_declined: AutoDeclined | null
}

/**
 * `never-timed` is a closure this flow has no measurement of — not a cheap one.
 * A threshold cannot admit a cost nobody has ever observed, so running it once
 * by hand is what lets reactivity keep it fresh afterwards. `blocked` is a
 * failure below it that nothing has changed since.
 */
export interface AutoDeclined {
  reason: 'blocked' | 'never-timed' | 'too-expensive'
  /** The closure's estimate, over the timed cells only. */
  estimate_seconds: number
  /** Cells in the closure the flow has never run, by slug. */
  untimed: string[]
}

/**
 * Authorship as the store recorded it. `attribution_uncertain` is the honest
 * end of it: one worktree cannot tell an agent's edit from the human's during
 * the same session, and a flagged window beats a confident wrong name.
 */
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
  /**
   * The word the cell declared it under. What leaves the flow is a declaration,
   * never an inference: a `model` whose value is a string still infers as a
   * note, and only this says it was meant to be published.
   */
  declared: DeclaredAssetType
  size: number
  persisted: boolean
  uploaded: boolean
}

export interface CellDetail extends CellSummary {
  branch: string
  /** The optimistic lock an editor carries back with `cells.edit`. Never printed. */
  definition_hash: string
  source: string
  /** The class docstring, dedented — and the whole content of a note cell. */
  doc: string
  params: Record<string, unknown>
  author: string
  produces: Record<string, OutputSpec>
  materialized: MaterializedOutput[]
  error: string | null
  /** Who wrote the version that failed — not necessarily whoever wrote the head. */
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
  /** The payload hit its cap and shrank from the tail — never a silent trim. */
  truncated?: boolean
}

/** `asset.preview`: one output as the store holds it. The kernel-free tier. */
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
}

/** `asset.page`: a window into the value itself. This one starts a kernel. */
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
  }
}

/** `asset.download`: the daemon copied the bytes out, and where they landed. */
export interface AssetDownload {
  slug: string
  output: string
  kind: string
  size: number
  path: string
}

/** `cells.logs`: the console of the run this branch observed, not the newest. */
export interface CellLogs {
  flow: string
  branch: string
  slug: string
  state: MaterializationState | null
  logs: string | null
}

/**
 * One branch's side of a compared asset: the verdict it holds and what it
 * produced. A definition side carries the version's own facts on top, so the
 * cell a comparison is *about* is not the one asset with no results on screen.
 */
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
  /** Declared data, read-only wherever it is shown. */
  params: Record<string, unknown>
}

/** Someone edited the cell — structural, and the branching point below it. */
export interface DefinitionDiff {
  slug: string
  versions: DiffVersionSide[]
}

/** Same code, different inputs — one entry per asset, never a fan of nodes. */
export interface MaterializationDiff {
  slug: string
  results: DiffSide[]
}

/** What neither shape covers: a cell a branch does not carry, a name that moved. */
export interface ShapelessDiff {
  slug: string
  branches: Record<string, string | null>
}

/**
 * Where pin-at-fork stopped keeping the comparison comparable. The daemon's
 * verdict: a side-by-side of two numbers computed under different upstream
 * code is worse than no comparison, so it says so rather than drawing it.
 */
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

/** `export`: a branch's slice as one file. A file export, not an upload. */
export interface FlowExport {
  flow: string
  branch: string
  cells: string[]
  source: string
}

export interface BranchRecord {
  branch: string
  /**
   * The key the journal scopes transactions by. Branches are addressed by name
   * everywhere a reader can see; this is how a client tells which branch a
   * transaction landed on, and it is never printed.
   */
  branch_id: string
  parent: string | null
  forked_at_step: number
  archived: boolean
  checked_out: boolean
  cells: number
  states: Partial<Record<StaleState, number>>
  checkpoint: number | null
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
  sandbox: string
  python?: string
  kinds?: string[]
}

/** The flow settings a surface renders; the runtime's own are not among them. */
export interface FlowSettingsReport {
  reactivity: 'lazy' | 'auto'
  eager_cost_threshold_s: number
  env_policy: 'ask' | 'auto' | 'never'
}

export interface FlowBrief {
  flow: string
  path: string
  branch: string
  checked_out: boolean
  agent: string | null
  /** Store edits whose projection into files the worktree lock is holding back. */
  unwritten: string[]
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
  /** Never run, so no recorded cost — estimated seconds exclude these. */
  unknown: string[]
  estimate_seconds: number
}

export interface RunOutcome {
  branch: string
  target: string
  executed: string[]
  cached: string[]
  pruned: string[]
  failed: string | null
  abandoned: boolean
}

export interface FocusReport {
  flow: string
  branch: string | null
  asset: string | null
  compare: string[]
}

/**
 * `agent.connect`: the paste-ready prompt that pairs an agent with this flow.
 *
 * Flow-scoped and nothing else — connecting is not a gesture against a branch,
 * and the branch the prompt names is whichever one the files hold. The prompt
 * is built where the facts are, so no surface has to guess at the line the
 * reader is about to paste into a harness's config.
 */
export interface ConnectPrompt {
  flow: string
  workspace: string
  /**
   * The `lumlflow` a config snippet can actually spawn — already inside `text`.
   * It crosses on its own because an install into a venv answers to no bare
   * `lumlflow`, and only the workspace knows which interpreter serves it.
   */
  command: string
  /** The whole prompt. One copy block, copied as-is. */
  text: string
}

/** `agent.payload`: the context one send-to-agent gesture hands over. */
export interface HandoffPayload {
  gesture: HandoffGesture
  flow: string
  branch: string
  /** The ask in a sentence, then the facts in a fenced block. Copied as-is. */
  text: string
}

export type HandoffGesture = 'fix' | 'explain' | 'diff' | 'summarize'

/**
 * `eval`: scratch code against a branch's values. A read — the names hydrate as
 * copies, so `mutated` names what the expression changed in its own copy and
 * nothing in the store moved.
 */
export interface EvalResult {
  flow: string
  branch: string
  repr: string | null
  output: string
  names: string[]
  mutated: string[]
  error: { type: string; message: string; traceback: string } | null
}

export interface JournalPage {
  flow: string
  path: string
  cursor: number
  transactions: Transaction[]
}
