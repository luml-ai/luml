import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from luml_prisma.schemas import (
    RunEdgeOut,
    RunNodeOut,
    RunOut,
)

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/runs/{run_id}")
async def ws_run_events(  # noqa: C901
    websocket: WebSocket, run_id: str,
) -> None:
    db = websocket.app.state.db
    engine = websocket.app.state.engine
    pty = websocket.app.state.pty

    if not (run := db.get_run(run_id)):
        await websocket.close(
            code=4004, reason="Run not found",
        )
        return

    await websocket.accept()

    nodes = db.list_run_nodes(run_id)
    edges = db.list_run_edges(run_id)

    node_dicts = []
    for n in nodes:
        sessions = db.get_node_sessions(n.id)
        active_sid = None
        for s in sessions:
            if pty.is_alive(s.session_id):
                active_sid = s.session_id
                break
        node_dicts.append(
            RunNodeOut.from_db(n, active_sid).model_dump()
        )

    snapshot: dict[str, Any] = {
        "type": "snapshot",
        "data": {
            "run": RunOut.from_db(run).model_dump(),
            "nodes": node_dicts,
            "edges": [
                RunEdgeOut.model_validate(
                    e, from_attributes=True,
                ).model_dump()
                for e in edges
            ],
        },
    }
    await websocket.send_text(json.dumps(snapshot))

    queue = engine.subscribe(run_id)

    async def _send_events() -> None:
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                await websocket.send_text(
                    json.dumps(
                        {"type": "event", "data": event}
                    )
                )
        except (WebSocketDisconnect, RuntimeError):
            pass

    send_task = asyncio.create_task(_send_events())

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await send_task
        engine.unsubscribe(run_id, queue)


@router.websocket("/ws/terminal/{session_id}")
async def ws_terminal(  # noqa: C901
    websocket: WebSocket, session_id: str,
) -> None:
    pty = websocket.app.state.pty

    if not pty.has_session(session_id):
        await websocket.close(
            code=4004, reason="No PTY session",
        )
        return

    await websocket.accept()

    scrollback = pty.get_scrollback(session_id)
    if scrollback:
        await websocket.send_bytes(scrollback)

    queue = pty.subscribe(session_id)

    async def _send_output() -> None:
        try:
            while True:
                data = await queue.get()
                if data is None:
                    exit_code = pty.get_exit_code(
                        session_id,
                    )
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "exit",
                                "code": exit_code or 0,
                            }
                        )
                    )
                    break
                if isinstance(data, str):
                    await websocket.send_text(data)
                else:
                    await websocket.send_bytes(data)
        except (WebSocketDisconnect, RuntimeError):
            pass

    send_task = asyncio.create_task(_send_output())

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.receive":
                if "bytes" in msg and msg["bytes"]:
                    pty.write(
                        session_id, msg["bytes"],
                    )
                elif "text" in msg and msg["text"]:
                    try:
                        payload = json.loads(msg["text"])
                        if (
                            payload.get("type")
                            == "resize"
                        ):
                            pty.resize(
                                session_id,
                                payload.get("cols", 120),
                                payload.get("rows", 40),
                            )
                    except (
                        json.JSONDecodeError,
                        KeyError,
                    ):
                        pass
            elif (
                msg["type"] == "websocket.disconnect"
            ):
                break
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await send_task
        pty.unsubscribe(session_id, queue)
