import asyncio
import json
import time

import pytest

from luml_agent.pty_manager import PtyManager, _has_printable_content


@pytest.fixture
def pty_manager() -> PtyManager:
    mgr = PtyManager()
    yield mgr
    mgr.shutdown()


@pytest.mark.asyncio
async def test_spawn_and_read(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn(
        "t1", ["bash", "-c", "sleep 0.2 && echo hello world"], cwd="/tmp",
    )
    queue = pty_manager.subscribe(session.session_id)

    output = b""
    try:
        while True:
            data = await asyncio.wait_for(queue.get(), timeout=5)
            if data is None:
                break
            output += data
    except TimeoutError:
        pass

    assert b"hello world" in output


@pytest.mark.asyncio
async def test_scrollback(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["echo", "scrollback test"], cwd="/tmp")
    await asyncio.sleep(0.5)
    scrollback = pty_manager.get_scrollback(session.session_id)
    assert b"scrollback test" in scrollback


@pytest.mark.asyncio
async def test_write_to_pty(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn(
        "t1", ["bash", "-c", "read line && echo got:$line"],
        cwd="/tmp",
    )
    await asyncio.sleep(0.3)
    queue = pty_manager.subscribe(session.session_id)

    pty_manager.write(session.session_id, b"typed input\n")

    output = b""
    try:
        while True:
            data = await asyncio.wait_for(queue.get(), timeout=3)
            if data is None:
                break
            output += data
    except TimeoutError:
        pass

    assert b"typed input" in output


@pytest.mark.asyncio
async def test_terminate(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp")
    assert pty_manager.is_alive(session.session_id)
    pty_manager.terminate(session.session_id)
    assert not pty_manager.is_alive(session.session_id)


@pytest.mark.asyncio
async def test_cleanup_dead(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["true"], cwd="/tmp")
    await asyncio.sleep(0.5)
    dead = pty_manager.cleanup_dead()
    assert any(sid == session.session_id for sid, _, _, _ in dead)
    assert not pty_manager.has_session(session.session_id)


@pytest.mark.asyncio
async def test_resize(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    pty_manager.resize(session.session_id, 200, 50)
    assert session.cols == 200
    assert session.rows == 50
    pty_manager.terminate(session.session_id)


@pytest.mark.asyncio
async def test_subscribe_unsubscribe(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    queue = pty_manager.subscribe(session.session_id)
    assert queue in pty_manager._sessions[session.session_id].subscribers
    pty_manager.unsubscribe(session.session_id, queue)
    assert queue not in pty_manager._sessions[session.session_id].subscribers
    pty_manager.terminate(session.session_id)


def test_get_scrollback_missing_session(pty_manager: PtyManager) -> None:
    assert pty_manager.get_scrollback("nonexistent") == b""


def test_is_alive_missing_session(pty_manager: PtyManager) -> None:
    assert not pty_manager.is_alive("nonexistent")


def test_has_session(pty_manager: PtyManager) -> None:
    assert not pty_manager.has_session("nonexistent")
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    assert pty_manager.has_session(session.session_id)
    pty_manager.terminate(session.session_id)
    assert not pty_manager.has_session(session.session_id)


def test_session_id_is_unique(pty_manager: PtyManager) -> None:
    s1 = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    s2 = pty_manager.spawn("t2", ["sleep", "5"], cwd="/tmp")
    assert s1.session_id != s2.session_id
    pty_manager.terminate(s1.session_id)
    pty_manager.terminate(s2.session_id)


def test_session_type_default(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    assert session.session_type == "agent"
    assert pty_manager.get_session_type(session.session_id) == "agent"
    pty_manager.terminate(session.session_id)


def test_session_type_shell(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp", session_type="shell")
    assert session.session_type == "shell"
    assert pty_manager.get_session_type(session.session_id) == "shell"
    pty_manager.terminate(session.session_id)


def test_get_session_type_missing(pty_manager: PtyManager) -> None:
    assert pty_manager.get_session_type("nonexistent") is None


@pytest.mark.asyncio
async def test_cleanup_dead_returns_session_type(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["true"], cwd="/tmp", session_type="shell")
    await asyncio.sleep(0.5)
    dead = pty_manager.cleanup_dead()
    assert any(
        sid == session.session_id and stype == "shell"
        for sid, _, stype, _ in dead
    )


def test_is_task_alive(pty_manager: PtyManager) -> None:
    assert not pty_manager.is_task_alive("t1")
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    assert pty_manager.is_task_alive("t1")
    pty_manager.terminate(session.session_id)
    assert not pty_manager.is_task_alive("t1")


def test_get_active_session_id(pty_manager: PtyManager) -> None:
    assert pty_manager.get_active_session_id("t1") is None
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    assert pty_manager.get_active_session_id("t1") == session.session_id
    pty_manager.terminate(session.session_id)
    assert pty_manager.get_active_session_id("t1") is None


def test_terminate_task(pty_manager: PtyManager) -> None:
    s1 = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp", session_type="agent")
    s2 = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp", session_type="shell")
    assert pty_manager.is_task_alive("t1")
    pty_manager.terminate_task("t1")
    assert not pty_manager.has_session(s1.session_id)
    assert not pty_manager.has_session(s2.session_id)


def test_idle_tracking_defaults(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "5"], cwd="/tmp")
    assert isinstance(session.last_output_time, float)
    assert session.last_output_time > 0
    assert session.waiting_notified is False
    pty_manager.terminate(session.session_id)


@pytest.mark.asyncio
async def test_check_idle_sends_notification(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp")
    queue = pty_manager.subscribe(session.session_id)

    session.last_output_time = time.monotonic() - 10.0

    pty_manager.check_idle_sessions(threshold=5.0)

    data = await asyncio.wait_for(queue.get(), timeout=2)
    assert isinstance(data, str)
    msg = json.loads(data)
    assert msg["type"] == "waiting_for_input"
    assert session.waiting_notified is True
    pty_manager.terminate(session.session_id)


@pytest.mark.asyncio
async def test_check_idle_notifies_only_once(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp")
    queue = pty_manager.subscribe(session.session_id)

    session.last_output_time = time.monotonic() - 10.0

    pty_manager.check_idle_sessions(threshold=5.0)
    pty_manager.check_idle_sessions(threshold=5.0)

    data = await asyncio.wait_for(queue.get(), timeout=2)
    assert isinstance(data, str)

    assert queue.empty()
    pty_manager.terminate(session.session_id)


@pytest.mark.asyncio
async def test_check_idle_cooldown_prevents_repeat(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp")
    queue = pty_manager.subscribe(session.session_id)

    session.last_output_time = time.monotonic() - 10.0
    pty_manager.check_idle_sessions(threshold=5.0, cooldown=30.0)

    data = await asyncio.wait_for(queue.get(), timeout=2)
    assert isinstance(data, str)

    session.waiting_notified = False
    session.last_output_time = time.monotonic() - 10.0
    pty_manager.check_idle_sessions(threshold=5.0, cooldown=30.0)

    assert queue.empty()
    pty_manager.terminate(session.session_id)


@pytest.mark.asyncio
async def test_check_idle_cooldown_expired_allows_repeat(
    pty_manager: PtyManager,
) -> None:
    session = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp")
    queue = pty_manager.subscribe(session.session_id)

    session.last_output_time = time.monotonic() - 10.0
    pty_manager.check_idle_sessions(threshold=5.0, cooldown=1.0)

    data = await asyncio.wait_for(queue.get(), timeout=2)
    assert isinstance(data, str)

    session.waiting_notified = False
    session.last_output_time = time.monotonic() - 10.0
    session.last_notified_time = time.monotonic() - 2.0
    pty_manager.check_idle_sessions(threshold=5.0, cooldown=1.0)

    data = await asyncio.wait_for(queue.get(), timeout=2)
    assert isinstance(data, str)
    assert json.loads(data)["type"] == "waiting_for_input"
    pty_manager.terminate(session.session_id)


@pytest.mark.asyncio
async def test_idle_resets_on_output(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn(
        "t1", ["bash", "-c", "sleep 0.3 && echo output"], cwd="/tmp",
    )
    queue = pty_manager.subscribe(session.session_id)

    session.last_output_time = time.monotonic() - 10.0
    session.waiting_notified = True

    output = b""
    try:
        while True:
            data = await asyncio.wait_for(queue.get(), timeout=3)
            if data is None:
                break
            if isinstance(data, bytes):
                output += data
    except TimeoutError:
        pass

    assert b"output" in output
    assert session.waiting_notified is False
    assert session.last_output_time > time.monotonic() - 2.0


def test_check_idle_ignores_shell(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn(
        "t1", ["sleep", "60"], cwd="/tmp", session_type="shell",
    )
    queue = pty_manager.subscribe(session.session_id)

    session.last_output_time = time.monotonic() - 10.0

    pty_manager.check_idle_sessions(threshold=5.0)

    assert queue.empty()
    assert session.waiting_notified is False
    pty_manager.terminate(session.session_id)


@pytest.mark.asyncio
async def test_check_idle_ignores_dead(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["true"], cwd="/tmp")
    await asyncio.sleep(0.5)
    queue = pty_manager.subscribe(session.session_id)

    session.last_output_time = time.monotonic() - 10.0

    pty_manager.check_idle_sessions(threshold=5.0)

    # Drain any pre-existing messages (output from "true" command)
    idle_msgs = []
    while not queue.empty():
        data = queue.get_nowait()
        if isinstance(data, str):
            idle_msgs.append(data)

    assert not any(
        json.loads(m).get("type") == "waiting_for_input" for m in idle_msgs
    )


def test_has_printable_content_with_text() -> None:
    assert _has_printable_content(b"hello world")
    assert _has_printable_content(b"a")
    assert _has_printable_content(b"\x1b[32mgreen\x1b[0m")


def test_has_printable_content_escape_only() -> None:
    assert not _has_printable_content(b"\x1b[H")
    assert not _has_printable_content(b"\x1b[2J")
    assert not _has_printable_content(b"\x1b[?25h")
    assert not _has_printable_content(b"\x1b[1;1H\x1b[2J")
    assert not _has_printable_content(b"\r\n")
    assert not _has_printable_content(b"\x07")


def test_has_printable_content_mixed() -> None:
    assert _has_printable_content(b"\x1b[H\x1b[2Jhello")
    assert not _has_printable_content(b"\x1b[H\x1b[2J\r\n")


def test_get_agent_session_ids(pty_manager: PtyManager) -> None:
    s1 = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp", session_type="agent")
    s2 = pty_manager.spawn("t2", ["sleep", "60"], cwd="/tmp", session_type="shell")
    ids = pty_manager.get_agent_session_ids()
    assert s1.session_id in ids
    assert s2.session_id not in ids
    pty_manager.terminate(s1.session_id)
    pty_manager.terminate(s2.session_id)


def test_get_agent_session_ids_excludes_dead(pty_manager: PtyManager) -> None:
    s1 = pty_manager.spawn("t1", ["true"], cwd="/tmp", session_type="agent")
    s1.process.wait()
    ids = pty_manager.get_agent_session_ids()
    assert s1.session_id not in ids


def test_is_session_waiting_notified(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp")
    assert not pty_manager.is_session_waiting_notified(session.session_id)
    session.waiting_notified = True
    assert pty_manager.is_session_waiting_notified(session.session_id)
    assert not pty_manager.is_session_waiting_notified("nonexistent")
    pty_manager.terminate(session.session_id)


def test_get_idle_duration(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp")
    session.last_output_time = time.monotonic() - 5.0
    duration = pty_manager.get_idle_duration(session.session_id)
    assert duration is not None
    assert duration >= 4.5
    assert pty_manager.get_idle_duration("nonexistent") is None
    pty_manager.terminate(session.session_id)


def test_get_idle_duration_dead_session(pty_manager: PtyManager) -> None:
    session = pty_manager.spawn("t1", ["true"], cwd="/tmp")
    session.process.wait()
    assert pty_manager.get_idle_duration(session.session_id) is None


def test_get_idle_agent_sessions(pty_manager: PtyManager) -> None:
    s1 = pty_manager.spawn("t1", ["sleep", "60"], cwd="/tmp", session_type="agent")
    s2 = pty_manager.spawn("t2", ["sleep", "60"], cwd="/tmp", session_type="agent")
    s3 = pty_manager.spawn("t3", ["sleep", "60"], cwd="/tmp", session_type="shell")
    s1.last_output_time = time.monotonic() - 10.0
    s2.last_output_time = time.monotonic()
    s3.last_output_time = time.monotonic() - 10.0
    idle = pty_manager.get_idle_agent_sessions(threshold=5.0)
    assert s1.session_id in idle
    assert s2.session_id not in idle
    assert s3.session_id not in idle
    pty_manager.terminate(s1.session_id)
    pty_manager.terminate(s2.session_id)
    pty_manager.terminate(s3.session_id)
