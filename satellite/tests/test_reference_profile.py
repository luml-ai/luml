from typing import Self

import httpx
import pytest

from agent.clients.model_server_client import ModelServerClient
from agent.handlers import model_server_handler
from agent.handlers.model_server_handler import ModelServerHandler
from agent.schemas import Deployment, usable_reference_profile

READY_PROFILE: dict = {
    "task_type": "regression",
    "profile_status": "ready",
    "feature_summaries": {"numerical_features": {}, "categorical_features": {}},
}

PLACEHOLDER_PROFILE: dict = {
    "task_type": "regression",
    "profile_status": "placeholder",
}


class FakeModelServerClient:
    """Stands in for ModelServerClient so the deploy path runs without a container."""

    def __init__(
        self,
        *,
        manifest: dict | None = None,
        openapi_schema: dict | None = None,
        reference_profile: dict | None = None,
    ) -> None:
        self._manifest = manifest
        self._openapi_schema = openapi_schema
        self._reference_profile = reference_profile

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get_manifest(self, deployment_id: str) -> dict | None:
        return self._manifest

    async def get_openapi_schema(self, deployment_id: str) -> dict | None:
        return self._openapi_schema

    async def get_reference_profile(self, deployment_id: str) -> dict | None:
        return self._reference_profile


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reference_profile: dict | None = None,
) -> None:
    def _factory(*args: object, **kwargs: object) -> FakeModelServerClient:
        return FakeModelServerClient(reference_profile=reference_profile)

    monkeypatch.setattr(model_server_handler, "ModelServerClient", _factory)


def _make_deployment(deployment_id: str) -> Deployment:
    return Deployment(
        id=deployment_id,
        orbit_id="orbit-1",
        satellite_id="sat-1",
        satellite_name="sat",
        name="model",
        artifact_id="artifact-1",
        artifact_name="model",
        collection_id="coll-1",
        status="pending",
        created_at="2026-01-01T00:00:00Z",
    )


def test_usable_reference_profile_returns_ready_profile() -> None:
    assert usable_reference_profile(READY_PROFILE) == READY_PROFILE


def test_usable_reference_profile_treats_placeholder_as_no_profile() -> None:
    assert usable_reference_profile(PLACEHOLDER_PROFILE) is None


def test_usable_reference_profile_treats_missing_status_as_no_profile() -> None:
    assert usable_reference_profile({"task_type": "regression"}) is None


@pytest.mark.parametrize("profile", [None, {}])
def test_usable_reference_profile_treats_empty_as_no_profile(profile: dict | None) -> None:
    assert usable_reference_profile(profile) is None


async def test_deploy_loads_reference_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_client(monkeypatch, reference_profile=READY_PROFILE)
    handler = ModelServerHandler()

    await handler.add_deployment(_make_deployment("dep-ready"))

    local = await handler.get_deployment("dep-ready")
    assert local is not None
    assert local.reference_profile == READY_PROFILE


@pytest.mark.parametrize("profile", [None, {}])
async def test_deploy_without_profile_marks_no_profile(
    monkeypatch: pytest.MonkeyPatch, profile: dict | None
) -> None:
    _install_fake_client(monkeypatch, reference_profile=profile)
    handler = ModelServerHandler()

    await handler.add_deployment(_make_deployment("dep-none"))

    local = await handler.get_deployment("dep-none")
    assert local is not None
    assert local.reference_profile is None


async def test_deploy_with_placeholder_profile_marks_no_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_client(monkeypatch, reference_profile=PLACEHOLDER_PROFILE)
    handler = ModelServerHandler()

    await handler.add_deployment(_make_deployment("dep-placeholder"))

    local = await handler.get_deployment("dep-placeholder")
    assert local is not None
    assert local.reference_profile is None


async def test_client_returns_profile_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/reference_profile"
        return httpx.Response(200, json=READY_PROFILE)

    client = ModelServerClient()
    client._session = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.get_reference_profile("dep-1")
    finally:
        await client._session.aclose()

    assert result == READY_PROFILE


async def test_client_returns_none_when_endpoint_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = ModelServerClient()
    client._session = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.get_reference_profile("dep-1")
    finally:
        await client._session.aclose()

    assert result is None
