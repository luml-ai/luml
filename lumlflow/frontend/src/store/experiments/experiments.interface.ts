import type { AnnotationSummary } from '@/api/api.interface'

export enum TraceStateEnum {
  UNSPECIFIED = 0,
  OK = 1,
  ERROR = 2,
  IN_PROGRESS = 3,
}

export interface Experiment {
  id: string
  name: string
  created_at: string
  tags: string[] | null
  models: Model[] | null
  duration: number
  description: string
  static_params: Record<string, string | number> | null
  dynamic_params: Record<string, number | string> | null
  status: 'active' | 'completed'
  source: string | null
  group_name: string | null
  group_id: string | null
}

export interface UpdateExperimentPayload {
  name?: string
  description?: string
  tags?: string[]
}

export interface Model {
  id: string
  name: string
  created_at: string
  tags: string[] | null
  path: string | null
}

export interface ExperimentMetricHistory {
  experiment_id: string
  key: string
  history: MetricPoint[]
}

export interface MetricPoint {
  value: number
  step: number
  logged_at: string
}

export interface Model {
  id: string
  name: string
  created_at: string
  tags: string[] | null
  path: string | null
  size: number | null
}

export interface Trace {
  trace_id: string
  execution_time: number
  span_count: number
  created_at: string
  state: TraceStateEnum
  evals: string[]
  annotations: AnnotationSummary | null
}

export interface Span {
  span_id: string
  parent_span_id: string | null
  name: string
  kind: number
  dfs_span_type: number
  start_time_unix_nano: number
  end_time_unix_nano: number
  status_code: number | null
  status_message: string | null
  attributes: Record<string, string> | null
  events: Record<string, string> | null
  links: Record<string, string> | null
  trace_flags: number | null
  annotation_count: number
}

export interface TraceDetails {
  trace_id: string
  spans: Span[]
}

export interface Eval {
  id: string
  dataset_id: string
  inputs: Record<string, string | number>
  created_at: string
  updated_at: string
  outputs: Record<string, string | number>
  refs: Record<string, string | number>
  scores: Record<string, string | number>
  metadata: Record<string, string | number>
  trace_ids: string[]
  annotations: AnnotationSummary | null
}

export interface EvalScores {
  inputs: string[]
  outputs: string[]
  refs: string[]
  scores: string[]
  metadata: string[]
}
