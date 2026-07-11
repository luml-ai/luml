from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import sessionmaker


class RepositoryBase:
    def __init__(self, session_factory: sessionmaker[Any]) -> None:
        self._session_factory = session_factory

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
