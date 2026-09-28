"""Packaging guarantees: the built web app must reach every artifact.

`lumlflow/static/` is gitignored, `frontend/` needs an npm workspace root that
only the monorepo has, and the server mounts the SPA only if `static/index.html`
exists — three places a missing bundle can pass unnoticed. These tests pin the
build hook's decisions and the pyproject config that carries the bundle.
"""

import subprocess
import tarfile
import tomllib
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from hatch_build import SKIP_ENV_VAR, WORKSPACE_BUILD_ORDER, FrontendBuildHook
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _no_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SKIP_ENV_VAR, raising=False)


def make_project(
    tmp_path: Path,
    *,
    frontend: bool,
    workspace_root: bool,
    bundle: bool,
) -> Path:
    """Lay out a project root and return it; the hook reads `root/..` too."""
    workspace = tmp_path / "workspace"
    root = workspace / "lumlflow"
    (root / "lumlflow").mkdir(parents=True)

    if frontend:
        (root / "frontend" / "src").mkdir(parents=True)
    if workspace_root:
        (workspace / "package-lock.json").write_text("{}")
    if bundle:
        static_dir = root / "lumlflow" / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<!doctype html>prebuilt")
        (static_dir / "stale-asset.js").write_text("// from an older build")

    return root


def run_hook(root: Path) -> None:
    """Drive `initialize` the way hatchling does, minus the builder machinery."""
    hook = FrontendBuildHook(
        str(root), {}, cast(Any, None), cast(Any, None), str(root), "wheel"
    )
    hook.initialize("standard", {"artifacts": [], "force_include": {}})


class NpmRecorder:
    """Stands in for `subprocess.run`; optionally emits a dist/ like vite would."""

    def __init__(self, dist_dir: Path | None = None) -> None:
        self.commands: list[list[str]] = []
        self.cwds: list[Path] = []
        self._dist_dir = dist_dir

    def __call__(
        self, command: Sequence[str], *, cwd: Path, check: bool
    ) -> subprocess.CompletedProcess[bytes]:
        self.commands.append(list(command))
        self.cwds.append(cwd)
        if self._dist_dir is not None and command[-1] == "--workspace=lumlflow-ui":
            self._dist_dir.mkdir(parents=True, exist_ok=True)
            (self._dist_dir / "index.html").write_text("<!doctype html>fresh")
            (self._dist_dir / "app.js").write_text("// fresh")
        return subprocess.CompletedProcess(list(command), 0)


@pytest.fixture
def npm(monkeypatch: pytest.MonkeyPatch) -> NpmRecorder:
    recorder = NpmRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    return recorder


def test_sdist_install_uses_prebuilt_bundle_quietly(
    tmp_path: Path, npm: NpmRecorder, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, frontend=False, workspace_root=False, bundle=True)

    run_hook(root)

    assert npm.commands == []
    assert capsys.readouterr().out == ""
    index = root / "lumlflow" / "static" / "index.html"
    assert index.read_text().endswith("prebuilt")


def test_no_frontend_and_no_bundle_raises(tmp_path: Path, npm: NpmRecorder) -> None:
    root = make_project(tmp_path, frontend=False, workspace_root=False, bundle=False)

    with pytest.raises(RuntimeError, match="no prebuilt web app"):
        run_hook(root)
    assert npm.commands == []


def test_missing_workspace_root_falls_back_to_bundle_with_notice(
    tmp_path: Path, npm: NpmRecorder, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, frontend=True, workspace_root=False, bundle=True)

    run_hook(root)

    assert npm.commands == []
    notice = capsys.readouterr().out
    assert "NOTICE" in notice
    assert "no npm workspace root" in notice


def test_missing_workspace_root_without_bundle_raises_naming_both_remedies(
    tmp_path: Path, npm: NpmRecorder
) -> None:
    root = make_project(tmp_path, frontend=True, workspace_root=False, bundle=False)

    with pytest.raises(RuntimeError) as excinfo:
        run_hook(root)

    message = str(excinfo.value)
    assert "npm workspace root" in message
    assert "monorepo" in message
    assert "install from an artifact that already carries the bundle" in message
    assert SKIP_ENV_VAR in message
    assert npm.commands == []


