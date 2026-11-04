from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.infra.exceptions import DatabaseConstraintError
from luml.schemas.orbit import OrbitUpdate
from luml.schemas.orbit_secret import OrbitSecretUpdate
from luml.schemas.tracks import TrackUpdateIn
from pydantic import BaseModel

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID

ORBIT_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}"


@pytest.mark.parametrize(
    ("path", "handler", "field"),
    [
        (ORBIT_PATH, "orbits.OrbitHandler.update_orbit", "name"),
        (
            f"{ORBIT_PATH}/tracks/{ORBIT_ID}",
            "tracks.TracksHandler.update_track",
            "name",
        ),
        (
            f"{ORBIT_PATH}/secrets/{ORBIT_ID}",
            "orbit_secrets.OrbitSecretHandler.update_orbit_secret",
            "name",
        ),
        (
            f"{ORBIT_PATH}/secrets/{ORBIT_ID}",
            "orbit_secrets.OrbitSecretHandler.update_orbit_secret",
            "value",
        ),
    ],
)
def test_patch_rejects_null_required_fields(
    client: TestClient, path: str, handler: str, field: str
) -> None:
    with patch(f"luml.handlers.{handler}", new_callable=AsyncMock) as update:
        response = client.patch(path, json={field: None})

    assert response.status_code == 422
    assert ["body", field] in [error["loc"] for error in response.json()["detail"]]
    update.assert_not_awaited()


@pytest.mark.parametrize("schema", [OrbitUpdate, OrbitSecretUpdate, TrackUpdateIn])
def test_patch_allows_omitted_fields(schema: type[BaseModel]) -> None:
    assert schema.model_validate({}).model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize(
    ("schema", "body"),
    [
        (OrbitSecretUpdate, {"tags": None}),
        (TrackUpdateIn, {"description": None, "tags": None}),
    ],
)
def test_patch_allows_clearing_nullable_fields(
    schema: type[BaseModel], body: dict[str, object]
) -> None:
    assert schema.model_validate(body).model_dump(exclude_unset=True) == body


def test_patch_secret_duplicate_name_returns_conflict(client: TestClient) -> None:
    with (
        patch(
            "luml.handlers.permissions.PermissionsHandler.check_permissions",
            new_callable=AsyncMock,
        ),
        patch(
            "luml.repositories.orbit_secrets.OrbitSecretRepository.update_orbit_secret",
            new_callable=AsyncMock,
            side_effect=DatabaseConstraintError(),
        ),
    ):
        response = client.patch(
            f"{ORBIT_PATH}/secrets/{ORBIT_ID}", json={"name": "taken"}
        )

    assert response.status_code == 409
