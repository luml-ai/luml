<a id="luml_api._exceptions"></a>

# luml_api._exceptions

Errors raised by the LUML API SDK, and how to tell them apart.

Three families. Only the first descends from `LumlAPIError`; the other two are
plain `Exception` subclasses, so `except LumlAPIError` does not catch them.

```text
LumlAPIError                        base of every SDK error below
├── APIError                        tied to one HTTP request: request, body
│   ├── APIStatusError              the Platform answered 4xx or 5xx
│   │   ├── BadRequestError               400
│   │   ├── AuthenticationError           401
│   │   ├── PermissionDeniedError         403
│   │   ├── NotFoundError                 404
│   │   │   └── SatelliteOutOfSyncError   a Satellite lacks a route it promised
│   │   ├── ConflictError                 409
│   │   ├── UnprocessableEntityError      422
│   │   └── InternalServerError           5xx, or a success body that is not JSON
│   └── APIResponseValidationError        reserved, not raised today
├── ConfigurationError              no default organization, orbit or collection
├── MultipleResourcesFoundError     a name lookup matched several resources
├── CapabilityNotSupportedError     monitoring: the Satellite lacks the capability
├── UnsupportedCapabilityVersionError   monitoring: no common API version
├── NotAvailableInVersionError      monitoring: not part of that API version
└── ContractViolationError          monitoring: the Satellite's answer is malformed

ResourceNotFoundError               client setup: a name or id did not resolve
├── OrganizationResourceNotFoundError
├── OrbitResourceNotFoundError
└── CollectionResourceNotFoundError

FileError                           bucket transfers, and an unsupported file format
├── FileUploadError
└── FileDownloadError
```

### HTTP errors

Every non-success answer of the Platform becomes an `APIStatusError`: the code
is in `status_code`, the `httpx` response in `response`, the parsed JSON body
in `body`, and the Platform's explanation in `body["detail"]`. The codes below
get a subclass of their own; any other 4xx arrives as a plain `APIStatusError`.

- **400** `BadRequestError`: the request makes no sense as such, for example an artifact linked to itself.
- **401** `AuthenticationError`: the API key is missing, expired or invalid.
- **403** `PermissionDeniedError`: the key's role lacks the permission, for example deleting artifacts as an orbit member.
- **404** `NotFoundError`: an unknown id, or an id that belongs to another organization, orbit or collection.
- **409** `ConflictError`: the current state forbids the change, for example a lineage link that already exists, a stage that already holds a version, or a deletion that is already pending.
- **422** `UnprocessableEntityError`: values rejected by validation, for example a lineage depth below 1 or an artifact of another orbit added to a track.
- **5xx** `InternalServerError`: the Platform failed, or answered success with a body that is not JSON.

### Catching errors

- `except APIStatusError` covers every failed request; `except LumlAPIError` adds the configuration, lookup and monitoring errors. Neither covers `ResourceNotFoundError` or `FileError`.
- A lookup by name such as `artifacts.get("churn model")` returns `None` when nothing matches and raises `MultipleResourcesFoundError` when several do; the id is unambiguous.
- `APIResponseValidationError` is exported for forward compatibility only. The resources validate answers with pydantic models, so a payload that does not match raises pydantic's `ValidationError`.

<a id="luml_api._exceptions.LumlAPIError"></a>

## LumlAPIError Objects

```python
class LumlAPIError(Exception)
```

Base class for every error the LUML API SDK raises, except the two
families that are not tied to the API: `ResourceNotFoundError` (client
setup) and `FileError` (bucket transfers).

**Attributes**:

- `message` - Human-readable description, also the exception's string form.

<a id="luml_api._exceptions.CapabilityNotSupportedError"></a>

## CapabilityNotSupportedError Objects

```python
class CapabilityNotSupportedError(LumlAPIError)
```

A Satellite does not have the capability a monitoring call needs.

Raised before any request is sent: the capability is missing from the
Satellite's `present_capabilities` on the Platform record, or the
deployment reports no monitoring URL.

**Attributes**:

- `capability` - Name of the capability, for example `"monitoring"`.
- `satellite_id` - The Satellite that lacks it.
- `deployment_id` - The deployment the call was made for, when known.

<a id="luml_api._exceptions.UnsupportedCapabilityVersionError"></a>

