# luml-mlflow

MLflow plugin that redirects MLflow tracking to a [LUML](https://luml.ai) orbit. Training code keeps calling the standard MLflow API, such as `mlflow.start_run`, `mlflow.log_param`, `mlflow.log_metric` and `mlflow.sklearn.log_model`. The plugin records each run in a local store and, when the run finishes, uploads it to the orbit as a LUML collection. No LUML SDK calls are needed in the training script.

The plugin registers a tracking store, an artifact repository and a placeholder model-registry store for the `luml://` URI scheme. MLflow discovers them automatically.

Requires Python 3.12 or later and MLflow 3.1 or later.

## Installation

```bash
pip install luml-mlflow
```

Uploading runs needs a LUML API key, created in the LUML web interface under account settings. The plugin reads it from `LUML_API_KEY`, then `~/.luml.json`, then the system keyring where [Flow](https://pypi.org/project/lumlflow/) stores it. Logging to the local store works without a key.

```bash
export LUML_API_KEY="luml_your_api_key"
```

## Usage

Set the tracking URI to an organization and an orbit, by name or id. It is the only LUML-specific line:

```python
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier

mlflow.set_tracking_uri("luml://my-org/my-orbit")
mlflow.set_experiment("churn_prediction")

with mlflow.start_run(run_name="random_forest_v1"):
    mlflow.log_param("n_estimators", 100)
    model = RandomForestClassifier(n_estimators=100).fit(X, y)
    mlflow.log_metric("accuracy", model.score(X, y))
    mlflow.sklearn.log_model(model, name="churn_model")
```

When the run finishes, it is uploaded to a collection named after the experiment. A logged model becomes a LUML model in the `.luml` format, other artifacts become attachments, and parameters, metrics and tags go into an experiment snapshot. The upload is best-effort: a failure is recorded on the run and never crashes the training script.

`luml://local` keeps runs on disk without uploading them. Runs are staged in the same SQLite store that Flow reads (`~/.luml/experiments`, set by `LUML_BACKEND_STORE_URI`), so they show up in `lumlflow ui` as well.

## Configuration

- `LUML_MLFLOW_AUTOSYNC=0` turns off the automatic upload.
- `LUML_MLFLOW_UPLOAD_MODE=separate` uploads each model and the experiment snapshot as separate artifacts. The default, `auto`, embeds the snapshot in the model when a run logged exactly one model.

## Command line

`luml-mlflow` uploads runs on demand, for example runs logged with autosync off or runs whose upload failed:

```bash
luml-mlflow sync --run <run_id>
luml-mlflow sync --experiment churn_prediction
luml-mlflow sync --all
luml-mlflow status --run <run_id>
```

Already uploaded runs are skipped unless `--force` is passed.

## Documentation

[Logging MLflow runs to LUML](https://docs.luml.ai/guides/Integrations/mlflow_tutorial)
