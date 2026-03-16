import type {
  AddAnnotationPayload,
  Annotation,
  AnnotationSummary,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'
import type { Trace } from '@/providers/ExperimentSnapshotApiProvider.interface'
import type { Database } from 'sql.js'

export interface ExperimentSnapshotProvider {
  init: (data: any) => Promise<void>
  getDynamicMetricsNames: (signal?: AbortSignal) => Promise<string[]>
  getDynamicMetricData: (
    metricName: string,
    signal?: AbortSignal,
  ) => Promise<ExperimentSnapshotDynamicMetric[]>
  getStaticParamsList: (signal?: AbortSignal) => Promise<ExperimentSnapshotStaticParams[]>
  getEvalsColumns: (datasetId: string, signal?: AbortSignal) => Promise<EvalsColumns>
  getTraceSpans: (modelId: string, traceId: string) => Promise<SpansListType>
  buildSpanTree: (spans: Omit<TraceSpan, 'children'>[]) => Promise<TraceSpan[]>
  getTraceId: (params: SpansParams) => Promise<any>
  getUniqueDatasetsIds: () => Promise<string[]>
  getNextEvalsByDatasetId: (params: GetEvalsByDatasetParams) => Promise<EvalsInfo[]>
  resetEvalsDatasetsRequestParams: () => Promise<void>
  resetDatasetPage: (datasetId: string) => Promise<void>
  getDatasetAverageScores: (datasetId: string) => Promise<ModelScores[]>

  createEvalAnnotation?: (
    artifactId: string,
    datasetId: string,
    evalId: string,
    data: AddAnnotationPayload,
  ) => Promise<Annotation>

  updateEvalAnnotation?: (
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) => Promise<Annotation>

  getEvalAnnotations: (
    artifactId: string,
    datasetId: string,
    evalId: string,
  ) => Promise<Annotation[]>

  deleteEvalAnnotation?: (artifactId: string, annotationId: string) => Promise<void>

  createSpanAnnotation?: (
    artifactId: string,
    traceId: string,
    spanId: string,
    data: AddAnnotationPayload,
  ) => Promise<Annotation>

  updateSpanAnnotation?: (
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) => Promise<Annotation>

  deleteSpanAnnotation?: (artifactId: string, annotationId: string) => Promise<void>

  getEvalsDatasetAnnotationsSummary: (datasetId: string) => Promise<AnnotationSummary>

  getTraces: (params: GetTracesParams) => Promise<Trace[]>

  resetTracesRequestParams: (artifactId?: string) => Promise<void>

  getEvalById: (artifactId: string, evalId: string) => Promise<EvalsInfo>

  getSpanAnnotations: (artifactId: string, traceId: string, spanId: string) => Promise<Annotation[]>

  getTracesAnnotationSummary: (artifactId: string) => Promise<AnnotationSummary>
}

export type GetDynamicMetricsListResult = Record<string, ExperimentSnapshotDynamicMetric[]>

export interface ExperimentSnapshotStaticParams {
  eval_dataset: string
  eval_version: string
  evaluation_metrics: string[]
  model_type: string
  modelId: string
}

export type ExperimentSnapshotDynamicMetrics = Record<string, ExperimentSnapshotDynamicMetric>

export interface ExperimentSnapshotDynamicMetric {
  x: number[]
  y: number[]
  modelId: string
  aggregated: boolean
}

export type EvalsDatasets = Record<string, EvalsInfo[]>

export interface EvalsColumns {
  inputs: string[]
  outputs: string[]
  refs: string[]
  scores: string[]
  metadata: string[]
}

export interface EvalsInfo {
  id: string
  dataset_id: string
  inputs: Record<string, string | number>
  outputs: Record<string, string | number>
  refs: Record<string, string | number>
  scores: Record<string, string | number>
  metadata: Record<string, string | number>
  modelId: string
  annotations: AnnotationSummary | null
}

export interface ModelSnapshot {
  modelId: string
  database: Database
}

export interface ModelInfo {
  name: string
  color: string
}

export type ModelsInfo = Record<string, ModelInfo>

export interface ScoreInfo {
  name: string
  value: number
}

export interface ModelScores {
  modelId: string
  scores: ScoreInfo[]
}

export interface SpansParams {
  modelId: string
  datasetId: string
  evalId: string
}

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
  attributes: string
  events: string | null
  links: string | null
  children: TraceSpan[]
  dfs_span_type: SpanTypeEnum | null
  annotation_count: number
}

export enum SpanTypeEnum {
  DEFAULT = 0,
  CHAT = 1,
  AGENT = 2,
  TOOL = 3,
  EMBEDDER = 4,
  RERANKER = 5,
}

export type EvalsListType = Record<string, EvalsInfo[]> | null

export type SpansListType = Omit<TraceSpan, 'children'>[] | null

export interface BaseTraceInfo {
  traceId: string
  count: number
  minTime: number | null
  maxTime: number | null
  tree: TraceSpan[]
}

export interface EvalTraceInfo extends BaseTraceInfo {
  modelId: string
  datasetId: string
  evalId: string
}

export interface GetEvalsByDatasetParams {
  limit: number
  sort_by: 'created_at'
  order: 'asc' | 'desc'
  dataset_id: string
  search: string
}

export interface GetTracesParams {
  limit: number
  sort_by: 'created_at' | 'execution_time' | 'span_count'
  order: 'asc' | 'desc'
  search: string
}
