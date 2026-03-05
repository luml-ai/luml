import type {
  EvalsColumns,
  EvalsInfo,
  GetEvalsByDatasetParams,
  ScoreInfo,
} from '@/interfaces/interfaces'

export interface ArtifactInfo {
  id: string
  dynamicMetrics: string[]
}

export interface TraceInfo {
  artifactId: string
  datasetId: string
  tracesIds: string[]
  evalId: string
}

export interface ApiServiceInterface {
  getExperimentMetricHistory: (
    artifactId: string,
    metricName: string,
  ) => Promise<ExperimentMetricHistory>

  getTraceDetails: (
    modelId: string,
    traceId: string,
  ) => Promise<{ spans: SpanFromApi[]; trace_id: string }>

  getExperimentTraces: (params: { experiment_id: string }) => Promise<{ items: Trace[] }>

  getExperimentEvalColumns: (artifactId: string, datasetId: string) => Promise<EvalsColumns>

  getExperimentUniqueDatasetsIds: (artifactId: string) => Promise<string[]>

  getExperimentEvals: (
    params: GetExperimentEvalsParams,
  ) => Promise<{ items: GetExperimentEvalsItem[]; cursor: string | null }>

  getExperimentDatasetAverageScores: (artifactId: string, datasetId: string) => Promise<ScoreInfo[]>
}

export interface ExperimentMetricHistory {
  experiment_id: string
  history: { step: number; value: number }[]
}

export interface Trace {
  trace_id: string
  execution_time: number
  span_count: number
  created_at: string
  state: TraceStateEnum
  evals: string[]
}

export interface GetExperimentEvalsParams extends GetEvalsByDatasetParams {
  experiment_id: string
  cursor?: string | null
}

export interface GetExperimentEvalsItem extends Omit<EvalsInfo, 'modelId'> {
  created_at: string
  updated_at: string
  trace_ids: string[]
}

export enum TraceStateEnum {
  UNSPECIFIED = 0,
  OK = 1,
  ERROR = 2,
  IN_PROGRESS = 3,
}

export interface SpanFromApi {
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
