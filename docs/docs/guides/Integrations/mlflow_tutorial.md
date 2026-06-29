---
title: Logging MLflow runs to LUML
sidebar_label: MLflow
sidebar_position: 3
---

# Logging MLflow runs to LUML

`luml-mlflow` is an MLflow plugin that redirects MLflow tracking to a LUML orbit. Training code keeps calling the standard MLflow API — `mlflow.start_run`, `mlflow.log_param`, `mlflow.log_metric`, `mlflow.sklearn.log_model`, and the rest. The plugin records each run in a local store and, when the run finishes, uploads it to the orbit as a LUML collection. No LUML SDK calls are required in the training script.

The plugin registers itself for the `luml://` URI scheme. Setting the MLflow tracking URI to `luml://<org>/<orbit>` is the only change a project needs.

*Note: the plugin requires Python 3.12 or later and MLflow 3.1 or later.*

## Setup

Install the plugin from PyPI:

```bash
pip install luml-mlflow
```

Installing the package registers three MLflow entry points for the `luml://` scheme: a tracking store, an artifact repository, and a placeholder model-registry store. MLflow discovers them automatically, so nothing else needs to be imported.

Uploading runs to an orbit requires a LUML API key, generated in the LUML web interface under account settings. The key can be made available in two ways.

The direct way is the `LUML_API_KEY` environment variable:

```bash
export LUML_API_KEY="luml_your_api_key"
```

Alternatively, save the key once through the [Flow](../../apps/lumlflow/lumlflow.md) app. Run `lumlflow ui`, open the interface, and enter the key. [Flow](../../apps/lumlflow/lumlflow.md) validates it against the platform and stores it in the system keyring, falling back to `~/.luml.json`. The plugin then reads the key back, looking at `LUML_API_KEY` first, then `~/.luml.json`, then the keyring.

The API key is only needed for uploads. Logging to the local store works without it.

## Pointing MLflow at LUML

Set the tracking URI to your organization and orbit before starting a run:

```python
import mlflow

mlflow.set_tracking_uri("luml://my-org/my-orbit")
```

The URI carries two pieces of information: the organization id (`my-org`) and the orbit id (`my-orbit`). Both accept names or ids. Runs created under this URI upload to that orbit when they finish.

To work offline, use the local-only URI:

```python
mlflow.set_tracking_uri("luml://local")
```

Local-only runs are recorded and viewable, but never uploaded. This is the way to try the plugin without an orbit, or to keep a run on disk until it is ready to publish.

Independently of the orbit target, runs are staged on disk in a SQLite store. Its location defaults to `~/.luml/experiments` and is controlled by `LUML_BACKEND_STORE_URI`. This is the same store the [Flow](../../apps/lumlflow/lumlflow.md) application reads, so runs logged through MLflow appear in [Flow](../../apps/lumlflow/lumlflow.md) as well.

## Logging a run

The following script logs a scikit-learn model. It is plain MLflow code — the only LUML-specific line is the tracking URI.

```python
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

mlflow.set_tracking_uri("luml://my-org/my-orbit")
mlflow.set_experiment("churn_prediction")

X = np.random.rand(1000, 8)
y = np.random.randint(0, 2, 1000)

with mlflow.start_run(run_name="random_forest_v1"):
    mlflow.log_param("n_estimators", 100)
    mlflow.log_param("max_depth", 10)

    model = RandomForestClassifier(n_estimators=100, max_depth=10)
    model.fit(X, y)

    mlflow.log_metric("accuracy", accuracy_score(y, model.predict(X)))
    mlflow.sklearn.log_model(model, name="churn_model")
```

Parameters become static values on the run, and metrics become dynamic values. The model logged with `log_model` is captured as an MLflow model directory. Any file logged with `mlflow.log_artifact` is stored as an attachment on the run.

When the `with` block exits, the run reaches the `FINISHED` status. That terminal status triggers the upload described below.

## What happens when a run finishes

Reaching a terminal status (`FINISHED` or `FAILED`) triggers an automatic upload to the orbit. The upload is best-effort: if it fails, the error is recorded on the run and `mlflow.end_run()` still returns normally, so a network problem never crashes a training script.

The upload lands in a LUML collection named after the MLflow experiment. The collection is of type `mixed` and is created on first use. Inside it:

- A model logged through `log_model` is packaged as a LUML **model** in the platform's [`.luml` format](../../documentation/Core-Concepts/luml_model.md) and stored on the run.
- Any other artifact logged on the run is stored as a LUML **attachment**.
- The run's parameters, metrics, and tags are packaged into an experiment snapshot.

By default (`LUML_MLFLOW_UPLOAD_MODE=auto`), a run that logged exactly one model embeds that snapshot inside the model artifact, producing a single artifact in the collection. A run with several models, or `LUML_MLFLOW_UPLOAD_MODE=separate`, uploads each model and the experiment snapshot as separate artifacts.

*Note: packaging supports the common MLflow model flavors. A model whose flavor cannot be packaged into the `.luml` format raises during the upload, and the run is marked as failed with the error recorded.*

To disable the automatic upload and publish runs manually instead, set `LUML_MLFLOW_AUTOSYNC=0`.

## Viewing runs

Use [Flow](../../apps/lumlflow/lumlflow.md) to inspect runs. Runs logged through the plugin are written to the same local store [Flow](../../apps/lumlflow/lumlflow.md) reads, so they show up there with no extra step. [Flow](../../apps/lumlflow/lumlflow.md) renders the groups, runs, parameters, metrics, logged models, and traces produced through MLflow, and it is the interface this store is built for.

