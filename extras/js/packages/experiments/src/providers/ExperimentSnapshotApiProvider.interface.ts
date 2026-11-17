import type {
  AddAnnotationPayload,
  Annotation,
  AnnotationSummary,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'
import type {
  EvalsInfo,
  GetEvalsByDatasetParams,
  GetTracesParams,
  ScoreInfo,
  TypedEvalsColumns,
  TypedTracesColumns,
  ValidateResponseItem,
} from '@/interfaces/interfaces'

export interface ArtifactInfo {
  id: string
  dynamicMetrics: string[]
  staticParams: Record<string, unknown>
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

  /**
   * `GET experiments/{id}/metric-catalog`. Optional so API services written before the
   * endpoint existed stay assignable; without it the catalog fails per experiment.
   */
  getExperimentMetricCatalog?: (
    experimentId: string,
    signal?: AbortSignal,
  ) => Promise<MetricCatalogWire>

  /**
   * `POST experiments/{id}/metric-buckets`. Optional for the same reason as the catalog.
   * Both reject like axios (`{response: {status, data}}`) so a 409 or 422 `detail.code`
   * reaches the viewer as its typed error.
   */
  getExperimentMetricBuckets?: (
    experimentId: string,
    body: MetricBucketsRequestWire,
    signal?: AbortSignal,
  ) => Promise<MetricBucketsWire>

  /**
   * `GET experiments/{id}/traces/{trace_id}`. With `payloads: false` (`?payloads=false`) the
   * spans come with null `attributes`, `events`, `links` and `status_message`.
   */
  getTraceDetails: (
    modelId: string,
    traceId: string,
    options?: { payloads?: boolean },
  ) => Promise<{ spans: SpanFromApi[]; trace_id: string }>

  /**
   * `GET experiments/{id}/traces/{trace_id}/spans/{span_id}`. Optional so API services
   * written before the endpoint existed stay assignable; without it the span is read from
   * `getTraceDetails`.
   */
  getSpan?: (modelId: string, traceId: string, spanId: string) => Promise<SpanFromApi>

  getExperimentTraces: (
    params: GetTracesParams & { experiment_id: string; cursor?: string | null },
  ) => Promise<{ items: Trace[]; cursor: string | null }>

  getAllExperimentTraces: (
    params: Omit<GetTracesParams, 'limit'> & { experiment_id: string },
  ) => Promise<Trace[]>

  getExperimentUniqueDatasetsIds: (artifactId: string) => Promise<string[]>

  getExperimentEvals: (
    params: GetExperimentEvalsParams,
  ) => Promise<{ items: GetExperimentEvalsItem[]; cursor: string | null }>

  getBatchExperimentEvals: (params: GetBatchExperimentsEvalsParams) => Promise<{
    items: (GetExperimentEvalsItem & { experiment_id: string })[]
    cursor: string | null
  }>

  getAllExperimentEvals: (params: GetExperimentEvalsParams) => Promise<GetExperimentEvalsItem[]>

  getEvalById: (experimentId: string, evalId: string) => Promise<GetExperimentEvalsItem>

  getExperimentDatasetAverageScores: (
    artifactId: string,
    datasetId: string,
    search?: string,
    filters?: string[],
  ) => Promise<ScoreInfo[]>

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

  getTypedTracesColumns: (artifactId: string) => Promise<TypedTracesColumns>

  getTypedEvalsColumns: (artifactId: string, datasetId: string) => Promise<TypedEvalsColumns>

  validateEvalsFilter: (filters: string[]) => Promise<ValidateResponseItem[]>

  validateTracesFilter: (filters: string[]) => Promise<ValidateResponseItem[]>
}

export interface ExperimentMetricHistory {
  experiment_id: string
  // Optional so consuming apps whose local response type predates the flag stay
  // assignable to ApiServiceInterface; the server always sends it at runtime.
  subsampled?: boolean
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

export interface GetBatchExperimentsEvalsParams {
  experiment_ids: string[]
  limit?: number
  cursor?: string | null
  dataset_id?: string
  search?: string
  filters?: string[]
}

/** JSON has no infinities: non-finite numbers travel as these strings. */
export type WireNumber = number | 'Infinity' | '-Infinity' | null

export interface MetricCatalogWire {
  revision: number
  bucket_min_level: number | null
  bucket_max_level: number | null
  /** Legacy metric rows the server left out, as `ExperimentMetricCatalog.skipped_rows`. */
  skipped_rows: number
  metrics: {
    key: string
    first_step: number
    last_step: number
    /** Null, like `min` and `max`, below revision 3. */
    count: number | null
    min: WireNumber
    max: WireNumber
  }[]
}

export interface MetricBucketsRequestWire {
  keys: string[]
  start_step: number | null
  end_step: number | null
  level: number
}

/** bucket, first_step, last_step, count, finite_count, min, max, sum (never infinite) */
export type MetricBucketWire = [
  number,
  number,
  number,
  number,
  number,
  WireNumber,
  WireNumber,
  number | null,
]

export interface MetricBucketsWire {
  level: number
  series: {
    key: string
    first_step: number | null
    last_step: number | null
    buckets: MetricBucketWire[]
    skipped_rows: number
  }[]
}
