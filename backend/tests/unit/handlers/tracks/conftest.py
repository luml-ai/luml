from datetime import datetime
from typing import Any

import pytest
from luml.handlers.tracks import TracksHandler
from luml.schemas.tracks import Stage, Track, TrackEntry
from sqlalchemy.exc import IntegrityError

from tests.support.ids import ARTIFACT_ID, ENTRY_ID, ORBIT_ID, STAGE_ID, TRACK_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

USER_NAME = "Track Author"
USER_EMAIL = "track.author@example.com"


@pytest.fixture
def mocks() -> CollaboratorMocks[TracksHandler]:
    return mock_collaborators(TracksHandler())


def _make_track(**overrides: object) -> Track:
    defaults: dict[str, Any] = {
        "id": TRACK_ID,
        "orbit_id": ORBIT_ID,
        "name": "churn-model",
        "artifact_type": "model",
        "description": None,
        "tags": None,
        "next_version": 1,
        "total_entries": 0,
        "created_at": datetime.now(),
        "updated_at": None,
    }
    defaults.update(overrides)
    return Track(**defaults)


def _make_entry(**overrides: object) -> TrackEntry:
    defaults: dict[str, Any] = {
        "id": ENTRY_ID,
        "track_id": TRACK_ID,
        "artifact_id": ARTIFACT_ID,
        "version": 1,
        "stage_id": None,
        "added_by": USER_NAME,
        "created_at": datetime.now(),
        "updated_at": None,
    }
    defaults.update(overrides)
    return TrackEntry(**defaults)


def _make_stage(**overrides: object) -> Stage:
    defaults: dict[str, Any] = {
        "id": STAGE_ID,
        "track_id": TRACK_ID,
        "name": "Staging",
        "created_at": datetime.now(),
        "updated_at": None,
    }
    defaults.update(overrides)
    return Stage(**defaults)


class _DriverError(Exception):
    def __init__(
        self, constraint_name: str | None = None, sqlstate: str | None = None
    ) -> None:
        super().__init__("driver error")
        self.constraint_name = constraint_name
        self.sqlstate = sqlstate


def _integrity_error(
    constraint_name: str | None = None, sqlstate: str | None = None
) -> IntegrityError:
    return IntegrityError("", {}, _DriverError(constraint_name, sqlstate))
