from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from httpx import URL, InvalidURL
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from luml_api._exceptions import LumlAPIError
from luml_api.resources._listed_resource import PaginatedList

if TYPE_CHECKING:
    from luml_api._client import AsyncLumlClient, LumlClient


_OPENAPI_HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)


class BaseOrmConfig:
    model_config = ConfigDict(use_enum_values=True)


def is_uuid(value: str | None) -> bool:
    if value is None:
        return False
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class BucketType(StrEnum):
    """
    Options: "s3", "azure
    """

    S3 = "s3"
    AZURE = "azure"


class CollectionType(StrEnum):
    """
    Options: "model", "dataset", "experiment", "model_dataset",
    "dataset_experiment", "model_experiment", "mixed".
    """

    MODEL = "model"
    DATASET = "dataset"
    EXPERIMENT = "experiment"
    MODEL_DATASET = "model_dataset"
    DATASET_EXPERIMENT = "dataset_experiment"
    MODEL_EXPERIMENT = "model_experiment"
    MIXED = "mixed"


class CollectionTypeFilter(StrEnum):
    """
    Options: "model", "dataset", "experiment", "mixed".
    """

    MODEL = "model"
    DATASET = "dataset"
    EXPERIMENT = "experiment"
    MIXED = "mixed"


class ArtifactType(StrEnum):
    """
    Options: "model", "experiment", "dataset"
    """

    MODEL = "model"
    EXPERIMENT = "experiment"
    DATASET = "dataset"


class ArtifactStatus(StrEnum):
    """
    Options: "pending_upload", "uploaded", "upload_failed", "deletion_failed"
    """

    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    UPLOAD_FAILED = "upload_failed"
    DELETION_FAILED = "deletion_failed"


class ArtifactSortBy(StrEnum):
    """
    Options: "created_at", "name", "description", "size", "status", "type"
    """

    CREATED_AT = "created_at"
    NAME = "name"
    SIZE = "size"
    DESCRIPTION = "description"
    STATUS = "status"
    TYPE = "type"


class SortOrder(StrEnum):
    """
    Options: "asc", "desc"
    """

    ASC = "asc"
    DESC = "desc"


class CollectionSortBy(StrEnum):
    """
    Options: "created_at", "name", "description", "type", "total_artifacts"
    """

    CREATED_AT = "created_at"
    NAME = "name"
    TYPE = "type"
    DESCRIPTION = "description"
    TOTAL_ARTIFACTS = "total_artifacts"


class TrackSortBy(StrEnum):
    NAME = "name"
    DESCRIPTION = "description"
    TOTAL_ENTRIES = "total_entries"
    CREATED_AT = "created_at"


class TrackEntrySortBy(StrEnum):
    ARTIFACT_NAME = "artifact_name"
    DESCRIPTION = "description"
    STAGE = "stage"
    VERSION = "version"
    CREATED_AT = "created_at"


class Organization(BaseModel):
    id: str
    name: str
    logo: str | None = None
    created_at: str
    updated_at: str | None = None


class Orbit(BaseModel):
    id: str
    name: str
    organization_id: str
    bucket_secret_id: str
    total_members: int | None = None
    total_collections: int | None = None
    created_at: str
    updated_at: str | None = None


class OrbitBase(BaseModel):
    id: UUID
    name: str
    created_at: str
    updated_at: str | None = None


class S3BucketSecret(BaseModel, BaseOrmConfig):
    id: str
    type: Literal[BucketType.S3] = BucketType.S3
    endpoint: str
    bucket_name: str
    secure: bool | None = None
    region: str
    cert_check: bool | None = None
    organization_id: str
    created_at: str
    updated_at: str | None = None
    orbits: list[OrbitBase] = []


class AzureBucketSecret(BaseModel, BaseOrmConfig):
    id: str
    type: Literal[BucketType.AZURE] = BucketType.AZURE
    endpoint: str
    bucket_name: str
    organization_id: str
    created_at: str
    updated_at: str | None = None
    orbits: list[OrbitBase] = []


BucketSecret = S3BucketSecret | AzureBucketSecret


def model_validate_bucket_secret(bucket: dict) -> S3BucketSecret | AzureBucketSecret:
    if bucket.get("type") == BucketType.S3:
        return S3BucketSecret.model_validate(bucket)
    return AzureBucketSecret.model_validate(bucket)


class BucketSecretUrls(BaseModel):
    presigned_url: str
    download_url: str
    delete_url: str


class Collection(BaseModel):
    id: str
    orbit_id: str
    description: str
    name: str
    type: str
    tags: list[str] | None = None
    total_artifacts: int = 0
    created_at: str
    updated_at: str | None = None


class CollectionDetails(Collection):
    artifacts_tags: list[str] | None = None
    artifacts_extra_values: list[str] | None = None


class CollectionsList(PaginatedList[Collection]):
    pass


class Artifact(BaseModel, BaseOrmConfig):
    id: str
    collection_id: str
    file_name: str
    name: str
    description: str | None = None
    extra_values: dict
    manifest: dict
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    bucket_location: str
    size: int
    unique_identifier: str
    tags: list[str] | None = None
    status: str
    type: ArtifactType
    created_at: str
    updated_at: str | None = None


