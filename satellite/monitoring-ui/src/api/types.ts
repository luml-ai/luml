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

export interface DataQualityFeatureRow {
  feature: string
  missing_rate?: number | null
  type_error_rate?: number | null
  range_unseen_rate?: number | null
  status: Severity
}

export interface DataQualityResponse {
  state: SectionState
  profile_status: ProfileStatus
  features: DataQualityFeatureRow[]
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

export interface Dimensions {
  window: Window
  compare: Compare
  severity: SeverityFilter
  feature: string | null
}
