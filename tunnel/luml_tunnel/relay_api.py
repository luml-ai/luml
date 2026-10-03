"""Client of LUML's relay-facing API, authenticated with the relay's own token."""

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.luml.ai"
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_REQUESTS_IN_FLIGHT = 32
REPORT_INTERVAL_SECONDS = 60.0

_PREFIX = "/relays/v1"
_ORIGIN = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?")
_APP_URL = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[^\s\"'<>]*)?")


class LumlUnavailableError(Exception):
    """LUML gave no answer: it is unreachable, too slow, failing or answered nonsense."""


class RelayTokenRefusedError(LumlUnavailableError):
    """LUML refused the relay's own token."""


@dataclass(frozen=True)
class RelayDescription:
    relay_id: str
    label: str
    base_domain: str
    agent_url: str
    app_origins: tuple[str, ...]
    app_url: str


@dataclass(frozen=True)
class ActiveToken:
    kind: str
    session: str
    user: str
    expires_at: datetime
    grant: str | None = None
    destination: str | None = None


@dataclass(frozen=True)
class ActiveGrant:
    session: str
    user: str
    expires_at: datetime


class RelayApi:
    def __init__(
        self,
        base_url: str,
        relay_token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        max_in_flight: int = MAX_REQUESTS_IN_FLIGHT,
    ) -> None:
        self._timeout = timeout
        self._slots = asyncio.Semaphore(max_in_flight)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + _PREFIX,
            headers={"authorization": f"Bearer {relay_token}"},
            transport=transport,
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def describe(self) -> RelayDescription:
        answer = await self._request("GET", "/self")
        try:
            app_url = str(answer["app_url"])
            return RelayDescription(
                relay_id=str(answer["id"]),
                label=str(answer["label"]),
                base_domain=str(answer["base_domain"]).lower(),
                agent_url=str(answer["agent_url"]),
                # They end up in response headers and pages, so only plain origins pass.
                app_origins=tuple(
                    origin for origin in answer["app_origins"] if _ORIGIN.fullmatch(str(origin))
                ),
                # It becomes a link on the relay's pages, so only a web address passes.
                app_url=app_url if _APP_URL.fullmatch(app_url) else "",
            )
        except (KeyError, TypeError) as error:
            raise LumlUnavailableError(f"LUML described the relay unreadably: {error!r}") from error

    async def validate(self, token: str, launch: bool = False) -> ActiveToken | None:
        """The token's own claims while it is active for this relay, otherwise None.

        A launch consumes a `view` token at LUML and answers the grant it became.
        """
        answer = await self._request("POST", "/tokens/validate", {"token": token, "launch": launch})
        if answer.get("active") is not True:
            return None
        try:
            grant, destination = answer.get("grant_id"), answer.get("destination")
            if launch and grant is None:
                raise KeyError("grant_id")
            return ActiveToken(
                kind=str(answer["kind"]),
                session=str(answer["session_id"]),
                user=str(answer["user_id"]),
                expires_at=_aware(datetime.fromisoformat(answer["expires_at"])),
                grant=None if grant is None else str(grant),
                destination=None if destination is None else str(destination),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise LumlUnavailableError(
                f"LUML answered a validation unreadably: {error!r}"
            ) from error

    async def check_grant(self, grant: str) -> ActiveGrant | None:
        """The grant's claims while it is active for this relay, otherwise None."""
        answer = await self._request("POST", "/grants/check", {"grant_id": grant})
        if answer.get("active") is not True:
            return None
        try:
            return ActiveGrant(
                session=str(answer["session_id"]),
                user=str(answer["user_id"]),
                expires_at=_aware(datetime.fromisoformat(answer["expires_at"])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise LumlUnavailableError(
                f"LUML answered a grant check unreadably: {error!r}"
            ) from error

    async def report(self, connected_agents: int) -> None:
        await self._send("POST", "/report", {"connected_agents": connected_agents})

    async def _send(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> httpx.Response:
        try:
            # httpx bounds each phase of a request; this bounds the whole of it, including
            # the wait for a slot, so a request that cannot get one in time fails too.
            async with asyncio.timeout(self._timeout), self._slots:
                response = await self._client.request(method, path, json=body)
        except (httpx.HTTPError, TimeoutError) as error:
            raise LumlUnavailableError(f"LUML cannot be reached: {error!r}") from error
        if response.status_code in (401, 403):
            raise RelayTokenRefusedError(f"LUML answered {response.status_code}")
        if not response.is_success:
            raise LumlUnavailableError(f"LUML answered {response.status_code}")
        return response

    async def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._send(method, path, body)
        try:
            answer = response.json()
        except ValueError as error:
            raise LumlUnavailableError("LUML answered something that is not JSON") from error
        if not isinstance(answer, dict):
            raise LumlUnavailableError("LUML answered something that is not an object")
        return answer


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
