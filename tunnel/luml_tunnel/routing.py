import re
from typing import Protocol

from luml_tunnel.protocol import RelayConnection

MAX_AGENTS = 1000

_SESSION_ID = re.compile(r"[a-z0-9]+")


class SessionResolver(Protocol):
    def session_for(self, host: str) -> str | None:
        """Return the session a request's host addresses, or None for the relay itself."""
        ...


class AgentRegistry(Protocol):
    def register(self, session: str, connection: RelayConnection) -> None: ...

    def unregister(self, session: str, connection: RelayConnection) -> None:
        """Remove the connection unless another one has taken its place."""
        ...

    def get(self, session: str) -> RelayConnection | None: ...

    def connections(self) -> list[RelayConnection]: ...


class HostnameSessionResolver:
    def __init__(self, base_domain: str) -> None:
        self._suffix = "." + base_domain.lower()

    def session_for(self, host: str) -> str | None:
        hostname = host.rsplit(":", 1)[0].lower()
        if not hostname.endswith(self._suffix):
            return None
        label = hostname.removesuffix(self._suffix)
        return label if _SESSION_ID.fullmatch(label) else None


class InMemoryAgentRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, RelayConnection] = {}

    def register(self, session: str, connection: RelayConnection) -> None:
        self._connections[session] = connection

    def unregister(self, session: str, connection: RelayConnection) -> None:
        if self._connections.get(session) is connection:
            del self._connections[session]

    def get(self, session: str) -> RelayConnection | None:
        return self._connections.get(session)

    def connections(self) -> list[RelayConnection]:
        return list(self._connections.values())
