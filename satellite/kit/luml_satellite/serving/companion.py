import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Protocol

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from luml_satellite.authorization import AuthorizationVerdict, Authorizer
from luml_satellite.tokens import TokenDeriver, TokenPurpose
from luml_satellite.wire import InferenceAccessIn
from luml_satellite.workload import DeploymentMetadata, LocalDeployment, RecordingPolicy

from .secrets import SecretSource, SecretUnavailable

COMPANION_PATH = "/satellites/deployments/{deployment_id}/companion"


class CompanionRecordingPolicy(BaseModel):
    sample_rate: float = Field(default=1.0, ge=0, le=1)
    body_max_bytes: int = Field(default=65_536, gt=0)
    keep_inputs: bool = True
    keep_outputs: bool = True

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_policy(cls, policy: RecordingPolicy) -> CompanionRecordingPolicy:
        return cls(
            sample_rate=policy.sample_rate,
            body_max_bytes=policy.body_max_bytes,
            keep_inputs=policy.keep_inputs,
            keep_outputs=policy.keep_outputs,
        )

    def to_policy(self) -> RecordingPolicy:
        return RecordingPolicy(
            sample_rate=self.sample_rate,
            body_max_bytes=self.body_max_bytes,
            keep_inputs=self.keep_inputs,
            keep_outputs=self.keep_outputs,
        )


class CompanionMetadata(BaseModel):
    deployment_id: str
    secret_attributes: list[str] = Field(default_factory=list)
    monitoring_enabled: bool = False
    metadata: DeploymentMetadata = Field(default_factory=DeploymentMetadata)
    artifact_id: str
    recording_policy: CompanionRecordingPolicy | None = None
    ttl_seconds: float = Field(default=60.0, gt=0)

    model_config = ConfigDict(extra="ignore")


class CompanionAuthorization(BaseModel):
    authorized: bool
    ttl_seconds: float = Field(default=60.0, gt=0)

    model_config = ConfigDict(extra="ignore")


class CompanionSecrets(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)
    ttl_seconds: float = Field(default=60.0, gt=0)

    model_config = ConfigDict(extra="ignore")


@dataclass
class CompanionRecord:
    deployment: LocalDeployment
    artifact_id: str
    secret_references: dict[str, str]
    schema: dict[str, Any] | None = None


class CompanionRecordSource(Protocol):
    def get_companion_record(self, deployment_id: str) -> CompanionRecord | None: ...


class CompanionApi(Protocol):
    async def metadata(self) -> CompanionMetadata: ...

    async def authorize(self, api_key: str) -> CompanionAuthorization: ...

    async def secrets(self) -> CompanionSecrets: ...


class CompanionUnavailableError(RuntimeError):
    pass


class CompanionRefusedError(CompanionUnavailableError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"companion API refused the request with status {status_code}")


