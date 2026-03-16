import type {
  AddAnnotationPayload,
  Annotation,
  AnnotationSummary,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'
import type {
  EvalsColumns,
  EvalsInfo,
  GetEvalsByDatasetParams,
  GetTracesParams,
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
    maxPoints?: number,
    signal?: AbortSignal,
  ) => Promise<ExperimentMetricHistory>

  getTraceDetails: (
    modelId: string,
    traceId: string,
  ) => Promise<{ spans: SpanFromApi[]; trace_id: string }>

  getExperimentTraces: (
    params: GetTracesParams & { experiment_id: string; cursor?: string | null },
  ) => Promise<{ items: Trace[]; cursor: string | null }>

  getExperimentEvalColumns: (artifactId: string, datasetId: string) => Promise<EvalsColumns>

  getExperimentUniqueDatasetsIds: (artifactId: string) => Promise<string[]>

  getExperimentEvals: (
    params: GetExperimentEvalsParams,
  ) => Promise<{ items: GetExperimentEvalsItem[]; cursor: string | null }>

  getEvalById: (experimentId: string, evalId: string) => Promise<GetExperimentEvalsItem>

  getExperimentDatasetAverageScores: (artifactId: string, datasetId: string) => Promise<ScoreInfo[]>

  createEvalAnnotation: (
    artifactId: string,
    datasetId: string,
    evalId: string,
    data: AddAnnotationPayload,
  ) => Promise<Annotation>

  updateEvalAnnotation: (
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) => Promise<Annotation>

  getEvalAnnotations: (
    artifactId: string,
    datasetId: string,
    evalId: string,
  ) => Promise<Annotation[]>

  deleteEvalAnnotation: (artifactId: string, annotationId: string) => Promise<void>

  getEvalAnnotationSummary: (artifactId: string, datasetId: string) => Promise<AnnotationSummary>

  createSpanAnnotation: (
    artifactId: string,
    traceId: string,
    spanId: string,
    data: AddAnnotationPayload,
  ) => Promise<Annotation>

  updateSpanAnnotation: (
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) => Promise<Annotation>

  getSpanAnnotations: (artifactId: string, traceId: string, spanId: string) => Promise<Annotation[]>

  deleteSpanAnnotation: (artifactId: string, annotationId: string) => Promise<void>

  getTracesAnnotationSummary: (artifactId: string) => Promise<AnnotationSummary>
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
  annotations: AnnotationSummary | null
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
  annotation_count: number
}
