<a id="dataforce.api.resources.model_artifacts"></a>

# dataforce.api.resources.model\_artifacts

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource"></a>

## ModelArtifactResource Objects

```python
class ModelArtifactResource(ModelArtifactResourceBase)
```

Resource for managing Model Artifacts.

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.get"></a>

#### get

```python
@validate_collection
def get(model_value: str,
        *,
        collection_id: str | None = None) -> ModelArtifact | None
```

Get model artifact by ID or name.

Retrieves model artifact details by its ID or name (model_name or file_name).
Search by name is case-sensitive and matches exact model or file name.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_value` - The ID or exact name of the model artifact to retrieve.
- `collection_id` - ID of the collection to search in. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  ModelArtifact object.
  
  Returns None if model artifact with the specified ID or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If there are several model artifacts
  with that name.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  ... model_by_name = dfs.model_artifacts.get("my_model")
  ... model_by_id = dfs.model_artifacts.get(
  ...     "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ... )
  
  Example response:
  >>> ModelArtifact(
  ...     id="0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...     model_name="my_model",
  ...     file_name="model.fnnx",
  ...     description="Trained model",
  ...     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=["ml", "production"],
  ...     created_at='2025-01-15T10:30:00.123456Z',
  ...     updated_at=None
  ... )

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.list"></a>

#### list

```python
@validate_collection
def list(*, collection_id: str | None = None) -> list[ModelArtifact]
```

List all model artifacts in the collection.

If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to list models from. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  List of ModelArtifact objects.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> models = dfs.model_artifacts.list()
  
  Example response:
  >>> [
  ...     ModelArtifact(
  ...         id="0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...         model_name="my_model",
  ...         file_name="model.fnnx",
  ...         description="Trained model",
  ...         collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
  ...         status=ModelArtifactStatus.UPLOADED,
  ...         tags=["ml", "production"],
  ...         created_at='2025-01-15T10:30:00.123456Z',
  ...         updated_at=None
  ...     )
  ... ]

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.download_url"></a>

#### download\_url

```python
@validate_collection
def download_url(model_id: str, *, collection_id: str | None = None) -> dict
```

Get download URL for model artifact.

Generates a secure download URL for the model file.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to download.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the download URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  ... url_info = dfs.model_artifacts.download_url(
  ...     "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ... )
  ... download_url = url_info["url"]

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.delete_url"></a>

#### delete\_url

```python
@validate_collection
def delete_url(model_id: str, *, collection_id: str | None = None) -> dict
```

Get delete URL for model artifact.

Generates a secure delete URL for the model file in storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to delete from storage.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the delete URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  ... url_info = dfs.model_artifacts.delete_url(
  ...     "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ... )

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.upload"></a>

#### upload

```python
@validate_collection
def upload(file_path: str,
           model_name: str,
           description: str | None = None,
           tags: builtins.list[str] | None = None,
           *,
           collection_id: str | None = None) -> ModelArtifact
```

Upload model artifact file to the collection.

Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `file_path` - Path to the local model file to upload.
- `model_name` - Name for the model artifact.
- `description` - Optional description of the model.
- `tags` - Optional list of tags for organizing models.
- `collection_id` - ID of the collection to upload to. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `ModelArtifact` - Uploaded model artifact object with
  UPLOADED or UPLOAD_FAILED status.
  

**Raises**:

- `FileError` - If file size exceeds 5GB or unsupported format.
- `FileUploadError` - If upload to storage fails.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> model = dfs.model_artifacts.upload(
  ...     file_path="/path/to/model.fnnx",
  ...     model_name="Production Model",
  ...     description="Trained on latest dataset",
  ...     tags=["ml", "production"],
  ...     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  
  Response object:
  >>> ModelArtifact(
  ...     id="0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
  ...     file_name="output.dfs",
  ...     model_name="500mb",
  ...     description=None,
  ...     metrics=\{
  ...         'F1': 0.9598319029897976,
  ...         'ACC': 0.9600000000000002,
  ...         'BACC': 0.96,
  ...         'B_F1': 0.9598319029897976,
  ...         'SCORE': 0.96
  ...     \},
  ...     manifest=\{
  ...         'variant': 'pipeline',
  ...         'name': None,
  ...         'version': None,
  ...         'description': '',
  ...         'producer_name': 'falcon.beastbyte.ai',
  ...         'producer_version': '0.8.0'
  ...     \},
  ...     file_hash='b128c34757114835c4bf690a87e7cbe',
  ...     size=524062720,
  ...     unique_identifier='b31fa3cb54aa453d9ca625aa24617e7a',
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=None,
  ...     created_at='2025-08-25T09:15:15.524206Z',
  ...     updated_at='2025-08-25T09:16:05.816506Z'
  ... )

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.download"></a>

#### download

```python
@validate_collection
def download(model_id: str,
             file_path: str | None = None,
             *,
             collection_id: str | None = None) -> None
