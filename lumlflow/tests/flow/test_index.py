import json
import sqlite3
from pathlib import Path

import pytest
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.store.index import INDEX_SCHEMA_VERSION, Index
from lumlflow.flow.store.models import (
    Adopted,
    AgentBegin,
    BranchArchived,
    BranchCreated,
    CellNoted,
    CellNoteKind,
    CellRemoved,
    EnvChanged,
    FlagSet,
    FlowInit,
    MemoHit,
    Rewound,
    SelectionSet,
    WorkspaceCodeChanged,
    WorktreeBound,
)

from tests.flow.helpers import (
    cell_accepted,
    run_recorded,
    snapshot,
    transaction,
)


@pytest.fixture
def index(tmp_path: Path) -> Index:
    return Index(tmp_path / "store.sqlite")


def rows(index: Index, sql: str, *args: object) -> list[sqlite3.Row]:
    return list(index.conn.execute(sql, args))


class TestFold:
    def test_records_the_transaction_itself(self, index: Index) -> None:
        index.apply(transaction(4, [FlowInit(flow_id="F", name="churn")], intent="new"))

        (row,) = rows(index, "SELECT * FROM transactions")
        assert (row["step"], row["actor"], row["intent"]) == (4, "user", "new")
        assert json.loads(row["ops"])[0]["op"] == "flow_init"
        assert index.last_step == 4

    def test_finds_a_branch_newest_line_at_or_before_a_step(self, index: Index) -> None:
        index.apply(transaction(1, branch="A"))
        index.apply(transaction(2, branch="B"))
        index.apply(transaction(3, branch="A"))
        index.apply(transaction(4))
        index.apply(transaction(5, branch="B"))

        assert index.last_step_on("A", at_or_before=5) == 3
        assert index.last_step_on("A", at_or_before=2) == 1
        assert index.last_step_on("B", at_or_before=1) is None
        assert index.last_step_on("unknown", at_or_before=5) is None

    def test_accepting_a_cell_creates_the_cell_and_its_version(
        self, index: Index
    ) -> None:
        first = cell_accepted(slug="features")
        second = cell_accepted(uid=first.uid, slug="features")
        index.apply(transaction(1, [first]))
        index.apply(transaction(2, [second]))

        (cell,) = rows(index, "SELECT * FROM cells")
        assert (cell["uid"], cell["created_step"]) == (first.uid, 1)
        versions = rows(index, "SELECT * FROM asset_versions ORDER BY created_step")
        assert [version["version_id"] for version in versions] == [
            first.version_id,
            second.version_id,
        ]
        assert json.loads(versions[0]["manifest"])["params"] == {"seed": 1337}

    def test_copied_cells_carry_their_provenance(self, index: Index) -> None:
        origin = cell_accepted(slug="eval")
        copy = cell_accepted(slug="eval_v2", copied_from=origin.uid)
        index.apply(transaction(1, [origin, copy]))

        (row,) = rows(index, "SELECT * FROM cells WHERE uid = ?", copy.uid)
        assert row["copied_from"] == origin.uid

    def test_selection_and_per_branch_removal(self, index: Index) -> None:
        accepted = cell_accepted()
        index.apply(transaction(1, [accepted]))
        index.apply(
            transaction(
                2,
                [
                    SelectionSet(
                        branch_id="main",
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                    ),
                    SelectionSet(
                        branch_id="sweep",
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                    ),
                ],
            )
        )
        index.apply(transaction(3, [CellRemoved(uid=accepted.uid, branch_id="sweep")]))

        remaining = rows(index, "SELECT * FROM selections")
        assert [row["branch_id"] for row in remaining] == ["main"]

    def test_adopt_points_the_selection_at_the_donor_version(
        self, index: Index
    ) -> None:
        winner = cell_accepted(slug="train_model")
        index.apply(transaction(1, [winner]))
        index.apply(
            transaction(
                2,
                [
                    Adopted(
                        branch_id="trunk",
                        uid=winner.uid,
                        version_id=winner.version_id,
                        from_branch_id="sweep",
                    )
                ],
            )
        )

        (row,) = rows(index, "SELECT * FROM selections")
        assert (row["branch_id"], row["version_id"]) == ("trunk", winner.version_id)

    def test_branch_creation_and_archiving(self, index: Index) -> None:
        index.apply(
            transaction(
                1,
                [
                    BranchCreated(branch_id="b1", name="main"),
                    BranchCreated(
                        branch_id="b2", name="sweep", parent_branch_id="b1", fork_step=1
                    ),
                ],
            )
        )
        index.apply(transaction(2, [BranchArchived(branch_id="b2")]))

        archived = rows(index, "SELECT * FROM branches ORDER BY branch_id")
        assert [row["archived"] for row in archived] == [0, 1]
        assert archived[1]["parent_branch_id"] == "b1"

    def test_binding_a_worktree_twice_rebinds_the_one_row(self, index: Index) -> None:
        index.apply(transaction(1, [WorktreeBound(flow_id="flow-1", branch_id="b1")]))
        index.apply(
            transaction(
                2,
                [WorktreeBound(flow_id="flow-1", branch_id="b2", actor="claude-1")],
            )
        )

        (row,) = rows(index, "SELECT * FROM worktrees")
        assert (row["flow_id"], row["branch_id"], row["actor"]) == (
            "flow-1",
            "b2",
            "claude-1",
        )

    def test_a_successful_run_becomes_the_branch_baseline(self, index: Index) -> None:
        accepted = cell_accepted()
        run = run_recorded(
            uid=accepted.uid, version_id=accepted.version_id, branch_id="main"
        )
        index.apply(transaction(1, [accepted, run]))

        (materialization,) = rows(index, "SELECT * FROM materializations")
        assert materialization["state"] == "succeeded"
        assert materialization["cost_seconds"] == 1.5
        (baseline,) = rows(index, "SELECT * FROM baselines")
        assert (baseline["branch_id"], baseline["mat_id"]) == ("main", run.mat_id)

    def test_a_failed_run_becomes_the_baseline_it_observed(self, index: Index) -> None:
        """The baseline is the last materialization observed, not the last that
        worked — staleness derives `failed` from it."""
        accepted = cell_accepted()
        succeeded = run_recorded(
            uid=accepted.uid, version_id=accepted.version_id, branch_id="main"
        )
        failed = run_recorded(
            uid=accepted.uid,
            version_id=accepted.version_id,
            branch_id="main",
            state="failed",
        )
        index.apply(transaction(1, [accepted, succeeded]))

        index.apply(transaction(2, [failed]))

        (baseline,) = rows(index, "SELECT * FROM baselines")
        assert baseline["mat_id"] == failed.mat_id

    def test_a_cancelled_run_moves_no_baseline(self, index: Index) -> None:
        accepted = cell_accepted()
        index.apply(
            transaction(
                1,
                [
                    accepted,
                    run_recorded(
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                        branch_id="main",
                        state="cancelled",
                    ),
                ],
            )
        )

        assert rows(index, "SELECT * FROM baselines") == []

    def test_a_memo_hit_updates_the_baseline_without_a_run(self, index: Index) -> None:
        accepted = cell_accepted()
        run = run_recorded(
            uid=accepted.uid, version_id=accepted.version_id, branch_id="main"
        )
        index.apply(transaction(1, [accepted, run]))
        index.apply(
            transaction(
                2,
                [
                    MemoHit(
                        branch_id="sweep",
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                        memo_key=run.memo_key,
                        mat_id=run.mat_id,
                    )
                ],
            )
        )

        baselines = rows(index, "SELECT * FROM baselines ORDER BY branch_id")
        assert [row["branch_id"] for row in baselines] == ["main", "sweep"]
        assert len(rows(index, "SELECT * FROM materializations")) == 1

    def test_rewind_restores_selections_and_baselines_together(
        self, index: Index
    ) -> None:
        old, new = cell_accepted(), cell_accepted()
        run = run_recorded(uid=old.uid, version_id=old.version_id, branch_id="main")
        index.apply(transaction(1, [old, new]))
        index.apply(
            transaction(
                2,
                [
                    SelectionSet(
                        branch_id="main", uid=new.uid, version_id=new.version_id
                    ),
                    SelectionSet(
                        branch_id="other", uid=new.uid, version_id=new.version_id
                    ),
                ],
            )
        )
        index.apply(
            transaction(
                3,
                [
                    Rewound(
                        branch_id="main",
                        to_step=1,
                        selections={old.uid: old.version_id},
                        baselines={old.uid: run.mat_id},
                    )
                ],
            )
        )

        selections = rows(index, "SELECT * FROM selections ORDER BY branch_id")
        assert [(row["branch_id"], row["uid"]) for row in selections] == [
            ("main", old.uid),
            ("other", new.uid),
        ]
        (baseline,) = rows(index, "SELECT * FROM baselines")
        assert baseline["mat_id"] == run.mat_id

    def test_workspace_code_changes_keep_one_current_row(self, index: Index) -> None:
        index.apply(transaction(1, [WorkspaceCodeChanged(tree_hash="a" * 64)]))
        index.apply(
            transaction(
                2,
                [
                    WorkspaceCodeChanged(
                        tree_hash="b" * 64,
                        previous_tree_hash="a" * 64,
                        changed_paths=["helpers.py"],
                    )
                ],
            )
        )

        (row,) = rows(index, "SELECT * FROM workspace_tree")
        assert row["tree_hash"] == "b" * 64
        assert json.loads(row["changed_paths"]) == ["helpers.py"]

    def test_env_changes_record_the_current_lock_hash(self, index: Index) -> None:
        index.apply(
            transaction(1, [EnvChanged(lock_hash="c" * 64, summary="+lightgbm")])
        )

        (row,) = rows(index, "SELECT * FROM meta WHERE key = 'env_lock_hash'")
        assert row["value"] == "c" * 64

    def test_flagging_a_version_appends_to_its_flags(self, index: Index) -> None:
        accepted = cell_accepted()
        index.apply(transaction(1, [accepted]))
        index.apply(
            transaction(
                2,
                [
                    FlagSet(
                        version_id=accepted.version_id,
                        flag="dangling_ref",
                        detail="did you mean `features.train_split`?",
                    )
                ],
            )
        )

        (row,) = rows(index, "SELECT flags FROM asset_versions")
        assert json.loads(row["flags"]) == [
            {"code": "dangling_ref", "detail": "did you mean `features.train_split`?"}
        ]

    def test_a_transaction_scoped_flag_touches_no_version(self, index: Index) -> None:
        accepted = cell_accepted()
        index.apply(transaction(1, [accepted]))
        index.apply(transaction(2, [FlagSet(flag="mixed_editing_window")]))

        (row,) = rows(index, "SELECT flags FROM asset_versions")
        assert json.loads(row["flags"]) == []

    def test_indexes_a_cell_note_with_its_transaction_scope(self, index: Index) -> None:
        index.apply(
            transaction(
                1,
                [
                    CellNoted(
                        uid="cell-score",
                        kind="projection_completed",
                        sentence="restored score to version 2",
                        version_id="version-2",
                    )
                ],
                actor="system",
                branch="lane-main",
            )
        )

        (row,) = rows(index, "SELECT * FROM cell_notes")
        assert (
            row["branch_id"],
            row["uid"],
            row["kind"],
            row["sentence"],
            row["version_id"],
            row["step"],
            row["actor"],
        ) == (
            "lane-main",
            "cell-score",
            "projection_completed",
            "restored score to version 2",
            "version-2",
            1,
            "system",
        )

    def test_returns_the_latest_note_per_kind_for_one_lane_and_cell(
        self, index: Index
    ) -> None:
        entries: list[tuple[int, str, str, CellNoteKind, str]] = [
            (1, "lane-main", "cell-score", "refresh_failed", "first failure"),
            (2, "lane-exp", "cell-score", "refresh_failed", "lane failure"),
            (3, "lane-main", "cell-report", "refresh_failed", "other cell"),
            (
                4,
                "lane-main",
                "cell-score",
                "projection_completed",
                "restored version",
            ),
            (5, "lane-main", "cell-score", "refresh_failed", "latest failure"),
        ]
        for step, branch, uid, kind, sentence in entries:
            index.apply(
                transaction(
                    step,
                    [CellNoted(uid=uid, kind=kind, sentence=sentence)],
                    actor="system",
                    branch=branch,
                )
            )

        notes = index.cell_notes("lane-main", "cell-score")

        assert [
            (note.kind, note.sentence, note.version_id, note.step, note.actor)
            for note in notes
        ] == [
            ("refresh_failed", "latest failure", None, 5, "system"),
            ("projection_completed", "restored version", None, 4, "system"),
        ]
        assert [
            note.sentence for note in index.cell_notes("lane-exp", "cell-score")
        ] == ["lane failure"]
        assert [
            note.sentence for note in index.cell_notes("lane-main", "cell-report")
        ] == ["other cell"]

    def test_session_ops_are_journal_facts_only(self, index: Index) -> None:
        index.apply(transaction(1, [AgentBegin(actor="claude-1", label="claude")]))

        assert index.last_step == 1
        assert len(rows(index, "SELECT * FROM transactions")) == 1

    def test_a_fork_dense_copies_the_parents_slice(self, index: Index) -> None:
        accepted = cell_accepted()
        run = run_recorded(
            uid=accepted.uid, version_id=accepted.version_id, branch_id="b1"
        )
        index.apply(transaction(1, [BranchCreated(branch_id="b1", name="main")]))
        index.apply(
            transaction(
                2,
                [
                    accepted,
                    SelectionSet(
                        branch_id="b1",
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                    ),
                    run,
                ],
            )
        )

        index.apply(
            transaction(
                3,
                [
                    BranchCreated(
                        branch_id="b2",
                        name="sweep",
                        parent_branch_id="b1",
                        fork_step=3,
                    )
                ],
            )
        )

        assert index.selections("b2") == {accepted.uid: accepted.version_id}
        assert index.baselines("b2") == {accepted.uid: run.mat_id}

    def test_a_rootless_branch_starts_empty(self, index: Index) -> None:
        accepted = cell_accepted()
        index.apply(
            transaction(
                1,
                [
                    accepted,
                    SelectionSet(
                        branch_id="b1",
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                    ),
                ],
            )
        )

        index.apply(transaction(2, [BranchCreated(branch_id="b2", name="other")]))

        assert index.selections("b2") == {}

    def test_removing_a_cell_takes_its_baseline_with_it(self, index: Index) -> None:
        accepted = cell_accepted()
        index.apply(
            transaction(
                1,
                [
                    accepted,
                    SelectionSet(
                        branch_id="main",
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                    ),
                    run_recorded(
                        uid=accepted.uid,
                        version_id=accepted.version_id,
                        branch_id="main",
                    ),
                ],
            )
        )

        index.apply(transaction(2, [CellRemoved(uid=accepted.uid, branch_id="main")]))

        assert index.baselines("main") == {}


