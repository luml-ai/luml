---
sidebar_label: Satellite Monitoring Processing Spec
title: Satellite Monitoring Processing & Metrics Worker Spec
---

# Proposals

## Problem

Part 1 makes the Satellite collect raw inference data (inputs, outputs, status,
latency) into local storage. But nothing turns that raw data into monitoring
metrics, and there is nothing to compare it against. Collected data just sits there:
no data-quality checks, no drift, no health rollups. To detect that a model is
degrading we need two things that do not exist yet:

- a **reference baseline** describing what the model's inputs and outputs looked like
  on the training data;
- a **processing layer** that periodically reads the collected data, compares it to
  the baseline, and produces monitoring metrics and alerts.

This spec is the **second slice** of the Live Monitoring architecture: the reference
profile and the Monitoring Worker that computes metrics from it.

## Solution at a glance

Three pieces:

- The **reference profile** is produced by the SDK from the model's training dataset
  at packaging and shipped in the model artifact. Its generation is specified
  separately in `spec_sdk_reference_profile.md`; this spec treats the profile as an
  input.
- **Satellite** loads the reference profile from the artifact when it deploys the
  model, and keeps it available for that deployment.
- **Monitoring Worker** — one shared per-Satellite background worker — periodically
  reads the collected inference data for each monitored deployment, compares it to
  the reference profile, and computes:
  - runtime health,
  - data quality,
  - univariate feature drift (PSI),
  - output drift (PSI on predictions),
  - multivariate drift (PCA reconstruction error).

  It writes the results and alert state into local storage, in a shape a later
  dashboard can read.

Out of scope: realized performance and delayed targets (deferred with the targets
work); the dashboard, Query API, and UI (a later slice).

## Why this approach

- The **training dataset is the natural baseline** — it defines what "normal" inputs
  and outputs are. The SDK produces the profile from it (separate spec), so the worker
  only reads and compares.
