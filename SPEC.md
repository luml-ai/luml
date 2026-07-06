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
- **Monitoring Worker** — one shared per-Satellite background worker — is a **generic
  metric engine**, not a fixed set of calculations. It holds a **registry of metric
  definitions**; every tick it reads each monitored deployment's latest window of
  collected data, selects the metrics that **apply** (by what the deployment has —
  profile parts, task type, data), computes them, and writes results and alert state
  into local storage. The initial registry ships five built-in metrics:
  - runtime health,
  - data quality,
  - univariate feature drift (PSI),
  - output drift (PSI on predictions),
  - multivariate drift (PCA reconstruction error).

  Adding a metric later is a new registry entry, not a change to the worker. The same
  metric interface is the extension point for custom metrics and, next stage, a
  deployed monitoring model.

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
- A **generic metric engine** follows how Evidently, NannyML, and W&B Weave work —
  every metric (built-in or custom) is the same kind of registered unit — so new and
  custom metrics are registry entries with a common interface, not worker rewrites.

# Design

## Scope

In scope:

- Satellite loading of the reference profile at deploy time
- a per-Satellite Monitoring Worker built as a **generic metric engine**: a metric
  interface, a registry, and applicability-based selection
- the five built-in metrics as registry entries: runtime health, data quality,
  feature drift, output drift, multivariate drift
- materialized results and alert state, in a read-ready shape

Out of scope: generation of the reference profile in the SDK; authoring and delivery
of custom metrics to the Satellite and monitoring by a deployed model (next stage —
this slice only defines the extension point they plug into); realized performance and
delayed targets; Query API, dashboard, and UI; alert delivery to external channels;
task types beyond the classical-ML tabular case (regression and classification are
covered; new metrics and task types are added as registry entries).

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

The worker is a **generic metric engine**, not a fixed set of calculations. It holds a
**registry** of metric definitions; the five built-in metrics below are its initial
entries, and everything the worker computes is driven by the registry.

**Metric interface.** Each metric definition declares:

- **requirements / applicability** — what it needs to run: which collected data, which
  reference-profile parts (feature summaries / output summary / PCA profile), and which
  `task_type`;
- **compute** — given a window of the deployment's collected data and the reference
  profile, produce metric values and a severity;
- **thresholds** — the values that turn a result into a warning or critical alert
  (built-in defaults now, overridable later).

**Selection (how the worker decides what to compute).** Each tick, for each monitored
deployment, the worker builds the deployment's context — does it have a profile, which
parts, which `task_type`, is there data in the window — and runs **only the registry
metrics whose requirements are satisfied**. The set of metrics is therefore not
hard-coded: with no profile only runtime health runs; with a partial profile only the
applicable subset runs; with a full profile all five run.

**Extension point.** Adding a metric is a new registry entry implementing the same
interface — no change to the worker loop. This is where custom metrics and, next stage,
a deployed monitoring model plug in; how such a metric is delivered to the Satellite
(bundled in the model artifact or deployed as a monitoring model) is decided in that
next stage and is out of scope here.

- **Scheduling:** the worker wakes on an interval and, for each monitored deployment,
  processes the most recent completed time window of collected data. Window size and
  interval are configurable with sensible defaults.
- **Scope:** every unit of work is deployment-scoped (deployment id, metric, window).
- **Source:** it reads only from GreptimeDB — primarily the `inference_events` trace
  table (parsing the JSON-string `inputs` / `output`) plus the runtime metric tables —
  and writes only `monitoring_results` and `monitoring_alerts`.
- **Best-effort:** the worker never blocks or affects inference. A metric whose
  requirements are unmet is skipped (e.g. no profile → only runtime health runs); a
  failing metric is isolated and does not stop the others; if storage is unavailable,
  the tick is skipped and retried next interval.

## Built-in metrics

