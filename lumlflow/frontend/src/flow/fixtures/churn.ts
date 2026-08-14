/**
 * Scenario (a): tabular churn.
 *
 * Deliberately adversarial. It contains, and a concept that renders it well must
 * survive: a rename (`Cleaned` → `CleanChurn`), a structural branch that drops
 * one asset and adds another, a failed materialization followed by a fix, a
 * definition fan at `Features`, a value fan at `TrainGBM` from a sweep, and —
 * the one that matters most — divergent pins, because the sweep branches forked
 * before the `RawChurn` data fix and never took it. Every metric comparison
 * between a sweep branch and a feature branch is therefore apples to oranges,
 * and the comparison surface has to say so.
 */

import type { AssetVersion, Branch, FlowSession, Materialization } from '../types'
import { curve, makeMaterialization, makeVersion } from './helpers'

const versions: AssetVersion[] = []
const materializations: Record<string, Materialization> = {}

const push = (version: AssetVersion): AssetVersion => {
  versions.push(version)
  return version
}

// --- raw source, with the data bug and its fix ------------------------------

const rawV1 = push(
  makeVersion({
    assetId: 'a_raw',
    name: 'RawChurn',
    kind: 'source',
    source: `class RawChurn(Asset):
    """Telco churn export, pulled nightly."""
    path: str = "data/churn_2026_07.parquet"

    def materialize(self) -> Frame:
        return pd.read_parquet(self.path)`,
    doc: 'Telco churn export, pulled nightly.',
    params: { path: 'data/churn_2026_07.parquet' },
    volatility: 'external',
    outputs: [{ name: 'value', kind: 'frame', content: 'raw-with-dupes' }],
    step: 1,
    author: 'human',
    intent: 'Pull the raw churn export',
    tag: 'v1',
  }),
)

const rawV2 = push(
  makeVersion({
    assetId: 'a_raw',
    name: 'RawChurn',
    kind: 'source',
    source: `class RawChurn(Asset):
    """Telco churn export, pulled nightly. Dedupes on customer_id —
    the July export double-counts ~4% of rows."""
    path: str = "data/churn_2026_07.parquet"

    def materialize(self) -> Frame:
        df = pd.read_parquet(self.path)
        return df.drop_duplicates(subset="customer_id", keep="last")`,
    doc: 'Telco churn export, pulled nightly. Dedupes on customer_id.',
    params: { path: 'data/churn_2026_07.parquet' },
    volatility: 'external',
    outputs: [{ name: 'value', kind: 'frame', content: 'raw-deduped' }],
    step: 22,
    author: 'human',
    intent: 'Fix duplicate customer rows in the July export',
    tag: 'v2',
  }),
)

// --- EDA --------------------------------------------------------------------

const profile = push(
  makeVersion({
    assetId: 'a_profile',
    name: 'ChurnProfile',
    kind: 'note',
    deps: ['a_raw'],
    source: `class ChurnProfile(Asset):
    """What the churn export actually contains."""
    raw: RawChurn

    def materialize(self) -> Note:
        return Note(f"{len(self.raw)} rows, {self.raw.churn.mean():.1%} churn rate")`,
    doc: 'What the churn export actually contains.',
    outputs: [{ name: 'value', kind: 'note', content: 'profile' }],
    step: 2,
    author: 'human',
    intent: 'Look at the raw export',
    tag: 'v1',
  }),
)

const missingness = push(
  makeVersion({
    assetId: 'a_missing',
    name: 'MissingnessPlot',
    kind: 'plot',
    deps: ['a_raw'],
    source: `class MissingnessPlot(Asset):
    """Null rate per column. total_charges is the one to worry about."""
    raw: RawChurn

    def materialize(self) -> Plot:
        return bar(self.raw.isna().mean().sort_values())`,
    doc: 'Null rate per column.',
    outputs: [{ name: 'value', kind: 'plot', content: 'missingness' }],
    step: 3,
    author: 'agent-1',
    intent: 'Chart missingness before cleaning',
    tag: 'v1',
  }),
)

