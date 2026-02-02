<a id="luml.api.resources.artifacts"></a>

# luml.api.resources.artifacts

<a id="luml.api.resources.artifacts.ArtifactResource"></a>

## ArtifactResource Objects

```python
class ArtifactResource(ArtifactResourceBase, ListedResource)
```

Resource for managing artifacts.

<a id="luml.api.resources.artifacts.ArtifactResource.get"></a>

#### get

```python
@validate_collection
def get(
    artifact_value: str,
    *,
    collection_id: str | None = None
) -> Artifact | None
```

Get artifact by ID or name.

Retrieves artifact details by its ID or name (name or file_name).
Search by name is case-sensitive and matches exact model or file name.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_value` - The ID or exact name of the artifact to retrieve.
- `collection_id` - ID of the collection to search in. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Artifact object.
  
  Returns None if artifact with the specified ID or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If there are several artifacts
  with that name.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
artifact_by_name = luml.artifacts.get("my_model")
artifact_by_id = luml.artifacts.get(
    "0199c455-21ee-74c6-b747-19a82f1a1e67"
)
```
  
  Example response:
```python
Artifact(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="my_model",
    file_name="model.fnnx",
    description="Trained model",
    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
    manifest={
        "variant": "pipeline",
        "name": None,
        "version": None,
        "description": "",
        "producer_name": "falcon.beastbyte.ai",
        "producer_version": "0.8.0",
        "producer_tags": [
            "falcon.beastbyte.ai::tabular_regression:v1",
            "dataforce.studio::tabular_regression:v1",
        ],
        "inputs": [
            {
                "name": "age",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                "shape": ["batch", 1],
            },
        ],
        "outputs": [
            {
                "name": "y_pred",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": None,
                "shape": ["batch", 1],
            }
        ],
        "dynamic_attributes": [],
        "env_vars": [],
    },
    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
    file_index = {
        "env.json": (3584, 2),
        "ops.json": (7168, 1869),
        "meta.json": (239616, 3279),
        "dtypes.json": (238592, 2),
        "manifest.json": (512, 2353),
        "variant_config.json": (4608, 372),
        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
    },
    size=245760,
    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
    status='pending_upload',
    type='model',
    tags=["ml", "production"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.artifacts.ArtifactResource.list_all"></a>

#### list\_all

```python
@validate_collection
def list_all(
    *,
    collection_id: str | None = None,
    limit: int | None = 100,
    sort_by: str | None = None,
    order: SortOrder = SortOrder.DESC,
    type: ArtifactType | None = None
) -> Iterator[Artifact]
```

List all collection artifacts with auto-paging.

**Arguments**:

- `collection_id` - ID of the collection to list models from. If not provided,
  uses the default collection set in the client.
- `limit` - Page size (default: 100).
- `sort_by` - Field to sort by.
- `Options` - name, created_at, size, description, status
  and any metric key
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `type` - Filter by artifact type: "model", "dataset", or "experiment".
  

**Returns**:

  Artifact objects from all pages.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)

# List all artifacts with default sorting
for artifact in luml.artifacts.list_all(limit=50):
    print(artifact.id)

# List all artifacts sorted by F1 metric
for artifact in luml.artifacts.list_all(
    sort_by="F1",
    order="desc",
    limit=50
):
    print(f"{artifact.name}: F1={artifact.metrics.get('F1')}")

# Filter by artifact type
for artifact in luml.artifacts.list_all(type=ArtifactType.MODEL):
    print(artifact.name)
```

<a id="luml.api.resources.artifacts.ArtifactResource.list"></a>

#### list

```python
@validate_collection
def list(
    *,
    collection_id: str | None = None,
    start_after: str | None = None,
    limit: int | None = 100,
    sort_by: str | None = None,
    order: SortOrder = SortOrder.DESC,
    type: ArtifactType | None = None
) -> ArtifactsList
```

List all artifacts in the collection.

