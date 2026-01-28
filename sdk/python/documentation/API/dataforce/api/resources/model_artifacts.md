---
sidebar_label: artifacts
title: dataforce.api.resources.artifacts
---

## ArtifactResourceBase

```python
class ArtifactResourceBase(ABC)
```

Abstract Resource for managing artifacts.

## ArtifactResource

```python
class ArtifactResource(ArtifactResourceBase)
```

Resource for managing artifacts.

#### get

```python
@validate_collection
def get(
    artifact_value: str, *, collection_id: str | None = None
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
  

**Example:**
```python
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  model_by_name = dfs.artifacts.get("my_model")
  model_by_id = dfs.artifacts.get(
      "0199c455-21ee-74c6-b747-19a82f1a1e67"
  )
```
**Example response:**
```python
  Artifact(
      id="0199c455-21ee-74c6-b747-19a82f1a1e67",
      name="my_model",
      file_name="model.fnnx",
      description="Trained model",
      collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
      status=ArtifactStatus.UPLOADED,
      tags=["ml", "production"],
      created_at="2025-01-15T10:30:00.123456Z",
      updated_at=None
  )
```

#### list

```python
@validate_collection
def list(*, collection_id: str | None = None) -> list[Artifact]
```

List all artifacts in the collection.

If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to list artifacts from. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  List of Artifact objects.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:
```python
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  artifacts = dfs.artifacts.list()
```

**Example response:**
```python
  [
      Artifact(
          id="0199c455-21ee-74c6-b747-19a82f1a1e67",
          name="my_model",
          file_name="model.fnnx",
          description="Trained model",
          collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
          status=ArtifactStatus.UPLOADED,
          tags=["ml", "production"],
          created_at="2025-01-15T10:30:00.123456Z",
          updated_at=None
      )
  ]
```
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
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  url_info = dfs.artifacts.download_url(
      "0199c455-21ee-74c6-b747-19a82f1a1e67"
  )
  download_url = url_info["url"]
```
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
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  url_info = dfs.artifacts.delete_url(
      "0199c455-21ee-74c6-b747-19a82f1a1e67"
  )