```bash
lumlflow ui
```

The plugin can also serve the standard MLflow web UI from the LUML store, but this is not recommended:

```bash
mlflow ui --backend-store-uri luml://my-org/my-orbit
```

The MLflow UI is supported only far enough to load runs, parameters, and metrics. Its other areas are partial. The model-registry pages stay empty, because the plugin does not map LUML's registry onto MLflow's registered-model model (see the limitations below). Logged models are held in memory by the process that logged them, so a separate `mlflow ui` process shows the run and its metrics but an empty Models section. Operations the plugin does not implement, such as deleting or renaming a run, fail when triggered from the UI. Treat `mlflow ui` as a last resort for an MLflow-native view you cannot get otherwise, and use [Flow](../../apps/lumlflow/lumlflow.md) for everything else.

## Syncing from the command line

The `luml-mlflow` CLI uploads runs on demand. This covers runs logged with autosync disabled, runs whose upload failed, and re-uploads.

Sync a single run by id:

```bash
luml-mlflow sync --run <run_id>
```

Sync every pending run of an experiment, by name or id:

```bash
luml-mlflow sync --experiment churn_prediction
```

Sync every pending run across all experiments:

```bash
luml-mlflow sync --all
```

The selectors `--run`, `--experiment`, and `--all` are mutually exclusive. Already-uploaded runs are skipped unless `--force` is passed, and local-only runs are reported as skipped because they never upload. A run with no stored orbit target can be given one with `--tracking-uri luml://my-org/my-orbit`.

Inspect a run's upload state without uploading:

```bash
luml-mlflow status --run <run_id>
```

The status is one of `not_uploaded`, `uploading`, `uploaded`, or `failed`, followed by the collection id and the artifact links once an upload has completed.

## How MLflow concepts map to LUML

MLflow and LUML both use the word "experiment", but for different things. The plugin applies a fixed mapping, which matters when reading LUML directly or correlating the two systems:

| MLflow concept                   | LUML concept                  |
| -------------------------------- | ----------------------------- |
| Experiment                       | Group                         |
| Run                              | Experiment                    |
| Model (`log_model`)              | Model (`.luml` package)       |
| Other run artifacts              | Attachments                   |
| Uploaded run                     | Artifacts in a collection     |

An MLflow run is a LUML experiment, and an MLflow experiment is a LUML group. The collection an uploaded run lands in takes the MLflow experiment (LUML group) name.

## How tags are stored

MLflow tags are key-value pairs, while the LUML store has a narrower tag model, so the plugin routes tags by shape. Tags in the `mlflow.*` namespace are stored verbatim and round-trip unchanged. A user tag whose value is `"true"` or empty is stored as a LUML flag tag and round-trips faithfully. Any other user tag is recorded as a static parameter with a warning, because the LUML store has no place to keep an arbitrary tag value as a tag.

The `luml.*` prefix is reserved for the plugin's own bookkeeping (upload status, artifact ids, artifact links). Writing a `luml.*` tag from training code is rejected through the same path as other unsupported operations.

## Configuration

Configuration is read from environment variables, or from a `.env` file in the working directory. The defaults work for a standard LUML account.

| Variable                          | Default                    | Purpose                                                                                 |
| --------------------------------- | -------------------------- | --------------------------------------------------------------------------------------- |
| `LUML_API_KEY`                    | —                          | API key for uploads. Falls back to `~/.luml.json`, then the system keyring.              |
| `LUML_BASE_URL`                   | `https://api.luml.ai`      | LUML API endpoint.                                                                       |
| `LUML_WEB_URL`                    | `https://app.luml.ai`      | Base of the artifact links recorded on each run.                                        |
| `LUML_BACKEND_STORE_URI`          | `~/.luml/experiments`      | Local SQLite directory where runs are staged before upload.                             |
| `LUML_MLFLOW_AUTOSYNC`            | `true`                     | Upload a run to its orbit when it reaches a terminal status.                             |
| `LUML_MLFLOW_UPLOAD_MODE`         | `auto`                     | `auto` embeds a lone model in the experiment snapshot; `separate` uploads each model on its own. |
| `LUML_MLFLOW_COLLECTION_CONFLICT` | `raise`                    | What to do when a non-`mixed` collection already owns the experiment name. `suffix` creates a renamed `mixed` collection instead. |
| `LUML_MLFLOW_ON_UNSUPPORTED`      | `warn`                     | `warn` logs and continues on unsupported operations; `raise` turns them into errors.    |

## Limitations

Some MLflow operations have no LUML equivalent. By default they log a warning and continue; setting `LUML_MLFLOW_ON_UNSUPPORTED=raise` turns them into errors instead. This applies to deleting, restoring, and renaming experiments, restoring runs, logging dataset inputs, and linking traces to a run after the fact.

LUML has a [Registry](../../documentation/Modules/Registry/registry.md), but it is organized around collections of artifacts rather than MLflow's registered models and their versions. The plugin does not bridge the two models, so the registry pages in the MLflow UI render empty rather than erroring. A run's model is published into the LUML Registry as an artifact in the orbit collection, not as an MLflow registered-model version.

GenAI tracing is supported only while a run is active. MLflow allows a trace to exist without a run, but a LUML span needs an owning experiment, which here is the run. Spans logged with no active run are dropped through the unsupported path rather than persisted without a home.