const balance = push(
  makeVersion({
    assetId: 'a_balance',
    name: 'TargetBalance',
    kind: 'plot',
    deps: ['a_raw'],
    source: `class TargetBalance(Asset):
    """Class balance. 26.5% positive, imbalanced but not pathologically."""
    raw: RawChurn

    def materialize(self) -> Plot:
        return bar(self.raw.churn.value_counts())`,
    doc: 'Class balance of the churn target.',
    outputs: [{ name: 'value', kind: 'plot', content: 'balance' }],
    step: 4,
    author: 'agent-1',
    intent: 'Chart missingness before cleaning',
    tag: 'v1',
  }),
)

// --- cleaning, including the rename -----------------------------------------

const cleanedV1 = push(
  makeVersion({
    assetId: 'a_clean',
    name: 'Cleaned',
    kind: 'frame',
    deps: ['a_raw'],
    source: `class Cleaned(Asset):
    """Coerce total_charges, drop rows with no tenure."""
    raw: RawChurn

    def materialize(self) -> Frame:
        df = self.raw.copy()
        df["total_charges"] = pd.to_numeric(df.total_charges, errors="coerce")
        return df.dropna(subset=["tenure"])`,
    doc: 'Coerce total_charges, drop rows with no tenure.',
    outputs: [{ name: 'value', kind: 'frame', content: 'clean-1' }],
    step: 5,
    author: 'agent-1',
    intent: 'Clean the raw frame',
    tag: 'v1',
  }),
)

const cleanedV2 = push(
  makeVersion({
    assetId: 'a_clean',
    name: 'CleanChurn',
    kind: 'frame',
    deps: ['a_raw'],
    source: `class CleanChurn(Asset):
    """Coerce total_charges, drop rows with no tenure."""
    raw: RawChurn

    def materialize(self) -> Frame:
        df = self.raw.copy()
        df["total_charges"] = pd.to_numeric(df.total_charges, errors="coerce")
        return df.dropna(subset=["tenure"])`,
    doc: 'Coerce total_charges, drop rows with no tenure.',
    outputs: [{ name: 'value', kind: 'frame', content: 'clean-1' }],
    step: 18,
    author: 'agent-2',
    intent: 'Rename Cleaned to CleanChurn for consistency',
    tag: 'v2',
  }),
)

// --- features: the definition fan -------------------------------------------

const featuresBase = push(
  makeVersion({
    assetId: 'a_features',
    name: 'Features',
    kind: 'frame',
    deps: ['a_clean'],
    source: `class Features(Asset):
    """One-hot contract and payment method, keep tenure raw."""
    clean: CleanChurn

    def materialize(self) -> Frame:
        return pd.get_dummies(self.clean, columns=["contract", "payment_method"])`,
    doc: 'One-hot contract and payment method, keep tenure raw.',
    outputs: [{ name: 'value', kind: 'frame', content: 'features-base' }],
    step: 6,
    author: 'agent-1',
    intent: 'Build a baseline feature set',
    tag: 'v1',
  }),
)

const featuresBuckets = push(
  makeVersion({
    assetId: 'a_features',
    name: 'Features',
    kind: 'frame',
    deps: ['a_clean'],
    params: { bucket_count: 8 },
    source: `class Features(Asset):
    """Baseline plus tenure buckets. Churn is very non-linear in tenure."""
    clean: CleanChurn
    bucket_count: int = 8

    def materialize(self) -> Frame:
        df = pd.get_dummies(self.clean, columns=["contract", "payment_method"])
        df["tenure_bucket"] = pd.qcut(df.tenure, self.bucket_count, labels=False)
        return df`,
    doc: 'Baseline plus tenure buckets. Churn is very non-linear in tenure.',
    outputs: [{ name: 'value', kind: 'frame', content: 'features-buckets' }],
    step: 12,
    author: 'agent-1',
    intent: 'Try tenure bucketing',
    tag: 'v2',
  }),
)