class TestProbe:
    def test_reads_the_state_the_transaction_would_land_in(self, index: Index) -> None:
        accepted = cell_accepted()
        pending = transaction(
            1,
            [
                accepted,
                SelectionSet(
                    branch_id="main", uid=accepted.uid, version_id=accepted.version_id
                ),
            ],
        )

        with index.probe(pending) as ahead:
            assert ahead.selections("main") == {accepted.uid: accepted.version_id}

        assert index.selections("main") == {}
        assert index.last_step == 0

    def test_rolls_back_when_the_fold_raises(self, index: Index) -> None:
        accepted = cell_accepted()
        index.apply(transaction(1, [accepted]))

        with pytest.raises(RuntimeError), index.probe(transaction(2)):
            raise RuntimeError("the reader gave up")

        assert index.last_step == 1
        assert len(rows(index, "SELECT * FROM asset_versions")) == 1


class TestValuePins:
    def test_pins_outlive_nothing_but_their_run(self, index: Index) -> None:
        index.pin_values("run-1", ["a" * 64, "b" * 64])
        index.pin_values("run-2", ["b" * 64])

        index.release_values("run-1")

        assert index.pinned_values() == {"b" * 64}

    def test_a_rebuild_drops_pins_because_nothing_is_in_flight(
        self, tmp_path: Path
    ) -> None:
        index = Index(tmp_path / "store.sqlite")
        index.pin_values("run-1", ["a" * 64])
        history = [transaction(1)]

        rebuilt = Index(tmp_path / "rebuilt.sqlite")
        rebuilt.rebuild(history)

        assert rebuilt.pinned_values() == set()


