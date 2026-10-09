<a id="luml_api._types"></a>

# luml_api._types

<a id="luml_api._types.BucketType"></a>

## BucketType Objects

```python
class BucketType(StrEnum)
```

Options: "s3", "azure

<a id="luml_api._types.CollectionType"></a>

## CollectionType Objects

```python
class CollectionType(StrEnum)
```

Options: "model", "dataset", "experiment", "model_dataset",
"dataset_experiment", "model_experiment", "mixed".

<a id="luml_api._types.CollectionTypeFilter"></a>

## CollectionTypeFilter Objects

```python
class CollectionTypeFilter(StrEnum)
```

Options: "model", "dataset", "experiment", "mixed".

<a id="luml_api._types.ArtifactType"></a>

## ArtifactType Objects

```python
class ArtifactType(StrEnum)
```

Options: "model", "experiment", "dataset"

<a id="luml_api._types.ArtifactStatus"></a>

## ArtifactStatus Objects

```python
class ArtifactStatus(StrEnum)
```

Options: "pending_upload", "uploaded", "upload_failed", "deletion_failed"

<a id="luml_api._types.ArtifactSortBy"></a>

## ArtifactSortBy Objects

```python
class ArtifactSortBy(StrEnum)
```

Options: "created_at", "name", "description", "size", "status", "type"

<a id="luml_api._types.SortOrder"></a>

## SortOrder Objects

```python
class SortOrder(StrEnum)
```

Options: "asc", "desc"

<a id="luml_api._types.CollectionSortBy"></a>

## CollectionSortBy Objects

```python
class CollectionSortBy(StrEnum)
```

Options: "created_at", "name", "description", "type", "total_artifacts"

<a id="luml_api._types.Deployment"></a>

## Deployment Objects

```python
class Deployment(BaseModel)
```

A model deployment on a Satellite, as the Platform records it.

<a id="luml_api._types.Satellite"></a>

## Satellite Objects

```python
class Satellite(_SatelliteRecord)
```

A Satellite record bound to its Platform and machine APIs.

<a id="luml_api._types.Satellite.operations"></a>

#### operations

```python
def operations(facet: str | None = None) -> list[dict[str, Any]]
```

List the Satellite's endpoints from its stored OpenAPI document.

The document is the one the Satellite pushed to the Platform when it
paired; the Satellite itself is not contacted. Each entry describes one
operation: method, path template, summary, description, parameters and
security.

**Arguments**:

- `facet` - Only list operations tagged with this facet id, for example "deployment:monitoring". None lists every operation.
  

**Returns**:

  list of dicts with "method", "path", "summary", "description",
  "parameters" and "security".
  

**Raises**:

- `LumlAPIError` - If the Satellite paired without an OpenAPI document, so no description is available.
  

**Example**:

```python
satellite = luml.satellites.get("0199c9cd-3e36-72c0-b823-040eb8195067")
operations = satellite.operations(facet="deployment:monitoring")
```

<a id="luml_api._types.Satellite.request"></a>

#### request

```python
def request(method: str, path: str, **kwargs: Any) -> Any
```

Perform one HTTP call against the Satellite's own API.

Sends the request with the client's bearer key and returns the parsed
JSON as-is. Use it together with `operations()` to call endpoints the SDK
has no native method for, such as a custom capability's routes.

**Arguments**:

- `method` - HTTP method, for example "GET".
- `path` - Path relative to the Satellite's base URL, or an absolute URL on the same origin. Any other origin raises before a request is sent, so the key cannot leak to a foreign host.
- `**kwargs` - Passed to the underlying HTTP client, for example `params` or `json`.
  

**Returns**:

  The Satellite's parsed JSON response.
  

**Raises**:

- `LumlAPIError` - If `path` resolves to a different origin than the Satellite's base URL.
- `APIStatusError` - Subclass matching the HTTP error status, if any.
  

**Example**:

```python
satellite = luml.satellites.get("0199c9cd-3e36-72c0-b823-040eb8195067")
health = satellite.request("GET", "/healthz")
```

<a id="luml_api._types.AsyncSatellite"></a>

## AsyncSatellite Objects

```python
class AsyncSatellite(_SatelliteRecord)
```

Async Satellite record bound to its Platform and machine APIs.

<a id="luml_api._types.AsyncSatellite.operations"></a>

#### operations

```python
async def operations(facet: str | None = None) -> list[dict[str, Any]]
```

List the Satellite's endpoints from its stored OpenAPI document.

Async variant of `Satellite.operations`.

<a id="luml_api._types.AsyncSatellite.request"></a>

#### request

```python
async def request(method: str, path: str, **kwargs: Any) -> Any
```

Perform one HTTP call against the Satellite's own API.

Async variant of `Satellite.request`.