If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to list models from. If not provided,
  uses the default collection set in the client.
- `start_after` - ID of the artifact to start listing from.
- `limit` - Limit number of models per page (default: 100).
- `sort_by` - Field to sort by.
- `Options` - name, created_at, size, description, status
  and any metric key
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `type` - Filter by artifact type: "model", "dataset", or "experiment".
  

**Returns**:

  ArtifactList object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
# Default: sorted by creation time, newest first
artifacts = luml.artifacts.list()

# Sort by size
artifacts = luml.artifacts.list(
    sort_by="size",
    order="desc"
)

# Sort by a specific metric (e.g., F1 score)
artifacts = luml.artifacts.list(
    sort_by="F1",
    order="desc"
)

# Filter by artifact type
artifacts = luml.artifacts.list(type=ArtifactType.MODEL)
```
  
  Example response:
```python
ArtifactsList(
    items=[
        Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
    ],
    cursor="WyIwMTliNDYxZmNmZDk3NTNhYjMwODJlMDUxZDkzZjVkZiIsICIyMDI1LTEyLTIyVDEyOjU0OjA4LjYwMTI5OCswMDowMCIsICJjcmVhdGVkX2F0Il0="
)
```

<a id="luml.api.resources.artifacts.ArtifactResource.download_url"></a>

#### download\_url

```python
@validate_collection
def download_url(artifact_id: str, *, collection_id: str | None = None) -> dict
```

Get download URL for artifact.

Generates a secure download URL for the model file.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to download.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the download URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
url_info = luml.artifacts.download_url(
    "0199c455-21ee-74c6-b747-19a82f1a1e67"
)
download_url = url_info["url"]
```

<a id="luml.api.resources.artifacts.ArtifactResource.delete_url"></a>

#### delete\_url

```python
@validate_collection
def delete_url(artifact_id: str, *, collection_id: str | None = None) -> dict
```

Get delete URL for artifact.

Generates a secure delete URL for the model file in storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to delete from storage.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the delete URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
url_info = luml.artifacts.delete_url(
    "0199c455-21ee-74c6-b747-19a82f1a1e67"
)
```

<a id="luml.api.resources.artifacts.ArtifactResource.upload"></a>

#### upload

```python
@validate_collection
def upload(
    file_path: str,
    name: str | None = None,
    description: str | None = None,
    tags: List[str] | None = None,
    *,
    collection_id: str | None = None
) -> Artifact
```

Upload artifact file to the collection.

Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `file_path` - Path to the local model file to upload.
- `name` - Name for the artifact. If not provided, uses the file name.
- `description` - Optional description of the model.
- `tags` - Optional list of tags for organizing models.
- `collection_id` - ID of the collection to upload to. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `Artifact` - Uploaded artifact object with
  UPLOADED or UPLOAD_FAILED status.
  

**Raises**:

- `FileError` - If file size exceeds 5GB or unsupported format.
- `FileUploadError` - If upload to storage fails.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
artifact = luml.artifacts.upload(
    file_path="/path/to/model.fnnx",
    name="Production Model",
    description="Trained on latest dataset",
    tags=["ml", "production"],
    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
```
  
  Response object:
```python
Artifact(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="my_model",
    file_name="model.fnnx",
    description="Trained model",
    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
    manifest={
        "variant": "pipeline",
        "name": None,
        "version": None,
        "description": "",
        "producer_name": "falcon.beastbyte.ai",
        "producer_version": "0.8.0",
        "producer_tags": [
            "falcon.beastbyte.ai::tabular_regression:v1",
            "dataforce.studio::tabular_regression:v1",
        ],
        "inputs": [
            {
                "name": "age",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                "shape": ["batch", 1],
            },
        ],
        "outputs": [
            {
                "name": "y_pred",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": None,
                "shape": ["batch", 1],
            }
        ],
        "dynamic_attributes": [],
        "env_vars": [],
    },
    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
    file_index = {
        "env.json": (3584, 2),
        "ops.json": (7168, 1869),
        "meta.json": (239616, 3279),
        "dtypes.json": (238592, 2),
        "manifest.json": (512, 2353),
        "variant_config.json": (4608, 372),
        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
    },
    size=245760,
    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
    status='pending_upload',
    type='model',
    tags=["ml", "production"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.artifacts.ArtifactResource.download"></a>

#### download

```python
@validate_collection
def download(
    artifact_id: str,
    file_path: str | None = None,
    *,
    collection_id: str | None = None
) -> None
```

Download artifact file from the collection.

Downloads the model file to local storage with progress tracking.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to download.
- `file_path` - Local path to save the downloaded file. If None,
  uses the original file name.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `None` - File is saved to the specified path.
  

**Raises**:

- `ValueError` - If model with specified ID not found.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
# Download with original filename
luml.artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e67")

# Download to specific path
luml.artifacts.download(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    file_path="/local/path/downloaded_model.fnnx",
    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
```

<a id="luml.api.resources.artifacts.ArtifactResource.create"></a>

#### create

```python
@validate_collection
def create(
    collection_id: str | None,
    file_name: str,
    extra_values: dict,
    manifest: dict,
    file_hash: str,
    file_index: dict[str, tuple[int, int]],
    size: int,
    name: str,
    description: str | None = None,
    tags: List[str] | None = None
) -> CreatedArtifact
```

Create new artifact record with upload URL.

Creates a artifact record and returns an upload URL for file storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to create model in.
- `file_name` - Name of the model file.
- `extra_values` - Model extra values (e.g. performance metrics).
- `manifest` - Model manifest with metadata.
- `file_hash` - SHA hash of the model file.
- `file_index` - File index mapping for efficient access.
- `size` - Size of the model file in bytes.
- `name` - Optional name for the model.
- `description` - Optional description.
- `tags` - Optional list of tags.
  

**Returns**:

  Dictionary containing upload URL and created Artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
result = luml.artifacts.create(
    file_name="model.fnnx",
    extra_values={"accuracy": 0.95},
    manifest={"version": "1.0"},
    file_hash="abc123",
    file_index={"layer1": (0, 1024)},
    size=1048576,
    name="Test Model"
)
upload_url = result.url
artifact = result.artifact
```
  
  Response object:
```python
    CreatedArtifact(
        artifact=Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        ),
        upload_details=UploadDetails(
            url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
            multipart=False,
            bucket_location="my_llm_attachments.pyfnx",
            bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"
        )
    )
```

<a id="luml.api.resources.artifacts.ArtifactResource.update"></a>

#### update

```python
@validate_collection
def update(
    artifact_id: str,
    file_name: str | None = None,
    name: str | None = None,
    description: str | None = None,
    tags: List[str] | None = None,
    status: ArtifactStatus | None = None,
    *,
    collection_id: str | None = None
) -> Artifact
```

Update artifact metadata.

Updates the artifact's metadata. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to update.
- `file_name` - New file name.
- `name` - New model name.
- `description` - New description.
- `tags` - New list of tags.
- `status` - "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
- `collection_id` - ID of the collection containing the model. Optional.
  

**Returns**:

- `Artifact` - Updated artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
artifact = luml.artifacts.update(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    name="Updated Model",
    status="uploaded"
)
```
  
  Example response:
```python
Artifact(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="my_model",
    file_name="model.fnnx",
    description="Trained model",
    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
    manifest={
        "variant": "pipeline",
        "name": None,
        "version": None,
        "description": "",
        "producer_name": "falcon.beastbyte.ai",
        "producer_version": "0.8.0",
        "producer_tags": [
            "falcon.beastbyte.ai::tabular_regression:v1",
            "dataforce.studio::tabular_regression:v1",
        ],
        "inputs": [
            {
                "name": "age",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                "shape": ["batch", 1],
            },
        ],
        "outputs": [
            {
                "name": "y_pred",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": None,
                "shape": ["batch", 1],
            }
        ],
        "dynamic_attributes": [],
        "env_vars": [],
    },
    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
    file_index = {
        "env.json": (3584, 2),
        "ops.json": (7168, 1869),
        "meta.json": (239616, 3279),
        "dtypes.json": (238592, 2),
        "manifest.json": (512, 2353),
        "variant_config.json": (4608, 372),
        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
    },
    size=245760,
    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
    status='pending_upload',
    type='model',
    tags=["ml", "production"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)

<a id="luml.api.resources.artifacts.ArtifactResource.delete"></a>

#### delete

```python
@validate_collection
def delete(artifact_id: str, *, collection_id: str | None = None) -> None
```

Delete artifact permanently.

Permanently removes the artifact record and associated file from storage.
This action cannot be undone. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to delete.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `None` - No return value on successful deletion.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
luml.artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e67")
```
  

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

<a id="luml.api.resources.artifacts.AsyncArtifactResource"></a>

## AsyncArtifactResource Objects

```python
class AsyncArtifactResource(ArtifactResourceBase, ListedResource)
```

Resource for managing artifacts for async client.

<a id="luml.api.resources.artifacts.AsyncArtifactResource.get"></a>

#### get

```python
@validate_collection
async def get(
    artifact_value: str,
    *,
    collection_id: str | None = None
) -> Artifact | None
```

Get artifact by ID or name.

Retrieves artifact details by its ID or name (name or file_name).
Search by name is case-sensitive and matches exact model or file name.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_value` - The ID or exact name of the artifact to retrieve.
- `collection_id` - ID of the collection to search in. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Artifact object.
  
  Returns None if artifact with the specified ID or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If there are several artifacts
  with that name.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    artifact_by_name = await luml.artifacts.get("my_model")
    artifact_by_id = await luml.artifacts.get(
        "0199c455-21ee-74c6-b747-19a82f1a1e67"
    )
```
  
  Example response:
```python
Artifact(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="my_model",
    file_name="model.fnnx",
    description="Trained model",
    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
    manifest={
        "variant": "pipeline",
        "name": None,
        "version": None,
        "description": "",
        "producer_name": "falcon.beastbyte.ai",
        "producer_version": "0.8.0",
        "producer_tags": [
            "falcon.beastbyte.ai::tabular_regression:v1",
            "dataforce.studio::tabular_regression:v1",
        ],
        "inputs": [
            {
                "name": "age",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                "shape": ["batch", 1],
            },
        ],
        "outputs": [
            {
                "name": "y_pred",
                "content_type": "NDJSON",
                "dtype": "Array[float32]",
                "tags": None,
                "shape": ["batch", 1],
            }
        ],
        "dynamic_attributes": [],
        "env_vars": [],
    },
    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
    file_index = {
        "env.json": (3584, 2),
        "ops.json": (7168, 1869),
        "meta.json": (239616, 3279),
        "dtypes.json": (238592, 2),
        "manifest.json": (512, 2353),
        "variant_config.json": (4608, 372),
        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
    },
    size=245760,
    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
    status='pending_upload',
    type='model',
    tags=["ml", "production"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.list_all"></a>

#### list\_all

```python
@validate_collection
def list_all(
    *,
    collection_id: str | None = None,
    limit: int | None = 100,
    sort_by: str | None = None,
    order: SortOrder = SortOrder.DESC,
    type: ArtifactType | None = None
) -> AsyncIterator[Artifact]
```

List all collection artifacts with auto-paging.

**Arguments**:

- `collection_id` - ID of the collection to list models from. If not provided,
  uses the default collection set in the client.
- `limit` - Page size (default: 100).
- `sort_by` - Field to sort by.
- `Options` - name, created_at, size, description, status and any metric key
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `type` - Filter by artifact type: "model", "dataset", or "experiment".
  

**Returns**:

  Artifact objects from all pages.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )

    # List all artifacts with default sorting
    async for artifact in luml.artifacts.list_all(limit=50):
        print(artifact.id)

    # List all artifacts sorted by F1 metric
    async for artifact in luml.artifacts.list_all(
        sort_by="F1",
        order="desc",
        limit=50
    ):
        print(f"{artifact.name}: F1={artifact.metrics.get('F1')}")

    # Filter by artifact type
    async for artifact in luml.artifacts.list_all(
        type=ArtifactType.MODEL
    ):
        print(artifact.name)
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.list"></a>

#### list

```python
@validate_collection
async def list(
    *,
    collection_id: str | None = None,
    start_after: str | None = None,
    limit: int | None = 100,
    sort_by: str | None = None,
    order: SortOrder = SortOrder.DESC,
    type: ArtifactType | None = None
) -> ArtifactsList
```

List all artifacts in the collection.

If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to list models from. If not provided,
  uses the default collection set in the client.
- `start_after` - ID of the artifact to start listing from.
- `limit` - Limit number of models per page (default: 100).
- `sort_by` - Field to sort by.
- `Options` - name, created_at, size, description, status
  and any metric key
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `type` - Filter by artifact type: "model", "dataset", or "experiment".
  

**Returns**:

  ArtifactsList object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    # Default: sorted by creation time, newest first
    artifacts = await luml.artifacts.list()

    # Sort by size
    artifacts = await luml.artifacts.list(
        sort_by="size",
        order="asc"
    )

    # Sort by a specific metric (e.g., F1 score)
    artifacts = await luml.artifacts.list(
        sort_by="F1",
        order="desc"
    )

    # Filter by artifact type
    artifacts = await luml.artifacts.list(type=ArtifactType.MODEL)
```
  
  Example response:
```python
ArtifactsList(
    items=[
        Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
    ],
    cursor="WyIwMTliNDYxZmNmZDk3NTNhYjMwODJlMDUxZDkzZjVkZiIsICIyMDI1LTEyLTIyVDEyOjU0OjA4LjYwMTI5OCswMDowMCIsICJjcmVhdGVkX2F0Il0="
)
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.download_url"></a>

#### download\_url

```python
@validate_collection
async def download_url(
    artifact_id: str,
    *,
    collection_id: str | None = None
) -> dict
```

Get download URL for artifact.

Generates a secure download URL for the model file.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to download.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the download URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
   await  luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    url_info = await luml.artifacts.download_url(
        "0199c455-21ee-74c6-b747-19a82f1a1e67"
    )
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.delete_url"></a>

#### delete\_url

```python
@validate_collection
async def delete_url(
    artifact_id: str,
    *,
    collection_id: str | None = None
) -> dict
```

Get delete URL for artifact.

Generates a secure delete URL for the model file in storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to delete from storage.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the delete URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    url_info = await luml.artifacts.delete_url(
        "0199c455-21ee-74c6-b747-19a82f1a1e67"
    )
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.create"></a>

#### create

```python
@validate_collection
async def create(
    collection_id: str | None,
    file_name: str,
    extra_values: dict,
    manifest: dict,
    file_hash: str,
    file_index: dict[str, tuple[int, int]],
    size: int,
    name: str,
    description: str | None = None,
    tags: List[str] | None = None
) -> CreatedArtifact
```

Create new artifact record with upload URL.

Creates a artifact record and returns an upload URL for file storage.
If collection_id is None, uses the default collection from client

**Arguments**:

- `collection_id` - ID of the collection to create model in.
- `file_name` - Name of the model file.
- `extra_values` - Model extra values (e.g. performance metrics).
- `manifest` - Model manifest with metadata.
- `file_hash` - SHA hash of the model file.
- `file_index` - File index mapping for efficient access.
- `size` - Size of the model file in bytes.
- `name` - Optional name for the model.
- `description` - Optional description.
- `tags` - Optional list of tags.
  

**Returns**:

  Dictionary containing upload URL and created Artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )

    result = await luml.artifacts.create(
        file_name="model.fnnx",
        extra_values={"accuracy": 0.95},
        manifest={"version": "1.0"},
        file_hash="abc123",
        file_index={"layer1": (0, 1024)},
        size=1048576,
        name="Test Model"
    )
```
  
  Response object:
```python
    CreatedArtifact(
        artifact=Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        ),
        upload_details=UploadDetails(
            url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
            multipart=False,
            bucket_location="my_llm_attachments.pyfnx",
            bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"
        )
    )
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.upload"></a>

#### upload

```python
@validate_collection
async def upload(
    file_path: str,
    name: str | None = None,
    description: str | None = None,
    tags: List[str] | None = None,
    *,
    collection_id: str | None = None
) -> Artifact
```

Upload artifact file to the collection.

Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
Maximum file size is 5GB. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `file_path` - Path to the local model file to upload.
- `name` - Name for the artifact. If not provided, uses the file name.
- `description` - Optional description of the model.
- `tags` - Optional list of tags for organizing models.
- `collection_id` - ID of the collection to upload to. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `Artifact` - Uploaded model artifact object with
  UPLOADED or UPLOAD_FAILED status.
  

**Raises**:

- `FileError` - If file size exceeds 5GB or unsupported format.
- `FileUploadError` - If upload to storage fails.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    artifact = await luml.artifacts.upload(
        file_path="/path/to/model.fnnx",
        name="Production Model",
        description="Trained on latest dataset",
        tags=["ml", "production"],
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
```
  
  Response object:
```python
    CreatedArtifact(
        artifact=Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        ),
        upload_details=UploadDetails(
            url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
            multipart=False,
            bucket_location="my_llm_attachments.pyfnx",
            bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"
        )
    )
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.download"></a>

#### download

```python
@validate_collection
async def download(
    artifact_id: str,
    file_path: str | None = None,
    *,
    collection_id: str | None = None
) -> None
```

Download artifact file from the collection.

Downloads the model file to local storage with progress tracking.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to download.
- `file_path` - Local path to save the downloaded file. If None,
  uses the original file name.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `None` - File is saved to the specified path.
  

**Raises**:

- `ValueError` - If model with specified ID not found.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )

    # Download with original filename
    await luml.artifacts.download(
        "0199c455-21ee-74c6-b747-19a82f1a1e67"
    )

    # Download to specific path
    await luml.artifacts.download(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        file_path="/local/path/downloaded_model.fnnx",
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.update"></a>

#### update

```python
@validate_collection
async def update(
    artifact_id: str,
    file_name: str | None = None,
    name: str | None = None,
    description: str | None = None,
    tags: List[str] | None = None,
    status: ArtifactStatus | None = None,
    *,
    collection_id: str | None = None
) -> Artifact
```

Update artifact metadata.

Updates the artifact's metadata. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `artifact_id` - ID of the artifact to update.
- `file_name` - New file name.
- `name` - New model name.
- `description` - New description.
- `tags` - New list of tags.
- `status` - "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
- `collection_id` - ID of the collection containing the model. Optional.
  

**Returns**:

- `Artifact` - Updated artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    artifact = await luml.artifacts.update(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        name="Updated Model",
        status="uploaded"
    )
```

<a id="luml.api.resources.artifacts.AsyncArtifactResource.delete"></a>

#### delete

```python
@validate_collection
async def delete(artifact_id: str, *, collection_id: str | None = None) -> None
```

Delete artifact permanently.

Permanently removes the artifact record and associated file from storage.
This action cannot be undone. If collection_id is None,
uses the default collection from client

**Arguments**:

- `artifact_id` - ID of the artifact to delete.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client
  

**Returns**:

- `None` - No return value on successful deletion
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If artifact with specified ID doesn't exist
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    await luml.artifacts.delete(
        "0199c455-21ee-74c6-b747-19a82f1a1e67"
    )
```
  

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

