import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from luml.handlers.platform_admin import PlatformAdminHandler, audit_logger
from luml.infra.exceptions import NotFoundError
from luml.schemas.platform_admin import (
    OrganizationLimits,
    OrganizationLimitsUpdate,
    OrganizationUsage,
    PlatformAdmin,
    PlatformAdminAuthMethod,
    PlatformAdminOrganizationDetails,
    PlatformAdminUserUpdate,
)

REPOSITORY = "luml.handlers.platform_admin.PlatformAdminRepository"
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ADMIN = PlatformAdmin(
    email="admin@luml.ai",
    auth_method=PlatformAdminAuthMethod.GOOGLE,
    expires_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@patch(f"{REPOSITORY}.update_organization_limits", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_limits_writes_audit_line(
    mock_update_limits: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    mock_update_limits.return_value = PlatformAdminOrganizationDetails(
        id=ORGANIZATION_ID,
        name="Acme",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        limits=OrganizationLimits(
            members_limit=3, orbits_limit=9, satellites_limit=2, artifacts_limit=50
        ),
        usage=OrganizationUsage(members=1, orbits=1, satellites=0, artifacts=0),
        members=[],
    )

    # Alembic's fileConfig in integration tests disables pre-existing loggers.
    with (
        patch.object(audit_logger, "disabled", False),
        caplog.at_level(logging.INFO, logger="luml.platform_admin.audit"),
    ):
        await PlatformAdminHandler().update_organization_limits(
            ADMIN, ORGANIZATION_ID, OrganizationLimitsUpdate(orbits_limit=9)
        )

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "action=organization.limits.update" in message
    assert f"target={ORGANIZATION_ID}" in message
    assert "admin=admin@luml.ai" in message
    assert "'orbits_limit': 9" in message


@patch(f"{REPOSITORY}.update_organization_limits", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_limits_of_unknown_organization(
    mock_update_limits: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    mock_update_limits.return_value = None

    with (
        patch.object(audit_logger, "disabled", False),
        caplog.at_level(logging.INFO, logger="luml.platform_admin.audit"),
        pytest.raises(NotFoundError),
    ):
        await PlatformAdminHandler().update_organization_limits(
            ADMIN, ORGANIZATION_ID, OrganizationLimitsUpdate(orbits_limit=9)
        )

    assert caplog.records == []


@patch(f"{REPOSITORY}.update_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_unknown_user(mock_update_user: AsyncMock) -> None:
    mock_update_user.return_value = None

    with pytest.raises(NotFoundError):
        await PlatformAdminHandler().update_user(
            ADMIN, USER_ID, PlatformAdminUserUpdate(disabled=True)
        )


@patch(f"{REPOSITORY}.get_organization_details", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_get_unknown_organization(mock_get_details: AsyncMock) -> None:
    mock_get_details.return_value = None

    with pytest.raises(NotFoundError):
        await PlatformAdminHandler().get_organization(ORGANIZATION_ID)
