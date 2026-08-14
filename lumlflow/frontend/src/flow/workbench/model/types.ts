/**
 * View model for the flow workbench design system.
 *
 * These are the shapes the daemon will eventually serve (ui-draft.md §10: no
 * derived truth in the frontend — staleness verdicts, preflight costs, and
 * divergence kinds arrive computed). Fixtures therefore author these shapes
 * directly; there is deliberately no derivation engine here.
 *
 * Vocabulary rules that are part of the contract, not taste:
 * - Cells are addressed by slug and branches by name. No positional numbers,
 *   and internal ids (uid, content hash, memo key) never appear in any
 *   user-facing string.
 * - `unmaterialized` is its own status, never a flavor of stale: the asset has
 *   no baseline anywhere, and claiming a change against a missing baseline is
 *   a claim the runtime refuses to make.
 * - Staleness causes are rendered in words ("parent `features` rematerialized"),
 *   never as bare enum values.
 */

import type { FlagCode } from '@/flow/api/types'

export type Slug = string
export type BranchName = string

/** The four-word authoring vocabulary: what leaves the flow vs. stays inline. */
export type DeclaredType = 'model' | 'dataset' | 'experiment' | 'asset'

/**
 * Inferred kind of a materialized value — drives the renderer registry.
 * The registry is open at runtime; `unknown` is the documented fallback,
 * rendered as a key-value grid, never an error.
 */
export type AssetKind =
  | 'frame'
  | 'plot'
  | 'metric'
  | 'note'
  | 'eval'
  | 'model'
  | 'dataset'
  | 'experiment'
  | 'checkpoint'
  | 'file'
  | 'image'
  | 'text'
  | 'html'
  | 'unknown'

export type CellStatus = 'materialized' | 'running' | 'stale' | 'unmaterialized' | 'failed'

export type StaleKind =
  | 'definition-changed'
  | 'deps-rewired'
  | 'parent-rematerialized'
  | 'workspace-code-changed'

/**
 * What a branch owes, counted for the one line in the top bar that says so.
 * The three counts are kept apart because they are three different claims —
 * and `unmaterialized` is not a flavour of stale.
 */
export interface StaleCounts {
  unsynced: number
  downstream: number
  unmaterialized: number
  /** The first stale cell's cause, in the daemon's own words. */
  cause?: string
}

export interface StaleInfo {
  /**
   * Optional because the wire does not carry it: the daemon serves causes as
   * sentences, and a live card that picked an enum back out of one would be
   * re-deriving a verdict it was handed.
   */
  kind?: StaleKind
  /** Human words shown on the chip, e.g. 'parent `features` rematerialized'. */
  cause: string
  /** Stale only under the transitive view — subdued tint, hidden by default. */
  transitive?: boolean
}

/**
 * Why a stale cell is being left for the user to run. The card says it out
 * loud: a cell reactivity declined and a cell reactivity forgot about look
 * identical otherwise, and that is what made auto mode read as broken.
 */
export interface AutoDeclinedInfo {
  reason: 'blocked' | 'never-timed' | 'too-expensive'
  /** Seconds the timed part of the closure is expected to take. */
  estimateSeconds: number
  /** Cells in the closure this flow has never run, by slug. */
  untimed: string[]
}

export interface ActorRef {
  kind: 'agent' | 'user'
  label: string
}

export interface ProvenanceInfo {
  createdBy: ActorRef
  lastEditedBy: ActorRef
  /** Intent string of the transaction that authored the current version. */
  intent: string
  step: number
  /** Mixed-editing window: render the flag, never a confident wrong name. */
  attributionUncertain?: boolean
}

export interface TimingInfo {
  /** Absent when the run recorded none — never a zero standing in for unknown. */
  costSeconds?: number
  /** Memo hit — a hit is not a 0-second run, and saying so keeps the cache legible. */
  cached?: boolean
  /** Recorded lock hash differs from the live env. */
  olderEnv?: boolean
  finishedAgo?: string
}

/** Accepted-but-flagged version (broken declaration, unknown reference). */
export interface CellFlagInfo {
  /**
   * Which flag this is. The card reads it to tell a broken declaration from a
   * cell that simply has not been named yet — one is a warning, the other is
   * the state every cell starts in.
   */
  code?: FlagCode
  message: string
  didYouMean?: string
}

export interface CellErrorInfo {
  author: 'agent' | 'user'
  summary: string
  traceback: string
  /** Folded history entry: a later version by the same author repaired it. */
  repairedAttempts?: number
}

