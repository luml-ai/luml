import datetime
from uuid import UUID

import pytest
from luml.handlers.orbit_secrets import OrbitSecretHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    NotFoundError,
)
from luml.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretCreateIn,
    OrbitSecretOut,
    OrbitSecretUpdate,
)
from luml.schemas.permissions import Action, Resource

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, OTHER_ORBIT_ID, USER_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

SECRET_ID = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")


@pytest.fixture
def mocks() -> CollaboratorMocks[OrbitSecretHandler]:
    return mock_collaborators(OrbitSecretHandler())


def _owner_orbit_secrets() -> dict[UUID, OrbitSecret]:
    return {
        SECRET_ID: OrbitSecret(
            id=SECRET_ID,
            orbit_id=OTHER_ORBIT_ID,
            name="owner-secret",
            value="owner-value",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    }


class TestOrbitSecretHandler:
    async def test_create_orbit_secret_returns_created_secret(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        expected = OrbitSecretOut(
            id=SECRET_ID,
            orbit_id=ORBIT_ID,
            name="test",
            value="test-value",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
        mocks.secret_repository.create_orbit_secret.return_value = expected

        secret_create_obj = OrbitSecretCreate(
            name=expected.name, value=expected.value, orbit_id=expected.orbit_id
        )

        created_secret = await mocks.handler.create_orbit_secret(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            OrbitSecretCreateIn(name=expected.name, value=expected.value),
        )

        assert created_secret == expected
        mocks.secret_repository.create_orbit_secret.assert_awaited_once_with(
            secret_create_obj
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT_SECRET, Action.CREATE, ORBIT_ID
        )

    async def test_get_orbit_secrets_returns_secrets_without_values(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        expected = [
            OrbitSecretOut(
                id=SECRET_ID,
                orbit_id=ORBIT_ID,
                name="test",
                value="",
                created_at=datetime.datetime.now(),
                updated_at=None,
            )
        ]
        mocks.secret_repository.get_orbit_secrets.return_value = expected

        secrets = await mocks.handler.get_orbit_secrets(
            USER_ID, ORGANIZATION_ID, ORBIT_ID
        )

        assert secrets == expected
        mocks.secret_repository.get_orbit_secrets.assert_awaited_once_with(ORBIT_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT_SECRET, Action.LIST, ORBIT_ID
        )

    async def test_get_orbit_secret_returns_secret(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        expected = OrbitSecretOut(
            id=SECRET_ID,
            orbit_id=ORBIT_ID,
            name="test",
            value="test-value",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.secret_repository.get_orbit_secret.return_value = expected

        secret = await mocks.handler.get_orbit_secret(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID
        )

        assert secret == expected
        mocks.secret_repository.get_orbit_secret.assert_awaited_once_with(
            SECRET_ID, ORBIT_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT_SECRET, Action.READ, ORBIT_ID
        )

    async def test_get_orbit_secret_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        mocks.secret_repository.get_orbit_secret.return_value = None

        with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
            await mocks.handler.get_orbit_secret(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID
            )

        assert error.value.status_code == 404

    async def test_update_orbit_secret_returns_updated_secret(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        secret_update = OrbitSecretUpdate(name="updated-name", value="updated-value")
        expected = OrbitSecretOut(
            id=SECRET_ID,
            orbit_id=ORBIT_ID,
            name="updated-name",
            value="updated-value",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        mocks.secret_repository.update_orbit_secret.return_value = expected

        result = await mocks.handler.update_orbit_secret(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID, secret_update
        )

        assert result == expected
        mocks.secret_repository.update_orbit_secret.assert_awaited_once_with(
            SECRET_ID, ORBIT_ID, secret_update
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT_SECRET, Action.UPDATE, ORBIT_ID
        )

    async def test_update_orbit_secret_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        secret_update = OrbitSecretUpdate(name="updated-name", value="updated-value")

        mocks.secret_repository.update_orbit_secret.return_value = None

        with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
            await mocks.handler.update_orbit_secret(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID, secret_update
            )

        assert error.value.status_code == 404
        mocks.secret_repository.update_orbit_secret.assert_awaited_once_with(
            SECRET_ID, ORBIT_ID, secret_update
        )

    async def test_delete_orbit_secret_deletes_by_id_and_orbit(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        mocks.secret_repository.delete_orbit_secret.return_value = True

        await mocks.handler.delete_orbit_secret(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID
        )

        mocks.secret_repository.delete_orbit_secret.assert_awaited_once_with(
            SECRET_ID, ORBIT_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT_SECRET, Action.DELETE, ORBIT_ID
        )

    async def test_delete_orbit_secret_raises_same_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        mocks.secret_repository.delete_orbit_secret.return_value = False

        with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
            await mocks.handler.delete_orbit_secret(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID
            )

        assert error.value.status_code == 404
        mocks.secret_repository.delete_orbit_secret.assert_awaited_once_with(
            SECRET_ID, ORBIT_ID
        )

    async def test_get_worker_orbit_secrets_returns_secrets(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        expected = [
            OrbitSecret(
                id=SECRET_ID,
                orbit_id=ORBIT_ID,
                name="secret1",
                value="value1",
                created_at=datetime.datetime.now(),
                updated_at=None,
            )
        ]

        mocks.secret_repository.get_orbit_secrets.return_value = expected

        result = await mocks.handler.get_worker_orbit_secrets(ORBIT_ID)

        assert result == expected
        mocks.secret_repository.get_orbit_secrets.assert_awaited_once_with(ORBIT_ID)

    async def test_get_worker_orbit_secret_returns_secret(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        expected_secret = OrbitSecret(
            id=SECRET_ID,
            orbit_id=ORBIT_ID,
            name="test-secret",
            value="secret-value",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.secret_repository.get_orbit_secret.return_value = expected_secret

        result = await mocks.handler.get_worker_orbit_secret(ORBIT_ID, SECRET_ID)

        assert result == expected_secret
        mocks.secret_repository.get_orbit_secret.assert_awaited_once_with(
            SECRET_ID, ORBIT_ID
        )

    async def test_get_worker_orbit_secret_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        mocks.secret_repository.get_orbit_secret.return_value = None

        with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
            await mocks.handler.get_worker_orbit_secret(ORBIT_ID, SECRET_ID)

        assert error.value.status_code == 404
        mocks.secret_repository.get_orbit_secret.assert_awaited_once_with(
            SECRET_ID, ORBIT_ID
        )

    async def test_create_orbit_secret_raises_bad_request_when_name_is_duplicate(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        secret_name = "duplicate-name"

        mocks.secret_repository.create_orbit_secret.side_effect = (
            DatabaseConstraintError("Secret with this name already exists")
        )

        with pytest.raises(
            ApplicationError,
            match=f"Secret with name {secret_name} already exist in orbit",
        ) as error:
            await mocks.handler.create_orbit_secret(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                OrbitSecretCreateIn(name=secret_name, value="test-value"),
            )

        assert error.value.status_code == 400
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT_SECRET, Action.CREATE, ORBIT_ID
        )

    async def test_get_orbit_secret_raises_not_found_for_foreign_orbit(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        stored = _owner_orbit_secrets()

        async def scoped_get(secret_id: UUID, orbit_id: UUID) -> OrbitSecret | None:
            secret = stored.get(secret_id)
            return secret if secret and secret.orbit_id == orbit_id else None

        mocks.secret_repository.get_orbit_secret.side_effect = scoped_get

        with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
            await mocks.handler.get_orbit_secret(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID
            )

        assert error.value.status_code == 404
        owner_read = await mocks.handler.get_worker_orbit_secret(
            OTHER_ORBIT_ID, SECRET_ID
        )
        assert owner_read.value == "owner-value"

    async def test_update_orbit_secret_raises_not_found_for_foreign_orbit(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        stored = _owner_orbit_secrets()

        async def scoped_update(
            secret_id: UUID, orbit_id: UUID, update: OrbitSecretUpdate
        ) -> OrbitSecret | None:
            secret = stored.get(secret_id)
            if not secret or secret.orbit_id != orbit_id:
                return None
            stored[secret_id] = secret.model_copy(
                update=update.model_dump(exclude_unset=True)
            )
            return stored[secret_id]

        mocks.secret_repository.update_orbit_secret.side_effect = scoped_update

        with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
            await mocks.handler.update_orbit_secret(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                SECRET_ID,
                OrbitSecretUpdate(name="renamed", value="renamed-value"),
            )

        assert error.value.status_code == 404
        assert stored[SECRET_ID].name == "owner-secret"
        assert stored[SECRET_ID].value == "owner-value"

    async def test_delete_orbit_secret_raises_not_found_for_foreign_orbit(
        self, mocks: CollaboratorMocks[OrbitSecretHandler]
    ) -> None:
        stored = _owner_orbit_secrets()

        async def scoped_get(secret_id: UUID, orbit_id: UUID) -> OrbitSecret | None:
            secret = stored.get(secret_id)
            return secret if secret and secret.orbit_id == orbit_id else None

        async def scoped_delete(secret_id: UUID, orbit_id: UUID) -> bool:
            if not await scoped_get(secret_id, orbit_id):
                return False
            del stored[secret_id]
            return True

        mocks.secret_repository.get_orbit_secret.side_effect = scoped_get
        mocks.secret_repository.delete_orbit_secret.side_effect = scoped_delete

        with pytest.raises(NotFoundError, match="Orbit secret not found") as error:
            await mocks.handler.delete_orbit_secret(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, SECRET_ID
            )

        assert error.value.status_code == 404
        assert await mocks.handler.get_worker_orbit_secret(OTHER_ORBIT_ID, SECRET_ID)
