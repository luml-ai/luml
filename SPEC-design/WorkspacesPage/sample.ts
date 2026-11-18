import type { WorkspaceFolderItem } from '@/blocks/WorkspaceFolder/interface'
import { workspaceDirectory, workspaceItems } from '@/fixtures/workspaces'

// Sample data for UIP-002: the same directory as `Pages/Lumlflow/WorkspacesPage`, now with
// its plain files listed after the notebooks and folders (the store's order: flow, folder, file).

const dir = workspaceDirectory

function file(name: string, size: number): WorkspaceFolderItem {
  return {
    id: `${dir}/${name}`,
    name,
    type: 'file',
    path: `${dir}/${name}`,
    size,
  }
}

export const filesListed: WorkspaceFolderItem[] = [
  ...workspaceItems,
  file('README.md', 1840),
  file('demand_forecaster.luml', 2400000),
  file('churn_gbm_experiment.luml', 3400000),
  file('churn_features.parquet', 4200000),
  file('customers_sample.csv', 86000),
  file('gbm_model.pkl', 12600000),
  file('params.yaml', 412),
  file('train.py', 2310),
  file('train.log', 1960),
  file('config.json', 638),
  file('customers.luml', 5100000),
  file('roc_curve.png', 48200),
  file('feature_importance.svg', 9400),
  file('model_report.pdf', 312000),
  file('eda_report.html', 74000),
  file('demo_walkthrough.mp4', 18400000),
  file('call_sample.wav', 2100000),
]

// product:PROP-004 B-14: the folders a file can be moved to (the "Move to…" dialog).
export const moveTargets = ['archive', 'data', 'reports']

export const trainPy = `import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split

import yaml

params = yaml.safe_load(open("params.yaml"))
df = pd.read_parquet("churn_features.parquet")

X = df.drop(columns=["churned"])
y = df["churned"]
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=params["seed"]
)

model = LGBMClassifier(**params["gbm"])
model.fit(X_train, y_train, eval_set=[(X_val, y_val)])
`

export const trainLog = `2026-11-04 16:42:03 INFO  train: params loaded from params.yaml (seed=42)
2026-11-04 16:42:03 INFO  train: churn_features.parquet: 48,120 rows, 37 columns
2026-11-04 16:42:04 INFO  train: split 38,496 / 9,624 (stratified)
2026-11-04 16:42:04 INFO  lightgbm: start training, 400 rounds, early stopping 50
2026-11-04 16:42:09 INFO  lightgbm: [50]  valid auc 0.8412
2026-11-04 16:42:14 INFO  lightgbm: [100] valid auc 0.8597
2026-11-04 16:42:19 INFO  lightgbm: [150] valid auc 0.8671
2026-11-04 16:42:24 INFO  lightgbm: [200] valid auc 0.8703
2026-11-04 16:42:29 WARN  lightgbm: no improvement for 50 rounds, stopping at [231]
2026-11-04 16:42:29 INFO  train: best iteration 181, valid auc 0.8709
2026-11-04 16:42:30 INFO  train: saved gbm_model.pkl (12.6 MB)
2026-11-04 16:42:30 INFO  train: done in 27.4s
`

export const readmeMd = `# Churn model

Predicts which customers cancel in the next 90 days.

## Data
- \`churn_features.parquet\`: one row per customer, 42 features, label \`churned\`.
- \`customers_sample.csv\`: 1,000 rows for quick checks.

## Notebooks
- **churn-baseline**: logistic regression baseline.
- **gbm-tuning**: LightGBM with the search space in \`params.yaml\`.
`

const customerRows = [
  ['C-10021', '34', 'Two year', '79.85', 'no'],
  ['C-10022', '2', 'Month-to-month', '53.10', 'yes'],
  ['C-10023', '58', 'One year', '104.20', 'no'],
  ['C-10024', '11', 'Month-to-month', '70.70', 'yes'],
  ['C-10025', '45', 'Two year', '42.30', 'no'],
  ['C-10026', '7', 'Month-to-month', '89.10', 'yes'],
  ['C-10027', '23', 'One year', '29.75', 'no'],
  ['C-10028', '61', 'Two year', '110.05', 'no'],
  ['C-10029', '1', 'Month-to-month', '20.20', 'yes'],
  ['C-10030', '16', 'One year', '65.60', 'no'],
]

