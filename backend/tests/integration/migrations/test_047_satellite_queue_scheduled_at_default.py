from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.alembic import run_alembic
from tests.support.seeds import SatelliteFixtureData


async def _insert_task(engine: AsyncEngine, satellite: SatelliteFixtureData) -> UUID:
    async with engine.begin() as connection:
        return await connection.scalar(
            text(
                "INSERT INTO satellite_queue (id, satellite_id, orbit_id, type) "
                "VALUES (gen_random_uuid(), :satellite_id, :orbit_id, 'deploy') "
                "RETURNING id"
            ),
            {
                "satellite_id": satellite.satellite.id,
                "orbit_id": satellite.orbit.id,
            },
        )


async def _schedule(
    engine: AsyncEngine, task_ids: list[UUID]
) -> list[tuple[datetime, datetime]]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT scheduled_at, created_at FROM satellite_queue "
                "WHERE id = ANY(:ids) ORDER BY array_position(:ids, id)"
            ),
            {"ids": task_ids},
        )
        return [(row.scheduled_at, row.created_at) for row in rows]


class TestSatelliteQueueScheduledAtDefaultMigration:
    async def test_upgrade_defaults_to_insert_time_and_backfills_created_at(
        self, engine: AsyncEngine, seeded_satellite: SatelliteFixtureData
    ) -> None:
        await run_alembic(engine, "downgrade", "046")
        old_tasks = [
            await _insert_task(engine, seeded_satellite),
            await _insert_task(engine, seeded_satellite),
        ]
        frozen = await _schedule(engine, old_tasks)
        assert frozen[0][0] == frozen[1][0]
        assert all(scheduled < created for scheduled, created in frozen)

        await run_alembic(engine, "upgrade", "head")
        new_tasks = [
            await _insert_task(engine, seeded_satellite),
            await _insert_task(engine, seeded_satellite),
        ]

        schedule = await _schedule(engine, old_tasks + new_tasks)
        assert all(scheduled == created for scheduled, created in schedule)
        assert [scheduled for scheduled, _ in schedule] == sorted(
            scheduled for scheduled, _ in schedule
        )
        assert len({scheduled for scheduled, _ in schedule}) == len(schedule)
