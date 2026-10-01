import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from inspect import unwrap
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import uuid7

import asyncpg  # type: ignore[import-untyped]
import pytest
from luml.settings import config
from sqlalchemy.engine import URL, make_url

from tests import conftest as fixtures

prepare_template = cast(
    Callable[[], Generator[tuple[str, str]]], unwrap(fixtures.database_template)
)
clone_database = cast(
    Callable[[tuple[str, str]], AsyncGenerator[str]],
    unwrap(fixtures.create_database_and_apply_migrations),
)


@pytest.fixture
def admin_connection(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    connection = AsyncMock()
    connection.fetchval.return_value = False
    monkeypatch.setattr(asyncpg, "connect", AsyncMock(return_value=connection))
    return connection


@pytest.fixture
def migration(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    migrate = AsyncMock()
    monkeypatch.setattr(fixtures, "migrate_db", migrate)
    return migrate


class TestDatabaseFixture:
    @pytest.mark.parametrize("database", ["df_studio", fixtures.TEMPLATE_DB_NAME, None])
    def test_wrong_database_stops_before_connecting(
        self,
        database: str | None,
        monkeypatch: pytest.MonkeyPatch,
        admin_connection: AsyncMock,
        migration: AsyncMock,
    ) -> None:
        url = URL.create("postgresql+asyncpg", host="localhost", database=database)
        monkeypatch.setattr(config, "POSTGRESQL_DSN", str(url))

        with pytest.raises(pytest.exit.Exception, match=fixtures.TEST_DB_NAME):
            next(prepare_template())

        asyncpg.connect.assert_not_called()
        migration.assert_not_awaited()

    @pytest.mark.parametrize("parameter", ["database", "dbname"])
    def test_query_cannot_override_the_guarded_database(
        self,
        parameter: str,
        monkeypatch: pytest.MonkeyPatch,
        admin_connection: AsyncMock,
        migration: AsyncMock,
    ) -> None:
        url = make_url(config.POSTGRESQL_DSN).set(query={parameter: "df_studio"})
        monkeypatch.setattr(config, "POSTGRESQL_DSN", str(url))

        with pytest.raises(pytest.exit.Exception, match=fixtures.TEST_DB_NAME):
            next(prepare_template())

        asyncpg.connect.assert_not_called()
        migration.assert_not_awaited()

    def test_template_is_migrated_once_and_connections_are_closed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_connection: AsyncMock,
        migration: AsyncMock,
    ) -> None:
        url = URL.create(
            "postgresql+asyncpg",
            username=f"user_{fixtures.TEST_DB_NAME}",
            password=f"{fixtures.TEST_DB_NAME}:+asyncpg@/?",
            host="::1",
            port=5433,
            database=fixtures.TEST_DB_NAME,
            query={"application_name": fixtures.TEST_DB_NAME},
        )
        test_dsn = url.render_as_string(hide_password=False)
        monkeypatch.setattr(config, "POSTGRESQL_DSN", test_dsn)
        preparation = prepare_template()
        try:
            admin_dsn, yielded_dsn = next(preparation)
            assert yielded_dsn == test_dsn
            assert make_url(admin_dsn) == url.set(
                drivername="postgresql", database="postgres"
            )
            migration.assert_awaited_once_with(
                url.set(database=fixtures.TEMPLATE_DB_NAME).render_as_string(
                    hide_password=False
                )
            )
            admin_connection.close.assert_not_awaited()

            async def run_test() -> None:
                database = clone_database((admin_dsn, yielded_dsn))
                try:
                    assert await anext(database) == test_dsn
                finally:
                    await database.aclose()

            asyncio.run(run_test())
            asyncio.run(run_test())
            migration.assert_awaited_once()
        finally:
            preparation.close()

        assert admin_connection.close.await_count == 3
        statements = [call.args[0] for call in admin_connection.execute.await_args_list]
        clone = (
            f'CREATE DATABASE "{fixtures.TEST_DB_NAME}" '
            f'TEMPLATE "{fixtures.TEMPLATE_DB_NAME}";'
        )
        assert statements.count(clone) == 2
        assert statements[-1] == (
            f'DROP DATABASE IF EXISTS "{fixtures.TEMPLATE_DB_NAME}";'
        )

    def test_interrupted_run_leftovers_are_dropped_and_recreated(
        self, admin_connection: AsyncMock, migration: AsyncMock
    ) -> None:
        leftovers = {
            fixtures.TEST_DB_NAME: object(),
            fixtures.TEMPLATE_DB_NAME: object(),
        }
        databases = leftovers.copy()
        idle_connections = set(databases)

        async def execute(statement: str, database_name: str | None = None) -> None:
            if "pg_terminate_backend" in statement:
                assert database_name is not None
                idle_connections.discard(database_name)
                return

            database_name = statement.split('"')[1]
            if statement.startswith("DROP DATABASE"):
                if database_name in idle_connections:
                    raise asyncpg.ObjectInUseError(database_name)
                databases.pop(database_name, None)
            elif statement.startswith("CREATE DATABASE"):
                if database_name in databases:
                    raise asyncpg.DuplicateDatabaseError(database_name)
                if " TEMPLATE " in statement:
                    template_name = statement.split('"')[3]
                    assert template_name in databases
                    assert template_name not in idle_connections
                databases[database_name] = object()
            else:
                raise AssertionError(f"Unexpected statement: {statement}")

        admin_connection.execute.side_effect = execute
        preparation = prepare_template()
        try:
            connection_strings = next(preparation)

            assert not idle_connections
            assert fixtures.TEST_DB_NAME not in databases
            assert (
                databases[fixtures.TEMPLATE_DB_NAME]
                is not leftovers[fixtures.TEMPLATE_DB_NAME]
            )
            migration.assert_awaited_once()

            async def run_test() -> None:
                database = clone_database(connection_strings)
                try:
                    assert await anext(database) == config.POSTGRESQL_DSN
                    assert (
                        databases[fixtures.TEST_DB_NAME]
                        is not leftovers[fixtures.TEST_DB_NAME]
                    )
                finally:
                    await database.aclose()

            asyncio.run(run_test())
        finally:
            preparation.close()

        assert not databases

    def test_failed_migration_drops_template_and_closes_connections(
        self, admin_connection: AsyncMock, migration: AsyncMock
    ) -> None:
        migration.side_effect = RuntimeError("migration failed")

        with pytest.raises(RuntimeError, match="migration failed"):
            next(prepare_template())

        admin_connection.execute.assert_awaited_with(
            f'DROP DATABASE IF EXISTS "{fixtures.TEMPLATE_DB_NAME}";'
        )
        admin_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failed_clone_drops_database_and_closes_connections(
        self, admin_connection: AsyncMock
    ) -> None:
        admin_connection.execute.side_effect = [
            None,
            None,
            RuntimeError("clone failed"),
            None,
            None,
        ]
        database = clone_database(
            ("postgresql://localhost/postgres", config.POSTGRESQL_DSN)
        )

        with pytest.raises(RuntimeError, match="clone failed"):
            await anext(database)

        admin_connection.execute.assert_awaited_with(
            f'DROP DATABASE IF EXISTS "{fixtures.TEST_DB_NAME}";'
        )
        admin_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failing_test_still_drops_its_database(
        self, admin_connection: AsyncMock
    ) -> None:
        database = clone_database(
            ("postgresql://localhost/postgres", config.POSTGRESQL_DSN)
        )
        await anext(database)

        with pytest.raises(RuntimeError, match="test failed"):
            await database.athrow(RuntimeError("test failed"))

        admin_connection.execute.assert_awaited_with(
            f'DROP DATABASE IF EXISTS "{fixtures.TEST_DB_NAME}";'
        )
        admin_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_drop_waits_for_terminated_sessions_to_disconnect(
        self, admin_connection: AsyncMock
    ) -> None:
        admin_connection.fetchval.side_effect = [True, False]

        await fixtures._drop_database(admin_connection, fixtures.TEST_DB_NAME)

        assert admin_connection.fetchval.await_count == 2
        assert [call[0] for call in admin_connection.mock_calls] == [
            "execute",
            "fetchval",
            "fetchval",
            "execute",
        ]

    @pytest.mark.asyncio
    async def test_stuck_session_times_out_without_dropping_database(
        self, admin_connection: AsyncMock
    ) -> None:
        database = clone_database(
            ("postgresql://localhost/postgres", config.POSTGRESQL_DSN)
        )
        await anext(database)
        admin_connection.execute.reset_mock()
        admin_connection.fetchval.return_value = True

        with (
            patch("tests.conftest.asyncio.timeout", return_value=asyncio.timeout(0)),
            pytest.raises(TimeoutError),
        ):
            await database.aclose()

        assert all(
            "DROP DATABASE" not in call.args[0]
            for call in admin_connection.execute.await_args_list
        )
        admin_connection.close.assert_awaited_once()


class TestDatabaseIsolation:
    @pytest.mark.parametrize("_attempt", range(2))
    @pytest.mark.asyncio
    async def test_clone_restores_data_and_schema(
        self,
        _attempt: int,
        create_database_and_apply_migrations: str,
    ) -> None:
        url = make_url(create_database_and_apply_migrations).set(
            drivername="postgresql"
        )
        connection = await asyncpg.connect(url.render_as_string(hide_password=False))
        try:
            assert await connection.fetchval("SELECT count(*) FROM organizations") == 0
            await connection.execute(
                "INSERT INTO organizations (id, name) VALUES ($1, $2)",
                uuid7(),
                "fixture regression",
            )
            assert await connection.fetchval("SELECT count(*) FROM organizations") == 1
            await connection.execute("DROP TABLE organizations CASCADE")
        finally:
            await connection.close()
