import type { DatasetPreview, ExperimentPreview, FramePreview, PlotPreview } from '../model/types'

/** Deterministic pseudo-noise so fixtures stay stable across reloads. */
function wobble(index: number, scale: number): number {
  return Math.sin(index * 12.9898) * scale
}

export function curve(count: number, from: number, to: number, noise = 0.01): [number, number][] {
  const points: [number, number][] = []
  for (let i = 0; i < count; i += 1) {
    const t = i / Math.max(count - 1, 1)
    // Saturating exponential — the shape of a healthy training curve.
    const base = from + (to - from) * (1 - Math.exp(-3 * t))
    points.push([i + 1, Number((base + wobble(i, noise)).toFixed(4))])
  }
  return points
}

export function decayCurve(
  count: number,
  from: number,
  to: number,
  noise = 0.02,
): [number, number][] {
  return curve(count, from, to, noise)
}

export function rocPoints(auc: number): [number, number][] {
  const points: [number, number][] = []
  const bend = 1 + (auc - 0.5) * 6
  for (let i = 0; i <= 20; i += 1) {
    const x = i / 20
    points.push([Number(x.toFixed(3)), Number(Math.pow(x, 1 / bend).toFixed(3))])
  }
  return points
}

export function trainingCurves(finalAuc: number): { name: string; points: [number, number][] }[] {
  return [
    { name: 'train_loss', points: decayCurve(24, 0.69, 0.31 - (finalAuc - 0.8)) },
    { name: 'val_auc', points: curve(24, 0.62, finalAuc, 0.006) },
  ]
}

export function experimentPreview(
  runName: string,
  auc: number,
  config: Record<string, number | string>,
  trackerRef?: string,
): ExperimentPreview {
  return {
    type: 'experiment',
    runName,
    mainMetric: { name: 'val_auc', value: auc },
    metrics: [],
    config,
    curves: trainingCurves(auc),
    tracker: trackerRef
      ? {
          id: trackerRef,
          group: 'churn',
          state: 'ok',
          url: '/experiments/churn/run',
          store: 'experiments',
          tags: ['main', 'train_model'],
          sentence: '',
          recorded_step: 22,
        }
      : undefined,
  }
}

export const customersDataset: DatasetPreview = {
  type: 'dataset',
  schema: [
    { name: 'customer_id', dtype: 'int64' },
    { name: 'tenure_months', dtype: 'int64' },
    { name: 'monthly_charges', dtype: 'float64' },
    { name: 'contract', dtype: 'object' },
    { name: 'payment_method', dtype: 'object' },
    { name: 'churned', dtype: 'bool' },
  ],
  head: [
    [1001, 34, 71.3, 'month-to-month', 'credit card', 'False'],
    [1002, 2, 89.9, 'month-to-month', 'e-check', 'True'],
    [1003, 61, 24.5, 'two-year', 'bank transfer', 'False'],
    [1004, 11, 55.0, 'one-year', 'credit card', 'False'],
    [1005, 5, 99.2, 'month-to-month', 'e-check', 'True'],
  ],
  totalRows: 84312,
  sizeBytes: 14_680_064,
}

export const cleanFrame: FramePreview = {
  type: 'frame',
  columns: ['customer_id', 'tenure_months', 'monthly_charges', 'contract', 'churned'],
  dtypes: ['int64', 'int64', 'float64', 'category', 'bool'],
  rows: [
    [1001, 34, 71.3, 'month-to-month', 'False'],
    [1002, 2, 89.9, 'month-to-month', 'True'],
    [1003, 61, 24.5, 'two-year', 'False'],
    [1004, 11, 55.0, 'one-year', 'False'],
    [1005, 5, 99.2, 'month-to-month', 'True'],
    [1006, 47, 19.9, 'two-year', 'False'],
  ],
  totalRows: 83907,
  totalColumns: 5,
}

export const trainSplitFrame: FramePreview = {
  type: 'frame',
  columns: ['tenure_bucket', 'monthly_charges', 'contract_code', 'autopay', 'churned'],
  dtypes: ['int8', 'float64', 'int8', 'bool', 'bool'],
  rows: [
    [2, 71.3, 0, 'True', 'False'],
    [0, 89.9, 0, 'False', 'True'],
    [5, 24.5, 2, 'True', 'False'],
    [1, 55.0, 1, 'True', 'False'],
    [0, 99.2, 0, 'False', 'True'],
    [4, 19.9, 2, 'True', 'False'],
  ],
  totalRows: 67125,
  totalColumns: 5,
}

export const errorAnalysisFrame: FramePreview = {
  type: 'frame',
  columns: ['customer_id', 'p_churn', 'churned', 'tenure_months', 'contract'],
  dtypes: ['int64', 'float64', 'bool', 'int64', 'category'],
  rows: [
    [4417, 0.08, 'True', 58, 'two-year'],
    [2093, 0.11, 'True', 44, 'one-year'],
    [7810, 0.93, 'False', 3, 'month-to-month'],
    [1266, 0.89, 'False', 6, 'month-to-month'],
    [5521, 0.14, 'True', 39, 'two-year'],
  ],
  totalRows: 412,
  totalColumns: 5,
}

export function rocPlot(auc: number): PlotPreview {
  return {
    type: 'plot',
    title: `ROC · holdout (AUC ${auc.toFixed(3)})`,
    kind: 'line',
    series: [
      { label: 'model', points: rocPoints(auc) },
      {
        label: 'chance',
        points: [
          [0, 0],
          [1, 1],
        ],
        color: 'var(--p-surface-400)',
      },
    ],
    xLabel: 'false positive rate',
    yLabel: 'true positive rate',
  }
}

export const summaryNote = `## Churn model: state of play

Best holdout **val_auc 0.856** from the lr sweep (\`exp/lr-1e3\`), up from the
0.841 baseline. Tenure buckets carry most of the lift. Dropping
\`payment_method\` costs ~0.004 and is not worth it.

Next: adopt the sweep winner onto \`main\`, then rerun \`holdout_eval\`
against the refreshed split.`
