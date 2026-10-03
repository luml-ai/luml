"""Expose a lumlflow on an orbit's Flow page from Python; needs the `flow` extra."""

import asyncio
import atexit
import logging
import os
import shutil
import signal
import socket
import subprocess
import threading
import time
from collections.abc import Callable, Coroutine
from types import FrameType
from typing import Any, Self

try:
    import httpx
    from luml_api import APIStatusError, AsyncLumlClient, LumlClient, NotFoundError
    from luml_api._types import LiveSessionStart
    from luml_tunnel.agent import LoopbackService
    from luml_tunnel.luml import serve_session
except ModuleNotFoundError as error:
    raise ImportError(
        f"{error.name} is missing; install luml_sdk[flow] to use luml.flow"
    ) from error

logger = logging.getLogger(__name__)

STATUS_PATH = "/api/auth/status"
LUMLFLOW_START_TIMEOUT = 30.0
LUMLFLOW_STOP_TIMEOUT = 10.0
CONNECT_TIMEOUT = 15.0

_SignalHandler = Callable[[int, FrameType | None], Any] | int | None


class LiveFlowError(Exception):
    """A LiveFlow cannot start; the message names the cause."""


class LiveFlow:
    """Shows a lumlflow as a flow on an orbit's Flow page while it runs.

    Use it as a context manager, or call `start` and `stop` where a block cannot
    span the work, as across notebook cells. The API key and the address of LUML
    come from the environment variables the API client reads. A lumlflow already
    answering on the port is exposed as it is; otherwise one is started on
    `store_path` and stopped with the flow.
    """

    def __init__(
        self,
        name: str | None = None,
        *,
        organization: str | None = None,
        orbit: str | None = None,
        store_path: str | None = None,
        port: int = 5000,
    ) -> None:
        self.name = name or socket.gethostname()
        self.organization = organization
        self.orbit = orbit
        self.store_path = store_path
        self.port = port
        self.app_url: str | None = None
        self._started = False
        self._running = False
        self._client: LumlClient | None = None
        self._flow_id: str | None = None
        self._lumlflow: subprocess.Popen[bytes] | None = None
        self._serving: _BackgroundServing | None = None
        self._previous_termination_handler: _SignalHandler = None
        self._handles_termination = False

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def start(self) -> str:
        """Expose the flow and return its address in the LUML app."""
        if self._started:
            raise LiveFlowError("This LiveFlow was already started")
        self._started = True
        try:
            app_url = self._expose()
        except BaseException:
            self._release()
            raise
        self._running = True
        self._register_cleanup()
        print(f"Flow {self.name} is live at {app_url}", flush=True)  # noqa: T201
        return app_url

    def stop(self) -> None:
        """Remove the flow at LUML and stop what `start` started; harmless twice."""
        if not self._running:
            return
        self._running = False
        self._unregister_cleanup()
        self._release()

    def _expose(self) -> str:
        client = LumlClient(organization=self.organization, orbit=self.orbit)
        if client.organization is None or client.orbit is None:
            raise LiveFlowError(
                "The API key reaches several organizations or orbits; "
                "name the organization and the orbit"
            )
        if _lumlflow_answers(self.port):
            if self.store_path is not None:
                logger.warning(
                    "lumlflow already answers on port %s; its own store is exposed, "
                    "not %s",
                    self.port,
                    self.store_path,
                )
        else:
            self._lumlflow = _start_lumlflow(self.port, self.store_path)
        self._client = client
        exposed = client.flows.expose(self.name)
        self._flow_id = exposed.flow.id
        self._serving = _BackgroundServing()
        self._serving.start(
            client.organization, client.orbit, exposed.session, self.port
        )
        self.app_url = exposed.app_url
        return exposed.app_url

    def _release(self) -> None:
        if self._client is not None and self._flow_id is not None:
            _remove_flow(self._client, self._flow_id)
        if self._serving is not None:
            self._serving.stop()
        if self._lumlflow is not None:
            _stop_process(self._lumlflow)

    def _register_cleanup(self) -> None:
        atexit.register(self.stop)
        if threading.current_thread() is threading.main_thread():
            self._previous_termination_handler = signal.signal(
                signal.SIGTERM, self._on_termination
            )
            self._handles_termination = True

    def _unregister_cleanup(self) -> None:
        atexit.unregister(self.stop)
        if (
            self._handles_termination
            and threading.current_thread() is threading.main_thread()
            and signal.getsignal(signal.SIGTERM) == self._on_termination
        ):
            previous = self._previous_termination_handler
            signal.signal(
                signal.SIGTERM, signal.SIG_DFL if previous is None else previous
            )

    def _on_termination(self, signum: int, frame: FrameType | None) -> None:
        previous = self._previous_termination_handler
        self.stop()
        if callable(previous):
            previous(signum, frame)
        elif previous in (signal.SIG_DFL, None):
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)


