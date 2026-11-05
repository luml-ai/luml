# Flow SDK — experiment tracking

`from luml.experiments.tracker import ExperimentTracker`

## Constructing

```python
tracker = ExperimentTracker()                              # sqlite://./experiments
tracker = ExperimentTracker("sqlite://./my_experiments")   # explicit path
```

The connection string is `backend://config`; a missing `://` raises `ValueError`.
Only the SQLite backend ships today. Point several scripts at the same path to
have them share one store and one dashboard.

Use it as a context manager. On exit it ends the current experiment, or fails it
when the block raised. An `atexit` hook fails a still-running experiment if the
process dies without either.

## Experiment lifecycle

```python
start_experiment(name=None, group="default", experiment_id=None, tags=None) -> str
end_experiment(experiment_id=None) -> None
fail_experiment(experiment_id=None) -> None
```

- `name` defaults to a generated `adjective-noun-###`.
- `experiment_id` defaults to a fresh UUID; pass one to resume or to control the id.
- The group is created implicitly if it does not exist.
- Every later call defaults to the experiment started last (`tracker.current_experiment_id`);
  pass `experiment_id=` to target another one.
- The path of the `__main__` script is recorded automatically as the run's source.

## Logging

```python
log_static(key, value, experiment_id=None)             # any serializable value
log_dynamic(key, value: int | float, step=None, experiment_id=None)
log_attachment(name, data, binary=False, experiment_id=None)
```

`log_static` is for values fixed for the run — hyperparameters, dataset name, git
sha, config dicts. `log_dynamic` is for series; it takes numbers only and the
dashboard plots them against `step`.

`log_attachment` takes a string, bytes, or a file path; set `binary=True` for
bytes. Use it for plots, configs, confusion matrices, prediction dumps.

Logging without an active experiment raises `ValueError: No active experiment.`

## Models

```python
log_model(
    model,                    # raw model object, or an already-saved ModelReference
    *,
    name=None, tags=None, description=None,
    flavor=None,              # auto-detected from the model's module
    inputs=None,              # sample inputs for signature inference
    experiment_id=None,
    dependencies="default",   # "default" | "all" | ["pkg", ...]
    extra_dependencies=None,
    extra_code_modules=None,  # list[str] | "auto"
    manifest_model_name=None, manifest_model_version=None,
    manifest_model_description=None, manifest_extra_producer_tags=None,
    **save_kwargs,
) -> ModelReference
```

Supported flavors: `sklearn`, `xgboost`, `lightgbm`, `catboost`, `langgraph`.
The flavor is detected from the model's top-level module; pass `flavor=` when
the object comes from a wrapper. `inputs` is **required for sklearn**, optional
for xgboost/lightgbm, unused by catboost and langgraph. Auto-detection failure
raises `ValueError` — name the flavor explicitly.

`dependencies="all"` freezes the full environment; a list pins exactly those
packages. Use it when the default capture misses an import the model needs at
load time.

Related:

```python
link_to_model(model_reference, experiment_id=None)   # attach an externally saved model
get_models(experiment_id=None) -> list[Model]
get_model(model_id) -> Model
get_model_card(model_id) -> bytes                    # the model card zip
update_model(model_id, name=None, tags=None, description=None) -> Model | None
```

## Reading experiments back

Use these when the task is "compare runs", "find the best run", "summarize what
was tried" — query the store instead of re-reading logs.

```python
list_experiments() -> list[Experiment]
get_experiment(experiment_id) -> ExperimentData | None      # full record
get_experiment_record(experiment_id) -> Experiment | None   # metadata only
get_experiment_metric_history(experiment_id, key) -> list[dict]
update_experiment(experiment_id, name=None, description=None, tags=None)
delete_experiment(experiment_id) -> None

list_attachments(experiment_id=None) -> list[AttachmentRecord]
list_attachments_tree(...) -> FileNode
get_attachment(name, experiment_id=None) -> bytes

get_experiment_metadata(experiment_id) -> dict
set_experiment_metadata(...) / update_experiment_metadata(...)
```

## Groups

```python
create_group(name, description=None, tags=None) -> Group
list_groups() -> list[Group]
get_group(group_id) -> Group | None
update_group(...) / delete_group(group_id)
```

Paginated listings, for dashboards or large stores:

```python
list_groups_pagination(...)                    -> PaginatedResponse[Group]
list_group_experiments_pagination(
    group_id, limit=20, cursor_str=None, sort_by="created_at",
    order="desc", search=None, json_sort_column=None,
) -> PaginatedResponse[Experiment]
list_groups_experiments_pagination(...)
get_group_experiments_static_params_keys(group_id)  -> list[str]
get_group_experiments_dynamic_metrics_keys(group_id) -> list[str]
```

`PaginatedResponse` is cursor-based: pass the previous response's cursor back as
`cursor_str`. `json_sort_column` is `"static_params"` or `"dynamic_params"` when
`sort_by` names a logged key rather than a column.

Source of truth: `sdk/python/sdk/luml/experiments/tracker.py`.
