import datetime
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from luml.handlers.satellites import SatelliteHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import (
    DEPLOY_FACETS,
    MAX_OPENAPI_DOCUMENT_SIZE_BYTES,
    MONITORING_FACETS,
    MONITORING_FEATURES,
    Satellite,
    SatelliteCreateIn,
    SatelliteCreateOut,
    SatellitePairIn,
    SatelliteQueueTask,
    SatelliteRegenerateApiKey,
    SatelliteTaskStatus,
    SatelliteTaskType,
    SatelliteUpdateIn,
    get_present_capabilities,
    normalize_capabilities,
)
from pydantic import HttpUrl, ValidationError

handler = SatelliteHandler()


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_satellites",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_satellites(
    mock_check_permissions: AsyncMock,
    mock_list_satellites: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

    expected = [
        Satellite(
            id=satellite_id,
            orbit_id=orbit_id,
            name="test",
            description=None,
            base_url="https://url.com",
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
    ]
    mock_list_satellites.return_value = expected

    result = await handler.list_satellites(user_id, organization_id, orbit_id)

    assert result == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )
    mock_list_satellites.assert_awaited_once_with(orbit_id, None)


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test",
        description=None,
        base_url="https://url.com",
        paired=False,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )
    mock_get_satellite.return_value = expected

    result = await handler.get_satellite(
        user_id, organization_id, orbit_id, satellite_id
    )

    assert result == expected
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.READ, orbit_id
    )


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite_openapi",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_openapi(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_get_satellite_openapi: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    document = {
        "openapi": "3.1.0",
        "paths": {"/health": {"get": {"summary": "Health"}}},
    }
    mock_get_satellite.return_value = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
    )
    mock_get_satellite_openapi.return_value = document

    result = await handler.get_satellite_openapi(
        user_id, organization_id, orbit_id, satellite_id
    )

    assert result == document
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.READ, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_get_satellite_openapi.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.get_satellite(user_id, organization_id, orbit_id, satellite_id)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.READ, orbit_id
    )


@patch(
    "luml.handlers.satellites.SatelliteHandler._check_organization_satellites_limit",
)
@patch(
    "luml.handlers.satellites.SatelliteHandler._get_key_hash",
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.create_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_public_user: AsyncMock,
    mock_create_satellite: AsyncMock,
    mock_get_key_hash: Mock,
    mock_check_organization_satellites_limit: AsyncMock,
) -> None:
    user_name = "John Doe"
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_create_in = SatelliteCreateIn(name="test-satellite")
    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url="https://url.com",
        paired=False,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_orbit_simple.return_value = Mock()
    mock_get_public_user.return_value = Mock(full_name=user_name)
    mock_create_satellite.return_value = mock_satellite
    mock_get_key_hash.return_value = str(uuid4())

    result = await handler.create_satellite(
        user_id, organization_id, orbit_id, satellite_create_in
    )

    assert isinstance(result, SatelliteCreateOut)
    assert result.satellite == mock_satellite
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_public_user.assert_awaited_once_with(user_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.CREATE, orbit_id
    )
    mock_check_organization_satellites_limit.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.satellites.SatelliteHandler._check_organization_satellites_limit",
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_orbit_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_organization_satellites_limit: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    satellite_create_in = SatelliteCreateIn(name="test-satellite")

    mock_get_orbit_simple.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_satellite(
            user_id, organization_id, orbit_id, satellite_create_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.CREATE, orbit_id
    )
    mock_check_organization_satellites_limit.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.satellites.SatelliteHandler._check_organization_satellites_limit",
)
@patch(
    "luml.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_user_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_public_user: AsyncMock,
    mock_check_organization_satellites_limit: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    satellite_create_in = SatelliteCreateIn(name="test-satellite")

    mock_get_orbit_simple.return_value = Mock()
    mock_get_public_user.return_value = None

    with pytest.raises(NotFoundError, match="User not found") as error:
        await handler.create_satellite(
            user_id, organization_id, orbit_id, satellite_create_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_public_user.assert_awaited_once_with(user_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.CREATE, orbit_id
    )
    mock_check_organization_satellites_limit.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}
    openapi = {
        "openapi": "3.1.0",
        "paths": {"/health": {"get": {"summary": "Health"}}},
    }

    unpaired_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url=None,
        paired=False,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )
    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url=base_url,
        paired=True,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=datetime.datetime.now(),
    )

    mock_get_satellite.return_value = unpaired_satellite
    mock_pair_satellite.return_value = expected

    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl(base_url),
        capabilities=capabilities,
        openapi=openapi,
    )
    satellite = await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert satellite == expected
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_awaited_once()
    pair_call = mock_pair_satellite.await_args
    assert pair_call is not None
    assert pair_call.args[0].openapi == openapi


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_without_openapi_clears_document(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    mock_get_satellite.return_value = Mock()
    mock_pair_satellite.return_value = Mock()

    await handler.pair_satellite(
        satellite_id,
        SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={"deploy": {"version": 1}},
        ),
    )

    pair_call = mock_pair_satellite.await_args
    assert pair_call is not None
    paired = pair_call.args[0]
    assert paired.openapi is None
    assert "openapi" in paired.model_fields_set