export const customersTable = {
  headers: ['customer_id', 'tenure_months', 'contract_type', 'monthly_charges', 'churned'],
  rows: customerRows.map(
    ([customer_id, tenure_months, contract_type, monthly_charges, churned]) => ({
      customer_id,
      tenure_months,
      contract_type,
      monthly_charges,
      churned,
    }),
  ),
  rowsCount: 1000,
}

const featureRows = [
  ['C-10021', '34', '79.85', '2714.90', '0', '1', '0'],
  ['C-10022', '2', '53.10', '106.20', '3', '0', '1'],
  ['C-10023', '58', '104.20', '6043.60', '1', '1', '0'],
  ['C-10024', '11', '70.70', '777.70', '2', '0', '1'],
  ['C-10025', '45', '42.30', '1903.50', '0', '1', '0'],
  ['C-10026', '7', '89.10', '623.70', '4', '0', '1'],
  ['C-10027', '23', '29.75', '684.25', '0', '0', '0'],
  ['C-10028', '61', '110.05', '6713.05', '1', '1', '0'],
  ['C-10029', '1', '20.20', '20.20', '0', '0', '1'],
  ['C-10030', '16', '65.60', '1049.60', '1', '1', '0'],
]

const featureHeaders = [
  'customer_id',
  'tenure_months',
  'monthly_charges',
  'total_charges',
  'support_tickets_90d',
  'auto_pay',
  'churned',
]

export const churnFeaturesTable = {
  headers: featureHeaders,
  rows: featureRows.map((row) =>
    Object.fromEntries(featureHeaders.map((header, i) => [header, row[i]])),
  ),
  rowsCount: 70432,
}

export const paramsYaml = `# Training settings for gbm-tuning
seed: 42
target: churned
test_size: 0.2

gbm:
  n_estimators: 400
  learning_rate: 0.03
  num_leaves: 31
  min_child_samples: 50
  subsample: 0.8
  colsample_bytree: 0.9
`

export const configJsonRaw =
  '{"project":"churn-model","version":3,"data":{"features":"churn_features.parquet","sample":"customers_sample.csv","label":"churned"},"tracking":{"group":"churn-model","tags":["lightgbm","baseline"]},"upload":{"collection":"customer-churn","auto":false}}'

export const configJsonPretty = JSON.stringify(JSON.parse(configJsonRaw), null, 2)

// A small chart as an inline SVG; it stands in for roc_curve.png (B-02) and is also the .svg sample.
export const chartSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320" width="480" height="320">
  <rect width="480" height="320" fill="#ffffff"/>
  <line x1="48" y1="272" x2="448" y2="272" stroke="#9ca3af" stroke-width="1"/>
  <line x1="48" y1="24" x2="48" y2="272" stroke="#9ca3af" stroke-width="1"/>
  <line x1="48" y1="272" x2="448" y2="24" stroke="#d1d5db" stroke-dasharray="6 6"/>
  <path d="M48 272 C 90 140, 150 90, 230 60 S 380 30, 448 24" fill="none" stroke="#2563eb" stroke-width="3"/>
  <text x="248" y="300" font-family="sans-serif" font-size="13" fill="#6b7280" text-anchor="middle">False positive rate</text>
  <text x="18" y="150" font-family="sans-serif" font-size="13" fill="#6b7280" text-anchor="middle" transform="rotate(-90 18 150)">True positive rate</text>
  <text x="300" y="130" font-family="sans-serif" font-size="14" fill="#1f2937">AUC = 0.91</text>
