import type { Database } from 'sql.js'

export interface ExperimentSnapshotProvider {
  getStaticParamsList: () => Promise<ExperimentSnapshotStaticParams[]>
  getDynamicMetricsList: () => Promise<ExperimentSnapshotDynamicMetrics[]>
  getEvalsList: () => Promise<Record<string, EvalsInfo[]> | null>
}

export interface ExperimentSnapshotStaticParams {
  eval_dataset: string
  eval_version: string
  evaluation_metrics: string[]
  model_type: string
  modelId: number
}

export interface ExperimentSnapshotDynamicMetrics
  extends Record<string, ExperimentSnapshotDynamicMetric> {}

export interface ExperimentSnapshotDynamicMetric {
  x: number[]
  y: number[]
  modelId: number
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
  modelId: number
}

export interface ModelSnapshot {
  modelId: number
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
  modelId: number | string
  scores: ScoreInfo[]
}
