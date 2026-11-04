from uuid import uuid4

import pytest
from luml.handlers.tracks import TracksHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.tracks import StageCreateIn, StageUpdateIn
from sqlalchemy.exc import IntegrityError

from tests.support.ids import (
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    STAGE_ID,
    TRACK_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.tracks.conftest import _make_stage, _make_track


class TestTrackStages:
    async def test_create_stage_returns_created_stage(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        expected = _make_stage(name="QA")
        mocks.stage_repository.create_stage.return_value = expected

        result = await mocks.handler.create_stage(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            StageCreateIn(name="QA"),
        )

        assert result == expected

    async def test_create_stage_raises_conflict_when_name_exists(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.create_stage.side_effect = IntegrityError(
            "", {}, Exception()
        )

        with pytest.raises(ApplicationError, match="already exists") as exc:
            await mocks.handler.create_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                StageCreateIn(name="Staging"),
            )
        assert exc.value.status_code == 409

    async def test_create_stage_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.create_stage(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, StageCreateIn(name="x")
            )

    async def test_list_stages_returns_track_stages(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        stages = [_make_stage()]
        mocks.stage_repository.list_stages.return_value = stages

        result = await mocks.handler.list_stages(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID
        )

        assert result == stages

    async def test_list_stages_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.list_stages(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID
            )

    async def test_update_stage_returns_updated_stage(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        expected = _make_stage(name="Renamed")
        mocks.stage_repository.update_stage.return_value = expected

        result = await mocks.handler.update_stage(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            TRACK_ID,
            STAGE_ID,
            StageUpdateIn(name="Renamed"),
        )

        assert result == expected

    async def test_update_stage_raises_not_found_when_stage_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.stage_repository.update_stage.return_value = None

        with pytest.raises(NotFoundError, match="Stage not found"):
            await mocks.handler.update_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                STAGE_ID,
                StageUpdateIn(name="Renamed"),
            )

    async def test_update_stage_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.update_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                STAGE_ID,
                StageUpdateIn(name="x"),
            )

    async def test_update_stage_raises_conflict_when_name_exists(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.stage_repository.update_stage.side_effect = IntegrityError(
            "", {}, Exception()
        )
        with pytest.raises(ApplicationError, match="already exists") as exc:
            await mocks.handler.update_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                STAGE_ID,
                StageUpdateIn(name="dup"),
            )
        assert exc.value.status_code == 409

    async def test_delete_stage_deletes_without_unassign_when_stage_is_unused(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.stage_repository.is_stage_in_use.return_value = False

        await mocks.handler.delete_stage(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID
        )

        mocks.stage_repository.delete_stage.assert_awaited_once_with(
            STAGE_ID, unassign=False
        )

    async def test_delete_stage_raises_conflict_when_stage_is_in_use_without_force(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.stage_repository.is_stage_in_use.return_value = True

        with pytest.raises(ApplicationError, match="currently assigned") as exc:
            await mocks.handler.delete_stage(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID
            )
        assert exc.value.status_code == 409

    async def test_delete_stage_unassigns_when_stage_is_in_use_and_forced(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = _make_track()
        mocks.stage_repository.get_stage.return_value = _make_stage()
        mocks.stage_repository.is_stage_in_use.return_value = True

        await mocks.handler.delete_stage(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID, force=True
        )

        mocks.stage_repository.delete_stage.assert_awaited_once_with(
            STAGE_ID, unassign=True
        )

    async def test_delete_stage_raises_not_found_when_track_is_missing(
        self, mocks: CollaboratorMocks[TracksHandler]
    ) -> None:
        mocks.track_repository.get_track.return_value = None
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.delete_stage(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, TRACK_ID, STAGE_ID
            )


@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize("missing", [False, True])
async def test_stage_mutations_reject_stage_outside_track(
    mocks: CollaboratorMocks[TracksHandler], operation: str, missing: bool
) -> None:
    mocks.track_repository.get_track.return_value = _make_track()
    mocks.stage_repository.get_stage.return_value = (
        None if missing else _make_stage(track_id=uuid4())
    )
    if operation == "update":
        with pytest.raises(NotFoundError, match="Stage not found"):
            await mocks.handler.update_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                STAGE_ID,
                StageUpdateIn(name="pwned"),
            )
    else:
        with pytest.raises(NotFoundError, match="Stage not found"):
            await mocks.handler.delete_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                STAGE_ID,
                force=True,
            )
    mocks.stage_repository.update_stage.assert_not_awaited()
    mocks.stage_repository.delete_stage.assert_not_awaited()
    mocks.stage_repository.is_stage_in_use.assert_not_awaited()


@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_stage_mutations_reject_foreign_orbit(
    mocks: CollaboratorMocks[TracksHandler], operation: str
) -> None:
    mocks.track_repository.get_track.return_value = _make_track(orbit_id=OTHER_ORBIT_ID)
    if operation == "update":
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.update_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                STAGE_ID,
                StageUpdateIn(name="pwned"),
            )
    else:
        with pytest.raises(NotFoundError, match="Track not found"):
            await mocks.handler.delete_stage(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                TRACK_ID,
                STAGE_ID,
                force=True,
            )
    mocks.stage_repository.update_stage.assert_not_awaited()
    mocks.stage_repository.delete_stage.assert_not_awaited()
