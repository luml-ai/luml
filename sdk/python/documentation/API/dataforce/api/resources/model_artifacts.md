---
sidebar_label: model_artifacts
title: dataforce.api.resources.model_artifacts
---

## ModelArtifactResourceBase

```python
class ModelArtifactResourceBase(ABC)
```

Abstract Resource for managing Model Artifacts.

## ModelArtifactResource

```python
class ModelArtifactResource(ModelArtifactResourceBase)
```

Resource for managing Model Artifacts.

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  ... model_by_name = dfs.model_artifacts.get(&quot;my_model&quot;)
  ... model_by_id = dfs.model_artifacts.get(
  ...     &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ... )
  
  Example response:
  &gt;&gt;&gt; ModelArtifact(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...     model_name=&quot;my_model&quot;,
  ...     file_name=&quot;model.fnnx&quot;,
  ...     description=&quot;Trained model&quot;,
  ...     collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=[&quot;ml&quot;, &quot;production&quot;],
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; models = dfs.model_artifacts.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     ModelArtifact(
  ...         id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...         model_name=&quot;my_model&quot;,
  ...         file_name=&quot;model.fnnx&quot;,
  ...         description=&quot;Trained model&quot;,
  ...         collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...         status=ModelArtifactStatus.UPLOADED,
  ...         tags=[&quot;ml&quot;, &quot;production&quot;],
  ...         created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...         updated_at=None
  ...     )
  ... ]

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
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  ... url_info = dfs.model_artifacts.download_url(
  ...     &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ... )
  ... download_url = url_info[&quot;url&quot;]

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
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  ... url_info = dfs.model_artifacts.delete_url(
  ...     &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ... )

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; model = dfs.model_artifacts.upload(
  ...     file_path=&quot;/path/to/model.fnnx&quot;,
  ...     model_name=&quot;Production Model&quot;,
  ...     description=&quot;Trained on latest dataset&quot;,
  ...     tags=[&quot;ml&quot;, &quot;production&quot;],
  ...     collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  
  Response object:
  &gt;&gt;&gt; ModelArtifact(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...     collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     file_name=&quot;output.dfs&quot;,
  ...     model_name=&quot;500mb&quot;,
  ...     description=None,
  ...     metrics={
  ...         &#x27;F1&#x27;: 0.9598319029897976,
  ...         &#x27;ACC&#x27;: 0.9600000000000002,
  ...         &#x27;BACC&#x27;: 0.96,
  ...         &#x27;B_F1&#x27;: 0.9598319029897976,
  ...         &#x27;SCORE&#x27;: 0.96
  ...     },
  ...     manifest={
  ...         &#x27;variant&#x27;: &#x27;pipeline&#x27;,
  ...         &#x27;name&#x27;: None,
  ...         &#x27;version&#x27;: None,
  ...         &#x27;description&#x27;: &#x27;&#x27;,
  ...         &#x27;producer_name&#x27;: &#x27;falcon.beastbyte.ai&#x27;,
  ...         &#x27;producer_version&#x27;: &#x27;0.8.0&#x27;
  ...     },
  ...     file_hash=&#x27;b128c34757114835c4bf690a87e7cbe&#x27;,
  ...     size=524062720,
  ...     unique_identifier=&#x27;b31fa3cb54aa453d9ca625aa24617e7a&#x27;,
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=None,
  ...     created_at=&#x27;2025-08-25T09:15:15.524206Z&#x27;,
  ...     updated_at=&#x27;2025-08-25T09:16:05.816506Z&#x27;
  ... )

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; # Download with original filename
  &gt;&gt;&gt; dfs.model_artifacts.download(&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;)
  
  &gt;&gt;&gt; # Download to specific path
  &gt;&gt;&gt; dfs.model_artifacts.download(
  ...     &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...     file_path=&quot;/local/path/downloaded_model.fnnx&quot;,
  ...     collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )

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

- `file_name`0 - If collection_id not provided and
  no default collection set.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; result = dfs.model_artifacts.create(
  ...     file_name=&quot;model.fnnx&quot;,
  ...     metrics={&quot;accuracy&quot;: 0.95},
  ...     manifest={&quot;version&quot;: &quot;1.0&quot;},
  ...     file_hash=&quot;abc123&quot;,
  ...     file_index={&quot;layer1&quot;: (0, 1024)},
  ...     size=1048576,
  ...     model_name=&quot;Test Model&quot;
  ... )
  &gt;&gt;&gt; upload_url = result[&quot;url&quot;]
  &gt;&gt;&gt; model = result[&quot;model&quot;]

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

Updates the model artifact&#x27;s metadata. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to update.
- `file_name` - New file name.
- `model_name` - New model name.
- `description` - New description.
- `tags` - New list of tags.
- `status` - &quot;pending_upload&quot; | &quot;uploaded&quot; | &quot;upload_failed&quot; | &quot;deletion_failed&quot;
- `collection_id` - ID of the collection containing the model. Optional.
  

**Returns**:

- `ModelArtifact` - Updated model artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; model = dfs.model_artifacts.update(
  ...     &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...     model_name=&quot;Updated Model&quot;,
  ...     status=ModelArtifactStatus.UPLOADED
  ... )

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
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; dfs.model_artifacts.delete(&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;)
  

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

## AsyncModelArtifactResource

```python
class AsyncModelArtifactResource(ModelArtifactResourceBase)
```

Resource for managing Model Artifacts for async client.

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     model_by_name = await dfs.model_artifacts.get(&quot;my_model&quot;)
  ...     model_by_id = await dfs.model_artifacts.get(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ...     )
  
  Example response:
  &gt;&gt;&gt; ModelArtifact(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...     model_name=&quot;my_model&quot;,
  ...     file_name=&quot;model.fnnx&quot;,
  ...     description=&quot;Trained model&quot;,
  ...     collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=[&quot;ml&quot;, &quot;production&quot;],
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     models = await dfs.model_artifacts.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     ModelArtifact(
  ...         id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...         model_name=&quot;my_model&quot;,
  ...         file_name=&quot;model.fnnx&quot;,
  ...         description=&quot;Trained model&quot;,
  ...         collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...         status=ModelArtifactStatus.UPLOADED,
  ...         tags=[&quot;ml&quot;, &quot;production&quot;],
  ...         created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...         updated_at=None
  ...     )
  ... ]

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
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     url_info = await dfs.model_artifacts.download_url(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ...     )

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
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     url_info = await dfs.model_artifacts.delete_url(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ...     )

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

- `file_name`0 - If collection_id not provided and
  no default collection set.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     result = await dfs.model_artifacts.create(
  ...         file_name=&quot;model.fnnx&quot;,
  ...         metrics={&quot;accuracy&quot;: 0.95},
  ...         manifest={&quot;version&quot;: &quot;1.0&quot;},
  ...         file_hash=&quot;abc123&quot;,
  ...         file_index={&quot;layer1&quot;: (0, 1024)},
  ...         size=1048576,
  ...         model_name=&quot;Test Model&quot;
  ...     )

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     model = await dfs.model_artifacts.upload(
  ...         file_path=&quot;/path/to/model.fnnx&quot;,
  ...         model_name=&quot;Production Model&quot;,
  ...         description=&quot;Trained on latest dataset&quot;,
  ...         tags=[&quot;ml&quot;, &quot;production&quot;],
  ...         collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ...     )
  
  Response object:
  &gt;&gt;&gt; ModelArtifact(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...     model_name=&quot;Production Model&quot;,
  ...     file_name=&quot;model.fnnx&quot;,
  ...     description=&quot;Trained on latest dataset&quot;,
  ...     collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     status=ModelArtifactStatus.UPLOADED,
  ...     tags=[&quot;ml&quot;, &quot;production&quot;],
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=&#x27;2025-01-15T10:35:00.123456Z&#x27;
  ... )

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     # Download with original filename
  ...     await dfs.model_artifacts.download(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ...     )
  ...
  ...     # Download to specific path
  ...     await dfs.model_artifacts.download(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...         file_path=&quot;/local/path/downloaded_model.fnnx&quot;,
  ...         collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ...     )

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

Updates the model artifact&#x27;s metadata. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
uses the default collection from client.

**Arguments**:

- `model_id` - ID of the model artifact to update.
- `file_name` - New file name.
- `model_name` - New model name.
- `description` - New description.
- `tags` - New list of tags.
- `status` - &quot;pending_upload&quot; | &quot;uploaded&quot; | &quot;upload_failed&quot; | &quot;deletion_failed&quot;
- `collection_id` - ID of the collection containing the model. Optional.
  

**Returns**:

- `ModelArtifact` - Updated model artifact object.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  &gt;&gt;&gt;     model = await dfs.model_artifacts.update(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;,
  ...         model_name=&quot;Updated Model&quot;,
  ...         status=ModelArtifactStatus.UPLOADED
  ...     )

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
- `NotFoundError` - If model artifact with specified ID doesn&#x27;t exist
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  ... async def main():
  ...     await dfs.model_artifacts.delete(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e67&quot;
  ...     )
  

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

