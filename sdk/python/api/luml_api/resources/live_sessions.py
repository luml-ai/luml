from datetime import datetime
from typing import TYPE_CHECKING

from luml_api._types import (
    LiveSession,
    LiveSessionHeartbeat,
    LiveSessionStart,
    LiveSessionViewToken,
)

if TYPE_CHECKING:
    from luml_api._client import AsyncLumlClient, LumlClient


class LiveSessionResource:
    """Live sessions of the configured orbit, exposed through the tunnel."""

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def _path(self, session_id: str | None = None) -> str:
        path = (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/live-sessions"
        )
        return path if session_id is None else f"{path}/{session_id}"

    def start(self, name: str) -> LiveSessionStart:
        """
        Start a live session in the configured orbit.

        Args:
            name: Name shown for the session on the Flow page.

        Returns:
            LiveSessionStart: The session's addresses, the relay address the agent
            connects to, an `expose` token and the heartbeat interval in seconds.

        Raises:
            InternalServerError: With status 501 when live sessions are off in
            this deployment; every live session operation fails this way then.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        started = luml.live_sessions.start("training dashboard")
        started.app_url
        ```
        """
        return LiveSessionStart.model_validate(
            self._client.post(self._path(), json={"name": name})
        )

    def list(self) -> list[LiveSession]:
        """List the current user's live sessions in the configured orbit."""
        return [
            LiveSession.model_validate(session)
            for session in self._client.get(self._path())
        ]

    def get(self, session_id: str) -> LiveSession:
        """
        Read one live session.

        Raises:
            NotFoundError: If the session does not exist or was started by another
            user.
        """
        return LiveSession.model_validate(self._client.get(self._path(session_id)))

    def heartbeat(
        self, session_id: str, connected: bool, token_expires_at: datetime
    ) -> LiveSessionHeartbeat:
        """
        Report whether the agent's connection to the relay works.

        Args:
            session_id: Id of the session.
            connected: Whether the agent currently holds a working connection.
            token_expires_at: Expiry of the `expose` token the agent holds; the
                Platform renews the token when it is about to expire.

        Returns:
            LiveSessionHeartbeat: The session's status and, when due, a renewed
            `expose` token. An agent exits once the status is `ended`.
        """
        return LiveSessionHeartbeat.model_validate(
            self._client.post(
                f"{self._path(session_id)}/heartbeat",
                json={
                    "connected": connected,
                    "token_expires_at": token_expires_at.isoformat(),
                },
            )
        )

    def view_token(self, session_id: str) -> LiveSessionViewToken:
        """
        Issue a `view` token and the launch address that exchanges it for a cookie.

        Raises:
            ConflictError: If the session has ended.
        """
        return LiveSessionViewToken.model_validate(
            self._client.post(f"{self._path(session_id)}/view-token")
        )

    def end(self, session_id: str) -> LiveSession:
        """End a live session; no further tokens are issued for it."""
        return LiveSession.model_validate(
            self._client.post(f"{self._path(session_id)}/end")
        )


class AsyncLiveSessionResource:
    """Async variant of `LiveSessionResource`."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    def _path(self, session_id: str | None = None) -> str:
        path = (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/live-sessions"
        )
        return path if session_id is None else f"{path}/{session_id}"

    async def start(self, name: str) -> LiveSessionStart:
        """Async variant of `LiveSessionResource.start`."""
        return LiveSessionStart.model_validate(
            await self._client.post(self._path(), json={"name": name})
        )

    async def list(self) -> list[LiveSession]:
        """Async variant of `LiveSessionResource.list`."""
        return [
            LiveSession.model_validate(session)
            for session in await self._client.get(self._path())
        ]

    async def get(self, session_id: str) -> LiveSession:
        """Async variant of `LiveSessionResource.get`."""
        return LiveSession.model_validate(
            await self._client.get(self._path(session_id))
        )

    async def heartbeat(
        self, session_id: str, connected: bool, token_expires_at: datetime
    ) -> LiveSessionHeartbeat:
        """Async variant of `LiveSessionResource.heartbeat`."""
        return LiveSessionHeartbeat.model_validate(
            await self._client.post(
                f"{self._path(session_id)}/heartbeat",
                json={
                    "connected": connected,
                    "token_expires_at": token_expires_at.isoformat(),
                },
            )
        )

    async def view_token(self, session_id: str) -> LiveSessionViewToken:
        """Async variant of `LiveSessionResource.view_token`."""
        return LiveSessionViewToken.model_validate(
            await self._client.post(f"{self._path(session_id)}/view-token")
        )

    async def end(self, session_id: str) -> LiveSession:
        """Async variant of `LiveSessionResource.end`."""
        return LiveSession.model_validate(
            await self._client.post(f"{self._path(session_id)}/end")
        )
