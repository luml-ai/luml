---
sidebar_label: _client
title: dataforce.api._client
---

## DataForceClientBase

```python
class DataForceClientBase(ABC)
```

Base class for DataForce API clients.

## AsyncDataForceClient

```python
class AsyncDataForceClient(DataForceClientBase, AsyncBaseClient)
```

#### \_\_init\_\_

```python
def __init__(base_url: str | None = None, api_key: str | None = None) -> None
```

Async client for interacting with the DataForce platform API.

**Arguments**:

- `base_url` - Base URL of the DataForce API.
  Defaults to production DataForce Api URL: https://api.dataforce.studio.
  Can also be set in env with name DFS_BASE_URL
- `api_key` - Your DataForce API key for authentication.
  Can also be set in env with name DFS_API_KEY
  

**Attributes**:

- `organizations` - Interface for managing experiments.
- `orbits` - Interface for managing orbits.
- `collections` - Interface for managing collections.
- `bucket_secrets` - Interface for managing bucket secrets.
- `model_artifacts` - Interface for managing model artifacts.
  

**Raises**:

- `AuthenticationError` - If API key is invalid or missing.
- `ConfigurationError` - If required configuration is missing.
- `OrganizationResourceNotFoundError` - If organization not found
  by ID or name passed for client configuration.
- `api_key`0 - If orbit not found by ID or name
  passed for client configuration
- `api_key`1 - If collection not found by ID or
  name passed for client configuration
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_api_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ... )
  
  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_api_key&quot;,
  ...     organization=&quot;My Personal Organization&quot;,
  ...     orbit=&quot;Default Orbit&quot;
  ... )
  

**Notes**:

  Default resource configuration is optional. If no values are provided during
  client initialization and you have only one organization, orbit,
  or collection, the appropriate resource will be automatically set as default
  
  Hierarchy constraints:
  
  - Cannot set default orbit without setting default organization first
  - Cannot set default collection without setting default orbit first
  - Default orbit must belong to the default organization
  - Default collection must belong to the default orbit
  
  You can change default resource after client inizialization
  `api_key`2dfs.organization=4`api_key`2.

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(api_key=&quot;dfs_api_key&quot;)
  &gt;&gt;&gt; async def main():
  ...     await dfs.setup_config(
  ...         &quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         &quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ...     )

#### organizations

```python
@cached_property
def organizations() -> "AsyncOrganizationResource"
```

Organizations interface.

#### bucket\_secrets

```python
@cached_property
def bucket_secrets() -> "AsyncBucketSecretResource"
```

Bucket Secrets interface.

#### orbits

```python
@cached_property
def orbits() -> "AsyncOrbitResource"
```

Orbits interface.

#### collections

```python
@cached_property
def collections() -> "AsyncCollectionResource"
```

Collections interface.

#### model\_artifacts

```python
@cached_property
def model_artifacts() -> "AsyncModelArtifactResource"
```

Model Artifacts interface.

## DataForceClient

```python
class DataForceClient(DataForceClientBase, SyncBaseClient)
```

#### \_\_init\_\_

```python
def __init__(base_url: str | None = None,
             api_key: str | None = None,
             organization: str | None = None,
             orbit: str | None = None,
             collection: str | None = None) -> None
```

Client for interacting with the DataForce platform API.

**Arguments**:

- `base_url` - Base URL of the DataForce API.
  Defaults to production DataForce Api URL: https://api.dataforce.studio.
  Can also be set in env with name DFS_BASE_URL
- `api_key` - Your DataForce API key for authentication.
  Can also be set in env with name DFS_API_KEY
- `organization` - Default organization to use for operations.
  Can be set by organization ID or name.
- `orbit` - Default orbit to use for operations.
  Can be set by organization ID or name.
- `collection` - Default collection to use for operations.
  Can be set by organization ID or name.
  

**Attributes**:

- `organizations` - Interface for managing experiments.
- `orbits` - Interface for managing orbits.
- `collections` - Interface for managing collections.
- `bucket_secrets` - Interface for managing bucket secrets.
- `model_artifacts` - Interface for managing model artifacts.
  

**Raises**:

- `api_key`0 - If API key is invalid or missing.
- `api_key`1 - If required configuration is missing.
- `api_key`2 - If organization not found by ID
  or name passed for client configuration
- `api_key`3 - If orbit not found by ID
  or name passed for client configuration
- `api_key`4 - If collection not found
  by ID or name passed for client configuration
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_api_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ... )
  
  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_api_key&quot;,
  ...     organization=&quot;My Personal Organization&quot;,
  ...     orbit=&quot;Default Orbit&quot;
  ... )
  

**Notes**:

  For long-running operations, consider using the async version:
  AsyncDataForceClient.
  
  Default resource configuration is optional. If no values are provided during
  client initialization and you have only one organization, orbit,
  or collection, the appropriate resource will be automatically set as default
  
  Hierarchy constraints:
  
  - Cannot set default orbit without setting default organization first
  - Cannot set default collection without setting default orbit first
  - Default orbit must belong to the default organization
  - Default collection must belong to the default orbit
  
  You can change default resource after client inizialization
  `api_key`5dfs.organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;`api_key`5.

#### organizations

```python
@cached_property
def organizations() -> "OrganizationResource"
```

Organizations interface.

#### bucket\_secrets

```python
@cached_property
def bucket_secrets() -> "BucketSecretResource"
```

Bucket Secrets interface.

#### orbits

```python
@cached_property
def orbits() -> "OrbitResource"
```

Orbits interface.

#### collections

```python
@cached_property
def collections() -> "CollectionResource"
```

Collections interface.

#### model\_artifacts

```python
@cached_property
def model_artifacts() -> "ModelArtifactResource"
```

Model Artifacts interface.

