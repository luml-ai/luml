/**
 * Single-purpose specimen cells for the design-system gallery: each exhibit
 * shows exactly one state on top of the same base cell, so a gallery visitor
 * can diff states by eye.
 */
import type { FlowCell, Preflight } from '../model/types'
import { cellWith, claude, mainCells, trainModel, user } from './cells'

const base = mainCells.find((cell) => cell.slug === 'roc_curve') as FlowCell

export const materializedCell = cellWith(base, {
  status: 'materialized',
  stale: undefined,
  timing: { costSeconds: 1.2, finishedAgo: '12m ago' },
})

export const cachedCell = cellWith(base, {
  status: 'materialized',
  stale: undefined,
  timing: { costSeconds: 1.2, cached: true, finishedAgo: '2h ago' },
})

export const olderEnvCell = cellWith(base, {
  status: 'materialized',
  stale: undefined,
  timing: { costSeconds: 1.2, olderEnv: true, finishedAgo: '3d ago' },
})

export const runningCell = cellWith(base, {
  status: 'running',
  stale: undefined,
  timing: { costSeconds: 1.2 },
  console: ['[14:33:02] rendering roc over 16,782 holdout scores'],
})

export const staleDefinitionCell = cellWith(base, {
  status: 'stale',
  stale: { kind: 'definition-changed', cause: 'definition changed · v4' },
})

export const staleParentCell = cellWith(base, {
  status: 'stale',
  stale: { kind: 'parent-rematerialized', cause: 'parent `holdout_eval` rematerialized' },
})

export const staleRewiredCell = cellWith(base, {
  status: 'stale',
  stale: { kind: 'deps-rewired', cause: 'inputs rewired · now reads `calibrated_eval.eval`' },
})

export const staleLibCell = cellWith(base, {
  status: 'stale',
  stale: { kind: 'workspace-code-changed', cause: '`helpers.py` changed' },
})

export const staleTransitiveCell = cellWith(base, {
  status: 'stale',
  stale: {
    kind: 'parent-rematerialized',
    cause: 'parent `features` rematerialized',
    transitive: true,
  },
})

export const unmaterializedCell = cellWith(base, {
  status: 'unmaterialized',
  stale: undefined,
  timing: undefined,
  logs: undefined,
})

export const agentFailedCell = cellWith(base, {
  status: 'failed',
  stale: undefined,
  error: {
    author: 'agent',
    summary: "KeyError: 'p_churn'",
    traceback: `Traceback (most recent call last):
  File "cells/roc_curve.py", line 8, in materialize
    return {"roc": plot_roc(eval)}
  File "helpers.py", line 41, in plot_roc
    scores = eval.frame["p_churn"]
KeyError: 'p_churn'`,
    repairedAttempts: 1,
  },
})

export const userFailedCell = cellWith(base, {
  status: 'failed',
  stale: undefined,
  provenance: {
    createdBy: user,
    lastEditedBy: user,
    intent: 'try a calibrated threshold',
    step: 24,
  },
  error: {
    author: 'user',
    summary: 'ValueError: threshold must be within (0, 1), got 5',
    traceback: `Traceback (most recent call last):
  File "cells/roc_curve.py", line 9, in materialize
    return {"roc": plot_roc(eval, threshold=self.params["threshold"])}
  File "helpers.py", line 44, in plot_roc
    raise ValueError(f"threshold must be within (0, 1), got {threshold}")
ValueError: threshold must be within (0, 1), got 5`,
  },
})

/**
 * The state every cell is created in: scaffolded, not yet named. The daemon
 * flags it, and the card renders the flag as the name rather than as a warning.
 */
export const placeholderCell = cellWith(base, {
  slug: 'untitled_1',
  status: 'unmaterialized',
  stale: undefined,
  timing: undefined,
  flag: {
    code: 'placeholder_slug',
    message: '`untitled_1` is a placeholder name. rename it to `roc_curve`.',
  },
})

export const flaggedCell = cellWith(base, {
  consumes: ['holdout_evl.eval'],
  flag: {
    code: 'dangling_ref',
    message: 'unknown reference `holdout_evl.eval`',
    didYouMean: 'holdout_eval.eval',
  },
})

export const conflictCell = cellWith(base, {
  conflict: true,
  provenance: {
    createdBy: claude,
    lastEditedBy: user,
    intent: 'tune the plot styling',
    step: 24,
  },
})

export const pendingProjectionCell = cellWith(base, {
  pendingProjection: true,
  provenance: {
    createdBy: claude,
    lastEditedBy: user,
    intent: 'tune the plot styling',
    step: 24,
  },
})

export const uncertainAttributionCell = cellWith(base, {
  provenance: {
    createdBy: claude,
    lastEditedBy: claude,
    intent: 'add tenure buckets to the feature set',
    step: 21,
    attributionUncertain: true,
  },
})

export const multiOutputCell = trainModel

export const noteCell = mainCells.find((cell) => cell.slug === 'summary') as FlowCell

export const kvFallbackCell = mainCells.find((cell) => cell.slug === 'sweep_config') as FlowCell

export const externalInputCell = mainCells.find(
  (cell) => cell.slug === 'load_customers',
) as FlowCell

/** Run `holdout_eval` while `features` is stale: the closure names three cells. */
export const evalPreflight: Preflight = {
  cached: ['load_customers', 'clean_data', 'sweep_config'],
  recompute: ['features', 'train_model', 'holdout_eval'],
  unknown: [],
  totalSeconds: 341,
}

export const cheapPreflight: Preflight = {
  cached: ['holdout_eval'],
  recompute: ['roc_curve'],
  unknown: [],
  totalSeconds: 1.2,
}
