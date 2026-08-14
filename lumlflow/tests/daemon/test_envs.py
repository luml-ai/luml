"""The workspace env: which interpreter runs a kernel, what the lockfile pins,
and what an install does to a kernel already holding the old imports.

The rule under all of it is that an env change is provenance, never
invalidation: what already ran keeps the pins it ran under, and the only thing
an install moves is what the next kernel imports.
"""

import asyncio
import sys
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
from lumlflow.flow.daemon import envs
from lumlflow.flow.daemon.hub import FlowSession
from lumlflow.flow.errors import EnvError
from lumlflow.flow.store.models import EnvChanged, RunRecorded

from tests.daemon.helpers import (
    FRAME_CELL,
    SCORE_CELL,
    daemon_api,
    fake_venv,
    flow_named,
    make_workspace,
    ops_of,
    stub_uv,
    uv_that_locks,
    write_cell,
    write_file,
    write_lock,
)

# The stub stands in for uv itself, so these run where a shell does. What the
# lockfile means is plain file reading, and is asserted everywhere.
stubbed_uv = pytest.mark.skipif(
    sys.platform == "win32", reason="the uv stub is a POSIX shell script"
)


def test_the_workspace_venv_is_the_interpreter(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    python = fake_venv(root)

    assert envs.describe(root) == envs.Interpreter(python=python, source="venv")


def test_a_workspace_without_a_venv_runs_on_the_daemons_interpreter(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    described = envs.describe(root)

    assert described.source == "lumlflow"
    assert described.python == Path(sys.executable)


@stubbed_uv
async def test_uv_sync_creates_the_venv_the_kernel_then_runs_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": "[project]"})
    stub_uv(
        tmp_path / "bin",
        f"""
        #!/bin/sh
        mkdir -p "$PWD/.venv/bin"
        ln -s "{sys.executable}" "$PWD/.venv/bin/python"
        echo "synced $1"
        """,
        monkeypatch,
    )

    interpreter = await envs.ensure_interpreter(root)

    assert interpreter.source == "venv"
    assert interpreter.python == root / ".venv" / "bin" / "python"


@stubbed_uv
async def test_a_failing_sync_is_the_users_to_fix_not_a_silent_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": "[project]"})
    stub_uv(
        tmp_path / "bin",
        """
        #!/bin/sh
        echo "no solution found for lightgbm"
        exit 1
        """,
        monkeypatch,
    )

    with pytest.raises(EnvError) as failed:
        await envs.ensure_interpreter(root)

    assert "no solution found for lightgbm" in str(failed.value)


@stubbed_uv
async def test_nothing_to_sync_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project")
    stub_uv(tmp_path / "bin", "#!/bin/sh\nexit 1\n", monkeypatch)

    interpreter = await envs.ensure_interpreter(root)

    assert interpreter.source == "lumlflow"


def _recording_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "uv.log"
    stub_uv(tmp_path / "bin", f'#!/bin/sh\necho "$@" >> "{log}"\n', monkeypatch)
    return log


@stubbed_uv
async def test_a_published_output_pulls_the_sdk_into_the_workspace_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The venv holds no lumlflow code, so the library that talks to the
    platform is an ordinary workspace dependency — scaffolded, not assumed."""
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": "[project]"})
    log = _recording_uv(tmp_path, monkeypatch)

    assert await envs.ensure_sdk(root) is True
    assert log.read_text("utf-8").strip() == f"add {envs.SDK_PACKAGE}"


@stubbed_uv
@pytest.mark.parametrize(
    "project",
    [
        '[project]\ndependencies = ["luml-sdk>=0.2.0,<0.3.0"]\n',
        # Normalised the way PyPI does, and found wherever it is declared.
        "[project]\ndependencies = []\n[dependency-groups]\ndev = ['LUML_SDK']\n",
        '[project]\n[project.optional-dependencies]\npublish = ["luml-sdk"]\n',
    ],
)
async def test_an_sdk_already_declared_is_not_added_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project: str
):
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": project})
    log = _recording_uv(tmp_path, monkeypatch)

    assert await envs.ensure_sdk(root) is False
    assert not log.exists()


@stubbed_uv
async def test_a_workspace_that_declares_no_env_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A bare directory has no env to add to, and writing a `pyproject.toml`
    into somebody's folder because a cell said `model` is not scaffolding."""
    root = make_workspace(tmp_path / "project")
    log = _recording_uv(tmp_path, monkeypatch)

    assert await envs.ensure_sdk(root) is False
    assert not log.exists()
    assert not (root / envs.PROJECT_FILE).exists()


@stubbed_uv
async def test_a_dependency_merely_named_like_the_sdk_is_not_the_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(
        tmp_path / "project",
        files={"pyproject.toml": '[project]\ndependencies = ["luml-sdk-extras"]\n'},
    )
    log = _recording_uv(tmp_path, monkeypatch)

    assert await envs.ensure_sdk(root) is True
    assert log.read_text("utf-8").strip() == f"add {envs.SDK_PACKAGE}"


@stubbed_uv
async def test_a_failing_add_is_reported_rather_than_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": "[project]"})
    stub_uv(
        tmp_path / "bin",
        '#!/bin/sh\necho "no solution found for luml-sdk"\nexit 1\n',
        monkeypatch,
    )

    with pytest.raises(EnvError) as failed:
        await envs.ensure_sdk(root)

    assert "no solution found for luml-sdk" in str(failed.value)


class TestLockfile:
    """What "the env" means: the pins, not the bytes that spell them."""

    def test_the_lockfile_is_what_the_workspace_pins(self, tmp_path: Path):
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": "2.2.0", "Scikit_Learn": "1.4.0"})

        assert envs.packages(root) == {"pandas": "2.2.0", "scikit-learn": "1.4.0"}

    def test_a_workspace_that_locks_nothing_records_no_env(self, tmp_path: Path):
        root = make_workspace(tmp_path / "project")

        assert envs.packages(root) == {}
        assert envs.lock_hash(envs.packages(root)) is None

    def test_an_unreadable_lockfile_is_no_env_rather_than_a_failure(
        self, tmp_path: Path
    ):
        root = make_workspace(tmp_path / "project")
        write_file(root / envs.LOCK_FILE, "this is not toml [[[")

        assert envs.lock_hash(envs.packages(root)) is None

    def test_a_lockfile_rewritten_to_the_same_pins_is_the_same_env(
        self, tmp_path: Path
    ):
        """Hashed over the pins, so a reformat is not a history entry."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": "2.2.0"})
        before = envs.lock_hash(envs.packages(root))

        write_file(
            root / envs.LOCK_FILE,
            '# regenerated\nversion = 1\n[[package]]\nversion = "2.2.0"\n'
            'name = "pandas"\n',
        )

        assert envs.lock_hash(envs.packages(root)) == before

    def test_an_untouched_lockfile_is_parsed_once(self, tmp_path: Path):
        """Every verb records the env before it resolves anything, and a real
        workspace's lockfile is a quarter of a megabyte of TOML. Re-parsing it
        twenty times while a notebook opens is twenty parses of bytes that
        cannot have changed; the pins that come back are the same object's
        worth either way, so the reads above are what say it stays correct."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": "2.2.0"})
        envs.packages(root)

        reads = 0
        original = Path.read_text

        def counted(self: Path, *args: object, **kwargs: object) -> str:
            nonlocal reads
            if self.name == envs.LOCK_FILE:
                reads += 1
            return original(self, *args, **kwargs)  # type: ignore[arg-type]

        with patch.object(Path, "read_text", counted):
            for _ in range(10):
                assert envs.packages(root) == {"pandas": "2.2.0"}

        assert reads == 0

    def test_moving_a_pin_moves_the_hash(self, tmp_path: Path):
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": "2.2.0"})
        before = envs.lock_hash(envs.packages(root))

        write_lock(root, {"pandas": "2.3.0"})

        assert envs.lock_hash(envs.packages(root)) != before

    def test_a_transition_is_named_in_words(self):
        moved = envs.summary(
            {"pandas": "2.2.0", "scipy": "1.11.0"},
            {"pandas": "2.3.0", "lightgbm": "4.5.0"},
        )

        assert (
            moved == "added lightgbm 4.5.0; removed scipy; updated pandas 2.2.0 → 2.3.0"
        )


