import asyncio
import logging
import signal
import sys
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from luml_tunnel.agent import AgentRefusedError, LoopbackService
from luml_tunnel.cli import main
from luml_tunnel.luml import LumlSessionError, LumlTokens, expose_through_luml
from luml_tunnel.relay import Relay
from luml_tunnel.tokens import TokenKind
from tests.harness import (
    FAST_RECONNECT,
    OTHER_RELAY_ID,
    RELAY_ID,
    SESSION,
    USER,
    FakeRelayApi,
    bound_socket,
    create_relay,
    port_of,
    relay_url,
    serve,
    until,
    viewer,
)

API_KEY = "luml_test_key"
ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
PUBLIC_URL = f"http://{SESSION}.tunnel.example"
CREATED_AT = "2026-09-29T10:00:00Z"


@dataclass
class Heartbeat:
    connected: bool
    token_expires_at: datetime


@dataclass
class FakeLuml:
    """Answers the calls the agent makes, with tokens issued through the relay-facing API."""

    relay_api: FakeRelayApi
    relay_port: int
    relay_id: str = RELAY_ID
    token_lifetime: timedelta = timedelta(minutes=10)
    renewed_token_lifetime: timedelta | None = None
    start_refusal: tuple[int, str] | None = None
    unanswered_heartbeats: int = 0
    ended: bool = False
    started: list[str | None] = field(default_factory=list)
    heartbeats: list[Heartbeat] = field(default_factory=list)
    end_calls: int = 0

    @property
    def last_connected(self) -> bool | None:
        return self.heartbeats[-1].connected if self.heartbeats else None

    def app(self) -> Starlette:
        sessions = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/live-sessions"
        return Starlette(
            routes=[
                Route("/v1/users/me/organizations", self._organizations),
                Route(f"/v1/organizations/{ORGANIZATION_ID}/orbits", self._orbits),
                Route(
                    f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/collections",
                    self._collections,
                ),
                Route(sessions, self._start, methods=["POST"]),
                Route(f"{sessions}/{SESSION}/heartbeat", self._heartbeat, methods=["POST"]),
                Route(f"{sessions}/{SESSION}/end", self._end, methods=["POST"]),
            ]
        )

    def _token(self, lifetime: timedelta) -> tuple[str, datetime]:
        token = self.relay_api.issue(TokenKind.EXPOSE, lifetime=lifetime, relay=self.relay_id)
        return token, self.relay_api.tokens[token].expires_at

    @staticmethod
    def _refused(request: Request) -> JSONResponse | None:
        if request.headers.get("authorization") == f"Bearer {API_KEY}":
            return None
        return JSONResponse({"detail": "Invalid API key"}, status_code=401)

    async def _organizations(self, request: Request) -> JSONResponse:
        organization = {"id": ORGANIZATION_ID, "name": "Lab", "created_at": CREATED_AT}
        return self._refused(request) or JSONResponse([organization])

    async def _orbits(self, request: Request) -> JSONResponse:
        orbit = {
            "id": ORBIT_ID,
            "name": "Research",
            "organization_id": ORGANIZATION_ID,
            "bucket_secret_id": "secret",
            "created_at": CREATED_AT,
        }
        return self._refused(request) or JSONResponse([orbit])

    async def _collections(self, request: Request) -> JSONResponse:
        return self._refused(request) or JSONResponse({"items": [], "cursor": None})

    async def _start(self, request: Request) -> JSONResponse:
        if refused := self._refused(request):
            return refused
        if self.start_refusal is not None:
            status_code, detail = self.start_refusal
            return JSONResponse({"detail": detail}, status_code=status_code)
        self.started.append((await request.json()).get("label"))
        token, expires_at = self._token(self.token_lifetime)
        return JSONResponse(
            {
                "id": SESSION,
                "public_url": PUBLIC_URL,
                "agent_url": relay_url(self.relay_port),
                "expose_token": token,
                "token_expires_at": expires_at.isoformat(),
                "heartbeat_interval": 1,
            }
        )

    async def _heartbeat(self, request: Request) -> JSONResponse:
        if refused := self._refused(request):
            return refused
        if self.unanswered_heartbeats > 0:
            self.unanswered_heartbeats -= 1
            return JSONResponse({"detail": "unavailable"}, status_code=503)
        body = await request.json()
        self.heartbeats.append(
            Heartbeat(body["connected"], datetime.fromisoformat(body["token_expires_at"]))
        )
        if self.ended:
            return JSONResponse({"status": "ended"})
        answer: dict[str, str] = {"status": "live" if body["connected"] else "disconnected"}
        if self.renewed_token_lifetime is not None:
            token, expires_at = self._token(self.renewed_token_lifetime)
            answer |= {"expose_token": token, "token_expires_at": expires_at.isoformat()}
        return JSONResponse(answer)

    async def _end(self, request: Request) -> JSONResponse:
        if refused := self._refused(request):
            return refused
        self.end_calls += 1
        self.ended = True
        self.relay_api.ended_sessions.add(SESSION)
        session = {
            "id": SESSION,
            "orbit_id": ORBIT_ID,
            "user_id": USER,
            "label": self.started[-1],
            "visibility": "owner",
            "relay_id": self.relay_id,
            "started_at": CREATED_AT,
            "connected": False,
            "ended_at": datetime.now(UTC).isoformat(),
            "status": "ended",
        }
        return JSONResponse(session)


