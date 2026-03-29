# LUML Agent Guide

This file documents the tools, output contracts, and conventions available in the `.luml-agent/` directory. Refer to this guide for CLI usage, expected file formats, and experiment tracking conventions.

---

## `luml-inspect` CLI Reference

`luml-inspect` is a read-only CLI for exploring experiment data. It is available on the system PATH.

All commands accept `--db <path>` to override the experiment database location (default: `~/.luml-agent/experiments`).

### `luml-inspect list`

List experiments. Default cap: 20 rows.

```
$ luml-inspect list
ID         NAME           STATUS     CREATED     TAGS         METRICS(final)
abc-123    baseline-lr    completed  2026-03-28  [gbt,v1]     accuracy=0.92 loss=0.08
def-456    high-lr        completed  2026-03-28  [gbt,v1]     accuracy=0.88 loss=0.12
(2 of 2 experiments)
```

Flags:
- `--all` — show all experiments (no cap)
- `--limit N` — show at most N rows
- `--group <name>` — filter by group
- `--tag <tag>` — filter by tag

### `luml-inspect show <experiment_id>`

Full experiment details: metadata, static params, and per-metric summary.

```
$ luml-inspect show abc-123
EXPERIMENT abc-123 "baseline-lr" (completed)
Created: 2026-03-28  Group: default  Tags: gbt, v1

PARAMS
  learning_rate    0.01
  batch_size       32
  model_type       gradient_boosting

METRICS SUMMARY
  KEY        STEPS  FINAL   MIN     MAX     MEAN
  accuracy   500    0.92    0.41    0.92    0.78
  loss       500    0.08    0.08    1.24    0.31
```

### `luml-inspect metrics <experiment_id> <key>`

Time-series for one metric. Default: subsample to ~20 buckets. Each row shows the sampled value plus the min/max within that bucket.

```
$ luml-inspect metrics abc-123 accuracy
accuracy (500 steps, showing 20 buckets)
  STEP     VALUE   MIN     MAX
  1        0.41    0.41    0.53
  25       0.58    0.52    0.61
  50       0.64    0.60    0.67
  ...
  500      0.92    0.91    0.92
```

Flags:
- `--all` — show every step (no subsampling)
- `--last N` — last N data points (raw, no bucketing)
- `--every N` — every Nth step (raw, no bucketing)
- `--summary` — only the summary line (final/min/max/mean)
- `--buckets N` — override default bucket count (default: 20)

### `luml-inspect params <experiment_id>`

Static params dump (compact).

```
$ luml-inspect params abc-123
learning_rate    0.01
batch_size       32
model_type       gradient_boosting
```

### `luml-inspect compare <id1> <id2> [...]`

Side-by-side metric and parameter comparison across two or more experiments.

```
$ luml-inspect compare abc-123 def-456
PARAMS DIFF
  KEY              abc-123    def-456
  learning_rate    0.01       0.1
  batch_size       32         32       (same)

METRIC: accuracy (500 steps, 20 buckets)
  STEP    abc-123         def-456
          VAL  MIN  MAX   VAL  MIN  MAX
  1       0.41 0.41 0.53  0.39 0.39 0.51
  25      0.58 0.52 0.61  0.55 0.50 0.58
  ...
  500     0.92 0.91 0.92  0.88 0.87 0.88

METRIC: loss (500 steps, 20 buckets)
  STEP    abc-123         def-456
          VAL  MIN  MAX   VAL  MIN  MAX
  1       1.24 1.10 1.24  1.30 1.15 1.30
  ...
  500     0.08 0.08 0.09  0.12 0.11 0.13
```

Flags (same as `metrics`):
- `--all` — show every step
- `--last N` — last N data points
- `--every N` — every Nth step
- `--summary` — only final values per metric
- `--buckets N` — override bucket count

### `luml-inspect evals <experiment_id>`

Eval samples. Default cap: 10 rows.

