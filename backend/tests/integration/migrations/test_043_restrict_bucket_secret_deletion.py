from luml.models import BucketSecretOrm, CollectionOrm, OrbitOrm
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.alembic import run_alembic
from tests.support.seeds import CollectionFixtureData


class TestBucketSecretDeletionMigration:
    async def test_upgrade_and_downgrade_change_delete_rule_and_preserve_data(
        self, engine: AsyncEngine, seeded_collection: CollectionFixtureData
    ) -> None:
        for upgrade in (False, True, False):
            await run_alembic(
                engine,
                "upgrade" if upgrade else "downgrade",
                "head" if upgrade else "042",
            )
            delete_rule = "RESTRICT" if upgrade else "CASCADE"
            async with engine.connect() as connection:
                foreign_keys = await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_foreign_keys(
                        "orbits"
                    )
                )
                bucket_secret_key = next(
                    key
                    for key in foreign_keys
                    if key["constrained_columns"] == ["bucket_secret_id"]
                )
                assert bucket_secret_key["options"]["ondelete"] == delete_rule
                for model, record_id in (
                    (BucketSecretOrm, seeded_collection.bucket_secret.id),
                    (OrbitOrm, seeded_collection.orbit.id),
                    (CollectionOrm, seeded_collection.collection.id),
                ):
                    assert (
                        await connection.scalar(
                            select(model.id).where(model.id == record_id)
                        )
                        == record_id
                    )