class TestRebuild:
    def test_reproduces_the_incremental_result_exactly(self, tmp_path: Path) -> None:
        accepted = cell_accepted()
        run = run_recorded(
            uid=accepted.uid, version_id=accepted.version_id, branch_id="b1"
        )
        history = [
            transaction(1, [FlowInit(flow_id=new_ulid(), name="churn")]),
            transaction(2, [BranchCreated(branch_id="b1", name="main")]),
            transaction(3, [accepted]),
            transaction(
                4,
                [
                    SelectionSet(
                        branch_id="b1", uid=accepted.uid, version_id=accepted.version_id
                    )
                ],
            ),
            transaction(5, [run]),
        ]
        incremental = Index(tmp_path / "incremental.sqlite")
        for entry in history:
            incremental.apply(entry)

        rebuilt = Index(tmp_path / "rebuilt.sqlite")
        rebuilt.rebuild(history)

        assert snapshot(rebuilt) == snapshot(incremental)


class TestSchemaVersion:
    def test_a_fresh_index_stamps_the_current_version(self, index: Index) -> None:
        assert index.schema_version == INDEX_SCHEMA_VERSION
        assert index.last_step == 0

    def test_an_older_stamp_is_reported_not_upgraded(self, tmp_path: Path) -> None:
        path = tmp_path / "store.sqlite"
        index = Index(path)
        index.apply(transaction(1))
        index.conn.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")
        index.conn.commit()
        index.close()

        assert Index(path).schema_version == 0

    def test_a_file_that_is_not_a_database_reports_unusable(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "store.sqlite"
        path.write_bytes(b"this is not a database")

        stale = Index(path)
        assert stale.schema_version == -1
        assert stale.last_step == 0
