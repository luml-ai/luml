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
  root_span: Span | null
  spans: Span[]
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
}
