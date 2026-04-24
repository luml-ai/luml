from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase


def _uuid_pk() -> str:
    return uuid4().hex


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass
