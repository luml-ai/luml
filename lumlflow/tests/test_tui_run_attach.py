"""Pilot tests for run-and-attach mode (`lumlflow tui <script>`).

Covers SPEC.md task: "Add run-and-attach mode" — the TUI runs the
given script as a child sharing the same SQLite store via env, streams
stdout/stderr into a scrollable log pane, snapshots existing
experiments and auto-attaches to the new one (handling multiple-new
and none-created cases), and surfaces a non-zero exit clearly.

All tests use a deterministic seed script that the test writes to the
tmp dir: short-lived, exits in well under a second, and either writes
to the shared tracker (via the same `ExperimentTracker` API the SDK
uses) or doesn't, depending on what the test wants to verify.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.run_manager import RunManager, RunSpec, iter_attach_candidates
from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen
from lumlflow.tui.screens.run_attach import RunAttachScreen
from lumlflow.tui.widgets.log_pane import RunLogPane

# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _store_uri_for(tracker: ExperimentTracker) -> str:
    backend = tracker.backend
    base_path = getattr(backend, "base_path", None)
    if base_path is not None:
        return f"sqlite://{base_path}"
    raise AssertionError("could not derive store URI from tracker")


def _write_script(tmp_path: Path, body: str, name: str = "seed.py") -> Path:
    script = tmp_path / name
    script.write_text(body)
    return script


def _success_script(group: str = "g", exp_name: str = "run-1") -> str:
    """A short script that creates one experiment and exits cleanly.

    The child reads its store URI from the env (which the TUI sets via
    `RunManager.build_environment`) so it writes into the same SQLite
    file the TUI is reading.
    """

    return f"""
import os
import sys
from luml.experiments.tracker import ExperimentTracker

uri = os.environ.get("BACKEND_STORE_URI") or os.environ.get("LUML_BACKEND_STORE_URI")
assert uri, "store URI not set in child env"
tracker = ExperimentTracker(uri)
tracker.create_group({group!r})
exp_id = tracker.start_experiment(name={exp_name!r}, group={group!r})
print("created", exp_id, flush=True)
sys.exit(0)
"""


def _no_experiment_script() -> str:
    return """
import sys
print("doing nothing", flush=True)
sys.exit(0)
"""


def _failing_script() -> str:
    return """
import sys
print("about to crash", flush=True)
print("kaboom", file=sys.stderr, flush=True)
sys.exit(7)
"""


def _multi_new_script(group: str = "g") -> str:
    return f"""