```

Download model artifact file from the collection.

Downloads the model file to local storage with progress tracking.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to download.
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

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> # Download with original filename
  >>> dfs.model_artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e67")
  
  >>> # Download to specific path
  >>> dfs.model_artifacts.download(
  ...     "0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...     file_path="/local/path/downloaded_model.fnnx",
  ...     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.create"></a>

#### create

```python
@validate_collection
def create(
        collection_id: str | None,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None
) -> dict[str, str | ModelArtifact]
```

Create new model artifact record with upload URL.

Creates a model artifact record and returns an upload URL for file storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to create model in.
- `file_name` - Name of the model file.
- `metrics` - Model performance metrics.
- `manifest` - Model manifest with metadata.
- `file_hash` - SHA hash of the model file.
- `file_index` - File index mapping for efficient access.
- `size` - Size of the model file in bytes.
- `model_name` - Optional name for the model.
- `description` - Optional description.
- `tags` - Optional list of tags.
  

**Returns**:

  Dictionary containing upload URL and created ModelArtifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> result = dfs.model_artifacts.create(
  ...     file_name="model.fnnx",
  ...     metrics=\{"accuracy": 0.95\},
  ...     manifest=\{"version": "1.0"\},
  ...     file_hash="abc123",
  ...     file_index=\{"layer1": (0, 1024)\},
  ...     size=1048576,
  ...     model_name="Test Model"
  ... )
  >>> upload_url = result["url"]
  >>> model = result["model"]

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.update"></a>

#### update

```python
@validate_collection
def update(model_id: str,
           file_name: str | None = None,
           model_name: str | None = None,
           description: str | None = None,
           tags: builtins.list[str] | None = None,
           status: ModelArtifactStatus | None = None,
           *,
           collection_id: str | None = None) -> ModelArtifact
```

Update model artifact metadata.

Updates the model artifact's metadata. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to update.
- `file_name` - New file name.
- `model_name` - New model name.
- `description` - New description.
- `tags` - New list of tags.
- `status` - "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
- `collection_id` - ID of the collection containing the model. Optional.
  

**Returns**:

- `ModelArtifact` - Updated model artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> model = dfs.model_artifacts.update(
  ...     "0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...     model_name="Updated Model",
  ...     status=ModelArtifactStatus.UPLOADED
  ... )

<a id="dataforce.api.resources.model_artifacts.ModelArtifactResource.delete"></a>

#### delete

```python
@validate_collection
def delete(model_id: str, *, collection_id: str | None = None) -> None
```

Delete model artifact permanently.

Permanently removes the model artifact record and associated file from storage.
This action cannot be undone. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to delete.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `None` - No return value on successful deletion.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> dfs.model_artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e67")
  

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource"></a>

## AsyncModelArtifactResource Objects

```python
class AsyncModelArtifactResource(ModelArtifactResourceBase)
```

Resource for managing Model Artifacts for async client.

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.get"></a>

#### get

```python
@validate_collection
async def get(model_value: str,
              *,
              collection_id: str | None = None) -> ModelArtifact | None
```

Get model artifact by ID or name.

Retrieves model artifact details by its ID or name (model_name or file_name).
Search by name is case-sensitive and matches exact model or file name.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_value` - The ID or exact name of the model artifact to retrieve.
- `collection_id` - ID of the collection to search in. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  ModelArtifact object.
  
  Returns None if model artifact with the specified ID or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If there are several model artifacts
  with that name.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     model_by_name = await dfs.model_artifacts.get("my_model")
  ...     model_by_id = await dfs.model_artifacts.get(
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ...     )
  
  Example response:
  >>> ModelArtifact(
  ...     id="0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...     model_name="my_model",
  ...     file_name="model.fnnx",
  ...     description="Trained model",
  ...     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=["ml", "production"],
  ...     created_at='2025-01-15T10:30:00.123456Z',
  ...     updated_at=None
  ... )

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.list"></a>

#### list

```python
@validate_collection
async def list(*, collection_id: str | None = None) -> list[ModelArtifact]
```

List all model artifacts in the collection.

If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to list models from. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  List of ModelArtifact objects.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     models = await dfs.model_artifacts.list()
  
  Example response:
  >>> [
  ...     ModelArtifact(
  ...         id="0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...         model_name="my_model",
  ...         file_name="model.fnnx",
  ...         description="Trained model",
  ...         collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
  ...         status=ModelArtifactStatus.UPLOADED,
  ...         tags=["ml", "production"],
  ...         created_at='2025-01-15T10:30:00.123456Z',
  ...         updated_at=None
  ...     )
  ... ]

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.download_url"></a>

#### download\_url

```python
@validate_collection
async def download_url(model_id: str,
                       *,
                       collection_id: str | None = None) -> dict
```

Get download URL for model artifact.

Generates a secure download URL for the model file.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to download.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the download URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     url_info = await dfs.model_artifacts.download_url(
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ...     )

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.delete_url"></a>

#### delete\_url

```python
@validate_collection
async def delete_url(model_id: str,
                     *,
                     collection_id: str | None = None) -> dict
```

