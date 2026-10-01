from unittest.mock import Mock
from uuid import UUID, uuid7

import pytest
from luml.handlers.orbits import OrbitHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.exceptions import NotFoundError, OrbitNotFoundError
from luml.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMemberCreateSimple,
    OrbitRole,
    OrbitUpdate,
)
from luml.schemas.organization import OrgRole
from luml.schemas.permissions import Action, Resource

from tests.support.ids import (
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.orbits.conftest import (
    FOREIGN_BUCKET_SECRET_ID,
    _owner_orbits,
    _scoped_bucket_secret,
)


class TestOrbits:
    async def test_create_organization_orbit_returns_created_orbit(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        mocks.secret_repository.get_bucket_secret.return_value = Mock(
            id=orbit.id,
            organization_id=orbit.organization_id,
            name="test_secret",
        )
        orbit_to_create = OrbitCreateIn(
            name=orbit.name,
            bucket_secret_id=orbit.bucket_secret_id,
        )

        mocks.orbits_repository.create_orbit.return_value = orbit
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_details.return_value = Mock(
            orbits_limit=10, total_orbits=0
        )

        result = await mocks.handler.create_organization_orbit(
            USER_ID, orbit.organization_id, orbit_to_create
        )

        assert result == orbit

        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            orbit.bucket_secret_id, orbit.organization_id
        )
        mocks.orbits_repository.create_orbit.assert_awaited_once_with(
            orbit.organization_id, orbit_to_create
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            orbit.organization_id, USER_ID, Resource.ORBIT, Action.CREATE
        )

    async def test_create_organization_orbit_makes_org_admin_creator_orbit_admin(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        mocks.secret_repository.get_bucket_secret.return_value = Mock(
            id=orbit.bucket_secret_id,
            organization_id=orbit.organization_id,
        )
        mocks.orbits_repository.create_orbit.return_value = orbit
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN
        mocks.user_repository.get_organization_details.return_value = Mock(
            orbits_limit=10, total_orbits=0
        )
        mocks.permissions_handler.get_orbit_permissions_by_role.side_effect = (
            PermissionsHandler().get_orbit_permissions_by_role
        )
        orbit_to_create = OrbitCreateIn(
            name=orbit.name, bucket_secret_id=orbit.bucket_secret_id
        )

        result = await mocks.handler.create_organization_orbit(
            USER_ID, orbit.organization_id, orbit_to_create
        )

        assert mocks.orbits_repository.create_orbit.await_args is not None
        created = mocks.orbits_repository.create_orbit.await_args.args[1]
        assert created.members == [
            OrbitMemberCreateSimple(user_id=USER_ID, role=OrbitRole.ADMIN)
        ]
        assert result.permissions is not None
        assert "delete" in result.permissions["orbit"]

    async def test_create_organization_orbit_raises_not_found_when_secret_missing(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        orbit_to_create = OrbitCreateIn(
            name=orbit.name,
            bucket_secret_id=orbit.bucket_secret_id,
        )

        mocks.secret_repository.get_bucket_secret.return_value = None
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_details.return_value = Mock(
            orbits_limit=10, total_orbits=0
        )

        with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
            await mocks.handler.create_organization_orbit(
                USER_ID, orbit.organization_id, orbit_to_create
            )

        assert error.value.status_code == 404
        mocks.orbits_repository.create_orbit.assert_not_called()

    async def test_create_organization_orbit_raises_not_found_when_secret_in_other_org(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        orbit_to_create = OrbitCreateIn(
            name=orbit.name,
            bucket_secret_id=orbit.bucket_secret_id,
        )

        mocks.secret_repository.get_bucket_secret.side_effect = _scoped_bucket_secret(
            Mock(id=orbit.bucket_secret_id, organization_id=ORGANIZATION_ID)
        )
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.user_repository.get_organization_details.return_value = Mock(
            orbits_limit=10, total_orbits=0
        )

        with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
            await mocks.handler.create_organization_orbit(
                USER_ID, orbit.organization_id, orbit_to_create
            )

        assert error.value.status_code == 404
        mocks.orbits_repository.create_orbit.assert_not_called()

    async def test_get_organization_orbits_returns_all_orbits_for_org_owner(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        expected = [orbit]

        mocks.orbits_repository.get_organization_orbits.return_value = expected
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER

        result = await mocks.handler.get_organization_orbits(
            USER_ID, orbit.organization_id
        )

        assert result == expected

        mocks.orbits_repository.get_organization_orbits.assert_awaited_once_with(
            orbit.organization_id, USER_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            orbit.organization_id, USER_ID, Resource.ORBIT, Action.LIST
        )

    async def test_get_organization_orbits_sets_orbit_role_permissions_for_org_admin(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        own_orbit = orbit.model_copy(update={"id": uuid7(), "role": OrbitRole.ADMIN})
        other_orbit = orbit.model_copy(update={"id": uuid7(), "role": None})
        mocks.orbits_repository.get_organization_orbits.return_value = [
            own_orbit,
            other_orbit,
        ]
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.ADMIN
        mocks.permissions_handler.get_orbit_permissions_by_role.side_effect = (
            PermissionsHandler().get_orbit_permissions_by_role
        )

        result = await mocks.handler.get_organization_orbits(
            USER_ID, orbit.organization_id
        )

        permissions = {listed.id: listed.permissions for listed in result}
        own_permissions = permissions[own_orbit.id]
        other_permissions = permissions[other_orbit.id]
        assert own_permissions is not None
        assert other_permissions is not None
        assert "delete" in own_permissions["orbit"]
        assert "delete" not in other_permissions["orbit"]

    async def test_get_orbit_returns_orbit_details(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit_details: OrbitDetails
    ) -> None:
        expected = orbit_details

        mocks.orbits_repository.get_orbit.return_value = expected
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.orbits_repository.get_orbit_member_role.return_value = OrgRole.ADMIN

        result = await mocks.handler.get_orbit(
            USER_ID, expected.organization_id, expected.id
        )

        assert result == expected
        mocks.orbits_repository.get_orbit.assert_awaited_once_with(
            expected.id, expected.organization_id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            expected.organization_id,
            USER_ID,
            Resource.ORBIT,
            Action.READ,
            expected.id,
        )

    async def test_get_orbit_raises_not_found_when_orbit_missing(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        mocks.orbits_repository.get_orbit.return_value = None
        mocks.user_repository.get_organization_member_role.return_value = OrgRole.OWNER
        mocks.orbits_repository.get_orbit_member_role.return_value = OrgRole.ADMIN

        with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
            await mocks.handler.get_orbit(USER_ID, ORGANIZATION_ID, ORBIT_ID)

        assert error.value.status_code == 404
        mocks.orbits_repository.get_orbit.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )

    async def test_update_orbit_returns_updated_orbit(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit_details: OrbitDetails
    ) -> None:
        expected = orbit_details

        mocks.orbits_repository.update_orbit.return_value = expected

        update_orbit = OrbitUpdate(name="new_name")
        result = await mocks.handler.update_orbit(
            USER_ID, expected.organization_id, expected.id, update_orbit
        )

        assert result == expected
        mocks.orbits_repository.update_orbit.assert_awaited_once_with(
            expected.id, expected.organization_id, update_orbit
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            expected.organization_id,
            USER_ID,
            Resource.ORBIT,
            Action.UPDATE,
            expected.id,
        )

    async def test_update_orbit_raises_not_found_when_orbit_missing(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        update_orbit = OrbitUpdate(name="new_name")

        mocks.orbits_repository.update_orbit.return_value = None

        with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
            await mocks.handler.update_orbit(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, update_orbit
            )

        assert error.value.status_code == 404
        mocks.orbits_repository.update_orbit.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID, update_orbit
        )

    async def test_delete_orbit_deletes_orbit(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        mocks.orbits_repository.delete_orbit.return_value = True

        await mocks.handler.delete_orbit(USER_ID, ORGANIZATION_ID, ORBIT_ID)
        mocks.orbits_repository.delete_orbit.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.ORBIT, Action.DELETE, ORBIT_ID
        )

    async def test_delete_orbit_raises_foreign_orbit_not_found_when_orbit_missing(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        mocks.orbits_repository.delete_orbit.return_value = False

        with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
            await mocks.handler.delete_orbit(USER_ID, ORGANIZATION_ID, ORBIT_ID)

        assert error.value.status_code == 404

    async def test_update_orbit_raises_not_found_when_orbit_in_other_org(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        stored = _owner_orbits()

        async def scoped_update(
            orbit_id: UUID, organization_id: UUID, update: OrbitUpdate
        ) -> Orbit | None:
            orbit = stored.get(orbit_id)
            if not orbit or orbit.organization_id != organization_id:
                return None
            stored[orbit_id] = orbit.model_copy(
                update=update.model_dump(exclude_unset=True)
            )
            return stored[orbit_id]

        mocks.orbits_repository.update_orbit.side_effect = scoped_update

        with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
            await mocks.handler.update_orbit(
                USER_ID,
                ORGANIZATION_ID,
                OTHER_ORBIT_ID,
                OrbitUpdate(name="renamed"),
            )

        assert error.value.status_code == 404
        assert stored[OTHER_ORBIT_ID].name == "owner-orbit"

    async def test_delete_orbit_raises_not_found_when_orbit_in_other_org(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        stored = _owner_orbits()

        async def scoped_delete(orbit_id: UUID, organization_id: UUID) -> bool:
            orbit = stored.get(orbit_id)
            if not orbit or orbit.organization_id != organization_id:
                return False
            del stored[orbit_id]
            return True

        mocks.orbits_repository.delete_orbit.side_effect = scoped_delete

        with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
            await mocks.handler.delete_orbit(USER_ID, ORGANIZATION_ID, OTHER_ORBIT_ID)

        assert error.value.status_code == 404
        assert OTHER_ORBIT_ID in stored

    async def test_update_orbit_raises_not_found_when_secret_in_other_org(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        mocks.secret_repository.get_bucket_secret.side_effect = _scoped_bucket_secret(
            Mock(id=FOREIGN_BUCKET_SECRET_ID, organization_id=OTHER_ORGANIZATION_ID)
        )

        with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
            await mocks.handler.update_orbit(
                USER_ID,
                orbit.organization_id,
                orbit.id,
                OrbitUpdate(bucket_secret_id=FOREIGN_BUCKET_SECRET_ID),
            )

        assert error.value.status_code == 404
        mocks.orbits_repository.update_orbit.assert_not_called()

    async def test_update_orbit_raises_not_found_when_bucket_secret_missing(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        mocks.secret_repository.get_bucket_secret.return_value = None

        with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
            await mocks.handler.update_orbit(
                USER_ID,
                orbit.organization_id,
                orbit.id,
                OrbitUpdate(bucket_secret_id=uuid7()),
            )

        assert error.value.status_code == 404
        mocks.orbits_repository.update_orbit.assert_not_called()

    async def test_update_orbit_raises_not_found_without_lookup_when_secret_is_null(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
            await mocks.handler.update_orbit(
                USER_ID,
                orbit.organization_id,
                orbit.id,
                OrbitUpdate(bucket_secret_id=None),
            )

        assert error.value.status_code == 404
        mocks.secret_repository.get_bucket_secret.assert_not_called()
        mocks.orbits_repository.update_orbit.assert_not_called()

    async def test_update_orbit_skips_secret_validation_when_secret_not_sent(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        mocks.orbits_repository.update_orbit.return_value = orbit

        update_orbit = OrbitUpdate(name="new_name")
        result = await mocks.handler.update_orbit(
            USER_ID,
            orbit.organization_id,
            orbit.id,
            update_orbit,
        )

        assert result == orbit
        mocks.secret_repository.get_bucket_secret.assert_not_called()
        mocks.orbits_repository.update_orbit.assert_awaited_once_with(
            orbit.id, orbit.organization_id, update_orbit
        )
        assert "bucket_secret_id" not in update_orbit.model_fields_set

    async def test_update_orbit_updates_bucket_secret_when_secret_in_own_organization(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit: Orbit
    ) -> None:
        new_secret_id = uuid7()
        updated = orbit.model_copy(update={"bucket_secret_id": new_secret_id})

        mocks.secret_repository.get_bucket_secret.return_value = Mock(
            id=new_secret_id, organization_id=orbit.organization_id
        )
        mocks.orbits_repository.update_orbit.return_value = updated

        update_orbit = OrbitUpdate(bucket_secret_id=new_secret_id)
        result = await mocks.handler.update_orbit(
            USER_ID, orbit.organization_id, orbit.id, update_orbit
        )

        assert result.bucket_secret_id == new_secret_id
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            new_secret_id, orbit.organization_id
        )
        mocks.orbits_repository.update_orbit.assert_awaited_once_with(
            orbit.id, orbit.organization_id, update_orbit
        )
