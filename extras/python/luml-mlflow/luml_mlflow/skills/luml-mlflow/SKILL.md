---
name: luml-mlflow
description: Log existing MLflow tracking code to LUML and Flow with the luml-mlflow plugin, changing only the tracking URI. Use when a project tracks experiments, models or traces with MLflow and should move to LUML.
---

# MLflow to LUML

`luml-mlflow` (PyPI: `luml-mlflow`) makes LUML an MLflow backend. The training
code keeps calling the MLflow API (`mlflow.start_run`, `log_param`,
`log_metric`, `mlflow.sklearn.log_model`, `@mlflow.trace`), and only the
tracking URI changes.

It is not a full two-way compatibility layer. It moves existing MLflow logging
to LUML with little change, as a first step. Features that only LUML has, such
as per-sample evals and monitoring profiles, come from the SDK
(`python -m luml skills show luml-sdk`), and new code is best written with the
SDK directly.

## Set up

Needs Python 3.12+ and MLflow 3.1+.

```bash
pip install luml-mlflow
```

```python
import mlflow

mlflow.set_tracking_uri("luml://local")  # local store only
# mlflow.set_tracking_uri("luml://My org/Research")  # also upload to this orbit
mlflow.set_experiment("churn")
```

This is the only LUML line in the code. The URI can also come from
`MLFLOW_TRACKING_URI`.

- `luml://local` writes to `~/.luml/experiments`, the store Flow reads by
  default, so `lumlflow ui` shows the experiments. `LUML_BACKEND_STORE_URI`
  changes the path.
- `luml://<organization>/<orbit>` (names or ids) does the same and uploads each
  experiment when it finishes, to a collection named after the MLflow
  experiment. Write names as they are, spaces included; `%20` is not decoded.
- The upload needs an API key: `LUML_API_KEY`, else `~/.luml.json`, else the
  key Flow keeps in the system keyring. Logging to the local store needs none.

## MLflow words in LUML

The two tools use some of the same words for different things. Talk to the
user in LUML's words, and translate when they use MLflow's. LUML has no
"run": an MLflow run is a LUML **experiment**.

| MLflow | LUML |
| --- | --- |
| Experiment | **Experiment group** in Flow; **collection** on the platform, where its experiments upload |
| Run | **Experiment**: one attempt with its params, metrics and attachments |
| Params, metrics, tags | Static params, metrics, tags of that experiment |
| Artifact (any logged file) | **Attachment**: a file inside an experiment. A LUML *artifact* is a whole item in the registry: a model, an experiment or a dataset |
| Logged model (`log_model`) | **Model**: a `.luml` artifact, converted from the MLflow model |
| Registered model | **Track**: the versions of one model, with stages |
| Model version | **Version** of a track |
| Traces (inside a run) | Traces of that experiment |
| Tracking server | **Orbit** inside an **organization** |

When an MLflow run logged exactly one model, the upload is that model with
its experiment embedded; the registry shows the experiment's snapshot with the
model. `LUML_MLFLOW_UPLOAD_MODE=separate` uploads each model and the
experiment as separate artifacts.

Below, `--run` and "run id" are the plugin's and MLflow's names; each one
refers to a LUML experiment.

## What does not carry over

| MLflow | What happens | Do instead |
| --- | --- | --- |
| The default experiment (no `set_experiment`) | `start_run` fails: `Experiment '0' not found` | Call `mlflow.set_experiment(...)` first |
| Traces without an active run | Dropped with a warning | Trace inside `with mlflow.start_run():` |
| `mlflow.genai.evaluate()` | Aggregate scores and traces are kept; per-sample scores are lost | Run evals with the SDK's `evaluate()` for per-sample results |
| Model registry (`register_model`, stages, aliases) | Not supported; the registry is an empty placeholder | Upload, then use LUML tracks and stages (`python -m luml_api skills show luml-api`) |
| `log_inputs(datasets=...)` | Dropped with a warning | Save the dataset with the SDK's `save_tabular_dataset` |
| Deleting, renaming or restoring MLflow experiments | Not supported | Manage the experiment groups in Flow |
| Tags starting with `luml.` | Rejected; the plugin reserves them | Use another prefix |
| Monitoring | Converted models carry no reference profile | Add one before upload: [references/monitoring.md](references/monitoring.md) |

Unsupported calls log a warning and carry on. Set
`LUML_MLFLOW_ON_UNSUPPORTED=raise` while migrating to turn them into errors and
find every call the plugin drops.

## Uploads

Each experiment uploads when its MLflow run finishes. The upload is
best-effort: a failure is recorded on the experiment and never stops the
training script.

```bash
luml-mlflow status --run <run_id>          # not_uploaded, uploading, uploaded or failed
luml-mlflow sync --run <run_id>            # upload one experiment now
luml-mlflow sync --experiment churn        # every experiment of an MLflow experiment
luml-mlflow sync --all
```

Uploaded experiments are skipped unless `--force` is given.
`LUML_MLFLOW_AUTOSYNC=0` turns the automatic upload off, so experiments upload
only with `sync`.

When the collection named after the MLflow experiment exists with another
type, the upload stops. `LUML_MLFLOW_COLLECTION_CONFLICT=suffix` uploads to a mixed
collection named `<experiment> (mlflow)` instead.

## Rules

1. Change only the tracking URI. Do not rewrite working MLflow calls into SDK
   calls unless the user asks for the migration.
2. Check each MLflow feature the project uses against the table above, and
   tell the user what will not carry over before they rely on it.
3. Never put the API key in code.
4. When the project starts needing what the table says is lost, suggest moving
   that part to the SDK.

## References

- [references/monitoring.md](references/monitoring.md): add a reference
  profile to an MLflow model before it is uploaded.
