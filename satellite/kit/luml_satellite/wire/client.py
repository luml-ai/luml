import json
import logging
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import httpx

from luml_satellite.wire.contract import (
    ContractComparison,
    compare_contract,
    log_contract_comparison,
)
from luml_satellite.wire.deployments import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    ErrorMessage,
)
from luml_satellite.wire.errors import (
    AuthenticationFailure,
    LegacyAddressRequired,
    PlatformError,
    PlatformRefusal,
)
from luml_satellite.wire.monitoring import MonitoringIntrospection
from luml_satellite.wire.pairing import KitInfo, PairedSatellite, PairingRequest, SatelliteContract
from luml_satellite.wire.tasks import SatelliteTaskStatus

_REFUSAL_STATUSES = frozenset({400, 404, 409, 410, 422})
_AUTHENTICATION_STATUSES = frozenset({401, 403})
_LEGACY_ADDRESS_MESSAGE = "this platform requires BASE_URL; set BASE_URL or upgrade the platform"


class PlatformClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout_s: float | httpx.Timeout = 30.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._transport = transport
        self._logger = logger or logging.getLogger("luml_satellite")
        self._session: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._session = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            headers=self._headers,
            transport=self._transport,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def list_tasks(
        self, status: SatelliteTaskStatus | str | None = None
    ) -> list[dict[str, Any]]:
        params = {"status": str(status)} if status is not None else None
        response = await self._request("GET", "/satellites/v1/tasks", params=params)
        return _dict_list(response.json(), "task listing")

    async def update_task_status(
        self,
        task_id: str | UUID,
        status: SatelliteTaskStatus | str,
        result: ErrorMessage | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"status": str(status)}
        if result is not None:
            body["result"] = (
                result.model_dump(mode="json", exclude_unset=True)
                if isinstance(result, ErrorMessage)
                else result
            )
        response = await self._request(
            "POST", f"/satellites/v1/tasks/{task_id}/status", json_body=body
        )
        return _dict(response.json(), "task update")

    async def update_deployment_status(
        self,
        deployment_id: str | UUID,
        status: DeploymentStatus | str,
    ) -> dict[str, Any]:
        response = await self._request(
            "PATCH",
            f"/satellites/v1/deployments/{deployment_id}/status",
            json_body={"status": str(status)},
        )
        return _dict(response.json(), "deployment status update")

    async def delete_deployment(self, deployment_id: str | UUID) -> None:
        await self._request("DELETE", f"/satellites/v1/deployments/{deployment_id}")

    async def pair_satellite(
        self,
        base_url: str | None,
        capabilities: dict[str, Any],
        slug: str | None = None,
        openapi: dict[str, Any] | None = None,
        kit: KitInfo | dict[str, Any] | None = None,
    ) -> PairedSatellite:
        kit_info = KitInfo.model_validate(kit) if kit is not None else None
        request = PairingRequest(
            base_url=base_url,
            capabilities=capabilities,
            slug=slug,
            openapi=openapi,
            kit=kit_info,
        )
        body = request.model_dump(mode="json", exclude_none=True)
        try:
            response = await self._request("POST", "/satellites/v1/pair", json_body=body)
        except PlatformRefusal as error:
            if (
                error.status_code == 422
                and base_url is None
                and _detail_mentions_field(error.detail, "base_url")
            ):
                self._logger.error(_LEGACY_ADDRESS_MESSAGE)
                raise LegacyAddressRequired(
                    _LEGACY_ADDRESS_MESSAGE,
                    status_code=error.status_code,
                    detail=error.detail,
                ) from error
            if error.status_code == 422:
                self._logger.error("platform refused pairing: %s", _format_detail(error.detail))
            raise
        return PairedSatellite.model_validate(response.json())

    async def get_contract(self) -> SatelliteContract:
        response = await self._request("GET", "/satellites/v1/contract")
        return SatelliteContract.model_validate(response.json())

    async def check_contract(self) -> ContractComparison:
        try:
            contract = await self.get_contract()
        except (PlatformError, ValueError) as error:
            comparison = ContractComparison.unavailable(str(error))
        else:
            comparison = compare_contract(contract)
        log_contract_comparison(comparison, self._logger)
        return comparison

    async def authorize_inference_access(self, api_key: str) -> bool:
        response = await self._request(
            "POST",
            "/satellites/v1/deployments/inference-access",
            json_body={"api_key": api_key},
        )
        return bool(_dict(response.json(), "inference authorization").get("authorized", False))

    async def introspect_monitoring_token(self, token: str) -> MonitoringIntrospection:
        response = await self._request(
            "POST", "/satellites/v1/monitoring/introspect", json_body={"token": token}
        )
        return MonitoringIntrospection.model_validate(response.json())

    async def get_artifact_download_url(self, artifact_id: str | UUID) -> str:
        response = await self._request(
            "GET", f"/satellites/v1/artifacts/{artifact_id}/download-url"
        )
        return str(_dict(response.json(), "artifact download URL").get("url", ""))

    async def get_artifact(self, artifact_id: str | UUID) -> tuple[dict[str, Any], str]:
        response = await self._request("GET", f"/satellites/v1/artifacts/{artifact_id}")
        data = _dict(response.json(), "artifact")
        artifact = data.get("artifact", data.get("model"))
        if not isinstance(artifact, dict):
            artifact = {}
        return artifact, str(data.get("url", ""))

    async def get_orbit_secret(self, secret_id: str | UUID) -> dict[str, Any]:
        response = await self._request("GET", f"/satellites/v1/secrets/{secret_id}")
        return _dict(response.json(), "secret")

    async def get_orbit_secrets(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/satellites/v1/secrets")
        return _dict_list(response.json(), "secret listing")

    async def list_deployments(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/satellites/v1/deployments")
        return _dict_list(response.json(), "deployment listing")

    async def get_deployment(self, deployment_id: str | UUID) -> Deployment:
        response = await self._request("GET", f"/satellites/v1/deployments/{deployment_id}")
        return Deployment.model_validate(response.json())

    async def update_deployment(
        self,
        deployment_id: str | UUID,
        deployment: DeploymentUpdate,
    ) -> Deployment:
        response = await self._request(
            "PATCH",
            f"/satellites/v1/deployments/{deployment_id}",
            json_body=deployment.model_dump(mode="json", exclude_unset=True),
        )
        return Deployment.model_validate(response.json())

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: object | None = None,
    ) -> httpx.Response:
        if self._session is None:
            raise RuntimeError("PlatformClient must be used as an async context manager")
        try:
            if json_body is None:
                response = await self._session.request(method, path, params=params)
            else:
                response = await self._session.request(method, path, params=params, json=json_body)
        except httpx.RequestError as error:
            raise PlatformError(f"platform request failed: {error}") from error
        if response.is_success:
            return response

        detail = _response_detail(response)
        message = f"platform returned {response.status_code}: {_format_detail(detail)}"
        if response.status_code in _AUTHENTICATION_STATUSES:
            raise AuthenticationFailure(message, status_code=response.status_code, detail=detail)
        if response.status_code in _REFUSAL_STATUSES:
            raise PlatformRefusal(message, status_code=response.status_code, detail=detail)
        raise PlatformError(message, status_code=response.status_code, detail=detail)


def _dict(value: object, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlatformError(f"platform returned an invalid {description}")
    return value


def _dict_list(value: object, description: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise PlatformError(f"platform returned an invalid {description}")
    return value


def _response_detail(response: httpx.Response) -> object:
    try:
        data: object = response.json()
    except ValueError:
        return response.text
    if isinstance(data, dict) and "detail" in data:
        return data["detail"]
    return data


def _detail_mentions_field(detail: object, field: str) -> bool:
    if isinstance(detail, str):
        return field.lower() in detail.lower()
    if isinstance(detail, dict):
        return any(
            _detail_mentions_field(key, field) or _detail_mentions_field(value, field)
            for key, value in detail.items()
        )
    if isinstance(detail, list | tuple):
        return any(_detail_mentions_field(item, field) for item in detail)
    return False


def _format_detail(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return json.dumps(detail, sort_keys=True, default=str)