const featuresInteractions = push(
  makeVersion({
    assetId: 'a_features',
    name: 'Features',
    kind: 'frame',
    deps: ['a_clean'],
    source: `class Features(Asset):
    """Baseline plus contract x tenure interactions."""
    clean: CleanChurn

    def materialize(self) -> Frame:
        df = pd.get_dummies(self.clean, columns=["contract", "payment_method"])
        for col in [c for c in df if c.startswith("contract_")]:
            df[f"{col}_x_tenure"] = df[col] * df.tenure
        return df`,
    doc: 'Baseline plus contract x tenure interactions.',
    outputs: [{ name: 'value', kind: 'frame', content: 'features-inter' }],
    step: 14,
    author: 'agent-2',
    intent: 'Try contract-tenure interactions',
    tag: 'v3',
  }),
)

const split = push(
  makeVersion({
    assetId: 'a_split',
    name: 'TrainTestSplit',
    kind: 'frame',
    deps: ['a_features'],
    params: { test_size: 0.2, seed: 42 },
    source: `class TrainTestSplit(Asset):
    """Stratified 80/20 split, seed pinned so lanes are comparable."""
    features: Features
    test_size: float = 0.2
    seed: int = 42

    def materialize(self) -> Split:
        return stratified_split(self.features, self.test_size, self.seed)`,
    doc: 'Stratified 80/20 split, seed pinned so lanes are comparable.',
    volatility: 'seeded',
    outputs: [{ name: 'value', kind: 'frame', content: 'split' }],
    step: 7,
    author: 'agent-1',
    intent: 'Build a baseline feature set',
    tag: 'v1',
  }),
)

// --- training: a failure, a fix, and a sweep --------------------------------

const gbmFailed = push(
  makeVersion({
    assetId: 'a_gbm',
    name: 'TrainGBM',
    kind: 'experiment',
    deps: ['a_split'],
    params: { n_estimators: 300, learning_rate: 0.05 },
    source: `class TrainGBM(Asset):
    """Gradient boosting baseline."""
    split: TrainTestSplit
    n_estimators: int = 300
    learning_rate: float = 0.05

    def materialize(self) -> ExperimentBundle:
        model = GradientBoostingClassifier(**self.params)
        model.fit(self.split.X_train, self.split.y_train)
        return ExperimentBundle(model=model, metrics=score(model, self.split))`,
    doc: 'Gradient boosting baseline.',
    outputs: [{ name: 'model', kind: 'model', content: 'gbm-fail' }],
    step: 8,
    author: 'agent-1',
    intent: 'Train a gradient boosting baseline',
    status: 'failed',
    failureMessage:
      "TypeError: GradientBoostingClassifier() got an unexpected keyword argument 'params'",
    tag: 'v0',
  }),
)

const gbmSource = (nEstimators: number, learningRate: number): string => `class TrainGBM(Asset):
    """Gradient boosting baseline."""
    split: TrainTestSplit
    n_estimators: int = ${nEstimators}
    learning_rate: float = ${learningRate}

    def materialize(self) -> ExperimentBundle:
        model = GradientBoostingClassifier(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
        )
        model.fit(self.split.X_train, self.split.y_train)
        return ExperimentBundle(
            model=model,
            checkpoint=dump(model),
            run=tracker.log(self.params),
            metrics=score(model, self.split),
        )`

