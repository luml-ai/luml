import {
  Tasks,
  type ClassificationMetrics,
  type RegressionMetrics,
  type TrainingData,
  type TrainingImportance,
} from '../../../src/lib/data-processing/interfaces'

export const MOCK_MODEL_ID = 'mock-model-id'

export const MOCK_MODEL_BYTES: Record<number, number> = { 0: 1, 1: 2, 2: 3, 3: 4 }

export function makeClassificationMetrics(
  overrides: Partial<ClassificationMetrics> = {},
): ClassificationMetrics {
  return {
    ACC: 0.92,
    PRECISION: 0.9,
    RECALL: 0.88,
    F1: 0.89,
    SC_SCORE: 0.91,
    ...overrides,
  }
}

export function makeRegressionMetrics(
  overrides: Partial<RegressionMetrics> = {},
): RegressionMetrics {
  return {
    MSE: 0.05,
    RMSE: 0.22,
    MAE: 0.15,
    R2: 0.87,
    SC_SCORE: 0.85,
    ...overrides,
  }
}

export function makeImportances(): TrainingImportance[] {
  return [
    { feature_name: 'feature_a', scaled_importance: 0.45 },
    { feature_name: 'feature_b', scaled_importance: 0.3 },
    { feature_name: 'feature_c', scaled_importance: 0.15 },
    { feature_name: 'feature_d', scaled_importance: 0.07 },
    { feature_name: 'feature_e', scaled_importance: 0.03 },
  ]
}

export function makePredictedData(): Record<string, []> {
  
  return {
    feature_a: [1, 2, 3] as unknown as [],
    feature_b: [4, 5, 6] as unknown as [],
    '<=PREDICTED=>': ['A', 'B', 'A'] as unknown as [],
  }
}

export function makeClassificationTrainingResult(
  overrides: Partial<TrainingData<ClassificationMetrics>> = {},
): TrainingData<ClassificationMetrics> {
  return {
    status: 'success',
    model_id: MOCK_MODEL_ID,
    model: MOCK_MODEL_BYTES,
    importances: makeImportances(),
    predicted_data: makePredictedData(),
    predicted_data_type: 'test',
    test_metrics: makeClassificationMetrics(),
    train_metrics: makeClassificationMetrics({ ACC: 0.95 }),
    ...overrides,
  }
}

export function makeRegressionTrainingResult(
  overrides: Partial<TrainingData<RegressionMetrics>> = {},
): TrainingData<RegressionMetrics> {
  return {
    status: 'success',
    model_id: MOCK_MODEL_ID,
    model: MOCK_MODEL_BYTES,
    importances: makeImportances(),
    predicted_data: makePredictedData(),
    predicted_data_type: 'test',
    test_metrics: makeRegressionMetrics(),
    train_metrics: makeRegressionMetrics({ R2: 0.92 }),
    ...overrides,
  }
}

export function makeTrainingError(message = 'Training failed') {
  return { status: 'error', error_message: message }
}

export function makePromptOptimizationResult(overrides: Record<string, unknown> = {}) {
  return {
    status: 'success',
    model_id: MOCK_MODEL_ID,
    model: MOCK_MODEL_BYTES,
    ...overrides,
  }
}

export function makePredictResult(overrides: Record<string, unknown> = {}) {
  return {
    status: 'success',
    predictions: { result: ['A'] },
    ...overrides,
  }
}

import type { Page } from '@playwright/test'

export async function injectConnectedProviders(
  page: Page,
  options: { openAiKey?: string; ollamaBase?: string } = {},
) {
  const { openAiKey = 'fake-openai-key', ollamaBase = 'http://localhost:11434' } = options

  await page.addInitScript(
    ({ openAiKey, ollamaBase }) => {
      localStorage.setItem(
        'providersSettings',
        JSON.stringify({
          saveApiKeys: true,
          openAi: { apiKey: openAiKey },
          ollama: { apiBase: ollamaBase },
        }),
      )
    },
    { openAiKey, ollamaBase },
  )
}
export const TASKS = Tasks