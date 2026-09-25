import type { ActorRef, FlowCell } from '../model/types'
import {
  cleanFrame,
  customersDataset,
  errorAnalysisFrame,
  experimentPreview,
  rocPlot,
  summaryNote,
  trainSplitFrame,
} from './previews'

export const claude: ActorRef = { kind: 'agent', label: 'claude-1' }
export const user: ActorRef = { kind: 'user', label: 'you' }

export function cellWith(base: FlowCell, overrides: Partial<FlowCell>): FlowCell {
  return {
    ...structuredClone(base),
    ...overrides,
    provenance: base.provenance
      ? { ...structuredClone(base.provenance), ...(overrides.provenance ?? {}) }
      : overrides.provenance,
  }
}

const loadCustomers: FlowCell = {
  slug: 'load_customers',
  doc: 'Load the raw customer extract from the workspace.',
  consumes: [],
  params: {},
  source: `class LoadCustomers:
    """Load the raw customer extract from the workspace."""
    produces = {"customers": "dataset"}

    def materialize(self, ctx):
        import pandas as pd
        raw = pd.read_csv(ctx.workspace_dir / "data/customers.csv")
        return {"customers": raw}
`,
  outputs: [{ name: 'customers', declared: 'dataset', kind: 'dataset', preview: customersDataset }],
  status: 'materialized',
  provenance: {
    createdBy: user,
    lastEditedBy: user,
    intent: 'set up data loading',
    step: 2,
  },
  timing: { costSeconds: 2.4, cached: true, finishedAgo: '2h ago' },
  logs: 'read 84,312 rows from data/customers.csv (14.0 MB)\n',
  externalInput: true,
}

const cleanData: FlowCell = {
  slug: 'clean_data',
  doc: 'Drop duplicates, coerce dtypes, and normalize contract labels.',
  consumes: ['load_customers.customers'],
  params: { drop_zero_tenure: false },
  source: `class CleanData:
    """Drop duplicates, coerce dtypes, and normalize contract labels."""
    consumes = {"customers": "load_customers.customers"}
    produces = {"clean": "asset"}
    params = {"drop_zero_tenure": False}

    def materialize(self, ctx, customers):
        clean = customers.drop_duplicates("customer_id")
        clean["contract"] = clean["contract"].str.lower().astype("category")
        if self.params["drop_zero_tenure"]:
            clean = clean[clean.tenure_months > 0]
        return {"clean": clean}
`,
  outputs: [{ name: 'clean', declared: 'asset', kind: 'frame', preview: cleanFrame }],
  status: 'materialized',
  provenance: {
    createdBy: claude,
    lastEditedBy: claude,
    intent: 'clean the extract before featurization',
    step: 4,
  },
  timing: { costSeconds: 3.1, cached: true, finishedAgo: '2h ago' },
  logs: 'dropped 405 duplicate rows\n83,907 rows out\n',
}

const features: FlowCell = {
  slug: 'features',
  doc: 'Engineer model features and split train/holdout.',
  consumes: ['clean_data.clean'],
  params: { tenure_buckets: 6, holdout_frac: 0.2, seed: 1337 },
  source: `class Features:
    """Engineer model features and split train/holdout."""
    consumes = {"clean": "clean_data.clean"}
    produces = {"train_split": "asset", "test_split": "asset"}
    params = {"tenure_buckets": 6, "holdout_frac": 0.2, "seed": 1337}

    def materialize(self, ctx, clean):
        ctx.seed()
        feats = engineer(clean, buckets=self.params["tenure_buckets"])
        train, test = split(feats, frac=self.params["holdout_frac"])
        return {"train_split": train, "test_split": test}
`,
  outputs: [
    { name: 'train_split', declared: 'asset', kind: 'frame', preview: trainSplitFrame },
    {
      name: 'test_split',
      declared: 'asset',
      kind: 'frame',
      preview: { ...trainSplitFrame, totalRows: 16782 },
    },
  ],
  status: 'materialized',
  provenance: {
    createdBy: claude,
    lastEditedBy: claude,
    intent: 'add tenure buckets to the feature set',
    step: 21,
  },
  timing: { costSeconds: 18.6, finishedAgo: '4m ago' },
  logs: 'bucketed tenure into 6 bins\ntrain 67,125 rows · holdout 16,782 rows\n',
}