</svg>`

export const chartImageUrl = `data:image/svg+xml;utf8,${encodeURIComponent(chartSvg)}`

export const edaReportHtml = `<!doctype html>
<html><head><meta charset="utf-8"><style>
  body { font-family: sans-serif; color: #1f2937; margin: 24px; }
  h1 { font-size: 20px; margin: 0 0 12px; }
  table { border-collapse: collapse; font-size: 13px; }
  td, th { border: 1px solid #e5e7eb; padding: 4px 10px; text-align: left; }
  th { background: #f3f4f6; }
</style></head>
<body>
  <h1>EDA report: churn_features.parquet</h1>
  <p>70,432 rows · 42 columns · 2.1% missing values</p>
  <table>
    <tr><th>column</th><th>type</th><th>missing</th><th>mean</th></tr>
    <tr><td>tenure_months</td><td>int</td><td>0</td><td>32.4</td></tr>
    <tr><td>monthly_charges</td><td>float</td><td>0</td><td>64.8</td></tr>
    <tr><td>total_charges</td><td>float</td><td>11</td><td>2283.3</td></tr>
    <tr><td>support_tickets_90d</td><td>int</td><td>0</td><td>1.2</td></tr>
  </table>
</body></html>`

// A dataset `.luml` (luml/artifacts/dataset): tabular, one subset with train / test splits,
// shown as data first (product:PROP-004 B-11).
const datasetHeaders = ['customer_id', 'tenure_months', 'contract_type', 'monthly_charges', 'churned']

export const customersDatasetLuml = {
  kind: 'dataset' as const,
  manifestYaml: `artifact_type: dataset
variant: tabular
name: customers
description: Customer records with the churn label, train / test split.
version: '2'
producer_name: luml.ai
producer_version: 0.1.0
producer_tags:
- luml.ai::dataset_tabular:v1
payload:
  file_format: parquet
  total_rows: 70432
  subsets:
    default:
      splits:
        train:
          file_format: parquet
          num_rows: 56345
          num_chunks: 1
          chunk_files:
          - data/default/train/chunk_000.parquet
        test:
          file_format: parquet
          num_rows: 14087
          num_chunks: 1
          chunk_files:
          - data/default/test/chunk_000.parquet
`,
  contents: [
    { path: 'manifest.json', size: '0.7 KB' },
    { path: 'data/', folder: true },
    { path: 'data/default/train/chunk_000.parquet', size: '4.1 MB' },
    { path: 'data/default/test/chunk_000.parquet', size: '1.0 MB' },
  ],
  data: {
    tabs: ['default / train', 'default / test'],
    activeTab: 'default / train',
    table: {
      headers: datasetHeaders,
      rows: customerRows.map((row) => Object.fromEntries(datasetHeaders.map((header, i) => [header, row[i]]))),
      rowsCount: 56345,
    },
  },
}

// A model `.luml`: its fnnx manifest.json, shown as YAML, and the archive's files.
export const forecasterLuml = {
  kind: 'model' as const,
  manifestYaml: `variant: pyfunc
name: demand_forecaster
version: null
description: Demo multi-horizon forecaster (1/7/30 steps) with a reference profile.
producer_name: luml.ai
producer_version: 0.1.0
producer_tags:
- luml.ai::sklearn:v1
- luml.ai::kind_tabular:v1
- luml.ai::tabular_monitoring:v1
inputs:
- name: lag_1
  content_type: NDJSON
  dtype: Array[float]
  tags: null
  shape:
  - batch
- name: lag_2
  content_type: NDJSON
  dtype: Array[float]
  tags: null
  shape:
  - batch
- name: lag_3
  content_type: NDJSON
  dtype: Array[float]
  tags: null
  shape:
  - batch
- name: lag_4
  content_type: NDJSON
  dtype: Array[float]
  tags: null
  shape:
  - batch
- name: lag_5
  content_type: NDJSON
  dtype: Array[float]
  tags: null
  shape:
  - batch
- name: lag_6
  content_type: NDJSON
  dtype: Array[float]
  tags: null
  shape:
  - batch
outputs:
- name: y
  content_type: NDJSON
  dtype: Array[float]
  tags: null
  shape:
  - batch
  - 3
dynamic_attributes: []
env_vars: []
`,
  contents: [
    { path: 'manifest.json', size: '1.6 KB' },
    { path: 'dtypes.json', size: '0.4 KB' },
    { path: 'env.json', size: '0.6 KB' },
    { path: 'meta.json', size: '5.2 KB' },
    { path: 'ops/', folder: true },
    { path: 'ops/model.pkl', size: '2.31 MB' },
    { path: 'ops/predict.py', size: '1.1 KB' },
  ],
}

// An experiment `.luml` (luml/artifacts/experiment.py save_experiment).
export const experimentLuml = {
  kind: 'experiment' as const,
  manifestYaml: `artifact_type: experiment
variant: default
name: gbm_baseline
description: null
version: '1'
producer_name: luml.ai
producer_version: 0.1.0
producer_tags:
- luml.ai::experiment_snapshot:v1
payload:
  local_experiment_id: 7f3c2a91-4b0e-4d2a-9c61-2e8f5d0b1a47
  status: completed
  group: churn-model
  tags:
  - lightgbm
  - baseline
`,
  contents: [
    { path: 'manifest.json', size: '0.5 KB' },
    { path: 'exp.db.zip', size: '2.9 MB' },
    { path: 'attachments.tar', size: '480 KB' },
    { path: 'attachments.index.json', size: '1.3 KB' },
  ],
}