## UnsupportedCapabilityVersionError Objects

```python
class UnsupportedCapabilityVersionError(LumlAPIError)
```

The SDK and the Satellite share no common version of a capability's API.

Upgrading whichever side is behind resolves it.

**Attributes**:

- `capability` - Name of the capability.
- `satellite_id` - The Satellite the call was aimed at.
- `sdk_versions` - API versions this SDK implements, ascending.
- `satellite_versions` - API versions the Satellite advertises, ascending.

<a id="luml_api._exceptions.NotAvailableInVersionError"></a>

## NotAvailableInVersionError Objects

```python
class NotAvailableInVersionError(LumlAPIError)
```

The capability API version negotiated with the Satellite does not include
the requested operation.

**Attributes**:

- `capability` - Name of the capability.
- `operation` - The operation that was requested.
- `api_version` - The version in use, which lacks it.

<a id="luml_api._exceptions.ContractViolationError"></a>

## ContractViolationError Objects

```python
class ContractViolationError(LumlAPIError)
```

A Satellite answered, but the answer lacks the structure its declared API
version requires. The Satellite build is at fault, not the request.

**Attributes**:

- `satellite_id` - The Satellite that answered.
- `operation` - The operation whose answer is malformed.
- `api_version` - The API version the answer was checked against.
- `response` - The decoded answer as received.
- `missing_fields` - Required top-level fields that were absent, sorted; empty when the answer was not a JSON object at all.

<a id="luml_api._exceptions.ConfigurationError"></a>

## ConfigurationError Objects

```python
class ConfigurationError(LumlAPIError)
```

A call needs a default organization, orbit or collection that the client
does not have.

Set the defaults when creating the client, with `setup_config` on the
async client, or pass the id to the call (`collection_id=...`). The message
shows how, and lists the resources available to the API key.

**Attributes**:

- `message` - The explanation, with the available resources appended.

<a id="luml_api._exceptions.MultipleResourcesFoundError"></a>

## MultipleResourcesFoundError Objects

```python
class MultipleResourcesFoundError(LumlAPIError)
```

A lookup by name matched more than one resource.

Names are not unique; the id is. Raised by the `get(...)` methods of the
resources and by the client setup when a name is ambiguous.

<a id="luml_api._exceptions.ResourceNotFoundError"></a>

## ResourceNotFoundError Objects

```python
class ResourceNotFoundError(Exception)
```

A resource the client was configured with does not exist.

Raised while setting the client's defaults, by name or by id. Not a
`LumlAPIError`: catch it, or one of its subclasses, on its own. The message
lists the resources available to the API key.

**Attributes**:

- `message` - The explanation, with the available resources appended.

<a id="luml_api._exceptions.OrbitResourceNotFoundError"></a>

## OrbitResourceNotFoundError Objects

```python
class OrbitResourceNotFoundError(ResourceNotFoundError)
```

The orbit the client was configured with does not exist in the
organization.

<a id="luml_api._exceptions.OrganizationResourceNotFoundError"></a>

## OrganizationResourceNotFoundError Objects

```python
class OrganizationResourceNotFoundError(ResourceNotFoundError)
```

The organization the client was configured with does not exist, or the
API key has no access to it.

<a id="luml_api._exceptions.CollectionResourceNotFoundError"></a>

## CollectionResourceNotFoundError Objects

```python
class CollectionResourceNotFoundError(ResourceNotFoundError)
```

The collection the client was configured with does not exist in the
orbit.

<a id="luml_api._exceptions.APIError"></a>

## APIError Objects

```python
class APIError(LumlAPIError)
```

Base class for errors tied to one HTTP request.

**Attributes**:

- `message` - Human-readable description.
- `request` - The `httpx` request that was sent.
- `body` - The answer's body when there was one: the parsed JSON, or the raw text when it was not JSON.

<a id="luml_api._exceptions.APIResponseValidationError"></a>

## APIResponseValidationError Objects

```python
class APIResponseValidationError(APIError)
```

The Platform answered with success, but the payload does not match the
expected schema.

Exported for forward compatibility and not raised by the current client:
the resources validate answers with pydantic models, so a mismatch surfaces
as pydantic's `ValidationError`.

**Attributes**:

