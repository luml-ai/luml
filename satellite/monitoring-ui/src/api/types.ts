// TypeScript mirrors of the Satellite Query API contracts
// (agent/schemas/monitoring_query.py). The UI does no metric math — it renders
// these already-aggregated shapes directly.

export enum Window {
  H24 = '24h',
  D7 = '7d',
  D30 = '30d',
}

export enum Compare {
  REFERENCE = 'reference',
  PREVIOUS = 'previous',
}

export enum SeverityFilter {
  ALL = 'all',
  WARNING = 'warning',
  CRITICAL = 'critical',
}

export enum Severity {
  OK = 'ok',
  WARNING = 'warning',
  CRITICAL = 'critical',
}

export enum SectionState {
  OK = 'ok',
  EMPTY = 'empty',
  UNAVAILABLE = 'unavailable',
}

export enum ProfileStatus {
  READY = 'ready',
  PLACEHOLDER = 'placeholder',
}

export interface SeriesPoint {
  t: string
  value: number | null
}

export interface Series {
  key: string
  label: string
  unit?: string | null
  points: SeriesPoint[]
}

export interface AlertBanner {
  group: string
  metric: string
  feature?: string | null
  severity: Severity
  current_value?: number | null
  threshold?: number | null
  message: string
  first_seen?: string | null
  last_seen?: string | null
  /** What fired, phrased for a reader: "PSI", "Missing rate", "Latency p95". */
  label?: string
  unit?: string
  value_label?: string
  threshold_label?: string
  state?: string
  duration_seconds?: number | null
  threshold_source?: string
  /** The alert's own metric across the materialized windows. */
  history?: Series | null
}

export interface MetricFailure {
  metric: string
  error: string
  at: string
}

export interface MetricIncident {
  metric: string
  error: string
  started_at: string
  ended_at?: string | null
  ongoing: boolean
}

/** Whether monitoring itself is keeping up — not a metric about the model. */
export interface WorkerHealthResponse {
  state: SectionState
  running: boolean
  last_tick_at?: string | null
  windows_processed: number
  last_window_end?: string | null
  last_lag_seconds?: number | null
  window_seconds?: number | null
  interval_seconds?: number | null
  failures: MetricFailure[]
  /** Failure history from the database; survives a restart, unlike the counters. */
  incidents: MetricIncident[]
}

export interface AlertGroup {
  group: string
  alerts: AlertBanner[]
}

export interface AlertsResponse {
  state: SectionState
  profile_status: ProfileStatus
  groups: AlertGroup[]
}

export interface Card {
  key: string
  label: string
  value?: number | null
  unit?: string | null
  delta?: number | null
  delta_kind?: Compare | null
  critical_count?: number | null
  feature_names?: string[] | null
}

export interface DriftedFeature {
  feature: string
  psi: number
  severity: Severity
}

export interface HeaderResponse {
  state: SectionState
  deployment_id: string
  name?: string | null
  status?: string | null
  task_type?: string | null
  model_name?: string | null
  environment?: string | null
  satellite?: string | null
  inference_url?: string | null
  last_prediction_at?: string | null
  last_monitored_at?: string | null
  profile_status: ProfileStatus
}

export interface OverviewResponse {
  state: SectionState
  profile_status: ProfileStatus
  cards: Card[]
  alert_banners: AlertBanner[]
  series: Series[]
  top_drifted_features: DriftedFeature[]
}

export interface UnseenCategoryCount {
  value: string
  count: number
}

/** What was wrong with the values a feature's rates counted — evidence for the panel. */
export interface InvalidValueSummary {
  missing_count: number
  type_mismatch_count: number
  observed_types: Record<string, number>
  type_examples: string[]
  range_violation_count: number
  below_min: number
  above_max: number
  observed_min?: number | null
  observed_max?: number | null
  reference_min?: number | null
  reference_max?: number | null
  unseen_category_count: number
  unseen_distinct: number
  reference_categories?: number | null
  unseen_categories: UnseenCategoryCount[]
}