```
#### upload

```python
@validate_collection
def upload(
    file_path: str,
    name: str,
    description: str | None = None,
    tags: list[str] | None = None,
    *,
    collection_id: str | None = None
) -> Artifact
```

Upload artifact file to the collection.

Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `file_path` - Path to the local model file to upload.
- `name` - Name for the artifact.
- `description` - Optional description of the model.
- `tags` - Optional list of tags for organizing artifacts.
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
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  model = dfs.artifacts.upload(
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
      file_name="output.dfs",
      name="500mb",
      description=None,
      extra_values={
          "F1": 0.9598319029897976,
          "ACC": 0.9600000000000002,
          "BACC": 0.96,
          "B_F1": 0.9598319029897976,
          "SCORE": 0.96
      },
      manifest={
          "variant": "pipeline",
          "name": None,
          "version": None,
          "description": "",
          "producer_name": "falcon.beastbyte.ai",
          "producer_version": "0.8.0"
      },
      file_hash="b128c34757114835c4bf690a87e7cbe",
      size=524062720,
      unique_identifier="b31fa3cb54aa453d9ca625aa24617e7a",
      status=ArtifactStatus.UPLOADED,
      tags=None,
      created_at="2025-08-25T09:15:15.524206Z",
      updated_at="2025-08-25T09:16:05.816506Z"
  )
```
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
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  # Download with original filename
  dfs.artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e67")
  
  # Download to specific path
  dfs.artifacts.download(
      "0199c455-21ee-74c6-b747-19a82f1a1e67",
      file_path="/local/path/downloaded_model.fnnx",
      collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
```
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
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None
) -> dict[str, str | Artifact]
```

Create new artifact record with upload URL.

Creates a artifact record and returns an upload URL for file storage.
If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to create model in.
- `file_name` - Name of the model file.
- `extra_values` - Model performance extra_values.
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

- `file_name`0 - If collection_id not provided and
  no default collection set.
  

**Example**:
```python
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  result = dfs.artifacts.create(
      file_name="model.fnnx",
      extra_values={"accuracy": 0.95},
      manifest={"version": "1.0"},
      file_hash="abc123",
      file_index={"layer1": (0, 1024)},
      size=1048576,
      name="Test Model"
  )
  upload_url = result["url"]
  model = result["model"]
```
#### update

```python
@validate_collection
def update(
    artifact_id: str,
    file_name: str | None = None,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    status: ArtifactStatus | None = None,
    *,
    collection_id: str | None = None
) -> Artifact
```

Update artifact metadata.

Updates the artifact"s metadata. Only provided parameters will be
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
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  model = dfs.artifacts.update(
      "0199c455-21ee-74c6-b747-19a82f1a1e67",
      name="Updated Model",
      status=ArtifactStatus.UPLOADED
  )
```
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
  dfs = DataForceClient(
      api_key="dfs_your_key",
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  dfs.artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e67")
```

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

## AsyncArtifactResource

```python
class AsyncArtifactResource(ArtifactResourceBase)
```

Resource for managing artifacts for async client.

#### get

```python
@validate_collection
async def get(
    artifact_value: str, *, collection_id: str | None = None
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

  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      model_by_name = await dfs.artifacts.get("my_model")
      model_by_id = await dfs.artifacts.get(
          "0199c455-21ee-74c6-b747-19a82f1a1e67"
      )
  
  Example response:
  Artifact(
      id="0199c455-21ee-74c6-b747-19a82f1a1e67",
      name="my_model",
      file_name="model.fnnx",
      description="Trained model",
      collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
      status=ArtifactStatus.UPLOADED,
      tags=["ml", "production"],
      created_at="2025-01-15T10:30:00.123456Z",
      updated_at=None
  )

#### list

```python
@validate_collection
async def list(*, collection_id: str | None = None) -> list[Artifact]
```

List all artifacts in the collection.

If collection_id is None, uses the default collection from client.

**Arguments**:

- `collection_id` - ID of the collection to list artifacts from. If not provided,
  uses the default collection set in the client.
  

**Returns**:

  List of Artifact objects.
  

**Raises**:

- `ConfigurationError` - If collection_id not provided and
  no default collection set.
  

**Example**:
```python
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      artifacts = await dfs.artifacts.list()
  
  Example response:
  [
      Artifact(
          id="0199c455-21ee-74c6-b747-19a82f1a1e67",
          name="my_model",
          file_name="model.fnnx",
          description="Trained model",
          collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
          status=ArtifactStatus.UPLOADED,
          tags=["ml", "production"],
          created_at="2025-01-15T10:30:00.123456Z",
          updated_at=None
      )
  ]
```
#### download\_url

```python
@validate_collection
async def download_url(
    artifact_id: str, *, collection_id: str | None = None
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
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      url_info = await dfs.artifacts.download_url(
          "0199c455-21ee-74c6-b747-19a82f1a1e67"
      )
```
#### delete\_url

```python
@validate_collection
async def delete_url(
    artifact_id: str, *, collection_id: str | None = None
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
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      url_info = await dfs.artifacts.delete_url(
          "0199c455-21ee-74c6-b747-19a82f1a1e67"
      )
```
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
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None
) -> dict[str, str | Artifact]
```

Create new artifact record with upload URL.

Creates a artifact record and returns an upload URL for file storage.
If collection_id is None, uses the default collection from client

**Arguments**:

- `collection_id` - ID of the collection to create model in.
- `file_name` - Name of the model file.
- `extra_values` - Model performance extra_values.
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

- `file_name`0 - If collection_id not provided and
  no default collection set.
  

**Example**:
```python
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      result = await dfs.artifacts.create(
          file_name="model.fnnx",
          extra_values={"accuracy": 0.95},
          manifest={"version": "1.0"},
          file_hash="abc123",
          file_index={"layer1": (0, 1024)},
          size=1048576,
          name="Test Model"
      )
```
#### upload

```python
@validate_collection
async def upload(
    file_path: str,
    name: str,
    description: str | None = None,
    tags: list[str] | None = None,
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
- `name` - Name for the artifact.
- `description` - Optional description of the model.
- `tags` - Optional list of tags for organizing artifacts.
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
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      model = await dfs.artifacts.upload(
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
      name="Production Model",
      file_name="model.fnnx",
      description="Trained on latest dataset",
      collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
      status=ArtifactStatus.UPLOADED,
      tags=["ml", "production"],
      created_at="2025-01-15T10:30:00.123456Z",
      updated_at="2025-01-15T10:35:00.123456Z"
  )
```
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
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      # Download with original filename
      await dfs.artifacts.download(
          "0199c455-21ee-74c6-b747-19a82f1a1e67"
      )
  ...
      # Download to specific path
      await dfs.artifacts.download(
          "0199c455-21ee-74c6-b747-19a82f1a1e67",
          file_path="/local/path/downloaded_model.fnnx",
          collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
      )
```
#### update

```python
@validate_collection
async def update(
    artifact_id: str,
    file_name: str | None = None,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    status: ArtifactStatus | None = None,
    *,
    collection_id: str | None = None
) -> Artifact
```

Update artifact metadata.

Updates the artifact"s metadata. Only provided parameters will be
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
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      model = await dfs.artifacts.update(
          "0199c455-21ee-74c6-b747-19a82f1a1e67",
          name="Updated Model",
          status=ArtifactStatus.UPLOADED
      )
```
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
  dfs = AsyncDataForceClient(
      api_key="dfs_your_key",
  )
  dfs.setup_config(
      organization="0199c455-21ec-7c74-8efe-41470e29bae5",
      orbit="0199c455-21ed-7aba-9fe5-5231611220de",
      collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  )
  async def main():
      await dfs.artifacts.delete(
          "0199c455-21ee-74c6-b747-19a82f1a1e67"
      )
```

**Warnings**:

  This operation is irreversible. The model file and all metadata
  will be permanently lost from database, but you can still
  find model in your storage.

