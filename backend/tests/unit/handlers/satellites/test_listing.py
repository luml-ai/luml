import datetime
from typing import Any

import pytest
from luml.handlers.satellites import SatelliteHandler
from luml.infra.exceptions import NotFoundError
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import Satellite

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, SATELLITE_ID, USER_ID
from tests.support.mocks import CollaboratorMocks


class TestSatelliteListing:
    async def test_list_satellites_returns_orbit_satellites(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

        expected = [
            Satellite(
                id=SATELLITE_ID,
                orbit_id=ORBIT_ID,
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
        mocks.sat_repo.list_satellites.return_value = expected

        result = await mocks.handler.list_satellites(USER_ID, ORGANIZATION_ID, ORBIT_ID)

        assert result == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.LIST, ORBIT_ID
        )
        mocks.sat_repo.list_satellites.assert_awaited_once_with(ORBIT_ID, None)

    async def test_get_satellite_returns_satellite(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        expected = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test",
            description=None,
            base_url="https://url.com",
            paired=False,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
        mocks.sat_repo.get_satellite.return_value = expected

        result = await mocks.handler.get_satellite(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID
        )

        assert result == expected
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.READ, ORBIT_ID
        )

    async def test_get_satellite_raises_not_found_when_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = None

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.get_satellite(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID
            )

        assert error.value.status_code == 404
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.READ, ORBIT_ID
        )

    async def test_get_satellite_openapi_returns_document(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        document = {
            "openapi": "3.1.0",
            "paths": {"/health": {"get": {"summary": "Health"}}},
        }
        mocks.sat_repo.get_satellite.return_value = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            paired=True,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
        )
        mocks.sat_repo.get_satellite_openapi.return_value = document

        result = await mocks.handler.get_satellite_openapi(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID
        )

        assert result == document
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.SATELLITE, Action.READ, ORBIT_ID
        )
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.get_satellite_openapi.assert_awaited_once_with(SATELLITE_ID)

    def test_satellite_payload_does_not_include_openapi(self) -> None:
        satellite = Satellite.model_validate(
            {
                "id": SATELLITE_ID,
                "orbit_id": ORBIT_ID,
                "name": "test-satellite",
                "paired": True,
                "capabilities": {"deploy": {"version": 1}},
                "openapi": {"openapi": "3.1.0", "paths": {}},
                "created_at": datetime.datetime.now(),
            }
        )

        assert "openapi" not in satellite.model_dump()