const sweepConfig: FlowCell = {
  slug: 'sweep_config',
  doc: 'Hyperparameter grid shared by the sweep lanes.',
  consumes: [],
  params: {},
  source: `class SweepConfig:
    """Hyperparameter grid shared by the sweep lanes."""
    produces = {"config": "asset"}

    def materialize(self, ctx):
        return {"config": {
            "objective": "binary:logistic",
            "max_depth": 6,
            "n_estimators": 400,
            "early_stopping_rounds": 20,
        }}
`,
  outputs: [
    {
      name: 'config',
      declared: 'asset',
      kind: 'unknown',
      preview: {
        type: 'kv',
        entries: {
          objective: 'binary:logistic',
          max_depth: 6,
          n_estimators: 400,
          early_stopping_rounds: 20,
        },
      },
    },
  ],
  status: 'materialized',
  provenance: {
    createdBy: claude,
    lastEditedBy: user,
    intent: 'bump the tree budget before sweeping',
    step: 15,
  },
  timing: { costSeconds: 0.1, cached: true, finishedAgo: '1h ago' },
}

const trackedTrainingRun = experimentPreview(
  'churn-xgb-lr3e4',
  0.841,
  { lr: '3e-4', epochs: 24, max_depth: 6 },
  'exp-0142',
)

export const trainModel: FlowCell = {
  slug: 'train_model',
  doc: 'Train the churn XGBoost model on engineered features.',
  consumes: ['features.train_split', 'sweep_config.config'],
  params: { lr: 3e-4, epochs: 24, seed: 1337 },
  source: `class TrainXGB:
    """Train the churn XGBoost model on engineered features."""
    consumes = {"train": "features.train_split", "config": "sweep_config.config"}
    produces = {
        "model": "model",
        "run": "experiment",
        "checkpoint": "asset",
        "curves": "asset",
    }
    params = {"lr": 3e-4, "epochs": 24, "seed": 1337}

    def materialize(self, ctx, train, config):
        ctx.seed()
        model, run, ckpt, curves = train_xgb(
            train, config, lr=self.params["lr"], epochs=self.params["epochs"],
            tracker=ctx.tracker,
        )
        return {"model": model, "run": run, "checkpoint": ckpt, "curves": curves}
`,
  outputs: [
    {
      name: 'model',
      declared: 'model',
      kind: 'model',
      preview: {
        type: 'model',
        flavor: 'xgboost',
        sizeBytes: 8_912_896,
        headlineMetric: { name: 'val_auc', value: 0.841, higherIsBetter: true },
        config: { max_depth: 6, n_estimators: 400, lr: 3e-4 },
        experimentRef: 'run',
      },
    },
    {
      name: 'run',
      declared: 'experiment',
      kind: 'experiment',
      preview: trackedTrainingRun,
    },
    {
      name: 'checkpoint',
      declared: 'asset',
      kind: 'checkpoint',
      preview: {
        type: 'file',
        fileName: 'epoch_24.ubj',
        sizeBytes: 8_912_896,
        contentType: 'application/octet-stream',
      },
    },
    {
      name: 'curves',
      declared: 'asset',
      kind: 'plot',
      preview: {
        type: 'plot',
        title: 'Training curves',
        kind: 'line',
        series: [
          { label: 'train_loss', points: experimentPreview('x', 0.841, {}).curves[0].points },
          { label: 'val_auc', points: experimentPreview('x', 0.841, {}).curves[1].points },
        ],
        xLabel: 'epoch',
        yLabel: 'value',
      },
    },
  ],
  primaryOutput: 'run',
  status: 'running',
  stale: { kind: 'parent-rematerialized', cause: 'parent `features` rematerialized' },
  provenance: {
    createdBy: claude,
    lastEditedBy: claude,
    intent: 'retrain on the bucketed features',
    step: 22,
  },
  timing: { costSeconds: 312 },
  console: [
    '[14:32:07] epoch 18/24 · train_loss 0.342 · val_auc 0.837',
    '[14:32:19] epoch 19/24 · train_loss 0.338 · val_auc 0.839',
    '[14:32:31] epoch 20/24 · train_loss 0.335 · val_auc 0.840',
    '[14:32:44] epoch 21/24 · train_loss 0.333 · val_auc 0.841',
  ],
  tracker: trackedTrainingRun.tracker,
}

