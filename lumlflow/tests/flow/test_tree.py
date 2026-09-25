from pathlib import Path

import pytest
from lumlflow.flow.dsl.accept import Acceptance
from lumlflow.flow.dsl.tree import scan_workspace, stray_note
from lumlflow.flow.store.flowstore import FlowStore

STRAY = """
class Util:
    '''Looks like a cell, lives outside cells/.'''

    produces = {"data": "asset"}

    def materialize(self, ctx):
        return {"data": 1}
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "helpers.py").write_text("SPLIT = 0.2\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "raw.csv").write_text("a,b\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def store(workspace: Path) -> FlowStore:
    store = FlowStore.init(workspace / "churn.flow")
    Acceptance(store).accept_path(
        _write(
            store.flow_dir / "cells" / "features.py",
            "class Features:\n    def materialize(self, ctx):\n        return {}\n",
        )
    )
    return store


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestScope:
    def test_a_stray_py_inside_the_flow_is_shared_code_with_a_hygiene_note(
        self, workspace: Path, store: FlowStore
    ) -> None:
        stray = _write(store.flow_dir / "util.py", STRAY)
        before = stray.read_bytes()

        tree = scan_workspace(workspace)

        assert "churn.flow/util.py" in tree.files
        assert tree.strays == ["churn.flow/util.py"]
        assert "not a cell" in stray_note(tree.strays[0])
        assert stray.read_bytes() == before  # no uid was ever written back
        assert (
            store.index.conn.execute(
                "SELECT count(*) AS n FROM asset_versions WHERE slug = 'util'"
            ).fetchone()["n"]
            == 0
        )

    def test_cells_are_not_shared_code(self, workspace: Path, store: FlowStore) -> None:
        tree = scan_workspace(workspace)

        assert list(tree.files) == ["helpers.py"]

    def test_a_workspace_cells_directory_is_ordinary_shared_code(
        self, workspace: Path
    ) -> None:
        _write(workspace / "cells" / "shared.py", "X = 1\n")

        assert "cells/shared.py" in scan_workspace(workspace).files

    def test_environments_and_caches_are_never_watched(self, workspace: Path) -> None:
        for excluded in (
            ".venv",
            ".git",
            "node_modules",
            "__pycache__",
            "site-packages",
            "env",
            "venv",
            ".tox",
            "build",
            "dist",
        ):
            _write(workspace / excluded / "ignored.py", "X = 1\n")
        _write(workspace / "custom-environment" / "pyvenv.cfg", "home = /python\n")
        _write(workspace / "custom-environment" / "ignored.py", "X = 1\n")
        _write(workspace / ".gitignore", "generated/\n")
        _write(workspace / "generated" / "ignored.py", "X = 1\n")
        _write(workspace / "src" / "nested" / "deep.py", "Y = 2\n")

        tree = scan_workspace(workspace)

        assert set(tree.files) == {"helpers.py", "src/nested/deep.py"}

    def test_the_store_is_never_part_of_the_tree(
        self, workspace: Path, store: FlowStore
    ) -> None:
        _write(store.store_dir / "kernel" / "scratch.py", "X = 1\n")

        assert list(scan_workspace(workspace).files) == ["helpers.py"]


class TestHash:
    def test_the_hash_moves_only_when_watched_code_does(self, workspace: Path) -> None:
        before = scan_workspace(workspace)
        (workspace / "data" / "raw.csv").write_text("a,b\n1,2\n", encoding="utf-8")

        assert scan_workspace(workspace).tree_hash == before.tree_hash

        (workspace / "helpers.py").write_text("SPLIT = 0.3\n", encoding="utf-8")
        after = scan_workspace(workspace)

        assert after.tree_hash != before.tree_hash
        assert after.changed_paths(before) == ["helpers.py"]

    def test_an_added_helper_is_named_as_the_change(self, workspace: Path) -> None:
        before = scan_workspace(workspace)
        _write(workspace / "features" / "text.py", "def clean(x):\n    return x\n")

        after = scan_workspace(workspace)

        assert after.changed_paths(before) == ["features/text.py"]
        assert after.tree_hash != before.tree_hash