export type ParamValue = string | number | boolean | null | ParamValue[]

// ---------------------------------------------------------------------------
// Preview payloads — the kernel-free tier every renderer draws from
// ---------------------------------------------------------------------------

export interface FramePreview {
  type: 'frame'
  columns: string[]
  dtypes: string[]
  rows: (string | number | boolean | null)[][]
  totalRows: number
}

export interface PlotPreview {
  type: 'plot'
  title: string
  kind: 'line' | 'scatter' | 'bar' | 'hist'
  series: { label: string; points: [number, number][]; color?: string }[]
  xLabel: string
  yLabel: string
}

export interface MetricPreview {
  type: 'metric'
  name: string
  value: number
  higherIsBetter: boolean
  /** Change against the previous materialization on this branch, if any. */
  delta?: number
}

export interface NotePreview {
  type: 'note'
  markdown: string
}

export interface ModelPreview {
  type: 'model'
  flavor: string
  sizeBytes: number
  headlineMetric?: { name: string; value: number; higherIsBetter: boolean }
  config: Record<string, ParamValue>
  /** Slug of the cell output holding the full experiment, when one exists. */
  experimentRef?: string
}

export interface ExperimentPreview {
  type: 'experiment'
  runName: string
  mainMetric: { name: string; value: number; higherIsBetter: boolean }
  config: Record<string, ParamValue>
  curves: { name: string; points: [number, number][] }[]
  /** Present once the daemon uploaded it — links out to the tracker. */
  trackerRef?: string
}

export interface EvalPreview {
  type: 'eval'
  datasetRef: string
  sampleCount: number
  scores: Record<string, number>
}

export interface DatasetPreview {
  type: 'dataset'
  schema: { name: string; dtype: string }[]
  head: (string | number | null)[][]
  totalRows: number
  sizeBytes: number
}

export interface FilePreview {
  type: 'file'
  fileName: string
  sizeBytes: number
  contentType: string
}

export interface TextPreview {
  type: 'text'
  text: string
}

/** Fallback for open-registry kinds the frontend has no renderer for. */
export interface KvPreview {
  type: 'kv'
  entries: Record<string, string | number | boolean>
  /** Set when the preview schema version is newer than this frontend. */
  newerFormatNote?: string
}

// ---------------------------------------------------------------------------
// Preview blocks — the primitives a stored preview is composed of
// ---------------------------------------------------------------------------

/**
 * The six renderable primitives of the stored preview schema. A kind — builtin
 * or one a workspace defined this morning — composes these and renders without
 * a line of frontend code, which is the whole reason the payload is blocks and
 * not a per-kind shape.
 */
export interface TableBlock {
  block: 'table'
  columns: string[]
  dtypes: string[]
  rows: (string | number | boolean | null)[][]
  totalRows: number
  totalColumns: number
}

export interface SeriesBlock {
  block: 'series'
  name: string
  points: [number, number][]
  totalPoints: number
}

export interface ImageBlock {
  block: 'image'
  mime: string
  /** base64, as stored — rendered inline, never fetched. */
  data: string
}

export interface MarkdownBlock {
  block: 'markdown'
  text: string
}

export interface KvBlock {
  block: 'kv'
  entries: Record<string, ParamValue>
}

export interface FileBlock {
  block: 'file'
  name: string
  size: number
  contentType: string
}

export type PreviewBlock =
  | TableBlock
  | SeriesBlock
  | ImageBlock
  | MarkdownBlock
  | KvBlock
  | FileBlock

/** A stored preview as served: the kind it was inferred as, and its blocks. */
export interface BlocksPreview {
  type: 'blocks'
  kind: AssetKind
  blocks: PreviewBlock[]
  /** The payload hit its cap; what is shown is the head of a longer value. */
  truncated?: boolean
  /** The payload is still on its way — not the same thing as an empty value. */
  pending?: boolean
}

/**
 * A window into a stored value, served by the kernel on request. The preview is
 * the head of a value; this is the rest of it, one page at a time — the browser
 * receives pages, never the frame.
 */
export interface ValuePage {
  columns: string[]
  dtypes: string[]
  rows: (string | number | boolean | null)[][]
  offset: number
  totalRows: number
}

export type PreviewValue =
  | FramePreview
  | PlotPreview
  | MetricPreview
  | NotePreview
  | ModelPreview
  | ExperimentPreview
  | EvalPreview
  | DatasetPreview
  | FilePreview
  | TextPreview
  | KvPreview
  | BlocksPreview