These five are the initial registry entries. Each follows the metric interface above:
it declares its requirements (shown as **Inputs**), computes over the window, and
raises or clears alerts in `monitoring_alerts` through its thresholds. The worker runs
each only when its requirements are met.

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
| `metric` | the registry metric that produced this result — a built-in group (runtime, data_quality, feature_drift, output_drift, multivariate) or a registered metric id |
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

## Scenario: worker runs only the applicable metrics
**Given** a monitored deployment whose profile has feature summaries but no PCA profile
**When** the worker ticks
**Then** runtime health, data quality, and feature drift run, while multivariate drift
is skipped because its requirements are unmet — without error.

## Scenario: a new metric is added as a registry entry
**Given** a new metric registered with the metric interface whose requirements are met
by a deployment
**When** the worker ticks
**Then** the new metric is computed and its results/alerts are materialized, with no
change to the worker loop or the built-in metrics.

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

- [x] **Task 1 — Satellite: load the reference profile at deploy**
  - [x] Read the reference profile from the artifact on the deploy path and store it
        on the deployment record alongside the existing schema/manifest.
  - [x] Treat a missing or placeholder profile as "no profile" rather than an error.
  - [x] Tests: profile loaded and available for a deployment that has one; deployment
        without a profile still deploys and is marked as having no profile.

- [x] **Task 2 — Monitoring Worker engine (registry + selection) + runtime health**
  - [x] Add a shared per-Satellite worker loop that wakes on an interval and, for each
        monitored deployment, processes the latest completed window; deployment-scoped,
        off the inference path, best-effort.
  - [x] Define the metric interface (requirements/applicability, compute over a window,
        thresholds) and a registry; each tick, build the deployment context and run only
        the metrics whose requirements are met; a failing metric is isolated from the
        others.
  - [x] Add the `monitoring_results` and `monitoring_alerts` storage and the alert
        lifecycle (open / update / resolve).
  - [x] Register runtime health (counts, error rate, latencies, failed inferences) as
        the first built-in metric; it requires no profile.
  - [x] Tests: only monitored deployments are processed; selection runs runtime health
        with no profile and skips profile-dependent metrics; results/alerts are
        materialized; an alert opens then resolves; a failing metric does not stop the
        others; a storage failure skips the window without affecting inference.

- [x] **Task 3 — Worker: data quality metric**
  - [x] Register data quality as a registry metric whose requirement is the profile's
        feature summaries: per-feature missing rate, type-mismatch rate, numeric
        range-violation rate (against reference min/max), and unseen-category rate
        (against reference categories), with alerts.
  - [x] Skip cleanly when no profile is available (requirement unmet).
  - [x] Tests: invalid inputs (missing, wrong type, out-of-range, unseen category)
        produce the expected rates and alerts; no profile → skipped.

- [ ] **Task 4 — Worker: feature drift and output drift metrics (PSI)**
  - [ ] Register feature drift as a registry metric (requires per-feature reference
        distributions): univariate PSI per input feature (numerical via reference bins,
        categorical via reference proportions) with severity thresholds.
  - [ ] Register output drift as a registry metric (requires the output summary and
        `task_type`): PSI on predictions against the output summary, plus the regression
        prediction-trend summary, with severity.
  - [ ] Tests: shifted inputs/outputs cross the PSI thresholds and raise alerts;
        stable data stays normal; unseen categories contribute to feature PSI.

- [ ] **Task 5 — Worker: multivariate drift metric (PCA reconstruction error)**
  - [ ] Register multivariate drift as a registry metric (requires the PCA profile):
        for the live window, standardize numerical features with the stored scaler,
        project and reconstruct via the stored PCA, compute mean reconstruction error,
        and alert when it exceeds the reference mean by more than 3 standard deviations.
  - [ ] Skip cleanly when the PCA profile or required numerical features are missing
        (requirement unmet).
  - [ ] Tests: a joint/correlation shift that univariate drift misses is caught by the
        reconstruction-error threshold; in-distribution data stays normal.