- A **shared, off-path worker** keeps expensive calculations away from inference, so
  it can never slow down or break serving (consistent with part 1's best-effort rule).
- It **reuses part 1's collected data** as its only source, so no new collection is
  needed.
- **PCA reconstruction error** is the established method for multivariate drift: it
  catches joint/correlation shifts that per-feature drift misses, with a single
  interpretable metric and a simple threshold.

# Design

## Scope

In scope:

- Satellite loading of the reference profile at deploy time
- a per-Satellite Monitoring Worker that computes, per monitored deployment and time
  window: runtime health, data quality, feature drift, output drift, multivariate
  drift
- materialized results and alert state, in a read-ready shape

Out of scope: generation of the reference profile in the SDK; realized performance and delayed targets; Query API,
dashboard, and UI; alert delivery to external channels; task types beyond the
classical-ML tabular case (regression and classification are covered; the
profile/worker are structured so more can be added later).

## Building on part 1

Part 1 is implemented and this slice builds directly on it:

- **Collected data lives in GreptimeDB** (database `public`), queried over its
  SQL/HTTP interface. Inference events are stored in a **trace table
  `inference_events`**, one row per request, carrying `event_id`, `deployment_id`,
  `status`, `status_code`, `latency_ms`, `trace_id` / `span_id`, and the model
  **`inputs` and `output` as JSON strings** (the worker parses them). Runtime signals
  also exist as OpenTelemetry **metric tables** (`inference.requests`,
  `inference.errors`, `inference.latency_ms`). There is **no separate `runtime_metrics`
  table** — runtime health is derived from `inference_events` (and, where useful, the
  metric tables). Real spans live in `otel_traces`.
- The per-deployment **`monitoring_enabled` flag**, the **monitoring capability**
  advertised to the Platform, and the Agent / model-server **telemetry setup** already
  exist — this slice reuses them and does not re-add them.
- The **deploy flow** downloads the model artifact and reads its contract (manifest /
  schema); the reference profile is loaded on the same path.

This slice adds two new stored datasets in GreptimeDB:

| Dataset | Purpose |
| --- | --- |
| `monitoring_results` | materialized metric values per deployment, metric group, and window |
| `monitoring_alerts` | alert state and lifecycle per deployment and metric |

## Reference profile (the contract)

The reference profile is the input the worker reads for each deployment. It is
**produced by the SDK** from the model's training data and shipped in the artifact —
its generation will implemented later. The worker only reads
it. This section documents the shape the worker relies on.

The profile carries a `task_type` (`regression` | `classification`) and a
`profile_status` (`ready` | `placeholder`), plus three parts.

### Per-feature summaries

For each **numerical** input feature:

| Field | Type | Meaning |
| --- | --- | --- |
| `position` | int | column position in input order |
| `mean`, `std`, `min`, `max` | number | basic statistics |
| `quantiles` | q05, q25, q50, q75, q95 | percentile values |
| `bin_edges` | list of number | reference histogram bin boundaries |
| `bin_centres` | list of number | bin centers |
| `frequencies` | list of int | reference counts per bin |
| `probabilities` | list of number | reference proportion per bin (used for PSI) |
| `count` | int | reference sample count |
| `missing` | int | missing count in reference |

For each **categorical** input feature:

| Field | Type | Meaning |
| --- | --- | --- |
| `position` | int | column position in input order |
| `categories` | list of string | known categories |
| `frequencies` | list of int | reference counts per category |
| `probabilities` | map category → number | reference proportion per category (PSI) |
| `count` | int | reference sample count |
| `missing` | int | missing count in reference |
| `n_unique` | int | number of distinct categories |

### Output summary

The output summary has the **same shape as a feature summary**, computed by running
the model on the training data (`predict` on the reference set) and summarizing the
predictions:

- **regression** output → a numerical summary (bins, probabilities, quantiles,
  min/max) of the predicted values;
- **classification** output → a categorical summary of predicted class proportions,
  and, when probabilities/scores are produced, a numerical summary of the score.

This is the baseline for output drift.

### PCA profile (multivariate)

Computed by the SDK from the numerical features of the training data:

| Part | Contents |
| --- | --- |
| `scaler` | standardization parameters (`mean_`, `scale_`, `var_`, feature count) for the numerical features |
| `pca` | number of components, component matrix, centering mean, and the ordered `feature_names` the PCA was fit on |
| `reconstruction_error_reference` | reference **mean** and **std** of the PCA reconstruction error, computed over chunks of the training data (used for the drift threshold) |

The PCA covers **numerical features only**. Categorical features participate in
univariate drift and data quality but not in the multivariate metric.

The profile status is marked so a placeholder (missing or not yet regenerated)
profile can be surfaced rather than trusted.

### Example

A concrete example the worker parses (regression model, two numerical and two
categorical features). The full contract and generation live in
`spec_sdk_reference_profile.md`; this example is kept here for implementation
accuracy.

```json
{
  "task_type": "regression",
  "profile_status": "ready",
  "feature_summaries": {
    "numerical_features": {
      "age": {
        "position": 1,
        "mean": 35.2, "std": 12.5, "min": 18, "max": 75,
        "quantiles": {"q05": 20, "q25": 25, "q50": 34, "q75": 45, "q95": 65},
        "bin_edges": [18, 25, 35, 45, 55, 65, 75],
        "bin_centres": [21.5, 30, 40, 50, 60, 70],
        "frequencies": [5, 15, 40, 25, 10, 5],
        "probabilities": [0.05, 0.15, 0.40, 0.25, 0.10, 0.05],
        "count": 100, "missing": 0
      }
    },
    "categorical_features": {
      "region": {
        "position": 3,
        "categories": ["north", "south", "east", "west"],
        "frequencies": [25, 25, 25, 25],
        "probabilities": {"north": 0.25, "south": 0.25, "east": 0.25, "west": 0.25},
        "count": 100, "missing": 0, "n_unique": 4
      }
    }
  },
  "output_summary": {
    "type": "numerical",
    "summary": {
      "mean": 51230.0, "std": 14800.0, "min": 21000, "max": 118000,
      "quantiles": {"q05": 26000, "q25": 40500, "q50": 50500, "q75": 64000, "q95": 99000},
      "bin_edges": [21000, 40000, 60000, 80000, 100000, 118000],
      "bin_centres": [30500, 50000, 70000, 90000, 109000],
      "frequencies": [12, 33, 34, 14, 7],
      "probabilities": [0.12, 0.33, 0.34, 0.14, 0.07],
      "count": 100, "missing": 0
    }
  },
  "pca_profile": {
    "scaler": {"mean_": [35.2, 52000], "scale_": [12.5, 15000], "var_": [156.25, 225000000], "n_features": 2},
    "pca": {
      "n_components": 2, "n_features": 2,
      "components": [[0.8, 0.6], [-0.6, 0.8]],
      "mean_": [0.0, 0.0],
      "feature_names": ["age", "income"]
    },
    "reconstruction_error_reference": {"mean": 0.42, "std": 0.08, "n_chunks": 10}
  }
}
```

For a classification model, `task_type` is `classification` and `output_summary` is
categorical (predicted-class proportions).

## The Monitoring Worker

One shared Monitoring Worker runs per Satellite as a background loop (alongside the
existing periodic controller), processing all deployments that are monitored. It is
strictly off the inference path.

- **Scheduling:** the worker wakes on an interval and, for each monitored deployment,
  processes the most recent completed time window of collected data. Window size and
  interval are configurable with sensible defaults.
- **Scope:** every unit of work is deployment-scoped (deployment id, metric group,
  window).
- **Source:** it reads only from GreptimeDB — primarily the `inference_events` trace
  table (parsing the JSON-string `inputs` / `output`) plus the runtime metric tables —
  and writes only `monitoring_results` and `monitoring_alerts`.
- **Best-effort:** the worker never blocks or affects inference. If the reference
  profile is missing, profile-dependent calculations (data-quality ranges, drift,
  multivariate) are skipped while runtime health still runs. If storage is
  unavailable, the tick is skipped and retried next interval.

## Calculations

Each calculation reads a window of collected data (and, where noted, the reference
profile), produces metric values written to `monitoring_results`, and raises or
clears alerts in `monitoring_alerts`.

### Runtime health

- **Inputs:** `inference_events` (per-request status and latency) and the runtime
  metric tables (no profile needed).
- **Metrics:** request count, success count, error count, error rate, latency p50 /
  p95 / max, failed-inference count.
- **Alerts:** error rate > 1% warning, > 5% critical; latency p95 over a
  deployment threshold.

### Data quality

- **Inputs:** live inputs from `inference_events`, plus the model schema and
  per-feature summaries from the profile.
- **Metrics per feature:** missing rate, type-mismatch rate, numeric range-violation
  rate (values outside the reference `min`/`max`), unseen-category rate (categories
  not in the reference `categories`).
- **Alerts:** missing rate > 1% / 5%; type-mismatch > 0% / 1%; range-violation
  > 1% / 5%; unseen-category > 0% / 1% (warning / critical).

### Feature drift (univariate, PSI)

- **Inputs:** live inputs; per-feature reference distributions.
- **Method — PSI** per feature per window:
  - numerical: bin the live values using the reference `bin_edges`, compute live
    per-bin proportions, and compute PSI against the reference `probabilities`;
  - categorical: compute live category proportions and compute PSI against the
    reference `probabilities`; unseen categories contribute to the score.
  - PSI = Σ (live_prop − ref_prop) · ln(live_prop / ref_prop), with a small epsilon
    to avoid division by zero.
- **Severity:** PSI < 0.1 normal, 0.1–0.25 warning, > 0.25 critical.

### Output drift (PSI on predictions)

- **Inputs:** live outputs from `inference_events`; the `output_summary`.
- **Method:** the same PSI, applied to predictions:
  - regression: PSI on the prediction histogram, plus mean / median / p05 / p95
    trend of the live predictions;
  - classification: PSI on predicted-class proportions and, when available, PSI on
    the score histogram.
- **Severity:** same PSI thresholds as feature drift.

### Multivariate drift (PCA reconstruction error)

- **Inputs:** live numerical inputs; the PCA profile.
- **Method:** for the live window, standardize the numerical features with the stored
  scaler, project them onto the stored PCA components and reconstruct them back to the
  original space, then compute the reconstruction error as the Euclidean distance
  between the original standardized rows and their reconstructions. Aggregate to the
  window mean reconstruction error.
- **Alert:** when the live mean reconstruction error exceeds the reference
  `reconstruction_error_reference.mean` by more than 3× its `std`. A rising
  reconstruction error means the live data no longer matches the correlation
  structure the PCA learned on training data.

### Realized performance (out of scope)

Realized performance (MAE / RMSE / R² and classification quality) requires delayed
targets, which are deferred. The worker leaves a clear place for it but does not
compute it in this slice.

## Results contract ("how it shows")

The worker does not render anything; it materializes results in a read-ready shape a
later dashboard/Query API can consume.

A `monitoring_results` entry represents one metric group for one deployment and one
window:

| Field | Meaning |
| --- | --- |
| `deployment_id` | which deployment |
| `metric_group` | runtime, data_quality, feature_drift, output_drift, multivariate |
| `window_start` / `window_end` | the time window covered |
| `values` | the computed metrics for the group (per-feature where applicable) |
| `severity` | worst severity in the group for the window (normal / warning / critical) |
| `profile_status` | whether a real or placeholder profile was used |

A `monitoring_alerts` entry tracks one alerting condition over time:

| Field | Meaning |
| --- | --- |
| `deployment_id` | which deployment |
| `metric` | which metric/feature triggered |
| `current_value` / `threshold` | the value and the breached threshold |
| `severity` | warning or critical |
| `state` | open, acknowledged, or resolved |
| `first_seen` / `last_seen` | lifecycle timestamps |

On each window the worker updates alert state: it opens a new alert when a threshold
is first breached, updates `last_seen` and `current_value` while it persists, and
resolves it when the metric returns to normal.

# Scenarios

## Scenario: Satellite loads the profile at deploy
**Given** a model artifact that contains a reference profile
**When** the Satellite deploys the model
**Then** the profile is loaded and available to the worker for that deployment.

## Scenario: worker computes runtime health without a profile
**Given** a monitored deployment with collected data but no reference profile
**When** the worker runs a window
**Then** runtime health metrics are materialized and profile-dependent calculations
are skipped, without error.

## Scenario: feature drift is detected
**Given** a monitored deployment whose live inputs for a feature have shifted well
away from the reference distribution
**When** the worker computes feature drift for the window
**Then** the feature's PSI exceeds 0.25, a critical drift result is materialized, and
a critical alert is opened for that feature.

## Scenario: data quality catches invalid inputs
**Given** live inputs that include an unseen category and out-of-range numeric values
**When** the worker computes data quality
**Then** the unseen-category and range-violation rates are materialized and the
corresponding alerts are opened.

## Scenario: output drift on predictions
**Given** a monitored regression deployment whose predictions have shifted from the
output baseline
**When** the worker computes output drift
**Then** the prediction PSI and the mean/median/p05/p95 trend are materialized and
severity reflects the PSI thresholds.

## Scenario: multivariate drift via reconstruction error
**Given** live numerical inputs whose joint structure differs from training even when
each feature alone looks normal
**When** the worker computes multivariate drift
**Then** the window mean reconstruction error exceeds the reference mean by more than
3 standard deviations and a multivariate alert is opened.

## Scenario: alert lifecycle
**Given** an open alert for a metric that has returned to normal
**When** the worker processes a later window where the metric is normal
**Then** the alert is resolved rather than left open.

## Scenario: worker never affects inference
**Given** the worker is running (or failing)
**When** inference requests are served for any deployment
**Then** serving is unaffected; a worker or storage failure only skips that window and
is retried next interval.

## Scenario: disabled deployment is not processed
**Given** a deployment with monitoring disabled
**When** the worker ticks
**Then** no results or alerts are produced for it.

# Tasks

The reference profile these tasks consume is produced by the SDK per
`spec_sdk_reference_profile.md`; that work is not part of these tasks.

- [ ] **Task 1 — Satellite: load the reference profile at deploy**
  - [ ] Read the reference profile from the artifact on the deploy path and store it
        on the deployment record alongside the existing schema/manifest.
  - [ ] Treat a missing or placeholder profile as "no profile" rather than an error.
  - [ ] Tests: profile loaded and available for a deployment that has one; deployment
        without a profile still deploys and is marked as having no profile.

- [ ] **Task 2 — Monitoring Worker foundation + runtime health**
  - [ ] Add a shared per-Satellite worker loop that wakes on an interval and, for each
        monitored deployment, processes the latest completed window; deployment-scoped,
        off the inference path, best-effort.
  - [ ] Add the `monitoring_results` and `monitoring_alerts` storage and the alert
        lifecycle (open / update / resolve).
  - [ ] Implement runtime health (counts, error rate, latencies, failed inferences)
        and its alerts; this needs no profile.
  - [ ] Tests: worker processes only monitored deployments; runtime health results and
        alerts are materialized; alert opens and later resolves; a storage failure
        skips the window without affecting inference.

- [ ] **Task 3 — Worker: data quality**
  - [ ] Compute per-feature missing rate, type-mismatch rate, numeric range-violation
        rate (against reference min/max), and unseen-category rate (against reference
        categories), with alerts.
  - [ ] Skip cleanly when no profile is available.
  - [ ] Tests: invalid inputs (missing, wrong type, out-of-range, unseen category)
        produce the expected rates and alerts; no profile → skipped.

- [ ] **Task 4 — Worker: feature drift and output drift (PSI)**
  - [ ] Compute univariate PSI per input feature against the reference distributions
        (numerical via reference bins, categorical via reference proportions) with
        severity thresholds.
  - [ ] Compute output drift via PSI on predictions against the output summary, plus
        the regression prediction-trend summary, with severity.
  - [ ] Tests: shifted inputs/outputs cross the PSI thresholds and raise alerts;
        stable data stays normal; unseen categories contribute to feature PSI.

- [ ] **Task 5 — Worker: multivariate drift (PCA reconstruction error)**
  - [ ] For the live window, standardize numerical features with the stored scaler,
        project and reconstruct via the stored PCA, compute mean reconstruction error,
        and alert when it exceeds the reference mean by more than 3 standard
        deviations.
  - [ ] Skip cleanly when the PCA profile or required numerical features are missing.
  - [ ] Tests: a joint/correlation shift that univariate drift misses is caught by the
        reconstruction-error threshold; in-distribution data stays normal.