// ---------------------------------------------------------------------------
// Cells
// ---------------------------------------------------------------------------

export interface CellOutput {
  name: string
  declared: DeclaredType
  kind: AssetKind
  preview: PreviewValue
  /** Value was never persisted → download becomes materialize-and-download. */
  neverPersisted?: boolean
}

export interface FlowCell {
  slug: Slug
  /** First line of the class docstring. */
  doc: string
  /** Reference strings exactly as authored: 'features.train_split'. */
  consumes: string[]
  params: Record<string, ParamValue>
  source: string
  outputs: CellOutput[]
  /** Defaults to the ranking in registry.ts when absent. */
  primaryOutput?: string
  status: CellStatus
  stale?: StaleInfo
  /**
   * The step the cell was minted at — what breaks ties in the notebook column.
   * The mint order never moves, so a rename or an edit cannot reorder cards.
   */
  authoredStep?: number
  /** Absent until authorship has been read — never a placeholder shaped like one. */
  provenance?: ProvenanceInfo
  timing?: TimingInfo
  /** Persistent logs of the current materialization. */
  logs?: string
  /** Live console lines while running. */
  console?: string[]
  error?: CellErrorInfo
  flag?: CellFlagInfo
  /** Edit landed on a moved head → overwrite / fork-my-edit menu. */
  conflict?: boolean
  /** Saved to the store, projection to files deferred by the worktree lock. */
  pendingProjection?: boolean
  /**
   * The name this cell answered to a moment ago. A rename is one identity
   * keeping its references, so the card carries the old name across rather than
   * reading as one cell disappearing and another arriving.
   */
  renamedFrom?: string
  /** volatility: external — listed under the left panel's "data" lens. */
  externalInput?: boolean
  /** Per-asset eager toggle (reactivity setting). */
  eager?: boolean
  /**
   * Reactivity is on, this cell is out of date, and it is not refreshing
   * itself. Absent whenever there is nothing to say — which includes the cell
   * that is about to refresh, because a label gone by the time it is read is
   * worse than none.
   */
  autoDeclined?: AutoDeclinedInfo
  /** Note cells render prose and skip the op row's run controls. */
  isNote?: boolean
}

// ---------------------------------------------------------------------------
// Branches and the journal
// ---------------------------------------------------------------------------

export interface BranchInfo {
  name: BranchName
  parent: BranchName | null
  forkedAtStep: number | null
  headStep: number
  lastIntent: string
  /** Fully materialized and consistent — a quality badge, never a gate. */
  settled: boolean
  /**
   * The step this branch was last marked or settled at — where the timeline
   * says it stands. Absent on a branch that has neither been marked nor been
   * whole, which is every branch with something unfinished on it.
   */
  checkpointStep?: number
  /** Agent currently registered on this branch. */
  agent?: ActorRef
  archived?: boolean
  sweepGroup?: string
  headlineMetric?: { name: string; value: number }
  /** Bound to the single v1 worktree. */
  checkedOut?: boolean
}

export type JournalKind =
  | 'edit'
  | 'run'
  | 'checkpoint'
  | 'fork'
  | 'adopt'
  | 'rename'
  | 'delete'
  | 'promote'
  | 'agent-begin'
  | 'agent-end'
  | 'offline'
  | 'env'

export interface JournalEntry {
  step: number
  time: string
  branch: BranchName
  actor: ActorRef
  intent: string
  kind: JournalKind
  /** One rendered line: 'edited `features` · 3 cells marked stale'. */
  summary: string
  /** Folded failed attempts: 'v3→v4 · 1 failed attempt'. */
  failedAttempts?: number
  settled?: boolean
}

// ---------------------------------------------------------------------------
// Session, env, settings
// ---------------------------------------------------------------------------

export type FlowState = 'running' | 'idle' | 'unpaired' | 'kernel-not-started' | 'daemon-down'

export interface PairedAgent {
  label: string
  branch: BranchName
  state: 'working' | 'idle'
  /** For idle agents: time since the last transaction. Never a fabricated status. */
  idleFor?: string
  /** Latest transaction intent — the "current agent task" line. */
  task?: string
}

export interface WorkbenchSession {
  flowName: string
  /** Absent until something has asked the daemon where it was launched. */
  workspacePath?: string
  state: FlowState
  paired?: PairedAgent
  worktreeBranch: BranchName
  /** Held by an agent session: checkout/rewind/adopt wait, edits defer projection. */
  worktreeLocked?: boolean
  /** "N changes since you were here" — a marker, not an inbox. */
  changesBehind?: number
  diskUsage?: string
}

