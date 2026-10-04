import datetime
from typing import Any
from unittest.mock import Mock

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
    MONITORING_FACETS,
    MONITORING_FEATURES,
    Satellite,
    SatelliteCreateIn,
    SatelliteCreateOut,
    SatelliteRegenerateApiKey,
    SatelliteUpdateIn,
    get_present_capabilities,
    normalize_capabilities,
)

from tests.support.ids import (
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    SATELLITE_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks


class TestSatelliteManagement:
    async def test_create_satellite_returns_satellite_and_api_key(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        user_name = "John Doe"

        satellite_create_in = SatelliteCreateIn(name="test-satellite")
        created_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            base_url="https://url.com",
            paired=False,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )

        mocks.user_repo.get_organization_details.return_value = Mock(
            total_satellites=0, satellites_limit=1
        )
        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.user_repo.get_public_user_by_id.return_value = Mock(full_name=user_name)
        mocks.sat_repo.create_satellite.return_value = created_satellite

        result = await mocks.handler.create_satellite(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, satellite_create_in
        )

        assert isinstance(result, SatelliteCreateOut)
        assert result.satellite == created_satellite
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.user_repo.get_public_user_by_id.assert_awaited_once_with(USER_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.CREATE, ORBIT_ID
        )
        mocks.user_repo.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )

    async def test_create_satellite_raises_not_found_when_orbit_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        satellite_create_in = SatelliteCreateIn(name="test-satellite")

        mocks.user_repo.get_organization_details.return_value = Mock(
            total_satellites=0, satellites_limit=1
        )
        mocks.orbit_repo.get_orbit_simple.return_value = None

        with pytest.raises(NotFoundError, match="Orbit not found") as error:
            await mocks.handler.create_satellite(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, satellite_create_in
            )

        assert error.value.status_code == 404
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.CREATE, ORBIT_ID
        )
        mocks.user_repo.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )

    async def test_create_satellite_raises_not_found_when_user_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        satellite_create_in = SatelliteCreateIn(name="test-satellite")

        mocks.user_repo.get_organization_details.return_value = Mock(
            total_satellites=0, satellites_limit=1
        )
        mocks.orbit_repo.get_orbit_simple.return_value = Mock()
        mocks.user_repo.get_public_user_by_id.return_value = None

        with pytest.raises(NotFoundError, match="User not found") as error:
            await mocks.handler.create_satellite(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, satellite_create_in
            )

        assert error.value.status_code == 404
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.user_repo.get_public_user_by_id.assert_awaited_once_with(USER_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.CREATE, ORBIT_ID
        )
        mocks.user_repo.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )

    async def test_create_satellite_raises_not_found_when_organization_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.user_repo.get_organization_details.return_value = None

        with pytest.raises(NotFoundError, match="Organization not found") as error:
            await mocks.handler.create_satellite(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                SatelliteCreateIn(name="test-satellite"),
            )

        assert error.value.status_code == 404
        mocks.user_repo.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )
        mocks.sat_repo.create_satellite.assert_not_awaited()

    async def test_create_satellite_raises_limit_reached_when_organization_is_full(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.user_repo.get_organization_details.return_value = Mock(
            total_satellites=3, satellites_limit=3
        )

        with pytest.raises(
            OrganizationLimitReachedError, match="maximum number of satellites"
        ) as error:
            await mocks.handler.create_satellite(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                SatelliteCreateIn(name="test-satellite"),
            )

        assert error.value.status_code == 409
        mocks.user_repo.get_organization_details.assert_awaited_once_with(
            ORGANIZATION_ID
        )
        mocks.sat_repo.create_satellite.assert_not_awaited()

    async def test_regenerate_satellite_api_key_stores_new_key_hash(
        self,
        mocks: CollaboratorMocks[SatelliteHandler],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stored_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url="https://url.com",
            paired=True,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )

        mocks.sat_repo.get_satellite.return_value = stored_satellite
        get_key_hash = Mock(return_value="hashed_key")
        monkeypatch.setattr(mocks.handler, "_get_key_hash", get_key_hash)

        api_key = await mocks.handler.regenerate_satellite_api_key(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID
        )

        assert api_key.startswith("dfssat_")
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.UPDATE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        get_key_hash.assert_called_once_with(api_key)
        mocks.sat_repo.update_satellite.assert_awaited_once_with(
            SatelliteRegenerateApiKey(id=SATELLITE_ID, api_key_hash="hashed_key")
        )

    async def test_regenerate_satellite_api_key_raises_not_found_when_satellite_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.regenerate_satellite_api_key(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.UPDATE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)

    async def test_regenerate_satellite_api_key_raises_not_found_for_other_orbit(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = Satellite(
            id=SATELLITE_ID,
            orbit_id=OTHER_ORBIT_ID,
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
            await mocks.handler.regenerate_satellite_api_key(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.UPDATE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.update_satellite.assert_not_awaited()

    async def test_update_satellite_returns_updated_satellite(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        satellite_update_in = SatelliteUpdateIn(
            name="updated-name", description="updated-desc"
        )

        stored_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
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
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="updated-name",
            base_url="https://url.com",
            paired=True,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            last_seen_at=None,
        )

        mocks.sat_repo.get_satellite.return_value = stored_satellite
        mocks.sat_repo.update_satellite.return_value = updated_satellite

        result = await mocks.handler.update_satellite(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID, satellite_update_in
        )

        assert result == updated_satellite
        assert result.name == "updated-name"
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.UPDATE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.update_satellite.assert_awaited_once()

    @pytest.mark.parametrize(
        "body",
        [{"description": "updated-desc"}, {"name": "updated-name"}],
        ids=["description-only", "name-only"],
    )
    async def test_update_satellite_sends_only_provided_fields(
        self, mocks: CollaboratorMocks[SatelliteHandler], body: dict[str, str]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = Mock(orbit_id=ORBIT_ID)

        await mocks.handler.update_satellite(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            SATELLITE_ID,
            SatelliteUpdateIn.model_validate(body),
        )

        mocks.sat_repo.update_satellite.assert_awaited_once()
        update_call = mocks.sat_repo.update_satellite.await_args
        assert update_call is not None
        assert update_call.args[0].model_dump(exclude_unset=True) == {
            "id": SATELLITE_ID,
            **body,
        }

    async def test_update_satellite_raises_not_found_when_satellite_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        satellite_update_in = SatelliteUpdateIn(name="updated-name")
        mocks.sat_repo.get_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.update_satellite(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID, satellite_update_in
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.UPDATE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)

    async def test_update_satellite_raises_not_found_when_satellite_in_other_orbit(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = Satellite(
            id=SATELLITE_ID,
            orbit_id=OTHER_ORBIT_ID,
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
            await mocks.handler.update_satellite(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                SATELLITE_ID,
                SatelliteUpdateIn(name="renamed"),
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.UPDATE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.update_satellite.assert_not_awaited()

    async def test_update_satellite_raises_not_found_when_update_returns_nothing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        satellite_update_in = SatelliteUpdateIn(name="updated-name")

        stored_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url="https://url.com",
            paired=True,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )

        mocks.sat_repo.get_satellite.return_value = stored_satellite
        mocks.sat_repo.update_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.update_satellite(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID, satellite_update_in
            )

        assert error.value.status_code == 404

    async def test_delete_satellite_deletes_orbit_satellite(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        stored_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url="https://url.com",
            paired=True,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )

        mocks.sat_repo.get_satellite.return_value = stored_satellite
        mocks.sat_repo.delete_satellite.return_value = None

        await mocks.handler.delete_satellite(
            ORGANIZATION_ID, ORBIT_ID, USER_ID, SATELLITE_ID
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.DELETE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.delete_satellite.assert_awaited_once_with(SATELLITE_ID)

    async def test_delete_satellite_raises_conflict_when_satellite_has_deployments(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        stored_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url="https://url.com",
            paired=True,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )

        mocks.sat_repo.get_satellite.return_value = stored_satellite
        mocks.sat_repo.delete_satellite.side_effect = DatabaseConstraintError(
            "Satellite has deployments"
        )

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.delete_satellite(
                ORGANIZATION_ID, ORBIT_ID, USER_ID, SATELLITE_ID
            )

        assert error.value.status_code == 409
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.DELETE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.delete_satellite.assert_awaited_once_with(SATELLITE_ID)

    async def test_delete_satellite_raises_not_found_when_satellite_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.delete_satellite(
                ORGANIZATION_ID, ORBIT_ID, USER_ID, SATELLITE_ID
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.DELETE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)

    async def test_delete_satellite_raises_not_found_when_satellite_in_other_orbit(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = Satellite(
            id=SATELLITE_ID,
            orbit_id=OTHER_ORBIT_ID,
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
            await mocks.handler.delete_satellite(
                ORGANIZATION_ID, ORBIT_ID, USER_ID, SATELLITE_ID
            )

        assert error.value.status_code == 404
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.DELETE, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.delete_satellite.assert_not_awaited()

    def test_bare_monitoring_declaration_is_complete_in_satellite_payload(
        self,
    ) -> None:
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
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
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

    def test_present_capabilities_respects_reserved_versions(self) -> None:
        capabilities: dict[str, dict[str, Any]] = {
            "deploy": {"version": 1, "api_versions": [1]},
            "monitoring": {"version": 1, "api_versions": [3]},
            "custom.gpu_monitoring": {"version": 7},
        }
        satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
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
