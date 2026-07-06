---
sidebar_label: SDK Reference Profile Spec
title: SDK Reference Profile Generation Spec
---

# Proposals

## Problem

The Monitoring Worker (part 2 — the monitoring metrics-processing spec) needs a
**reference baseline** to compare live inference data against — per-feature statistics
and distributions, an output distribution, and a multivariate (PCA) profile. Nothing
produces this today. The SDK already packages classical-ML models and embeds the
input/output **schema** (types and categorical categories) into the artifact, but not
the **statistics** the worker needs.

We need the SDK to generate a **reference profile** from the model's training dataset
at packaging time and embed it in the model artifact, so the Satellite can load it at
deploy and the worker can use it.

## Solution at a glance

At packaging the user passes the **training dataset**, the **model**, and the **task
type**. The SDK computes:

- per-feature summaries (numerical and categorical) from the training features,
- output summaries by running the model on the training data,
- a PCA profile (scaler + PCA + reference distribution of PCA scores) for
  multivariate monitoring,

assembles them into a single reference profile, and embeds it in the `.luml`
artifact. The user hand-authors nothing.

## Why this approach

- The **training dataset is the natural baseline** — it defines what "normal" inputs
  and outputs look like.
- The SDK **already owns packaging** and already extracts the schema and categorical
  categories, so the profile is a natural extra step on the same path.
- **Precomputing at packaging** keeps the Satellite and the worker simple: they only
  read and compare, never fit.

# Design

## Where it lives

Packaging today (`sdk/python/sdk/luml/utils/packaging.py`) already extracts the
input/output schema and, for pandas inputs, the categorical categories, and writes
them into the artifact alongside the manifest. Reference-profile generation is a new
step on this same packaging path, run when the user provides reference data. The
assembled profile is embedded in the artifact next to the existing manifest / dtypes,
so the Satellite reads it on the same deploy path it already uses for the manifest.

## What the user passes

- **reference data** — the training feature set (the same shape the model consumes);
- **the model** — used to compute the output summaries via prediction;
- **task type** — `regression` or `classification`; used by the SDK to summarize the
  output the right way. It is not stored as a field — it is reflected structurally by
  which output group is populated (`numerical_outputs` vs `categorical_outputs`).

If reference data is not provided, packaging still succeeds and no profile is embedded
(the deployment simply has no profile; the worker then runs only profile-free
metrics).

## The reference profile (contract)

The profile is the data contract between the SDK (producer) and the worker
(consumer). Top level: `feature_summaries`, `output_summaries`, `pca_profile`.

For each **numerical** feature (under `feature_summaries.numerical_features`):

| Field | Type | Meaning |
| --- | --- | --- |
| `position` | int | column position in input order |
| `mean`, `std`, `min`, `max` | number | basic statistics |
| `quantiles` | q05, q25, q50, q75, q95 | percentile values |
| `bin_edges` | list of number | reference histogram bin boundaries |
| `bin_centres` | list of number | bin centers |
| `frequencies` | list of int | reference counts per bin |
| `probabilities` | list of number | reference proportion per bin (for PSI) |
| `count` | int | reference sample count |
| `missing` | int | missing count in reference |

For each **categorical** feature (under `feature_summaries.categorical_features`):

| Field | Type | Meaning |
| --- | --- | --- |
| `position` | int | column position in input order |
| `categories` | list of string | known categories |
| `frequencies` | list of int | reference counts per category |
| `probabilities` | map category → number | reference proportion per category (for PSI) |
| `count` | int | reference sample count |
| `missing` | int | missing count in reference |
| `n_unique` | int | number of distinct categories |

**Output summaries** mirror feature summaries, computed from the model's predictions
on the training data: `output_summaries.numerical_outputs.{name}` uses the numerical
shape (regression, e.g. `y_pred`); `output_summaries.categorical_outputs.{name}` uses
the categorical shape (classification, predicted-class proportions). Multiple outputs
are supported. The presence of `numerical_outputs` vs `categorical_outputs` is how the
worker tells regression from classification.

The **PCA profile** (numerical features only):

| Part | Contents |
| --- | --- |
| `scaler` | standardization params (`mean_`, `scale_`, `var_`, `n_features`) |
| `pca` | `n_components`, `n_features`, component matrix (`components`), centering `mean_`, ordered `feature_names` |
| `reference_distribution` | `mean` (vector) and `covariance` (matrix) of the training PCA scores, plus `n_samples` and `n_components` — the reference the worker measures Mahalanobis distance against |

## Example profile

The canonical example — the `tabular_regression` insurance model (features
age/bmi/sex/children/smoker/region, output `y_pred` charges):

```json
{
  "feature_summaries": {
    "numerical_features": {
      "age": {
        "position": 1,
        "mean": 39.2, "std": 14.05, "min": 18, "max": 64,
        "quantiles": {"q05": 18, "q25": 27, "q50": 39, "q75": 51, "q95": 62},
        "bin_edges": [18, 25, 35, 45, 55, 65],
        "bin_centres": [21.5, 30, 40, 50, 60],
        "frequencies": [204, 302, 276, 286, 270],
        "probabilities": [0.152, 0.226, 0.206, 0.214, 0.202],
        "count": 1338, "missing": 0
      },
      "bmi": {
        "position": 3,
        "mean": 30.66, "std": 6.1, "min": 15.96, "max": 53.13,
        "quantiles": {"q05": 21.26, "q25": 26.3, "q50": 30.4, "q75": 34.69, "q95": 41.11},
        "bin_edges": [15, 20, 25, 30, 35, 40, 45, 55],
        "bin_centres": [17.5, 22.5, 27.5, 32.5, 37.5, 42.5, 50],
        "frequencies": [52, 220, 352, 360, 235, 88, 31],
        "probabilities": [0.039, 0.164, 0.263, 0.269, 0.176, 0.066, 0.023],
        "count": 1338, "missing": 0
      }
    },
    "categorical_features": {
      "sex": {
        "position": 2,
        "categories": ["female", "male"],
        "frequencies": [662, 676],
        "probabilities": {"female": 0.495, "male": 0.505},
        "count": 1338, "missing": 0, "n_unique": 2
      },
      "children": {
        "position": 4,
        "categories": ["0", "1", "2", "3", "4", "5"],
        "frequencies": [574, 324, 240, 157, 25, 18],
        "probabilities": {"0": 0.429, "1": 0.242, "2": 0.179, "3": 0.117, "4": 0.019, "5": 0.014},
        "count": 1338, "missing": 0, "n_unique": 6
      },
      "smoker": {
        "position": 5,
        "categories": ["no", "yes"],
        "frequencies": [1064, 274],
        "probabilities": {"no": 0.795, "yes": 0.205},
        "count": 1338, "missing": 0, "n_unique": 2
      },
      "region": {
        "position": 6,
        "categories": ["northeast", "northwest", "southeast", "southwest"],
        "frequencies": [324, 325, 364, 325],
        "probabilities": {"northeast": 0.242, "northwest": 0.243, "southeast": 0.272, "southwest": 0.243},
        "count": 1338, "missing": 0, "n_unique": 4
      }
    }
  },
  "output_summaries": {
    "numerical_outputs": {
      "y_pred": {
        "position": 1,
        "mean": 13270, "std": 11500, "min": 1700, "max": 52000,
        "quantiles": {"q05": 2500, "q25": 4700, "q50": 9500, "q75": 17000, "q95": 41000},
        "bin_edges": [0, 5000, 10000, 15000, 20000, 30000, 50000, 65000],
        "bin_centres": [2500, 7500, 12500, 17500, 25000, 40000, 57500],
        "frequencies": [338, 295, 209, 173, 151, 139, 33],
        "probabilities": [0.253, 0.22, 0.156, 0.129, 0.113, 0.104, 0.025],
        "count": 1338, "missing": 0
      }
    }
  },
  "pca_profile": {
    "scaler": {
      "mean_": [39.2, 30.66],
      "scale_": [14.05, 6.1],
      "var_": [197.4025, 37.21],
      "n_features": 2
    },
    "pca": {
      "n_components": 2,
      "n_features": 2,
      "components": [[0.71, 0.7], [-0.7, 0.71]],
      "mean_": [0.0, 0.0],
      "feature_names": ["age", "bmi"]
    },
    "reference_distribution": {
      "mean": [0.0, 0.0],
      "covariance": [[1.0, 0.12], [0.12, 1.0]],
      "n_samples": 1338,
      "n_components": 2
    }
  }
}
```