def test_opt_out_env_var_skips_the_build_with_a_warning(
    tmp_path: Path,
    npm: NpmRecorder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(SKIP_ENV_VAR, "1")
    root = make_project(tmp_path, frontend=True, workspace_root=True, bundle=False)

    run_hook(root)

    assert npm.commands == []
    warning = capsys.readouterr().out
    assert "WARNING" in warning
    assert "without the web UI" in warning


def test_opt_out_env_var_ignores_other_values(
    tmp_path: Path, npm: NpmRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SKIP_ENV_VAR, "0")
    root = make_project(tmp_path, frontend=False, workspace_root=False, bundle=False)

    with pytest.raises(RuntimeError):
        run_hook(root)


def test_dev_shape_builds_workspaces_in_order_and_replaces_static(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_project(tmp_path, frontend=True, workspace_root=True, bundle=True)
    recorder = NpmRecorder(dist_dir=root / "frontend" / "dist")
    monkeypatch.setattr(subprocess, "run", recorder)

    run_hook(root)

    assert recorder.commands[0] == ["npm", "ci"]
    built = [c[-1].removeprefix("--workspace=") for c in recorder.commands[1:]]
    assert built == list(WORKSPACE_BUILD_ORDER)
    assert all(cwd == root.parent for cwd in recorder.cwds)

    static_dir = root / "lumlflow" / "static"
    assert (static_dir / "index.html").read_text().endswith("fresh")
    assert (static_dir / "app.js").exists()
    assert not (static_dir / "stale-asset.js").exists()


def test_npm_success_without_dist_raises(tmp_path: Path, npm: NpmRecorder) -> None:
    root = make_project(tmp_path, frontend=True, workspace_root=True, bundle=False)

    with pytest.raises(RuntimeError, match="produced no"):
        run_hook(root)


def test_npm_failure_propagates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(command: Sequence[str], *, cwd: Path, check: bool) -> None:
        raise subprocess.CalledProcessError(1, list(command))

    monkeypatch.setattr(subprocess, "run", explode)
    root = make_project(tmp_path, frontend=True, workspace_root=True, bundle=True)

    with pytest.raises(subprocess.CalledProcessError):
        run_hook(root)


def test_pyproject_carries_static_into_every_target() -> None:
    with (REPO_ROOT / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)

    build = config["tool"]["hatch"]["build"]
    assert "/lumlflow/static/**" in build["artifacts"]
    # Target-level `artifacts` would shadow the global list for that target.
    assert "artifacts" not in build["targets"]["sdist"]
    assert "artifacts" not in build["targets"]["wheel"]
    assert build["targets"]["sdist"]["exclude"] == [
        "/frontend",
        "/node_modules",
        "/examples",
    ]
    assert build["hooks"]["custom"]["path"] == "hatch_build.py"


def test_churn_demo_has_an_isolated_project() -> None:
    example = REPO_ROOT / "examples" / "churn"

    assert not (REPO_ROOT / "churn.flow").exists()
    assert (example / "churn.flow").is_dir()
    with (example / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)

    assert set(config["project"]["dependencies"]) == {
        "luml-sdk>=0.2.0,<0.3.0",
        "matplotlib>=3.11.1",
        "pandas>=3.0.5",
        "pyarrow>=25.0.1",
        "scikit-learn>=1.9.0",
    }


def test_distributions_exclude_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SKIP_ENV_VAR, "1")
    sdist = Path(next(SdistBuilder(str(REPO_ROOT)).build(directory=str(tmp_path))))
    wheel = Path(next(WheelBuilder(str(REPO_ROOT)).build(directory=str(tmp_path))))

    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()

    assert all("examples" not in Path(name).parts for name in sdist_names)
    assert all("examples" not in Path(name).parts for name in wheel_names)
