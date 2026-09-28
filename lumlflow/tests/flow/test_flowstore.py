import json
import os
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from lumlflow.flow.errors import FlowAlreadyExists, FlowError, FlowNotFound
from lumlflow.flow.ids import is_ulid
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.index import INDEX_SCHEMA_VERSION
from lumlflow.flow.store.models import Transaction

from tests.flow.helpers import accept, cell_accepted, transaction

_WINDOWS_ILLEGAL = set('<>:"|?*\\')


@pytest.fixture
def flow_dir(tmp_path: Path) -> Path:
    return tmp_path / "churn.flow"


@pytest.fixture
def store(flow_dir: Path) -> FlowStore:
    return FlowStore.init(flow_dir)


def read_manifest(flow_dir: Path) -> dict[str, object]:
    loaded = yaml.safe_load((flow_dir / "flow.yaml").read_text())
    assert isinstance(loaded, dict)
    return loaded


class TestInit:
    def test_scaffolds_the_flow_layout(self, store: FlowStore) -> None:
        assert (store.flow_dir / "cells").is_dir()
        for area in ("objects", "values", "previews", "logs", "kernel", "worktrees"):
            assert (store.store_dir / area).is_dir()
        assert (store.store_dir / "journal.jsonl").is_file()
        assert (store.store_dir / "store.sqlite").is_file()

    def test_writes_a_flow_manifest_naming_the_flow_after_its_directory(
        self, store: FlowStore
    ) -> None:
        manifest = read_manifest(store.flow_dir)
        assert manifest["name"] == "churn"
        assert manifest["language"] == "python"
        assert manifest["cells"] == {}
        assert is_ulid(str(manifest["flow_id"]))
        assert manifest["settings"] == {
            "eager_cost_threshold_s": 5.0,
            "reactivity": "auto",
            "eager": [],
        }
        assert "order" not in manifest

    def test_takes_an_explicit_name(self, flow_dir: Path) -> None:
        store = FlowStore.init(flow_dir, name="churn-v2")
        assert store.manifest.name == "churn-v2"
        assert read_manifest(flow_dir)["name"] == "churn-v2"

    def test_journals_the_flow_as_the_first_transaction(self, store: FlowStore) -> None:
        (first,) = list(store.journal.replay())
        assert first.step == 1
        assert first.intent == "created flow churn"
        assert first.ops[0].op == "flow_init"
        assert store.next_step == 2

    def test_refuses_a_directory_that_already_holds_a_store(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        with pytest.raises(FlowAlreadyExists):
            FlowStore.init(flow_dir)

    def test_a_clone_keeps_its_committed_identity(self, store: FlowStore) -> None:
        store.manifest.cells["features"] = "01J9W3ZK7QABCDEF0123456789"
        store.save_manifest()
        store.close()
        flow_id = store.manifest.flow_id
        _remove_tree(store.store_dir)

        rebuilt = FlowStore.init(store.flow_dir)

        assert rebuilt.manifest.flow_id == flow_id
        assert rebuilt.manifest.cells == {"features": "01J9W3ZK7QABCDEF0123456789"}

    def test_every_created_path_is_legal_on_windows(self, store: FlowStore) -> None:
        store.objects.put(b"class Features: pass")
        for path in store.flow_dir.rglob("*"):
            assert not set(path.name) & _WINDOWS_ILLEGAL
            assert path.name == path.name.rstrip(" .")


class TestGitignore:
    def test_ignores_the_store_when_the_flow_sits_in_a_repository(
        self, tmp_path: Path, flow_dir: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        FlowStore.init(flow_dir)

        assert (flow_dir / ".gitignore").read_text() == ".lumlflow/\n"

    def test_appends_without_disturbing_existing_rules(
        self, tmp_path: Path, flow_dir: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        flow_dir.mkdir()
        (flow_dir / ".gitignore").write_text("*.log")
        FlowStore.init(flow_dir)

        assert (flow_dir / ".gitignore").read_text() == "*.log\n.lumlflow/\n"

    def test_leaves_an_existing_rule_alone(
        self, tmp_path: Path, flow_dir: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        flow_dir.mkdir()
        (flow_dir / ".gitignore").write_text(".lumlflow\n")
        FlowStore.init(flow_dir)

        assert (flow_dir / ".gitignore").read_text() == ".lumlflow\n"

    def test_writes_nothing_outside_a_repository(self, store: FlowStore) -> None:
        assert not (store.flow_dir / ".gitignore").exists()


class TestCloudSyncWarning:
    def test_warns_on_a_dropbox_marker(self, tmp_path: Path, flow_dir: Path) -> None:
        (tmp_path / ".dropbox").write_text("")
        store = FlowStore.init(flow_dir)

        assert any("Dropbox" in warning for warning in store.warnings)

    def test_warns_inside_a_onedrive_folder(self, tmp_path: Path) -> None:
        store = FlowStore.init(tmp_path / "OneDrive - Contoso" / "churn.flow")

        assert any("OneDrive" in warning for warning in store.warnings)

    def test_stays_quiet_on_ordinary_storage(self, store: FlowStore) -> None:
        assert store.warnings == []


class TestOpen:
    def test_refuses_a_directory_that_is_not_a_flow(self, tmp_path: Path) -> None:
        with pytest.raises(FlowNotFound):
            FlowStore.open(tmp_path)

    def test_resumes_the_step_sequence(self, flow_dir: Path, store: FlowStore) -> None:
        store.commit([cell_accepted()], intent="accept features", actor="user")
        store.close()

        reopened = FlowStore.open(flow_dir)

        assert reopened.manifest.name == "churn"
        assert reopened.next_step == 3
        assert reopened.index.last_step == 2

    def test_restores_a_layout_directory_that_went_missing(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.close()
        (store.store_dir / "values" / "tmp").rmdir()
        (store.store_dir / "values").rmdir()

        reopened = FlowStore.open(flow_dir)

        assert reopened.values.exists(reopened.values.put(b"rows"))

    def test_reports_an_unreadable_manifest(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.close()
        (flow_dir / "flow.yaml").write_text("name: [unterminated\n")

        with pytest.raises(FlowError):
            FlowStore.open(flow_dir)

    def test_preserves_unknown_manifest_and_settings_keys_on_rewrite(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.close()
        manifest = read_manifest(flow_dir)
        manifest["future_section"] = {"format": 3, "enabled": True}
        settings = manifest["settings"]
        assert isinstance(settings, dict)
        settings["future_setting"] = ["one", "two"]
        (flow_dir / "flow.yaml").write_text(yaml.safe_dump(manifest))

        reopened = FlowStore.open(flow_dir)
        reopened.manifest.cells["features"] = "cell-features"
        reopened.manifest.settings.reactivity = "lazy"
        reopened.save_manifest()

        rewritten = read_manifest(flow_dir)
        assert rewritten["future_section"] == {"format": 3, "enabled": True}
        assert rewritten["settings"] == {
            "eager_cost_threshold_s": 5.0,
            "reactivity": "lazy",
            "eager": [],
            "future_setting": ["one", "two"],
        }

    def test_round_trips_decimal_order_keys_without_losing_digits(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        store.manifest.order = {features.uid: "2.00000000000000000000000000005"}
        store.save_manifest()
        store.close()

        reopened = FlowStore.open(flow_dir)

        assert reopened.manifest.order == {
            features.uid: "2.00000000000000000000000000005"
        }
        assert reopened.effective_order()[features.uid] == Decimal(
            "2.00000000000000000000000000005"
        )
        assert reopened.order_after(features.uid) == (
            "2.500000000000000000000000000025"
        )

    def test_a_malformed_top_level_order_value_does_not_block_open(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.close()
        manifest = read_manifest(flow_dir)
        manifest["order"] = ["not", "a", "map"]
        (flow_dir / "flow.yaml").write_text(yaml.safe_dump(manifest))

        reopened = FlowStore.open(flow_dir)
        reopened.save_manifest()

        assert reopened.manifest.order is None
        assert "order" not in read_manifest(flow_dir)

    def test_ignores_bad_and_duplicate_keys_among_unmapped_cells(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        split = accept(store, "split")
        train = accept(store, "train")
        evaluate = accept(store, "evaluate")
        store.manifest.order = {
            features.uid: "2.5",
            train.uid: "not-a-number",
            evaluate.uid: str(store.index.creation_steps()[split.uid]),
        }

        order = store.effective_order()
        born = store.index.creation_steps()

        assert order == {
            features.uid: Decimal("2.5"),
            split.uid: Decimal(born[split.uid]),
            train.uid: Decimal(born[train.uid]),
            evaluate.uid: Decimal(born[evaluate.uid]),
        }

    def test_drops_an_order_entry_for_a_uid_no_lane_selects(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        store.manifest.order = {
            features.uid: "1.5",
            "01J00000000000000000000GONE": "1.75",
        }

        store.save_manifest()

        assert store.manifest.order == {features.uid: "1.5"}
        assert read_manifest(store.flow_dir)["order"] == {features.uid: "1.5"}

    def test_refuses_a_newer_journal_schema_naming_both_versions(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.close()
        _set_journal_schema_version(flow_dir, 3)

        with pytest.raises(FlowError) as raised:
            FlowStore.open(flow_dir)

        message = str(raised.value)
        assert "schema version 3" in message
        assert "version 2" in message
        assert "corrupt" not in message.lower()

    def test_refuses_an_older_journal_schema_with_reinitialise_instructions(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.close()
        _set_journal_schema_version(flow_dir, 1)

        with pytest.raises(FlowError) as raised:
            FlowStore.open(flow_dir)

        message = str(raised.value)
        assert "schema version 1" in message
        assert "version 2" in message
        assert f"delete {flow_dir / '.lumlflow'}/" in message
        assert "re-initialise it from cells/ and flow.yaml" in message

    def test_refuses_an_unknown_op_naming_it_even_with_a_caught_up_index(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.commit([cell_accepted()], intent="accept features", actor="user")
        store.close()
        journal_path = flow_dir / ".lumlflow" / "journal.jsonl"
        lines = journal_path.read_bytes().splitlines()
        first = json.loads(lines[0])
        first["ops"].append({"op": "future_launch", "target": "features"})
        lines[0] = json.dumps(first).encode()
        journal_path.write_bytes(b"\n".join(lines) + b"\n")

        with pytest.raises(FlowError, match="future_launch"):
            FlowStore.open(flow_dir)


class TestCommit:
    def test_requires_an_intent(self, store: FlowStore) -> None:
        with pytest.raises(ValueError):
            store.commit([cell_accepted()], intent="   ", actor="user")

    def test_journals_and_indexes_in_one_step(self, store: FlowStore) -> None:
        accepted = cell_accepted(slug="features")
        committed = store.commit(
            [accepted], intent="accept features", actor="claude-1", branch="b1"
        )

        assert committed.step == 2
        assert [entry.step for entry in store.journal.replay()] == [1, 2]
        (row,) = store.index.conn.execute(
            "SELECT * FROM asset_versions WHERE version_id = ?", (accepted.version_id,)
        )
        assert row["slug"] == "features"

    def test_steps_advance_one_at_a_time(self, store: FlowStore) -> None:
        steps = [
            store.commit([cell_accepted()], intent=f"edit {n}", actor="user").step
            for n in range(3)
        ]
        assert steps == [2, 3, 4]


class TestCrashPoints:
    def test_a_failed_fsync_restores_the_journal_before_the_next_commit(
        self, flow_dir: Path, store: FlowStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before = store.journal.path.read_bytes()
        real_fsync = os.fsync
        fail_next = True

        def fail_after_sync(fd: int) -> None:
            nonlocal fail_next
            real_fsync(fd)
            if fail_next:
                fail_next = False
                raise OSError("fsync failed")

        monkeypatch.setattr(os, "fsync", fail_after_sync)

        with pytest.raises(OSError, match="fsync failed"):
            store.commit(
                [cell_accepted(slug="features")], intent="accept", actor="user"
            )

        assert store.journal.path.read_bytes() == before

        committed = store.commit(
            [cell_accepted(slug="metrics")], intent="accept", actor="user"
        )
        assert committed.step == 2
        store.close()

        reopened = FlowStore.open(flow_dir)

        assert [entry.step for entry in reopened.journal.replay()] == [1, 2]
        assert reopened.next_step == 3
        assert _version_slugs(reopened) == ["metrics"]

    def test_a_lost_index_update_is_caught_up_on_the_next_open(
        self, flow_dir: Path, store: FlowStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        accepted = cell_accepted()

        def crash(_transaction: object) -> None:
            raise RuntimeError("crash after the commit point")

        monkeypatch.setattr(store.index, "apply", crash)
        with pytest.raises(RuntimeError):
            store.commit([accepted], intent="accept features", actor="user")
        store.close()

        reopened = FlowStore.open(flow_dir)

        assert reopened.index.last_step == 2
        assert reopened.next_step == 3
        assert _version_slugs(reopened) == [accepted.slug]

    def test_a_lost_index_update_is_rebuilt_before_the_next_commit(
        self, store: FlowStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        healthy = store.index.apply

        def crash_once(transaction: Transaction) -> None:
            monkeypatch.setattr(store.index, "apply", healthy)
            raise sqlite3.OperationalError("disk I/O error")

        monkeypatch.setattr(store.index, "apply", crash_once)
        with pytest.raises(sqlite3.OperationalError):
            store.commit([cell_accepted(slug="features")], intent="a", actor="user")

        store.commit([cell_accepted(slug="metrics")], intent="b", actor="user")

        assert _version_slugs(store) == ["features", "metrics"]
        assert store.index.last_step == 3

    def test_a_torn_trailing_line_is_dropped_and_the_index_matches(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.commit([cell_accepted(slug="features")], intent="accept", actor="user")
        store.close()
        with (flow_dir / ".lumlflow" / "journal.jsonl").open("ab") as handle:
            handle.write(b'{"step":3,"ts":"2026-08-12T09:00:03+00:0')

        reopened = FlowStore.open(flow_dir)

        assert [entry.step for entry in reopened.journal.replay()] == [1, 2]
        assert reopened.index.last_step == 2
        assert reopened.next_step == 3

    def test_an_index_ahead_of_the_journal_is_rebuilt_from_it(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.commit([cell_accepted(slug="features")], intent="accept", actor="user")
        store.commit([cell_accepted(slug="metrics")], intent="accept", actor="user")
        store.close()
        journal_path = flow_dir / ".lumlflow" / "journal.jsonl"
        kept = journal_path.read_bytes().splitlines(keepends=True)[:2]
        journal_path.write_bytes(b"".join(kept))

        reopened = FlowStore.open(flow_dir)

        assert reopened.index.last_step == 2
        assert _version_slugs(reopened) == ["features"]

    def test_an_index_of_the_wrong_schema_version_is_rebuilt(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.commit([cell_accepted(slug="features")], intent="accept", actor="user")
        store.close()
        index_path = flow_dir / ".lumlflow" / "store.sqlite"
        with sqlite3.connect(index_path) as conn:
            conn.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")

        reopened = FlowStore.open(flow_dir)

        assert reopened.index.schema_version == INDEX_SCHEMA_VERSION
        assert reopened.index.last_step == 2
        assert _version_slugs(reopened) == ["features"]

    def test_an_unreadable_index_is_rebuilt_from_the_journal(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.commit([cell_accepted(slug="features")], intent="accept", actor="user")
        store.close()
        (flow_dir / ".lumlflow" / "store.sqlite").write_bytes(b"not a database")

        reopened = FlowStore.open(flow_dir)

        assert reopened.index.last_step == 2
        assert _version_slugs(reopened) == ["features"]

    def test_blobs_staged_without_a_commit_stay_unreferenced(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        digest = store.objects.put(b"class Features: pass")
        store.close()

        reopened = FlowStore.open(flow_dir)

        assert reopened.objects.exists(digest)
        assert reopened.index.last_step == 1
        assert _version_slugs(reopened) == []

    def test_the_index_is_rebuilt_when_it_is_missing_entirely(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.commit([cell_accepted(slug="features")], intent="accept", actor="user")
        store.close()
        (flow_dir / ".lumlflow" / "store.sqlite").unlink()

        reopened = FlowStore.open(flow_dir)

        assert reopened.index.last_step == 2
        assert _version_slugs(reopened) == ["features"]

    def test_a_journal_written_by_hand_replays_into_a_fresh_index(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        store.close()
        entry = transaction(2, [cell_accepted(slug="metrics")])
        with (flow_dir / ".lumlflow" / "journal.jsonl").open("ab") as handle:
            handle.write(entry.to_line())

        reopened = FlowStore.open(flow_dir)

        assert _version_slugs(reopened) == ["metrics"]
        assert reopened.next_step == 3


def _version_slugs(store: FlowStore) -> list[str]:
    return [
        row["slug"]
        for row in store.index.conn.execute(
            "SELECT slug FROM asset_versions ORDER BY created_step"
        )
    ]


def _set_journal_schema_version(flow_dir: Path, version: int) -> None:
    journal_path = flow_dir / ".lumlflow" / "journal.jsonl"
    lines = journal_path.read_bytes().splitlines()
    first = json.loads(lines[0])
    flow_init = next(op for op in first["ops"] if op["op"] == "flow_init")
    flow_init["schema_version"] = version
    lines[0] = json.dumps(first).encode()
    journal_path.write_bytes(b"\n".join(lines) + b"\n")


def _remove_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        child.rmdir() if child.is_dir() else child.unlink()
    path.rmdir()
