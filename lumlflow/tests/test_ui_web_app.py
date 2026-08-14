"""What `lumlflow ui` owes the built web app it is about to serve.

A source checkout serves `lumlflow/static` off the disk and nothing rebuilds
it, so an edited frontend goes out the door as whatever was built last. The
layouts here are made by hand with stamped mtimes: nothing reads the real
`frontend`, and nothing runs npm.
"""

import os
from pathlib import Path

import pytest
from lumlflow.cli import WebAppCheck, _refresh_web_app, _web_app_check

_OLD = 1_700_000_000.0
_NEW = 1_800_000_000.0


def _write(path: Path, text: str, stamp: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.utime(path, (stamp, stamp))


def _checkout(
    root: Path,
    *,
    sources: float | None = _OLD,
    dist: float | None = None,
    static: float | None = None,
) -> Path:
    """A project layout: the package, with `frontend` beside it. Returns the
    package directory, which is what the check is handed."""
    package = root / "lumlflow"
    package.mkdir(parents=True)
    if sources is not None:
        _write(root / "frontend" / "src" / "main.ts", "render()", sources)
        _write(root / "frontend" / "package.json", "{}", sources)
    if dist is not None:
        _write(root / "frontend" / "dist" / "index.html", "<html>dist</html>", dist)
        _write(root / "frontend" / "dist" / "assets" / "app.js", "dist", dist)
    if static is not None:
        _write(package / "static" / "index.html", "<html>static</html>", static)
    return package


def test_an_installed_wheel_has_no_sources_to_be_behind(tmp_path: Path) -> None:
    """No `frontend` beside the package: the build came with the wheel and
    there is nothing it could be older than."""
    package = tmp_path / "lumlflow"
    _write(package / "static" / "index.html", "<html>static</html>", _OLD)

    assert _web_app_check(package) == WebAppCheck()


def test_a_build_nobody_copied_over_is_copied_here(tmp_path: Path) -> None:
    """`vite build` writes `frontend/dist`; only packaging copies it across.
    A dev who stopped at the build gets the copy made for them, not a lecture."""
    package = _checkout(tmp_path, sources=_OLD, dist=_NEW, static=_OLD)
    _write(package / "static" / "stale.js", "gone", _OLD)

    check = _web_app_check(package)

    assert check == WebAppCheck(sync_from=tmp_path / "frontend" / "dist")
    assert check.warning is None


def test_the_copy_replaces_what_was_served_and_is_said_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _checkout(tmp_path, sources=_OLD, dist=_NEW, static=_OLD)
    _write(package / "static" / "stale.js", "gone", _OLD)

    _refresh_web_app(package)
    printed = capsys.readouterr()

    assert (package / "static" / "index.html").read_text() == "<html>dist</html>"
    assert (package / "static" / "assets" / "app.js").exists()
    # rmtree, not merge: what the last build left behind does not linger.
    assert not (package / "static" / "stale.js").exists()
    # stdout belongs to the address `ui` prints once it is serving.
    assert printed.out == ""
    assert printed.err.splitlines() == ["web app updated from frontend/dist"]


def test_sources_newer_than_any_build_name_the_rebuild(tmp_path: Path) -> None:
    """The footgun itself: edited frontend, stale build, silence until now."""
    package = _checkout(tmp_path, sources=_NEW, dist=_OLD, static=_OLD)

    check = _web_app_check(package)

    assert check.sync_from is None
    assert check.warning is not None
    assert "npm run build --workspace=lumlflow-ui" in check.warning
    assert "repo root" in check.warning
    assert "daemon" not in check.warning.lower()


def test_a_warning_is_all_it_is_and_it_goes_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _checkout(tmp_path, sources=_NEW, dist=_OLD, static=_OLD)

    _refresh_web_app(package)
    printed = capsys.readouterr()

    assert printed.out == ""
    assert len(printed.err.splitlines()) == 1
    assert "npm run build --workspace=lumlflow-ui" in printed.err


def test_nothing_built_at_all_says_the_browser_gets_nothing(tmp_path: Path) -> None:
    """No static, no dist: the warning is not about staleness — there is no
    web app to serve until someone builds one."""
    package = _checkout(tmp_path, sources=_NEW)

    check = _web_app_check(package)

    assert check.sync_from is None
    assert check.warning is not None
    assert "nothing" in check.warning
    assert "npm run build --workspace=lumlflow-ui" in check.warning


def test_a_build_never_copied_still_beats_no_build(tmp_path: Path) -> None:
    """Static missing but a fresh dist there: copy it, and say nothing about
    a browser getting nothing, because it will not."""
    package = _checkout(tmp_path, sources=_OLD, dist=_NEW)

    assert _web_app_check(package) == WebAppCheck(
        sync_from=tmp_path / "frontend" / "dist"
    )


def test_a_build_that_stands_for_its_sources_is_left_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The everyday case, and the one that must stay quiet."""
    package = _checkout(tmp_path, sources=_OLD, dist=_NEW, static=_NEW)

    check = _web_app_check(package)
    _refresh_web_app(package)
    printed = capsys.readouterr()

    assert check == WebAppCheck()
    assert printed.out == "" and printed.err == ""


def test_a_copy_that_cannot_be_made_is_not_a_failed_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two workspaces starting at once are two copies over one checkout. The
    loser leaves the build that is there standing and says nothing; `ui` is
    never the command that fails because a dev build could not be copied."""
    package = _checkout(tmp_path, sources=_OLD, dist=_NEW, static=_OLD)

    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("someone else got there first")

    monkeypatch.setattr("lumlflow.cli.shutil.copytree", refuse)

    _refresh_web_app(package)
    printed = capsys.readouterr()

    assert (package / "static" / "index.html").read_text() == "<html>static</html>"
    assert printed.out == "" and printed.err == ""
    assert [path.name for path in package.iterdir()] == ["static"]


def test_node_modules_below_the_sources_is_not_walked(tmp_path: Path) -> None:
    """A nested install is thousands of files and none of them are the app."""
    package = _checkout(tmp_path, sources=_OLD, dist=_NEW, static=_NEW)
    _write(tmp_path / "frontend" / "src" / "node_modules" / "x" / "i.js", "x", _NEW * 2)

    assert _web_app_check(package) == WebAppCheck()
