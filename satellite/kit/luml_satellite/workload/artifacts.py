from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import parse_qs, urlparse

from luml_satellite.tokens import TokenDeriver
from luml_satellite.wire import ArtifactDownload, Deployment, PlatformRefusal
from luml_satellite.workload.driver import ArtifactDeliveryMode, ArtifactHandle

_AMZ_DATE_FORMAT = "%Y%m%dT%H%M%SZ"
_ARTIFACT_ROUTE = "/satellites/deployments/{deployment_id}/artifact"


class ArtifactResolutionError(RuntimeError):
    pass


class ArtifactTokenError(PermissionError):
    pass


class ArtifactPlatform(Protocol):
    async def get_deployment(self, deployment_id: str) -> Deployment: ...

    async def get_artifact_download_url(self, artifact_id: str) -> str: ...


class ArtifactPusher(Protocol):
    async def push(self, deployment: Deployment, artifact: ArtifactDownload) -> str: ...


class ArtifactResolver:
    def __init__(
        self,
        platform: ArtifactPlatform,
        token_deriver: TokenDeriver,
        *,
        satellite_address: str | None = None,
        pusher: ArtifactPusher | None = None,
    ) -> None:
        self._platform = platform
        self._tokens = token_deriver
        self._satellite_address = satellite_address.rstrip("/") if satellite_address else None
        self._pusher = pusher

    async def resolve(
        self,
        deployment: Deployment,
        mode: ArtifactDeliveryMode,
    ) -> ArtifactHandle:
        deployment_id = str(deployment.id)
        artifact_id = str(deployment.artifact_id)
        token = self._tokens.artifact_token(deployment_id)
        refresh_url = self._refresh_url(deployment_id)

        if mode is ArtifactDeliveryMode.ON_DEMAND:
            if refresh_url is None:
                raise ArtifactResolutionError(
                    "on-demand artifact delivery requires a satellite address"
                )
            return ArtifactHandle(
                artifact_id=artifact_id,
                mode=mode,
                refresh_url=refresh_url,
                token=token,
            )

        download = await self._download(artifact_id)
        if mode is ArtifactDeliveryMode.PRESIGNED_LINK:
            return ArtifactHandle(
                artifact_id=artifact_id,
                mode=mode,
                download_url=download.url,
                refresh_url=refresh_url,
                token=token if refresh_url is not None else None,
                expires_at=download.expires_at,
            )

        if mode is not ArtifactDeliveryMode.PUSH:
            raise ArtifactResolutionError(f"unsupported artifact delivery mode: {mode}")
        if self._pusher is None:
            raise ArtifactResolutionError("push artifact delivery requires an artifact pusher")
        provider_ref = await self._pusher.push(deployment, download)
        if not provider_ref:
            raise ArtifactResolutionError("artifact pusher returned an empty provider reference")
        return ArtifactHandle(
            artifact_id=artifact_id,
            mode=mode,
            provider_ref=provider_ref,
        )

    async def resolve_download(self, deployment_id: str, token: str | None) -> ArtifactDownload:
        if not self.verify_token(deployment_id, token):
            raise ArtifactTokenError("invalid artifact token")
        try:
            deployment = await self._platform.get_deployment(deployment_id)
        except PlatformRefusal as error:
            if error.status_code in {404, 410}:
                raise KeyError(deployment_id) from error
            raise
        return await self._download(str(deployment.artifact_id))

    def verify_token(self, deployment_id: str, token: str | None) -> bool:
        return self._tokens.verify_artifact_token(deployment_id, token)

    async def _download(self, artifact_id: str) -> ArtifactDownload:
        try:
            url = await self._platform.get_artifact_download_url(artifact_id)
        except Exception as error:
            raise ArtifactResolutionError(
                f"could not resolve artifact '{artifact_id}': {error}"
            ) from error
        if not url:
            raise ArtifactResolutionError(
                f"platform returned an empty download URL for artifact '{artifact_id}'"
            )
        return ArtifactDownload(
            url=url,
            artifact_id=artifact_id,
            expires_at=presigned_expiry(url),
        )

    def _refresh_url(self, deployment_id: str) -> str | None:
        if self._satellite_address is None:
            return None
        return f"{self._satellite_address}{_ARTIFACT_ROUTE.format(deployment_id=deployment_id)}"


def presigned_expiry(url: str) -> datetime | None:
    query = parse_qs(urlparse(url).query)
    signed_values = query.get("X-Amz-Date")
    lifetime_values = query.get("X-Amz-Expires")
    if not signed_values or not lifetime_values:
        return None
    signed_at = signed_values[0]
    lifetime = lifetime_values[0]
    try:
        start = datetime.strptime(signed_at, _AMZ_DATE_FORMAT).replace(tzinfo=UTC)
        return start + timedelta(seconds=int(lifetime))
    except TypeError, ValueError:
        return None


type ArtifactPushHandler = Callable[[Deployment, ArtifactDownload], Awaitable[str]]
