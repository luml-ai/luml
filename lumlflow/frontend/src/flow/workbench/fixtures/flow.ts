import type {
  BranchInfo,
  EnvState,
  FlowCell,
  FlowSettings,
  JournalEntry,
  WorkbenchFixture,
  WorkbenchSession,
} from '../model/types'
import { cellWith, claude, mainCells, trainModel, user } from './cells'
import { experimentPreview, rocPlot } from './previews'

function sweepCells(lr: string, auc: number, runSuffix: string): FlowCell[] {
  return mainCells.map((cell) => {
    if (cell.slug === 'train_model') {
      const trained = cellWith(trainModel, {
        status: 'materialized',
        stale: undefined,
        console: undefined,
        params: { ...trainModel.params, lr },
        timing: { costSeconds: 298, finishedAgo: '1h ago' },
        logs: `trained 24 epochs · best val_auc ${auc.toFixed(3)}\ncheckpoint epoch_24.ubj staged\n`,
        provenance: {
          createdBy: claude,
          lastEditedBy: claude,
          intent: `sweep lr=${lr}`,
          step: 25,
        },
      })
      trained.source = trained.source.replace('"lr": 3e-4', `"lr": ${lr}`)
      trained.outputs = trained.outputs.map((output) => {
        if (output.name === 'run') {
          return {
            ...output,
            preview: experimentPreview(
              `churn-xgb-${runSuffix}`,
              auc,
              { lr, epochs: 24, max_depth: 6 },
              `exp-01${runSuffix.slice(-2)}`,
            ),
          }
        }
        if (output.name === 'model' && output.preview.type === 'model') {
          return {
            ...output,
            preview: {
              ...output.preview,
              headlineMetric: { name: 'val_auc', value: auc, higherIsBetter: true },
              config: { ...output.preview.config, lr },
            },
          }
        }
        return output
      })
      return trained
    }
    if (cell.slug === 'holdout_eval') {
      const evaluated = cellWith(cell, {
        status: 'materialized',
        stale: undefined,
        timing: { costSeconds: 9.4, finishedAgo: '1h ago' },
      })
      evaluated.outputs = evaluated.outputs.map((output) => {
        if (output.preview.type === 'eval') {
          return {
            ...output,
            preview: {
              ...output.preview,
              scores: { auc, accuracy: auc - 0.04, precision: 0.71, recall: 0.63 },
            },
          }
        }
        if (output.preview.type === 'metric') {
          return { ...output, preview: { ...output.preview, value: auc, delta: auc - 0.841 } }
        }
        return output
      })
      return evaluated
    }
    if (cell.slug === 'roc_curve') {
      const plotted = cellWith(cell, { status: 'materialized', stale: undefined })
      plotted.outputs = [{ ...plotted.outputs[0], preview: rocPlot(auc) }]
      return plotted
    }
    if (cell.stale) return cellWith(cell, { status: 'materialized', stale: undefined })
    return structuredClone(cell)
  })
}

function featureDropCells(): FlowCell[] {
  return mainCells.flatMap((cell) => {
    if (cell.slug === 'summary') return []
    if (cell.slug === 'features') {
      const edited = cellWith(cell, {
        doc: 'Engineer model features without payment_method.',
        params: { tenure_buckets: 6, holdout_frac: 0.2, seed: 1337, drop_payment: true },
        provenance: {
          createdBy: claude,
          lastEditedBy: user,
          intent: 'drop payment_method to test its lift',
          step: 31,
        },
        status: 'materialized',
        timing: { costSeconds: 17.9, finishedAgo: '3d ago' },
      })
      edited.source = edited.source.replace('"seed": 1337}', '"seed": 1337, "drop_payment": True}')
      return [edited]
    }
    if (cell.slug === 'train_model') {
      return [
        cellWith(trainModel, {
          status: 'stale',
          stale: { kind: 'parent-rematerialized', cause: 'parent `features` rematerialized' },
          console: undefined,
          timing: { costSeconds: 305, finishedAgo: '3d ago', olderEnv: true },
          provenance: {
            createdBy: claude,
            lastEditedBy: claude,
            intent: 'retrain without payment_method',
            step: 32,
          },
        }),
      ]
    }
    if (cell.slug === 'holdout_eval') {
      return [
        cellWith(cell, {
          status: 'unmaterialized',
          stale: undefined,
          timing: undefined,
          logs: undefined,
        }),
      ]
    }
    if (cell.stale) return [cellWith(cell, { status: 'materialized', stale: undefined })]
    return [structuredClone(cell)]
  })
}

export const branches: BranchInfo[] = [
  {
    name: 'main',
    parent: null,
    forkedAtStep: null,
    headStep: 23,
    lastIntent: 'retrain on the bucketed features',
    settled: false,
    agent: claude,
    checkedOut: true,
  },
  {
    name: 'exp/lr-3e4',
    parent: 'main',
    forkedAtStep: 14,
    headStep: 26,
    lastIntent: 'sweep lr=3e-4',
    settled: true,
    sweepGroup: 'lr-sweep',
    headlineMetric: { name: 'val_auc', value: 0.841 },
  },
  {
    name: 'exp/lr-1e3',
    parent: 'main',
    forkedAtStep: 14,
    headStep: 27,
    lastIntent: 'sweep lr=1e-3',
    settled: true,
    sweepGroup: 'lr-sweep',
    headlineMetric: { name: 'val_auc', value: 0.856 },
  },
  {
    name: 'exp/lr-3e3',
    parent: 'main',
    forkedAtStep: 14,
    headStep: 28,
    lastIntent: 'sweep lr=3e-3',
    settled: true,
    sweepGroup: 'lr-sweep',
    headlineMetric: { name: 'val_auc', value: 0.848 },
  },
  {
    name: 'exp/feature-drop',
    parent: 'main',
    forkedAtStep: 9,
    headStep: 33,
    lastIntent: 'drop payment_method to test its lift',
    settled: false,
    headlineMetric: { name: 'val_auc', value: 0.837 },
  },
  {
    name: 'old/baseline',
    parent: 'main',
    forkedAtStep: 5,
    headStep: 8,
    lastIntent: 'freeze the logistic baseline',
    settled: true,
    archived: true,
    headlineMetric: { name: 'val_auc', value: 0.802 },
  },
]