export interface PackageInfo {
  name: string
  version: string
  /** Installed into the env but not yet active in the running kernel. */
  pendingRestart?: boolean
}

export interface EnvState {
  pythonVersion: string
  packages: PackageInfo[]
  /**
   * The running kernel imported packages the workspace has moved since, so it
   * is behind until restarted. There is no per-branch env: one venv per
   * workspace, and what already ran keeps the lock hash it ran under.
   */
  mismatch?: boolean
}

export interface FlowSettings {
  reactivity: 'lazy' | 'auto'
  /** Assets cheaper than this auto-materialize when reactivity is 'auto'. */
  autoThresholdSeconds: number
  onEnvChange: 'ask' | 'restart' | 'never'
}

// ---------------------------------------------------------------------------
// Run preflight
// ---------------------------------------------------------------------------

/**
 * The daemon's own answer, in the shape it gave it. Which cells recompute and
 * what the closure costs is a scheduling verdict; a client that split the total
 * back into per-cell guesses would be answering the question the preflight
 * exists to ask.
 */
export interface Preflight {
  cached: Slug[]
  recompute: Slug[]
  /** Never timed here — seconds absent from the total rather than guessed at. */
  unknown: Slug[]
  totalSeconds: number
}

// ---------------------------------------------------------------------------
// The whole fixture a page consumes
// ---------------------------------------------------------------------------

export interface WorkbenchFixture {
  session: WorkbenchSession
  settings: FlowSettings
  env: EnvState
  branches: BranchInfo[]
  cellsByBranch: Record<BranchName, FlowCell[]>
  journal: JournalEntry[]
}

// ---------------------------------------------------------------------------
// The compare surface (ui-draft.md §7)
//
// The two divergence kinds are the load-bearing distinction: definition
// divergence (someone edited the cell — rare, structural, rendered as the
// branching point) vs materialization divergence (same code, different inputs —
// transitively closed, rendered collapsed to one row per asset).
// ---------------------------------------------------------------------------

export interface CompareBranchColumn {
  branch: BranchName
  /**
   * The one number the asset leads with, where it has one. `higherIsBetter` is
   * the comparison's own declaration and absent on a live one: nothing the
   * runtime records says which way a metric reads, and a column marked best
   * against a guess is a claim nobody measured.
   */
  headlineMetric?: { name: string; value: number; higherIsBetter?: boolean }
  scores: Record<string, number>
  /** Overlaid on the shared-metric curve chart, for outputs that carry one. */
  curve?: { name: string; points: [number, number][] }
  settled: boolean
  /**
   * What the branch holds where it holds no numbers — most kinds record none.
   * Absent when the branch stored nothing at all, which is the one case that
   * honestly reads as never materialized.
   */
  heldKind?: AssetKind
}

export interface DefinitionDivergence {
  slug: Slug
  /** One side per distinct definition, not per branch. */
  sides: {
    branches: BranchName[]
    params: Record<string, ParamValue>
    /** The line(s) that differ, where the comparison carries source to show. */
    sourceExcerpt?: string
    version: string
  }[]
}

export interface MaterializationRow {
  slug: Slug
  /** Absent collapses the row to the asset — one row per cell, not per output. */
  output?: string
  kind: 'metric' | 'chip'
  /** One chip per branch: the value or a short state label. */
  byBranch: Record<BranchName, { label: string; state: 'same' | 'better' | 'worse' | 'missing' }>
}

export interface ShapelessDifference {
  slug: Slug
  what: string
  branches: BranchName[]
}

export interface CompareWarning {
  kind: 'divergent-pin' | 'dataset-mismatch' | 'scoring-mismatch' | 'nondeterministic-input'
  message: string
  affectedBranches: BranchName[]
}

export interface CompareArtifactLink {
  slug: Slug
  output: string
  kind: 'experiment' | 'model' | 'dataset' | 'metric'
  label: string
  /** Tracker route, per the fallback chain. */
  href: string
  byBranch: Record<BranchName, string>
}

export interface CompareView {
  branches: CompareBranchColumn[]
  sharedMetric: string
  definitionDivergences: DefinitionDivergence[]
  materializationRows: MaterializationRow[]
  shapelessDifferences: ShapelessDifference[]
  warnings: CompareWarning[]
  artifacts: CompareArtifactLink[]
}
