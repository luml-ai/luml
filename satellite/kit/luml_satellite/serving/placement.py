import asyncio
import copy
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, FastAPI

from luml_satellite.authorization import Authorizer
from luml_satellite.convergence import ModelDescription
from luml_satellite.tokens import TokenDeriver
from luml_satellite.wire import Deployment
from luml_satellite.workload import (
    ArtifactResolver,
    DeploymentMetadata,
    LocalDeployment,
    NoOpRecorder,
    ProfileStatus,
    Recorder,
    RecordingPolicy,
)

from .application import (
    StartingGate,
    create_artifact_router,
    create_internal_application,
    create_serving_application,
)
from .companion import (
    CompanionRecord,
    create_companion_router,
)
from .secrets import SecretSource
from .transforms import JsonTransform, ServingTransform

_TABULAR_MONITORING_TAG_PREFIX = "luml.ai::tabular_monitoring:v"
_SUPPORTED_TABULAR_MONITORING_VERSION = 1


class InProcessServingPlacement:
    def __init__(
        self,
        authorizer: Authorizer,
        secret_source: SecretSource,
        *,
        recorder: Recorder | None = None,
        recording_policy: RecordingPolicy | None = None,
        transform: ServingTransform | None = None,
        artifact_resolver: ArtifactResolver | None = None,
        injection_body_max_bytes: int = 16_777_216,
        upstream_timeout_seconds: float = 45.0,
        upstream_client: httpx.AsyncClient | None = None,
        upstream_transport: httpx.AsyncBaseTransport | None = None,
        gate: StartingGate | None = None,
        last_monitored_at: Callable[[str], datetime | None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if upstream_client is not None and upstream_transport is not None:
            raise ValueError("provide either upstream_client or upstream_transport, not both")
        self._logger = logger or logging.getLogger("luml_satellite.serving")
        self._recording_policy = recording_policy or RecordingPolicy()
        self._deployments: dict[str, LocalDeployment] = {}
        self._gate = gate or StartingGate()
        self._owns_client = upstream_client is None
        self._client = upstream_client or httpx.AsyncClient(
            timeout=upstream_timeout_seconds,
            transport=upstream_transport,
        )
        self.application = create_serving_application(
            self,
            authorizer,
            secret_source,
            recorder=recorder or NoOpRecorder(),
            transform=transform or JsonTransform(),
            upstream_client=self._client,
            starting_gate=self._gate,
            injection_body_max_bytes=injection_body_max_bytes,
            upstream_timeout_seconds=upstream_timeout_seconds,
            last_monitored_at=last_monitored_at,
            logger=self._logger,
        )
        self.internal_router: APIRouter | None = None
        self.internal_application: FastAPI | None = None
        if artifact_resolver is not None:
            self.internal_router = create_artifact_router(artifact_resolver)
            self.internal_application = create_internal_application(artifact_resolver)

    @property
    def router(self) -> FastAPI:
        return self.application

    @property
    def deployments(self) -> tuple[LocalDeployment, ...]:
        return tuple(self._deployments.values())

    async def describe(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> ModelDescription:
        del deployment
        if upstream_url is None:
            return ModelDescription()
        manifest, schema, raw_profile = await asyncio.gather(
            self._read_json(upstream_url, "manifest"),
            self._read_json(upstream_url, "openapi.json"),
            self._read_json(upstream_url, "reference_profile"),
        )
        profile, profile_status = gate_reference_profile(manifest, raw_profile)
        return ModelDescription(
            manifest=manifest,
            schema=schema,
            reference_profile=profile,
            profile_status=profile_status,
        )

    async def register(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
        description: ModelDescription,
    ) -> None:
        if upstream_url is None:
            if self.is_registered(str(deployment.id)):
                self.note_platform_record(str(deployment.id), deployment)
                return
            raise ValueError("in-process serving requires an upstream URL")
        manifest = _mapping_copy(description.manifest)
        profile, derived_status = gate_reference_profile(
            manifest,
            _mapping_copy(description.reference_profile),
        )
        profile_status = (
            description.profile_status
            if description.profile_status is not ProfileStatus.ABSENT
            else derived_status
        )
        self._deployments[str(deployment.id)] = LocalDeployment(
            deployment_id=str(deployment.id),
            dynamic_attributes_secrets=dict(deployment.dynamic_attributes_secrets or {}),
            manifest=manifest,
            openapi_schema=without_secret_attributes(
                _mapping_copy(description.schema),
                deployment.dynamic_attributes_secrets or {},
            ),
            reference_profile=profile,
            profile_status=profile_status,
            monitoring_enabled=_monitoring_enabled(deployment.monitoring_mode),
            metadata=DeploymentMetadata.from_platform(deployment.model_dump()),
            upstream_url=upstream_url,
            recording_policy=self._recording_policy,
        )
        self.application.openapi_schema = None

    async def unregister(self, deployment_id: str) -> None:
        self._deployments.pop(deployment_id, None)
        self.application.openapi_schema = None

    def address(self, deployment: Deployment, *, upstream_url: str | None) -> str:
        del upstream_url
        return f"/deployments/{deployment.id}"

    async def check_health(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> bool:
        del deployment
        if upstream_url is None:
            return False
        try:
            response = await self._client.get(f"{upstream_url.rstrip('/')}/healthz")
        except Exception:
            return False
        return response.status_code == 200

    def note_platform_record(self, deployment_id: str, record: Deployment) -> None:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return
        deployment.metadata = DeploymentMetadata.from_platform(record.model_dump())
        deployment.dynamic_attributes_secrets = dict(record.dynamic_attributes_secrets or {})
        deployment.monitoring_enabled = _monitoring_enabled(record.monitoring_mode)

    def is_registered(self, deployment_id: str) -> bool:
        return deployment_id in self._deployments

    def get_deployment(self, deployment_id: str) -> LocalDeployment | None:
        return self._deployments.get(deployment_id)

    def list_deployments(self) -> tuple[LocalDeployment, ...]:
        return self.deployments

    def mark_reconciled(self) -> None:
        self._gate.mark_ready()

    def include_internal_routes(self, application: FastAPI | None = None) -> None:
        if self.internal_router is None:
            raise RuntimeError("this placement has no artifact resolver")
        (application or self.application).include_router(self.internal_router)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _read_json(self, upstream_url: str, path: str) -> dict[str, Any] | None:
        try:
            response = await self._client.get(f"{upstream_url.rstrip('/')}/{path}")
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            self._logger.warning("could not read upstream %s: %s", path, error)
            return None
        return payload if isinstance(payload, dict) else None


class CompanionServingPlacement:
    def __init__(
        self,
        authorizer: Authorizer,
        secret_source: SecretSource,
        token_deriver: TokenDeriver,
        *,
        satellite_id: str | None = None,
        recording_policy: RecordingPolicy | None = None,
        artifact_resolver: ArtifactResolver | None = None,
        cache_ttl_seconds: float = 60.0,
        upstream_timeout_seconds: float = 45.0,
        upstream_client: httpx.AsyncClient | None = None,
        upstream_transport: httpx.AsyncBaseTransport | None = None,
        gate: StartingGate | None = None,
        last_monitored_at: Callable[[str], datetime | None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if upstream_client is not None and upstream_transport is not None:
            raise ValueError("provide either upstream_client or upstream_transport, not both")
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be greater than zero")
        self._authorizer = authorizer
        self._secret_source = secret_source
        self._token_deriver = token_deriver
        self._satellite_id = satellite_id
        self._recording_policy = recording_policy or RecordingPolicy()
        self._logger = logger or logging.getLogger("luml_satellite.serving.companion")
        self._records: dict[str, CompanionRecord] = {}
        self._gate = gate or StartingGate()
        self._owns_client = upstream_client is None
        self._client = upstream_client or httpx.AsyncClient(
            timeout=upstream_timeout_seconds,
            transport=upstream_transport,
        )
        self.application = create_serving_application(
            self,
            authorizer,
            secret_source,
            upstream_client=self._client,
            starting_gate=self._gate,
            not_hosted=True,
            upstream_timeout_seconds=upstream_timeout_seconds,
            last_monitored_at=last_monitored_at,
            logger=self._logger,
        )
        self.internal_router = create_companion_router(
            self,
            authorizer,
            secret_source,
            token_deriver,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        self.internal_application = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.internal_application.include_router(self.internal_router)
        if artifact_resolver is not None:
            artifact_router = create_artifact_router(artifact_resolver)
            self.internal_application.include_router(artifact_router)
            self.internal_router.include_router(artifact_router)

    @property
    def router(self) -> FastAPI:
        return self.application

    @property
    def deployments(self) -> tuple[LocalDeployment, ...]:
        return tuple(record.deployment for record in self._records.values())

    async def describe(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> ModelDescription:
        if upstream_url is None:
            return ModelDescription()
        token = self._token_deriver.companion_token(str(deployment.id))
        manifest, schema, raw_profile = await asyncio.gather(
            self._read_json(upstream_url, "manifest", token),
            self._read_json(upstream_url, "openapi.json", token),
            self._read_json(upstream_url, "reference_profile", token),
        )
        profile, profile_status = gate_reference_profile(manifest, raw_profile)
        return ModelDescription(
            manifest=manifest,
            schema=schema,
            reference_profile=profile,
            profile_status=profile_status,
        )

    async def register(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
        description: ModelDescription,
    ) -> None:
        if self._satellite_id is not None and deployment.satellite_id != self._satellite_id:
            raise ValueError("cannot register a deployment owned by another satellite")
        deployment_id = str(deployment.id)
        if upstream_url is None:
            if self.is_registered(deployment_id):
                self.note_platform_record(deployment_id, deployment)
                return
            raise ValueError("companion serving requires a sidecar internal URL")
        manifest = _mapping_copy(description.manifest)
        profile, derived_status = gate_reference_profile(
            manifest,
            _mapping_copy(description.reference_profile),
        )
        profile_status = (
            description.profile_status
            if description.profile_status is not ProfileStatus.ABSENT
            else derived_status
        )
        local = LocalDeployment(
            deployment_id=deployment_id,
            dynamic_attributes_secrets=dict(deployment.dynamic_attributes_secrets or {}),
            manifest=manifest,
            openapi_schema=without_secret_attributes(
                _mapping_copy(description.schema),
                deployment.dynamic_attributes_secrets or {},
            ),
            reference_profile=profile,
            profile_status=profile_status,
            monitoring_enabled=_monitoring_enabled(deployment.monitoring_mode),
            metadata=DeploymentMetadata.from_platform(deployment.model_dump()),
            upstream_url=upstream_url,
            recording_policy=self._recording_policy,
        )
        self._records[deployment_id] = CompanionRecord(
            deployment=local,
            artifact_id=deployment.artifact_id,
            secret_references=dict(deployment.dynamic_attributes_secrets or {}),
            schema=_mapping_copy(description.schema),
        )
        self.application.openapi_schema = None

    async def unregister(self, deployment_id: str) -> None:
        self._records.pop(deployment_id, None)
        self.application.openapi_schema = None

    def address(self, deployment: Deployment, *, upstream_url: str | None) -> str:
        del upstream_url
        return f"/deployments/{deployment.id}"

    async def check_health(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> bool:
        if upstream_url is None:
            return False
        token = self._token_deriver.companion_token(str(deployment.id))
        try:
            response = await self._client.get(
                f"{upstream_url.rstrip('/')}/healthz",
                headers={"Authorization": f"Bearer {token}"},
            )
        except Exception:
            return False
        return response.status_code == 200

    def note_platform_record(self, deployment_id: str, record: Deployment) -> None:
        companion = self._records.get(deployment_id)
        if companion is None:
            return
        companion.deployment.metadata = DeploymentMetadata.from_platform(record.model_dump())
        companion.deployment.dynamic_attributes_secrets = dict(
            record.dynamic_attributes_secrets or {}
        )
        companion.deployment.monitoring_enabled = _monitoring_enabled(record.monitoring_mode)
        companion.artifact_id = record.artifact_id
        companion.secret_references = dict(record.dynamic_attributes_secrets or {})
        companion.deployment.openapi_schema = without_secret_attributes(
            _mapping_copy(companion.schema),
            companion.secret_references,
        )

    def is_registered(self, deployment_id: str) -> bool:
        return deployment_id in self._records

    def get_deployment(self, deployment_id: str) -> LocalDeployment | None:
        record = self._records.get(deployment_id)
        return record.deployment if record is not None else None

    def get_companion_record(self, deployment_id: str) -> CompanionRecord | None:
        return self._records.get(deployment_id)

    def list_deployments(self) -> tuple[LocalDeployment, ...]:
        return self.deployments

    def mark_reconciled(self) -> None:
        self._gate.mark_ready()

    def include_internal_routes(self, application: FastAPI | None = None) -> None:
        target = application or self.application
        target.include_router(self.internal_router)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _read_json(
        self,
        upstream_url: str,
        path: str,
        token: str,
    ) -> dict[str, Any] | None:
        try:
            response = await self._client.get(
                f"{upstream_url.rstrip('/')}/{path}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            self._logger.warning("could not read sidecar %s: %s", path, error)
            return None
        return payload if isinstance(payload, dict) else None


def usable_reference_profile(profile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not profile or profile.get("profile_status") == ProfileStatus.PLACEHOLDER:
        return None
    summaries = profile.get("feature_summaries")
    has_summaries = isinstance(summaries, Mapping) and bool(
        summaries.get("numerical_features") or summaries.get("categorical_features")
    )
    if profile.get("profile_status") == ProfileStatus.READY or has_summaries:
        return dict(profile)
    return None


def gate_reference_profile(
    manifest: Mapping[str, Any] | None,
    profile: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, ProfileStatus]:
    versions = {
        int(suffix)
        for tag in _producer_tags(manifest)
        if tag.startswith(_TABULAR_MONITORING_TAG_PREFIX)
        and (suffix := tag.removeprefix(_TABULAR_MONITORING_TAG_PREFIX)).isdecimal()
    }
    if not versions:
        return None, ProfileStatus.ABSENT
    if _SUPPORTED_TABULAR_MONITORING_VERSION not in versions:
        return None, ProfileStatus.UNSUPPORTED
    if not profile:
        return None, ProfileStatus.ABSENT
    usable = usable_reference_profile(profile)
    if usable is None:
        return None, ProfileStatus.PLACEHOLDER
    return usable, ProfileStatus.READY


def _producer_tags(manifest: Mapping[str, Any] | None) -> set[str]:
    tags = (manifest or {}).get("producer_tags")
    if not isinstance(tags, list):
        return set()
    return {tag for tag in tags if isinstance(tag, str)}


def _mapping_copy(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return copy.deepcopy(dict(value)) if value is not None else None


def without_secret_attributes(
    schema: dict[str, Any] | None,
    secrets: Mapping[str, str],
) -> dict[str, Any] | None:
    if schema is None:
        return None
    components = schema.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    dynamic = schemas.get("DynamicAttributesModel") if isinstance(schemas, dict) else None
    properties = dynamic.get("properties") if isinstance(dynamic, dict) else None
    if isinstance(properties, dict):
        for attribute in secrets:
            properties.pop(attribute, None)
    return schema


def _monitoring_enabled(mode: str | None) -> bool:
    return (mode or "off").strip().lower() == "full"
