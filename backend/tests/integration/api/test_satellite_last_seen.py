from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.satellites import SatelliteHandler
from luml.models import SatelliteOrm
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.satellite import SatelliteCreate
from luml.service import AppService
from sqlalchemy import event, update
from sqlalchemy.engine import Connection, ExecutionContext
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.seeds import OrbitFixtureData


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/satellites/v1/tasks", None),
        ("POST", "/satellites/v1/pair", {"capabilities": {"deploy": {"version": 1}}}),
    ],
)
async def test_satellite_requests_write_one_heartbeat_then_throttle(
    seeded_orbit: OrbitFixtureData,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    engine = seeded_orbit.engine
    repository = SatelliteRepository(engine)
    handler = SatelliteHandler()
    satellite = await repository.create_satellite(
        SatelliteCreate(
            orbit_id=seeded_orbit.orbit.id,
            name="heartbeat",
            api_key_hash=handler._get_key_hash("dfssat_heartbeat-test"),
        )
    )
    monkeypatch.setattr(SatelliteHandler, "_SatelliteHandler__sat_repo", repository)
    updates: list[str] = []

    def record_update(
        _conn: Connection,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: ExecutionContext,
        _executemany: bool,
    ) -> None:
        if statement.startswith("UPDATE satellites"):
            updates.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record_update)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=AppService()),
            base_url="http://test",
            headers={"Authorization": "Bearer dfssat_heartbeat-test"},
        ) as client:
            for expected_heartbeats in (1, 0):
                updates.clear()
                response = await client.request(method, path, json=payload)
                assert response.status_code == 200
                heartbeats = [
                    statement
                    for statement in updates
                    if "last_seen_at" in statement.split(" WHERE ")[0]
                ]
                assert len(heartbeats) == expected_heartbeats
                if method == "GET":
                    assert len(updates) == expected_heartbeats

            async with AsyncSession(engine) as session:
                await session.execute(
                    update(SatelliteOrm)
                    .where(SatelliteOrm.id == satellite.id)
                    .values(last_seen_at=datetime.now(UTC) - timedelta(seconds=61))
                )
                await session.commit()
            updates.clear()
            response = await client.request(method, path, json=payload)
            assert response.status_code == 200
            assert (
                sum(
                    "last_seen_at" in statement.split(" WHERE ")[0]
                    for statement in updates
                )
                == 1
            )

            updates.clear()
            response = await client.get(
                "/satellites/v1/tasks",
                headers={"Authorization": "Bearer dfssat_invalid-test"},
            )
            assert response.status_code == 401
            assert not updates
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record_update)
