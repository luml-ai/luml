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

We need to generate a **reference profile** from the model's training dataset at
packaging time and embed it in the model artifact, so the Satellite can load it at
deploy and the worker can use it. This must happen on **both** paths that produce a
model artifact:

- the **Python SDK** packaging path (`sdk/python/sdk/luml/utils/packaging.py`), and
- the browser **Express Tasks** path, where tabular models are trained and packaged
  entirely in the Pyodide **web worker**
  (`wasm/packages/dfs_webworker/dfs_webworker/tabular.py`) for the
  `tabular_classification` and `tabular_regression` tasks.

A consumer must be able to tell **whether an artifact carries a profile** without
opening and probing its files. So profile presence is signalled by a dedicated
**producer tag** on the artifact manifest, and the profile itself is stored as
**JSON** (no pickled or binary blobs) so it round-trips identically through both the
Python and the browser toolchains.

## Solution at a glance

Whenever a model is packaged with its training data available, the same
profile-computation logic computes:

- per-feature summaries (numerical and categorical) from the training features,
- output summaries by running the model on the training data,
- a PCA profile (scaler + PCA + reference distribution of PCA scores) for
  multivariate monitoring,

assembles them into a single reference profile, writes it into the artifact as a
JSON document (`reference_profile.json`), and stamps a **`reference_profile:v1`**
producer tag on the manifest to mark its presence. The user hand-authors nothing.

Because the logic must run in two separately packaged toolchains that share no
internal package (the SDK wheel and the `dfs_webworker` Pyodide wheel), it lives in a
**single canonical, dependency-light module** (numpy / scikit-learn / pandas only),
with a **byte-identical vendored copy** shipped inside `dfs_webworker`.

## Why this approach

- The **training dataset is the natural baseline** — it defines what "normal" inputs
  and outputs look like.
- Both packaging paths **already own packaging** and already produce fnnx/`.luml`
  artifacts, so the profile is a natural extra step on the same path.
- **Precomputing at packaging** keeps the Satellite and the worker simple: they only
  read and compare, never fit.
- A **presence tag** lets the Satellite/worker branch cheaply (profile-based vs
  profile-free metrics) by reading the manifest, without unpacking artifact files.
- **JSON-only** storage means the profile produced in the browser (Pyodide) and the
  profile produced by the SDK are the same shape and are readable everywhere.

# Design

## Where it lives

Reference-profile generation is one behaviour with two integration points:

**1. Canonical module (single source of truth).** The computation — feature
summaries, output summaries, PCA profile, and assembly into the JSON contract — lives
in one dependency-light module that imports **only numpy, scikit-learn, and pandas**
(no `luml`-, `fnnx`-, or `falcon`-specific imports), so it runs unchanged in both a
CPython SDK environment and the Pyodide web worker. It is the source of truth in the
SDK. A **byte-identical copy is vendored into `dfs_webworker`** (the two are separate
wheels with no shared internal package). Both copies are covered by tests; a check
keeps them from drifting.

**2. SDK packaging path** (`sdk/python/sdk/luml/utils/packaging.py`). Packaging today
already extracts the input/output schema and, for pandas inputs, the categorical
categories, and writes them into the artifact alongside the manifest via
`PyfuncBuilder`. When reference data is provided, the packaging path calls the
canonical module, writes the result as `reference_profile.json` into the artifact, and
adds the presence tag to the manifest producer tags. The Satellite reads it on the
same deploy path it already uses for the manifest.

**3. Web-worker (Express Tasks) path**
(`wasm/packages/dfs_webworker/dfs_webworker/tabular.py::tabular_train`). This trains a
tabular model with falcon `AutoML` and packages it with `m.save_model(...)`, which
returns an **uncompressed tar** fnnx artifact whose `manifest.json` producer tags are
`["falcon.beastbyte.ai::{task}:v1"] + extra_tags`. Here the profile is generated from
the training data (always, for both `tabular_classification` and `tabular_regression`)
using the vendored module, and embedded into the returned artifact.

## What produces a profile

- **reference data** — the training feature set (the same shape the model consumes);
- **the model** — used to compute the output summaries via prediction;
- **task type** — `regression` or `classification`; used to summarize the output the
  right way. It is not stored as a field — it is reflected structurally by which output
  group is populated (`numerical_outputs` vs `categorical_outputs`).

On the **SDK path** reference data is optional: if it is not provided, packaging still
succeeds, no `reference_profile.json` is written, and the presence tag is **not** added
(the deployment simply has no profile; the worker then runs only profile-free metrics).

