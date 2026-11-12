# Monitoring for a model logged through MLflow

A deployed tabular model shows drift and data quality only when its artifact
holds a reference profile built from the training data. Models the plugin
converts from MLflow have none yet. Add it to the stored model before the
experiment is uploaded.

The converted model has one input per column of the MLflow signature, which is
what the profile needs. Log the model with an `input_example` or a signature so
the column names carry over.

## Steps

1. Turn off the automatic upload, so the experiment waits for the profile:

   ```bash
   export LUML_MLFLOW_AUTOSYNC=0
   ```

2. Train and log as usual. Keep the run id.

   ```python
   import mlflow
   import mlflow.sklearn

   mlflow.set_tracking_uri("luml://My org/Research")
   mlflow.set_experiment("churn")
   with mlflow.start_run() as run:
       model.fit(X_train, y_train)
       mlflow.sklearn.log_model(model, name="churn_model", input_example=X_train.head())
   ```

3. Add the profile to the model in the local store. An MLflow run id is also
   its LUML experiment id.

   ```python
   from pathlib import Path

   from luml.experiments.tracker import ExperimentTracker
   from luml.utils.packaging import TABULAR_MONITORING_TAG, add_reference_profile

   store = Path.home() / ".luml" / "experiments"  # or LUML_BACKEND_STORE_URI
   tracker = ExperimentTracker(f"sqlite://{store}")
   (logged,) = tracker.get_models(run.info.run_id)

   add_reference_profile(
       str(store / logged.path),
       X_train,
       "classification",  # or "regression"
       model.predict,
       predict_proba=model.predict_proba,  # classification only
       output_names=["predictions"],
       class_names=["no", "yes"],
       additional_producer_tags=[TABULAR_MONITORING_TAG, "luml.ai::kind_tabular:v1"],
   )
   ```

4. Upload the experiment:

   ```bash
   luml-mlflow sync --run <run_id>
   ```

## What makes it work

- `X_train` has the same column names as the logged signature.
- `predict` returns what the converted model returns. The model's output is
  named `predictions` and holds the raw `predict` result, so pass
  `model.predict` itself. Do not cast or reshape it.
- The two tags turn on the monitoring views and mark the model as tabular.
  The plugin sets neither.
- The store path is written out in full. The tracker does not expand `~`.

To check the result before uploading, run the check from the SDK skill:
`python -m luml skills show luml-sdk references/monitoring.md`.