class TestObservation:
    """Every flow records the env it runs under, in its own journal."""

    async def test_every_hosted_flow_records_the_env_it_runs_under(
        self, tmp_path: Path
    ):
        root = make_workspace(tmp_path / "project", flows=("churn", "fraud"))
        write_lock(root, {"pandas": "2.2.0"})

        async with daemon_api(root) as api:
            await api.status({})
            observed = {
                name: ops_of(api.hub.session(name), EnvChanged)
                for name in ("churn", "fraud")
            }

        for ops in observed.values():
            assert [op.packages for op in ops] == [{"pandas": "2.2.0"}]
            assert [op.lock_hash for op in ops] == [envs.lock_hash(envs.packages(root))]

    async def test_the_first_observation_claims_no_install(self, tmp_path: Path):
        """There is no env it moved from, and listing the whole lockfile as
        "added" would read as an install the user never ran."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": "2.2.0", "scipy": "1.11.0"})

        async with daemon_api(root) as api:
            await api.status({})
            (recorded,) = ops_of(api.hub.session("churn"), EnvChanged)

        assert recorded.summary == "recorded the workspace env"
        assert recorded.packages == {"pandas": "2.2.0", "scipy": "1.11.0"}

    async def test_an_unchanged_env_is_not_journalled_twice(self, tmp_path: Path):
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": "2.2.0"})

        async with daemon_api(root) as api:
            await api.status({})
            await api.status({})
            await api.cells_list({"flow": "churn"})
            recorded = ops_of(api.hub.session("churn"), EnvChanged)

        assert len(recorded) == 1

    async def test_a_run_records_the_pins_it_ran_under(self, tmp_path: Path):
        """Provenance on the materialization, so a later upgrade can say which
        results predate it."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": "2.2.0"})
        write_cell(root / "churn.flow", "score", SCORE_CELL)

        async with daemon_api(root) as api:
            await api.run({"flow": "churn", "target": "score"})
            (run,) = ops_of(api.hub.session("churn"), RunRecorded)

        assert run.env_lock_hash == envs.lock_hash(envs.packages(root))


