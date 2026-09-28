"""The workspace env: which interpreter runs a kernel, what the lockfile pins,
and what an install does to a kernel already holding the old imports.

The rule under all of it is that an env change is provenance, never
invalidation: what already ran keeps the pins it ran under, and the only thing
an install moves is what the next kernel imports.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from lumlflow.flow.daemon import envs
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


async def test_interpreter_resolution_walks_up_to_an_existing_venv_without_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": "[project]"})
    python = fake_venv(root)
    containing = root / "experiments" / "q3"
    containing.mkdir(parents=True)
    synced: list[Path] = []

    async def record_sync(path: Path) -> None:
        synced.append(path)

    monkeypatch.setattr(envs, "uv_sync", record_sync)

    interpreter = await envs.ensure_interpreter(containing)

    assert interpreter == envs.Interpreter(python=python, source="venv")
    assert envs.describe(containing) == interpreter
    assert synced == []


@stubbed_uv
async def test_interpreter_resolution_syncs_the_nearest_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": "[project]"})
    containing = root / "experiments" / "q3"
    containing.mkdir(parents=True)
    stub_uv(
        tmp_path / "bin",
        f"""
        #!/bin/sh
        mkdir -p "$PWD/.venv/bin"
        ln -s "{sys.executable}" "$PWD/.venv/bin/python"
        """,
        monkeypatch,
    )

    interpreter = await envs.ensure_interpreter(containing)

    assert interpreter == envs.Interpreter(
        python=root / ".venv" / "bin" / "python", source="venv"
    )
    assert envs.describe(containing) == interpreter


async def test_interpreter_resolution_without_a_project_uses_lumlflow(
    tmp_path: Path,
) -> None:
    containing = tmp_path / "project" / "experiments" / "q3"
    containing.mkdir(parents=True)

    interpreter = await envs.ensure_interpreter(containing)

    assert interpreter == envs.Interpreter(
        python=Path(sys.executable), source="lumlflow"
    )


async def test_interpreter_resolution_names_uv_when_a_project_cannot_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"pyproject.toml": "[project]"})
    monkeypatch.setattr(envs.shutil, "which", lambda command: None)

    with pytest.raises(EnvError, match="uv"):
        await envs.ensure_interpreter(root)


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

# Whatever the workspace actually has installed, this is not it: the drift a
# kernel is measured against is the lockfile it started under against the one
# there now, and both are read from the file.
PINNED_BEFORE = "1.0.0"
PINNED_AFTER = "9.9.9"


class TestExternalChange:
    async def test_a_change_leaves_results_alone_and_asks_for_a_restart(
        self, tmp_path: Path
    ) -> None:
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        write_cell(root / "churn.flow", "rows", FRAME_CELL)

        async with daemon_api(root) as api:
            await api.run({"flow": "churn", "target": "rows"})
            session = api.hub.session("churn")
            assert session.kernel.handshake is not None
            pid = session.kernel.handshake["pid"]
            ran_under = ops_of(session, RunRecorded)[0].env_lock_hash

            write_lock(root, {"pandas": PINNED_AFTER})
            status = await api.status({})
            reported = await api.env_status({})
            listed = await api.cells_list({"flow": "churn"})
            runs = ops_of(session, RunRecorded)
            moved = ops_of(session, EnvChanged)[-1]

            assert session.kernel.handshake is not None
            assert session.kernel.handshake["pid"] == pid
            await api.kernel_restart({"flow": "churn"})
            restarted = await api.env_status({})

        assert [run.env_lock_hash for run in runs] == [ran_under]
        assert ran_under != envs.lock_hash(envs.packages(root))
        assert [entry["state"] for entry in listed["cells"]] == ["synced"]
        assert [entry["older_env"] for entry in listed["cells"]] == [True]
        assert moved.summary == f"updated pandas {PINNED_BEFORE} → {PINNED_AFTER}"
        kernel = flow_named(status, "churn")["kernel"]
        assert (kernel["state"], kernel["restart_required"], kernel["behind"]) == (
            "running",
            True,
            ["pandas"],
        )
        assert flow_named(reported, "churn") == {
            "flow": "churn",
            "kernel": "running",
            "restart_required": True,
            "behind": ["pandas"],
        }
        assert flow_named(restarted, "churn")["restart_required"] is False

    async def test_only_a_cell_that_declared_the_env_reruns_after_a_change(
        self, tmp_path: Path
    ) -> None:
        root = make_workspace(tmp_path / "project")
        write_lock(root, {"pandas": PINNED_BEFORE})
        write_cell(root / "churn.flow", "score", SCORE_CELL)
        write_cell(root / "churn.flow", "pinned", ENV_SENSITIVE_CELL)

        async with daemon_api(root) as api:
            for slug in ("score", "pinned"):
                await api.run({"flow": "churn", "target": slug})
            write_lock(root, {"pandas": PINNED_AFTER})
            again = {
                slug: await api.run({"flow": "churn", "target": slug})
                for slug in ("score", "pinned")
            }

        assert again["score"]["pruned"] == ["score"]
        assert again["pinned"]["executed"] == ["pinned"]