import os
from luml.experiments.tracker import ExperimentTracker
uri = os.environ["BACKEND_STORE_URI"]
tracker = ExperimentTracker(uri)
tracker.create_group({group!r})
tracker.start_experiment(name="run-A", group={group!r})
tracker.start_experiment(name="run-B", group={group!r})
tracker.start_experiment(name="run-C", group={group!r})
print("done", flush=True)
"""


async def _wait_until(predicate, *, pilot, timeout: float = 6.0) -> None:
    """Pump the event loop until `predicate()` returns truthy.

    Subprocess wait + log streaming requires several event-loop turns —
    `pilot.pause()` is a single turn; this helper loops until the
    condition holds (or times out) so tests stay deterministic without
    asserting on a specific number of pauses.
    """

    elapsed = 0.0
    while not predicate():
        await pilot.pause()
        await asyncio.sleep(0.05)
        elapsed += 0.05
        if elapsed >= timeout:
            raise AssertionError("predicate did not become true in time")


# ---------------------------------------------------------------------------
# Unit tests for RunManager (no UI)
# ---------------------------------------------------------------------------


class TestRunManagerSnapshot:
    def test_snapshot_records_existing_ids(self, tracker: ExperimentTracker) -> None:
        tracker.create_group("g")
        existing = tracker.start_experiment(name="seed", group="g")
        manager = RunManager(
            spec=RunSpec(script="/dev/null"),
            tracker=tracker,
            store_uri=_store_uri_for(tracker),
            on_line=lambda *_: None,
            on_exit=lambda _: None,
        )
        snapshot = manager.snapshot_experiments()
        assert existing in snapshot

    def test_detect_new_filters_already_seen(self, tracker: ExperimentTracker) -> None:
        tracker.create_group("g")
        old = tracker.start_experiment(name="old", group="g")
        manager = RunManager(
            spec=RunSpec(script="/dev/null"),
            tracker=tracker,
            store_uri=_store_uri_for(tracker),
            on_line=lambda *_: None,
            on_exit=lambda _: None,
        )
        manager.snapshot_experiments()
        # The old experiment is in the snapshot → not "new".
        assert old not in manager.detect_new_experiments(require_active=False)
        # Create a fresh one after the snapshot.
        new = tracker.start_experiment(name="fresh", group="g")
        new_ids = manager.detect_new_experiments(require_active=False)
        assert new in new_ids
        assert old not in new_ids

    def test_iter_attach_candidates_helper(self, tracker: ExperimentTracker) -> None:
        tracker.create_group("g")
        a = tracker.start_experiment(name="a", group="g")
        snapshot = {a}
        b = tracker.start_experiment(name="b", group="g")
        candidates = iter_attach_candidates(tracker, snapshot)
        assert b in candidates
        assert a not in candidates


class TestRunManagerProcessLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_capture(
        self, tmp_path: Path, tracker: ExperimentTracker
    ) -> None:
        script = _write_script(
            tmp_path,
            "import sys\nprint('hi out'); print('hi err', file=sys.stderr)\n",
        )
        lines: list[tuple[str, str]] = []
        exit_codes: list[int | None] = []
        manager = RunManager(
            spec=RunSpec(script=str(script)),
            tracker=tracker,
            store_uri=_store_uri_for(tracker),
            on_line=lambda stream, line: lines.append((stream, line)),
            on_exit=lambda code: exit_codes.append(code),
        )
        await manager.start()
        # Wait for the wait task to dispatch the exit callback.
        for _ in range(60):
            await asyncio.sleep(0.05)
            if exit_codes:
                break
        assert exit_codes and exit_codes[0] == 0
        # Both streams captured.
        streams = {stream for stream, _ in lines}
        assert "stdout" in streams
        assert "stderr" in streams
        joined = " ".join(line for _, line in lines)
        assert "hi out" in joined
        assert "hi err" in joined

    async def test_streams_output_before_exit(
        self, tmp_path: Path, tracker: ExperimentTracker
    ) -> None:
        release = tmp_path / "release"
        script = _write_script(
            tmp_path,
            f"""
import sys
import time
from pathlib import Path
print("live stdout")
print("live stderr", file=sys.stderr)
while not Path({str(release)!r}).exists():
    time.sleep(0.01)
sys.stdout.write("final stdout")
sys.stderr.write("final stderr")
""",
        )
        lines: list[tuple[str, str]] = []
        exit_codes: list[int | None] = []
        manager = RunManager(
            spec=RunSpec(script=str(script)),
            tracker=tracker,
            store_uri=_store_uri_for(tracker),
            on_line=lambda stream, line: lines.append((stream, line)),
            on_exit=lambda code: exit_codes.append(code),
        )
        try:
            await manager.start()
            async with asyncio.timeout(5):
                while len(lines) < 2:
                    await asyncio.sleep(0.01)
            assert manager.is_running
            assert ("stdout", "live stdout") in lines
            assert ("stderr", "live stderr") in lines
            release.touch()
            async with asyncio.timeout(5):
                while not exit_codes:
                    await asyncio.sleep(0.01)
            assert exit_codes == [0]
            assert ("stdout", "final stdout") in lines
            assert ("stderr", "final stderr") in lines
        finally:
            release.touch()
            await manager.terminate(kill_after=0.1)

    def test_child_survives_parent_exit(
        self, tmp_path: Path, tracker: ExperimentTracker
    ) -> None:
        release = tmp_path / "release"
        done = tmp_path / "done"
        pid_file = tmp_path / "pid"
        log_dir_file = tmp_path / "log-dir"
        script = _write_script(
            tmp_path,
            f"""
import os
import sys
import time
from pathlib import Path
Path({str(pid_file)!r}).write_text(str(os.getpid()))
print("before detach", flush=True)
while not Path({str(release)!r}).exists():
    time.sleep(0.01)
for i in range(100):
    print("after detach stdout", i, flush=True)
    print("after detach stderr", i, file=sys.stderr, flush=True)
