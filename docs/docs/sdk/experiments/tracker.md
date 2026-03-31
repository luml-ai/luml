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
exp_id = tracker.start_experiment(
    name="my_experiment", group="my_group", tags=["baseline"]
)
tracker.log_static("learning_rate", 0.001)
tracker.log_dynamic("loss", 0.5, step=1)
tracker.end_experiment(exp_id)
```

<a id="luml.experiments.tracker.ExperimentTracker.start_experiment"></a>

#### start\_experiment

```python
def start_experiment(
    name: str | None = None,
    group: str = "default",
    experiment_id: str | None = None,
    tags: list[str] | None = None
) -> str
```

Starts a new experiment by initializing it with the backend and setting
the experiment's metadata.

**Arguments**:

- `name` _str | None_ - The name of the experiment. If not provided,
  the experiment will be initialized without a specific name
- `group` _str_ - The group to which the experiment belongs. Defaults to
  "default".
- `experiment_id` _str | None_ - A unique identifier for the experiment. If not
  provided, a new UUID will be generated as the experiment ID.
- `tags` _list[str] | None_ - A list of tags to associate with the experiment.
  Can be None if no tags are necessary.
  

**Returns**:

- `str` - The experiment ID.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment(
    "image_classification",
    name="baseline_model",
    tags=["resnet", "baseline"]
)
```

<a id="luml.experiments.tracker.ExperimentTracker.end_experiment"></a>

#### end\_experiment

```python
def end_experiment(experiment_id: str | None = None) -> None
```

End an active experiment tracking session.

**Arguments**:

- `experiment_id` - ID of experiment to end.
  Uses current experiment if not specified.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment(name="my_exp")
tracker.end_experiment(exp_id)
```

<a id="luml.experiments.tracker.ExperimentTracker.fail_experiment"></a>

#### fail\_experiment

```python
def fail_experiment(experiment_id: str | None = None) -> None
```

Mark an experiment as failed due to an error or interruption.

<a id="luml.experiments.tracker.ExperimentTracker.log_static"></a>

#### log\_static

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

#### log\_dynamic

```python
def log_dynamic(
    key: str,
    value: int | float,
    step: int | None = None,
    experiment_id: str | None = None
) -> None
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

<a id="luml.experiments.tracker.ExperimentTracker.log_span"></a>

#### log\_span

```python
def log_span(
    trace_id: str,
    span_id: str,
    name: str,
    start_time_unix_nano: int,
    end_time_unix_nano: int,
    parent_span_id: str | None = None,
    kind: int = 0,
    status_code: int = 0,
    status_message: str | None = None,
    attributes: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    links: list[dict[str, Any]] | None = None,
    trace_flags: int = 0,
    experiment_id: str | None = None
) -> None
```

Log an OpenTelemetry-compatible span to the experiment.

Records a single span representing a unit of work within a trace.
Spans can be nested via ``parent_span_id`` to form a trace tree.

**Arguments**:

- `trace_id` _str_ - Unique identifier for the trace this span belongs to.
- `span_id` _str_ - Unique identifier for this span.
- `name` _str_ - Human-readable name describing the operation.
- `start_time_unix_nano` _int_ - Span start time in nanoseconds since Unix epoch.
- `end_time_unix_nano` _int_ - Span end time in nanoseconds since Unix epoch.
- `parent_span_id` _str | None_ - Span ID of the parent span, or ``None`` for
  root spans.
- `kind` _int_ - Span kind following the OpenTelemetry spec (0=INTERNAL,
  1=SERVER, 2=CLIENT, 3=PRODUCER, 4=CONSUMER). Defaults to 0.
- `status_code` _int_ - Status code (0=UNSET, 1=OK, 2=ERROR). Defaults to 0.
- `status_message` _str | None_ - Optional status description, typically set
  for error spans.
- `attributes` _dict[str, Any] | None_ - Key-value pairs of span attributes.
- `events` _list[dict[str, Any]] | None_ - Timestamped event records attached
  to the span.
- `links` _list[dict[str, Any]] | None_ - Links to other spans, each containing
  at minimum ``trace_id`` and ``span_id`` keys.
- `trace_flags` _int_ - W3C trace flags. Defaults to 0.
- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if
  not specified.
  

**Raises**:

- `ValueError` - If no experiment is active and ``experiment_id`` is not provided.
  

**Example**:

```python
import time

tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
start = time.time_ns()
# ... do work ...
end = time.time_ns()
tracker.log_span(
    trace_id="abc123",
    span_id="span_1",
    name="data_preprocessing",
    start_time_unix_nano=start,
    end_time_unix_nano=end,
    attributes={"input_rows": 1000},
)
```

<a id="luml.experiments.tracker.ExperimentTracker.log_eval_sample"></a>

#### log\_eval\_sample

```python
def log_eval_sample(
    eval_id: str,
    dataset_id: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any] | None = None,
    references: dict[str, Any] | None = None,
    scores: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    experiment_id: str | None = None
) -> None
```

Log a single evaluation sample to the experiment.

Records one data point from a model evaluation run, including its inputs,
model outputs, ground-truth references, computed scores, and optional metadata.

**Arguments**:

- `eval_id` _str_ - Unique identifier for this evaluation sample.
- `dataset_id` _str_ - Identifier of the evaluation dataset this sample
  belongs to.
- `inputs` _dict[str, Any]_ - Input data fed to the model for this sample.
- `outputs` _dict[str, Any] | None_ - Model outputs/predictions for this sample.
- `references` _dict[str, Any] | None_ - Ground-truth or reference values to
  compare against.
