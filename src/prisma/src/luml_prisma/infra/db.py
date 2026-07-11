from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(
    dbapi_connection: Any,  # noqa: ANN401
    connection_record: Any,  # noqa: ANN401
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(db_url: str) -> Engine:
    from sqlalchemy import create_engine

    kwargs: dict[str, Any] = {
        "connect_args": {"check_same_thread": False},
    }
    if db_url == "sqlite://" or db_url == "sqlite:///:memory:":
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(db_url, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Any]:
    return sessionmaker(bind=engine, expire_on_commit=False)