@pytest.mark.parametrize("openapi", [[], "not-an-object", 1, True])
def test_pair_satellite_rejects_non_object_openapi(openapi: object) -> None:
    with pytest.raises(ValidationError, match="openapi"):
        SatellitePairIn.model_validate(
            {
                "base_url": "https://satellite.example.com",
                "capabilities": {"deploy": {"version": 1}},
                "openapi": openapi,
            }
        )


def test_pair_satellite_accepts_openapi_at_size_cap() -> None:
    empty_document_size = len(
        json.dumps({"value": ""}, ensure_ascii=False, separators=(",", ":")).encode()
    )
    document = {"value": "x" * (MAX_OPENAPI_DOCUMENT_SIZE_BYTES - empty_document_size)}

    satellite = SatellitePairIn(
        base_url=HttpUrl("https://satellite.example.com"),
        capabilities={"deploy": {"version": 1}},
        openapi=document,
    )

    assert satellite.openapi == document


def test_pair_satellite_rejects_openapi_over_size_cap() -> None:
    document = {"value": "x" * MAX_OPENAPI_DOCUMENT_SIZE_BYTES}

    with pytest.raises(ValidationError, match="2 MB"):
        SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={"deploy": {"version": 1}},
            openapi=document,
        )


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_normalizes_reserved_capabilities(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    mock_get_satellite.return_value = Mock()
    mock_pair_satellite.return_value = Mock()
    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl("https://satellite.example.com"),
        capabilities={
            "deploy": {
                "version": 1,
                "supported_variants": ["pyfunc"],
                "supported_tags_combinations": [["luml.ai::kind_tabular:v1"]],
                "extra_fields_form_spec": [],
            },
            "monitoring": {"version": 1, "ignored": "value"},
        },
    )

    await handler.pair_satellite(satellite_id, satellite_pair_in)

    pair_call = mock_pair_satellite.await_args
    assert pair_call is not None
    paired = pair_call.args[0]
    assert paired.capabilities == {
        "deploy": {
            "version": 1,
            "api_versions": [1],
            "facets": DEPLOY_FACETS,
            "supported_variants": ["pyfunc"],
            "supported_tags_combinations": [["luml.ai::kind_tabular:v1"]],
            "extra_fields_form_spec": [],
        },
        "monitoring": {
            "version": 1,
            "api_versions": [1],
            "facets": MONITORING_FACETS,
            "features": MONITORING_FEATURES,
        },
    }


def test_bare_monitoring_declaration_is_complete_in_satellite_payload() -> None:
    capabilities = normalize_capabilities(
        {
            "deploy": {
                "version": 1,
                "supported_variants": ["pyfunc"],
                "supported_tags_combinations": None,
                "extra_fields_form_spec": [],
            },
            "monitoring": {"version": 1},
        }
    )
    satellite = Satellite(
        id=UUID("0199c418-8be4-737c-a5e4-997685950d42"),
        orbit_id=UUID("0199c337-09f3-753e-9def-b27745e69be6"),
        name="test-satellite",
        paired=True,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
    )

    assert capabilities["monitoring"] == {
        "version": 1,
        "api_versions": [1],
        "facets": MONITORING_FACETS,
        "features": MONITORING_FEATURES,
    }
    assert satellite.present_capabilities == ["deploy", "monitoring"]
    assert satellite.model_dump()["capabilities"] == capabilities


def test_satellite_payload_does_not_include_openapi() -> None:
    satellite = Satellite.model_validate(
        {
            "id": UUID("0199c418-8be4-737c-a5e4-997685950d42"),
            "orbit_id": UUID("0199c337-09f3-753e-9def-b27745e69be6"),
            "paired": True,
            "capabilities": {"deploy": {"version": 1}},
            "openapi": {"openapi": "3.1.0", "paths": {}},
            "created_at": datetime.datetime.now(),
        }
    )

    assert "openapi" not in satellite.model_dump()


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_stores_custom_capability_verbatim(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    declaration = {
        "version": 1,
        "api_versions": [1],
        "facets": ["deployment:custom.gpu_monitoring"],
        "vendor_setting": {"sample_rate": 0.5},
    }
    mock_get_satellite.return_value = Mock()
    mock_pair_satellite.return_value = Mock()

    await handler.pair_satellite(
        satellite_id,
        SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={"custom.gpu_monitoring": declaration},
        ),
    )

    pair_call = mock_pair_satellite.await_args
    assert pair_call is not None
    paired = pair_call.args[0]
    assert paired.capabilities == {"custom.gpu_monitoring": declaration}


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.parametrize("capability", ["monitorng", "gpu_monitoring"])
@pytest.mark.asyncio
async def test_pair_satellite_rejects_unknown_unprefixed_capability(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
    capability: str,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl("https://satellite.example.com"),
        capabilities={capability: {"version": 1}},
    )

    with pytest.raises(ApplicationError, match=capability) as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 422
    mock_get_satellite.assert_not_awaited()
    mock_pair_satellite.assert_not_awaited()


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.parametrize(
    "facet",
    [
        "deployment:monitoring",
        "deployment:gpu",
        "cluster:custom.gpu_monitoring",
    ],
)
@pytest.mark.asyncio
async def test_pair_satellite_rejects_invalid_custom_facet(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
    facet: str,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl("https://satellite.example.com"),
        capabilities={
            "custom.gpu_monitoring": {
                "version": 1,
                "facets": [facet],
            }
        },
    )

    with pytest.raises(ApplicationError, match=facet) as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 422
    mock_get_satellite.assert_not_awaited()
    mock_pair_satellite.assert_not_awaited()


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.parametrize(
    ("capability", "declaration"),
    [
        ("monitoring", {"version": 1, "features": "runtime"}),
        ("monitoring", {"version": 1, "facets": ["satellite:future"]}),
        ("deploy", {"version": 1, "supported_variants": "pyfunc"}),
    ],
)
@pytest.mark.asyncio
async def test_pair_satellite_rejects_malformed_reserved_capability(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
    capability: str,
    declaration: dict[str, Any],
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl("https://satellite.example.com"),
        capabilities={capability: declaration},
    )

    with pytest.raises(ApplicationError, match=capability) as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 422
    mock_get_satellite.assert_not_awaited()
    mock_pair_satellite.assert_not_awaited()


