import type { FlagCode, TrackerExperiment } from '@/flow/api/types'
import type { MetricValue } from './format'

export type Slug = string
export type BranchName = string

export type DeclaredType = 'model' | 'dataset' | 'experiment' | 'asset'

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

export type CellStatus =
  | 'materialized'
  | 'refreshing'
  | 'running'
  | 'stale'
  | 'unmaterialized'
  | 'failed'

export type StaleKind =
  | 'definition-changed'
  | 'deps-rewired'
  | 'env-changed'
  | 'parent-rematerialized'
  | 'workspace-code-changed'

export interface StaleCounts {
  unsynced: number
  downstream: number
  unmaterialized: number
  waitingOnThreshold: number
  neverTimed: number
  blockedByFailure: number
  refreshFailed: number
  cause?: string
}

export interface StaleInfo {
  kind?: StaleKind
  cause: string
  transitive?: boolean
}

export interface AutoDeclinedInfo {
  reason:
    | 'blocked'
    | 'never-timed'
    | 'too-expensive'
    | 'dangling-experiment'
    | 'unresolvable-reference'
    | 'refresh-failed'
  estimateSeconds: number
  untimed: string[]
  detail?: string
}

export interface ActorRef {
  kind: 'agent' | 'user'
  label: string
}

export interface ProvenanceInfo {
  createdBy: ActorRef
  lastEditedBy: ActorRef
  intent: string
  step: number
  attributionUncertain?: boolean
}

export interface TimingInfo {
  costSeconds?: number
  cached?: boolean
  olderEnv?: boolean
  finishedAgo?: string
}

export interface CellFlagInfo {
  code?: FlagCode
  message: string
  didYouMean?: string
}

export interface CellErrorInfo {
  author: 'agent' | 'user'
  summary: string
  traceback: string
  repairedAttempts?: number
}

export type ParamValue = string | number | boolean | null | ParamValue[]

export interface FramePreview {
  type: 'frame'
  columns: string[]
  dtypes: string[]
  rows: (string | number | boolean | null)[][]
  totalRows: number
  totalColumns: number
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
  experimentRef?: string
}

export interface ExperimentPreview {
  type: 'experiment'
  runName: string
  mainMetric?: { name: string; value: MetricValue }
  metrics: { name: string; value: MetricValue }[]
  config: Record<string, ParamValue>
  curves: { name: string; points: [number, number][] }[]
  tracker?: TrackerExperiment
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

export interface KvPreview {
  type: 'kv'
  entries: Record<string, string | number | boolean>
  newerFormatNote?: string
}

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

export interface BlocksPreview {
  type: 'blocks'
  kind: AssetKind
  blocks: PreviewBlock[]
  truncated?: boolean
  pending?: boolean
}

export interface ValuePage {
  columns: string[]
  dtypes: string[]
  rows: (string | number | boolean | null)[][]
  offset: number
  totalRows: number
  totalColumns: number
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

export interface CellOutput {
  name: string
  declared: DeclaredType
  kind: AssetKind
  preview: PreviewValue
  neverPersisted?: boolean
  downloadUrl?: string
}

export interface FlowCell {
  uid?: string
  slug: Slug
  doc: string
  consumes: string[]
  consumesByInput?: Record<string, string>
  params: Record<string, ParamValue>
  source: string
  outputs: CellOutput[]
  primaryOutput?: string
  status: CellStatus
  stale?: StaleInfo
  authoredStep?: number
  order?: string
  provenance?: ProvenanceInfo
  timing?: TimingInfo
  logs?: string
  console?: string[]
  error?: CellErrorInfo
  flag?: CellFlagInfo
  conflict?: boolean
  renamedFrom?: string
  externalInput?: boolean
  eager?: boolean
  autoDeclined?: AutoDeclinedInfo
  tracker?: TrackerExperiment
  sdkVersionWarning?: string
  isNote?: boolean
}

export interface BranchInfo {
  name: BranchName
  parent: BranchName | null
  forkedAtStep: number | null
  parentStep: number | null
  headStep: number
  newestStep?: number
  lastIntent: string
  settled: boolean
  checkpointStep?: number
  agent?: ActorRef
  archived?: boolean
  sweepGroup?: string
  headlineMetric?: { name: string; value: number }
  checkedOut?: boolean
}

export type JournalKind =
  | 'edit'
  | 'note'
  | 'run'
  | 'fork'
  | 'rewind'
  | 'checkout'
  | 'adopt'
  | 'rename'
  | 'delete'
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
  summary: string
  failedAttempts?: number
  settled?: boolean
  mark?: string
  position: boolean
}

export type FlowState = 'running' | 'idle' | 'unpaired' | 'kernel-not-started' | 'daemon-down'

export interface PairedAgent {
  label: string
  branch: BranchName
  state: 'working' | 'idle'
  idleFor?: string
  task?: string
}

export interface WorkbenchSession {
  flowName: string
  workspacePath?: string
  state: FlowState
  paired?: PairedAgent
  worktreeBranch: BranchName
  changesBehind?: number
  diskUsage?: string
}

export interface PackageInfo {
  name: string
  version: string
  pendingRestart?: boolean
}

export interface EnvState {
  pythonVersion: string
  interpreter?: { path: string; source: string }
  packages: PackageInfo[]
  mismatch?: boolean
}

export interface FlowSettings {
  reactivity: 'lazy' | 'auto'
  autoThresholdSeconds: number
}

export interface Preflight {
  cached: Slug[]
  recompute: Slug[]
  unknown: Slug[]
  totalSeconds: number
  reasons: string[]
}

export interface WorkbenchFixture {
  session: WorkbenchSession
  settings: FlowSettings
  env: EnvState
  branches: BranchInfo[]
  cellsByBranch: Record<BranchName, FlowCell[]>
  journal: JournalEntry[]
}

export interface CompareBranchColumn {
  branch: BranchName
  headlineMetric?: { name: string; value: number; higherIsBetter?: boolean }
  scores: Record<string, number>
  curve?: { name: string; points: [number, number][] }
  settled: boolean
  heldKind?: AssetKind
}

export interface DefinitionDivergence {
  slug: Slug
  sides: {
    branches: BranchName[]
    params: Record<string, ParamValue>
    sourceExcerpt?: string
    version: string
  }[]
}

export interface MaterializationRow {
  slug: Slug
  output?: string
  kind: 'metric' | 'chip'
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

export interface CompareTrackerLink {
  branch: BranchName
  slug: Slug
  output: string
  tracker: TrackerExperiment
}

export interface CompareView {
  branches: CompareBranchColumn[]
  sharedMetric: string
  definitionDivergences: DefinitionDivergence[]
  materializationRows: MaterializationRow[]
  shapelessDifferences: ShapelessDifference[]
  warnings: CompareWarning[]
  trackerLinks: CompareTrackerLink[]
}
