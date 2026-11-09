# Experiment tracking

```python
from luml.experiments.tracker import ExperimentTracker
```

## The store

```python
tracker = ExperimentTracker()                               # sqlite://./experiments
tracker = ExperimentTracker("sqlite://./tracking/experiments")  # explicit location
```

The connection string is `backend://config`. Only the SQLite backend exists.
Scripts that use the same path share one store. Flow reads
`~/.luml/experiments` by default, so open a project's store with
`lumlflow ui --path ./experiments`. The path is not expanded: write `~` out as
the full home directory.

Use the tracker as a context manager. On exit it ends the current
experiment, or marks it failed when the block raised.

## Experiments

```python
experiment_id = tracker.start_experiment(
    name="gbm-baseline",   # default: a generated adjective-noun-### name
    group="churn",         # created when missing; default "default"
    tags=["baseline"],
)
tracker.end_experiment()
tracker.fail_experiment()
```

- Every logging call targets the experiment started last
  (`tracker.current_experiment_id`). Pass `experiment_id=` to target another.
- Logging with no active experiment raises `ValueError`.
- The path of the `__main__` script is recorded as the experiment's source.

## Parameters, metrics and files

```python
tracker.log_static("learning_rate", 0.05)          # any JSON-serializable value
tracker.log_static("config", {"depth": 6, "loss": "logloss"})
tracker.log_dynamic("val_loss", 0.41, step=epoch)  # int or float only
tracker.log_attachment("report.md", markdown_text)
tracker.log_attachment("plots/roc.png", png_bytes, binary=True)
```

- `log_static`: values fixed for the experiment, such as hyperparameters, the dataset
  name, the git commit, final test metrics.
- `log_dynamic`: a value over training steps. It is drawn as a line chart
  against `step`. It is not for per-sample or per-rubric scores; log those as
  eval samples ([evals-tracing.md](evals-tracing.md)).
- `log_attachment` takes the content, not a path: a `str` (text) or `bytes`
  with `binary=True`. To attach a file, read it first:
  `tracker.log_attachment("plot.png", Path("plot.png").read_bytes(), binary=True)`.
  A name with `/` creates folders. Absolute paths and `..` are rejected.

Save a matplotlib figure as an attachment:

```python
import io

buffer = io.BytesIO()
figure.savefig(buffer, format="png")
tracker.log_attachment("confusion_matrix.png", buffer.getvalue(), binary=True)
```

## Models

```python
model_ref = tracker.log_model(
    model,                      # a trained model, or a ModelReference you saved
    name="gbm",
    inputs=X_train,             # sample inputs; required for sklearn
    tags=["candidate"],
    description="GBM on 90 days of events",
)
```

- The flavor (`sklearn`, `xgboost`, `lightgbm`, `catboost`, `langgraph`) is
  detected from the model's module. Pass `flavor=` when detection fails.
- The packaging arguments (`dependencies`, `extra_dependencies`,
  `extra_code_modules`, `manifest_*`) and any extra keyword arguments are passed
  to the flavor's `save_*` function ([packaging.md](packaging.md)).
- For a custom model, save it yourself and pass the `ModelReference`:
  `tracker.log_model(save_my_model(...), name="ranker")`.
- The returned `ModelReference` points at the copy inside the store. Do not
  modify that file: no `link_to_model`, no `add_model_card`. Add cards and
  profiles before logging.

```python
tracker.get_models(experiment_id)         # list[Model] with id, name, path
tracker.get_model(model_id)
tracker.update_model(model_id, name=None, tags=None, description=None)
tracker.link_to_model(model_ref)          # only for a model at a path you chose
```

## Experiment groups

```python
tracker.create_group("churn", description="Churn models", tags=["q4"])
tracker.list_groups()
tracker.get_group(group_id)
tracker.update_group(group_id, name=None, description=None, tags=None)
tracker.delete_group(group_id)
```

## Reading experiments back

Query the store to compare experiments or find the best one, instead of reading logs.

```python
tracker.list_experiments()                          # list[Experiment]
tracker.get_experiment(experiment_id)               # full record with params and metrics
tracker.get_experiment_record(experiment_id)        # metadata only
tracker.get_experiment_metric_history(experiment_id, "val_loss")
tracker.list_attachments(experiment_id)
tracker.get_attachment("report.md", experiment_id)  # bytes
tracker.update_experiment(experiment_id, name=None, description=None, tags=None)
tracker.delete_experiment(experiment_id)
```

For large stores there are paginated listings:
`list_group_experiments_pagination(group_id, limit=20, cursor_str=None,
sort_by="created_at", order="desc", search=None, json_sort_column=None)`.
Pass the previous response's cursor as `cursor_str`.

## Exporting an experiment

```python
from luml import save_experiment

experiment_ref = save_experiment(tracker, experiment_id, output_path="experiment.luml")
# or: tracker.export("experiment.luml", experiment_id=experiment_id)
```

This makes a standalone experiment artifact with all records and
attachments. Upload it on its own when an experiment has no model, or several
models ([upload.md](upload.md)).