const gbmVersion = (
  tag: string,
  nEstimators: number,
  learningRate: number,
  step: number,
  author: string,
  intent: string,
): AssetVersion =>
  push(
    makeVersion({
      assetId: 'a_gbm',
      name: 'TrainGBM',
      kind: 'experiment',
      deps: ['a_split'],
      params: { n_estimators: nEstimators, learning_rate: learningRate },
      source: gbmSource(nEstimators, learningRate),
      doc: 'Gradient boosting baseline.',
      volatility: 'seeded',
      // Separate outputs so early cutoff is demonstrable: editing logging changes
      // `run` without touching `checkpoint`, so a fine-tune downstream survives.
      outputs: [
        { name: 'model', kind: 'model', content: `gbm-${tag}` },
        { name: 'checkpoint', kind: 'model', content: `gbm-ckpt-${tag}` },
        { name: 'run', kind: 'experiment', content: `gbm-run-${tag}` },
        { name: 'metrics', kind: 'metric', content: `gbm-metrics-${tag}` },
      ],
      step,
      author,
      intent,
      tag,
    }),
  )

const gbmV1 = gbmVersion('v1', 300, 0.05, 9, 'agent-1', 'Fix the constructor call and retrain')
const gbmV2 = gbmVersion('v2', 600, 0.05, 26, 'agent-3', 'Sweep n_estimators and learning_rate')
const gbmV3 = gbmVersion('v3', 300, 0.1, 27, 'agent-3', 'Sweep n_estimators and learning_rate')
const gbmV4 = gbmVersion('v4', 900, 0.03, 28, 'agent-3', 'Sweep n_estimators and learning_rate')

const logreg = push(
  makeVersion({
    assetId: 'a_logreg',
    name: 'TrainLogReg',
    kind: 'experiment',
    deps: ['a_split'],
    params: { C: 1.0 },
    source: `class TrainLogReg(Asset):
    """Regularised logistic regression, the interpretable baseline."""
    split: TrainTestSplit
    C: float = 1.0

    def materialize(self) -> ExperimentBundle:
        model = LogisticRegression(C=self.C, max_iter=2000)
        model.fit(self.split.X_train, self.split.y_train)
        return ExperimentBundle(model=model, metrics=score(model, self.split))`,
    doc: 'Regularised logistic regression, the interpretable baseline.',
    outputs: [
      { name: 'model', kind: 'model', content: 'logreg' },
      { name: 'metrics', kind: 'metric', content: 'logreg-metrics' },
    ],
    step: 30,
    author: 'agent-2',
    intent: 'Swap GBM for an interpretable baseline',
    tag: 'v1',
  }),
)

const evalGbm = push(
  makeVersion({
    assetId: 'a_eval',
    name: 'HoldoutEval',
    kind: 'eval',
    deps: ['a_gbm', 'a_split'],
    source: `class HoldoutEval(Asset):
    """Holdout scores for the trained model."""
    run: TrainGBM
    split: TrainTestSplit

    def materialize(self) -> EvalBundle:
        return evaluate(self.run.model, self.split.X_test, self.split.y_test)`,
    doc: 'Holdout scores for the trained model.',
    outputs: [{ name: 'value', kind: 'eval', content: 'eval' }],
    step: 10,
    author: 'agent-1',
    intent: 'Score the baseline on holdout',
    tag: 'v1',
  }),
)

const evalRewired = push(
  makeVersion({
    assetId: 'a_eval',
    name: 'HoldoutEval',
    kind: 'eval',
    deps: ['a_logreg', 'a_split'],
    source: `class HoldoutEval(Asset):
    """Holdout scores for the trained model."""
    run: TrainLogReg
    split: TrainTestSplit

    def materialize(self) -> EvalBundle:
        return evaluate(self.run.model, self.split.X_test, self.split.y_test)`,
    doc: 'Holdout scores for the trained model.',
    outputs: [{ name: 'value', kind: 'eval', content: 'eval-logreg' }],
    step: 31,
    author: 'agent-2',
    intent: 'Swap GBM for an interpretable baseline',
    tag: 'v2',
  }),
)