def test_present_capabilities_respects_reserved_versions() -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    capabilities: dict[str, dict[str, Any]] = {
        "deploy": {"version": 1, "api_versions": [1]},
        "monitoring": {"version": 1, "api_versions": [3]},
        "custom.gpu_monitoring": {"version": 7},
    }
    satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        paired=True,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
    )

    expected = [
        "deploy",
        "custom.gpu_monitoring",
    ]
    assert get_present_capabilities(capabilities) == expected
    assert satellite.present_capabilities == expected
    assert satellite.model_dump()["present_capabilities"] == expected


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_stores_unsupported_reserved_version(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    declaration = {
        "version": 7,
        "facets": ["satellite:future"],
        "future_field": {"value": True},
    }
    mock_get_satellite.return_value = Mock()
    mock_pair_satellite.return_value = Mock()

    await handler.pair_satellite(
        satellite_id,
        SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={"monitoring": declaration},
        ),
    )

    pair_call = mock_pair_satellite.await_args
    assert pair_call is not None
    paired = pair_call.args[0]
    assert paired.capabilities == {"monitoring": declaration}
    assert get_present_capabilities(paired.capabilities) == []


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_stores_unsupported_api_version(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    mock_get_satellite.return_value = Mock()
    mock_pair_satellite.return_value = Mock()

    await handler.pair_satellite(
        satellite_id,
        SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={
                "monitoring": {"version": 1, "api_versions": [3]},
            },
        ),
    )

    pair_call = mock_pair_satellite.await_args
    assert pair_call is not None
    paired = pair_call.args[0]
    assert paired.capabilities == {
        "monitoring": {
            "version": 1,
            "api_versions": [3],
            "facets": MONITORING_FACETS,
            "features": MONITORING_FEATURES,
        }
    }
    assert get_present_capabilities(paired.capabilities) == []