- `scores` _dict[str, Any] | None_ - Computed evaluation scores (e.g. accuracy,
  F1, BLEU).
- `metadata` _dict[str, Any] | None_ - Additional metadata for the sample (e.g.
  latency, token counts).
- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if
  not specified.
  

**Raises**:

- `ValueError` - If no experiment is active and ``experiment_id`` is not provided.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
tracker.log_eval_sample(
    eval_id="sample_001",
    dataset_id="test_set_v2",
    inputs={"prompt": "Summarize this text..."},
    outputs={"response": "The text discusses..."},
    references={"expected": "A summary of..."},
    scores={"bleu": 0.72, "rouge_l": 0.65},
)
```

<a id="luml.experiments.tracker.ExperimentTracker.link_eval_sample_to_trace"></a>

#### link\_eval\_sample\_to\_trace

```python
def link_eval_sample_to_trace(
    eval_dataset_id: str,
    eval_id: str,
    trace_id: str,
    experiment_id: str | None = None
) -> None
```

Link an evaluation sample to a trace.

Associates a previously logged evaluation sample with an execution trace,
enabling correlation between evaluation results and the traced execution
that produced them.

**Arguments**:

- `eval_dataset_id` _str_ - Identifier of the evaluation dataset the sample
  belongs to.
- `eval_id` _str_ - Identifier of the evaluation sample to link.
- `trace_id` _str_ - Identifier of the trace to link to.
- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if
  not specified.
  

**Raises**:

- `ValueError` - If no experiment is active and ``experiment_id`` is not provided.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
tracker.log_eval_sample(
    eval_id="sample_001",
    dataset_id="test_set_v2",
    inputs={"prompt": "Hello"},
)
tracker.link_eval_sample_to_trace(
    eval_dataset_id="test_set_v2",
    eval_id="sample_001",
    trace_id="trace_abc",
)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_evals_annotation_summaries"></a>

#### get\_evals\_annotation\_summaries

```python
def get_evals_annotation_summaries(
    experiment_id: str,
    eval_ids: list[str]
) -> dict[str, AnnotationSummary]
```

Retrieves annotation summaries for a batch of evaluations within an experiment.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment.
- `eval_ids` _list[str]_ - A list of evaluation IDs to retrieve summaries for.
  

**Returns**:

  dict[str, AnnotationSummary]: A dictionary mapping each eval ID to its annotation
  summary. Eval IDs with no annotations are excluded from the result.
  

**Example**:
```python
  tracker = ExperimentTracker()
  tracker.get_evals_annotation_summaries("exp-001", ["eval-xyz", "eval-abc"])
  
  result = {
    "eval-xyz": AnnotationSummary(
        feedback=[
          FeedbackSummaryItem(
            name="quality", 
            total=2, 
            counts={"true": 1, "false": 1}
          )
        ],
        expectations=[]
    )
  }
```
<a id="luml.experiments.tracker.ExperimentTracker.log_attachment"></a>

#### log\_attachment

```python
def log_attachment(
    name: str,
    data: Any,
    binary: bool = False,
    experiment_id: str | None = None
) -> None
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

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment"></a>

#### get\_experiment

```python
def get_experiment(experiment_id: str) -> ExperimentData
```

Retrieve full experiment data by ID.

Returns the complete experiment record including metadata, static parameters,
dynamic metrics, and attachment information.

**Arguments**:

- `experiment_id` _str_ - Unique identifier of the experiment to retrieve.
  

**Returns**:

- `ExperimentData` - Complete experiment data containing ``experiment_id``, ``metadata``, ``static_params``, ``dynamic_metrics``, and ``attachments``.
  

**Example**:

```python
tracker = ExperimentTracker()
data = tracker.get_experiment("my-experiment-id")

print(data.metadata.name)
print(data.static_params)
print(data.dynamic_metrics)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_attachment"></a>

#### get\_attachment

```python
def get_attachment(name: str, experiment_id: str | None = None) -> Any
```

Retrieve a previously logged attachment by name.

**Arguments**:

- `name` _str_ - Name of the attachment as specified during :meth:`log_attachment`.
- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if not specified.
  

**Returns**:

- `Any` - The attachment data as bytes.
  

**Raises**:

- `ValueError` - If no experiment is active and ``experiment_id`` is not provided.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
tracker.log_attachment("config.json", '{"lr": 0.001}')
config = tracker.get_attachment("config.json")
```

<a id="luml.experiments.tracker.ExperimentTracker.list_attachments"></a>

#### list\_attachments

```python
def list_attachments(experiment_id: str | None = None) -> list[AttachmentRecord]
```

List all attachments logged for an experiment.

**Arguments**:

- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if not specified.
  

**Returns**:

- `list[AttachmentRecord]` - List of attachment records with ``name``, ``file_path`` and ``created_at`` fields.
  

**Raises**:

- `ValueError` - If no experiment is active and ``experiment_id`` is not provided.

<a id="luml.experiments.tracker.ExperimentTracker.list_experiments"></a>

#### list\_experiments

```python
def list_experiments() -> list[Experiment]
```

List all experiments in the backend.

**Returns**:

  List of Experiment objects with metadata.
  

**Example**:

```python
tracker = ExperimentTracker()
experiments = tracker.list_experiments()

for exp in experiments:
    print(f"{exp.id}: {exp.name}")
```

<a id="luml.experiments.tracker.ExperimentTracker.delete_experiment"></a>

#### delete\_experiment

```python
def delete_experiment(experiment_id: str) -> None
```

Delete an experiment and all its associated data.