const report = push(
  makeVersion({
    assetId: 'a_report',
    name: 'Report',
    kind: 'note',
    deps: ['a_eval', 'a_balance'],
    source: `class Report(Asset):
    """What we found, for the weekly review."""
    scores: HoldoutEval
    balance: TargetBalance

    def materialize(self) -> Note:
        return Note(template.render(scores=self.scores, balance=self.balance))`,
    doc: 'What we found, for the weekly review.',
    outputs: [{ name: 'value', kind: 'note', content: 'report' }],
    step: 11,
    author: 'human',
    intent: 'Write up the baseline result',
    tag: 'v1',
  }),
)

// --- materializations -------------------------------------------------------

const frameRows = (seed: number, n: number): (string | number | null)[][] => {
  const contracts = ['Month-to-month', 'One year', 'Two year']
  return Array.from({ length: n }, (_, i) => [
    `C${(7000 + i * 37 + seed).toString().padStart(5, '0')}`,
    (i * 7 + seed) % 72,
    contracts[(i + seed) % 3],
    Number((19.5 + ((i * 13 + seed) % 90)).toFixed(2)),
    (i + seed) % 4 === 0 ? 1 : 0,
  ])
}

const frame = (seed: number, totalRows: number) => ({
  type: 'frame' as const,
  columns: ['customer_id', 'tenure', 'contract', 'monthly_charges', 'churn'],
  dtypes: ['str', 'int64', 'category', 'float64', 'int8'],
  rows: frameRows(seed, 8),
  totalRows,
})

materializations[rawV1.versionId] = makeMaterialization(rawV1, {
  costSeconds: 12,
  values: { value: frame(1, 7318) },
})
materializations[rawV2.versionId] = makeMaterialization(rawV2, {
  costSeconds: 12,
  values: { value: frame(2, 7043) },
})
materializations[profile.versionId] = makeMaterialization(profile, {
  inputVersionIds: [rawV2.versionId],
  values: {
    value: {
      type: 'note',
      markdown:
        '**7,043 rows**, 26.5% churn rate. `total_charges` is stored as text and has 11 blanks. All of them are customers with `tenure == 0`, so they are new accounts rather than bad data.',
    },
  },
})
materializations[missingness.versionId] = makeMaterialization(missingness, {
  inputVersionIds: [rawV2.versionId],
  values: {
    value: {
      type: 'plot',
      title: 'Null rate by column',
      kind: 'bar',
      xLabel: 'column',
      yLabel: 'null rate',
      series: [
        {
          label: 'null rate',
          points: [
            [0, 0.0016],
            [1, 0],
            [2, 0],
            [3, 0],
            [4, 0],
          ],
        },
      ],
    },
  },
})
materializations[balance.versionId] = makeMaterialization(balance, {
  inputVersionIds: [rawV2.versionId],
  values: {
    value: {
      type: 'plot',
      title: 'Churn class balance',
      kind: 'bar',
      xLabel: 'churn',
      yLabel: 'customers',
      series: [
        {
          label: 'customers',
          points: [
            [0, 5174],
            [1, 1869],
          ],
        },
      ],
    },
  },
})
for (const version of [cleanedV1, cleanedV2]) {
  materializations[version.versionId] = makeMaterialization(version, {
    inputVersionIds: [rawV2.versionId],
    costSeconds: 3,
    values: { value: frame(3, 7032) },
  })
}
materializations[featuresBase.versionId] = makeMaterialization(featuresBase, {
  inputVersionIds: [cleanedV2.versionId],
  costSeconds: 6,
  values: { value: frame(4, 7032) },
})
materializations[featuresBuckets.versionId] = makeMaterialization(featuresBuckets, {
  inputVersionIds: [cleanedV2.versionId],
  costSeconds: 7,
  values: { value: frame(5, 7032) },
})
materializations[featuresInteractions.versionId] = makeMaterialization(featuresInteractions, {
  inputVersionIds: [cleanedV2.versionId],
  costSeconds: 9,
  values: { value: frame(6, 7032) },
})
materializations[split.versionId] = makeMaterialization(split, {
  inputVersionIds: [featuresBase.versionId],
  costSeconds: 2,
  values: { value: frame(7, 5625) },
})
materializations[gbmFailed.versionId] = makeMaterialization(gbmFailed, {
  inputVersionIds: [split.versionId],
  state: 'failed',
  costSeconds: 4,
  cached: false,
  values: {},
})