Path({str(done)!r}).touch()
""",
        )
        parent = _write_script(
            tmp_path,
            textwrap.dedent(f"""
                import asyncio
                from pathlib import Path
                from luml.experiments.tracker import ExperimentTracker
                from lumlflow.tui.run_manager import RunManager, RunSpec

                async def main():
                    manager = RunManager(
                        spec=RunSpec(script={str(script)!r}),
                        tracker=ExperimentTracker({_store_uri_for(tracker)!r}),
                        store_uri={_store_uri_for(tracker)!r},
                        on_line=lambda *_: None,
                        on_exit=lambda _: None,
                    )
                    await manager.start()
                    while not Path({str(pid_file)!r}).exists():
                        await asyncio.sleep(0.01)
                    Path({str(log_dir_file)!r}).write_text(
                        str(getattr(manager.state, "log_dir", None))
                    )

                asyncio.run(main())
            """),
            name="parent.py",
        )
        try:
            result = subprocess.run(
                [sys.executable, str(parent)], capture_output=True, timeout=10
            )
            assert result.returncode == 0, result.stderr.decode()
            pid = int(pid_file.read_text())
            os.kill(pid, 0)
            release.touch()
            import time

            deadline = time.monotonic() + 5
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert done.exists(), "detached child failed to finish after parent exit"
            log_dir = Path(log_dir_file.read_text())
            assert "after detach stdout 99" in (log_dir / "stdout.log").read_text()
            assert "after detach stderr 99" in (log_dir / "stderr.log").read_text()
        finally:
            if pid_file.exists():
                try:
                    os.killpg(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    async def test_unwritable_log_directory_reports_failure(
        self, tmp_path: Path, tracker: ExperimentTracker, monkeypatch
    ) -> None:
        home_file = tmp_path / "not-a-directory"
        home_file.touch()
        monkeypatch.setattr(Path, "home", lambda: home_file)
        exit_codes: list[int | None] = []
        manager = RunManager(
            spec=RunSpec(script="/dev/null"),
            tracker=tracker,
            store_uri=_store_uri_for(tracker),
            on_line=lambda *_: None,
            on_exit=exit_codes.append,
        )
        await manager.start()
        assert not manager.is_running
        assert manager.state.finished
        assert manager.state.error_message
        assert exit_codes and exit_codes[0] not in (0, None)

    async def test_terminate_escalates_and_waits_for_exit(
        self, tmp_path: Path, tracker: ExperimentTracker
    ) -> None:
        ready = tmp_path / "ready"
        script = _write_script(
            tmp_path,
            f"""
import signal
import time
from pathlib import Path
signal.signal(signal.SIGINT, signal.SIG_IGN)
Path({str(ready)!r}).touch()
while True:
    time.sleep(0.1)