class _BackgroundServing:
    """Serves a session with the tunnel on a thread with its own event loop."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="luml-flow", daemon=True
        )
        self._task: asyncio.Task[None] | None = None

    def start(
        self, organization: str, orbit: str, session: LiveSessionStart, port: int
    ) -> None:
        """Serve, waiting until the agent connects or `CONNECT_TIMEOUT` passes."""
        self._thread.start()
        self._run(self._start(organization, orbit, session, port))

    def stop(self) -> None:
        if self._thread.is_alive():
            self._run(self._cancel())
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join()
        self._loop.close()

    def _run(self, coroutine: Coroutine[Any, Any, None]) -> None:
        asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()

    async def _start(
        self, organization: str, orbit: str, session: LiveSessionStart, port: int
    ) -> None:
        connected = asyncio.Event()
        self._task = asyncio.create_task(
            _serve(organization, orbit, session, port, connected)
        )
        waiting = asyncio.create_task(connected.wait())
        await asyncio.wait(
            (self._task, waiting),
            timeout=CONNECT_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED,
        )
        waiting.cancel()
        if self._task.done():
            self._task.result()
            raise LiveFlowError("LUML ended the session before the agent connected")
        if not connected.is_set():
            logger.warning("The agent has not reached the relay yet and keeps trying")
        self._task.add_done_callback(_report_serving_end)

    async def _cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)


async def _serve(
    organization: str,
    orbit: str,
    session: LiveSessionStart,
    port: int,
    connected: asyncio.Event,
) -> None:
    client = AsyncLumlClient()
    client.organization = organization
    client.orbit = orbit
    service = LoopbackService(port)
    try:
        # Never set: the flow is removed through the API and serving is cancelled.
        await serve_session(client, session, service, asyncio.Event(), None, connected)
    finally:
        await service.aclose()


def _report_serving_end(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is None:
        logger.info("LUML ended the flow's session; it is no longer served")
    else:
        logger.error("The flow is no longer served: %s", error)


def _remove_flow(client: LumlClient, flow_id: str) -> None:
    try:
        client.flows.remove(flow_id)
    except NotFoundError:
        logger.info("The flow was already gone at LUML")
    except (httpx.HTTPError, APIStatusError) as error:
        logger.warning(
            "Could not remove the flow at LUML; its session ends by silence: %s", error
        )


def _lumlflow_answers(port: int) -> bool:
    """Whether lumlflow answers on the loopback port; False when nothing listens."""
    in_use = LiveFlowError(f"Port {port} is in use by a server that is not lumlflow")
    try:
        response = httpx.get(
            f"http://127.0.0.1:{port}{STATUS_PATH}", timeout=2.0, trust_env=False
        )
    except httpx.ConnectError:
        return False
    except httpx.HTTPError as error:
        raise in_use from error
    try:
        body = response.json()
    except ValueError:
        body = None
    if (
        response.status_code != 200
        or not isinstance(body, dict)
        or "has_key" not in body
    ):
        raise in_use
    return True


def _start_lumlflow(port: int, store_path: str | None) -> subprocess.Popen[bytes]:
    command = shutil.which("lumlflow")
    if command is None:
        raise LiveFlowError(
            f"Nothing answers on port {port} and the lumlflow command is not on "
            "the path; install lumlflow to have LiveFlow start one"
        )
    arguments = [command, "ui", "--port", str(port), "--no-browser"]
    if store_path is not None:
        arguments += ["--path", store_path]
    # Its access log goes to stdout and would flood the caller's output.
    process = subprocess.Popen(arguments, stdout=subprocess.DEVNULL)
    try:
        _wait_until_answering(process, port)
    except BaseException:
        _stop_process(process)
        raise
    return process


def _wait_until_answering(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + LUMLFLOW_START_TIMEOUT
    while not _lumlflow_answers(port):
        if process.poll() is not None:
            raise LiveFlowError(
                f"lumlflow exited with code {process.returncode} before answering"
            )
        if time.monotonic() > deadline:
            raise LiveFlowError(
                f"lumlflow did not answer on port {port} "
                f"within {LUMLFLOW_START_TIMEOUT:g} seconds"
            )
        time.sleep(0.2)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(LUMLFLOW_STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
