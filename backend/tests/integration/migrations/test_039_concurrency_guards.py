import time
import uuid

import jwt
import pytest
from alembic import command
from luml.models import TokenBlackListOrm
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from utils.db import cfg as alembic_cfg


async def _alembic(engine: AsyncEngine, action: str, revision: str) -> None:
    def run(connection: Connection) -> None:
        alembic_cfg.attributes["connection"] = connection
        getattr(command, action)(alembic_cfg, revision)

    async with engine.begin() as connection:
        await connection.run_sync(run)


async def _blacklist_expiry(engine: AsyncEngine, token: str) -> list[int]:
    async with AsyncSession(engine) as session:
        return list(
            await session.scalars(
                select(TokenBlackListOrm.expire_at).where(
                    TokenBlackListOrm.token == token
                )
            )
        )


class TestConcurrencyGuards:
    @pytest.mark.asyncio
    async def test_migration_keeps_the_longest_blacklist_expiry(
        self, create_database_and_apply_migrations: str
    ) -> None:
        engine = create_async_engine(create_database_and_apply_migrations)
        token = f"refresh-{uuid.uuid4()}"
        await _alembic(engine, "downgrade", "038")
        async with AsyncSession(engine) as session:
            await session.execute(
                insert(TokenBlackListOrm),
                [
                    {"id": uuid.uuid4(), "token": token, "expire_at": 100},
                    {"id": uuid.uuid4(), "token": token, "expire_at": 300},
                    {"id": uuid.uuid4(), "token": token, "expire_at": 200},
                ],
            )
            await session.commit()

        await _alembic(engine, "upgrade", "head")

        assert await _blacklist_expiry(engine, token) == [300]

    @pytest.mark.asyncio
    async def test_migration_extends_legacy_rows_to_the_token_expiry(
        self, create_database_and_apply_migrations: str
    ) -> None:
        engine = create_async_engine(create_database_and_apply_migrations)
        now = int(time.time())
        refresh_exp = now + 7 * 86400
        access_exp = now + 3 * 3600

        def refresh_token() -> str:
            claims = {
                "sub": f"{uuid.uuid4()}@x.io",
                "type": "refresh",
                "exp": refresh_exp,
            }
            return jwt.encode(claims, "secret", algorithm="HS256")

        shortened = refresh_token()
        already_dropped = refresh_token()
        listed_longer = refresh_token()
        opaque = f"opaque-{uuid.uuid4()}"

        await _alembic(engine, "downgrade", "038")
        async with AsyncSession(engine) as session:
            await session.execute(
                insert(TokenBlackListOrm),
                [
                    {"id": uuid.uuid4(), "token": shortened, "expire_at": access_exp},
                    {
                        "id": uuid.uuid4(),
                        "token": already_dropped,
                        "expire_at": now - 60,
                    },
                    {
                        "id": uuid.uuid4(),
                        "token": listed_longer,
                        "expire_at": refresh_exp + 60,
                    },
                    {"id": uuid.uuid4(), "token": opaque, "expire_at": access_exp},
                ],
            )
            await session.commit()

        await _alembic(engine, "upgrade", "head")

        assert await _blacklist_expiry(engine, shortened) == [refresh_exp]
        assert await _blacklist_expiry(engine, already_dropped) == [refresh_exp]
        assert await _blacklist_expiry(engine, listed_longer) == [refresh_exp + 60]
        assert await _blacklist_expiry(engine, opaque) == [access_exp]
