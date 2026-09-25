"""The workspace daemon's web endpoint: the SPA, the tracker, the flow API.

One loopback port serves all three, because they are one product — Experiments
is the tracker this workspace already had, Workspace is the flows beside it,
and a browser that had to reach two ports to see them would be reading an
implementation detail as a choice.

The flow API here is the same `Api` the socket answers with, so the browser and
the CLI cannot disagree about what a verb does. It asks for the same token,
too: a loopback port is reachable by anything else on the machine, and this API
runs the user's code. The static files are served without one — they are the
client that is about to present it.
"""

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response

from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.stream import Frame, Streams, Subscription
from lumlflow.flow.errors import FlowError, FlowNotFound
from lumlflow.flow.store.models import OutputRecord

TOKEN_HEADER = "x-lumlflow-token"
TOKEN_PARAM = "token"

RPC_PATH = "/api/flow/rpc"
STREAM_PATH = "/api/flow/stream"
DOWNLOAD_PATH = "/api/flow/download"

UNAUTHORIZED = 401
# The close code that separates "you may not" from "the socket dropped" — the
# client's degraded states are not the same state.
WS_UNAUTHORIZED = 4401
_REFUSED = 400
_NO_METHOD = 404
_INTERNAL = 500

_DOWNLOAD_EXTENSIONS = {
    "frame": ".arrow",
    "metric": ".json",
    "eval": ".json",
    "note": ".md",
    "checkpoint": ".pkl",
    "pickle": ".pkl",
}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

logger = logging.getLogger(__name__)


def build_app(
    hub: Hub, api: Api, streams: Streams, *, token: str, static: Path | None = None
) -> FastAPI:
    """The daemon's HTTP surface: tracker routers, flow API, SPA.

    `AppService` is the tracker's own app — the one the standalone server was —
    so Experiments arrives here whole: its routers under their own `/api/…`
    prefixes, its CORS, its error handler. The flow API is added beside it, and
    only the flow API asks for the token; Experiments answers on loopback as it
    always did.

    Mount order is what keeps the SPA from swallowing the API — the static
    fallback answers everything, so it goes on last. A build that was never
    made is simply absent: the API is what a browser-less workspace needs.

    The tracker app stays a late import because `lumlflow ui --path` sets its
    process settings on the way past this module. Its handler singletons retain
    one lazy provider, so importing them neither opens nor freezes the store.
    """
    from lumlflow.server import SPAStaticFiles, get_static_dir
    from lumlflow.service import AppService

    app = AppService()
    app.include_router(_flow_router(hub, api, streams, token=token))
    directory = static if static is not None else get_static_dir()
    if (directory / "index.html").exists():
        app.mount("/", SPAStaticFiles(directory=directory, html=True), name="spa")
    return app


