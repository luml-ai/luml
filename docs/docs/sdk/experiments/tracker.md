<a id="luml.experiments.tracker"></a>

# luml.experiments.tracker

<a id="luml.experiments.tracker.ExperimentTracker"></a>

## ExperimentTracker Objects

```python
class ExperimentTracker()
```

Local experiment tracking for ML experiments.

Tracks metrics, parameters, artifacts, and traces for machine learning experiments.
Supports multiple backend storage options via connection strings.

**Arguments**:

- `connection_string` - Backend connection string. Format: 'backend://config'.
  Default is 'sqlite://./experiments' for local SQLite storage.
  

**Example**:

```python
tracker = ExperimentTracker("sqlite://./my_experiments")
exp_id = tracker.start_experiment(name="my_experiment", tags=["baseline"])
tracker.log_static("learning_rate", 0.001, experiment_id=exp_id)
tracker.log_dynamic("loss", 0.5, step=1, experiment_id=exp_id)
tracker.end_experiment(exp_id)
```

<a id="luml.experiments.tracker.ExperimentTracker.start_experiment"></a>

#### start_experiment

```python
def start_experiment(experiment_id: str | None = None,
                     name: str | None = None,
                     group: str | None = None,
                     tags: list[str] | None = None) -> str
```

Start a new experiment tracking session.

**Arguments**:

- `experiment_id` - Unique experiment ID. Auto-generated if not provided.
- `name` - Human-readable experiment name.
- `group` - Group name to organize related experiments.
- `tags` - List of tags for categorizing the experiment.
  

**Returns**:

- `str` - The experiment ID.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment(
    name="baseline_model",
    group="image_classification",
    tags=["resnet", "baseline"]
)
```

<a id="luml.experiments.tracker.ExperimentTracker.end_experiment"></a>

#### end_experiment

```python
def end_experiment(experiment_id: str | None = None) -> None
```

End an active experiment tracking session.

**Arguments**:

- `experiment_id` - ID of experiment to end. Uses current experiment if not specified.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment(name="my_exp")
tracker.end_experiment(exp_id)
```

<a id="luml.experiments.tracker.ExperimentTracker.log_static"></a>

#### log_static

```python
def log_static(key: str, value: Any, experiment_id: str | None = None) -> None
```

Log static parameters or metadata (values that don't change during training).

**Arguments**:

- `key` - Parameter name.
- `value` - Parameter value (can be any serializable type).
- `experiment_id` - Experiment ID. Uses current experiment if not specified.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
tracker.log_static("learning_rate", 0.001)
tracker.log_static("model_architecture", "resnet50")
tracker.log_static("batch_size", 32)
```

<a id="luml.experiments.tracker.ExperimentTracker.log_dynamic"></a>

#### log_dynamic

```python
def log_dynamic(key: str,
                value: int | float,
                step: int | None = None,
                experiment_id: str | None = None) -> None
```

Log time-series metrics (values that change during training).

**Arguments**:

- `key` - Metric name.
- `value` - Metric value (numeric).
- `step` - Training step/epoch number.
- `experiment_id` - Experiment ID. Uses current experiment if not specified.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
for epoch in range(10):
    loss = train_epoch()
    tracker.log_dynamic("train_loss", loss, step=epoch)
```

<a id="luml.experiments.tracker.ExperimentTracker.log_attachment"></a>

#### log_attachment

```python
def log_attachment(name: str,
                   data: Any,
                   binary: bool = False,
                   experiment_id: str | None = None) -> None
```

Log files or artifacts to the experiment.

**Arguments**:

- `name` - Attachment name/filename.
- `data` - Data to attach (string, bytes, or file path).
- `binary` - Whether data is binary. Default is False.
- `experiment_id` - Experiment ID. Uses current experiment if not specified.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
tracker.log_attachment("model_config.json", config_json)
tracker.log_attachment("plot.png", image_bytes, binary=True)
```

<a id="luml.experiments.tracker.ExperimentTracker.list_experiments"></a>

#### list_experiments

```python
def list_experiments() -> list[dict[str, Any]]
```

List all experiments in the backend.

**Returns**:

  List of experiment dictionaries with metadata.
  

**Example**:

```python
tracker = ExperimentTracker()
experiments = tracker.list_experiments()
for exp in experiments:
    print(f"{exp['id']}: {exp['name']}")
```

<a id="luml.experiments.tracker.ExperimentTracker.link_to_model"></a>

#### link_to_model

```python
def link_to_model(model_reference: ModelReference,
                  experiment_id: str | None = None) -> None
```

Link experiment data to a saved model.

Attaches experiment tracking data (metrics, parameters, artifacts) to a model
for reproducibility and model versioning.

**Arguments**:

- `model_reference` - ModelReference object to link to.
- `experiment_id` - Experiment ID. Uses current experiment if not specified.
  

**Example**:

```python
from luml.integrations.sklearn import save_sklearn

tracker = ExperimentTracker()
exp_id = tracker.start_experiment(name="sklearn_model")
tracker.log_static("model_type", "RandomForest")

model_ref = save_sklearn(model, X_train)
tracker.link_to_model(model_ref)
```

<a id="luml.experiments.tracker.ExperimentTracker.enable_tracing"></a>

#### enable_tracing

```python
def enable_tracing() -> None
```

Enable OpenTelemetry tracing for the experiment.

Sets up automatic tracing of function calls and links traces to the experiment.
Useful for tracking execution flow in ML pipelines.

**Example**:

```python
tracker = ExperimentTracker()
tracker.enable_tracing()
exp_id = tracker.start_experiment()
# All traced functions will be logged to this experiment
```