- `response` - The `httpx` response.
- `status_code` - Its HTTP status code.

<a id="luml_api._exceptions.APIStatusError"></a>

## APIStatusError Objects

```python
class APIStatusError(APIError)
```

The Platform answered with a 4xx or 5xx status.

The codes 400, 401, 403, 404, 409, 422 and 5xx raise the subclass listed
in the module overview; any other code raises this class itself. The
message names the method, the URL, the status and the Platform's `detail`.

**Attributes**:

- `response` - The `httpx` response.
- `status_code` - Its HTTP status code.
- `body` - The parsed JSON body; the Platform's explanation is in `body["detail"]`.

<a id="luml_api._exceptions.BadRequestError"></a>

## BadRequestError Objects

```python
class BadRequestError(APIStatusError)
```

HTTP 400: the request makes no sense as such, for example an artifact
linked to itself in the lineage.

<a id="luml_api._exceptions.AuthenticationError"></a>

## AuthenticationError Objects

```python
class AuthenticationError(APIStatusError)
```

HTTP 401: the API key is missing, expired or invalid.

<a id="luml_api._exceptions.PermissionDeniedError"></a>

## PermissionDeniedError Objects

```python
class PermissionDeniedError(APIStatusError)
```

HTTP 403: the API key's role lacks the permission the call needs, for
example deleting artifacts as an orbit member.

<a id="luml_api._exceptions.NotFoundError"></a>

## NotFoundError Objects

```python
class NotFoundError(APIStatusError)
```

HTTP 404: the id does not exist, or belongs to another organization,
orbit or collection than the one addressed.

<a id="luml_api._exceptions.SatelliteOutOfSyncError"></a>

## SatelliteOutOfSyncError Objects

```python
class SatelliteOutOfSyncError(NotFoundError)
```

A Satellite answered `unknown_route` for a monitoring path its stored
capabilities promise.

The Platform's copy of the Satellite's capabilities no longer matches the
running build; restarting or re-pairing the Satellite refreshes it.

**Attributes**:

- `satellite_id` - The Satellite that answered.
- `operation` - The monitoring operation that was requested.
- `api_version` - The capability API version the route belongs to.

<a id="luml_api._exceptions.ConflictError"></a>

## ConflictError Objects

```python
class ConflictError(APIStatusError)
```

HTTP 409: the current state forbids the change, for example a lineage
link that already exists, a stage that already holds a version (pass
`force=True` to displace it), or a deployment deletion that is already
pending.

<a id="luml_api._exceptions.UnprocessableEntityError"></a>

## UnprocessableEntityError Objects

```python
class UnprocessableEntityError(APIStatusError)
```

HTTP 422: the request is well-formed but its values were rejected by
validation, for example a lineage depth below 1 or an artifact of another
orbit added to a track.

<a id="luml_api._exceptions.InternalServerError"></a>

## InternalServerError Objects

```python
class InternalServerError(APIStatusError)
```

HTTP 5xx: the Platform failed to process the request. Also raised when a
success answer carries a body that is not JSON; `body` then holds the raw
text.

<a id="luml_api._exceptions.ArtifactDeleteError"></a>

## ArtifactDeleteError Objects

```python
class ArtifactDeleteError(LumlAPIError)
```

A single artifact stayed in the registry after a deletion attempt.

<a id="luml_api._exceptions.ArtifactBatchDeleteError"></a>

## ArtifactBatchDeleteError Objects

```python
class ArtifactBatchDeleteError(LumlAPIError)
```

A platform request interrupted a batch artifact deletion.

<a id="luml_api._exceptions.FileError"></a>

## FileError Objects

```python
class FileError(Exception)
```

Base class for bucket file transfer errors. Not a `LumlAPIError`.

Raised on its own when a file handed to `upload` has an unsupported
extension; the transfers raise the subclasses below.

<a id="luml_api._exceptions.FileUploadError"></a>

## FileUploadError Objects

```python
class FileUploadError(FileError)
```

Uploading a file to the bucket failed, in a single or a multipart
upload. The artifact is left in `upload_failed`; the message carries the
storage error.

<a id="luml_api._exceptions.FileDownloadError"></a>

## FileDownloadError Objects

```python
class FileDownloadError(FileError)
```

Downloading a file from the bucket failed; the message carries the
storage error.