def _flow_router(hub: Hub, api: Api, streams: Streams, *, token: str) -> APIRouter:
    router = APIRouter()

    @router.post(RPC_PATH)
    async def rpc(request: Request) -> JSONResponse:
        """One door, the same one the socket knocks on."""
        if not _authorized(request, token):
            return _unauthorized()
        message = await _message(request)
        if message is None:
            return _failed("unreadable message", status=_REFUSED)
        method_name = str(message.get("method"))
        if method_name == "asset.download":
            failure = FlowError("`asset.download` is available only over the socket")
            return _failed(str(failure), status=_REFUSED, kind=type(failure).__name__)
        method = api.methods.get(method_name)
        if method is None:
            return _failed(f"no method `{message.get('method')}`", status=_NO_METHOD)
        try:
            result = await method(dict(message.get("params") or {}))
        except FlowError as failure:
            # A refusal the runtime named crosses as itself, so the browser's
            # client can rebuild it the way the CLI does.
            return _failed(str(failure), status=_REFUSED, kind=type(failure).__name__)
        except asyncio.CancelledError:
            raise
        except Exception as failure:
            logger.exception("HTTP RPC `%s` failed", method_name)
            return _failed(str(failure), status=_INTERNAL)
        return JSONResponse({"result": result})

    @router.get(DOWNLOAD_PATH)
    async def download(request: Request) -> Response:
        if not _authorized(request, token):
            return _unauthorized()
        flow = str(request.query_params.get("flow") or "")
        if not Path(flow).is_absolute():
            return _failed(
                "downloads address a flow by its absolute path, not a bare name",
                status=_REFUSED,
                kind="FlowError",
            )
        params = {
            "flow": flow,
            "branch": request.query_params.get("branch"),
            "target": request.query_params.get("target"),
        }
        try:
            session, _, slug, output, record = await api.stored_output(params)
            if record.kind == "experiment":
                raise FlowError(
                    f"`{slug}.{output}` is an experiment output and is not downloadable"
                )
            value_ref = record.value_ref
            assert value_ref is not None
            path = session.store.values.path(value_ref)
            filename = _download_name(slug, output, record, path)
        except FlowError as failure:
            return _failed(str(failure), status=_NO_METHOD, kind=type(failure).__name__)
        except asyncio.CancelledError:
            raise
        except Exception as failure:
            logger.exception("HTTP download failed")
            return _failed(str(failure), status=_INTERNAL)
        return FileResponse(path, filename=filename)

    @router.websocket(STREAM_PATH)
    async def stream(socket: WebSocket) -> None:
        """Both channels, one connection, one frame order.

        Two halves, and either one ending ends the other: a tab that goes away
        without a word leaves the writer waiting on a queue rather than on the
        socket, and nothing would wake it until the next frame — which for a
        quiet flow is never.
        """
        # Accepted before it is refused: a close sent ahead of the accept is a
        # handshake rejection, and a browser reads that as 1006 — the same
        # thing a dropped socket looks like, which is the one distinction this
        # code exists to draw.
        await socket.accept()
        if not _authorized(socket, token):
            await socket.close(code=WS_UNAUTHORIZED)
            return
        subscription = streams.subscribe()
        halves = {
            asyncio.create_task(_read(socket, hub, api, streams, subscription)),
            asyncio.create_task(_write(socket, subscription)),
        }
        for half in halves:
            half.add_done_callback(_reported)
        try:
            await asyncio.wait(halves, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # Nothing is awaited here. A shutdown cancels this handler, and an
            # await under a cancellation resumes as `CancelledError` — so a
            # teardown that awaited would run only for the connections that
            # ended politely, leaving the rest registered as queues the daemon
            # fans out to for the rest of its life.
            subscription.close()
            for half in halves:
                half.cancel()

    return router


def _reported(half: "asyncio.Task[None]") -> None:
    """A connection that died of something unforeseen still says so in the
    daemon's log: to the tab it looks like any other drop."""
    if half.cancelled():
        return
    failure = half.exception()
    if failure is not None:
        logger.error(
            "web stream failed",
            exc_info=(type(failure), failure, failure.__traceback__),
        )


async def _write(socket: WebSocket, subscription: Subscription) -> None:
    """Frames only ever leave from here.

    The reader hands its catch-up to the same subscription the live frames
    arrive on, and a catch-up is drained before them — so a replay can neither
    be interleaved with what came after it nor overtaken by it.
    """
    with contextlib.suppress(WebSocketDisconnect, RuntimeError):
        while True:
            await socket.send_json(await subscription.next())


async def _read(
    socket: WebSocket,
    hub: Hub,
    api: Api,
    streams: Streams,
    subscription: Subscription,
) -> None:
    """What the client asks to watch, and the catch-up each ask deserves."""
    while True:
        try:
            message = json.loads(await socket.receive_text())
        except (WebSocketDisconnect, RuntimeError, ValueError, UnicodeDecodeError):
            return
        if not isinstance(message, dict):
            continue
        try:
            subscription.replay(_subscribed(hub, api, streams, subscription, message))
        except FlowError as failure:
            # Naming a flow that is not here is the client's mistake to fix,
            # not this connection's death: everything else it watches stands.
            subscription.offer({"type": "error", "message": str(failure)})


def _subscribed(
    hub: Hub,
    api: Api,
    streams: Streams,
    subscription: Subscription,
    message: dict[str, Any],
) -> list[Frame]:
    """Attach a channel and answer with what the client missed on it.

    Nothing awaits between attaching and reading, which is what makes the
    catch-up whole: no transaction can land in the gap, and none is delivered
    twice. Every frame carries its `step` regardless, so a client holding a
    cursor is never obliged to trust that.
    """
    channel = str(message.get("subscribe") or "")
    if channel not in ("journal", "logs"):
        return []
    named = str(message["flow"]) if message.get("flow") else None
    try:
        session = hub.session(named)
    except FlowNotFound:
        session = hub.open(api.resolve(named))
    flow = session.ref.address
    if channel == "logs":
        run_id = str(message.get("run_id") or "")
        subscription.runs.add((flow, run_id))
        return streams.tail(flow, run_id)
    session.experiment_states.clear()
    subscription.journals.add(flow)
    caught_up: Frame = {
        "channel": "journal",
        "type": "caught_up",
        "flow": flow,
        "step": session.store.next_step - 1,
        # A run's lifecycle is not journaled, so no cursor reaches it. A tab
        # opened halfway through one learns here which console it can still
        # ask for — without this the ring buffer holds a tail nobody can name.
        "running": streams.running(flow),
    }
    return [
        *(
            streams.journal_frame(flow, entry)
            for entry in session.store.journal.since(_cursor(message.get("cursor")))
        ),
        caught_up,
    ]


def _cursor(value: Any) -> int:
    """Where a client says it got to. A cursor it garbled reads as none.

    Answering from the start over-delivers, which every frame's `step` makes
    harmless — and is the catch-up such a client needs anyway. Raising here
    would take down the whole connection, including the flows it watches
    correctly.
    """
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


async def _message(request: Request) -> dict[str, Any] | None:
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _authorized(request: Request | WebSocket, token: str) -> bool:
    """The daemon's token, in a header or — for a WebSocket, which the browser
    opens with no headers of its own — in the query string."""
    header = request.headers.get(TOKEN_HEADER)
    return token in (header, request.query_params.get(TOKEN_PARAM))


def _unauthorized() -> JSONResponse:
    return _failed(
        "this workspace's key is required. open the address `lumlflow ui` prints",
        status=UNAUTHORIZED,
    )


def _failed(message: str, *, status: int, kind: str | None = None) -> JSONResponse:
    error: dict[str, Any] = {"message": message}
    if kind is not None:
        error["kind"] = kind
    return JSONResponse({"error": error}, status_code=status)


def _download_name(slug: str, output: str, record: OutputRecord, path: Path) -> str:
    if record.kind == "file":
        original = Path(record.filename or "").name
        return original if original not in ("", ".", "..") else f"{slug}.{output}"
    extension = _DOWNLOAD_EXTENSIONS.get(record.kind, "")
    if record.kind == "plot":
        with path.open("rb") as stored:
            is_png = stored.read(len(_PNG_SIGNATURE)) == _PNG_SIGNATURE
        extension = ".png" if is_png else ".json"
    return f"{slug}.{output}{extension}"
