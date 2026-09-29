"""Registration of an agent's session with LUML; needs the luml extra."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable
from datetime import datetime

import httpx
from luml_api import APIStatusError, AsyncLumlClient, LumlAPIError
from luml_api._exceptions import ResourceNotFoundError
from luml_api._types import LiveSessionStart, LiveSessionStatus

from luml_tunnel.agent import Agent, LocalService, ReconnectPolicy

logger = logging.getLogger(__name__)

API_KEY_ENV = "LUML_API_KEY"

_NOT_SET_UP_STATUS = 501


class LumlSessionError(Exception):
    """LUML cannot be used for the session; the message names the cause."""


class LumlTokens:
    """The session's current `expose` token, renewed through heartbeats."""

    def __init__(self, token: str, expires_at: datetime) -> None:
        self._token = token
        self.expires_at = expires_at

    async def token(self) -> str:
        return self._token

    def renew(self, token: str, expires_at: datetime) -> None:
        self._token = token
        self.expires_at = expires_at


async def expose_through_luml(
    name: str,
    organization: str,
    orbit: str,
    service: LocalService,
    stop: asyncio.Event,
    reconnect: ReconnectPolicy | None = None,
) -> None:
    """Start a session at LUML and serve it until `stop` is set or LUML ends it.

    The API key and the address of LUML come from the environment variables the API
    client reads. Setting `stop` ends the session at LUML. Raises LumlSessionError when
    LUML cannot be used, and AgentRefusedError when the relay refuses the agent.
    """
    client = await _configured_client(organization, orbit)
    started = await _call_luml("start the session", client.live_sessions.start(name))
    print(f"Session {name!r} is live at {started.app_url}", flush=True)
    tokens = LumlTokens(started.expose_token, started.token_expires_at)
    agent = Agent(started.agent_url, tokens, service, reconnect)
    serving = asyncio.create_task(agent.run())
    heartbeats = asyncio.create_task(_send_heartbeats(client, started, agent, tokens))
    stopping = asyncio.create_task(stop.wait())
    tasks = (serving, heartbeats, stopping)
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    if stopping in done:
        await _end(client, started.id)
        return
    for finished in (serving, heartbeats):
        if finished in done:
            finished.result()


async def _configured_client(organization: str, orbit: str) -> AsyncLumlClient:
    try:
        client = AsyncLumlClient()
    except LumlAPIError as error:
        raise LumlSessionError(f"Set {API_KEY_ENV} to an API key of LUML") from error
    try:
        await _call_luml(
            "read the organization and the orbit",
            client.setup_config(organization=organization, orbit=orbit),
        )
    except ResourceNotFoundError as error:
        raise LumlSessionError(error.message) from error
    return client


async def _call_luml[T](action: str, call: Awaitable[T]) -> T:
    try:
        return await call
    except httpx.RequestError as error:
        raise LumlSessionError(
            f"LUML cannot be reached at {error.request.url}: {error!r}"
        ) from error
    except APIStatusError as error:
        raise LumlSessionError(_refusal(action, error)) from error


def _refusal(action: str, error: APIStatusError) -> str:
    if error.status_code == 401:
        return f"LUML refused the API key in {API_KEY_ENV}"
    if error.status_code == _NOT_SET_UP_STATUS:
        return "Live sessions are not set up in this LUML deployment"
    detail = error.body.get("detail") if isinstance(error.body, dict) else error.body
    return f"LUML refused to {action} with status {error.status_code}: {detail}"


def _worth_retrying(error: APIStatusError) -> bool:
    return error.status_code >= 500 or error.status_code == 429


async def _send_heartbeats(
    client: AsyncLumlClient, started: LiveSessionStart, agent: Agent, tokens: LumlTokens
) -> None:
    """Report the connection to LUML until LUML reports the session as ended.

    A heartbeat that LUML does not answer is sent again at the next interval; the
    tunnel stays open meanwhile. The first heartbeat goes out once the agent connects.
    """
    interval = started.heartbeat_interval
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(interval):
            await agent.wait_connected()
    while True:
        try:
            answer = await client.live_sessions.heartbeat(
                started.id, agent.connected, tokens.expires_at
            )
        except httpx.RequestError as error:
            logger.warning("LUML cannot be reached for a heartbeat, trying again: %r", error)
        except APIStatusError as error:
            if not _worth_retrying(error):
                raise LumlSessionError(_refusal("take a heartbeat", error)) from error
            logger.warning("LUML did not take a heartbeat, trying again: %s", error.status_code)
        else:
            if answer.status == LiveSessionStatus.ENDED:
                logger.info("The session was ended at LUML")
                return
            if answer.expose_token is not None and answer.token_expires_at is not None:
                tokens.renew(answer.expose_token, answer.token_expires_at)
                await agent.renew_token(answer.expose_token)
        await asyncio.sleep(interval)


async def _end(client: AsyncLumlClient, session_id: str) -> None:
    try:
        await client.live_sessions.end(session_id)
    except (httpx.RequestError, APIStatusError) as error:
        logger.warning("Could not end the session at LUML: %r", error)
        return
    logger.info("Ended the session at LUML")