const holdoutEval: FlowCell = {
  slug: 'holdout_eval',
  doc: 'Score the trained model on the holdout split.',
  consumes: ['train_model.model', 'features.test_split'],
  params: { threshold: 0.5 },
  source: `class HoldoutEval:
    """Score the trained model on the holdout split."""
    consumes = {"model": "train_model.model", "test": "features.test_split"}
    produces = {"eval": "asset", "auc": "asset"}
    params = {"threshold": 0.5}

    def materialize(self, ctx, model, test):
        scores = score(model, test, threshold=self.params["threshold"])
        return {"eval": scores, "auc": scores.summary["auc"]}
`,
  outputs: [
    {
      name: 'eval',
      declared: 'asset',
      kind: 'eval',
      preview: {
        type: 'eval',
        datasetRef: 'features.test_split',
        sampleCount: 16782,
        scores: { auc: 0.841, accuracy: 0.804, precision: 0.71, recall: 0.63 },
      },
    },
    {
      name: 'auc',
      declared: 'asset',
      kind: 'metric',
      preview: { type: 'metric', name: 'auc', value: 0.841, higherIsBetter: true, delta: 0.006 },
    },
  ],
  status: 'stale',
  stale: {
    kind: 'parent-rematerialized',
    cause: 'parent `features` rematerialized',
    transitive: true,
  },
  provenance: {
    createdBy: claude,
    lastEditedBy: claude,
    intent: 'evaluate on holdout',
    step: 12,
  },
  timing: { costSeconds: 9.8, finishedAgo: '1h ago' },
  logs: 'scored 16,782 holdout rows\nauc 0.841 · accuracy 0.804\n',
}

const rocCurve: FlowCell = {
  slug: 'roc_curve',
  doc: 'ROC over the holdout scores.',
  consumes: ['holdout_eval.eval'],
  params: {},
  source: `class RocCurve:
    """ROC over the holdout scores."""
    consumes = {"eval": "holdout_eval.eval"}
    produces = {"roc": "asset"}

    def materialize(self, ctx, eval):
        return {"roc": plot_roc(eval)}
`,
  outputs: [{ name: 'roc', declared: 'asset', kind: 'plot', preview: rocPlot(0.841) }],
  status: 'stale',
  stale: {
    kind: 'parent-rematerialized',
    cause: 'parent `features` rematerialized',
    transitive: true,
  },
  provenance: {
    createdBy: claude,
    lastEditedBy: claude,
    intent: 'plot the holdout ROC',
    step: 13,
  },
  timing: { costSeconds: 1.2, finishedAgo: '1h ago' },
}

const errorAnalysis: FlowCell = {
  slug: 'error_analysis',
  doc: 'Worst mispredictions on the holdout, for manual review.',
  consumes: ['holdout_eval.eval', 'features.test_split'],
  params: { top_k: 412 },
  source: `class ErrorAnalysis:
    """Worst mispredictions on the holdout, for manual review."""
    consumes = {"eval": "holdout_eval.eval", "test": "features.test_split"}
    produces = {"errors": "asset"}
    params = {"top_k": 412}

    def materialize(self, ctx, eval, test):
        return {"errors": worst_errors(eval, test, k=self.params["top_k"])}
`,
  outputs: [{ name: 'errors', declared: 'asset', kind: 'frame', preview: errorAnalysisFrame }],
  status: 'stale',
  stale: {
    kind: 'parent-rematerialized',
    cause: 'parent `features` rematerialized',
    transitive: true,
  },
  provenance: {
    createdBy: user,
    lastEditedBy: user,
    intent: 'inspect the confident mistakes',
    step: 17,
  },
  timing: { costSeconds: 4.5, finishedAgo: '1h ago' },
}

const summary: FlowCell = {
  slug: 'summary',
  doc: 'Branch summary note.',
  consumes: [],
  params: {},
  source: `class Summary:
    """${summaryNote.split('\n')[0]}"""
`,
  outputs: [
    {
      name: 'note',
      declared: 'asset',
      kind: 'note',
      preview: { type: 'note', markdown: summaryNote },
    },
  ],
  status: 'materialized',
  provenance: {
    createdBy: claude,
    lastEditedBy: claude,
    intent: 'summarize the sweep outcome',
    step: 19,
  },
  isNote: true,
}

export const mainCells: FlowCell[] = [
  loadCustomers,
  cleanData,
  features,
  sweepConfig,
  trainModel,
  holdoutEval,
  rocCurve,
  errorAnalysis,
  summary,
]
