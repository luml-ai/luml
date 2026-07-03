import type { PayloadData, PromptFusionPayload } from '../promt-fusion/prompt-fusion.interfaces'

export enum WebworkerMessage {
  LOAD_PYODIDE = 'LOAD_PYODIDE',
  // TABULAR_PREDICT = 'tabular_predict',
  // TABULAR_TRAIN = 'tabular_train',
  // TABULAR_DEALLOCATE = 'tabular_deallocate',
  INVOKE_ROUTE = 'invokeRoute',
  INTERRUPT = 'interrupt',
}

export enum WEBWORKER_ROUTES_ENUM {
  TABULAR_TRAIN = '/tabular/train',
  TABULAR_PREDICT = '/tabular/predict',
  TABULAR_DEALLOCATE = '/tabular/deallocate',
  FORECASTING_TRAIN = '/forecasting/train',
  FORECASTING_PREDICT = '/forecasting/predict',
  FORECASTING_DEALLOCATE = '/forecasting/deallocate',
  PROMPT_OPTIMIZATION_TRAIN = '/prompt_optimization/train',
  PROMPT_OPTIMIZATION_PREDICT = '/prompt_optimization/predict',
  STORE_DEALLOCATE = '/store/deallocate',
  PYFUNC_INIT = '/pyfunc/init',
  PYFUNC_COMPUTE = '/pyfunc/compute',
  PYFUNC_DEINIT = '/pyfunc/deinit',
}

export enum Tasks {
  TABULAR_CLASSIFICATION = 'tabular_classification',
  TABULAR_REGRESSION = 'tabular_regression',
  FORECASTING = 'forecasting',
}

export interface TaskPayload {
  data: object
  target: string
  groups?: string[]
  task: Tasks.TABULAR_CLASSIFICATION | Tasks.TABULAR_REGRESSION
}

export interface TrainingData<T extends ClassificationMetrics | RegressionMetrics> {
  importances: TrainingImportance[]
  model: object
  model_id: string
  predicted_data: Record<string, []>
  predicted_data_type: PredictedDataType
  test_metrics: T
  train_metrics: T
  status: TrainingStatus
  error_message?: string
}

type PredictedDataType = 'train' | 'test'

type TrainingStatus = 'success' | 'error'

export interface TrainingImportance {
  feature_name: string
  scaled_importance: number
}

export interface ClassificationMetrics {
  ACC: number
  PRECISION: number
  RECALL: number
  F1: number
  SC_SCORE: number
}

export interface RegressionMetrics {
  MSE: number
  RMSE: number
  MAE: number
  R2: number
  SC_SCORE: number
}

export interface PredictRequestData {
  data: object
  model_id: string
}

export interface PredictResponse {
  status: 'success' | 'error'
  error_message?: string
  predictions: (string | number | object)[]
}

export interface TabularMetrics {
  performance: {
    eval_cv?: ClassificationMetrics | RegressionMetrics
    eval_holdout?: ClassificationMetrics | RegressionMetrics
    train: ClassificationMetrics | RegressionMetrics
  }
  permutation_feature_importance_train: {
    importances: TrainingImportance[]
  }
}

export interface PromptOptimizationData {
  task_spec: PromptFusionPayload
}

export interface TabularModelMetadataPayload {
  metrics: TabularMetrics
}

export type PromptOptimizationModelMetadataPayload = PayloadData

export type ForecastingFrequency = 'day' | 'week' | 'month' | 'quarter' | 'year'

export interface ForecastingMetrics {
  MAE: number
  RMSE: number
  MAPE: number | null
  R2: number
  SC_SCORE: number
}

export type ForecastingTrainMetrics = Omit<ForecastingMetrics, 'SC_SCORE'>

export interface ForecastingSeriesConfig {
  order: [number, number, number]
  seasonal_order: [number, number, number, number]
  trend: string
  min_history: number
}

export interface ForecastingModelConfig {
  frequency: ForecastingFrequency
  seasonal_period: number
  date_col: string
  target_col: string
  aux_cols: string[]
  known_future_cols: string[]
  min_history: number
  series: Record<string, ForecastingSeriesConfig>
}

export type ForecastingTrainingTable = Record<string, (string | number)[]>

export interface ForecastingTrainPayload {
  data: ForecastingTrainingTable
  date_col: string
  target_col: string
  aux_cols?: string[]
  known_future_cols?: string[]
  frequency: ForecastingFrequency
  preview_horizon?: number | null
}

export interface ForecastPoint {
  date: string
  value: number
  lower?: number
  upper?: number
}

export interface ForecastingSeriesChart {
  actuals: ForecastPoint[]
  test_fit?: ForecastPoint[]
  future?: ForecastPoint[]
}

export interface ForecastingChart {
  split_date: string | null
  series: Record<string, ForecastingSeriesChart>
}

export type ForecastingRecord = Record<string, string | number>

export interface ForecastingPredictRequest {
  model_id: string
  history: ForecastingRecord[]
  horizon: number
  future?: ForecastingRecord[]
}

export type ForecastPredictedRecord = Record<string, string | number>

export interface WorkerErrorResponse {
  status: 'error'
  error_type?: string
  error_message: string
  traceback?: string
}

export interface ForecastingTrainingData {
  status: 'success'
  model_id: string
  train_metrics: ForecastingTrainMetrics
  test_metrics: ForecastingMetrics
  model_config: ForecastingModelConfig
  chart: ForecastingChart
  model: object
}

export type ForecastingTrainResponse = ForecastingTrainingData | WorkerErrorResponse

export interface ForecastingPredictSuccess {
  status: 'success'
  forecast: ForecastPredictedRecord[]
}

export type ForecastingPredictResponse = ForecastingPredictSuccess | WorkerErrorResponse
