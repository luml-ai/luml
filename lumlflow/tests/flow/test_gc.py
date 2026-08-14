from pathlib import Path

import pytest
from lumlflow.flow.store import gc
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.journal import Journal

from tests.flow.helpers import accept, record_run


@pytest.fixture
def store(tmp_path: Path) -> FlowStore:
    return FlowStore.init(tmp_path / "churn.flow")


class TestSweep:
    def test_a_fresh_store_has_nothing_to_collect(self, store: FlowStore) -> None:
        assert gc.sweep(store) == gc.SweepReport(collected=0, freed_bytes=0, kept=0)

    def test_journal_referenced_values_survive_archives_and_rewinds(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        old = record_run(store, features, content=b"old rows")
        checkpoint = store.next_step - 1
        second = accept(store, "features", uid=features.uid, source="class F: v2")
        rewound_past = record_run(store, second, content=b"new rows")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        archived = record_run(store, second, branch="sweep", content=b"swept rows")
        store.branches.archive("sweep")
        store.branches.rewind(MAIN_BRANCH, to_step=checkpoint)

        report = gc.sweep(store)

        assert report.collected == 0
        for run in (old, rewound_past, archived):
            assert store.values.exists(run.outputs["data"].content_hash)

    def test_an_orphan_from_a_crashed_run_is_collected(self, store: FlowStore) -> None:
        features = accept(store, "features")
        kept = record_run(store, features, content=b"rows")
        orphan = store.values.put(b"staged but never journaled")

        report = gc.sweep(store)

        assert (report.collected, report.kept) == (1, 1)
        assert report.freed_bytes == len(b"staged but never journaled")
        assert not store.values.exists(orphan)
        assert store.values.exists(kept.outputs["data"].content_hash)

    def test_an_in_flight_run_holds_its_values(self, store: FlowStore) -> None:
        staged = store.values.put(b"outputs of a run still executing")
        store.index.pin_values("run-1", [staged])

        assert gc.sweep(store).collected == 0
        assert store.values.exists(staged)

    def test_releasing_a_pin_exposes_a_value_the_run_never_journaled(
        self, store: FlowStore
    ) -> None:
        staged = store.values.put(b"outputs of a run that died")
        store.index.pin_values("run-1", [staged])
        gc.sweep(store)

        store.index.release_values("run-1")

        assert gc.sweep(store).collected == 1
        assert not store.values.exists(staged)

    def test_a_run_finishing_mid_sweep_keeps_its_value(
        self, store: FlowStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins are read before the journal, so a run that lands between the two
        reads is covered by the pin the sweep already saw."""
        staged = store.values.put(b"outputs of a run about to commit")
        store.index.pin_values("run-1", [staged])
        walk = gc.journal_referenced

        def commit_and_release(journal: Journal) -> set[str]:
            store.index.release_values("run-1")
            return walk(journal)

        monkeypatch.setattr(gc, "journal_referenced", commit_and_release)

        gc.sweep(store)

        assert store.values.exists(staged)

    def test_a_run_starting_mid_sweep_keeps_its_value(
        self, store: FlowStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Blobs are listed before the pins are read, so a run that pins and
        stages between the two is invisible to this sweep rather than its
        victim."""
        walk = gc.journal_referenced
        started: dict[str, str] = {}

        def pin_then_stage(journal: Journal) -> set[str]:
            digest = store.values.put(b"outputs of a run just started")
            store.index.pin_values("run-1", [digest])
            started["digest"] = digest
            return walk(journal)

        monkeypatch.setattr(gc, "journal_referenced", pin_then_stage)

        gc.sweep(store)

        assert store.values.exists(started["digest"])

    def test_objects_previews_and_logs_are_never_pruned(self, store: FlowStore) -> None:
        orphans = [
            area.put(b"unreferenced")
            for area in (store.objects, store.previews, store.logs)
        ]

        gc.sweep(store)

        assert all(
            area.exists(digest)
            for area, digest in zip(
                (store.objects, store.previews, store.logs), orphans, strict=True
            )
        )

    def test_the_journal_is_never_pruned(self, store: FlowStore) -> None:
        features = accept(store, "features")
        record_run(store, features, content=b"rows")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        store.branches.archive("sweep")
        before = store.journal.path.read_bytes()

        gc.sweep(store)

        assert store.journal.path.read_bytes() == before
        assert [line.step for line in store.journal.replay()] == list(
            range(1, store.next_step)
        )

    def test_a_value_shared_by_two_branches_survives_one_of_them_going_away(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        run = record_run(store, features, content=b"shared rows")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        store.branches.delete("features", branch="sweep")

        gc.sweep(store)

        assert store.values.exists(run.outputs["data"].content_hash)

    def test_staging_areas_are_left_alone(self, store: FlowStore) -> None:
        staging = store.values.root / "tmp" / "half-written.tmp"
        staging.write_bytes(b"partial")

        gc.sweep(store)

        assert staging.exists()