On the **web-worker path** the training data is always present (it is what the model is
trained on), so the profile is **always** generated for both tabular tasks.

## Presence tag

Profile presence is signalled by a single, un-namespaced sentinel producer tag:

```
reference_profile:v1
```

- It is added to the artifact's `manifest.json` producer-tag list **only when** a
  profile was actually written.
- On the SDK path it is passed through the builder's producer tags
  (`set_producer_info(tags=...)`).
- On the web-worker path it is passed through `m.save_model(extra_tags=[...,
  "reference_profile:v1"])`, which falcon concatenates verbatim into the manifest
  producer tags — so no tar surgery is needed for the tag itself.
- A consumer (Satellite / worker) determines whether a profile exists by checking for
  this exact tag in the manifest producer tags, **without unpacking** the artifact's
  other files.

## JSON-only serialization

Everything the profile stores is plain JSON — objects, arrays, numbers, strings,
booleans, `null`. There are **no** pickled objects, numpy arrays, or binary blobs
anywhere in `reference_profile.json`:

- numpy scalars are converted to native Python numbers; numpy arrays to nested lists;
- the scaler and PCA parameters (`mean_`, `scale_`, `var_`, `components`, `mean_`, …)
  and the reference distribution (`mean` vector, `covariance` matrix) are stored as
  nested lists of numbers, not serialized estimator objects;
- the document round-trips identically whether produced by the SDK (CPython) or the
  web worker (Pyodide), and is embedded as a standalone `reference_profile.json` file
  next to the manifest.

## Embedding into the artifact

- **SDK path:** write `reference_profile.json` into the artifact through the
  `PyfuncBuilder` file API (next to `manifest.json` / `dtypes.json`) and add the
  presence tag via `set_producer_info(tags=...)`.
- **Web-worker path:** call `m.save_model(extra_tags=[..., "reference_profile:v1"])`
  to get the tar bytes with the tag already in the manifest, then add a single
  `reference_profile.json` member to that uncompressed tar and return the repacked
  bytes. `tarfile`, `json`, numpy, scikit-learn, pandas, and `fnnx` are all available
  in the worker (see `frontend/public/webworker.js`).

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
  reads it defensively. The presence **tag is versioned** (`reference_profile:v1`) so a
  future breaking change can bump the tag.
- The computation module is **duplicated by vendoring** (one canonical copy in the SDK,
  a byte-identical copy in `dfs_webworker`) rather than shared via a third package —
  chosen to avoid publishing/versioning an extra wheel. A drift check (byte comparison
  in CI/tests) is the guard against the two copies diverging.
- The web-worker path must keep everything **JSON-serializable end to end** because the
  artifact bytes cross the Pyodide ↔ JS boundary; this is the same constraint that
  makes JSON-only storage natural.

# Scenarios

## Scenario: SDK — profile generated for a regression model
**Given** a user packaging a regression model with the SDK and passing the training
features
**When** the model is packaged
**Then** the artifact contains `reference_profile.json` with numerical and categorical
feature summaries, a `numerical_outputs` output summary, and a PCA profile with a
`reference_distribution` (mean + covariance), all computed from the training data, and
the manifest producer tags include `reference_profile:v1`.

## Scenario: SDK — profile generated for a classification model
**Given** a user packaging a classification model with the SDK and training features
**When** the model is packaged
**Then** the output summary lives under `categorical_outputs` (predicted-class
proportions), with a numerical score summary when the model produces scores, and the
manifest carries the `reference_profile:v1` tag.

## Scenario: SDK — no reference data means no profile and no tag
**Given** a user packaging a model with the SDK without reference data
**When** the model is packaged
**Then** packaging still succeeds, no `reference_profile.json` is embedded, and the
manifest producer tags do **not** include `reference_profile:v1`.

## Scenario: presence detected by tag alone
**Given** two artifacts, one with a profile and one without
**When** a consumer reads only each `manifest.json` producer tags (without unpacking
other files)
**Then** the presence of `reference_profile:v1` correctly distinguishes the artifact
that carries a profile from the one that does not.

## Scenario: Express Tasks web worker — classification profile
**Given** the Express Tasks flow trains a `tabular_classification` model in the web
worker
**When** `tabular_train` packages the model
**Then** the returned fnnx artifact contains `reference_profile.json` (full profile
including feature summaries, `categorical_outputs`, and a PCA profile) and its manifest
producer tags include `reference_profile:v1` alongside the existing
`dataforce.studio::tabular_classification:v1` tag.