Permanently removes the experiment record along with its static parameters,
dynamic metrics, spans, evaluation samples, attachments, and models from
the backend.

**Arguments**:

- `experiment_id` _str_ - Unique identifier of the experiment to delete.
  

**Example**:

```python
tracker = ExperimentTracker()
tracker.delete_experiment("old-experiment-id")
```

<a id="luml.experiments.tracker.ExperimentTracker.create_group"></a>

#### create\_group

```python
def create_group(
    name: str,
    description: str | None = None,
    tags: list[str] | None = None
) -> Group
```

Create a new experiment group.

Groups organize related experiments (e.g. by project, task, or hypothesis).
Experiments are assigned to a group via the ``group`` parameter of
:meth:`start_experiment`.

**Arguments**:

- `name` _str_ - Unique name for the group.
- `description` _str | None_ - Optional human-readable description of the group's purpose.
- `tags` _list[str] | None_ - Optional tags to associate with the group.
  

**Returns**:

- `Group` - The created group with ``id``, ``name``, ``description``,
  ``created_at``, and ``tags`` fields.
  

**Example**:

```python
tracker = ExperimentTracker()
group = tracker.create_group(
    "hyperparameter_search",
    description="LR sweep experiments",
    tags=["production", "v2"],
)
exp_id = tracker.start_experiment(group=group.name)
```

<a id="luml.experiments.tracker.ExperimentTracker.list_groups"></a>

#### list\_groups

```python
def list_groups() -> list[Group]
```

List all experiment groups in the backend.

**Returns**:

- `list[Group]` - List of Group objects, each containing ``id``, ``name``, ``description``, and ``created_at`` fields.
  

**Example**:

```python
tracker = ExperimentTracker()
groups = tracker.list_groups()
for group in groups:
    print(f"{group.name}: {group.description}")
```

<a id="luml.experiments.tracker.ExperimentTracker.log_model"></a>

#### log\_model

```python
def log_model(
    model: ModelReference | Any,
    *,
    name: str | None = None,
    tags: list[str] | None = None,
    flavor: str | None = None,
    inputs: Any = None,
    experiment_id: str | None = None,
    dependencies: Literal["default", "all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
    **save_kwargs: Any
) -> ModelReference
```

Log a model to the experiment.

Accepts either a pre-saved ``ModelReference`` or a raw model object. When a
raw model is provided, it is serialized automatically using the detected or
explicitly specified flavor. The serialized artifact is stored in the backend
and the temporary file is cleaned up.

**Arguments**:

- `model` _ModelReference | Any_ - A ``ModelReference`` pointing to an already-saved model, or a raw model object to be serialized.
- `name` _str | None_ - Optional display name for the model.
- `tags` _list[str] | None_ - Optional tags to associate with the model.
- `flavor` _str | None_ - Serialization flavor (e.g. ``"sklearn"``, ``"xgboost"``). Auto-detected from the model's module if not provided. Supported flavors: sklearn, xgboost, lightgbm, catboost, langgraph.
- `inputs` _Any_ - Sample input data used for model signature inference. Required by ``sklearn``, optional for ``xgboost`` and ``lightgbm``, and not used by ``catboost`` or ``langgraph``.
- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if not specified.
- `dependencies` _Literal["default", "all"] | list[str]_ - Dependency capture strategy. ``"default"`` captures direct dependencies, ``"all"``captures the full environment, or pass an explicit list of package names.
- `extra_dependencies` _list[str] | None_ - Additional package dependencies to include beyond those captured by ``dependencies``.
- `extra_code_modules` _list[str] | Literal["auto"] | None_ - Extra Python modules to bundle with the model. ``"auto"`` attempts automatic  detection.
- `manifest_model_name` _str | None_ - Model name for the artifact manifest.
- `manifest_model_version` _str | None_ - Model version for the artifact manifest.
- `manifest_model_description` _str | None_ - Model description for the artifact manifest.
- `manifest_extra_producer_tags` _list[str] | None_ - Additional producer tags for the artifact manifest.
- `**save_kwargs` _Any_ - Additional keyword arguments forwarded to the flavor-specific save function.
  

**Returns**:

- `ModelReference` - Reference to the stored model in the backend.
  

**Raises**:

- `ValueError` - If no experiment is active and ``experiment_id`` is not
  provided, or if the flavor cannot be auto-detected.
  

**Example**:

```python
from sklearn.ensemble import RandomForestClassifier

tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
model = RandomForestClassifier().fit(X_train, y_train)
model_ref = tracker.log_model(model, name="rf_v1", inputs=X_train)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_models"></a>

#### get\_models

```python
def get_models(experiment_id: str | None = None) -> list[Model]
```

List all models logged to an experiment.

**Arguments**:

- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if
  not specified.
  

**Returns**:

- `list[Model]` - List of Model objects, each containing ``id``, ``name``, ``created_at``, ``tags``, ``path``, and ``experiment_id`` fields.
  

**Raises**:

- `ValueError` - If no experiment is active and ``experiment_id`` is not provided.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
tracker.log_model(model, name="rf_v1", inputs=X_train)
models = tracker.get_models()

for m in models:
    print(f"{m.name} logged at {m.created_at}")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_model"></a>

#### get\_model

```python
def get_model(model_id: str) -> Model
```

Retrieve a single model by its ID.

**Arguments**:

- `model_id` _str_ - Unique identifier of the model to retrieve.
  

**Returns**:

- `Model` - The model record containing ``id``, ``name``, ``created_at``, ``tags``, ``path``, and ``experiment_id`` fields.
  

**Example**:

```python
tracker = ExperimentTracker()
model = tracker.get_model("model-uuid-123")
print(f"{model.name}: {model.path}")
```

<a id="luml.experiments.tracker.ExperimentTracker.link_to_model"></a>

#### link\_to\_model

```python
def link_to_model(
    model_reference: ModelReference,
    experiment_id: str | None = None
) -> None
```

Link experiment data to a saved model.

Attaches experiment tracking data (metrics, parameters, artifacts) to a model for reproducibility and model versioning.

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

<a id="luml.experiments.tracker.ExperimentTracker.log_eval_annotation"></a>

#### log\_eval\_annotation

```python
def log_eval_annotation(
    dataset_id: str,
    eval_id: str,
    name: str,
    annotation_kind: str,
    value_type: str,
    value: int | bool | str,
    user: str,
    rationale: str | None = None,
    experiment_id: str | None = None
) -> AnnotationRecord
```

Create an annotation on an eval sample.

Annotations categorize eval results with human feedback or expectations.
Feedback annotations must use ``value_type='bool'``.

**Arguments**:

- `dataset_id` _str_ - The dataset the eval belongs to.
- `eval_id` _str_ - The eval sample to annotate.
- `name` _str_ - Annotation name used for grouping (e.g. "accuracy", "relevance").
- `annotation_kind` _str_ - Either ``'feedback'`` or ``'expectation'``.
- `value_type` _str_ - Type of the value: ``'bool'``, ``'int'``, or ``'string'``.
- `value` _int | bool | str_ - The annotation value.
- `user` _str_ - The user who created the annotation.
- `rationale` _str | None_ - Optional free-text explanation for the annotation.
- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if not specified.
  

**Returns**:

- `AnnotationRecord` - The created annotation record.
  

**Raises**:

- `ValueError` - If no experiment is active, the experiment uses an older schema without annotation support, or a feedback annotation uses a non-bool ``value_type``.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
tracker.log_eval_sample(
    eval_id="eval-1", dataset_id="ds-1",
    inputs={"prompt": "What is 2+2?"},
    outputs={"response": "4"},
)
annotation = tracker.log_eval_annotation(
    dataset_id="ds-1",
    eval_id="eval-1",
    name="accuracy",
    annotation_kind="feedback",
    value_type="bool",
    value=True,
    user="alice",
    rationale="The answer is correct",
)
```

<a id="luml.experiments.tracker.ExperimentTracker.log_span_annotation"></a>

#### log\_span\_annotation

```python
def log_span_annotation(
    trace_id: str,
    span_id: str,
    name: str,
    annotation_kind: str,
    value_type: str,
    value: int | bool | str,
    user: str,
    rationale: str | None = None,
    experiment_id: str | None = None
) -> AnnotationRecord
```

Create an annotation on a span within a trace.

Annotations attach human feedback or expectations to individual spans.
Feedback annotations must use ``value_type='bool'``.

**Arguments**:

- `trace_id` _str_ - The trace containing the span.
- `span_id` _str_ - The span to annotate.
- `name` _str_ - Annotation name used for grouping (e.g. "quality", "latency").
- `annotation_kind` _str_ - Either ``'feedback'`` or ``'expectation'``.
- `value_type` _str_ - Type of the value: ``'bool'``, ``'int'``, or ``'string'``.
- `value` _int | bool | str_ - The annotation value.
- `user` _str_ - The user who created the annotation.
- `rationale` _str | None_ - Optional free-text explanation for the annotation.
- `experiment_id` _str | None_ - Experiment ID. Uses current experiment if not specified.
  

**Returns**:

- `AnnotationRecord` - The created annotation record.
  

**Raises**:

- `ValueError` - If no experiment is active, the experiment uses an older schema without annotation support, or a feedback annotation uses a non-bool ``value_type``.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
annotation = tracker.log_span_annotation(
    trace_id="trace-abc",
    span_id="span-1",
    name="quality",
    annotation_kind="feedback",
    value_type="bool",
    value=True,
    user="alice",
    rationale="Output was relevant and well-structured",
)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_record"></a>

#### get\_experiment\_record

```python
def get_experiment_record(experiment_id: str) -> Experiment | None
```

Retrieve experiment metadata by ID.

**Arguments**:

- `experiment_id` _str_ - The experiment to look up.
  

**Returns**:

  Experiment | None: The experiment metadata, or ``None`` if not found.
  

**Example**:

```python
tracker = ExperimentTracker()
exp = tracker.get_experiment_record("my-experiment-id")

if exp:
    print(exp.name, exp.tags)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_trace"></a>

#### get\_trace

```python
def get_trace(experiment_id: str, trace_id: str) -> TraceDetails | None
```

Retrieve full trace details including all spans.

**Arguments**:

- `experiment_id` _str_ - The experiment containing the trace.
- `trace_id` _str_ - The trace to retrieve.
  

**Returns**:

  TraceDetails | None: Trace with its spans, or ``None`` if not found.
  

**Example**:

```python
tracker = ExperimentTracker()
trace = tracker.get_trace("exp-1", "trace-abc")

if trace:
    for span in trace.spans:
        print(span.name, span.annotation_count)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_traces"></a>

#### get\_experiment\_traces

```python
def get_experiment_traces(
    experiment_id: str,
    limit: int = 20,
    cursor_str: str | None = None,
    sort_by: str = "execution_time",
    order: str = "desc",
    search: str | None = None,
    filters: list[str] | None = None,
    states: list[TraceState] | None = None
) -> PaginatedResponse[TraceRecord]
```

