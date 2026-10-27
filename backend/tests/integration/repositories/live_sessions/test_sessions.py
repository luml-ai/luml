import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.live_session import LiveSessionStatus, LiveSessionVisibility
from luml.schemas.orbit import OrbitCreateIn
from luml.schemas.user import CreateUser
from sqlalchemy.exc import IntegrityError

from tests.support.live_sessions import (
    OWN,
    count_tokens,
    create_other_user,
    create_relay,
    issue_expose_token,
    set_fields,
    start_session,
    unviewed_for,
)
from tests.support.seeds import OrbitFixtureData


class TestLiveSessionRepository:
    async def test_create_live_session(self, seeded_orbit: OrbitFixtureData) -> None:
        data = seeded_orbit

        relay = await create_relay(data.engine, data.organization.id)

        session = await start_session(data, label="training run", relay=relay)

        assert re.fullmatch(r"[a-z0-9]+", session.id)
        assert session.orbit_id == data.orbit.id
        assert session.user_id == data.user.id
        assert session.label == "training run"
        assert session.visibility == LiveSessionVisibility.OWNER
        assert session.relay_id == relay.id
        assert session.last_heartbeat_at is None
        assert session.ended_at is None
        assert session.status == LiveSessionStatus.DISCONNECTED

    async def test_session_identifiers_differ(
        self, seeded_orbit: OrbitFixtureData
    ) -> None:
        first = await start_session(seeded_orbit)
        second = await start_session(seeded_orbit)

        assert first.id != second.id

    async def test_identifier_clash_is_retried(
        self, seeded_orbit: OrbitFixtureData
    ) -> None:
        existing = await start_session(seeded_orbit)

        with patch(
            "luml.repositories.live_sessions.new_session_id",
            side_effect=[existing.id, "freshid00001"],
        ):
            session = await start_session(seeded_orbit)

        assert session.id == "freshid00001"

    async def test_identifier_is_never_reused(
        self, seeded_orbit: OrbitFixtureData
    ) -> None:
        existing = await start_session(seeded_orbit)

        with (
            patch(
                "luml.repositories.live_sessions.new_session_id",
                return_value=existing.id,
            ),
            pytest.raises(IntegrityError),
        ):
            await start_session(seeded_orbit)

    async def test_get_live_session(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)

        assert await repository.get_live_session(session.id) == session
        assert await repository.get_live_session("missing") is None

    async def test_record_heartbeat(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)

        live = await repository.record_heartbeat(session.id, connected=True)
        assert live is not None
        assert live.last_heartbeat_at is not None
        assert live.status == LiveSessionStatus.LIVE

        disconnected = await repository.record_heartbeat(session.id, connected=False)
        assert disconnected is not None
        assert disconnected.status == LiveSessionStatus.DISCONNECTED

    async def test_heartbeat_after_hour_of_silence_does_not_revive(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        silent_since = datetime.now(UTC) - timedelta(minutes=61)
        await set_fields(
            seeded_orbit.engine,
            session.id,
            started_at=silent_since,
            last_heartbeat_at=silent_since,
            connected=True,
        )

        result = await repository.record_heartbeat(session.id, connected=True)

        assert result is not None
        assert result.status == LiveSessionStatus.ENDED
        assert result.last_heartbeat_at == silent_since

    async def test_heartbeat_to_ended_session_is_not_recorded(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        await repository.end_live_session(session.id)

        result = await repository.record_heartbeat(session.id, connected=True)

        assert result is not None
        assert result.status == LiveSessionStatus.ENDED
        assert result.last_heartbeat_at is None

    async def test_heartbeat_to_missing_session(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        assert await repository.record_heartbeat("missing", connected=True) is None

    async def test_end_live_session(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        await repository.record_heartbeat(session.id, connected=True)

        ended = await repository.end_live_session(session.id)
        assert ended is not None
        assert ended.ended_at is not None
        assert ended.status == LiveSessionStatus.ENDED

        ended_again = await repository.end_live_session(session.id)
        assert ended_again is not None
        assert ended_again.ended_at == ended.ended_at
        assert await repository.end_live_session("missing") is None

    async def test_ending_a_silent_session_keeps_its_end_time(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        last_heartbeat = datetime.now(UTC) - timedelta(hours=3)
        await set_fields(
            seeded_orbit.engine,
            session.id,
            started_at=last_heartbeat,
            last_heartbeat_at=last_heartbeat,
        )

        ended = await repository.end_live_session(session.id)

        assert ended is not None
        assert ended.ended_at == last_heartbeat + timedelta(hours=1)

    async def test_list_contains_only_own_sessions_of_the_orbit(
        self,
        repository: LiveSessionRepository,
        seeded_orbit: OrbitFixtureData,
        new_user: CreateUser,
    ) -> None:
        data = seeded_orbit
        other_user_id = await create_other_user(data.engine, new_user)
        other_orbit = await OrbitRepository(data.engine).create_orbit(
            data.organization.id,
            OrbitCreateIn(name="other orbit", bucket_secret_id=data.bucket_secret.id),
        )
        assert other_orbit is not None

        first = await start_session(data)
        second = await start_session(data)
        await start_session(data, user_id=other_user_id)
        await start_session(data, label="elsewhere", orbit_id=other_orbit.id)

        sessions = await repository.list_live_sessions(data.orbit.id, data.user.id)

        assert [s.id for s in sessions] == [second.id, first.id]

    async def test_list_drops_sessions_ended_over_a_day_ago(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        now = datetime.now(UTC)
        recent = await start_session(data, label="recent")
        old = await start_session(data, label="old")
        silent_recently = await start_session(data, label="silent recently")
        silent_long_ago = await start_session(data, label="silent long ago")
        await set_fields(data.engine, recent.id, ended_at=now - timedelta(hours=23))
        await set_fields(data.engine, old.id, ended_at=now - timedelta(hours=25))
        await set_fields(
            data.engine,
            silent_recently.id,
            started_at=now - timedelta(hours=30),
            last_heartbeat_at=now - timedelta(hours=24),
        )
        await set_fields(
            data.engine,
            silent_long_ago.id,
            started_at=now - timedelta(hours=30),
            last_heartbeat_at=now - timedelta(hours=26),
        )

        sessions = await repository.list_live_sessions(data.orbit.id, data.user.id)

        assert {s.label for s in sessions} == {"recent", "silent recently"}

    async def test_a_session_without_a_label_is_started(
        self, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit, label=None)

        assert session.label is None
        assert session.visibility == LiveSessionVisibility.OWNER

    async def test_heartbeat_to_a_session_nobody_viewed_is_not_recorded(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        await unviewed_for(
            seeded_orbit.engine, session.id, timedelta(days=7, minutes=1)
        )
        before = await repository.get_live_session(session.id)
        assert before is not None

        result = await repository.record_heartbeat(session.id, connected=True)

        assert result is not None
        assert result.status == LiveSessionStatus.ENDED
        assert result.last_heartbeat_at == before.last_heartbeat_at

    async def test_viewer_activity_resets_the_idle_clock(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        await unviewed_for(seeded_orbit.engine, session.id, timedelta(days=8))
        await set_fields(
            seeded_orbit.engine,
            session.id,
            last_viewer_activity_at=datetime.now(UTC) - timedelta(days=1),
        )

        result = await repository.record_heartbeat(session.id, connected=True)

        assert result is not None
        assert result.status == LiveSessionStatus.LIVE
        assert [
            s.id
            for s in await repository.list_live_sessions(
                seeded_orbit.orbit.id, seeded_orbit.user.id
            )
        ] == [session.id]
        await repository.check_session_slot(seeded_orbit.organization.id, OWN)

    async def test_recorded_viewer_activity_keeps_a_session_open(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        await unviewed_for(seeded_orbit.engine, session.id, timedelta(days=6, hours=23))

        await repository.record_viewer_activity(session.id)
        await unviewed_for(seeded_orbit.engine, session.id, timedelta(days=8))

        stored = await repository.get_live_session(session.id)
        assert stored is not None
        assert stored.status == LiveSessionStatus.LIVE

    async def test_ending_a_session_nobody_viewed_keeps_its_end_time(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        session = await start_session(seeded_orbit)
        await unviewed_for(seeded_orbit.engine, session.id, timedelta(days=7, hours=2))
        stored = await repository.get_live_session(session.id)
        assert stored is not None

        ended = await repository.end_live_session(session.id)

        assert ended is not None
        assert ended.ended_at == stored.started_at + timedelta(days=7)

    async def test_list_keeps_a_session_ended_by_viewer_idleness_for_a_day(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        recently = await start_session(data, label="recently")
        long_ago = await start_session(data, label="long ago")
        await unviewed_for(data.engine, recently.id, timedelta(days=7, hours=23))
        await unviewed_for(data.engine, long_ago.id, timedelta(days=8, hours=1))

        sessions = await repository.list_live_sessions(data.orbit.id, data.user.id)

        assert [(s.label, s.status) for s in sessions] == [
            ("recently", LiveSessionStatus.ENDED)
        ]

    async def test_ended_sessions_are_removed_after_their_retention_on_start(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        now = datetime.now(UTC)
        ended_by_owner = await start_session(data, label="ended by owner")
        silent = await start_session(data, label="silent")
        unviewed = await start_session(data, label="unviewed")
        ended_recently = await start_session(data, label="ended recently")
        for session in (ended_by_owner, silent, unviewed, ended_recently):
            await issue_expose_token(data.engine, session)
        await set_fields(
            data.engine,
            ended_by_owner.id,
            started_at=now - timedelta(days=3),
            ended_at=now - timedelta(days=2),
        )
        await set_fields(
            data.engine,
            silent.id,
            started_at=now - timedelta(hours=30),
            last_heartbeat_at=now - timedelta(hours=26),
        )
        await unviewed_for(data.engine, unviewed.id, timedelta(days=8, hours=1))
        await set_fields(
            data.engine, ended_recently.id, ended_at=now - timedelta(minutes=10)
        )

        await start_session(data, label="new")

        for gone in (ended_by_owner, silent, unviewed):
            assert await repository.get_live_session(gone.id) is None
            assert await count_tokens(data.engine, gone.id) == 0
        kept = await repository.get_live_session(ended_recently.id)
        assert kept is not None
        assert kept.status == LiveSessionStatus.ENDED
        assert await count_tokens(data.engine, ended_recently.id) == 1
        listed = await repository.list_live_sessions(data.orbit.id, data.user.id)
        assert {s.label for s in listed} == {"ended recently", "new"}

    async def test_ended_sessions_are_removed_after_their_retention_on_end(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        old = await start_session(data)
        current = await start_session(data)
        await set_fields(
            data.engine, old.id, ended_at=datetime.now(UTC) - timedelta(days=2)
        )

        ended = await repository.end_live_session(current.id)

        assert ended is not None
        assert ended.status == LiveSessionStatus.ENDED
        assert await repository.get_live_session(old.id) is None
        assert await repository.get_live_session(current.id) is not None

    async def test_a_session_silent_for_a_day_but_ended_late_is_removed_by_its_silence(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        session = await start_session(data)
        await set_fields(
            data.engine,
            session.id,
            started_at=datetime.now(UTC) - timedelta(hours=27),
            last_heartbeat_at=datetime.now(UTC) - timedelta(hours=26),
        )

        assert await repository.end_live_session(session.id) is not None

        assert await repository.get_live_session(session.id) is None