export interface DataQualityFeatureRow {
  feature: string
  kind?: string | null
  missing_rate?: number | null
  type_error_rate?: number | null
  // the worst of the two checks below, for the single column the table shows
  range_unseen_rate?: number | null
  range_violation_rate?: number | null
  unseen_category_rate?: number | null
  checked?: number | null
  status: Severity
  invalid?: InvalidValueSummary | null
}

export interface DataQualityResponse {
  state: SectionState
  profile_status: ProfileStatus
  features: DataQualityFeatureRow[]
  /** One series per check of the requested feature; empty for the whole-table request. */
  trends?: Series[]
  alerts: AlertBanner[]
}

export interface DistributionBin {
  label: string
  reference?: number | null
  current?: number | null
}

export interface FeatureDistribution {
  kind: string // "numeric" | "categorical"
  bins: DistributionBin[]
}

export interface FeatureDriftDetail {
  feature: string
  psi?: number | null
  status: Severity
  distribution?: FeatureDistribution | null
  psi_over_time?: Series | null
}

export interface PcaPoint {
  x: number
  y: number
}

export interface MultivariatePanel {
  state: SectionState
  status: Severity
  shift_value?: number | null
  shift_metric?: string | null
  shift_unit?: string
  dispersion_ratio?: number | null
  outlier_rate?: number | null
  reference_ellipse?: PcaPoint[]
  current_ellipse?: PcaPoint[]
  explained_variance: number[]
  feature_psi: DriftedFeature[]
  reference_projection: PcaPoint[]
  current_projection: PcaPoint[]
}

export interface FeatureDriftResponse {
  state: SectionState
  profile_status: ProfileStatus
  features: DriftedFeature[]
  selected?: FeatureDriftDetail | null
  multivariate: MultivariatePanel
  alerts: AlertBanner[]
}

export interface ReferenceProfileFeature {
  feature: string
  kind: string // "numeric" | "categorical"
  summary: Record<string, number>
  bin_edges?: number[] | null
  histogram?: number[] | null
  categories?: string[] | null
  category_probabilities?: number[] | null
}

export interface ReferenceProfileResponse {
  state: SectionState
  profile_status: ProfileStatus
  baseline_label?: string | null
  computed_at?: string | null
  features: string[]
  feature?: ReferenceProfileFeature | null
  /** The artifact's reference_profile.json itself, for the Reference profile tab. */
  document?: Record<string, unknown> | null
}

export interface TraceRow {
  event_id: string
  ts: string
  features_summary?: string | null
  prediction?: string | null
  latency_ms: number
  status: string
  status_code: number
}

export interface TracesResponse {
  state: SectionState
  profile_status: ProfileStatus
  rows: TraceRow[]
  total: number
  limit: number
  offset: number
}

/** Span type as tagged by instrumentation; drives the icon, exactly as on the Platform. */
export enum SpanTypeEnum {
  DEFAULT = 0,
  CHAT = 1,
  AGENT = 2,
  TOOL = 3,
  EMBEDDER = 4,
  RERANKER = 5,
}

/** One span of a trace. Field-for-field the Platform's span shape. */
export interface TraceSpan {
  trace_id: string
  span_id: string
  parent_span_id: string | null
  name: string
  kind: number
  start_time_unix_nano: number
  end_time_unix_nano: number
  status_code: number | null
  status_message: string | null
  attributes: Record<string, unknown>
  events: unknown[]
  links: unknown[]
  dfs_span_type: SpanTypeEnum | null
  annotation_count: number
}

/** A span with its children resolved — the tree the viewer renders. */
export interface TraceSpanNode extends TraceSpan {
  children: TraceSpanNode[]
}

/** One call opened from the traces table: full payloads, not the truncated summaries. */
export interface TraceDetail {
  event_id: string
  ts: string
  latency_ms: number
  status: string
  status_code: number
  trace_id?: string | null
  span_id?: string | null
  inputs?: unknown
  output?: unknown
  spans: TraceSpan[]
}

export interface TraceDetailResponse {
  state: SectionState
  profile_status: ProfileStatus
  trace: TraceDetail | null
}

export interface Dimensions {
  window: Window
  compare: Compare
  severity: SeverityFilter
  feature: string | null
}
