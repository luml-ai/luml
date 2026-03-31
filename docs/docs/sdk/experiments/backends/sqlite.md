<a id="luml.experiments.backends.sqlite"></a>

# luml.experiments.backends.sqlite

<a id="luml.experiments.backends.sqlite.SQLiteBackend"></a>

## SQLiteBackend Objects

```python
class SQLiteBackend(Backend, SQLitePaginationMixin)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.initialize_experiment"></a>

#### initialize\_experiment

```python
def initialize_experiment(
    experiment_id: str,
    group: str = "default",
    name: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None
) -> None
```

Initializes an experiment by associating it with a group and storing its metadata in the database.

**Arguments**:

- `experiment_id` - Unique identifier for the experiment.
- `group` - Group name to which the experiment belongs. If the group does not exist, it will
  be created. Defaults to "Default group".
- `name` - Optional name of the experiment. If not provided, the `experiment_id` will
  be used as the name.
- `tags` - Optional list of tags associated with the experiment.
- `description` - Optional description of the experiment.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_static"></a>

#### log\_static

```python
def log_static(experiment_id: str, key: str, value: Any) -> None
```

Logs a static parameter to the database for a given experiment.

This method logs a static parameter with a specified key and value to the associated
experiment. The parameter can be of type string, integer, float, boolean, or any other
data structure that can be serialized into JSON. If a static parameter with the same key
already exists, it will be updated.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment for which the static
  parameter is being logged.
- `key` _str_ - The key associated with the static parameter.
- `value` _Any_ - The value of the static parameter. It can be of type string, integer,
  float, boolean, or any serializable object.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_dynamic"></a>

#### log\_dynamic

```python
def log_dynamic(
    experiment_id: str,
    key: str,
    value: int | float,
    step: int | None = None
) -> None
```

Logs a dynamic metric for a given experiment. This method allows updating or
tracking metrics like performance indicators over multiple steps for analysis.

**Arguments**:

- `experiment_id` _str_ - Identifier for the experiment where the metric will
  be stored. It must be a valid experiment ID initialized beforehand.
- `key` _str_ - The label or name of the metric being recorded. Used to
  differentiate between various tracked metrics.
- `value` _int | float_ - Numeric value of the metric being logged. Must be
  either an integer or a float.
- `step` _int | None, optional_ - The specific step number associated with this
  value. If not provided, the method defaults to the next available
  step, determined by the maximum recorded step for the specified key.
  

**Returns**:

  None

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_attachment"></a>

#### log\_attachment

```python
def log_attachment(
    experiment_id: str,
    name: str,
    data: bytes | str,
    binary: bool = False
) -> None
```

Logs an attachment for a specific experiment by saving the data to a file and updating
the corresponding database record.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment where the attachment
  will be logged.
- `name` _str_ - The name of the attachment file.
- `data` _bytes | str_ - The content of the attachment to be logged. This must be either
  bytes or a string.
- `binary` _bool_ - Whether the attachment data should be saved in binary mode. Defaults
  to False.
  

**Raises**:

- `ValueError` - If the provided `data` is not of type `bytes` or `str`.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_span"></a>

#### log\_span

```python
def log_span(experiment_id: str,
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
             trace_flags: int = 0) -> None