Retrieve paginated traces for an experiment.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
- `limit` _int_ - Maximum number of traces per page (1–100). Defaults to 20.
- `cursor_str` _str | None_ - Pagination cursor from a previous response.
- `sort_by` _str_ - Sort field. Defaults to ``'execution_time'``.
- `order` _str_ - Sort order, ``'asc'`` or ``'desc'``. Defaults to ``'desc'``.
- `search` _str | None_ - Optional substring filter on trace ID.
- `states` _list[TraceState] | None_ - Optional filter by trace state.
  

**Returns**:

- `PaginatedResponse[TraceRecord]` - Page of traces with pagination cursor.
  

**Example**:

```python
tracker = ExperimentTracker()
page = tracker.get_experiment_traces("exp-1", limit=10)
for trace in page.items:
    print(trace.trace_id, trace.execution_time_ms)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_metric_history"></a>

#### get\_experiment\_metric\_history

```python
def get_experiment_metric_history(
    experiment_id: str,
    key: str
) -> list[dict[str, Any]]
```

Retrieve the full history of a dynamic metric.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
- `key` _str_ - The metric key (e.g. ``'train_loss'``).
  

**Returns**:

  list[dict[str, Any]]: List of ``{value, step, logged_at}`` entries
  ordered by step.
  

**Example**:

```python
tracker = ExperimentTracker()
history = tracker.get_experiment_metric_history("exp-1", "train_loss")

for point in history:
    print(f"step={point['step']} loss={point['value']}")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_evals"></a>

#### get\_experiment\_evals

```python
def get_experiment_evals(
    experiment_id: str,
    limit: int = 20,
    cursor_str: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    dataset_id: str | None = None,
    json_sort_column: str | None = None,
    search: str | None = None,
    filters: list[str] | None = None
) -> PaginatedResponse[EvalRecord]
```

Retrieve paginated eval samples for an experiment.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
- `limit` _int_ - Maximum number of evals per page (1–100). Defaults to 20.
- `cursor_str` _str | None_ - Pagination cursor from a previous response.
- `sort_by` _str_ - Sort field. Defaults to ``'created_at'``.
- `order` _str_ - Sort order, ``'asc'`` or ``'desc'``. Defaults to ``'desc'``.
- `dataset_id` _str | None_ - Optional filter by dataset.
- `json_sort_column` _str | None_ - Resolved JSON column for sorting by score / input / output keys.
- `search` _str | None_ - Optional substring filter on eval ID.
  

**Returns**:

- `PaginatedResponse[EvalRecord]` - Page of eval records with pagination cursor.
  

**Example**:

```python
tracker = ExperimentTracker()
page = tracker.get_experiment_evals("exp-1", dataset_id="ds-1")
for eval_rec in page.items:
    print(eval_rec.eval_id, eval_rec.scores)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_eval_columns"></a>

#### get\_experiment\_eval\_columns

```python
def get_experiment_eval_columns(
    experiment_id: str,
    dataset_id: str | None = None
) -> EvalColumns
```

Retrieve the set of available column keys across all evals in an experiment.

Returns the distinct keys found in scores, inputs, outputs, and refs fields, useful for building dynamic table headers.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
- `dataset_id` _str | None, optional_ - Dataset ID for filtering. If not provided, all datasets within the experiment are considered.
  

**Returns**:

- `EvalColumns` - Object containing lists of available column keys.
  

**Example**:

```python
tracker = ExperimentTracker()
columns = tracker.get_experiment_eval_columns("exp-1")
print("Score columns:", columns.scores)
print("Input columns:", columns.inputs)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_eval_typed_columns"></a>

#### get\_experiment\_eval\_typed\_columns

```python
def get_experiment_eval_typed_columns(
    experiment_id: str,
    dataset_id: str | None = None
) -> EvalTypedColumns
```

Like get_experiment_eval_columns but also returns the type for each key.

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_trace_columns"></a>

#### get\_experiment\_trace\_columns

```python
def get_experiment_trace_columns(experiment_id: str) -> TraceColumns
```

Return distinct attribute keys from all spans in an experiment.

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_trace_typed_columns"></a>

#### get\_experiment\_trace\_typed\_columns

```python
def get_experiment_trace_typed_columns(experiment_id: str) -> TraceTypedColumns
```

Like get_experiment_trace_columns but also returns the type for each key.

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_evals_average_scores"></a>

#### get\_experiment\_evals\_average\_scores

```python
def get_experiment_evals_average_scores(
    experiment_id: str,
    dataset_id: str | None = None
) -> dict[str, float]
```

Calculates the average scores for evaluations from a specified experiment and optionally filters them by a specific dataset.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment from which to fetch evaluation data.
- `dataset_id` _str | None, optional_ - The unique identifier of the dataset to filter evaluations. If not provided, all datasets within the experiment will be considered.
  

**Returns**:

  dict[str, float]: A dictionary where the keys are evaluation metric names and the values are their corresponding average scores.

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_eval_dataset_ids"></a>

#### get\_experiment\_eval\_dataset\_ids

```python
def get_experiment_eval_dataset_ids(experiment_id: str) -> list[str]
```

Retrieve all unique dataset IDs from evals of an experiment.

<a id="luml.experiments.tracker.ExperimentTracker.resolve_evals_sort_column"></a>

#### resolve\_evals\_sort\_column
```python
def resolve_evals_sort_column(self, experiment_id: str, sort_by: str) -> str | None:
```
**Arguments**:

- `experiment_id` _str_ - The experiment to query.
  

**Returns**:

- `list[str]` - Sorted list of distinct dataset IDs.

