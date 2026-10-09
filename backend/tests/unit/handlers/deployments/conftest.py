from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest
from luml.handlers.deployments import DeploymentHandler
from luml.schemas.artifacts import ArtifactStatus
from luml.schemas.satellite import get_present_capabilities, normalize_capabilities

from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[DeploymentHandler]:
    return mock_collaborators(DeploymentHandler())


def _capabilities(
    *,
    deploy: bool = True,
    monitoring: bool = True,
    deploy_api_versions: list[int] | None = None,
    monitoring_api_versions: list[int] | None = None,
    supported_variants: list[str] | None = None,
    supported_tags_combinations: list[list[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    capabilities: dict[str, dict[str, Any]] = {}
    if deploy:
        capabilities["deploy"] = {
            "version": 1,
            "supported_variants": (
                ["pyfunc"] if supported_variants is None else supported_variants
            ),
            "supported_tags_combinations": supported_tags_combinations,
        }
        if deploy_api_versions is not None:
            capabilities["deploy"]["api_versions"] = deploy_api_versions
    if monitoring:
        capabilities["monitoring"] = {"version": 1}
        if monitoring_api_versions is not None:
            capabilities["monitoring"]["api_versions"] = monitoring_api_versions
    return capabilities


def _satellite(orbit_id: UUID, capabilities: dict[str, dict[str, Any]]) -> Mock:
    normalized = normalize_capabilities(capabilities)
    return Mock(
        orbit_id=orbit_id,
        capabilities=normalized,
        present_capabilities=get_present_capabilities(normalized),
    )


def _artifact(
    collection_id: UUID,
    *,
    variant: str = "pyfunc",
    producer_tags: list[str] | None = None,
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
) -> Mock:
    return Mock(
        collection_id=collection_id,
        status=status,
        manifest=Mock(
            variant=variant,
            producer_tags=producer_tags or [],
        ),
    )