```

Logs a span into the database for a specific experiment. This function inserts or replaces
a span record in the `spans` table associated with a given experiment. It allows the user
to register spans with detailed metadata including trace IDs, span attributes, events,
links, timestamps, and status information.

**Arguments**:

- `experiment_id` _str_ - Identifier for the experiment to which the span belongs.
- `trace_id` _str_ - Unique identifier for the trace.
- `span_id` _str_ - Unique identifier for the span.
- `name` _str_ - Name associated with the span.
- `start_time_unix_nano` _int_ - Span start time in nanoseconds since Unix epoch.
- `end_time_unix_nano` _int_ - Span end time in nanoseconds since Unix epoch.
- `parent_span_id` _str | None_ - Identifier for the parent span, or None if root span.
- `kind` _int_ - Type of the span (e.g., internal, server, client).
- `status_code` _int_ - Status code of the span (e.g., OK, ERROR).
- `status_message` _str | None_ - Human-readable description of the span's status,
  or None if not provided.
- `attributes` _dict[str, Any] | None_ - Arbitrary span attributes, or None if not provided.
- `events` _list[dict[str, Any]] | None_ - List of event dictionaries associated with the span,
  or None if no events are present.
- `links` _list[dict[str, Any]] | None_ - List of link dictionaries associated with the span,
  or None for no links.
- `trace_flags` _int_ - Flags providing additional trace information.
  

**Raises**:

- `ValueError` - If the specified experiment does not exist, or has not been initialized.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_eval_sample"></a>

#### log\_eval\_sample

```python
def log_eval_sample(
    experiment_id: str,
    eval_id: str,
    dataset_id: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any] | None = None,
    references: dict[str, Any] | None = None,
    scores: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None
) -> None
```

Logs evaluation sample data into the database for a given experiment.

This function inserts or updates evaluation data related to a specific experiment
identified by its ID. Each evaluation includes information about the dataset,
inputs, outputs, references, scores, and additional metadata. The function
serializes the provided data into JSON format to store in the database.

**Arguments**:

- `experiment_id` - Unique identifier of the experiment for which the evaluation
  is being logged.
- `eval_id` - Unique identifier of the evaluation sample within the experiment.
- `dataset_id` - Identifier of the dataset associated with the evaluation.
- `inputs` - A dictionary containing input data for the evaluation sample.
- `outputs` - A dictionary containing output data generated during the evaluation.
  It can be None if no outputs are available.
- `references` - A dictionary containing reference data or ground truth values
  for the evaluation. It can be None if no references are provided.
- `scores` - A dictionary containing evaluation scores or metrics. It can be None
  if no scores are available.
- `metadata` - A dictionary containing additional metadata information related to
  the evaluation sample. It can be None if no metadata is provided.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.link_eval_sample_to_trace"></a>

#### link\_eval\_sample\_to\_trace

```python
def link_eval_sample_to_trace(
    experiment_id: str,
    eval_dataset_id: str,
    eval_id: str,
    trace_id: str
) -> None
```

Links an evaluation sample to a trace by creating or updating an entry in the
eval_traces_bridge table. This is used to associate evaluation results with
trace data for a given experiment context.

**Arguments**:

- `experiment_id` - Identifier of the experiment containing the database.
- `eval_dataset_id` - Identifier of the dataset in which the evaluation resides.
- `eval_id` - Identifier of the evaluation to be linked.
- `trace_id` - Identifier of the trace to be associated with the evaluation sample.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_data"></a>

#### get\_experiment\_data

```python
def get_experiment_data(experiment_id: str) -> ExperimentData
```

Retrieves and constructs the experiment data for a specified experiment ID from the
corresponding database. It encompasses metadata, static parameters, dynamic metrics,
and attachments associated with the experiment.

**Arguments**:

- `experiment_id` _str_ - Unique identifier for the experiment.
  

**Returns**:

- `ExperimentData` - An object containing all experiment data, including metadata,
  static parameters, dynamic metrics, and attachments.
  

**Raises**:

- `ValueError` - If the experiment with the given experiment ID is not found.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_attachment"></a>

#### get\_attachment

```python
def get_attachment(experiment_id: str, name: str) -> Any
```

Fetches the content of a specific attachment file associated with an experiment.

This method retrieves the contents of an attachment file from the directory
corresponding to a given experiment. The file is identified by its name and
the ID of the experiment. If the experiment has not been initialized or
the specified attachment cannot be found, appropriate errors are raised.

**Arguments**:

- `experiment_id` _str_ - Identifier for the experiment whose attachment is
  being accessed.
- `name` _str_ - Name of the attachment file to retrieve.
  

**Returns**:

- `Any` - The binary content of the specified attachment file.
  

**Raises**:

- `ValueError` - If the specified attachment file is not found within the
  directory of the given experiment.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.list_experiments"></a>

#### list\_experiments

```python
def list_experiments() -> list[Experiment]
```

Retrieves and returns a list of all experiments stored in the database.

The method queries the database to fetch experiment details such as
ID, name, creation date, status, group ID, associated tags, static
parameters, and dynamic parameters. The information is used to construct
a list of `Experiment` objects which represent the stored experiments.

**Returns**:

- `list[Experiment]` - A list of `Experiment` objects containing information
  about each experiment retrieved from the database.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.resolve_experiment_sort_column"></a>

#### resolve\_experiment\_sort\_column

```python
def resolve_experiment_sort_column(group_id: str, sort_by: str) -> str | None
```

Resolves the json_sort_column for list_group_experiments_pagination.

Specific to experiments: checks dynamic_params and static_params keys.
- None              → sort_by is a standard experiment column
- "dynamic_params"  → sort_by is a dynamic metric key
- "static_params"   → sort_by is a static param key
- raises ValueError → sort_by is unknown

<a id="luml.experiments.backends.sqlite.SQLiteBackend.resolve_groups_experiment_sort_column"></a>

#### resolve\_groups\_experiment\_sort\_column

```python
def resolve_groups_experiment_sort_column(
    group_ids: list[str],
    sort_by: str
) -> str | None
```

Resolves the json_sort_column for list_groups_experiments_pagination.

Checks across all provided groups.
- None              → sort_by is a standard experiment column
- "dynamic_params"  → sort_by is a dynamic metric key in any group
- "static_params"   → sort_by is a static param key in any group
- raises ValueError → sort_by is unknown across all groups

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment"></a>

#### get\_experiment

```python
def get_experiment(experiment_id: str) -> Experiment | None
```

Fetches an experiment's details from the database by the given experiment ID.

This method queries the database to retrieve information about a specific experiment
based on its unique identifier. If no experiment is found, the method returns None.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment to retrieve.
  

**Returns**:

  Experiment | None: An instance of the `Experiment` class containing the details of
  the experiment if found, or None if no matching record exists.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.delete_experiment"></a>

#### delete\_experiment

```python
def delete_experiment(experiment_id: str) -> None
```

Deletes a specified experiment from the database and cleans up associated files
from the filesystem.

This method performs the following actions:
1. Deletes the experiment record from the database.
2. Marks the experiment as inactive in the experiment pool.
3. Deletes all associated files and directories for the experiment if they
exist on the filesystem.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment to delete.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.update_experiment"></a>

#### update\_experiment

```python
def update_experiment(
    experiment_id: str,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None
) -> Experiment | None
```

Updates an existing experiment record in the database. Fields such as name, description,
and tags can be updated selectively. If no fields are updated, the function retrieves
the current experiment details.

**Arguments**:

- `experiment_id` - Unique identifier of the experiment to update.
- `name` - Optional new name for the experiment.
- `description` - Optional new description for the experiment.
- `tags` - Optional list of new tags associated with the experiment.
  

**Returns**:

- `Experiment` - Updated experiment object if the update is successful or the record is retrieved.
- `None` - If the experiment with the given ID does not exist.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.create_group"></a>

#### create\_group

```python
def create_group(
    name: str,
    description: str | None = None,
    tags: list[str] | None = None
) -> Group
```

Creates or retrieves an existing experiment group from the database.

This method checks if a group with the specified name exists. If it exists, it retrieves
the existing group data and returns it. Otherwise, it creates a new group in the database,
commits the changes, and returns the newly created group.

**Arguments**:

- `name` - The name of the experiment group to create or retrieve.
- `description` - Optional. Additional details about the group. If not provided, defaults to None.
- `tags` - Optional list of tags for the group.
  

**Returns**:

- `Group` - An instance of the Group class containing the data for the retrieved or newly created group.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.update_group"></a>

#### update\_group

```python
def update_group(
    group_id: str,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None
) -> Group | None
```

Updates the attributes of an existing group identified by its group ID. If no
updates are provided, the method retrieves the existing group's details.

**Arguments**:

- `group_id` - The unique identifier of the group to be updated.
- `name` - The new name of the group. If None, the name remains unchanged.
- `description` - The new description of the group. If None, the description
  remains unchanged.
- `tags` - A list of new tags associated with the group. If None, the tags
  remain unchanged.
  

**Returns**:

  An updated Group object if the update is successful. If there are no
  updates provided, or the group ID doesn't exist, returns None.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.delete_group"></a>

#### delete\_group

```python
def delete_group(group_id: str) -> None
```

Deletes a group and all its experiments from the database, including
their associated files and directories on the filesystem.

**Arguments**:

- `group_id` _str_ - The unique identifier of the group to be deleted.
  

**Returns**:

  None

<a id="luml.experiments.backends.sqlite.SQLiteBackend.list_groups"></a>

#### list\_groups

```python
def list_groups() -> list[Group]
```

Retrieves a list of all experiment groups from the database and returns them as a list
of `Group` objects. Each group contains metadata including its ID, name, description,
and creation date.

**Returns**:

- `list[Group]` - A list of `Group` objects representing all experiment groups in the
  database.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.list_groups()

[
    Group(
        id="group-123",
        name="cv_experiments",
        description="Computer vision experiments",
        created_at=datetime(2024, 6, 1, 10, 0, 0),
        tags=["cv", "production"],
        last_modified=datetime(2024, 6, 5, 15, 30, 0),
    ),
    Group(
        id="group-456",
        name="nlp_experiments",
        description=None,
        created_at=datetime(2024, 6, 2, 8, 0, 0),
        tags=[],
        last_modified=None,
    ),
]
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_model"></a>

#### log\_model

```python
def log_model(
    experiment_id: str,
    model_path: str,
    name: str | None = None,
    tags: list[str] | None = None
) -> tuple[Model, str]
```

Logs a machine learning model to the specified experiment by storing its metadata and
copying the model file to the appropriate storage location.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment to which the model
  is logged.
- `model_path` _str_ - The file path of the model to be logged.
- `name` _str | None, optional_ - The name of the model. If not provided, the stem of
  the model file name is used.
- `tags` _list[str] | None, optional_ - A list of tags associated with the model to
  provide metadata for organizational or informational purposes.
  

**Returns**:

  tuple[Model, str]: A tuple containing the `Model` object representing the logged
  model's metadata and the absolute destination path of the copied model file.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
model, dest_path = backend.log_model(
    experiment_id="exp-001",
    model_path="/tmp/resnet50.pt",
    name="resnet50_v1",
    tags=["production", "v1"],
)
model

Model(
    id="model-abc",
    name="resnet50_v1",
    created_at=datetime(2024, 6, 1, 12, 0, 0),
    tags=["production", "v1"],
    path="/storage/exp-001/models/resnet50_v1.pt",
    experiment_id="exp-001",
)
dest_path

"/storage/exp-001/models/resnet50_v1.pt"
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_models"></a>

#### get\_models

```python
def get_models(experiment_id: str) -> list[Model]
```

Fetches all models associated with a given experiment ID.

This method queries the database for all models that are linked to the
specified experiment ID. Each row fetched from the database is converted
to a `Model` object and returned as part of a list.

**Arguments**:

- `experiment_id` _str_ - The identifier of the experiment whose models
  need to be fetched.
  

**Returns**:

- `list[Model]` - A list of `Model` objects associated with the given
  experiment ID.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_models("exp-001")

[
    Model(
        id="model-abc",
        name="resnet50_v1",
        created_at=datetime(2024, 6, 1, 12, 0, 0),
        tags=["production", "v1"],
        path="/artifacts/resnet50_v1.pt",
        experiment_id="exp-001",
    ),
    Model(
        id="model-def",
        name="resnet50_v2",
        created_at=datetime(2024, 6, 2, 9, 0, 0),
        tags=[],
        path=None,
        experiment_id="exp-001",
    ),
]
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_model"></a>

#### get\_model

```python
def get_model(model_id: str) -> Model
```

Retrieves a model instance based on the provided model ID.

Uses an internal meta connection to locate and fetch the model by the
given model ID. If the model does not exist, a ValueError is raised.

**Arguments**:

- `model_id` _str_ - The unique identifier of the model to retrieve.
  

**Returns**:

- `Model` - The retrieved model instance.
  

**Raises**:

- `ValueError` - If the model with the specified ID is not found.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_model("model-abc")

Model(
    id="model-abc",
    name="resnet50_v1",
    created_at=datetime(2024, 6, 1, 12, 0, 0),
    tags=["production", "v1"],
    path="/artifacts/resnet50_v1.pt",
    experiment_id="exp-001",
)

backend.get_model("nonexistent-id")

ValueError: Model nonexistent-id not found
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.update_model"></a>

#### update\_model

```python
def update_model(
    model_id: str,
    name: str | None = None,
    tags: list[str] | None = None
) -> Model | None
```

Updates the attributes of a model in the database given its model ID.

This method allows updating the name and tags of a model. If no fields are
provided for updating, it fetches and returns the original model. The tags,
if provided, are stored as a JSON string in the database.

**Arguments**:

- `model_id` _str_ - The unique identifier of the model to update.
- `name` _str | None_ - The new name for the model. Defaults to None.
- `tags` _list[str] | None_ - A list of string tags to associate with the model.
  Defaults to None.
  

**Returns**:

  Model | None: The updated model as a `Model` object if the update is
  successful, or None if the model with the given ID does not exist.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.update_model("model-abc", name="resnet50_v2", tags=["production", "v2"])

Model(
    id="model-abc",
    name="resnet50_v2",
    created_at=datetime(2024, 6, 1, 12, 0, 0),
    tags=["production", "v2"],
    path="/artifacts/resnet50_v1.pt",
    experiment_id="exp-001",
)

backend.update_model("nonexistent-id")

None
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.delete_model"></a>

#### delete\_model

```python
def delete_model(model_id: str) -> None
```

Deletes a model and its files from the database and filesystem.

The method removes a model entry from the database and, if a file path for the
model exists, deletes the associated file from the specified directory.

**Arguments**:

- `model_id` _str_ - The unique identifier of the model to be deleted.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.list_groups_pagination"></a>

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

Retrieves a paginated list of experiment groups from the database. Supports optional
filtering, sorting, and cursor-based pagination mechanisms to improve query efficiency
and usability.

**Arguments**:

- `limit` _int_ - The maximum number of items to include in the response. Defaults to 20.
- `cursor_str` _str | None_ - An optional encoded cursor string to specify the starting
  point for the query. Used for cursor-based pagination.
- `sort_by` _str_ - The attribute by which to sort the results. Must be one of
  "created_at", "name", or "last_modified". Defaults to "created_at".
- `order` _str_ - The sort order for the results. Must be either "asc" or "desc".
  Defaults to "desc".
- `search` _str | None_ - An optional search term to filter groups based on name or tags.
  

**Returns**:

- `PaginatedResponse[Group]` - A paginated response object containing a list of
  Group objects and pagination metadata.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.list_groups_pagination(limit=2, sort_by="created_at", order="desc")

PaginatedResponse(
    items=[
        Group(
            id="group-123",
            name="cv_experiments",
            description="Computer vision experiments",
            created_at=datetime(2024, 6, 2, 10, 0, 0),
            tags=["cv", "production"],
            last_modified=datetime(2024, 6, 5, 15, 30, 0),
        ),
        Group(
            id="group-456",
            name="nlp_experiments",
            description=None,
            created_at=datetime(2024, 6, 1, 8, 0, 0),
            tags=[],
            last_modified=None,
        ),
    ],
    cursor="eyJjcmVhdGVkX2F0IjogIjIwMjQtMDYtMDEifQ==",
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_group"></a>

#### get\_group

```python
def get_group(group_id: str) -> Group | None
```

Retrieves information about an experiment group by its unique identifier.

This method queries the database for an experiment group with the provided
group identifier. If the group exists, it returns a `Group` object populated
with the group's details. Otherwise, it returns `None`.

**Arguments**:

- `group_id` _str_ - A unique identifier for the experiment group.
  

**Returns**:

  Group | None: A `Group` object containing the details of the experiment
  group if found, otherwise `None`.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_group("group-123")

Group(
    id="group-123",
    name="cv_experiments",
    description="Computer vision experiments",
    created_at=datetime(2024, 6, 1, 10, 0, 0),
    tags=["cv", "production"],
    last_modified=datetime(2024, 6, 5, 15, 30, 0),
)

backend.get_group("nonexistent-id")

None
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.list_batch_experiments_models"></a>

#### list\_batch\_experiments\_models

```python
def list_batch_experiments_models(
    experiment_ids: list[str]
) -> dict[str, list[Model]]
```

Retrieves models associated with a list of experiment IDs. Models are organized into a dictionary
where the key is the experiment ID, and the value is a list of `Model` objects belonging to that
experiment. If no experiment IDs are provided, an empty dictionary is returned.

**Arguments**:

- `experiment_ids` _list[str]_ - A list of experiment IDs for which models need to be fetched.
  

**Returns**:

  dict[str, list[Model]]: A dictionary where keys are experiment IDs and values are lists of
  models associated with those experiment IDs.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.list_batch_experiments_models(["exp-001", "exp-002"])

{
    "exp-001": [
        Model(
            id="model-abc",
            name="resnet50_v1",
            created_at=datetime(2024, 6, 1, 12, 0, 0),
            tags=["production"],
            path="/artifacts/resnet50_v1.pt",
            experiment_id="exp-001",
        ),
    ],
    "exp-002": [
        Model(
            id="model-def",
            name="bert_base",
            created_at=datetime(2024, 6, 2, 9, 0, 0),
            tags=[],
            path=None,
            experiment_id="exp-002",
        ),
    ],
}
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.list_experiment_models"></a>

#### list\_experiment\_models

```python
def list_experiment_models(experiment_id: str) -> list[Model]
```

Fetches a list of models associated with the specified experiment.

This method queries the database for all models tied to an experiment identified
by the provided `experiment_id`. Each model is returned as an instance of the
`Model` class. The models include details such as their IDs, names, creation
timestamps, tags, associated paths, and experiment IDs.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment whose
  models are to be retrieved.
  

**Returns**:

- `list[Model]` - A list of `Model` instances representing the models
  associated with the specified experiment.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.list_experiment_models("exp-001")

[
    Model(
        id="model-abc",
        name="resnet50_v1",
        created_at=datetime(2024, 6, 1, 12, 0, 0),
        tags=["production", "v1"],
        path="/artifacts/resnet50_v1.pt",
        experiment_id="exp-001",
    ),
    Model(
        id="model-def",
        name="resnet50_v2",
        created_at=datetime(2024, 6, 1, 14, 30, 0),
        tags=[],
        path=None,
        experiment_id="exp-001",
    ),
]
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.list_group_experiments_pagination"></a>

#### list\_group\_experiments\_pagination

```python
def list_group_experiments_pagination(
    group_id: str,
    limit: int = 20,
    cursor_str: str | None = None,
    sort_by: str = "created_at",
    order: Literal["asc", "desc"] = "desc",
    search: str | None = None,
    json_sort_column: Literal["static_params", "dynamic_params"] | None = None
) -> PaginatedResponse[Experiment]
```

Fetches a paginated list of experiments within a specified group, supporting various
sorting, filtering, and cursor-based pagination options.

This method retrieves experiments associated with a specific group ID, ordering and
filtering them based on the provided parameters. It supports sorting by both standard
columns and specific JSON fields, as well as filtering based on search terms and
integrating with a cursor-based pagination approach.

**Arguments**:

- `group_id` _str_ - The unique identifier for the group whose experiments are being
  listed.
- `limit` _int, optional_ - The maximum number of records to retrieve per page. Default
  is 20.
- `cursor_str` _str | None, optional_ - The encoded cursor string for implementing
  pagination. Default is None.
- `sort_by` _str, optional_ - The column name to sort the results by. Default is
  "created_at".
- `order` _str, optional_ - The order of sorting, either "asc" (ascending) or "desc"
  (descending). Default is "desc".
- `search` _str | None, optional_ - The search string for filtering experiments by name
  or tags. Default is None.
- `json_sort_column` _str | None, optional_ - A JSON column (either "static_params" or
  "dynamic_params") to use for sorting. Default is None.
  

**Returns**:

- `PaginatedResponse[Experiment]` - A paginated response object containing the list of
  Experiment objects and pagination-related metadata.
  

**Raises**:

- `ValueError` - If the provided `json_sort_column` is not one of the allowed values
  ("static_params", "dynamic_params").
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
response = backend.list_group_experiments_pagination(
    group_id="group-123",
    limit=2,
    sort_by="created_at",
    order="desc",
)

PaginatedResponse(
    items=[
        Experiment(
            id="exp-001",
            name="baseline_run",
            status="completed",
            created_at=datetime(2024, 6, 1, 12, 0, 0),
            tags=["baseline", "v1"],
            models=[],
            duration=42.3,
            description="Initial baseline experiment",
            group_id="group-123",
            static_params={"lr": 0.01, "epochs": 10},
            dynamic_params={"loss": 0.25, "accuracy": 0.91},
        )
    ],
    cursor="eyJjcmVhdGVkX2F0IjogIjIwMjQtMDYtMDIifQ=="
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.list_groups_experiments_pagination"></a>

#### list\_groups\_experiments\_pagination

```python
def list_groups_experiments_pagination(
    group_ids: list[str],
    limit: int = 20,
    cursor_str: str | None = None,
    sort_by: str = "created_at",
    order: Literal["asc", "desc"] = "desc",
    search: str | None = None,
    json_sort_column: Literal["static_params", "dynamic_params"] | None = None
) -> PaginatedResponse[Experiment]
```

Fetches a paginated list of experiments across multiple groups, supporting various
sorting, filtering, and cursor-based pagination options.

This method retrieves experiments associated with the provided group IDs, ordering and
filtering them based on the given parameters. It supports sorting by both standard
columns and specific JSON fields, as well as filtering based on search terms and
cursor-based pagination. Returns an empty response if the group list is empty.

**Arguments**:

- `group_ids` _list[str]_ - The list of group identifiers whose experiments are being
  listed.
- `limit` _int, optional_ - The maximum number of records to retrieve per page. Default
  is 20.
- `cursor_str` _str | None, optional_ - The encoded cursor string for implementing
  pagination. Default is None.
- `sort_by` _str, optional_ - The column name to sort the results by. Default is
  "created_at".
- `order` _str, optional_ - The order of sorting, either "asc" (ascending) or "desc"
  (descending). Default is "desc".
- `search` _str | None, optional_ - The search string for filtering experiments by name
  or tags. Default is None.
- `json_sort_column` _str | None, optional_ - A JSON column (either "static_params" or
  "dynamic_params") to use for sorting. Default is None.
  

**Returns**:

- `PaginatedResponse[Experiment]` - A paginated response object containing the list of
  Experiment objects and pagination-related metadata.
  

**Raises**:

- `ValueError` - If the provided `json_sort_column` is not one of the allowed values
  ("static_params", "dynamic_params").
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
response = backend.list_groups_experiments_pagination(
    group_ids=["group-123", "group-456"],
    limit=2,
    sort_by="created_at",
    order="desc",
)

PaginatedResponse(
    items=[
        Experiment(
            id="exp-001",
            name="baseline_run",
            status="completed",
            created_at=datetime(2024, 6, 1, 12, 0, 0),
            tags=["baseline", "v1"],
            models=[],
            duration=42.3,
            description="Initial baseline experiment",
            group_id="group-123",
            static_params={"lr": 0.01, "epochs": 10},
            dynamic_params={"loss": 0.25, "accuracy": 0.91},
        )
    ],
    cursor="eyJjcmVhdGVkX2F0IjogIjIwMjQtMDYtMDIifQ=="
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.end_experiment"></a>

#### end\_experiment

```python
def end_experiment(experiment_id: str) -> None
```

Finalizes the experiment by setting its status to 'completed' and saving its static
and dynamic parameters.

This method fetches the relevant parameters for the experiment from the database
and updates its status and associated values in the metadata store. It ensures
resource cleanup by marking the experiment as inactive in the connection pool.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment to be finalized.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.export_experiment_db"></a>

#### export\_experiment\_db

```python
def export_experiment_db(experiment_id: str) -> DiskFile
```

Exports the database file associated with the specified experiment.

This method retrieves the database file path for the given experiment ID.
It ensures the database exists and performs a write-ahead log (WAL)
checkpoint to truncate the log before returning the database file. The
method raises an error if the specified experiment cannot be found.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment whose
  database file needs to be exported.
  

**Returns**:

- `DiskFile` - An object representing the exported database file.
  

**Raises**:

- `ValueError` - If the experiment with the given experiment ID does not
  exist.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.export_attachments"></a>

#### export\_attachments

```python
def export_attachments(experiment_id: str) -> tuple[_BaseFile, _BaseFile] | None
```

Exports attachments associated with a specific experiment.

This function retrieves, archives, and indexes the attachments of a specified
experiment by creating a tarball. Depending on the presence of attachments,
it may return created files or None.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment whose
  attachments need to be exported.
  

**Returns**:

  tuple[_BaseFile, _BaseFile] | None: A tuple containing the created tarball
  and index file if attachments exist, or `None` if no attachments are
  found.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_metric_history"></a>

#### get\_experiment\_metric\_history

```python
def get_experiment_metric_history(
    experiment_id: str,
    key: str
) -> list[dict[str, Any]]
```

Retrieves the historical metrics data for a specific experiment and metric key. The data
is ordered by the step value in ascending order. Each metric record contains the value,
step, and timestamp when the metric was logged.

**Arguments**:

- `experiment_id` - The unique identifier for the experiment whose metric history is
  being retrieved.
- `key` - The key for the metric whose history is being fetched.
  

**Returns**:

  A list of dictionaries where each dictionary contains the following keys:
  - 'value' (Any): The stored value of the metric.
  - 'step' (int): The step or index associated with the metric value.
  - 'logged_at' (datetime): A timestamp representing when the metric was logged.
  

**Raises**:

- `ValueError` - If the experiment with the given `experiment_id` does not exist.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_traces"></a>

#### get\_experiment\_traces

```python
def get_experiment_traces(
        experiment_id: str,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: Literal["execution_time", "span_count",
                         "created_at"] = "execution_time",
        order: Literal["asc", "desc"] = "desc",
        search: str | None = None,
        filters: list[str] | None = None,
        states: list[TraceState] | None = None
) -> PaginatedResponse[TraceRecord]
```

Retrieve paginated trace summaries for a given experiment.

Returns an aggregated summary per trace: trace_id, execution_time
(MAX(end) - MIN(start) across all spans in seconds), span_count,
created_at, state, and linked eval IDs. Supports filtering by trace_id
substring and state, sorting by execution_time, span_count or created_at,
and cursor-based pagination.

**Arguments**:

- `experiment_id` - The unique identifier of the experiment.
- `limit` - Maximum number of summaries to return. Defaults to 20.
- `cursor_str` - Opaque pagination cursor from a previous response.
- `sort_by` - Sort field — "execution_time", "span_count", or "created_at".
- `order` - Sort direction — "asc" or "desc".
- `search` - Substring to filter trace_id (LIKE %...%).
- `states` - Filter by one or more TraceState values.
  

**Returns**:

  PaginatedResponse[TraceRecord]
  

**Raises**:

- `ValueError` - If experiment not found.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_experiment_traces(
    "exp-001", limit=2, sort_by="execution_time", order="desc"
)

PaginatedResponse(
    items=[
        TraceRecord(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            execution_time=15.442,
            span_count=6,
            created_at=datetime(2024, 6, 1, 12, 0, 1),
            state=TraceState.OK,
            evals=["eval-001", "eval-002"],
            annotations=AnnotationSummary(
                feedback=[
                    FeedbackSummaryItem(
                        name="correct",
                        total=3,
                        counts={"true": 2, "false": 1}
                    )
                ],
                expectations=[
                    ExpectationSummaryItem(
                        name="expected_answer",
                        total=1
                    )
                ],
            ),
        ),
    ],
    cursor="eyJ0cmFjZV9pZCI6ICJhM2NlOTI5ZC4uLiJ9",
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_traces_all"></a>

#### get\_experiment\_traces\_all

```python
def get_experiment_traces_all(
    experiment_id: str,
    sort_by: str = "execution_time",
    order: Literal["asc", "desc"] = "desc",
    search: str | None = None,
    filters: list[str] | None = None,
    states: list[TraceState] | None = None
) -> list[TraceRecord]
```

Retrieve paginated trace summaries for a given experiment.

Returns an aggregated summary per trace: trace_id, execution_time
(MAX(end) - MIN(start) across all spans in seconds), span_count,
created_at, state, and linked eval IDs. Supports filtering by trace_id
substring and state, sorting by execution_time, span_count or created_at,
and cursor-based pagination.

**Arguments**:

- `experiment_id` - The unique identifier of the experiment.
- `sort_by` - Sort field — "execution_time", "span_count", or "created_at".
- `order` - Sort direction — "asc" or "desc".
- `search` - Substring to filter trace_id (LIKE %...%).
- `states` - Filter by one or more TraceState values.
  

**Returns**:

  PaginatedResponse[TraceRecord]
  

**Raises**:

- `ValueError` - If experiment not found.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_experiment_traces(
    "exp-001", sort_by="execution_time", order="desc"
)

[
    TraceRecord(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        execution_time=15.442,
        span_count=6,
        created_at=datetime(2024, 6, 1, 12, 0, 1),
        state=TraceState.OK,
        evals=["eval-001", "eval-002"],
        annotations=AnnotationSummary(
            feedback=[
                FeedbackSummaryItem(
                    name="correct",
                    total=3,
                    counts={"true": 2, "false": 1}
                )
            ],
            expectations=[
                ExpectationSummaryItem(
                    name="expected_answer",
                    total=1
                )
            ],
        ),
    ),
]
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_trace"></a>

#### get\_trace

```python
def get_trace(experiment_id: str, trace_id: str) -> TraceDetails | None
```

Retrieves trace details for a given trace ID within an experiment.

This method queries the database associated with the specified experiment ID
to fetch detailed information about the trace, including span records and
their associated metadata. If the trace ID does not exist within the database,
the method returns None. Errors are raised if the experiment's database is not
found.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment whose trace
  details are being retrieved.
- `trace_id` _str_ - The unique identifier of the trace within the experiment.
  

**Returns**:

  TraceDetails | None: A TraceDetails object containing the trace ID and
  its associated spans if the trace is found; otherwise, None.
  

**Raises**:

- `ValueError` - If the specified experiment ID does not have an associated
  database or the database cannot be found.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_trace("exp-001", "4bf92f3577b34da6a3ce929d0e0e4736")

TraceDetails(
    trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    spans=[
        SpanRecord(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            parent_span_id=None,
            name="agent.run",
            kind=1,
            dfs_span_type=2,
            start_time_unix_nano=1717200000000000000,
            end_time_unix_nano=1717200015442000000,
            status_code=1,
            status_message=None,
            attributes={"llm.model": "gpt-4o", "llm.token_count": 512},
            events=None,
            links=None,
            trace_flags=1,
        )
    ]
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_evals"></a>

#### get\_experiment\_evals

```python
def get_experiment_evals(
    experiment_id: str,
    limit: int = 20,
    cursor_str: str | None = None,
    sort_by: str = "created_at",
    order: Literal["asc", "desc"] = "desc",
    dataset_id: str | None = None,
    json_sort_column: str | None = None,
    search: str | None = None,
    filters: list[str] | None = None
) -> PaginatedResponse[EvalRecord]
```

Retrieve paginated eval samples for a given experiment.

Returns eval samples with their inputs, outputs, scores, and linked trace IDs.
Supports optional filtering by dataset_id, sorting by created_at, updated_at,
dataset_id, or a JSON column key (via json_sort_column), and cursor-based pagination.

**Arguments**:

- `search` - string to search by id.
- `experiment_id` - The unique identifier of the experiment.
- `limit` - Maximum number of evals to return. Defaults to 20.
- `cursor_str` - Opaque pagination cursor from a previous response.
- `sort_by` - Sort field or JSON key name when json_sort_column is set.
- `order` - Sort direction — "asc" or "desc".
- `dataset_id` - Filter evals to a specific dataset.
- `json_sort_column` - When set (e.g. "scores"), sort by json_extract(json_sort_column, '$.\{sort_by\}').
  

**Returns**:

  PaginatedResponse[EvalRecord]
  

**Raises**:

- `ValueError` - If experiment not found.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_experiment_evals("exp-001", limit=2)

PaginatedResponse(
    items=[
        EvalRecord(
            id="eval-001",
            dataset_id="ds-abc",
            inputs={"question": "What is 2+2?"},
            outputs={"answer": "4"},
            scores={"accuracy": 1.0},
            metadata={"source": "test-set"},
            created_at=datetime(2024, 6, 1, 12, 0, 0),
            updated_at=datetime(2024, 6, 1, 12, 0, 0),
            trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
            annotations=AnnotationSummary(
                feedback=[
                    FeedbackSummaryItem(
                        name="correct",
                        total=3,
                        counts={"true": 2, "false": 1}
                    )
                ],
                expectations=[
                    ExpectationSummaryItem(
                        name="expected_answer",
                        total=1
                    )
                ],
            ),
        ),
    ],
    cursor="eyJpZCI6ICJldmFsLTAwMSJ9",
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_evals_all"></a>

#### get\_experiment\_evals\_all

```python
def get_experiment_evals_all(
    experiment_id: str,
    sort_by: str = "created_at",
    order: Literal["asc", "desc"] = "desc",
    dataset_id: str | None = None,
    json_sort_column: str | None = None,
    search: str | None = None,
    filters: list[str] | None = None
) -> list[EvalRecord]
```

Retrieve all eval records for a given experiment.

Returns evals with their inputs, outputs, scores, and linked trace IDs.
Supports optional filtering by dataset_id, sorting by created_at, updated_at,
dataset_id, or a JSON column key (via json_sort_column).

**Arguments**:

- `experiment_id` - The unique identifier of the experiment.
- `sort_by` - Sort field or JSON key name when json_sort_column is set.
- `order` - Sort direction — "asc" or "desc".
- `dataset_id` - Filter evals to a specific dataset.
- `json_sort_column` - When set (e.g. "scores"), sort by json_extract(json_sort_column, '$.\{sort_by\}').
- `search` - string to search by name or tag.
  

**Returns**:

  list[EvalRecord]
  

**Raises**:

- `ValueError` - If experiment not found.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_experiment_evals_all("exp-001")

[
    EvalRecord(
        id="eval-001",
        dataset_id="ds-abc",
        inputs={"question": "What is 2+2?"},
        outputs={"answer": "4"},
        scores={"accuracy": 1.0},
        metadata={"source": "test-set"},
        created_at=datetime(2024, 6, 1, 12, 0, 0),
        updated_at=datetime(2024, 6, 1, 12, 0, 0),
        trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
        annotations=AnnotationSummary(
            feedback=[
                FeedbackSummaryItem(
                    name="correct",
                    total=3,
                    counts={"true": 2, "false": 1}
                )
            ],
            expectations=[
                ExpectationSummaryItem(
                    name="expected_answer",
                    total=1
                )
            ],
        ),
    ),
]
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_eval"></a>

#### get\_eval

```python
def get_eval(experiment_id: str, eval_id: str) -> EvalRecord | None
```

Retrieves an evaluation record associated with a given experiment and evaluation ID

**Arguments**:

- `experiment_id` _str_ - the experiment id
- `eval_id` _str_ - id of the specific evaluation to retrieve
  

**Returns**:

  EvalRecord | None: Returns `None` if no such record exists.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_eval("experiment_id", "eval_id")

EvalRecord(
    id="eval-001",
    dataset_id="ds-abc",
    inputs={"question": "What is 2+2?"},
    outputs={"answer": "4"},
    scores={"accuracy": 1.0},
    metadata={"source": "test-set"},
    created_at=datetime(2024, 6, 1, 12, 0, 0),
    updated_at=datetime(2024, 6, 1, 12, 0, 0),
    trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
    annotations=None
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_eval_columns"></a>

#### get\_experiment\_eval\_columns

```python
def get_experiment_eval_columns(
    experiment_id: str,
    dataset_id: str | None = None
) -> EvalColumns
```

Returns all evals for the experiment with their inputs, outputs, refs, and scores.

**Arguments**:

- `dataset_id` - dataset_id for filtering
- `experiment_id` - The unique identifier of the experiment.
  

**Returns**:

- `list[EvalColumns]` - All evals with scoring-relevant fields.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_eval_typed_columns"></a>

#### get\_experiment\_eval\_typed\_columns

```python
def get_experiment_eval_typed_columns(
    experiment_id: str,
    dataset_id: str | None = None
) -> EvalTypedColumns
```

Like get_experiment_eval_columns but also returns the SQLite type for each key.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_trace_columns"></a>

#### get\_experiment\_trace\_columns

```python
def get_experiment_trace_columns(experiment_id: str) -> TraceColumns
```

Return distinct attribute keys from all spans in an experiment.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_experiment_trace_typed_columns"></a>

#### get\_experiment\_trace\_typed\_columns

```python
def get_experiment_trace_typed_columns(experiment_id: str) -> TraceTypedColumns
```

Like get_experiment_trace_columns but also returns the type for each key.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.resolve_evals_sort_column"></a>

#### resolve\_evals\_sort\_column

```python
def resolve_evals_sort_column(experiment_id: str, sort_by: str) -> str | None
```

Resolves the json_sort_column for get_experiment_evals.

- None        → sort_by is a standard evals column
- "scores"    → sort_by is a score key
- "inputs"    → sort_by is a input key
- "outputs"   → sort_by is a output key
- "refs"      → sort_by is a ref key
- raises ValueError → sort_by is unknown

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_evals_average_scores"></a>

#### get\_evals\_average\_scores

```python
def get_evals_average_scores(
    experiment_id: str,
    dataset_id: str | None = None
) -> dict[str, float]
```

Calculates the average scores for evaluations from a specified experiment and optionally
filters them by a specific dataset.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment from which to fetch
  evaluation data.
- `dataset_id` _str | None, optional_ - The unique identifier of the dataset to filter
  evaluations. If not provided, all datasets within the experiment will be considered.
  

**Returns**:

  dict[str, float]: A dictionary where the keys are evaluation metric names and the values
  are their corresponding average scores.

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_eval_annotation"></a>

#### log\_eval\_annotation

```python
def log_eval_annotation(
    experiment_id: str,
    dataset_id: str,
    eval_id: str,
    name: str,
    annotation_kind: AnnotationKind,
    value_type: AnnotationValueType,
    value: int | bool | str,
    user: str,
    rationale: str | None = None
) -> AnnotationRecord
```

Logs an annotation for a specific evaluation within an experiment and records it in the database.

This function stores metadata, rationale, and value of the annotation associated with a specific
evaluation ID. It ensures the consistency of the annotation's type and validates the necessary
conditions before committing the record into the database.

**Arguments**:

- `experiment_id` _str_ - The id of the experiment.
- `dataset_id` _str_ - The id of the dataset within the experiment.
- `eval_id` _str_ - The id of the eval within the dataset.
- `name` _str_ - The name of the annotation being logged.
- `annotation_kind` _AnnotationKind_ - The type of the annotation
- `value_type` _AnnotationValueType_ - Defines the expected type of the annotation value.
- `value` _int | bool | str_ - The actual value of the annotation.
- `user` _str_ - The user who created the annotation.
- `rationale` _str | None_ - The rationale or reasoning behind the annotation, if applicable.
  

**Returns**:

- `AnnotationRecord` - Object containing the logged annotation's details from the database.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
record = backend.log_eval_annotation(
    experiment_id="exp-001",
    dataset_id="dataset-abc",
    eval_id="eval-xyz",
    name="quality",
    annotation_kind=AnnotationKind.FEEDBACK,
    value_type=AnnotationValueType.BOOL,
    value=True,
    user="alice",
    rationale="Looks correct",
)

AnnotationRecord(
    id="annot-001",
    name="quality",
    annotation_kind=AnnotationKind.FEEDBACK,
    value=True,
    user="alice",
    value_type=AnnotationValueType.BOOL,
    created_at=datetime(2024, 6, 1, 10, 0, 0),
    rationale="Looks correct"
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_eval_annotations"></a>

#### get\_eval\_annotations

```python
def get_eval_annotations(
    experiment_id: str,
    dataset_id: str,
    eval_id: str
) -> list[AnnotationRecord]
```

Retrieves evaluation annotations associated with a specific experiment, dataset,
and evaluation identifier. The annotations are fetched from a database table and
returned as a list of AnnotationRecord objects.

**Arguments**:

- `experiment_id` - Unique identifier for the experiment.
- `dataset_id` - Unique identifier for the dataset within the experiment.
- `eval_id` - Unique identifier for the evaluation phase.
  

**Returns**:

  A list of AnnotationRecord objects representing the annotations retrieved for the
  specified dataset and evaluation phase. Returns an empty list if annotation
  tables are not available for the given experiment.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_eval_annotations("exp-001", "dataset-abc", "eval-xyz")

[
    AnnotationRecord(
        id="annot-001",
        name="quality",
        annotation_kind=AnnotationKind.FEEDBACK,
        value=True,
        user="alice",
        value_type=AnnotationValueType.BOOL,
        created_at=datetime(2024, 6, 1, 10, 0, 0),
        rationale="Looks correct"
    )
]
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.log_span_annotation"></a>

#### log\_span\_annotation

```python
def log_span_annotation(
    experiment_id: str,
    trace_id: str,
    span_id: str,
    name: str,
    annotation_kind: AnnotationKind,
    value_type: AnnotationValueType,
    value: int | bool | str,
    user: str,
    rationale: str | None = None
) -> AnnotationRecord
```

Logs a span annotation for a specific experiment, enabling traceability and observability within
the system. This method ensures that the provided annotation is valid, persists the annotation
data in the experiment database, and retrieves the newly created annotation record.

**Arguments**:

- `experiment_id` _str_ - Identifier for the experiment where the annotation will be logged.
- `trace_id` _str_ - Identifier for the trace to which the span belongs.
- `span_id` _str_ - Identifier for the span to be annotated.
- `name` _str_ - Name of the annotation being logged.
- `annotation_kind` _AnnotationKind_ - Type or category of the annotation, specifying its role or
  purpose.
- `value_type` _AnnotationValueType_ - Data type of the annotation's value, ensuring compatibility
  and validity.
- `value` _int | bool | str_ - The actual value associated with the annotation, adhering to the
  specified value type.
- `user` _str_ - Identifier of the user or system initiating the creation of the annotation.
- `rationale` _str | None_ - Optional explanation or justification for the annotation.
  

**Returns**:

- `AnnotationRecord` - An object containing the details of the newly created annotation, including
  associated metadata and identifier.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
record = backend.log_span_annotation(
    experiment_id="exp-001",
    trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    span_id="span-abc",
    name="latency_ok",
    annotation_kind=AnnotationKind.FEEDBACK,
    value_type=AnnotationValueType.BOOL,
    value=True,
    user="alice",
)

AnnotationRecord(
    id="annot-002",
    name="latency_ok",
    annotation_kind=AnnotationKind.FEEDBACK,
    value=True,
    user="alice",
    value_type=AnnotationValueType.BOOL,
    created_at=datetime(2024, 6, 1, 10, 0, 0),
    rationale=None,
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_span_annotations"></a>

#### get\_span\_annotations

```python
def get_span_annotations(
    experiment_id: str,
    trace_id: str,
    span_id: str
) -> list[AnnotationRecord]
```

Fetches annotations for a specific span in a trace within the context of an experiment.

This method retrieves all annotations associated with a span, identified by its trace
and span IDs, within a given experiment. The annotations are returned as a list of
`AnnotationRecord` objects, sorted by their creation timestamp. If no annotation tables
exist for the given experiment, an empty list is returned.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment.
- `trace_id` _str_ - The unique identifier of the trace.
- `span_id` _str_ - The unique identifier of the span whose annotations are to be fetched.
  

**Returns**:

- `list[AnnotationRecord]` - A list of annotations for the specified span. If no
  annotations are found, the returned list will be empty.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_span_annotations(
    "exp-001",
    "4bf92f3577b34da6a3ce929d0e0e4736",
    "span-abc",
)

[
    AnnotationRecord(
        id="annot-002",
        name="latency_ok",
        annotation_kind=AnnotationKind.FEEDBACK,
        value=True,
        user="alice",
        value_type=AnnotationValueType.BOOL,
        created_at=datetime(2024, 6, 1, 10, 0, 0),
        rationale=None
    )
]
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.update_annotation"></a>

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

Updates an annotation record in the specified table with the provided fields.

This method allows modification of an existing annotation record by updating its
`value` and/or `rationale` fields in the corresponding database table. The table is
selected based on the target type ("eval" or "span"). If no fields are provided for
update, an error is raised.

**Arguments**:

- `experiment_id` _str_ - The unique identifier for the experiment associated with the
  annotation.
- `annotation_id` _str_ - The unique identifier for the annotation to be updated.
- `target` _Literal["eval", "span"]_ - Specifies the annotation table to use. "eval"
  refers to evaluation annotations and "span" refers to span annotations.
- `value` _int | bool | str | None, optional_ - The new value to set for the annotation.
  If not provided, the value field will not be updated.
- `rationale` _str | None, optional_ - The new rationale to set for the annotation. If
  not provided, the rationale field will not be updated.
  

**Returns**:

- `AnnotationRecord` - An updated annotation record object after the update operation.
  

**Raises**:

- `ValueError` - If no fields (`value` or `rationale`) are specified for update or if
  the specified annotation does not exist in the database.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.update_annotation(
    experiment_id="exp-001",
    annotation_id="annot-001",
    target="eval",
    value=False,
    rationale="Reconsidered after review",
)

AnnotationRecord(
    id="annot-001",
    name="quality",
    annotation_kind=AnnotationKind.FEEDBACK,
    value=False,
    user="alice",
    value_type=AnnotationValueType.BOOL,
    created_at=datetime(2024, 6, 1, 10, 0, 0),
    rationale="Reconsidered after review",
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.delete_annotation"></a>

#### delete\_annotation

```python
def delete_annotation(
    experiment_id: str,
    annotation_id: str,
    target: Literal["eval", "span"]
) -> None
```

Deletes a specific annotation from the database for a given experiment.

This method removes an annotation identified by its annotation_id from the
appropriate table associated with the target type (either "eval" or "span")
within the specified experiment. If the experiment does not have annotation
tables, the method exits without performing any operation.

**Arguments**:

- `experiment_id` _str_ - The unique identifier for the experiment.
- `annotation_id` _str_ - The unique identifier for the annotation to be deleted.
- `target` _Literal["eval", "span"]_ - Specifies the target table from which the
  annotation should be deleted. Must be either "eval" or "span".
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.delete_annotation("exp-001", "annot-001", target="eval")
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_evals_annotation_summaries"></a>

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
backend = SQLiteBackend("/backend/path")
backend.get_evals_annotation_summaries("exp-001", ["eval-xyz", "eval-abc"])

{
    "eval-xyz": AnnotationSummary(
        feedback=[FeedbackSummaryItem(name="quality", total=2, counts={"true": 1, "false": 1})],
        expectations=[],
    ),
}
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_eval_annotation_summary"></a>

#### get\_eval\_annotation\_summary

```python
def get_eval_annotation_summary(
    experiment_id: str,
    dataset_id: str
) -> AnnotationSummary
```

Retrieves a summary of evaluation annotations for a specific experiment and dataset.

This method queries annotation data associated with the provided experiment
and dataset identifiers, specifically gathering details about feedback and
expectation annotations. Feedback annotations provide a count of distinct
name-value pairs, while expectation annotations summarize details such as
total occurrences, positive and negative boolean counts, and sample values
for non-boolean annotations.

**Arguments**:

- `experiment_id` _str_ - Unique identifier for the experiment to retrieve
  annotation data from.
- `dataset_id` _str_ - Unique identifier for the dataset within the specified
  experiment.
  

**Returns**:

- `AnnotationSummary` - A summary of feedback and expectations contained in
  the evaluation annotations for the given experiment and dataset.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_eval_annotation_summary("exp-001", "dataset-abc")

AnnotationSummary(
    feedback=[FeedbackSummaryItem(name="quality", total=3, counts={"true": 2, "false": 1})],
    expectations=[],
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_traces_annotation_summaries"></a>

#### get\_traces\_annotation\_summaries

```python
def get_traces_annotation_summaries(
    experiment_id: str,
    trace_ids: list[str]
) -> dict[str, AnnotationSummary]
```

Retrieves annotation summaries for specified traces in a given experiment. This method aggregates
feedback and expectation annotations for each trace, combining them to build summaries of annotations.
For annotation kinds, 'feedback' aggregates counts of values, while 'expectation' provides both
aggregate counts and value-specific information.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment.
- `trace_ids` _list[str]_ - A list of trace IDs for which annotation summaries are to be retrieved.
  

**Returns**:

  dict[str, AnnotationSummary]: A dictionary mapping each trace ID to its annotation summary.
  If no annotations are present, or the input trace list is empty, an empty dictionary is returned.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_traces_annotation_summaries(
    "exp-001",
    ["4bf92f3577b34da6a3ce929d0e0e4736", "5bf92f3577b34da6a3ce929d0e0e4737"],
)

{
    "4bf92f3577b34da6a3ce929d0e0e4736": AnnotationSummary(
        feedback=[FeedbackSummaryItem(name="latency_ok", total=1, counts={"true": 1})],
        expectations=[],
    ),
}
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_trace_annotation_summary"></a>

#### get\_trace\_annotation\_summary

```python
def get_trace_annotation_summary(
    experiment_id: str,
    trace_id: str
) -> AnnotationSummary
```

Retrieves the annotation summary for a specific trace in a given experiment. The summary includes
feedback and expectation annotations grouped by name and processed according to their type and values.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment.
- `trace_id` _str_ - The unique identifier of the trace.
  

**Returns**:

- `AnnotationSummary` - An object containing summarized feedback and expectations annotations
  for the specified trace.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_trace_annotation_summary("exp-001", "4bf92f3577b34da6a3ce929d0e0e4736")

AnnotationSummary(
    feedback=[FeedbackSummaryItem(name="latency_ok", total=1, counts={"true": 1})],
    expectations=[],
)
```

<a id="luml.experiments.backends.sqlite.SQLiteBackend.get_all_traces_annotation_summary"></a>

#### get\_all\_traces\_annotation\_summary

```python
def get_all_traces_annotation_summary(experiment_id: str) -> AnnotationSummary
```

Retrieves an annotation summary, including detailed feedback and expectation statistics, for a
specified experiment given its identifier.

This method extracts and organizes data from the annotation tables of an experiment, if available,
to generate a summary of the feedback and expectations associated with that experiment. If the
annotation tables are not present, it will return an empty summary object.

**Arguments**:

- `experiment_id` _str_ - The unique identifier of the experiment from which annotation data
  will be retrieved.
  

**Returns**:

- `AnnotationSummary` - A summary object containing feedback-related statistics and expectation
  values derived from the experiment's annotations.
  

**Example**:

```python
backend = SQLiteBackend("/backend/path")
backend.get_all_traces_annotation_summary("exp-001")

AnnotationSummary(
    feedback=[
        FeedbackSummaryItem(
            name="latency_ok",
            total=5,
            counts={"true": 4, "false": 1}
        )
    ],
    expectations=[]
)
```