""",
        )
        manager = RunManager(
            spec=RunSpec(script=str(script)),
            tracker=tracker,
            store_uri=_store_uri_for(tracker),
            on_line=lambda *_: None,
            on_exit=lambda _: None,
        )
        try:
            await manager.start()
            async with asyncio.timeout(5):
                while not ready.exists():
                    await asyncio.sleep(0.01)
            await manager.terminate(kill_after=0.05)
            assert not manager.is_running
        finally:
            await manager.terminate(kill_after=0.1)

    @pytest.mark.asyncio
    async def test_missing_script_reports_non_zero_exit(
        self, tracker: ExperimentTracker
    ) -> None:
        exit_codes: list[int | None] = []
        # Use the real tracker but a script path that does not exist.
        # `python /nonexistent.py` exits with code 2; we surface that
        # via the exit callback so the UI can display the failure.
        manager = RunManager(
            spec=RunSpec(script="/nonexistent/path/__nope.py"),
            tracker=tracker,
            store_uri=_store_uri_for(tracker),
            on_line=lambda *_: None,
            on_exit=lambda code: exit_codes.append(code),
        )
        await manager.start()
        for _ in range(60):
            await asyncio.sleep(0.05)
            if exit_codes:
                break
        assert exit_codes and exit_codes[0] not in (0, None)

    @pytest.mark.asyncio
    async def test_environment_injects_store_uri(
        self, tracker: ExperimentTracker
    ) -> None:
        manager = RunManager(
            spec=RunSpec(script="/dev/null"),
            tracker=tracker,
            store_uri="sqlite:///tmp/abc",
            on_line=lambda *_: None,
            on_exit=lambda _: None,
            env={"OTHER": "value"},
        )
        env = manager.build_environment()
        assert env["BACKEND_STORE_URI"] == "sqlite:///tmp/abc"
        assert env["LUML_BACKEND_STORE_URI"] == "sqlite:///tmp/abc"
        # The non-store env entry is preserved.
        assert env["OTHER"] == "value"


# ---------------------------------------------------------------------------
# RunSpec
# ---------------------------------------------------------------------------


class TestRunSpec:
    def test_command_uses_current_interpreter(self) -> None:
        import sys

        spec = RunSpec(script="train.py", args=("--epochs", "10"))
        cmd = spec.command
        assert cmd[0] == sys.executable
        assert cmd[1] == "train.py"
        assert cmd[2:] == ["--epochs", "10"]

    def test_describe_quotes_args(self) -> None:
        spec = RunSpec(script="train.py", args=("--name", "my run"))
        described = spec.describe()
        assert "train.py" in described
        # The space-containing arg should be quoted.
        assert "'my run'" in described or '"my run"' in described


# ---------------------------------------------------------------------------
# Run-and-attach screen — successful attach
# ---------------------------------------------------------------------------


class TestRunAttachSuccess:
    async def test_attaches_to_new_experiment_and_navigates(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        script = _write_script(tmp_path, _success_script())
        spec = RunSpec(script=str(script))
        app = LumlflowApp(
            facade=facade,
            run_spec=spec,
            store_uri=_store_uri_for(tracker),
            attach_timeout=10.0,
        )
        async with app.run_test() as pilot:
            # Wait for the RunAttachScreen to be active.
            await _wait_until(
                lambda: (
                    isinstance(app.screen, RunAttachScreen)
                    or isinstance(app.screen, ExperimentDetailScreen)
                ),
                pilot=pilot,
            )
            # Wait for auto-navigate to the detail screen.
            await _wait_until(
                lambda: isinstance(app.screen, ExperimentDetailScreen),
                pilot=pilot,
                timeout=10.0,
            )
            assert isinstance(app.screen, ExperimentDetailScreen)
            # The detail screen is the one for the script-created experiment.
            experiments = tracker.list_experiments()
            ids = {e.id for e in experiments}
            assert app.screen._experiment_id in ids
            # Let the lazy-loaded panels (Traces / Evals / Attachments)
            # finish composing before the test tears down — their
            # `on_mount` queries internal widgets and would crash if the
            # compose step were interrupted by teardown.
            for _ in range(8):
                await pilot.pause()

    async def test_log_pane_captures_script_output(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        script = _write_script(tmp_path, _success_script())
        spec = RunSpec(script=str(script))
        app = LumlflowApp(
            facade=facade,
            run_spec=spec,
            store_uri=_store_uri_for(tracker),
        )
        async with app.run_test() as pilot:
            await _wait_until(
                lambda: any(isinstance(s, RunAttachScreen) for s in app.screen_stack),
                pilot=pilot,
            )
            run_screen = next(
                s for s in app.screen_stack if isinstance(s, RunAttachScreen)
            )
            log = run_screen.query_one("#run-log", RunLogPane)
            # Wait until the child's stdout has been written into the log.
            await _wait_until(
                lambda: any("created" in str(line.text) for line in log.lines),
                pilot=pilot,
                timeout=10.0,
            )

    async def test_status_indicator_shows_attached_id(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        # `auto_navigate=False` keeps us on RunAttachScreen so the test
        # can inspect `_attached_id` without racing the teardown against
        # the ExperimentDetailScreen panels' on_mount handlers.
        script = _write_script(tmp_path, _success_script())
        spec = RunSpec(script=str(script))
        run_screen = RunAttachScreen(
            facade=facade,
            spec=spec,
            store_uri=_store_uri_for(tracker),
            attach_timeout=10.0,
            attach_poll_seconds=0.1,
            auto_navigate=False,
        )
        app = LumlflowApp(facade=facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(run_screen)
            await pilot.pause()
            await _wait_until(
                lambda: run_screen._attached_id is not None,
                pilot=pilot,
                timeout=10.0,
            )
            assert run_screen._attached_id is not None


# ---------------------------------------------------------------------------
# No experiment created
# ---------------------------------------------------------------------------


class TestRunAttachNoExperiment:
    async def test_announces_when_no_experiment_appears(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        script = _write_script(tmp_path, _no_experiment_script())
        spec = RunSpec(script=str(script))
        # Short timeout so the test doesn't wait the default 60 s.
        app = LumlflowApp(
            facade=facade,
            run_spec=spec,
            store_uri=_store_uri_for(tracker),
            attach_timeout=2.0,
        )
        async with app.run_test() as pilot:
            await _wait_until(
                lambda: any(isinstance(s, RunAttachScreen) for s in app.screen_stack),
                pilot=pilot,
            )
            run_screen = next(
                s for s in app.screen_stack if isinstance(s, RunAttachScreen)
            )
            # The script will exit quickly, the post-exit poll will fail,
            # and the screen will announce "no experiment was created".
            await _wait_until(
                lambda: run_screen._exited,
                pilot=pilot,
                timeout=10.0,
            )
            # Give the announce timer a chance to fire.
            await _wait_until(
                lambda: any(
                    "no experiment" in str(line.text).lower()
                    for line in run_screen.query_one("#run-log", RunLogPane).lines
                ),
                pilot=pilot,
                timeout=5.0,
            )
            # The screen remains usable (still mounted) — not crashed.
            assert isinstance(app.screen, RunAttachScreen)


# ---------------------------------------------------------------------------
# Failure / non-zero exit
# ---------------------------------------------------------------------------


class TestRunAttachFailure:
    async def test_non_zero_exit_surfaced_in_log(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        script = _write_script(tmp_path, _failing_script())
        spec = RunSpec(script=str(script))
        app = LumlflowApp(
            facade=facade,
            run_spec=spec,
            store_uri=_store_uri_for(tracker),
            attach_timeout=2.0,
        )
        async with app.run_test() as pilot:
            await _wait_until(
                lambda: any(isinstance(s, RunAttachScreen) for s in app.screen_stack),
                pilot=pilot,
            )
            run_screen = next(
                s for s in app.screen_stack if isinstance(s, RunAttachScreen)
            )
            await _wait_until(
                lambda: (
                    run_screen._run is not None
                    and run_screen._run.state.exit_code is not None
                ),
                pilot=pilot,
                timeout=10.0,
            )
            assert run_screen._run is not None
            assert run_screen._run.state.exit_code == 7
            log = run_screen.query_one("#run-log", RunLogPane)
            # The stderr "kaboom" was captured into the log.
            await _wait_until(
                lambda: any("kaboom" in str(line.text) for line in log.lines),
                pilot=pilot,
                timeout=5.0,
            )
            # And the exit-code status line was added.
            await _wait_until(
                lambda: any(
                    "exit" in str(line.text).lower() and "7" in str(line.text)
                    for line in log.lines
                ),
                pilot=pilot,
                timeout=5.0,
            )


# ---------------------------------------------------------------------------
# Lifecycle: quit-prompt + stop-run
# ---------------------------------------------------------------------------


class TestRunAttachLifecycle:
    @pytest.mark.parametrize("choice", ["escape", "enter", "t"])
    async def test_quit_prompt_cancel_detach_or_terminate(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
        choice: str,
    ) -> None:
        release = tmp_path / "release"
        script = _write_script(
            tmp_path,
            f"""
