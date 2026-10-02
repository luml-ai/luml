import time
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid7

import jwt
import pytest
from luml.handlers.monitoring import MonitoringHandler
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.schemas.deployment import MonitoringMode
from luml.schemas.monitoring import (
    MONITORING_READ_SCOPE,
    MonitoringIneligibilityReason,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import get_present_capabilities

from tests.support.ids import (
    DEPLOYMENT_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    SATELLITE_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks, mock_collaborators

SECRET = "unit-test-secret"
ALGORITHM = "HS256"
BASE_URL = "https://satellite.example"


@pytest.fixture
def mocks() -> CollaboratorMocks[MonitoringHandler]:
    return mock_collaborators(
        MonitoringHandler(secret_key=SECRET, launch_token_expire=300)
    )


def _deployment(
    mode: MonitoringMode = MonitoringMode.FULL,
    monitoring_url: str | None = None,
) -> Mock:
    return Mock(
        monitoring_mode=mode,
        monitoring_url=monitoring_url,
        satellite_id=SATELLITE_ID,
    )


def _satellite(
    *,
    capabilities: dict[str, dict[str, Any]] | None = None,
    base_url: str | None = BASE_URL,
) -> Mock:
    if capabilities is None:
        capabilities = {
            "monitoring": {"version": 1, "api_versions": [1]},
        }
    return Mock(
        capabilities=capabilities,
        present_capabilities=get_present_capabilities(capabilities),
        base_url=base_url,
    )


def _make_token(
    *,
    deployment_id: UUID = DEPLOYMENT_ID,
    satellite_id: UUID = SATELLITE_ID,
    user_id: UUID = USER_ID,
    scope: str = MONITORING_READ_SCOPE,
    jti: UUID | None = None,
    exp: int | None = None,
) -> str:
    claims = {
        "deployment_id": str(deployment_id),
        "satellite_id": str(satellite_id),
        "user_id": str(user_id),
        "scope": scope,
        "jti": str(jti or uuid7()),
        "exp": exp if exp is not None else int(time.time()) + 300,
    }
    return jwt.encode(claims, SECRET, algorithm=ALGORITHM)


class TestMonitoringHandler:
    async def test_get_eligibility_returns_eligible_when_full_mode_and_capability(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite()

        result = await mocks.handler.get_eligibility(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result.eligible is True
        assert result.reason is None
        assert result.satellite_base_url == BASE_URL
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.READ, ORBIT_ID
        )

    async def test_get_eligibility_returns_monitoring_off_when_mode_off(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.OFF
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite()

        result = await mocks.handler.get_eligibility(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result.eligible is False
        assert result.reason == MonitoringIneligibilityReason.MONITORING_OFF

    async def test_get_eligibility_applies_capability_rules_when_mode_unknown(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = Mock(
            monitoring_mode="sampled",
            satellite_id=SATELLITE_ID,
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite()

        result = await mocks.handler.get_eligibility(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result.eligible is True
        assert result.reason is None

    async def test_get_eligibility_returns_capability_missing_when_not_declared(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite(
            capabilities={"deploy": {"version": 1, "api_versions": [1]}}
        )

        result = await mocks.handler.get_eligibility(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result.eligible is False
        assert result.reason == MonitoringIneligibilityReason.CAPABILITY_MISSING

    @pytest.mark.parametrize(
        "declaration",
        [
            {"version": 7},
            {"version": 1, "api_versions": [3]},
        ],
    )
    async def test_get_eligibility_returns_version_unsupported_when_version_unknown(
        self,
        mocks: CollaboratorMocks[MonitoringHandler],
        declaration: dict[str, Any],
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite(
            capabilities={"monitoring": declaration}
        )

        result = await mocks.handler.get_eligibility(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result.eligible is False
        assert (
            result.reason
            == MonitoringIneligibilityReason.CAPABILITY_VERSION_UNSUPPORTED
        )

    async def test_get_eligibility_raises_not_found_when_deployment_missing(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = None

        with pytest.raises(NotFoundError, match="Deployment not found"):
            await mocks.handler.get_eligibility(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        mocks.deployment_repo.get_deployment.assert_awaited_once_with(
            DEPLOYMENT_ID, ORBIT_ID
        )
        mocks.satellite_repo.get_satellite.assert_not_awaited()

    async def test_get_eligibility_raises_not_found_when_satellite_missing(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL
        )
        mocks.satellite_repo.get_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found"):
            await mocks.handler.get_eligibility(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        mocks.satellite_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)

    async def test_mint_launch_token_returns_token_with_scope_claims_and_expiry(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite()

        result = await mocks.handler.mint_launch_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        decoded = jwt.decode(result.token, SECRET, algorithms=[ALGORITHM])
        assert decoded["scope"] == MONITORING_READ_SCOPE
        assert decoded["deployment_id"] == str(DEPLOYMENT_ID)
        assert decoded["satellite_id"] == str(SATELLITE_ID)
        assert decoded["user_id"] == str(USER_ID)
        assert UUID(decoded["jti"])
        assert decoded["exp"] > int(time.time())
        assert result.expires_at == decoded["exp"]
        assert result.satellite_base_url == BASE_URL
        assert result.launch_url == (
            f"{BASE_URL}/monitoring/launch?token={result.token}"
        )

    async def test_mint_launch_token_raises_insufficient_permissions_when_access_denied(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        with pytest.raises(InsufficientPermissionsError):
            await mocks.handler.mint_launch_token(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        mocks.deployment_repo.get_deployment.assert_not_awaited()

    async def test_mint_launch_token_raises_conflict_when_monitoring_off(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.OFF
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite()

        with pytest.raises(ApplicationError) as err:
            await mocks.handler.mint_launch_token(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        assert err.value.status_code == 409

    async def test_launch_is_refused_when_no_dashboard_address(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL, "/deployments/id/monitoring"
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite(base_url=None)

        eligibility = await mocks.handler.get_eligibility(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert eligibility.eligible is False
        assert eligibility.reason == MonitoringIneligibilityReason.NO_DASHBOARD_ADDRESS
        assert eligibility.satellite_base_url is None

        with pytest.raises(ApplicationError, match="dashboard address") as error:
            await mocks.handler.mint_launch_token(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
            )

        assert error.value.status_code == 409

    async def test_mint_launch_token_uses_external_link_when_satellite_has_no_address(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        external_link = "https://monitoring.example/dashboards/deployment"
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL, external_link
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite(base_url=None)

        eligibility = await mocks.handler.get_eligibility(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )
        result = await mocks.handler.mint_launch_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert eligibility.eligible is True
        assert result.satellite_base_url is None
        assert result.launch_url == (
            f"{external_link}/monitoring/launch?token={result.token}"
        )

    async def test_mint_launch_token_uses_satellite_address_when_link_relative(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.deployment_repo.get_deployment.return_value = _deployment(
            MonitoringMode.FULL, "/deployments/id/monitoring"
        )
        mocks.satellite_repo.get_satellite.return_value = _satellite(
            base_url=f"{BASE_URL}/"
        )

        result = await mocks.handler.mint_launch_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

        assert result.satellite_base_url == f"{BASE_URL}/"
        assert result.launch_url == (
            f"{BASE_URL}/monitoring/launch?token={result.token}"
        )

    async def test_introspect_token_returns_active_claims_when_token_valid(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        mocks.launch_token_repo.consume.return_value = True
        jti = uuid7()
        exp = int(time.time()) + 300
        token = _make_token(jti=jti, exp=exp)

        result = await mocks.handler.introspect_token(SATELLITE_ID, token)

        assert result.active is True
        assert result.claims is not None
        assert result.claims.deployment_id == DEPLOYMENT_ID
        assert result.claims.satellite_id == SATELLITE_ID
        assert result.claims.user_id == USER_ID
        assert result.claims.scope == MONITORING_READ_SCOPE
        mocks.launch_token_repo.consume.assert_awaited_once_with(jti, exp)

    async def test_introspect_token_returns_inactive_when_token_reused(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        consumed: set[UUID] = set()

        async def fake_consume(jti: UUID, expire_at: int) -> bool:
            if jti in consumed:
                return False
            consumed.add(jti)
            return True

        mocks.launch_token_repo.consume.side_effect = fake_consume
        token = _make_token()

        first = await mocks.handler.introspect_token(SATELLITE_ID, token)
        second = await mocks.handler.introspect_token(SATELLITE_ID, token)

        assert first.active is True
        assert second.active is False
        assert second.claims is None

    async def test_introspect_token_returns_inactive_when_token_expired(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        token = _make_token(exp=int(time.time()) - 10)

        result = await mocks.handler.introspect_token(SATELLITE_ID, token)

        assert result.active is False
        mocks.launch_token_repo.consume.assert_not_awaited()

    async def test_introspect_token_returns_inactive_when_signature_invalid(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        bad_token = jwt.encode(
            {"scope": MONITORING_READ_SCOPE, "exp": int(time.time()) + 300},
            "a-different-secret",
            algorithm=ALGORITHM,
        )

        result = await mocks.handler.introspect_token(SATELLITE_ID, bad_token)

        assert result.active is False
        mocks.launch_token_repo.consume.assert_not_awaited()

    async def test_introspect_token_returns_inactive_when_scope_wrong(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        token = _make_token(scope="inference:write")

        result = await mocks.handler.introspect_token(SATELLITE_ID, token)

        assert result.active is False
        mocks.launch_token_repo.consume.assert_not_awaited()

    async def test_introspect_token_returns_inactive_when_satellite_differs(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        token = _make_token(satellite_id=SATELLITE_ID)
        foreign_satellite_id = UUID("0199c337-0aaa-7000-8000-000000000000")

        result = await mocks.handler.introspect_token(foreign_satellite_id, token)

        assert result.active is False
        mocks.launch_token_repo.consume.assert_not_awaited()

    async def test_introspect_token_returns_inactive_when_claims_malformed(
        self, mocks: CollaboratorMocks[MonitoringHandler]
    ) -> None:
        claims = {
            "deployment_id": "not-a-uuid",
            "satellite_id": str(SATELLITE_ID),
            "user_id": str(USER_ID),
            "scope": MONITORING_READ_SCOPE,
            "jti": str(uuid7()),
            "exp": int(time.time()) + 300,
        }
        token = jwt.encode(claims, SECRET, algorithm=ALGORITHM)

        result = await mocks.handler.introspect_token(SATELLITE_ID, token)

        assert result.active is False
        assert result.claims is None
        mocks.launch_token_repo.consume.assert_not_awaited()
