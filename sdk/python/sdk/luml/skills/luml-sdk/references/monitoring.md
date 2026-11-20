# Monitoring: the reference profile

## Why

Drift means the inputs or the predictions of a deployed model now differ from
what the model was trained on. The reference profile records "what it was trained
on": a summary of every feature, of the predictions and class probabilities, and
a PCA profile. It is computed from the training features and stored inside the
artifact as `reference_profile.json`. The model server reads it from there, so
every deployment of the artifact can be monitored with no extra setup.

What a deployment shows:

- **Every model:** runtime, traces and alerts.
- **Only with a reference profile:** data quality, feature drift, output drift,
  multivariate drift. The deploy form recommends repackaging a tabular model
  that has no profile.

LLM chains and agents get no profile. Monitor them with traces and evals.

## Rules

- Every tabular model that may be deployed gets a profile.
- Use the training features. Not test data, not a small sample.
- Add the profile before the model is logged or uploaded. An uploaded artifact
  does not change.

## scikit-learn

```python
from luml.integrations.sklearn import save_sklearn

model_ref = save_sklearn(model, inputs=X_train, reference_data=X_train)
# or, through the tracker:
tracker.log_model(model, name="churn", inputs=X_train, reference_data=X_train)
# or, on a sklearn artifact you saved earlier:
model_ref.add_reference_profile(X_train)
```

The task type (classification or regression) comes from the estimator. For a
forecasting model, pass `horizons=["h1", "h2", ...]`, the names of the outputs.

## Any other tabular model

Built-in support for other frameworks will come. Until then, write it yourself.
It is a few lines:

```python
from luml.utils.packaging import TABULAR_MONITORING_TAG, add_reference_profile

add_reference_profile(
    model_ref.path,              # a saved artifact, before upload
    X_train,                     # DataFrame of training features
    "classification",            # or "regression" or "forecasting"
    predict,                     # features -> what the artifact returns as "y"
    predict_proba=predict_proba, # classification only, optional
    output_names=["y"],          # the artifact's prediction output
    class_names=["no", "yes"],   # classification only, optional
    additional_producer_tags=[TABULAR_MONITORING_TAG],
)
```

What makes it work:

- **Inputs match by name.** The profile's feature names are the DataFrame's
  columns. They must be the artifact's input names: one input per feature, as
  `save_*(inputs=DataFrame)` and the custom tabular example in
  [packaging.md](packaging.md) produce. A model with one matrix input cannot be
  monitored per feature.
- **Same predictions as the artifact.** `predict` must return exactly what the
  artifact returns under `output_names`. If the artifact's `y` is a probability,
  `predict` returns that probability, not a label.
- **Tags.** `TABULAR_MONITORING_TAG` turns the monitoring views on. The artifact
  should also carry `luml.ai::kind_tabular:v1`, which marks it as tabular. The
  built-in `save_*` functions set it; for a custom model set it in
  `set_producer_info`, or add it to `additional_producer_tags`.

## Check it

```python
import json
import tarfile

with tarfile.open(model_ref.path) as archive:
    manifest = json.load(archive.extractfile("manifest.json"))
    profile = json.load(archive.extractfile("reference_profile.json"))

inputs = {spec["name"] for spec in manifest["inputs"]}
summaries = profile["feature_summaries"]
profiled = set(summaries.get("numerical_features", {})) | set(
    summaries.get("categorical_features", {})
)
assert "luml.ai::tabular_monitoring:v1" in manifest["producer_tags"]
assert profiled == inputs, (profiled, inputs)
assert profile["profile_status"] == "ready"
```

Then run the artifact on a few rows ([verify-artifact.md](verify-artifact.md))
and compare its output with `predict` on the same rows.