import time
from pathlib import Path
print("ready", flush=True)
while not Path({str(release)!r}).exists():
    time.sleep(0.01)
print("finished after detach", flush=True)
""",
        )
        app = LumlflowApp(
            facade=facade,
            run_spec=RunSpec(script=str(script)),
            store_uri=_store_uri_for(tracker),
        )
        manager = None
        try:
            async with app.run_test() as pilot:
                await _wait_until(lambda: app.has_active_run, pilot=pilot)
                assert app._active_run_screen is not None
                manager = app._active_run_screen._run
                assert manager is not None
                await app.action_quit()
                await pilot.pause()
                labels = " ".join(
                    str(node.render()) for node in app.screen.query("Static")
                )
                assert "Quit (detach)" in labels
                assert "Terminate" in labels
                assert "Cancel" in labels
                assert str(manager.state.log_dir) in labels
                await pilot.press(choice)
                await pilot.pause()
                if choice == "escape":
                    assert isinstance(app.screen, RunAttachScreen)
                    assert manager.is_running
                    assert not app._quit_in_progress
                elif choice == "enter":
                    assert manager.is_running
                    assert manager.state.detach_only
                else:
                    assert not manager.is_running
            if choice == "enter":
                assert manager.is_running
                release.touch()
                async with asyncio.timeout(5):
                    while manager.is_running:
                        await asyncio.sleep(0.01)
                assert manager.state.log_dir is not None
                assert (
                    "finished after detach"
                    in (manager.state.log_dir / "stdout.log").read_text()
                )
        finally:
            release.touch()
            if manager is not None:
                await manager.terminate(kill_after=0.1)

    async def test_stop_run_terminates_process(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        long_script = _write_script(
            tmp_path,
            "import time\nwhile True:\n    time.sleep(0.1)\n",
            name="long.py",
        )
        spec = RunSpec(script=str(long_script))
        app = LumlflowApp(
            facade=facade,
            run_spec=spec,
            store_uri=_store_uri_for(tracker),
            attach_timeout=10.0,
        )
        async with app.run_test() as pilot:
            await _wait_until(
                lambda: any(isinstance(s, RunAttachScreen) for s in app.screen_stack),
                pilot=pilot,
            )
            run_screen = next(
                s for s in app.screen_stack if isinstance(s, RunAttachScreen)
            )
            # Wait until the process is running before stopping.
            await _wait_until(
                lambda: run_screen._run is not None and run_screen._run.is_running,
                pilot=pilot,
                timeout=10.0,
            )
            # Trigger the stop action; child should exit shortly after.
            run_screen.action_stop_run()
            await _wait_until(
                lambda: run_screen._exited,
                pilot=pilot,
                timeout=10.0,
            )

    async def test_has_active_run_flag(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        long_script = _write_script(
            tmp_path,
            "import time\nwhile True:\n    time.sleep(0.1)\n",
            name="long.py",
        )
        spec = RunSpec(script=str(long_script))
        app = LumlflowApp(
            facade=facade,
            run_spec=spec,
            store_uri=_store_uri_for(tracker),
            attach_timeout=10.0,
        )
        async with app.run_test() as pilot:
            await _wait_until(
                lambda: app.has_active_run,
                pilot=pilot,
                timeout=10.0,
            )
            assert app.has_active_run is True
            # Stop the run; the flag flips back.
            run_screen = next(
                s for s in app.screen_stack if isinstance(s, RunAttachScreen)
            )
            run_screen.action_stop_run()
            await _wait_until(
                lambda: not app.has_active_run,
                pilot=pilot,
                timeout=10.0,
            )


# ---------------------------------------------------------------------------
# Multiple new experiments — attach to first, surface the rest
# ---------------------------------------------------------------------------


class TestMultipleNewExperiments:
    async def test_attaches_to_first_new_experiment(
        self,
        tmp_path: Path,
        tracker: ExperimentTracker,
        facade: DataFacade,
    ) -> None:
        # `auto_navigate=False` keeps us on RunAttachScreen so the
        # subsequent assertion on `_attached_id` doesn't race the
        # ExperimentDetailScreen panel composition during teardown.
        script = _write_script(tmp_path, _multi_new_script())
        spec = RunSpec(script=str(script))
        run_screen = RunAttachScreen(
            facade=facade,
            spec=spec,
            store_uri=_store_uri_for(tracker),
            attach_timeout=10.0,
            attach_poll_seconds=0.1,
            auto_navigate=False,
        )
        app = LumlflowApp(facade=facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(run_screen)
            await pilot.pause()
            await _wait_until(
                lambda: run_screen._attached_id is not None,
                pilot=pilot,
                timeout=10.0,
            )
            attached = run_screen._attached_id
            # All three experiments should exist; the attach picks one.
            assert attached is not None
            ids = {e.id for e in tracker.list_experiments()}
            assert attached in ids
