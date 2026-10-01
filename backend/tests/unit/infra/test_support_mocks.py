from unittest.mock import AsyncMock, Mock

import pytest
from luml.handlers.artifacts import ArtifactHandler
from luml.handlers.lineage import LineageHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.exceptions import InsufficientPermissionsError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.lineage import LineageRepository
from luml.schemas.permissions import Action, Resource

from tests.support.ids import ARTIFACT_ID, ORBIT_ID, ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

ARTIFACT_COLLABORATORS = {
    "repository",
    "orbit_repository",
    "secret_repository",
    "collection_repository",
    "deployment_repository",
    "lineage_repository",
    "track_entry_repository",
    "track_repository",
    "user_repository",
    "permissions_handler",
    "lineage_handler",
}
LINEAGE_COLLABORATORS = {
    "repository",
    "artifact_repository",
    "orbit_repository",
    "user_repository",
    "permissions_handler",
}


class TestSupportMocks:
    @pytest.fixture
    def artifact_mocks(self) -> CollaboratorMocks[ArtifactHandler]:
        return mock_collaborators(ArtifactHandler())

    @pytest.fixture
    def lineage_mocks(self) -> CollaboratorMocks[LineageHandler]:
        return mock_collaborators(LineageHandler())

    def test_artifact_handler_collaborators_are_all_replaced(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        exposed = set(vars(artifact_mocks)) - {
            "handler",
            "session",
            "transaction_errors",
        }

        assert exposed == ARTIFACT_COLLABORATORS
        for name in ARTIFACT_COLLABORATORS:
            mock = getattr(artifact_mocks, name)
            assert isinstance(mock, Mock)
            assert vars(artifact_mocks.handler)[f"_ArtifactHandler__{name}"] is mock

    def test_lineage_handler_collaborators_are_all_replaced(
        self, lineage_mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        exposed = set(vars(lineage_mocks)) - {
            "handler",
            "session",
            "transaction_errors",
        }

        assert exposed == LINEAGE_COLLABORATORS
        for name in LINEAGE_COLLABORATORS:
            mock = getattr(lineage_mocks, name)
            assert isinstance(mock, Mock)
            assert vars(lineage_mocks.handler)[f"_LineageHandler__{name}"] is mock

    def test_non_collaborator_attributes_stay_real(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        assert not hasattr(artifact_mocks, "artifact_transitions")
        assert "_ArtifactHandler__artifact_transitions" not in vars(
            artifact_mocks.handler
        )

    def test_permission_tables_of_a_real_permissions_handler_stay_real(
        self,
    ) -> None:
        mocks = mock_collaborators(PermissionsHandler())

        assert set(vars(mocks)) - {"handler", "session", "transaction_errors"} == {
            "user_repository",
            "orbits_repository",
        }
        assert "_PermissionsHandler__org_permissions" not in vars(mocks.handler)
        assert "_PermissionsHandler__orbit_permissions" not in vars(mocks.handler)

    def test_spec_enforced(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        assert artifact_mocks.repository._spec_class is ArtifactRepository
        assert isinstance(artifact_mocks.repository.delete_artifact, AsyncMock)
        assert not isinstance(
            artifact_mocks.permissions_handler.has_orbit_permission, AsyncMock
        )
        with pytest.raises(AttributeError):
            artifact_mocks.repository.no_such_method  # noqa: B018
        with pytest.raises(AttributeError):
            artifact_mocks.permissions_handler.no_such_method  # noqa: B018

    async def test_helper_handler_methods_return_nothing(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        assert (
            await artifact_mocks.permissions_handler.check_permissions(
                ORGANIZATION_ID, USER_ID, Resource.ARTIFACT, Action.DELETE, ORBIT_ID
            )
            is None
        )
        assert artifact_mocks.permissions_handler.has_orbit_permission() is None
        assert await artifact_mocks.lineage_handler.link_inputs() is None

    async def test_permission_refusal_propagates(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        artifact_mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        with pytest.raises(InsufficientPermissionsError):
            await artifact_mocks.handler.confirm_deletion(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, ORBIT_ID, ARTIFACT_ID
            )

        artifact_mocks.repository.get_artifact.assert_not_awaited()
        artifact_mocks.repository.delete_artifact.assert_not_awaited()

    async def test_transaction_passes_the_session(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        await artifact_mocks.handler._delete_artifact(ORBIT_ID, ARTIFACT_ID)

        artifact_mocks.lineage_repository.transaction.assert_called_once_with()
        artifact_mocks.lineage_repository.lock_orbit.assert_awaited_once_with(
            ORBIT_ID, artifact_mocks.session
        )
        artifact_mocks.repository.delete_artifact.assert_awaited_once_with(
            ARTIFACT_ID, artifact_mocks.session
        )
        assert artifact_mocks.transaction_errors == []

    async def test_transaction_records_errors(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        failure = RuntimeError("delete failed")
        artifact_mocks.repository.delete_artifact.side_effect = failure

        with pytest.raises(RuntimeError):
            await artifact_mocks.handler._delete_artifact(ORBIT_ID, ARTIFACT_ID)

        assert artifact_mocks.transaction_errors == [failure]
        artifact_mocks.lineage_repository.delete_unreachable_deleted_nodes.assert_not_awaited()

    async def test_lineage_repository_transaction_is_faked(
        self, lineage_mocks: CollaboratorMocks[LineageHandler]
    ) -> None:
        failure = ValueError("inside")

        async with lineage_mocks.repository.transaction() as session:
            assert session is lineage_mocks.session
        with pytest.raises(ValueError, match="inside"):
            async with lineage_mocks.repository.transaction():
                raise failure

        assert lineage_mocks.transaction_errors == [failure]

    def test_each_call_gets_its_own_session_and_errors(
        self,
        artifact_mocks: CollaboratorMocks[ArtifactHandler],
        lineage_mocks: CollaboratorMocks[LineageHandler],
    ) -> None:
        artifact_mocks.transaction_errors.append(RuntimeError())

        assert artifact_mocks.session is not lineage_mocks.session
        assert lineage_mocks.transaction_errors == []

    def test_production_class_untouched(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        artifact_repository = vars(ArtifactHandler)["_ArtifactHandler__repository"]
        lineage_repository = vars(ArtifactHandler)[
            "_ArtifactHandler__lineage_repository"
        ]
        fresh = ArtifactHandler()

        assert type(artifact_repository) is ArtifactRepository
        assert type(lineage_repository) is LineageRepository
        assert type(vars(ArtifactHandler)["_ArtifactHandler__lineage_handler"]) is (
            LineageHandler
        )
        assert vars(fresh) == {}

    def test_returned_object_carries_extra_attributes(
        self, artifact_mocks: CollaboratorMocks[ArtifactHandler]
    ) -> None:
        extra = Mock()
        artifact_mocks.auth_handler = extra

        assert artifact_mocks.auth_handler is extra