class CompanionClient:
    def __init__(
        self,
        base_url: str,
        deployment_id: str,
        token: str,
        *,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        if client is not None and transport is not None:
            raise ValueError("provide either client or transport, not both")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._base_url = base_url.rstrip("/")
        self._deployment_id = deployment_id
        self._token = token
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            transport=transport,
            timeout=timeout_seconds,
        )

    async def metadata(self) -> CompanionMetadata:
        payload = await self._request("GET", "")
        try:
            return CompanionMetadata.model_validate(payload)
        except ValidationError as error:
            raise CompanionUnavailableError("invalid companion metadata") from error

    async def authorize(self, api_key: str) -> CompanionAuthorization:
        payload = await self._request(
            "POST",
            "/inference-access",
            json={"api_key": api_key},
        )
        try:
            return CompanionAuthorization.model_validate(payload)
        except ValidationError as error:
            raise CompanionUnavailableError("invalid companion authorization") from error

    async def secrets(self) -> CompanionSecrets:
        payload = await self._request("GET", "/secrets")
        try:
            return CompanionSecrets.model_validate(payload)
        except ValidationError as error:
            raise CompanionUnavailableError("invalid companion secrets") from error

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        suffix: str,
        *,
        json: object | None = None,
    ) -> object:
        path = COMPANION_PATH.format(deployment_id=self._deployment_id)
        url = f"{self._base_url}{path}{suffix}"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            response = (
                await self._client.request(method, url, headers=headers)
                if json is None
                else await self._client.request(method, url, headers=headers, json=json)
            )
        except httpx.HTTPError as error:
            raise CompanionUnavailableError("companion API is unavailable") from error
        if response.status_code in (403, 404):
            raise CompanionRefusedError(response.status_code)
        if response.status_code >= 400:
            raise CompanionUnavailableError(f"companion API returned status {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise CompanionUnavailableError("companion API returned invalid JSON") from error


@dataclass(frozen=True)
class _AuthorizationCacheEntry:
    verdict: AuthorizationVerdict
    expires_at: float
    stale_until: float


class CompanionAuthorizer:
    def __init__(
        self,
        companion: CompanionApi,
        *,
        ttl_seconds: float = 60.0,
        refresh_ahead_seconds: float = 15.0,
        stale_allowance_seconds: float = 600.0,
        negative_ttl_seconds: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if refresh_ahead_seconds < 0 or refresh_ahead_seconds >= ttl_seconds:
            raise ValueError("refresh_ahead_seconds must be non-negative and less than the TTL")
        if stale_allowance_seconds < 0:
            raise ValueError("stale_allowance_seconds must not be negative")
        if negative_ttl_seconds <= 0:
            raise ValueError("negative_ttl_seconds must be greater than zero")
        self._companion = companion
        self._ttl_seconds = ttl_seconds
        self._refresh_ahead_seconds = refresh_ahead_seconds
        self._stale_allowance_seconds = stale_allowance_seconds
        self._negative_ttl_seconds = negative_ttl_seconds
        self._clock = clock
        self._logger = logger or logging.getLogger("luml_satellite.serving.companion")
        self._cache: dict[str, _AuthorizationCacheEntry] = {}
        self._refreshes: dict[str, asyncio.Task[None]] = {}
        self._unavailable_logged = False

    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        cache_key = hashlib.sha256(api_key.encode()).hexdigest()
        now = self._clock()
        cached = self._cache.get(cache_key)
        if cached is not None and cached.expires_at > now:
            if (
                cached.verdict is AuthorizationVerdict.ALLOWED
                and cached.expires_at - now <= self._refresh_ahead_seconds
            ):
                self._schedule_refresh(cache_key, api_key)
            return cached.verdict

        try:
            return await self._fetch(cache_key, api_key)
        except CompanionUnavailableError:
            self._log_unavailable()
            if (
                cached is not None
                and cached.verdict is AuthorizationVerdict.ALLOWED
                and cached.stale_until > now
            ):
                return cached.verdict
            return AuthorizationVerdict.UNAVAILABLE

    async def aclose(self) -> None:
        tasks = tuple(self._refreshes.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch(self, cache_key: str, api_key: str) -> AuthorizationVerdict:
        response = await self._companion.authorize(api_key)
        now = self._clock()
        verdict = (
            AuthorizationVerdict.ALLOWED if response.authorized else AuthorizationVerdict.DENIED
        )
        ttl = (
            min(self._ttl_seconds, response.ttl_seconds)
            if verdict is AuthorizationVerdict.ALLOWED
            else self._negative_ttl_seconds
        )
        self._cache[cache_key] = _AuthorizationCacheEntry(
            verdict=verdict,
            expires_at=now + ttl,
            stale_until=(
                now + ttl + self._stale_allowance_seconds
                if verdict is AuthorizationVerdict.ALLOWED
                else now + ttl
            ),
        )
        self._unavailable_logged = False
        return verdict

    def _schedule_refresh(self, cache_key: str, api_key: str) -> None:
        task = self._refreshes.get(cache_key)
        if task is not None and not task.done():
            return
        task = asyncio.create_task(
            self._refresh(cache_key, api_key),
            name="luml-companion-authorization-refresh",
        )
        self._refreshes[cache_key] = task
        task.add_done_callback(lambda completed: self._refresh_done(cache_key, completed))

    async def _refresh(self, cache_key: str, api_key: str) -> None:
        try:
            await self._fetch(cache_key, api_key)
        except CompanionUnavailableError:
            self._log_unavailable()

    def _refresh_done(self, cache_key: str, task: asyncio.Task[None]) -> None:
        if self._refreshes.get(cache_key) is task:
            self._refreshes.pop(cache_key, None)

    def _log_unavailable(self) -> None:
        if self._unavailable_logged:
            return
        self._unavailable_logged = True
        self._logger.warning("companion API is unavailable; serving cached authorization")


@dataclass(frozen=True)
class _SecretCacheEntry:
    values: Mapping[str, str]
    expires_at: float
    stale_until: float


class CompanionSecretSource:
    def __init__(
        self,
        companion: CompanionApi,
        deployment_id: str,
        *,
        ttl_seconds: float = 60.0,
        refresh_ahead_seconds: float = 15.0,
        stale_allowance_seconds: float = 600.0,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if refresh_ahead_seconds < 0 or refresh_ahead_seconds >= ttl_seconds:
            raise ValueError("refresh_ahead_seconds must be non-negative and less than the TTL")
        if stale_allowance_seconds < 0:
            raise ValueError("stale_allowance_seconds must not be negative")
        self._companion = companion
        self._deployment_id = deployment_id
        self._ttl_seconds = ttl_seconds
        self._refresh_ahead_seconds = refresh_ahead_seconds
        self._stale_allowance_seconds = stale_allowance_seconds
        self._clock = clock
        self._logger = logger or logging.getLogger("luml_satellite.serving.companion")
        self._cache: _SecretCacheEntry | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._unavailable_logged = False

    async def resolve(
        self,
        deployment_id: str,
        secrets: Mapping[str, str],
    ) -> Mapping[str, str]:
        if not secrets:
            return {}
        attributes = set(secrets)
        if deployment_id != self._deployment_id:
            raise SecretUnavailable(next(iter(attributes)))

        now = self._clock()
        cached = self._cache
        has_values = cached is not None and attributes <= cached.values.keys()
        if has_values and cached is not None and cached.expires_at > now:
            if cached.expires_at - now <= self._refresh_ahead_seconds:
                self._schedule_refresh()
            return {attribute: cached.values[attribute] for attribute in attributes}

        try:
            cached = await self._fetch()
        except CompanionUnavailableError:
            self._log_unavailable()
            if has_values and cached is not None and cached.stale_until > now:
                return {attribute: cached.values[attribute] for attribute in attributes}
            raise SecretUnavailable(next(iter(attributes))) from None

        missing = attributes - cached.values.keys()
        if missing:
            raise SecretUnavailable(next(iter(missing)))
        return {attribute: cached.values[attribute] for attribute in attributes}

    async def aclose(self) -> None:
        if self._refresh_task is None:
            return
        self._refresh_task.cancel()
        await asyncio.gather(self._refresh_task, return_exceptions=True)

    async def _fetch(self) -> _SecretCacheEntry:
        response = await self._companion.secrets()
        now = self._clock()
        ttl = min(self._ttl_seconds, response.ttl_seconds)
        cached = _SecretCacheEntry(
            values=dict(response.values),
            expires_at=now + ttl,
            stale_until=now + ttl + self._stale_allowance_seconds,
        )
        self._cache = cached
        self._unavailable_logged = False
        return cached

    def _schedule_refresh(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.create_task(
            self._refresh(),
            name="luml-companion-secrets-refresh",
        )

    async def _refresh(self) -> None:
        try:
            await self._fetch()
        except CompanionUnavailableError:
            self._log_unavailable()

    def _log_unavailable(self) -> None:
        if self._unavailable_logged:
            return
        self._unavailable_logged = True
        self._logger.warning("companion API is unavailable; serving cached secrets")


def create_companion_router(
    records: CompanionRecordSource,
    authorizer: Authorizer,
    secret_source: SecretSource,
    token_deriver: TokenDeriver,
    *,
    cache_ttl_seconds: float = 60.0,
) -> APIRouter:
    if cache_ttl_seconds <= 0:
        raise ValueError("cache_ttl_seconds must be greater than zero")
    router = APIRouter()
    security = HTTPBearer(auto_error=False)

    async def verify_token(
        deployment_id: str,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    ) -> None:
        token = credentials.credentials if credentials is not None else None
        if not token_deriver.verify(TokenPurpose.COMPANION, deployment_id, token):
            raise HTTPException(status_code=403, detail="Invalid companion token")

    @router.get(
        COMPANION_PATH,
        response_model=CompanionMetadata,
        dependencies=[Depends(verify_token)],
        include_in_schema=False,
    )
    async def metadata(
        deployment_id: str,
    ) -> CompanionMetadata | JSONResponse:
        record = records.get_companion_record(deployment_id)
        if record is None:
            return _deployment_not_hosted()
        return CompanionMetadata(
            deployment_id=deployment_id,
            secret_attributes=list(record.secret_references),
            monitoring_enabled=record.deployment.monitoring_enabled,
            metadata=record.deployment.metadata,
            artifact_id=record.artifact_id,
            recording_policy=CompanionRecordingPolicy.from_policy(
                record.deployment.recording_policy
            ),
            ttl_seconds=cache_ttl_seconds,
        )

    @router.post(
        f"{COMPANION_PATH}/inference-access",
        response_model=CompanionAuthorization,
        dependencies=[Depends(verify_token)],
        include_in_schema=False,
    )
    async def authorize(
        deployment_id: str,
        body: InferenceAccessIn,
    ) -> CompanionAuthorization | JSONResponse:
        if records.get_companion_record(deployment_id) is None:
            return _deployment_not_hosted()
        verdict = await authorizer.authorize(body.api_key)
        if verdict is AuthorizationVerdict.UNAVAILABLE:
            raise HTTPException(status_code=503, detail="authorization unavailable")
        return CompanionAuthorization(
            authorized=verdict is AuthorizationVerdict.ALLOWED,
            ttl_seconds=cache_ttl_seconds,
        )

    @router.get(
        f"{COMPANION_PATH}/secrets",
        response_model=CompanionSecrets,
        dependencies=[Depends(verify_token)],
        include_in_schema=False,
    )
    async def secrets(
        deployment_id: str,
    ) -> CompanionSecrets | JSONResponse:
        record = records.get_companion_record(deployment_id)
        if record is None:
            return _deployment_not_hosted()
        try:
            values = await secret_source.resolve(deployment_id, record.secret_references)
        except SecretUnavailable as error:
            raise HTTPException(status_code=503, detail="secrets unavailable") from error
        return CompanionSecrets(values=dict(values), ttl_seconds=cache_ttl_seconds)

    return router


def _deployment_not_hosted() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": "Deployment not hosted", "code": "deployment_not_hosted"},
    )
