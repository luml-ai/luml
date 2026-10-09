from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, SATELLITE_ID, USER_ID

SATELLITES_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/satellites"


class TestOrbitSatellites:
    @pytest.mark.parametrize(
        "body", [{}, {"name": None}, {"name": ""}], ids=["missing", "null", "empty"]
    )
    @patch(
        "luml.handlers.satellites.SatelliteHandler.create_satellite",
        new_callable=AsyncMock,
    )
    def test_create_satellite_requires_name(
        self,
        mock_create_satellite: AsyncMock,
        body: dict[str, object],
        client: TestClient,
    ) -> None:
        response = client.post(SATELLITES_PATH, json=body)

        assert response.status_code == 422
        assert ["body", "name"] in [error["loc"] for error in response.json()["detail"]]
        mock_create_satellite.assert_not_awaited()

    @pytest.mark.parametrize(
        "body", [{"name": None}, {"name": ""}], ids=["null", "empty"]
    )
    @patch(
        "luml.handlers.satellites.SatelliteHandler.update_satellite",
        new_callable=AsyncMock,
    )
    def test_update_satellite_rejects_invalid_name(
        self,
        mock_update_satellite: AsyncMock,
        body: dict[str, object],
        client: TestClient,
    ) -> None:
        response = client.patch(f"{SATELLITES_PATH}/{SATELLITE_ID}", json=body)

        assert response.status_code == 422
        assert ["body", "name"] in [error["loc"] for error in response.json()["detail"]]
        mock_update_satellite.assert_not_awaited()

    @patch(
        "luml.api.orbits.orbit_satellites.SatelliteHandler.get_satellite_openapi",
        new_callable=AsyncMock,
    )
    def test_get_satellite_openapi_endpoint(
        self,
        mock_get_satellite_openapi: AsyncMock,
        client: TestClient,
    ) -> None:
        document = {"openapi": "3.1.0", "paths": {}}
        mock_get_satellite_openapi.return_value = document

        response = client.get(f"{SATELLITES_PATH}/{SATELLITE_ID}/openapi")

        assert response.status_code == 200
        assert response.json() == document
        mock_get_satellite_openapi.assert_awaited_once_with(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SATELLITE_ID
        )