<a id="luml.experiments.tracker.ExperimentTracker.resolve_evals_sort_column"></a>

#### resolve\_evals\_sort\_column

```python
def resolve_evals_sort_column(experiment_id: str, sort_by: str) -> str | None
```

Resolve a sort key to the underlying JSON column expression for eval queries.

Used to translate user-facing sort keys (e.g. ``'scores.accuracy'``) into the SQL expression needed for sorting.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
- `sort_by` _str_ - The sort key to resolve.
  

**Returns**:

  str | None: The resolved SQL column expression, or ``None`` if invalid.
  

**Example**:

```python
tracker = ExperimentTracker()
col = tracker.resolve_evals_sort_column("exp-1", "scores.accuracy")
```

<a id="luml.experiments.tracker.ExperimentTracker.update_experiment"></a>

#### update\_experiment

```python
def update_experiment(
    experiment_id: str,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None
) -> Experiment | None
```

Update experiment metadata.

Only the provided fields are updated; ``None`` values are ignored.

**Arguments**:

- `experiment_id` _str_ - The experiment to update.
- `name` _str | None_ - New experiment name.
- `description` _str | None_ - New experiment description.
- `tags` _list[str] | None_ - New list of tags.
  

**Returns**:

  Experiment | None: The updated experiment, or ``None`` if not found.
  

**Example**:

```python
tracker = ExperimentTracker()

tracker.update_experiment(
    "exp-1",
    name="renamed_experiment",
    tags=["production", "v2"],
)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_eval_annotations"></a>

#### get\_eval\_annotations

```python
def get_eval_annotations(
    experiment_id: str,
    dataset_id: str,
    eval_id: str
) -> list[AnnotationRecord]
```

Retrieve all annotations for a specific eval sample.

Returns an empty list if the experiment DB uses an older schema without annotation support.

**Arguments**:

- `experiment_id` _str_ - The experiment containing the eval.
- `dataset_id` _str_ - The dataset the eval belongs to.
- `eval_id` _str_ - The eval sample to query.
  

**Returns**:

- `list[AnnotationRecord]` - Annotations ordered by creation time.
  

**Example**:

```python
tracker = ExperimentTracker()
annotations = tracker.get_eval_annotations("exp-1", "ds-1", "eval-1")
for ann in annotations:
    print(f"{ann.name}: {ann.value} by {ann.user}")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_span_annotations"></a>

#### get\_span\_annotations

```python
def get_span_annotations(
    experiment_id: str,
    trace_id: str,
    span_id: str
) -> list[AnnotationRecord]
```

Retrieve all annotations for a specific span.

Returns an empty list if the experiment DB uses an older schema without annotation support.

**Arguments**:

- `experiment_id` _str_ - The experiment containing the trace.
- `trace_id` _str_ - The trace containing the span.
- `span_id` _str_ - The span to query.
  

**Returns**:

- `list[AnnotationRecord]` - Annotations ordered by creation time.
  

**Example**:

```python
tracker = ExperimentTracker()
annotations = tracker.get_span_annotations("exp-1", "trace-abc", "span-1")
for ann in annotations:
    print(f"{ann.name}: {ann.value} by {ann.user}")
```

<a id="luml.experiments.tracker.ExperimentTracker.update_annotation"></a>

#### update\_annotation

```python
def update_annotation(
    experiment_id: str,
    annotation_id: str,
    target: Literal["eval", "span"],
    value: int | bool | str | None = None,
    rationale: str | None = None
) -> AnnotationRecord
```

Update an existing annotation's value and/or rationale.

At least one of ``value`` or ``rationale`` must be provided.

**Arguments**:

- `experiment_id` _str_ - The experiment containing the annotation.
- `annotation_id` _str_ - The annotation to update.
- `target` _Literal["eval", "span"]_ - Whether this is an eval or span
  annotation.
- `value` _int | bool | str | None_ - New annotation value. ``None`` to
  leave unchanged.
- `rationale` _str | None_ - New rationale text. ``None`` to leave unchanged.
  

**Returns**:

- `AnnotationRecord` - The updated annotation record.
  

**Raises**:

- `ValueError` - If no fields are provided to update, the annotation is not found, or the experiment uses an older schema.
  

**Example**:

```python
tracker = ExperimentTracker()
updated = tracker.update_annotation(
    "exp-1", "ann-uuid", "eval",
    value=False,
    rationale="Revised: answer was actually wrong",
)
```

<a id="luml.experiments.tracker.ExperimentTracker.delete_annotation"></a>

#### delete\_annotation

```python
def delete_annotation(
    experiment_id: str,
    annotation_id: str,
    target: Literal["eval", "span"]
) -> None
```

Delete an annotation by ID.

No-op if the experiment DB uses an older schema without annotation support.

**Arguments**:

- `experiment_id` _str_ - The experiment containing the annotation.
- `annotation_id` _str_ - The annotation to delete.
- `target` _Literal["eval", "span"]_ - Whether this is an eval or span annotation.
  

**Example**:

```python
tracker = ExperimentTracker()
tracker.delete_annotation("exp-1", "ann-uuid", "eval")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_eval_annotation_summary"></a>

#### get\_eval\_annotation\_summary

```python
def get_eval_annotation_summary(
    experiment_id: str,
    dataset_id: str
) -> AnnotationSummary
```

Get an aggregated summary of annotations across all evals in a dataset.

Returns feedback and expectation annotations grouped by annotation name.
Feedback items include a ``counts`` dict keyed by value (e.g. ``{"true": 3, "false": 1}``). Returns empty lists if the experiment DB uses an older schema.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
- `dataset_id` _str_ - The dataset to summarize.
  

**Returns**:

- `AnnotationSummary` - Summary with ``feedback`` and ``expectations`` lists.
  

**Example**:

```python
tracker = ExperimentTracker()
summary = tracker.get_eval_annotation_summary("exp-1", "ds-1")
for fb in summary.feedback:
    print(f"{fb.name}: {fb.total} total, counts={fb.counts}")
for exp in summary.expectations:
    print(f"{exp.name}: {exp.total} total")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_trace_annotation_summary"></a>

#### get\_trace\_annotation\_summary

```python
def get_trace_annotation_summary(
    experiment_id: str,
    trace_id: str
) -> AnnotationSummary
```

Get an aggregated summary of annotations across all spans in a trace.

Returns feedback and expectation annotations grouped by annotation name.
Feedback items include a ``counts`` dict keyed by value. Returns empty lists if the experiment DB uses an older schema.

**Arguments**:

- `experiment_id` _str_ - The experiment containing the trace.
- `trace_id` _str_ - The trace to summarize.
  

**Returns**:

- `AnnotationSummary` - Summary with ``feedback`` and ``expectations`` lists.
  

**Example**:

```python
tracker = ExperimentTracker()
summary = tracker.get_trace_annotation_summary("exp-1", "trace-abc")
for fb in summary.feedback:
    print(f"{fb.name}: {fb.total} total, counts={fb.counts}")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_all_traces_annotation_summary"></a>

#### get\_all\_traces\_annotation\_summary

```python
def get_all_traces_annotation_summary(experiment_id: str) -> AnnotationSummary
```

Get an aggregated summary of span annotations across all traces.

Unlike ``get_trace_annotation_summary`` which scopes to a single trace, this method aggregates annotations from every span in the experiment.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
  

**Returns**:

- `AnnotationSummary` - Summary with ``feedback`` and ``expectations`` lists.
  

**Example**:

```python
tracker = ExperimentTracker()
summary = tracker.get_all_traces_annotation_summary("exp-1")
for fb in summary.feedback:
    print(f"{fb.name}: {fb.total} total, counts={fb.counts}")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_experiment_ddl_version"></a>

#### get\_experiment\_ddl\_version

```python
def get_experiment_ddl_version(experiment_id: str) -> int
```

Retrieve the schema version of the experiment database.

The version corresponds to ``PRAGMA user_version`` in the SQLite DB.
Version 0 indicates a legacy DB without annotation table support.

**Arguments**:

- `experiment_id` _str_ - The experiment to check.
  

**Returns**:

- `int` - The schema version number.
  

**Example**:

```python
tracker = ExperimentTracker()
version = tracker.get_experiment_ddl_version("exp-1")
if version < 1:
    print("This experiment does not support annotations")
```

<a id="luml.experiments.tracker.ExperimentTracker.get_group"></a>

#### get\_group

```python
def get_group(group_id: str) -> Group | None
```

Retrieve a group by ID.

**Arguments**:

- `group_id` _str_ - The group to look up.
  

**Returns**:

  Group | None: The group metadata, or ``None`` if not found.
  

**Example**:

```python
tracker = ExperimentTracker()
group = tracker.get_group("group-uuid")
if group:
    print(group.name)
```

<a id="luml.experiments.tracker.ExperimentTracker.update_group"></a>

#### update\_group

```python
def update_group(
    group_id: str,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None
) -> Group | None
```

Update group metadata.

Only the provided fields are updated; ``None`` values are ignored.

**Arguments**:

- `group_id` _str_ - The group to update.
- `name` _str | None_ - New group name.
- `description` _str | None_ - New group description.
- `tags` _list[str] | None_ - New list of tags.
  

**Returns**:

  Group | None: The updated group, or ``None`` if not found.
  

**Example**:

```python
tracker = ExperimentTracker()
tracker.update_group("group-uuid", name="Production Models")
```

<a id="luml.experiments.tracker.ExperimentTracker.delete_group"></a>

#### delete\_group

```python
def delete_group(group_id: str) -> None
```

Delete a group by ID.

**Arguments**:

- `group_id` _str_ - The group to delete.
  

**Example**:

```python
tracker = ExperimentTracker()
tracker.delete_group("group-uuid")
```

<a id="luml.experiments.tracker.ExperimentTracker.list_groups_pagination"></a>

#### list\_groups\_pagination

```python
def list_groups_pagination(
    limit: int = 20,
    cursor_str: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    search: str | None = None
) -> PaginatedResponse[Group]
```

Retrieve a paginated list of groups.

**Arguments**:

- `limit` _int_ - Maximum number of groups per page. Defaults to 20.
- `cursor_str` _str | None_ - Pagination cursor from a previous response.
- `sort_by` _str_ - Sort field. Defaults to ``'created_at'``.
- `order` _str_ - Sort order, ``'asc'`` or ``'desc'``. Defaults to ``'desc'``.
- `search` _str | None_ - Optional substring filter on group name.
  

**Returns**:

- `PaginatedResponse[Group]` - Page of groups with pagination cursor.
  

**Example**:

```python
tracker = ExperimentTracker()
page = tracker.list_groups_pagination(limit=10, search="prod")
for group in page.items:
    print(group.name)
```

<a id="luml.experiments.tracker.ExperimentTracker.list_group_experiments_pagination"></a>

#### list\_group\_experiments\_pagination

```python
def list_group_experiments_pagination(
    group_id: str,
    limit: int = 20,
    cursor_str: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    search: str | None = None,
    json_sort_column: str | None = None
) -> PaginatedResponse[Experiment]
```