class DeploymentBase(BaseModel):
    id: str
    name: str
    status: str
    orbit_id: str


class ArtifactListed(Artifact):
    created_by_user: str | None = None
    deployments: list[DeploymentBase] = []
    collection_name: str


class ArtifactsList(PaginatedList[Artifact]):
    pass


ArtifactDeleteReason = Literal[
    "not_found",
    "deployments",
    "tracks",
    "not_pending_deletion",
    "storage_error",
]


class ArtifactDeleteDeployment(BaseModel):
    id: str
    name: str
    status: str


class ArtifactDeleteTrack(BaseModel):
    id: str
    name: str


class ArtifactDeleteFailure(BaseModel):
    artifact_id: str
    name: str | None
    reason: ArtifactDeleteReason
    deployments: list[ArtifactDeleteDeployment] = Field(default_factory=list)
    tracks: list[ArtifactDeleteTrack] = Field(default_factory=list)


class ArtifactDeleteURL(BaseModel):
    artifact_id: str
    name: str
    url: str


class ArtifactsDeleteURLsResponse(BaseModel):
    urls: list[ArtifactDeleteURL]
    failed: list[ArtifactDeleteFailure]


class ArtifactsDeleteResponse(BaseModel):
    deleted: list[str]
    failed: list[ArtifactDeleteFailure]


class ArtifactsDeleteResult(BaseModel):
    deleted: list[str]
    failed: list[ArtifactDeleteFailure]


class ArtifactFileDetails(BaseModel):
    file_name: str
    extra_values: dict
    manifest: dict
    file_hash: str
    file_index: dict[str, tuple[int, int]]
    size: int


class MultipartUploadInfo(BaseModel):
    upload_id: str
    parts_count: int
    part_size: int


class PartDetails(BaseModel):
    part_number: int
    url: str
    start_byte: int
    end_byte: int
    part_size: int


class UploadDetails(BaseModel, BaseOrmConfig):
    type: BucketType
    url: str | None = None
    multipart: bool = False
    bucket_location: str
    bucket_secret_id: str


class MultiPartUploadDetails(BaseModel, BaseOrmConfig):
    type: BucketType
    upload_id: str | None = None
    parts: list[PartDetails]
    complete_url: str


class BucketMultipartUpload(BaseModel):
    bucket_id: str
    bucket_location: str
    size: int
    upload_id: str


class CreatedArtifact(BaseModel):
    upload_details: UploadDetails
    artifact: Artifact


class LineageEdge(BaseModel):
    id: str
    source: str
    target: str
    created_by_user: str
    created_via: Literal["ui", "api"]
    created_at: str


class LineageNode(BaseModel):
    id: str
    artifact_id: str | None
    type: str
    name: str
    collection_name: str | None
    x: float | None
    y: float | None
    is_deleted: bool
    data: ArtifactListed | None


class LineageGraph(BaseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    focal_artifact_id: str
    depth: int | None
    truncated: bool


class StageUpsertIn(BaseModel):
    id: UUID | None = None
    name: str


class Stage(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    name: str
    is_used: bool = False
    created_at: str
    updated_at: str | None = None


class TrackBase(BaseModel, BaseOrmConfig):
    id: UUID
    name: str
    created_at: str
    updated_at: str | None = None


class Track(TrackBase):
    orbit_id: UUID
    artifact_type: str
    description: str | None = None
    tags: list[str] | None = None
    stages: list[Stage]
    next_version: int
    total_entries: int


class TrackEntry(BaseModel, BaseOrmConfig):
    id: UUID
    track_id: UUID
    artifact_id: UUID
    version: int
    stage_id: UUID | None = None
    added_by: UUID
    created_at: str
    updated_at: str | None = None
    artifact_name: str | None = None
    artifact_description: str | None = None
    stage_name: str | None = None


class TrackEntriesList(BaseModel):
    items: list[TrackEntry]
    cursor: str | None


class TracksList(BaseModel):
    items: list[Track]
    cursor: str | None = None


class Deployment(BaseModel):
    """A model deployment on a Satellite, as the Platform records it."""

    id: str
    orbit_id: str
    satellite_id: str
    satellite_name: str | None = None
    name: str
    artifact_id: str
    artifact_name: str | None = None
    collection_id: str | None = None
    inference_url: str | None = None
    monitoring_url: str | None = None
    status: str
    monitoring_mode: str = "off"
    description: str | None = None
    created_by_user: str | None = None
    tags: list[str] | None = None
    created_at: str
    updated_at: str | None = None


def _satellite_origin(url: URL) -> tuple[str, str, int | None]:
    return (url.scheme, url.host, url.port)


def _resolve_satellite_url(base_url: str | None, path: str, satellite_id: str) -> str:
    if not base_url:
        raise LumlAPIError(
            f"Satellite {satellite_id} has no reachable base URL configured"
        )

    try:
        base = URL(base_url)
        target = base.join(path)
    except InvalidURL as error:
        raise LumlAPIError(f"Invalid Satellite request URL: {path!r}") from error

    if not base.is_absolute_url or _satellite_origin(target) != _satellite_origin(base):
        raise LumlAPIError(
            "Satellite requests must use the same origin as its base URL "
            f"{base_url!r}; got {path!r}"
        )
    return str(target)


def _as_openapi_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _openapi_operations(
    document: object,
    satellite_id: str,
    facet: str | None,
) -> list[dict[str, Any]]:
    if document is None:
        raise LumlAPIError(
            f"Satellite {satellite_id} has no description available because it did "
            "not provide an OpenAPI document when pairing"
        )
    if not isinstance(document, dict):
        raise LumlAPIError(
            f"Satellite {satellite_id} has an invalid OpenAPI description"
        )

    paths = document.get("paths")
    if not isinstance(paths, dict):
        return []

    default_security = document.get("security", [])
    operations: list[dict[str, Any]] = []
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        path_parameters = _as_openapi_list(path_item.get("parameters"))

        for method, operation in path_item.items():
            if method not in _OPENAPI_HTTP_METHODS or not isinstance(operation, dict):
                continue
            tags = operation.get("tags", [])
            if facet is not None and (not isinstance(tags, list) or facet not in tags):
                continue
            operation_parameters = _as_openapi_list(operation.get("parameters"))
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary"),
                    "description": operation.get("description"),
                    "parameters": [*path_parameters, *operation_parameters],
                    "security": operation.get("security", default_security),
                }
            )
    return operations