## Scenario: Express Tasks web worker — regression profile
**Given** the Express Tasks flow trains a `tabular_regression` model in the web worker
**When** `tabular_train` packages the model
**Then** the returned fnnx artifact contains `reference_profile.json` with
`numerical_outputs`, a PCA profile, and the `reference_profile:v1` tag.

## Scenario: profile is JSON-only
**Given** a generated `reference_profile.json` from either path
**When** it is loaded with a plain JSON parser
**Then** it parses with no custom decoders, contains only objects/arrays/numbers/
strings/booleans/null (no pickled objects or numpy arrays), and the scaler, PCA
`components`, and `covariance` are nested lists of native numbers.

## Scenario: SDK and web-worker profiles match in shape
**Given** the same training data and an equivalent model packaged on both paths
**When** the two `reference_profile.json` documents are compared
**Then** they have the same top-level structure and field names (values may differ
where the models differ), because both paths call the same canonical module.

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

- [x] **Task 1 — Canonical profile module: feature and output summaries**
  - [x] Create a dependency-light module (numpy / scikit-learn / pandas only — no
        `luml`/`fnnx`/`falcon` imports) that computes per-feature **numerical** and
        **categorical** summaries from a training feature set, and **output summaries**
        from model predictions, placing outputs under `numerical_outputs` for
        regression or `categorical_outputs` for classification. It accepts the training
        features, the task type, and a way to obtain predictions.
  - [x] Assemble these into the `feature_summaries` + `output_summaries` portions of
        the profile as **plain JSON-serializable** Python structures (native numbers,
        nested lists — no numpy scalars/arrays, no pickled objects).
  - [x] Tests: summaries for a regression and a classification input; probabilities sum
        to ~1 and histogram arrays are aligned (edges/centres/frequencies/probabilities
        lengths match); mixed numerical + categorical columns land in the correct group;
        `json.dumps` of the result succeeds with no custom encoder.

- [x] **Task 2 — Canonical profile module: PCA profile**
  - [x] In the same module, fit a scaler and PCA on the numerical features; transform
        the training data to PCA scores and store their mean vector and covariance
        matrix as `reference_distribution` (with `n_samples`); store the scaler and PCA
        parameters (components, centering, ordered feature names) as nested lists of
        native numbers. Assemble the full profile (`feature_summaries`,
        `output_summaries`, `pca_profile`).
  - [x] Tests: PCA profile present and consistent (feature names match numerical
        features in order, component-matrix shape matches); `reference_distribution` has
        a mean vector and a square covariance of size `n_components`; numerical-only
        coverage; whole profile is JSON-serializable.

- [x] **Task 3 — SDK packaging integration + presence tag**
  - [x] On the SDK packaging path (`sdk/python/sdk/luml/utils/packaging.py`), when
        reference data is provided, call the canonical module, write the result as
        `reference_profile.json` into the artifact via the `PyfuncBuilder` file API
        (next to `manifest.json`/`dtypes.json`), and add `reference_profile:v1` to the
        manifest producer tags (`set_producer_info(tags=...)`).
  - [x] When no reference data is provided: write no `reference_profile.json` and do
        not add the tag; packaging still succeeds.
  - [x] Tests: regression and classification artifacts contain `reference_profile.json`
        and carry the `reference_profile:v1` tag; without reference data neither the
        file nor the tag is present; the embedded file parses as plain JSON.

- [x] **Task 4 — Express Tasks web-worker integration**
  - [x] Vendor a **byte-identical copy** of the canonical module into
        `wasm/packages/dfs_webworker/dfs_webworker/` and add a drift check (byte
        comparison against the SDK canonical copy) to the test suite.
  - [x] In `dfs_webworker/tabular.py::tabular_train`, for both `tabular_classification`
        and `tabular_regression`, generate the full profile from the training data using
        the vendored module; call `m.save_model(extra_tags=[..., "reference_profile:v1"])`
        so the tag lands in the manifest, then add a single `reference_profile.json`
        member to the returned uncompressed tar and return the repacked bytes.
  - [x] Rebuild the `dfs_webworker` wheel shipped at
        `frontend/public/dfs_webworker-0.1.0-py3-none-any.whl` (and `frontend/dist`).
  - [x] Tests: for both tasks, the produced artifact contains `reference_profile.json`
        (full profile) and its manifest producer tags include `reference_profile:v1`
        alongside the existing `dataforce.studio::{task}:v1` tag; the profile is
        JSON-only; the vendored copy matches the SDK canonical copy byte-for-byte.
