<a id="dataforce.api._client"></a>

# dataforce.api.\_client

<a id="dataforce.api._client.AsyncDataForceClient"></a>

## AsyncDataForceClient Objects

```python
class AsyncDataForceClient(DataForceClientBase, AsyncBaseClient)
```

<a id="dataforce.api._client.AsyncDataForceClient.setup_config"></a>

#### setup\_config

```python
async def setup_config(*,
                       organization: str | None = None,
                       orbit: str | None = None,
                       collection: str | None = None) -> None
```

Method for setting default values for AsyncDataForceClient

**Arguments**:

- `organization` - Default organization to use for operations.
  Can be set by organization ID or name.
- `orbit` - Default orbit to use for operations.
  Can be set by organization ID or name.
- `collection` - Default collection to use for operations.
  Can be set by organization ID or name.
  

**Example**:

  >>> dfs = AsyncDataForceClient(api_key="dfs_api_key")
  >>> async def main():
  ...     await dfs.setup_config(
  ...         "0199c455-21ec-7c74-8efe-41470e29bae5",
  ...         "0199c455-21ed-7aba-9fe5-5231611220de",
  ...         "0199c455-21ee-74c6-b747-19a82f1a1e75"
  ...     )

<a id="dataforce.api._client.AsyncDataForceClient.organizations"></a>

#### organizations

```python
@cached_property
def organizations() -> "AsyncOrganizationResource"
```

Organizations interface.

<a id="dataforce.api._client.AsyncDataForceClient.bucket_secrets"></a>

#### bucket\_secrets

```python
@cached_property
def bucket_secrets() -> "AsyncBucketSecretResource"
```

Bucket Secrets interface.

<a id="dataforce.api._client.AsyncDataForceClient.orbits"></a>

#### orbits

```python
@cached_property
def orbits() -> "AsyncOrbitResource"
```

Orbits interface.

<a id="dataforce.api._client.AsyncDataForceClient.collections"></a>

#### collections

```python
@cached_property
def collections() -> "AsyncCollectionResource"
```

Collections interface.

<a id="dataforce.api._client.AsyncDataForceClient.model_artifacts"></a>

#### model\_artifacts

```python
@cached_property
def model_artifacts() -> "AsyncModelArtifactResource"
```

Model Artifacts interface.

<a id="dataforce.api._client.DataForceClient"></a>

## DataForceClient Objects

```python
class DataForceClient(DataForceClientBase, SyncBaseClient)
```

<a id="dataforce.api._client.DataForceClient.organizations"></a>

#### organizations

```python
@cached_property
def organizations() -> "OrganizationResource"
```

Organizations interface.

<a id="dataforce.api._client.DataForceClient.bucket_secrets"></a>

#### bucket\_secrets

```python
@cached_property
def bucket_secrets() -> "BucketSecretResource"
```

Bucket Secrets interface.

<a id="dataforce.api._client.DataForceClient.orbits"></a>

#### orbits

```python
@cached_property
def orbits() -> "OrbitResource"
```

Orbits interface.

<a id="dataforce.api._client.DataForceClient.collections"></a>

#### collections

```python
@cached_property
def collections() -> "CollectionResource"
```

Collections interface.

<a id="dataforce.api._client.DataForceClient.model_artifacts"></a>

#### model\_artifacts

```python
@cached_property
def model_artifacts() -> "ModelArtifactResource"
```

Model Artifacts interface.