ENV_SENSITIVE_CELL = """
class Pinned:
    \"\"\"Says its answer depends on the packages it ran under.\"\"\"
    env_sensitive = True
    produces = {"reading": "asset"}

    def materialize(self, ctx):
        return {"reading": {"auc": 0.5}}
"""

RELEASE_FILE = "release"

HELD_CELL = f"""
class Held:
    \"\"\"Holds the kernel's worker until the test lets go of it.\"\"\"
    produces = {{"done": "asset"}}

    def materialize(self, ctx):
        import time

        release = ctx.workspace_dir / "{RELEASE_FILE}"
        deadline = time.monotonic() + 30
        while not release.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        return {{"done": True}}
"""

# Whatever the workspace actually has installed, this is not it: the drift a
# kernel is measured against is the lockfile it started under against the one
# there now, and both are read from the file.
PINNED_BEFORE = "1.0.0"
PINNED_AFTER = "9.9.9"


class TestInstall:
    """`env add` while a kernel is up: the banner, and nothing else."""

    @stubbed_uv
    async def test_an_install_leaves_results_alone_and_asks_for_a_restart(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        write_cell(root / "churn.flow", "rows", FRAME_CELL)
        log = uv_that_locks(tmp_path, {"pandas": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            await api.run({"flow": "churn", "target": "rows"})
            ran_under = ops_of(api.hub.session("churn"), RunRecorded)[0].env_lock_hash

            await api.env_add({"packages": ["pandas"], "intent": "faster frames"})
            status = await api.status({})
            listed = await api.cells_list({"flow": "churn"})
            runs = ops_of(api.hub.session("churn"), RunRecorded)
            moved = ops_of(api.hub.session("churn"), EnvChanged)[-1]

        assert log.read_text("utf-8").strip() == "add pandas"
        # No cache nuke: the run that already happened keeps the pins it ran
        # under, and nothing about it went stale.
        assert [run.env_lock_hash for run in runs] == [ran_under]
        assert ran_under != envs.lock_hash(envs.packages(root))
        assert [entry["state"] for entry in listed["cells"]] == ["synced"]
        assert moved.summary == f"updated pandas {PINNED_BEFORE} → {PINNED_AFTER}"
        # The kernel imported pandas, so it is holding code the lockfile has
        # moved past — the one kernel control that surfaces.
        kernel = flow_named(status, "churn")["kernel"]
        assert (kernel["state"], kernel["restart_required"], kernel["behind"]) == (
            "running",
            True,
            ["pandas"],
        )
        # And the result says which side of the install it was computed on.
        assert [entry["older_env"] for entry in listed["cells"]] == [True]

    @stubbed_uv
    async def test_a_package_the_kernel_never_imported_needs_no_restart(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A restart is worth raising only over code already in `sys.modules`.
        Everything else the next run imports as installed."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"lightgbm": PINNED_BEFORE})
        write_cell(root / "churn.flow", "score", SCORE_CELL)
        uv_that_locks(tmp_path, {"lightgbm": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            await api.run({"flow": "churn", "target": "score"})
            env = await api.env_add({"packages": ["lightgbm"]})

        assert flow_named(env, "churn") == {
            "flow": "churn",
            "kernel": "running",
            "policy": "ask",
            "restart_required": False,
            "behind": [],
        }

    @stubbed_uv
    async def test_only_a_cell_that_declared_the_env_reruns_after_an_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The env is provenance, not a memo-key ingredient — except where a
        cell said otherwise."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        write_cell(root / "churn.flow", "score", SCORE_CELL)
        write_cell(root / "churn.flow", "pinned", ENV_SENSITIVE_CELL)
        uv_that_locks(tmp_path, {"pandas": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            for slug in ("score", "pinned"):
                await api.run({"flow": "churn", "target": slug})
            await api.env_add({"packages": ["pandas"]})
            again = {
                slug: await api.run({"flow": "churn", "target": slug})
                for slug in ("score", "pinned")
            }

        # Pruned, not merely cached: the ordinary cell's key never moved, so
        # there is nothing to serve it from — there is nothing to do.
        assert again["score"]["pruned"] == ["score"]
        assert again["pinned"]["executed"] == ["pinned"]

    @stubbed_uv
    async def test_no_flow_is_open_yet_and_the_install_still_lands(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A flow picks the env up when it opens — the same lazy path shared
        code takes — so nothing has to be running for `env add` to work."""
        root = make_workspace(tmp_path / "project")
        uv_that_locks(tmp_path, {"pandas": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            env = await api.env_add({"packages": ["pandas"]})
            (recorded,) = ops_of(api.hub.session("churn"), EnvChanged)

        assert env["packages"] == [{"name": "pandas", "version": PINNED_AFTER}]
        assert env["flows"] == []
        assert recorded.packages == {"pandas": PINNED_AFTER}

    @stubbed_uv
    async def test_removing_a_package_is_the_same_transaction_in_reverse(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE, "scipy": "1.11.0"})
        log = uv_that_locks(tmp_path, {"pandas": PINNED_BEFORE}, monkeypatch)

        async with daemon_api(root) as api:
            await api.status({})
            await api.env_remove({"packages": ["scipy"]})
            moved = ops_of(api.hub.session("churn"), EnvChanged)[-1]

        assert log.read_text("utf-8").strip() == "remove scipy"
        assert moved.summary == "removed scipy"

    async def test_naming_no_package_is_refused_before_uv_is_reached(
        self, tmp_path: Path
    ):
        root = make_workspace(tmp_path / "project")

        async with daemon_api(root) as api:
            with pytest.raises(EnvError) as failed:
                await api.env_add({"packages": []})

        assert "name a package" in str(failed.value)

    @stubbed_uv
    async def test_the_banner_answers_while_a_run_is_in_flight(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """An install landing mid-run is the case this is for. A status call
        that queued behind a ten-minute cell would put a spinner where the
        banner goes, so asking what the kernel imported never waits on it."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        write_cell(root / "churn.flow", "rows", FRAME_CELL)
        write_cell(root / "churn.flow", "held", HELD_CELL)
        uv_that_locks(tmp_path, {"pandas": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            await api.run({"flow": "churn", "target": "rows"})
            session = api.hub.session("churn")
            held = asyncio.create_task(api.run({"flow": "churn", "target": "held"}))
            try:
                await _until(lambda: session.queue.busy, "the run never started")
                env = await api.env_add({"packages": ["pandas"]})
            finally:
                (root / RELEASE_FILE).touch()
                await held

        assert flow_named(env, "churn")["restart_required"] is True

    @stubbed_uv
    async def test_a_run_in_flight_records_the_pins_it_started_under(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The kernel imported before the install landed, so that is what the
        cell computed under. Recording the pins the install left would take the
        "computed under an older env" badge off a result that predates it."""
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        started_under = envs.lock_hash(envs.packages(root))
        write_cell(root / "churn.flow", "held", HELD_CELL)
        uv_that_locks(tmp_path, {"pandas": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            session = api.hub.session("churn")
            held = asyncio.create_task(api.run({"flow": "churn", "target": "held"}))
            try:
                await _until(lambda: session.queue.busy, "the run never started")
                await api.env_add({"packages": ["pandas"]})
            finally:
                (root / RELEASE_FILE).touch()
                await held
            (run,) = ops_of(session, RunRecorded)
            listed = await api.cells_list({"flow": "churn"})

        assert run.env_lock_hash == started_under
        assert [entry["older_env"] for entry in listed["cells"]] == [True]


class TestRestartPolicy:
    """Three policies, and a banner under all of them."""

    @stubbed_uv
    @pytest.mark.parametrize("policy", ["ask", "never"])
    async def test_a_kernel_is_never_restarted_out_from_under_the_user(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy: str
    ):
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        write_cell(root / "churn.flow", "rows", FRAME_CELL)
        uv_that_locks(tmp_path, {"pandas": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            await api.run({"flow": "churn", "target": "rows"})
            session = api.hub.session("churn")
            session.store.manifest.settings.env_policy = policy  # type: ignore[assignment]
            pid = _kernel_pid(session)

            env = await api.env_add({"packages": ["pandas"]})

            assert _kernel_pid(session) == pid
            assert flow_named(env, "churn")["restart_required"] is True

    @stubbed_uv
    async def test_the_auto_policy_applies_the_install_to_the_kernel(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        write_cell(root / "churn.flow", "rows", FRAME_CELL)
        uv_that_locks(tmp_path, {"pandas": PINNED_AFTER}, monkeypatch)

        async with daemon_api(root) as api:
            await api.run({"flow": "churn", "target": "rows"})
            session = api.hub.session("churn")
            session.store.manifest.settings.env_policy = "auto"
            pid = _kernel_pid(session)

            env = await api.env_add({"packages": ["pandas"]})

            # A different process, up and holding the packages the lockfile now
            # names — which is the whole of what "apply the install" means.
            assert _kernel_pid(session) != pid
            assert flow_named(env, "churn") == {
                "flow": "churn",
                "kernel": "running",
                "policy": "auto",
                "restart_required": False,
                "behind": [],
            }


def _kernel_pid(session: FlowSession) -> int:
    assert session.kernel.handshake is not None
    return int(session.kernel.handshake["pid"])


async def _until(ready: Callable[[], bool], complaint: str, seconds: float = 10.0):
    deadline = time.monotonic() + seconds
    while not ready():
        assert time.monotonic() < deadline, complaint
        await asyncio.sleep(0.01)
