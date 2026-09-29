import time
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
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

SECRET = "unit-test-secret"
ALGORITHM = "HS256"

ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
DEPLOYMENT_ID = UUID("0199c337-09f7-751e-add2-d952f0d6cf4e")
SATELLITE_ID = UUID("0199c337-09f9-706e-9b80-58939d5fba79")
USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
BASE_URL = "https://satellite.example"

handler = MonitoringHandler(secret_key=SECRET, launch_token_expire=300)


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


# --- Eligibility --------------------------------------------------------------


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_eligibility_full_mode_and_capability(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(MonitoringMode.FULL)
    mock_get_satellite.return_value = _satellite()

    result = await handler.get_eligibility(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert result.eligible is True
    assert result.reason is None
    assert result.satellite_base_url == BASE_URL
    mock_check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.DEPLOYMENT, Action.READ, ORBIT_ID
    )


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_eligibility_off_mode(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(MonitoringMode.OFF)
    mock_get_satellite.return_value = _satellite()

    result = await handler.get_eligibility(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert result.eligible is False
    assert result.reason == MonitoringIneligibilityReason.MONITORING_OFF


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_eligibility_future_non_off_mode_inherits_capability_rules(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = Mock(
        monitoring_mode="sampled",
        satellite_id=SATELLITE_ID,
    )
    mock_get_satellite.return_value = _satellite()

    result = await handler.get_eligibility(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert result.eligible is True
    assert result.reason is None


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_eligibility_missing_capability(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(MonitoringMode.FULL)
    mock_get_satellite.return_value = _satellite(
        capabilities={"deploy": {"version": 1, "api_versions": [1]}}
    )

    result = await handler.get_eligibility(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert result.eligible is False
    assert result.reason == MonitoringIneligibilityReason.CAPABILITY_MISSING


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.parametrize(
    "declaration",
    [
        {"version": 7},
        {"version": 1, "api_versions": [3]},
    ],
)
@pytest.mark.asyncio
async def test_eligibility_unsupported_capability_version(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
    declaration: dict[str, Any],
) -> None:
    mock_get_deployment.return_value = _deployment(MonitoringMode.FULL)
    mock_get_satellite.return_value = _satellite(
        capabilities={"monitoring": declaration}
    )

    result = await handler.get_eligibility(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert result.eligible is False
    assert result.reason == MonitoringIneligibilityReason.CAPABILITY_VERSION_UNSUPPORTED


# --- Mint ---------------------------------------------------------------------


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_mint_launch_token_carries_scope_claims_and_expiry(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(MonitoringMode.FULL)
    mock_get_satellite.return_value = _satellite()

    result = await handler.mint_launch_token(
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
    assert result.launch_url == (f"{BASE_URL}/monitoring/launch?token={result.token}")


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_mint_launch_token_requires_deployment_access(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_check_permissions.side_effect = InsufficientPermissionsError()

    with pytest.raises(InsufficientPermissionsError):
        await handler.mint_launch_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

    mock_get_deployment.assert_not_awaited()


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_mint_launch_token_refused_when_off(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(MonitoringMode.OFF)
    mock_get_satellite.return_value = _satellite()

    with pytest.raises(ApplicationError) as err:
        await handler.mint_launch_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

    assert err.value.status_code == 409


# --- Introspection ------------------------------------------------------------


@patch(
    "luml.handlers.monitoring.MonitoringLaunchTokenRepository.consume",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_introspect_valid_token(mock_consume: AsyncMock) -> None:
    mock_consume.return_value = True
    jti = uuid7()
    exp = int(time.time()) + 300
    token = _make_token(jti=jti, exp=exp)

    result = await handler.introspect_token(SATELLITE_ID, token)

    assert result.active is True
    assert result.claims is not None
    assert result.claims.deployment_id == DEPLOYMENT_ID
    assert result.claims.satellite_id == SATELLITE_ID
    assert result.claims.user_id == USER_ID
    assert result.claims.scope == MONITORING_READ_SCOPE
    mock_consume.assert_awaited_once_with(jti, exp)


@patch(
    "luml.handlers.monitoring.MonitoringLaunchTokenRepository.consume",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_introspect_single_use(mock_consume: AsyncMock) -> None:
    consumed: set[UUID] = set()

    async def fake_consume(jti: UUID, expire_at: int) -> bool:
        if jti in consumed:
            return False
        consumed.add(jti)
        return True

    mock_consume.side_effect = fake_consume
    token = _make_token()

    first = await handler.introspect_token(SATELLITE_ID, token)
    second = await handler.introspect_token(SATELLITE_ID, token)

    assert first.active is True
    assert second.active is False
    assert second.claims is None


@patch(
    "luml.handlers.monitoring.MonitoringLaunchTokenRepository.consume",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_introspect_expired_token(mock_consume: AsyncMock) -> None:
    token = _make_token(exp=int(time.time()) - 10)

    result = await handler.introspect_token(SATELLITE_ID, token)

    assert result.active is False
    mock_consume.assert_not_awaited()


@patch(
    "luml.handlers.monitoring.MonitoringLaunchTokenRepository.consume",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_introspect_invalid_signature(mock_consume: AsyncMock) -> None:
    bad_token = jwt.encode(
        {"scope": MONITORING_READ_SCOPE, "exp": int(time.time()) + 300},
        "a-different-secret",
        algorithm=ALGORITHM,
    )

    result = await handler.introspect_token(SATELLITE_ID, bad_token)

    assert result.active is False
    mock_consume.assert_not_awaited()


@patch(
    "luml.handlers.monitoring.MonitoringLaunchTokenRepository.consume",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_introspect_wrong_scope(mock_consume: AsyncMock) -> None:
    token = _make_token(scope="inference:write")

    result = await handler.introspect_token(SATELLITE_ID, token)

    assert result.active is False
    mock_consume.assert_not_awaited()


@patch(
    "luml.handlers.monitoring.MonitoringLaunchTokenRepository.consume",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_introspect_wrong_satellite_does_not_consume(
    mock_consume: AsyncMock,
) -> None:
    token = _make_token(satellite_id=SATELLITE_ID)
    other_satellite = UUID("0199c337-0aaa-7000-8000-000000000000")

    result = await handler.introspect_token(other_satellite, token)

    assert result.active is False
    mock_consume.assert_not_awaited()


# --- Missing deployment or satellite -----------------------------------------


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_eligibility_deployment_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = None

    with pytest.raises(NotFoundError, match="Deployment not found"):
        await handler.get_eligibility(USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID)

    mock_get_deployment.assert_awaited_once_with(DEPLOYMENT_ID, ORBIT_ID)
    mock_get_satellite.assert_not_awaited()


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_eligibility_satellite_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(MonitoringMode.FULL)
    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found"):
        await handler.get_eligibility(USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID)

    mock_get_satellite.assert_awaited_once_with(SATELLITE_ID)


# --- Launch token without a satellite base URL --------------------------------


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_monitoring_launch_without_any_address(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(
        MonitoringMode.FULL, "/deployments/id/monitoring"
    )
    mock_get_satellite.return_value = _satellite(base_url=None)

    eligibility = await handler.get_eligibility(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert eligibility.eligible is False
    assert eligibility.reason == MonitoringIneligibilityReason.NO_DASHBOARD_ADDRESS
    assert eligibility.satellite_base_url is None

    with pytest.raises(ApplicationError, match="dashboard address") as error:
        await handler.mint_launch_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
        )

    assert error.value.status_code == 409


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_monitoring_launch_uses_an_external_link_without_satellite_address(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    external_link = "https://monitoring.example/dashboards/deployment"
    mock_get_deployment.return_value = _deployment(MonitoringMode.FULL, external_link)
    mock_get_satellite.return_value = _satellite(base_url=None)

    eligibility = await handler.get_eligibility(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )
    result = await handler.mint_launch_token(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert eligibility.eligible is True
    assert result.satellite_base_url is None
    assert result.launch_url == (
        f"{external_link}/monitoring/launch?token={result.token}"
    )


@patch(
    "luml.handlers.monitoring.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.DeploymentRepository.get_deployment",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.monitoring.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_monitoring_launch_uses_satellite_address_for_a_relative_link(
    mock_check_permissions: AsyncMock,
    mock_get_deployment: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    mock_get_deployment.return_value = _deployment(
        MonitoringMode.FULL, "/deployments/id/monitoring"
    )
    mock_get_satellite.return_value = _satellite(base_url=f"{BASE_URL}/")

    result = await handler.mint_launch_token(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, DEPLOYMENT_ID
    )

    assert result.satellite_base_url == f"{BASE_URL}/"
    assert result.launch_url == (f"{BASE_URL}/monitoring/launch?token={result.token}")


# --- Introspection of a token with malformed claims ---------------------------


@patch(
    "luml.handlers.monitoring.MonitoringLaunchTokenRepository.consume",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_introspect_malformed_claims_are_inactive(
    mock_consume: AsyncMock,
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

    result = await handler.introspect_token(SATELLITE_ID, token)

    assert result.active is False
    assert result.claims is None
    mock_consume.assert_not_awaited()