Get delete URL for model artifact.

Generates a secure delete URL for the model file in storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to delete from storage.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  Dictionary containing the delete URL.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     url_info = await dfs.model_artifacts.delete_url(
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ...     )

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.create"></a>

#### create

```python
@validate_collection
async def create(
        collection_id: str | None,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None
) -> dict[str, str | ModelArtifact]
```

Create new model artifact record with upload URL.

Creates a model artifact record and returns an upload URL for file storage.
If collection_id is None, uses the default collection from client

**Arguments**:

- `collection_id` - ID of the collection to create model in.
- `file_name` - Name of the model file.
- `metrics` - Model performance metrics.
- `manifest` - Model manifest with metadata.
- `file_hash` - SHA hash of the model file.
- `file_index` - File index mapping for efficient access.
- `size` - Size of the model file in bytes.
- `model_name` - Optional name for the model.
- `description` - Optional description.
- `tags` - Optional list of tags.
  

**Returns**:

  Dictionary containing upload URL and created ModelArtifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     result = await dfs.model_artifacts.create(
  ...         file_name="model.fnnx",
  ...         metrics=\{"accuracy": 0.95\},
  ...         manifest=\{"version": "1.0"\},
  ...         file_hash="abc123",
  ...         file_index=\{"layer1": (0, 1024)\},
  ...         size=1048576,
  ...         model_name="Test Model"
  ...     )

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.upload"></a>

#### upload

```python
@validate_collection
async def upload(file_path: str,
                 model_name: str,
                 description: str | None = None,
                 tags: builtins.list[str] | None = None,
                 *,
                 collection_id: str | None = None) -> ModelArtifact
```

Upload model artifact file to the collection.

Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
Maximum file size is 5GB. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `file_path` - Path to the local model file to upload.
- `model_name` - Name for the model artifact.
- `description` - Optional description of the model.
- `tags` - Optional list of tags for organizing models.
- `collection_id` - ID of the collection to upload to. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `ModelArtifact` - Uploaded model artifact object with
  UPLOADED or UPLOAD_FAILED status.
  

**Raises**:

- `FileError` - If file size exceeds 5GB or unsupported format.
- `FileUploadError` - If upload to storage fails.
- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     model = await dfs.model_artifacts.upload(
  ...         file_path="/path/to/model.fnnx",
  ...         model_name="Production Model",
  ...         description="Trained on latest dataset",
  ...         tags=["ml", "production"],
  ...         collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ...     )
  
  Response object:
  >>> ModelArtifact(
  ...     id="0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...     model_name="Production Model",
  ...     file_name="model.fnnx",
  ...     description="Trained on latest dataset",
  ...     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=["ml", "production"],
  ...     created_at='2025-01-15T10:30:00.123456Z',
  ...     updated_at='2025-01-15T10:35:00.123456Z'
  ... )

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.download"></a>

#### download

```python
@validate_collection
async def download(model_id: str,
                   file_path: str | None = None,
                   *,
                   collection_id: str | None = None) -> None
```

Download model artifact file from the collection.

Downloads the model file to local storage with progress tracking.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to download.
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

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     # Download with original filename
  ...     await dfs.model_artifacts.download(
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ...     )
  ...
  ...     # Download to specific path
  ...     await dfs.model_artifacts.download(
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...         file_path="/local/path/downloaded_model.fnnx",
  ...         collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ...     )

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.update"></a>

#### update

```python
@validate_collection
async def update(model_id: str,
                 file_name: str | None = None,
                 model_name: str | None = None,
                 description: str | None = None,
                 tags: builtins.list[str] | None = None,
                 status: ModelArtifactStatus | None = None,
                 *,
                 collection_id: str | None = None) -> ModelArtifact
```

Update model artifact metadata.

Updates the model artifact's metadata. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to update.
- `file_name` - New file name.
- `model_name` - New model name.
- `description` - New description.
- `tags` - New list of tags.
- `status` - "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
- `collection_id` - ID of the collection containing the model. Optional.
  

**Returns**:

- `ModelArtifact` - Updated model artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  >>>     model = await dfs.model_artifacts.update(
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e67",
  ...         model_name="Updated Model",
  ...         status=ModelArtifactStatus.UPLOADED
  ...     )

<a id="dataforce.api.resources.model_artifacts.AsyncModelArtifactResource.delete"></a>

#### delete

```python
@validate_collection
async def delete(model_id: str, *, collection_id: str | None = None) -> None
```

Delete model artifact permanently.

Permanently removes the model artifact record and associated file from storage.
This action cannot be undone. If collection_id is None,
uses the default collection from client

**Arguments**:

- `model_id` - ID of the model artifact to delete.
- `collection_id` - ID of the collection containing the model. If not provided,
  uses the default collection set in the client
  

**Returns**:

- `None` - No return value on successful deletion
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn't exist
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  ... async def main():
  ...     await dfs.model_artifacts.delete(
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e67"
  ...     )
  

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

