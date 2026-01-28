<a id="luml.api._client"></a>

# luml.api._client

<a id="luml.api._client.AsyncLumlClient"></a>

## AsyncLumlClient Objects

```python
class AsyncLumlClient(LumlClientBase, AsyncBaseClient)
```

<a id="luml.api._client.AsyncLumlClient.setup_config"></a>

#### setup_config

```python
async def setup_config(*,
                       organization: str | None = None,
                       orbit: str | None = None,
                       collection: str | None = None) -> None
```

Method for setting default values for AsyncLumlClient

**Arguments**:

- `organization` - Default organization to use for operations.
  Can be set by organization ID or name.
- `orbit` - Default orbit to use for operations.
  Can be set by organization ID or name.
- `collection` - Default collection to use for operations.
  Can be set by organization ID or name.
  

**Example**:

```python
luml = AsyncLumlClient(api_key="luml_api_key")
async def main():
    await luml.setup_config(
        "0199c455-21ec-7c74-8efe-41470e29bae5",
        "0199c455-21ed-7aba-9fe5-5231611220de",
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
```

<a id="luml.api._client.AsyncLumlClient.organizations"></a>

#### organizations

```python
@cached_property
def organizations() -> "AsyncOrganizationResource"
```

Organizations interface.

<a id="luml.api._client.AsyncLumlClient.bucket_secrets"></a>

#### bucket_secrets

```python
@cached_property
def bucket_secrets() -> "AsyncBucketSecretResource"
```

Bucket Secrets interface.

<a id="luml.api._client.AsyncLumlClient.orbits"></a>

#### orbits

```python
@cached_property
def orbits() -> "AsyncOrbitResource"
```

Orbits interface.

<a id="luml.api._client.AsyncLumlClient.collections"></a>

#### collections

```python
@cached_property
def collections() -> "AsyncCollectionResource"
```

Collections interface.

<a id="luml.api._client.AsyncLumlClient.model_artifacts"></a>

#### model_artifacts

```python
@cached_property
def model_artifacts() -> "AsyncModelArtifactResource"
```

Model Artifacts interface.

<a id="luml.api._client.LumlClient"></a>

## LumlClient Objects

```python
class LumlClient(LumlClientBase, SyncBaseClient)
```

<a id="luml.api._client.LumlClient.organizations"></a>

#### organizations

```python
@cached_property
def organizations() -> "OrganizationResource"
```

Organizations interface.

<a id="luml.api._client.LumlClient.bucket_secrets"></a>

#### bucket_secrets

```python
@cached_property
def bucket_secrets() -> "BucketSecretResource"
```

Bucket Secrets interface.

<a id="luml.api._client.LumlClient.orbits"></a>

#### orbits

```python
@cached_property
def orbits() -> "OrbitResource"
```

Orbits interface.

<a id="luml.api._client.LumlClient.collections"></a>

#### collections

```python
@cached_property
def collections() -> "CollectionResource"
```

Collections interface.

<a id="luml.api._client.LumlClient.model_artifacts"></a>

#### model_artifacts

```python
@cached_property
def model_artifacts() -> "ModelArtifactResource"
```

Model Artifacts interface.