const gbmMaterialization = (
  version: AssetVersion,
  auc: number,
  accuracy: number,
  seed: number,
  costSeconds: number,
): void => {
  materializations[version.versionId] = makeMaterialization(version, {
    inputVersionIds: [split.versionId],
    costSeconds,
    values: {
      model: { type: 'model', flavor: 'sklearn.GradientBoostingClassifier', paramCount: 300, sizeBytes: 1_240_000, signature: 'Frame[24] -> float' },
      checkpoint: { type: 'model', flavor: 'joblib', paramCount: 300, sizeBytes: 1_240_000, signature: 'gbm.joblib' },
      run: {
        type: 'experiment',
        runName: `gbm_${version.versionId}`,
        config: version.definition.params,
        curves: [
          { name: 'log_loss', points: curve(40, 0.68, 0.36, 0.02, seed) },
          { name: 'auc', points: curve(40, 0.62, auc, 0.01, seed + 1) },
        ],
        finalMetrics: { auc, accuracy },
        checkpointRef: `ckpt/${version.versionId}`,
      },
      metrics: { type: 'metric', name: 'auc', value: auc, higherIsBetter: true },
    },
    metrics: { auc, accuracy },
  })
}

gbmMaterialization(gbmV1, 0.842, 0.801, 11, 214)
gbmMaterialization(gbmV2, 0.851, 0.807, 21, 412)
gbmMaterialization(gbmV3, 0.847, 0.804, 31, 208)
gbmMaterialization(gbmV4, 0.856, 0.811, 41, 638)

materializations[logreg.versionId] = makeMaterialization(logreg, {
  inputVersionIds: [split.versionId],
  costSeconds: 8,
  values: {
    model: { type: 'model', flavor: 'sklearn.LogisticRegression', paramCount: 24, sizeBytes: 4_200, signature: 'Frame[24] -> float' },
    metrics: { type: 'metric', name: 'auc', value: 0.814, higherIsBetter: true },
  },
  metrics: { auc: 0.814, accuracy: 0.789 },
})

for (const [version, auc, upstream] of [
  [evalGbm, 0.842, gbmV1.versionId],
  [evalRewired, 0.814, logreg.versionId],
] as const) {
  materializations[version.versionId] = makeMaterialization(version, {
    inputVersionIds: [upstream, split.versionId],
    costSeconds: 5,
    values: {
      value: {
        type: 'eval',
        datasetRef: 'holdout@7032',
        sampleCount: 1407,
        scores: { auc, accuracy: auc - 0.03, precision: auc - 0.12, recall: auc - 0.18 },
        traces: [],
      },
    },
    metrics: { auc },
  })
}

materializations[report.versionId] = makeMaterialization(report, {
  inputVersionIds: [evalGbm.versionId, balance.versionId],
  values: {
    value: {
      type: 'note',
      markdown:
        'Gradient boosting reaches **0.842 AUC** on holdout. Tenure is the dominant signal; contract type adds most of the rest. Next: bucket tenure, and check whether interactions help.',
    },
  },
})

// --- branches ---------------------------------------------------------------

const baseSelection = {
  a_raw: rawV2.versionId,
  a_profile: profile.versionId,
  a_missing: missingness.versionId,
  a_balance: balance.versionId,
  a_clean: cleanedV2.versionId,
  a_features: featuresBase.versionId,
  a_split: split.versionId,
  a_gbm: gbmV1.versionId,
  a_eval: evalGbm.versionId,
  a_report: report.versionId,
}

/** Sweep branches forked before the RawChurn fix and still pin the buggy version. */
const stalePins = { a_raw: rawV1.versionId }