class _SatelliteRecord(BaseModel):
    id: str
    orbit_id: str
    name: str | None = None
    description: str | None = None
    base_url: str | None = None
    paired: bool
    capabilities: dict[str, dict[str, Any]]
    present_capabilities: list[str]
    slug: str | None = None
    status: str
    created_at: str
    updated_at: str | None = None
    last_seen_at: str | None = None


class Satellite(_SatelliteRecord):
    """A Satellite record bound to its Platform and machine APIs."""

    _client: "LumlClient" = PrivateAttr()
    _openapi_path: str = PrivateAttr()

    def _bind(self, client: "LumlClient", openapi_path: str) -> None:
        self._client = client
        self._openapi_path = openapi_path

    def operations(self, facet: str | None = None) -> list[dict[str, Any]]:
        """
        List the Satellite's endpoints from its stored OpenAPI document.

        The document is the one the Satellite pushed to the Platform when it
        paired; the Satellite itself is not contacted. Each entry describes one
        operation: method, path template, summary, description, parameters and
        security.

        Args:
            facet: Only list operations tagged with this facet id, for example
                "deployment:monitoring". None lists every operation.

        Returns:
            list of dicts with "method", "path", "summary", "description",
            "parameters" and "security".

        Raises:
            LumlAPIError: If the Satellite paired without an OpenAPI document, so
                no description is available.

        Example:
        ```python
        satellite = luml.satellites.get("0199c9cd-3e36-72c0-b823-040eb8195067")
        operations = satellite.operations(facet="deployment:monitoring")
        ```
        """
        document = self._client.get(self._openapi_path)
        return _openapi_operations(document, self.id, facet)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN401
        """
        Perform one HTTP call against the Satellite's own API.

        Sends the request with the client's bearer key and returns the parsed
        JSON as-is. Use it together with `operations()` to call endpoints the SDK
        has no native method for, such as a custom capability's routes.

        Args:
            method: HTTP method, for example "GET".
            path: Path relative to the Satellite's base URL, or an absolute URL
                on the same origin. Any other origin raises before a request is
                sent, so the key cannot leak to a foreign host.
            **kwargs: Passed to the underlying HTTP client, for example `params`
                or `json`.

        Returns:
            The Satellite's parsed JSON response.

        Raises:
            LumlAPIError: If `path` resolves to a different origin than the
                Satellite's base URL.
            APIStatusError: Subclass matching the HTTP error status, if any.

        Example:
        ```python
        satellite = luml.satellites.get("0199c9cd-3e36-72c0-b823-040eb8195067")
        health = satellite.request("GET", "/healthz")
        ```
        """
        url = _resolve_satellite_url(self.base_url, path, self.id)
        return self._client.request(method, url, **kwargs)


class AsyncSatellite(_SatelliteRecord):
    """Async Satellite record bound to its Platform and machine APIs."""

    _client: "AsyncLumlClient" = PrivateAttr()
    _openapi_path: str = PrivateAttr()

    def _bind(self, client: "AsyncLumlClient", openapi_path: str) -> None:
        self._client = client
        self._openapi_path = openapi_path

    async def operations(self, facet: str | None = None) -> list[dict[str, Any]]:
        """
        List the Satellite's endpoints from its stored OpenAPI document.

        Async variant of `Satellite.operations`.
        """
        document = await self._client.get(self._openapi_path)
        return _openapi_operations(document, self.id, facet)

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """
        Perform one HTTP call against the Satellite's own API.

        Async variant of `Satellite.request`.
        """
        url = _resolve_satellite_url(self.base_url, path, self.id)
        return await self._client.request(method, url, **kwargs)