@pytest.mark.asyncio
async def test_pair_satellite_empty_capabilities() -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[str, dict[str, Any]] = {}

    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl(base_url),
        capabilities=capabilities,
    )

    with pytest.raises(ApplicationError, match="Invalid capabilities") as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 400


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_satellite_not_found(
    mock_get_satellite: AsyncMock,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

    mock_get_satellite.return_value = None

    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl(base_url),
        capabilities=capabilities,
    )

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_update_error(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

    unpaired_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url=None,
        paired=False,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = unpaired_satellite
    mock_pair_satellite.return_value = None

    satellite_pair_in = SatellitePairIn(
        base_url=HttpUrl(base_url),
        capabilities=capabilities,
    )

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_awaited_once()


@patch(
    "luml.handlers.satellites.SatelliteRepository.touch_last_seen",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_touch_last_seen(mock_touch_last_seen: AsyncMock) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    await handler.touch_last_seen(satellite_id)

    mock_touch_last_seen.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_tasks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tasks(mock_list_tasks: AsyncMock) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

    expected = [
        SatelliteQueueTask(
            id=task_id,
            satellite_id=satellite_id,
            orbit_id=orbit_id,
            type=SatelliteTaskType.DEPLOY,
            payload={"created_by_user": "Full Name"},
            status=SatelliteTaskStatus.PENDING,
            scheduled_at=datetime.datetime.now(),
            started_at=datetime.datetime.now(),
            finished_at=None,
            result=None,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_list_tasks.return_value = expected

    tasks = await handler.list_tasks(satellite_id)

    assert tasks == expected
    mock_list_tasks.assert_awaited_once_with(satellite_id, None)


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_tasks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tasks_with_status(mock_list_tasks: AsyncMock) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    status = SatelliteTaskStatus.PENDING

    expected = [Mock(status=status), Mock(status=status)]

    mock_list_tasks.return_value = expected

    tasks = await handler.list_tasks(satellite_id, status)

    assert tasks == expected
    assert tasks[0].status == status
    mock_list_tasks.assert_awaited_once_with(satellite_id, status)


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_task_status",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_task_status_success(mock_update_task_status: AsyncMock) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

    status = SatelliteTaskStatus.DONE
    result = {"success": True}

    expected = SatelliteQueueTask(
        id=task_id,
        satellite_id=satellite_id,
        orbit_id=orbit_id,
        type=SatelliteTaskType.DEPLOY,
        payload={"created_by_user": "Full Name"},
        status=status,
        scheduled_at=datetime.datetime.now(),
        started_at=datetime.datetime.now(),
        finished_at=datetime.datetime.now(),
        result=result,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )
    mock_update_task_status.return_value = expected

    task = await handler.update_task_status(satellite_id, task_id, status, result)

    assert task == expected
    assert expected.status == status
    assert expected.finished_at
    assert expected.result == result
    mock_update_task_status.assert_awaited_once_with(
        satellite_id, task_id, status, result
    )


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_task_status",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_task_status_not_found(mock_update_task_status: AsyncMock) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

    status = SatelliteTaskStatus.DONE

    mock_update_task_status.return_value = None

    with pytest.raises(NotFoundError, match="Task not found") as error:
        await handler.update_task_status(satellite_id, task_id, status)

    assert error.value.status_code == 404
    mock_update_task_status.assert_awaited_once_with(
        satellite_id, task_id, status, None
    )


@patch(
    "luml.handlers.satellites.SatelliteHandler._get_key_hash",
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_regenerate_satellite_api_key(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
    mock_get_key_hash: Mock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_get_key_hash.return_value = "hashed_key"

    api_key = await handler.regenerate_satellite_api_key(
        user_id, organization_id, orbit_id, satellite_id
    )

    assert api_key.startswith("dfssat_")
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_get_key_hash.assert_called_once_with(api_key)
    mock_update_satellite.assert_awaited_once_with(
        SatelliteRegenerateApiKey(id=satellite_id, api_key_hash="hashed_key")
    )


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_regenerate_satellite_api_key_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.regenerate_satellite_api_key(
            user_id, organization_id, orbit_id, satellite_id
        )

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_regenerate_satellite_api_key_foreign_orbit(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    foreign_orbit_id = UUID("0199c337-09f4-7c21-8b3a-6d0f2f1b4e57")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = Satellite(
        id=satellite_id,
        orbit_id=foreign_orbit_id,
        name="foreign-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.regenerate_satellite_api_key(
            user_id, organization_id, orbit_id, satellite_id
        )

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_update_satellite.assert_not_awaited()


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_update_in = SatelliteUpdateIn(
        name="updated-name", description="updated-desc"
    )

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    updated_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="updated-name",
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_update_satellite.return_value = updated_satellite

    result = await handler.update_satellite(
        user_id, organization_id, orbit_id, satellite_id, satellite_update_in
    )

    assert result == updated_satellite
    assert result.name == "updated-name"
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_update_satellite.assert_awaited_once()


@pytest.mark.parametrize(
    "body",
    [{"description": "updated-desc"}, {"name": "updated-name"}],
    ids=["description-only", "name-only"],
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite_sends_only_provided_fields(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
    body: dict[str, str],
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = Mock(orbit_id=orbit_id)

    await handler.update_satellite(
        user_id,
        organization_id,
        orbit_id,
        satellite_id,
        SatelliteUpdateIn.model_validate(body),
    )

    mock_update_satellite.assert_awaited_once()
    update_call = mock_update_satellite.await_args
    assert update_call is not None
    assert update_call.args[0].model_dump(exclude_unset=True) == {
        "id": satellite_id,
        **body,
    }


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_update_in = SatelliteUpdateIn(name="updated-name")
    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.update_satellite(
            user_id, organization_id, orbit_id, satellite_id, satellite_update_in
        )

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite_foreign_orbit(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    foreign_orbit_id = UUID("0199c337-09f4-7c21-8b3a-6d0f2f1b4e57")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = Satellite(
        id=satellite_id,
        orbit_id=foreign_orbit_id,
        name="foreign-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.update_satellite(
            user_id,
            organization_id,
            orbit_id,
            satellite_id,
            SatelliteUpdateIn(name="renamed"),
        )

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_update_satellite.assert_not_awaited()


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite_update_failed(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_update_in = SatelliteUpdateIn(name="updated-name")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_update_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.update_satellite(
            user_id, organization_id, orbit_id, satellite_id, satellite_update_in
        )

    assert error.value.status_code == 404


@patch(
    "luml.handlers.satellites.SatelliteRepository.delete_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_delete_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_delete_satellite.return_value = None

    await handler.delete_satellite(organization_id, orbit_id, user_id, satellite_id)

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.DELETE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_delete_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.delete_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_satellite_with_deployments(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_delete_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_delete_satellite.side_effect = DatabaseConstraintError(
        "Satellite has deployments"
    )

    with pytest.raises(ApplicationError) as error:
        await handler.delete_satellite(organization_id, orbit_id, user_id, satellite_id)

    assert error.value.status_code == 409
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.DELETE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_delete_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_satellite_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.delete_satellite(organization_id, orbit_id, user_id, satellite_id)

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.DELETE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.delete_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_satellite_foreign_orbit(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_delete_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    foreign_orbit_id = UUID("0199c337-09f4-7c21-8b3a-6d0f2f1b4e57")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = Satellite(
        id=satellite_id,
        orbit_id=foreign_orbit_id,
        name="foreign-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.delete_satellite(organization_id, orbit_id, user_id, satellite_id)

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.DELETE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_delete_satellite.assert_not_awaited()


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_satellites",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__user_repository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__orbits_repository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__orbits_repository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_satellites_orbit_member_permissions(
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_org_member_role: AsyncMock,
    mock_list_satellites: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

    expected = [
        Satellite(
            id=satellite_id,
            orbit_id=orbit_id,
            name="test",
            description=None,
            base_url="https://url.com",
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
    ]

    mock_get_org_member_role.return_value = "member"
    mock_get_orbit_member_role.return_value = "member"
    mock_list_satellites.return_value = expected

    result = await handler.list_satellites(user_id, organization_id, orbit_id)

    assert result == expected
    mock_get_org_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)
    mock_list_satellites.assert_awaited_once_with(orbit_id, None)


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_satellites",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__user_repository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__orbits_repository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__orbits_repository.get_orbit_simple",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_satellites_organization_admin_permissions(
    mock_get_orbit_simple: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_org_member_role: AsyncMock,
    mock_list_satellites: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

    expected = [
        Satellite(
            id=satellite_id,
            orbit_id=orbit_id,
            name="test",
            description=None,
            base_url="https://url.com",
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
    ]

    mock_get_org_member_role.return_value = "admin"
    mock_list_satellites.return_value = expected

    result = await handler.list_satellites(user_id, organization_id, orbit_id)

    assert result == expected
    mock_get_org_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_not_awaited()
    mock_list_satellites.assert_awaited_once_with(orbit_id, None)


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite_by_hash",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_authenticate_api_key(
    mock_get_satellite_by_hash: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={"deploy": {"version": 1}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite_by_hash.return_value = expected

    api_key = "dfssat_test_key_12345"
    result = await handler.authenticate_api_key(api_key)

    assert result == expected
    mock_get_satellite_by_hash.assert_awaited_once()


@patch(
    "luml.handlers.satellites.SatelliteRepository.create_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_organization_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_public_user: AsyncMock,
    mock_create_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit_simple.return_value = Mock()
    mock_get_organization_details.return_value = None
    mock_get_public_user.return_value = Mock(full_name="John Doe")

    with pytest.raises(NotFoundError, match="Organization not found") as error:
        await handler.create_satellite(
            user_id, organization_id, orbit_id, SatelliteCreateIn(name="test-satellite")
        )

    assert error.value.status_code == 404
    mock_get_organization_details.assert_awaited_once_with(organization_id)
    mock_create_satellite.assert_not_awaited()


@patch(
    "luml.handlers.satellites.SatelliteRepository.create_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_rejects_an_organization_at_its_satellites_limit(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_public_user: AsyncMock,
    mock_create_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit_simple.return_value = Mock()
    mock_get_organization_details.return_value = Mock(
        total_satellites=3, satellites_limit=3
    )
    mock_get_public_user.return_value = Mock(full_name="John Doe")

    with pytest.raises(
        OrganizationLimitReachedError, match="maximum number of satellites"
    ) as error:
        await handler.create_satellite(
            user_id, organization_id, orbit_id, SatelliteCreateIn(name="test-satellite")
        )

    assert error.value.status_code == 409
    mock_get_organization_details.assert_awaited_once_with(organization_id)
    mock_create_satellite.assert_not_awaited()
