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
        params = dict(message.get("params") or {})
        if method_name == "agent.begin":
            params.pop("lease", None)
        try:
            result = await method(params)
        except FlowError as failure:
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
    session.touch()
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
        "running": streams.running(flow),
        "activity": streams.activities(flow),
        "claims": streams.claimed(flow),
        "claim_idle_s": streams.claim_idle_s,
    }
    return [
        *(
            streams.journal_frame(flow, entry)
            for entry in session.store.journal.since(_cursor(message.get("cursor")))
        ),
        caught_up,
    ]


def _cursor(value: Any) -> int:
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
