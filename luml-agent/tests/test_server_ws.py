import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient, WebSocketDisconnect

from luml_agent.config import AppConfig
from luml_agent.database import Database
from luml_agent.services.pty_manager import PtyManager
from luml_agent.server import app


@pytest.fixture
def db() -> Database:
    return Database()


@pytest.fixture
def pty() -> PtyManager:
    mgr = PtyManager()
    yield mgr
    mgr.shutdown()


@pytest.fixture
def setup_server(
    tmp_path: Path, db: Database, pty: PtyManager,
) -> None:
    app.state.config = AppConfig(
        data_dir=tmp_path,
        db_path=tmp_path / "test.db",
    )
    app.state.db = db
    app.state.pty = pty
    return


def test_ws_missing_session_rejected(
    setup_server: None,
) -> None:
    client = TestClient(app)
    with pytest.raises(
        WebSocketDisconnect,
    ), client.websocket_connect(
        "/ws/terminal/nonexistent",
    ):
        pass


def test_ws_resize_message(
    setup_server: None, pty: PtyManager,
) -> None:
    import time

    session = pty.spawn(
        "t1", ["sleep", "10"], cwd="/tmp",
    )
    time.sleep(0.3)

    client = TestClient(app)
    with client.websocket_connect(
        f"/ws/terminal/{session.session_id}",
    ) as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "resize",
                    "cols": 200,
                    "rows": 50,
                },
            )
        )
        time.sleep(0.3)
        assert session.cols == 200
        assert session.rows == 50
