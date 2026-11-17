"""Errors raised by the LUML API SDK, and how to tell them apart.

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

- **400** `BadRequestError`: the request makes no sense as such, for example an
  artifact linked to itself.
- **401** `AuthenticationError`: the API key is missing, expired or invalid.
- **403** `PermissionDeniedError`: the key's role lacks the permission, for
  example deleting artifacts as an orbit member.
- **404** `NotFoundError`: an unknown id, or an id that belongs to another
  organization, orbit or collection.
- **409** `ConflictError`: the current state forbids the change, for example a
  lineage link that already exists, a stage that already holds a version, or a
  deletion that is already pending.
- **422** `UnprocessableEntityError`: values rejected by validation, for example
  a lineage depth below 1 or an artifact of another orbit added to a track.
- **5xx** `InternalServerError`: the Platform failed, or answered success with a
  body that is not JSON.

### Catching errors

- `except APIStatusError` covers every failed request; `except LumlAPIError`
  adds the configuration, lookup and monitoring errors. Neither covers
  `ResourceNotFoundError` or `FileError`.
- A lookup by name such as `artifacts.get("churn model")` returns `None` when
  nothing matches and raises `MultipleResourcesFoundError` when several do;
  the id is unambiguous.
- `APIResponseValidationError` is exported for forward compatibility only. The
  resources validate answers with pydantic models, so a payload that does not
  match raises pydantic's `ValidationError`.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Literal

import httpx

if TYPE_CHECKING:
    from luml_api._types import (
        ArtifactDeleteDeployment,
        ArtifactDeleteFailure,
        ArtifactDeleteReason,
        ArtifactDeleteTrack,
    )


def _format_resources(
    resource_type: str,
    all_values: list | None,
    has_more: bool = False,
) -> str:
    if not all_values:
        return ""

    if len(all_values) == 0:
        return f"\nYou do not have available {resource_type}s yet."

    result = f"\nAvailable {resource_type}s for configuration:"

    for item in all_values:
        result += f'\n      {resource_type}(id={item.id}, name="{item.name}")'

    if has_more:
        result += "..."

    return result


class LumlAPIError(Exception):
    """Base class for every error the LUML API SDK raises, except the two
    families that are not tied to the API: `ResourceNotFoundError` (client
    setup) and `FileError` (bucket transfers).

    Attributes:
        message: Human-readable description, also the exception's string form.
    """

    def __init__(
        self,
        message: str = "LUML Studio API error.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class CapabilityNotSupportedError(LumlAPIError):
    """A Satellite does not have the capability a monitoring call needs.

    Raised before any request is sent: the capability is missing from the
    Satellite's `present_capabilities` on the Platform record, or the
    deployment reports no monitoring URL.

    Attributes:
        capability: Name of the capability, for example `"monitoring"`.
        satellite_id: The Satellite that lacks it.
        deployment_id: The deployment the call was made for, when known.
    """

    capability: str
    satellite_id: str
    deployment_id: str | None

    def __init__(
        self,
        capability: str,
        satellite_id: str,
        *,
        deployment_id: str | None = None,
        message: str | None = None,
    ) -> None:
        self.capability = capability
        self.satellite_id = satellite_id
        self.deployment_id = deployment_id
        super().__init__(
            message
            or f"Satellite {satellite_id} does not support capability {capability!r}"
        )


class UnsupportedCapabilityVersionError(LumlAPIError):
    """The SDK and the Satellite share no common version of a capability's API.

    Upgrading whichever side is behind resolves it.

    Attributes:
        capability: Name of the capability.
        satellite_id: The Satellite the call was aimed at.
        sdk_versions: API versions this SDK implements, ascending.
        satellite_versions: API versions the Satellite advertises, ascending.
    """

    capability: str
    satellite_id: str
    sdk_versions: tuple[int, ...]
    satellite_versions: tuple[int, ...]

    def __init__(
        self,
        capability: str,
        satellite_id: str,
        sdk_versions: Iterable[int],
        satellite_versions: Iterable[int],
    ) -> None:
        self.capability = capability
        self.satellite_id = satellite_id
        self.sdk_versions = tuple(sorted(set(sdk_versions)))
        self.satellite_versions = tuple(sorted(set(satellite_versions)))
        super().__init__(
            f"No common {capability} API version for Satellite {satellite_id}: "
            f"SDK supports {list(self.sdk_versions)}; Satellite advertises "
            f"{list(self.satellite_versions)}"
        )


class NotAvailableInVersionError(LumlAPIError):
    """The capability API version negotiated with the Satellite does not include
    the requested operation.

    Attributes:
        capability: Name of the capability.
        operation: The operation that was requested.
        api_version: The version in use, which lacks it.
    """

    capability: str
    operation: str
    api_version: int

    def __init__(self, capability: str, operation: str, api_version: int) -> None:
        self.capability = capability
        self.operation = operation
        self.api_version = api_version
        super().__init__(
            f"{capability.capitalize()} operation {operation!r} is not available in "
            f"API version {api_version}"
        )


class ContractViolationError(LumlAPIError):
    """A Satellite answered, but the answer lacks the structure its declared API
    version requires. The Satellite build is at fault, not the request.

    Attributes:
        satellite_id: The Satellite that answered.
        operation: The operation whose answer is malformed.
        api_version: The API version the answer was checked against.
        response: The decoded answer as received.
        missing_fields: Required top-level fields that were absent, sorted;
            empty when the answer was not a JSON object at all.
    """

    satellite_id: str
    operation: str
    api_version: int
    response: object
    missing_fields: tuple[str, ...]

    def __init__(
        self,
        satellite_id: str,
        operation: str,
        api_version: int,
        response: object,
        missing_fields: Iterable[str],
    ) -> None:
        self.satellite_id = satellite_id
        self.operation = operation
        self.api_version = api_version
        self.response = response
        self.missing_fields = tuple(sorted(missing_fields))
        detail = (
            f"missing required top-level fields {list(self.missing_fields)}"
            if self.missing_fields
            else "response is not a JSON object"
        )
        super().__init__(
            f"Satellite {satellite_id} violated the monitoring API version "
            f"{api_version} contract for operation {operation!r}: {detail}"
        )


class ConfigurationError(LumlAPIError):
    """A call needs a default organization, orbit or collection that the client
    does not have.

    Set the defaults when creating the client, with `setup_config` on the
    async client, or pass the id to the call (`collection_id=...`). The message
    shows how, and lists the resources available to the API key.

    Attributes:
        message: The explanation, with the available resources appended.
    """

    def __init__(
        self,
        resource_type: str,
        message: str | None = None,
        all_values: list | None = None,
        has_more: bool = False,
    ) -> None:
        self.message = message if message else ""
        self.message += """
        luml = LumlClient(
            api_key="luml_api_key",
            organization=1,
            orbit=1215,
            collection=15
        )
        """
        self.message += _format_resources(resource_type, all_values, has_more)

        super().__init__(self.message)


class MultipleResourcesFoundError(LumlAPIError):
    """A lookup by name matched more than one resource.

    Names are not unique; the id is. Raised by the `get(...)` methods of the
    resources and by the client setup when a name is ambiguous.
    """

    pass


class ResourceNotFoundError(Exception):
    """A resource the client was configured with does not exist.

    Raised while setting the client's defaults, by name or by id. Not a
    `LumlAPIError`: catch it, or one of its subclasses, on its own. The message
    lists the resources available to the API key.

    Attributes:
        message: The explanation, with the available resources appended.
    """

    def __init__(
        self,
        resource_type: str,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        if message:
            self.message = message
        else:
            value_reference = "id" if isinstance(value, int) else "name"
            self.message = (
                f"{resource_type} with {value_reference} '{value}'"
                f" not found. Try to set with another id or name."
            )
        self.message += _format_resources(resource_type, all_values, has_more)

        super().__init__(self.message)


class OrbitResourceNotFoundError(ResourceNotFoundError):
    """The orbit the client was configured with does not exist in the
    organization."""

    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Orbit", value, all_values, has_more, message)


class OrganizationResourceNotFoundError(ResourceNotFoundError):
    """The organization the client was configured with does not exist, or the
    API key has no access to it."""

    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Organization", value, all_values, has_more, message)


class CollectionResourceNotFoundError(ResourceNotFoundError):
    """The collection the client was configured with does not exist in the
    orbit."""

    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Collection", value, all_values, has_more, message)


class APIError(LumlAPIError):
    """Base class for errors tied to one HTTP request.

    Attributes:
        message: Human-readable description.
        request: The `httpx` request that was sent.
        body: The answer's body when there was one: the parsed JSON, or the
            raw text when it was not JSON.
    """

    message: str
    request: httpx.Request
    body: object | None

    def __init__(
        self, message: str, request: httpx.Request, *, body: object | None
    ) -> None:
        super().__init__(message)
        self.request = request
        self.message = message
        self.body = body


class APIResponseValidationError(APIError):
    """The Platform answered with success, but the payload does not match the
    expected schema.

    Exported for forward compatibility and not raised by the current client:
    the resources validate answers with pydantic models, so a mismatch surfaces
    as pydantic's `ValidationError`.

    Attributes:
        response: The `httpx` response.
        status_code: Its HTTP status code.
    """

    response: httpx.Response
    status_code: int

    def __init__(
        self,
        response: httpx.Response,
        body: object | None,
        *,
        message: str | None = None,
    ) -> None:
        super().__init__(
            message or "Data returned by API invalid for expected schema.",
            response.request,
            body=body,
        )
        self.response = response
        self.status_code = response.status_code


class APIStatusError(APIError):
    """The Platform answered with a 4xx or 5xx status.

    The codes 400, 401, 403, 404, 409, 422 and 5xx raise the subclass listed
    in the module overview; any other code raises this class itself. The
    message names the method, the URL, the status and the Platform's `detail`.

    Attributes:
        response: The `httpx` response.
        status_code: Its HTTP status code.
        body: The parsed JSON body; the Platform's explanation is in
            `body["detail"]`.
    """

    response: httpx.Response
    status_code: int

    def __init__(
        self, message: str, *, response: httpx.Response, body: object | None
    ) -> None:
        super().__init__(message, response.request, body=body)
        self.response = response
        self.status_code = response.status_code


class BadRequestError(APIStatusError):
    """HTTP 400: the request makes no sense as such, for example an artifact
    linked to itself in the lineage."""

    status_code: Literal[400] = 400


class AuthenticationError(APIStatusError):
    """HTTP 401: the API key is missing, expired or invalid."""

    status_code: Literal[401] = 401


class PermissionDeniedError(APIStatusError):
    """HTTP 403: the API key's role lacks the permission the call needs, for
    example deleting artifacts as an orbit member."""

    status_code: Literal[403] = 403


class NotFoundError(APIStatusError):
    """HTTP 404: the id does not exist, or belongs to another organization,
    orbit or collection than the one addressed."""

    status_code: Literal[404] = 404


class SatelliteOutOfSyncError(NotFoundError):
    """A Satellite answered `unknown_route` for a monitoring path its stored
    capabilities promise.

    The Platform's copy of the Satellite's capabilities no longer matches the
    running build; restarting or re-pairing the Satellite refreshes it.

    Attributes:
        satellite_id: The Satellite that answered.
        operation: The monitoring operation that was requested.
        api_version: The capability API version the route belongs to.
    """

    satellite_id: str
    operation: str
    api_version: int

    def __init__(
        self,
        satellite_id: str,
        operation: str,
        api_version: int,
        *,
        response: httpx.Response,
        body: object | None,
    ) -> None:
        self.satellite_id = satellite_id
        self.operation = operation
        self.api_version = api_version
        super().__init__(
            f"Satellite {satellite_id} returned unknown_route for monitoring "
            f"operation {operation!r} at API version {api_version}; restart or "
            "re-pair the Satellite so its capabilities match its routes",
            response=response,
            body=body,
        )


class ConflictError(APIStatusError):
    """HTTP 409: the current state forbids the change, for example a lineage
    link that already exists, a stage that already holds a version (pass
    `force=True` to displace it), or a deployment deletion that is already
    pending."""

    status_code: Literal[409] = 409


class UnprocessableEntityError(APIStatusError):
    """HTTP 422: the request is well-formed but its values were rejected by
    validation, for example a lineage depth below 1 or an artifact of another
    orbit added to a track."""

    status_code: Literal[422] = 422


class InternalServerError(APIStatusError):
    """HTTP 5xx: the Platform failed to process the request. Also raised when a
    success answer carries a body that is not JSON; `body` then holds the raw
    text."""

    pass


class ArtifactDeleteError(LumlAPIError):
    """A single artifact stayed in the registry after a deletion attempt."""

    failure: "ArtifactDeleteFailure"
    artifact_id: str
    name: str | None
    reason: "ArtifactDeleteReason"
    deployments: list["ArtifactDeleteDeployment"]
    tracks: list["ArtifactDeleteTrack"]

    def __init__(self, failure: "ArtifactDeleteFailure") -> None:
        self.failure = failure
        self.artifact_id = failure.artifact_id
        self.name = failure.name
        self.reason = failure.reason
        self.deployments = list(failure.deployments)
        self.tracks = list(failure.tracks)
        super().__init__(
            f"Artifact {failure.artifact_id} was not deleted: {failure.reason}"
        )


class ArtifactBatchDeleteError(LumlAPIError):
    """A platform request interrupted a batch artifact deletion."""

    cause: Exception
    deleted: list[str]
    failed: list["ArtifactDeleteFailure"]
    not_completed: list[str]

    def __init__(
        self,
        cause: Exception,
        *,
        deleted: list[str],
        failed: list["ArtifactDeleteFailure"],
        not_completed: list[str],
    ) -> None:
        self.cause = cause
        self.deleted = list(deleted)
        self.failed = list(failed)
        self.not_completed = list(not_completed)
        super().__init__(f"Artifact batch deletion was interrupted: {cause}")


class FileError(Exception):
    """Base class for bucket file transfer errors. Not a `LumlAPIError`.

    Raised on its own when a file handed to `upload` has an unsupported
    extension; the transfers raise the subclasses below."""

    pass


class FileUploadError(FileError):
    """Uploading a file to the bucket failed, in a single or a multipart
    upload. The artifact is left in `upload_failed`; the message carries the
    storage error."""

    def __init__(self, message: str = "") -> None:
        super().__init__("Error uploading file to bucket." + message)


class FileDownloadError(FileError):
    """Downloading a file from the bucket failed; the message carries the
    storage error."""

    def __init__(self, message: str = "") -> None:
        super().__init__("Error downloading file from bucket." + message)
