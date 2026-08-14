/**
 * Fixture for the compare surface (ui-draft.md §7): 2–5 branches selected from
 * the branch graph, aligned on asset.
 *
 * The two divergence kinds are the load-bearing distinction: definition
 * divergence (someone edited the cell — rare, structural, rendered as the
 * branching point) vs materialization divergence (same code, different inputs —
 * transitively closed, rendered collapsed to one row per asset).
 */
import type { BranchName, CompareView } from '../model/types'

import { trainingCurves } from './previews'

const SWEEP: BranchName[] = ['main', 'exp/lr-3e4', 'exp/lr-1e3', 'exp/lr-3e3']

export const sweepCompare: CompareView = {
  sharedMetric: 'val_auc',
  branches: [
    {
      branch: 'main',
      headlineMetric: { name: 'val_auc', value: 0.841, higherIsBetter: true },
      scores: { auc: 0.841, accuracy: 0.804, precision: 0.71, recall: 0.63 },
      curve: { name: 'val_auc', points: trainingCurves(0.841)[1].points },
      settled: false,
    },
    {
      branch: 'exp/lr-3e4',
      headlineMetric: { name: 'val_auc', value: 0.841, higherIsBetter: true },
      scores: { auc: 0.841, accuracy: 0.801, precision: 0.7, recall: 0.63 },
      curve: { name: 'val_auc', points: trainingCurves(0.841)[1].points },
      settled: true,
    },
    {
      branch: 'exp/lr-1e3',
      headlineMetric: { name: 'val_auc', value: 0.856, higherIsBetter: true },
      scores: { auc: 0.856, accuracy: 0.816, precision: 0.73, recall: 0.66 },
      curve: { name: 'val_auc', points: trainingCurves(0.856)[1].points },
      settled: true,
    },
    {
      branch: 'exp/lr-3e3',
      headlineMetric: { name: 'val_auc', value: 0.848, higherIsBetter: true },
      scores: { auc: 0.848, accuracy: 0.808, precision: 0.72, recall: 0.64 },
      curve: { name: 'val_auc', points: trainingCurves(0.848)[1].points },
      settled: true,
    },
  ],
  definitionDivergences: [
    {
      slug: 'train_model',
      sides: [
        {
          branches: ['main', 'exp/lr-3e4'],
          params: { lr: '3e-4', epochs: 24, seed: 1337 },
          sourceExcerpt: 'params = {"lr": 3e-4, "epochs": 24, "seed": 1337}',
          version: 'v7',
        },
        {
          branches: ['exp/lr-1e3'],
          params: { lr: '1e-3', epochs: 24, seed: 1337 },
          sourceExcerpt: 'params = {"lr": 1e-3, "epochs": 24, "seed": 1337}',
          version: 'v7·lr-1e3',
        },
        {
          branches: ['exp/lr-3e3'],
          params: { lr: '3e-3', epochs: 24, seed: 1337 },
          sourceExcerpt: 'params = {"lr": 3e-3, "epochs": 24, "seed": 1337}',
          version: 'v7·lr-3e3',
        },
      ],
    },
  ],
  materializationRows: [
    {
      slug: 'holdout_eval',
      output: 'auc',
      kind: 'metric',
      byBranch: {
        main: { label: '0.841', state: 'same' },
        'exp/lr-3e4': { label: '0.841', state: 'same' },
        'exp/lr-1e3': { label: '0.856', state: 'better' },
        'exp/lr-3e3': { label: '0.848', state: 'better' },
      },
    },
    {
      slug: 'roc_curve',
      output: 'roc',
      kind: 'chip',
      byBranch: {
        main: { label: 'stale', state: 'missing' },
        'exp/lr-3e4': { label: 'materialized', state: 'same' },
        'exp/lr-1e3': { label: 'materialized', state: 'better' },
        'exp/lr-3e3': { label: 'materialized', state: 'same' },
      },
    },
    {
      slug: 'error_analysis',
      output: 'errors',
      kind: 'chip',
      byBranch: {
        main: { label: '412 rows', state: 'same' },
        'exp/lr-3e4': { label: '409 rows', state: 'same' },
        'exp/lr-1e3': { label: '371 rows', state: 'better' },
        'exp/lr-3e3': { label: '388 rows', state: 'same' },
      },
    },
  ],
  shapelessDifferences: [
    {
      slug: 'summary',
      what: 'note exists only on main',
      branches: ['main'],
    },
    {
      slug: 'sweep_config',
      what: 'param-only edit v2→v3 not yet picked up by the sweep lanes (pinned when they started)',
      branches: ['exp/lr-3e4', 'exp/lr-1e3', 'exp/lr-3e3'],
    },
  ],
  warnings: [
    {
      kind: 'divergent-pin',
      message: 'sweep lanes pin `sweep_config` at v2. main is at v3.',
      affectedBranches: ['exp/lr-3e4', 'exp/lr-1e3', 'exp/lr-3e3'],
    },
  ],
  artifacts: [
    {
      slug: 'train_model',
      output: 'run',
      kind: 'experiment',
      label: 'churn-xgb experiment',
      href: '/experiments',
      byBranch: {
        main: 'exp-0142',
        'exp/lr-3e4': 'exp-0143',
        'exp/lr-1e3': 'exp-0144',
        'exp/lr-3e3': 'exp-0145',
      },
    },
    {
      slug: 'train_model',
      output: 'model',
      kind: 'model',
      label: 'churn model',
      href: '/experiments',
      byBranch: {
        main: 'churn-xgb v6',
        'exp/lr-3e4': 'churn-xgb v7',
        'exp/lr-1e3': 'churn-xgb v8',
        'exp/lr-3e3': 'churn-xgb v9',
      },
    },
    {
      slug: 'holdout_eval',
      output: 'auc',
      kind: 'metric',
      label: 'holdout auc',
      href: '',
      byBranch: {
        main: '0.841',
        'exp/lr-3e4': '0.841',
        'exp/lr-1e3': '0.856',
        'exp/lr-3e3': '0.848',
      },
    },
  ],
}

export const sweepCompareBranches = SWEEP