```
$ luml-inspect evals abc-123
DATASET    EVAL_ID    SCORES                    INPUTS(trunc)
ds-01      eval-001   f1=0.91 em=0.85           {"query": "what is..."}
ds-01      eval-002   f1=0.78 em=0.70           {"query": "how does..."}
(2 of 2 samples)
```

Flags:
- `--all` — show all samples
- `--limit N` — show at most N rows
- `--dataset <id>` — filter by dataset

---

## `.luml-agent/result.json` Schema

The training code writes this file after execution. The run node reads it to extract results.

```json
{
  "success": true,
  "experiment_id": "abc-123",
  "experiment_ids": ["abc-123", "def-456"],
  "metrics": {
    "accuracy": 0.92,
    "f1_score": 0.88
  },
  "artifacts": {
    "model_path": "model.luml"
  },
  "error_message": ""
}
```

### Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `success` | `bool` | Yes | Whether the run succeeded |
| `experiment_id` | `string` | No | Single experiment ID (use for single-experiment runs) |
| `experiment_ids` | `string[]` | No | Multiple experiment IDs (use for grid search / multi-experiment runs) |
| `metrics` | `dict[string, float]` | No | Named metrics (e.g. `{"accuracy": 0.92}`) |
| `artifacts.model_path` | `string` | No | Path to the trained model file (relative to worktree) |
| `error_message` | `string` | No | Error description if `success` is `false` |

### Notes

- Use `experiment_id` (singular) for single-experiment runs and `experiment_ids` (list) for multi-experiment runs. Both are normalized to a list internally.
- For backward compatibility, a top-level `"metric": 0.5` (float) is accepted and treated as `{"metric": 0.5}`.
- The `model_path` can also be specified at the top level: `"model_path": "model.luml"`.

---

## `.luml-agent/fork.json` Schema

The fork agent writes this file with proposals for child branches.

```json
[
  {
    "prompt": "Increase learning rate to 0.1 and add learning rate warmup for 10% of steps",
    "title": "higher-lr-with-warmup"
  },
  {
    "prompt": "Switch from SGD to AdamW optimizer with weight decay 0.01",
    "title": "adamw-optimizer"
  }
]
```

### Fields

Each element in the array:

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | `string` | Yes | Instructions for the child implement agent |
| `title` | `string` | Yes | Short label for the branch/proposal |

---

## ExperimentTracker Convention

All experiments are stored in a shared global database at:

```
~/.luml-agent/experiments/
```

### Connection String

```
sqlite://~/.luml-agent/experiments
```

### Usage in Training Code

```python
from luml import ExperimentTracker

tracker = ExperimentTracker("sqlite://~/.luml-agent/experiments")
exp = tracker.create_experiment(name="my-experiment")
exp.log_params({"learning_rate": 0.01, "batch_size": 32})

for step in range(num_steps):
    # ... training ...
    exp.log_metrics({"loss": loss_val, "accuracy": acc_val}, step=step)

exp.set_status("completed")
```

### Database Structure

```
~/.luml-agent/experiments/
├── meta.db              # experiment index (shared across all experiments)
└── {experiment_id}/     # per-experiment data
    └── exp.db           # static params, dynamic metrics, evals
```

The `luml-inspect` CLI reads from this location by default. No `--db` flag is needed when using the default path.

---

## Metric Consistency Rules

When iterating on an experiment (e.g., after a fork), follow these rules to ensure metrics are comparable across runs:

1. **Use the same metric names.** If the parent experiment logged `accuracy` and `loss`, the child must use `accuracy` and `loss` — not `acc` or `val_loss`.
2. **Use the same calculation method.** If the parent computed accuracy as `correct / total` on the validation set, the child must do the same. Do not switch between micro/macro averaging, change the eval dataset, or alter the calculation without renaming the metric.
3. **Log metrics at comparable intervals.** If the parent logged every epoch, the child should log every epoch (not every batch). This ensures `luml-inspect compare` produces meaningful side-by-side output.
4. **Preserve the primary metric.** The metric used for comparing runs (configured in the run settings) must always be present in the result.