Retrieve a paginated list of experiments within a group.

**Arguments**:

- `group_id` _str_ - The group to query.
- `limit` _int_ - Maximum number of experiments per page. Defaults to 20.
- `cursor_str` _str | None_ - Pagination cursor from a previous response.
- `sort_by` _str_ - Sort field. Defaults to ``'created_at'``.
- `order` _str_ - Sort order, ``'asc'`` or ``'desc'``. Defaults to ``'desc'``.
- `search` _str | None_ - Optional string for filtering experiments by sql-like query.
- `json_sort_column` _str | None_ - Resolved JSON column for sorting by static param or dynamic metric keys.
  

**Returns**:

- `PaginatedResponse[Experiment]` - Page of experiments with pagination cursor.
  

**Example**:

```python
tracker = ExperimentTracker()
page = tracker.list_group_experiments_pagination("group-uuid", limit=5)
for exp in page.items:
    print(exp.name, exp.tags)
```

<a id="luml.experiments.tracker.ExperimentTracker.get_group_experiments_static_params_keys"></a>

#### get\_group\_experiments\_static\_params\_keys

```python
def get_group_experiments_static_params_keys(group_id: str) -> list[str]
```

Retrieve all distinct static parameter keys across experiments in a group.

Useful for building comparison tables where each column is a parameter.

**Arguments**:

- `group_id` _str_ - The group to query.
  

**Returns**:

- `list[str]` - Sorted list of distinct parameter key names.
  

**Example**:

```python
tracker = ExperimentTracker()
keys = tracker.get_group_experiments_static_params_keys("group-uuid")
# e.g. ["batch_size", "learning_rate", "model_architecture"]
```

<a id="luml.experiments.tracker.ExperimentTracker.get_group_experiments_dynamic_metrics_keys"></a>

#### get\_group\_experiments\_dynamic\_metrics\_keys

```python
def get_group_experiments_dynamic_metrics_keys(group_id: str) -> list[str]
```

Retrieve all distinct dynamic metric keys across experiments in a group.

Useful for building comparison charts where each series is a metric.

**Arguments**:

- `group_id` _str_ - The group to query.
  

**Returns**:

- `list[str]` - Sorted list of distinct metric key names.
  

**Example**:

```python
tracker = ExperimentTracker()
keys = tracker.get_group_experiments_dynamic_metrics_keys("group-uuid")
# e.g. ["eval_accuracy", "train_loss", "val_loss"]
```

<a id="luml.experiments.tracker.ExperimentTracker.resolve_experiment_sort_column"></a>

#### resolve\_experiment\_sort\_column

```python
def resolve_experiment_sort_column(group_id: str, sort_by: str) -> str | None
```

Resolve a sort key to the underlying column expression for experiment queries.

Used to translate user-facing sort keys (e.g. ``'static.learning_rate'``) into the SQL expression needed for sorting.

**Arguments**:

- `group_id` _str_ - The group context for resolution.
- `sort_by` _str_ - The sort key to resolve.
  

**Returns**:

  str | None: The resolved SQL column expression, or ``None`` if invalid.
  

**Example**:

```python
tracker = ExperimentTracker()
col = tracker.resolve_experiment_sort_column("group-uuid", "static.lr")
```

<a id="luml.experiments.tracker.ExperimentTracker.update_model"></a>

#### update\_model

```python
def update_model(
    model_id: str,
    name: str | None = None,
    tags: list[str] | None = None
) -> Model | None
```

Update model metadata.

Only the provided fields are updated; ``None`` values are ignored.

**Arguments**:

- `model_id` _str_ - The model to update.
- `name` _str | None_ - New model name.
- `tags` _list[str] | None_ - New list of tags.
  

**Returns**:

  Model | None: The updated model, or ``None`` if not found.
  

**Example**:

```python
tracker = ExperimentTracker()
tracker.update_model("model-uuid", name="v2-finetuned", tags=["prod"])
```

<a id="luml.experiments.tracker.ExperimentTracker.delete_model"></a>

#### delete\_model

```python
def delete_model(model_id: str) -> None
```

Delete a model by ID.

**Arguments**:

- `model_id` _str_ - The model to delete.
  

**Example**:

```python
tracker = ExperimentTracker()
tracker.delete_model("model-uuid")
```

<a id="luml.experiments.tracker.ExperimentTracker.list_experiment_models"></a>

#### list\_experiment\_models

```python
def list_experiment_models(experiment_id: str) -> list[Model]
```

Retrieve all models associated with an experiment.

**Arguments**:

- `experiment_id` _str_ - The experiment to query.
  

**Returns**:

- `list[Model]` - List of models linked to the experiment.
  

**Example**:

```python
tracker = ExperimentTracker()
models = tracker.list_experiment_models("exp-1")
for model in models:
    print(f"{model.name} ({model.size} bytes)")
```

<a id="luml.experiments.tracker.ExperimentTracker.enable_tracing"></a>

#### enable\_tracing

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

<a id="luml.experiments.tracker.ExperimentTracker.export"></a>

#### export

```python
def export(
    output_path: str,
    experiment_id: str | None = None
) -> "ExperimentReference"
```

Export the entire experiment tracking data and save as an artifact.

**Arguments**:

- `output_path` - Path to save the exported artifact.
  

**Example**:

```python
tracker = ExperimentTracker()
exp_id = tracker.start_experiment()
# Log data...
tracker.end_experiment()
tracker.export("experiment_data.tar", experiment_id=exp_id)
```