const branches: Record<string, Branch> = {
  main: {
    branchId: 'main',
    name: 'main',
    parentBranchId: null,
    forkedAtStep: 0,
    selection: baseSelection,
    pins: {},
    color: '#64748b',
    archived: false,
  },
  'feat-buckets': {
    branchId: 'feat-buckets',
    name: 'feat/tenure-buckets',
    parentBranchId: 'main',
    forkedAtStep: 12,
    selection: { ...baseSelection, a_features: featuresBuckets.versionId },
    pins: { a_raw: rawV2.versionId, a_clean: cleanedV2.versionId },
    color: '#2563eb',
    archived: false,
  },
  'feat-interactions': {
    branchId: 'feat-interactions',
    name: 'feat/interactions',
    parentBranchId: 'main',
    forkedAtStep: 14,
    selection: { ...baseSelection, a_features: featuresInteractions.versionId },
    pins: { a_raw: rawV2.versionId, a_clean: cleanedV2.versionId },
    color: '#7c3aed',
    archived: false,
  },
  'model-logreg': {
    branchId: 'model-logreg',
    name: 'model/logreg',
    parentBranchId: 'main',
    forkedAtStep: 30,
    // Structural divergence: TrainGBM is gone, TrainLogReg is new, eval is rewired.
    selection: (() => {
      const selection: Record<string, string> = {
        ...baseSelection,
        a_logreg: logreg.versionId,
        a_eval: evalRewired.versionId,
      }
      delete selection.a_gbm
      return selection
    })(),
    pins: { a_raw: rawV2.versionId },
    color: '#0d9488',
    archived: false,
  },
}

const sweepConfigs = [
  { id: 'sweep-600-005', version: gbmV2, color: '#d97706' },
  { id: 'sweep-300-01', version: gbmV3, color: '#dc2626' },
  { id: 'sweep-900-003', version: gbmV4, color: '#db2777' },
]

for (const config of sweepConfigs) {
  branches[config.id] = {
    branchId: config.id,
    name: `sweep/${config.version.definition.params.n_estimators}-${config.version.definition.params.learning_rate}`,
    parentBranchId: 'main',
    forkedAtStep: 20,
    selection: { ...baseSelection, a_raw: rawV1.versionId, a_gbm: config.version.versionId },
    pins: stalePins,
    color: config.color,
    archived: false,
    sweepGroup: 'gbm-sweep-1',
  }
}

const assets: Record<string, AssetVersion[]> = {}
for (const version of versions) {
  assets[version.assetId] = assets[version.assetId] ?? []
  assets[version.assetId].push(version)
}
for (const list of Object.values(assets)) {
  list.sort((a, b) => a.createdAtStep - b.createdAtStep)
}

export const churnSession: FlowSession = {
  sessionId: 'session-churn',
  name: 'churn baseline',
  projectName: 'telco-churn',
  scenario: 'churn',
  createdAt: '2026-08-07T09:12:00Z',
  assets,
  materializations,
  branches,
  agents: {
    human: { agentId: 'human', label: 'You', color: '#0f172a', activeBranchId: 'main', activeAssetId: null },
    'agent-1': { agentId: 'agent-1', label: 'claude-1', color: '#2563eb', activeBranchId: 'feat-buckets', activeAssetId: 'a_features' },
    'agent-2': { agentId: 'agent-2', label: 'claude-2', color: '#0d9488', activeBranchId: 'model-logreg', activeAssetId: 'a_logreg' },
    'agent-3': { agentId: 'agent-3', label: 'codex-1', color: '#d97706', activeBranchId: 'sweep-600-005', activeAssetId: 'a_gbm' },
  },
  transactions: [],
  headBranchId: 'main',
}

export const churnVersions = {
  rawV1,
  rawV2,
  cleanedV1,
  cleanedV2,
  featuresBase,
  featuresBuckets,
  featuresInteractions,
  gbmFailed,
  gbmV1,
  gbmV2,
  gbmV3,
  gbmV4,
  logreg,
  evalGbm,
  evalRewired,
}