export const cellsByBranch: Record<string, FlowCell[]> = {
  main: mainCells,
  'exp/lr-3e4': sweepCells('3e-4', 0.841, 'lr3e4'),
  'exp/lr-1e3': sweepCells('1e-3', 0.856, 'lr1e3'),
  'exp/lr-3e3': sweepCells('3e-3', 0.848, 'lr3e3'),
  'exp/feature-drop': featureDropCells(),
  'old/baseline': mainCells
    .filter((cell) => ['load_customers', 'clean_data', 'features'].includes(cell.slug))
    .map((cell) => cellWith(cell, { status: 'materialized', stale: undefined })),
}

export const journal: JournalEntry[] = [
  {
    step: 23,
    time: '14:31',
    branch: 'main',
    actor: claude,
    intent: 'retrain on the bucketed features',
    kind: 'run',
    summary: 'running `train_model` · epoch 21/24',
  },
  {
    step: 22,
    time: '14:28',
    branch: 'main',
    actor: claude,
    intent: 'retrain on the bucketed features',
    kind: 'edit',
    summary: 'edited `train_model` · v6→v7',
  },
  {
    step: 21,
    time: '14:27',
    branch: 'main',
    actor: claude,
    intent: 'add tenure buckets to the feature set',
    kind: 'run',
    summary: 'ran `features` · 4 cells marked stale',
    failedAttempts: 1,
  },
  {
    step: 20,
    time: '14:24',
    branch: 'main',
    actor: claude,
    intent: 'add tenure buckets to the feature set',
    kind: 'edit',
    summary: 'edited `features` · v11→v12',
  },
  {
    step: 19,
    time: '13:55',
    branch: 'main',
    actor: claude,
    intent: 'summarize the sweep outcome',
    kind: 'edit',
    summary: 'wrote note `summary`',
    settled: true,
  },
  {
    step: 18,
    time: '13:52',
    branch: 'main',
    actor: claude,
    intent: 'publish the sweep winner',
    kind: 'promote',
    summary: 'promoted `train_model.model` → collection churn-models',
  },
  {
    step: 17,
    time: '13:40',
    branch: 'main',
    actor: user,
    intent: 'inspect the confident mistakes',
    kind: 'edit',
    summary: 'created `error_analysis`',
  },
  {
    step: 16,
    time: '13:22',
    branch: 'main',
    actor: user,
    intent: 'edits while lumlflow was stopped',
    kind: 'offline',
    summary: 'offline window · the fine-grained edit sequence was not recorded',
  },
  {
    step: 15,
    time: '12:58',
    branch: 'main',
    actor: user,
    intent: 'bump the tree budget before sweeping',
    kind: 'edit',
    summary: 'edited `sweep_config` · v2→v3',
  },
  {
    step: 14,
    time: '12:41',
    branch: 'exp/lr-1e3',
    actor: claude,
    intent: 'sweep the learning rate',
    kind: 'fork',
    summary: 'started exp/lr-3e4, exp/lr-1e3, exp/lr-3e3 from main',
  },
  {
    step: 12,
    time: '12:12',
    branch: 'main',
    actor: claude,
    intent: 'evaluate on holdout',
    kind: 'run',
    summary: 'ran `holdout_eval`, `roc_curve` · settled',
    settled: true,
  },
  {
    step: 10,
    time: '11:58',
    branch: 'main',
    actor: claude,
    intent: 'first full training pass',
    kind: 'run',
    summary: 'ran `train_model` · val_auc 0.833',
    failedAttempts: 2,
  },
  {
    step: 9,
    time: '11:31',
    branch: 'main',
    actor: claude,
    intent: 'wire the training cell',
    kind: 'rename',
    summary: 'renamed `train` → `train_model` · 3 references rewired',
  },
  {
    step: 8,
    time: '11:02',
    branch: 'main',
    actor: claude,
    intent: 'session start',
    kind: 'agent-begin',
    summary: 'claude-1 registered on main',
  },
]

export const session: WorkbenchSession = {
  flowName: 'churn.flow',
  workspacePath: '~/work/churn-analysis',
  state: 'running',
  paired: {
    label: 'claude-1',
    branch: 'main',
    state: 'working',
    task: 'retrain on the bucketed features',
  },
  worktreeBranch: 'main',
  worktreeLocked: true,
  diskUsage: '1.8 GB',
}

export const env: EnvState = {
  pythonVersion: '3.12.4',
  packages: [
    { name: 'pandas', version: '2.2.3' },
    { name: 'xgboost', version: '2.1.1' },
    { name: 'scikit-learn', version: '1.5.2' },
    { name: 'matplotlib', version: '3.9.2' },
    { name: 'shap', version: '0.46.0', pendingRestart: true },
  ],
}

export const settings: FlowSettings = {
  reactivity: 'auto',
  autoThresholdSeconds: 10,
  onEnvChange: 'ask',
}

export const churnFixture: WorkbenchFixture = {
  session,
  settings,
  env,
  branches,
  cellsByBranch,
  journal,
}
