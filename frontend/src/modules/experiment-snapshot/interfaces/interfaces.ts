import type { Database } from 'sql.js'

export interface ExperimentSnapshotProvider {
  init: (data: any[]) => Promise<void>
  getDynamicMetricsNames: (signal?: AbortSignal) => Promise<string[]>
  getDynamicMetricData: (
    metricName: string,
    signal?: AbortSignal,
  ) => Promise<ExperimentSnapshotDynamicMetric[]>
  getStaticParamsList: (signal?: AbortSignal) => Promise<ExperimentSnapshotStaticParams[]>
  getEvalsList: (signal?: AbortSignal) => Promise<EvalsListType>
  getTraceSpans: (modelId: string, traceId: string) => Promise<SpansListType>
  buildSpanTree: (spans: Omit<TraceSpan, 'children'>[]) => Promise<TraceSpan[]>
  getTraceId: (params: SpansParams) => Promise<any>
  getUniqueTraceIds: (modelId: string) => Promise<string[]>
}

export type GetDynamicMetricsListResult = Record<string, ExperimentSnapshotDynamicMetric[]>

export interface ExperimentSnapshotStaticParams {
  eval_dataset: string
  eval_version: string
  evaluation_metrics: string[]
  model_type: string
  modelId: string
}

export interface ExperimentSnapshotDynamicMetrics
  extends Record<string, ExperimentSnapshotDynamicMetric> {}

export interface ExperimentSnapshotDynamicMetric {
  x: number[]
  y: number[]
  modelId: string
  aggregated: boolean
}

export interface EvalsDatasets extends Record<string, EvalsInfo[]> {}

export interface EvalsInfo {
  id: string
  dataset_id: string
  inputs: Record<string, string | number>
  outputs: Record<string, string | number>
  refs: Record<string, string | number>
  scores: Record<string, string | number>
  metadata: Record<string, string | number>
  modelId: string
}

export interface ModelSnapshot {
  modelId: string
  database: Database
}

export interface ModelInfo {
  name: string
  color: string
}

export interface ModelsInfo extends Record<string, ModelInfo> {}

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
  status_code: number
  status_message: string | null
  attributes: string
  events: string | null
  links: string | null
  children: TraceSpan[]
  dfs_span_type: SpanTypeEnum | null
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