For a **classification** model the output lives under
`output_summaries.categorical_outputs.{name}` with the categorical shape
(predicted-class proportions); when the model produces scores, a numerical score
summary can also be added under `numerical_outputs`.

## Generation methods

- **Numerical summary:** mean/std/min/max, the five quantiles, a histogram (bin edges,
  centres, per-bin frequencies and probabilities that sum to ~1), count, and missing
  count, from the training column.
- **Categorical summary:** known categories, per-category frequencies and
  probabilities, distinct count, and missing count.
- **Output summaries:** run the model on the training data; summarize predictions with
  the numerical method for regression (`numerical_outputs`) or the categorical method
  for classification (`categorical_outputs`); when the model produces
  scores/probabilities, also summarize the score numerically.
- **PCA profile:** fit a standard scaler and PCA on the numerical features; transform
  the training data to PCA scores and store the **mean vector and covariance matrix**
  of those scores as `reference_distribution` (with `n_samples`); store the scaler and
  PCA parameters (component matrix, centering, ordered feature names). This is what the
  worker uses to compute Mahalanobis distance for multivariate drift.

## Trade-offs and notes

- The PCA covers **numerical features only** (matching how multivariate drift is
  computed); categorical features participate only in univariate drift and data
  quality.
- Generation is deterministic given the same data (and PCA seed), so the profile is
  reproducible.
- The profile schema is expected to evolve, but changes should stay small; the worker
  reads it defensively.

# Scenarios

## Scenario: profile generated for a regression model
**Given** a user packaging a regression model and passing the training features
**When** the model is packaged
**Then** the artifact contains a profile with numerical and categorical feature
summaries, a `numerical_outputs` output summary, and a PCA profile with a
`reference_distribution` (mean + covariance), all computed from the training data.

## Scenario: profile generated for a classification model
**Given** a user packaging a classification model with training features
**When** the model is packaged
**Then** the output summary lives under `categorical_outputs` (predicted-class
proportions), with a numerical score summary when the model produces scores.

## Scenario: no reference data means no profile
**Given** a user packaging a model without reference data
**When** the model is packaged
**Then** packaging still succeeds and no profile is embedded in the artifact.

## Scenario: profile is internally consistent
**Given** a generated profile
**When** it is inspected
**Then** per-feature probabilities sum to ~1, histogram arrays are aligned
(edges/centres/frequencies/probabilities lengths match), the PCA `feature_names` match
the numerical features in order, and the `reference_distribution` covariance is square
of size `n_components`.

## Scenario: mixed numerical and categorical features
**Given** training data with both numerical and categorical columns
**When** the profile is generated
**Then** each column is summarized under the correct group, and the PCA profile
includes only the numerical columns.

# Tasks

- [ ] **Task 1 — Feature and output summaries in the artifact**
  - [ ] On the packaging path, when reference data is provided, compute per-feature
        numerical and categorical summaries and the output summaries (by predicting on
        the training data), placing outputs under `numerical_outputs` for regression or
        `categorical_outputs` for classification.
  - [ ] Assemble the reference profile and embed it in the model artifact next to the
        existing manifest/schema; embed nothing when no reference data is given.
  - [ ] Tests: summaries produced for a regression and a classification model;
        probabilities sum to ~1 and histogram arrays are aligned; no reference data →
        no profile embedded; packaging still succeeds either way.

- [ ] **Task 2 — PCA profile for multivariate monitoring**
  - [ ] Fit a scaler and PCA on the numerical features; transform training data to PCA
        scores and store their mean vector and covariance matrix as
        `reference_distribution` (with `n_samples`); store the scaler and PCA
        parameters (components, centering, ordered feature names).
  - [ ] Add the PCA profile to the embedded reference profile.
  - [ ] Tests: PCA profile present and consistent (feature names match numerical
        features, component matrix shape matches); `reference_distribution` has a mean
        vector and a square covariance of size `n_components`; numerical-only coverage.