@pytest.fixture()
def fake_luml(luml: FakeRelayApi, relay_port: int) -> FakeLuml:
    return FakeLuml(luml, relay_port)


@pytest.fixture()
async def luml_port(fake_luml: FakeLuml, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[int]:
    sock = bound_socket()
    monkeypatch.setenv("LUML_BASE_URL", f"http://127.0.0.1:{port_of(sock)}")
    monkeypatch.setenv("LUML_API_KEY", API_KEY)
    async with serve(fake_luml.app(), sock) as port:
        yield port


@dataclass
class RunningExpose:
    task: "asyncio.Task[None]"
    stop: asyncio.Event


@asynccontextmanager
async def exposing(
    service_port: int, label: str | None = "dashboard"
) -> AsyncGenerator[RunningExpose]:
    service = LoopbackService(service_port)
    stop = asyncio.Event()
    task = asyncio.create_task(
        expose_through_luml(ORGANIZATION_ID, ORBIT_ID, label, service, stop, FAST_RECONNECT)
    )
    try:
        yield RunningExpose(task, stop)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await service.aclose()


async def _served(relay_port: int, view_token: str) -> int:
    async with viewer(relay_port, view_token) as client:
        return (await client.get("/")).status_code


@pytest.mark.usefixtures("luml_port")
async def test_expose_starts_a_session_and_becomes_live(
    fake_luml: FakeLuml,
    relay: Relay,
    relay_port: int,
    service_port: int,
    view_token: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with exposing(service_port) as running:
        await until(lambda: fake_luml.last_connected is True)

        assert fake_luml.started == ["dashboard"]
        assert relay.agents.get(SESSION) is not None
        assert f"Session {SESSION} is live at {PUBLIC_URL}" in capsys.readouterr().out
        assert await _served(relay_port, view_token) == 200
        assert not running.task.done()


@pytest.mark.usefixtures("luml_port")
async def test_expose_without_a_label_starts_an_unlabelled_session(
    fake_luml: FakeLuml, service_port: int
) -> None:
    async with exposing(service_port, label=None):
        await until(lambda: fake_luml.last_connected is True)

    assert fake_luml.started == [None]


@pytest.mark.usefixtures("luml_port")
async def test_stopping_the_agent_ends_the_session_at_luml(
    fake_luml: FakeLuml, service_port: int
) -> None:
    async with exposing(service_port) as running:
        await until(lambda: fake_luml.last_connected is True)
        running.stop.set()
        await asyncio.wait_for(running.task, 5)

    assert fake_luml.end_calls == 1


@pytest.mark.usefixtures("luml_port")
async def test_agent_exits_when_luml_reports_the_session_ended(
    fake_luml: FakeLuml, service_port: int
) -> None:
    async with exposing(service_port) as running:
        await until(lambda: fake_luml.last_connected is True)
        fake_luml.ended = True
        await asyncio.wait_for(running.task, 5)

    assert fake_luml.end_calls == 0


@pytest.mark.usefixtures("luml_port")
async def test_heartbeats_report_a_dropped_connection_until_the_agent_reconnects(
    fake_luml: FakeLuml, luml: FakeRelayApi, service_port: int
) -> None:
    relay_socket = bound_socket()
    fake_luml.relay_port = port_of(relay_socket)
    first_relay = create_relay(luml)
    async with exposing(service_port) as running:
        async with serve(first_relay, relay_socket):
            await until(lambda: fake_luml.last_connected is True)
        await until(lambda: fake_luml.last_connected is False)
        second_relay = create_relay(luml)
        async with serve(second_relay, bound_socket(fake_luml.relay_port)):
            await until(lambda: fake_luml.last_connected is True)
            assert second_relay.agents.get(SESSION) is not None
        assert not running.task.done()


async def test_tunnel_stays_open_while_luml_does_not_answer_heartbeats(
    fake_luml: FakeLuml,
    luml_port: int,
    relay_port: int,
    service_port: int,
    view_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="luml_tunnel.luml")
    async with exposing(service_port) as running:
        await until(lambda: fake_luml.last_connected is True)
        fake_luml.unanswered_heartbeats = 2
        await until(lambda: "LUML did not take a heartbeat" in caplog.text)
        assert await _served(relay_port, view_token) == 200

        answered = len(fake_luml.heartbeats)
        await until(lambda: len(fake_luml.heartbeats) > answered)
        assert fake_luml.unanswered_heartbeats == 0
        assert not running.task.done()


async def test_tunnel_stays_open_while_luml_cannot_be_reached(
    fake_luml: FakeLuml,
    relay: Relay,
    relay_port: int,
    service_port: int,
    view_token: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.WARNING, logger="luml_tunnel.luml")
    luml_socket = bound_socket()
    luml_port = port_of(luml_socket)
    monkeypatch.setenv("LUML_BASE_URL", f"http://127.0.0.1:{luml_port}")
    monkeypatch.setenv("LUML_API_KEY", API_KEY)
    first_luml = AsyncExitStack()
    await first_luml.enter_async_context(serve(fake_luml.app(), luml_socket))
    async with exposing(service_port) as running:
        async with first_luml:
            await until(lambda: fake_luml.last_connected is True)
        await until(lambda: "LUML cannot be reached for a heartbeat" in caplog.text)
        assert relay.agents.get(SESSION) is not None
        assert await _served(relay_port, view_token) == 200

        answered = len(fake_luml.heartbeats)
        async with serve(fake_luml.app(), bound_socket(luml_port)):
            await until(lambda: len(fake_luml.heartbeats) > answered)
        assert not running.task.done()


@pytest.mark.usefixtures("luml_port")
async def test_renewed_token_keeps_the_connection_open(
    fake_luml: FakeLuml, relay: Relay, service_port: int
) -> None:
    fake_luml.token_lifetime = timedelta(seconds=2)
    fake_luml.renewed_token_lifetime = timedelta(minutes=10)
    async with exposing(service_port):
        await until(lambda: relay.agents.get(SESSION) is not None)
        connection = relay.agents.get(SESSION)
        await asyncio.sleep(3)

        assert relay.agents.get(SESSION) is connection
        assert connection is not None and not connection.closed
    first_expiry = fake_luml.heartbeats[0].token_expires_at
    assert fake_luml.heartbeats[-1].token_expires_at > first_expiry + timedelta(minutes=5)


OUTAGE = 10**6


async def _expire_during_an_outage(fake_luml: FakeLuml, relay: Relay) -> None:
    """Connect with a short token, cut LUML off and wait until the relay closes at expiry."""
    fake_luml.token_lifetime = timedelta(seconds=2)
    await until(lambda: fake_luml.last_connected is True)
    fake_luml.unanswered_heartbeats = OUTAGE
    await until(lambda: relay.agents.get(SESSION) is None)
    await asyncio.sleep(1)


@pytest.mark.usefixtures("luml_port")
async def test_agent_waits_for_a_fresh_token_after_an_outage(
    fake_luml: FakeLuml,
    relay: Relay,
    relay_port: int,
    service_port: int,
    view_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    async with exposing(service_port) as running:
        await _expire_during_an_outage(fake_luml, relay)
        assert not running.task.done()
        assert "waiting for LUML to renew it" in caplog.text
        assert "Refused an agent" not in caplog.text

        fake_luml.renewed_token_lifetime = timedelta(minutes=10)
        fake_luml.unanswered_heartbeats = 0
        await until(lambda: relay.agents.get(SESSION) is not None)
        await until(lambda: fake_luml.last_connected is True)

        assert await _served(relay_port, view_token) == 200
        assert not running.task.done()
    assert "Refused an agent" not in caplog.text


@pytest.mark.usefixtures("luml_port")
async def test_agent_waiting_for_a_token_exits_when_the_session_ended(
    fake_luml: FakeLuml, relay: Relay, service_port: int
) -> None:
    async with exposing(service_port) as running:
        await _expire_during_an_outage(fake_luml, relay)
        fake_luml.ended = True
        fake_luml.unanswered_heartbeats = 0
        await asyncio.wait_for(running.task, 5)

    assert fake_luml.end_calls == 0
    assert relay.agents.get(SESSION) is None


async def test_tokens_wait_for_a_renewal_once_expired() -> None:
    tokens = LumlTokens("first", datetime.now(UTC) - timedelta(seconds=1))
    waiting = asyncio.create_task(tokens.token())
    await asyncio.sleep(0.05)
    assert not waiting.done()

    tokens.renew("second", datetime.now(UTC) + timedelta(minutes=10))

    assert await asyncio.wait_for(waiting, 1) == "second"


async def test_tokens_named_expired_by_the_relay_wait_before_their_own_expiry() -> None:
    tokens = LumlTokens("first", datetime.now(UTC) + timedelta(minutes=10))
    tokens.expired("older")
    assert await asyncio.wait_for(tokens.token(), 1) == "first"

    tokens.expired("first")
    waiting = asyncio.create_task(tokens.token())
    await asyncio.sleep(0.05)
    assert not waiting.done()

    tokens.renew("second", datetime.now(UTC) + timedelta(minutes=10))

    assert await asyncio.wait_for(waiting, 1) == "second"


@pytest.mark.usefixtures("luml_port")
async def test_missing_api_key_names_the_cause(
    fake_luml: FakeLuml, service_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LUML_API_KEY")
    async with exposing(service_port) as running:
        with pytest.raises(LumlSessionError, match="LUML_API_KEY"):
            await running.task

    assert fake_luml.started == []


@pytest.mark.usefixtures("luml_port")
async def test_refused_api_key_names_the_cause(
    fake_luml: FakeLuml, service_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LUML_API_KEY", "luml_revoked")
    async with exposing(service_port) as running:
        with pytest.raises(LumlSessionError, match="refused the API key"):
            await running.task

    assert fake_luml.started == []


@pytest.mark.usefixtures("luml_port")
async def test_orbit_without_a_relay_names_the_cause(
    fake_luml: FakeLuml, service_port: int
) -> None:
    fake_luml.start_refusal = (409, "Assign a relay to the orbit in orbit settings")
    async with exposing(service_port) as running:
        with pytest.raises(LumlSessionError, match="status 409: Assign a relay to the orbit"):
            await running.task

    assert fake_luml.started == []


@pytest.mark.usefixtures("luml_port")
async def test_agent_refused_by_the_relay_exits(fake_luml: FakeLuml, service_port: int) -> None:
    fake_luml.relay_id = OTHER_RELAY_ID
    async with exposing(service_port) as running:
        with pytest.raises(AgentRefusedError):
            await running.task


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
@pytest.mark.usefixtures("luml_port")
async def test_command_ends_the_session_on_a_signal(
    fake_luml: FakeLuml, service_port: int, stop_signal: signal.Signals
) -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "luml_tunnel.cli",
        "expose",
        str(service_port),
        "--label",
        "dashboard",
        "--organization",
        ORGANIZATION_ID,
        "--orbit",
        ORBIT_ID,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        printed = await asyncio.wait_for(process.stdout.readline(), 20)  # type: ignore[union-attr]
        await until(lambda: fake_luml.last_connected is True)
        process.send_signal(stop_signal)
        exit_code = await asyncio.wait_for(process.wait(), 10)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()

    assert printed.decode().strip() == f"Session {SESSION} is live at {PUBLIC_URL}"
    assert fake_luml.started == ["dashboard"]
    assert exit_code == 0
    assert fake_luml.end_calls == 1


@pytest.mark.parametrize(
    "arguments",
    [
        ["expose", "5000"],
        ["expose", "5000", "--label", "dashboard", "--orbit", ORBIT_ID],
        ["expose", "5000", "--relay-url", "ws://relay.example", "--label", "dashboard"],
        ["expose", "5000", "--relay-url", "ws://relay.example", "--orbit", ORBIT_ID],
    ],
)
def test_expose_needs_either_luml_or_a_relay(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(arguments) == 2
    assert "--relay-url" in capsys.readouterr().err
