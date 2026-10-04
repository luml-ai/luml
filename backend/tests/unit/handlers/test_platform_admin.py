import logging
from collections.abc import Iterator
from datetime import UTC, datetime

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

from tests.support.ids import ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

ADMIN = PlatformAdmin(
    email="admin@luml.ai",
    auth_method=PlatformAdminAuthMethod.GOOGLE,
    expires_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.fixture
def mocks() -> CollaboratorMocks[PlatformAdminHandler]:
    return mock_collaborators(PlatformAdminHandler())


@pytest.fixture
def audit_log(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pytest.LogCaptureFixture]:
    monkeypatch.setattr(audit_logger, "disabled", False)
    with caplog.at_level(logging.INFO, logger=audit_logger.name):
        yield caplog


class TestPlatformAdminHandler:
    async def test_update_organization_limits_writes_audit_line(
        self,
        mocks: CollaboratorMocks[PlatformAdminHandler],
        audit_log: pytest.LogCaptureFixture,
    ) -> None:
        mocks.repository.update_organization_limits.return_value = (
            PlatformAdminOrganizationDetails(
                id=ORGANIZATION_ID,
                name="Acme",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                limits=OrganizationLimits(
                    members_limit=3,
                    orbits_limit=9,
                    satellites_limit=2,
                    artifacts_limit=50,
                ),
                usage=OrganizationUsage(members=1, orbits=1, satellites=0, artifacts=0),
                members=[],
            )
        )

        await mocks.handler.update_organization_limits(
            ADMIN, ORGANIZATION_ID, OrganizationLimitsUpdate(orbits_limit=9)
        )

        assert len(audit_log.records) == 1
        message = audit_log.records[0].getMessage()
        assert "action=organization.limits.update" in message
        assert f"target={ORGANIZATION_ID}" in message
        assert "admin=admin@luml.ai" in message
        assert "'orbits_limit': 9" in message

    async def test_update_organization_limits_skips_audit_line_when_not_found(
        self,
        mocks: CollaboratorMocks[PlatformAdminHandler],
        audit_log: pytest.LogCaptureFixture,
    ) -> None:
        mocks.repository.update_organization_limits.return_value = None

        with pytest.raises(NotFoundError):
            await mocks.handler.update_organization_limits(
                ADMIN, ORGANIZATION_ID, OrganizationLimitsUpdate(orbits_limit=9)
            )

        assert audit_log.records == []

    async def test_update_user_raises_not_found_when_user_unknown(
        self, mocks: CollaboratorMocks[PlatformAdminHandler]
    ) -> None:
        mocks.repository.update_user.return_value = None

        with pytest.raises(NotFoundError):
            await mocks.handler.update_user(
                ADMIN, USER_ID, PlatformAdminUserUpdate(disabled=True)
            )

    async def test_get_organization_raises_not_found_when_organization_unknown(
        self, mocks: CollaboratorMocks[PlatformAdminHandler]
    ) -> None:
        mocks.repository.get_organization_details.return_value = None

        with pytest.raises(NotFoundError):
            await mocks.handler.get_organization(ORGANIZATION_ID)
