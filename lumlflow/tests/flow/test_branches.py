from pathlib import Path

import pytest
from lumlflow.flow.errors import (
    AdoptConflict,
    BranchAlreadyExists,
    BranchNotFound,
    CellNotFound,
    RewindTargetNotFound,
)
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    MemoHit,
    SelectionSet,
    Transaction,
    WorkspaceCodeChanged,
)

from tests.flow.helpers import (
    accept,
    input_ref,
    record_run,
    run_recorded,
    snapshot,
)


@pytest.fixture
def flow_dir(tmp_path: Path) -> Path:
    return tmp_path / "churn.flow"


@pytest.fixture
def store(flow_dir: Path) -> FlowStore:
    return FlowStore.init(flow_dir)


def selections(store: FlowStore, branch: str) -> dict[str, str]:
    return store.index.selections(store.branches.get(branch).branch_id)


def baselines(store: FlowStore, branch: str) -> dict[str, str]:
    return store.index.baselines(store.branches.get(branch).branch_id)


def last(store: FlowStore) -> Transaction:
    return list(store.journal.replay())[-1]


def _count(store: FlowStore, table: str) -> int:
    (row,) = store.index.conn.execute(f"SELECT count(*) AS n FROM {table}")
    return int(row["n"])


def values_bytes(store: FlowStore) -> int:
    return sum(
        blob.stat().st_size for blob in store.values.root.rglob("*") if blob.is_file()
    )


class TestInit:
    def test_a_new_flow_is_born_on_main(self, store: FlowStore) -> None:
        main = store.branches.get(MAIN_BRANCH)

        assert (main.parent_branch_id, main.archived) == (None, False)
        assert selections(store, MAIN_BRANCH) == {}

    def test_an_unknown_branch_is_named_in_the_error(self, store: FlowStore) -> None:
        with pytest.raises(BranchNotFound, match="sweep"):
            store.branches.get("sweep")


class TestFork:
    def test_twenty_forks_cost_rows_and_no_bytes(self, store: FlowStore) -> None:
        features = accept(store, "features")
        accept(store, "plot")
        record_run(store, features, content=b"x" * 4096)
        before = values_bytes(store)

        for index in range(20):
            store.branches.fork(f"sweep/lr{index}", from_branch=MAIN_BRANCH)

        assert values_bytes(store) == before
        assert all(
            len(entry.ops) == 1
            for entry in store.journal.replay()
            if entry.intent.startswith("forked")
        )
        assert len(store.index.branches()) == 21
        assert _count(store, "selections") == 21 * 2
        assert _count(store, "baselines") == 21

    def test_a_fork_inherits_the_parents_selections_and_baselines(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        accept(store, "plot")
        record_run(store, features)

        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        assert selections(store, "sweep") == selections(store, MAIN_BRANCH)
        assert baselines(store, "sweep") == baselines(store, MAIN_BRANCH)

    def test_forked_selections_are_pinned(self, store: FlowStore) -> None:
        accept(store, "features")
        sweep = store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        pins = [
            row["pinned"]
            for row in store.index.conn.execute(
                "SELECT pinned FROM selections WHERE branch_id = ?", (sweep.branch_id,)
            )
        ]
        assert pins == [1]

    def test_a_fork_records_where_it_split(self, store: FlowStore) -> None:
        accept(store, "features")
        main = store.branches.get(MAIN_BRANCH)

        sweep = store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        assert sweep.parent_branch_id == main.branch_id
        assert sweep.fork_step == last(store).step
        assert last(store).intent == "started sweep from main"

    def test_editing_on_a_fork_leaves_the_parent_alone(self, store: FlowStore) -> None:
        first = accept(store, "features")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        second = accept(
            store, "features", uid=first.uid, source="class F: v2", branch="sweep"
        )

        assert selections(store, "sweep") == {first.uid: second.version_id}
        assert selections(store, MAIN_BRANCH) == {first.uid: first.version_id}

    def test_a_later_parent_edit_does_not_reach_the_fork(
        self, store: FlowStore
    ) -> None:
        first = accept(store, "features")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        accept(store, "features", uid=first.uid, source="class F: v2")
        accept(store, "plot")

        assert selections(store, "sweep") == {first.uid: first.version_id}

    def test_a_name_can_only_be_taken_once(self, store: FlowStore) -> None:
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        with pytest.raises(BranchAlreadyExists, match="sweep"):
            store.branches.fork("sweep", from_branch=MAIN_BRANCH)

    def test_forking_from_an_unknown_branch_is_refused(self, store: FlowStore) -> None:
        with pytest.raises(BranchNotFound):
            store.branches.fork("sweep", from_branch="ghost")


class TestSwitch:
    def test_binding_the_worktree_is_the_whole_store_side_of_a_checkout(
        self, store: FlowStore
    ) -> None:
        first = accept(store, "features")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        store.branches.switch("sweep")

        bound = store.branches.bound_branch()
        assert bound is not None and bound.name == "sweep"
        assert selections(store, MAIN_BRANCH) == {first.uid: first.version_id}

    def test_nothing_is_bound_until_a_checkout(self, store: FlowStore) -> None:
        assert store.branches.bound_branch() is None

    def test_switching_again_moves_the_one_binding(self, store: FlowStore) -> None:
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        store.branches.switch("sweep")

        store.branches.switch(MAIN_BRANCH)

        bound = store.branches.bound_branch()
        assert bound is not None and bound.name == MAIN_BRANCH
        assert len(list(store.index.conn.execute("SELECT * FROM worktrees"))) == 1

    def test_switching_to_an_unknown_branch_is_refused(self, store: FlowStore) -> None:
        with pytest.raises(BranchNotFound):
            store.branches.switch("ghost")


class TestArchive:
    def test_archiving_marks_the_branch(self, store: FlowStore) -> None:
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        assert store.branches.archive("sweep").archived is True
        assert last(store).intent == "archived sweep"

    def test_archiving_twice_journals_once(self, store: FlowStore) -> None:
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        store.branches.archive("sweep")
        step = store.next_step

        store.branches.archive("sweep")

        assert store.next_step == step


class TestRewind:
    def test_rewind_restores_selections_and_baselines_without_recomputing(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        first_run = record_run(store, features, content=b"first")
        checkpoint = last(store).step
        second = accept(store, "features", uid=features.uid, source="class F: v2")
        second_run = record_run(store, second, content=b"second")
        accept(store, "expensive_leaf")

        result = store.branches.rewind(MAIN_BRANCH, to_step=checkpoint)

        assert result.selections == {features.uid: features.version_id}
        assert result.baselines == {features.uid: first_run.mat_id}
        assert selections(store, MAIN_BRANCH) == result.selections
        assert baselines(store, MAIN_BRANCH) == result.baselines
        assert [op.op for op in last(store).ops] == ["rewound"]
        assert store.values.exists(first_run.outputs["data"].content_hash)
        assert store.values.exists(second_run.outputs["data"].content_hash)

    def test_an_unmaterialized_leaf_keeps_every_transaction_unsettled(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        accept(store, "expensive_leaf")
        record_run(store, features)

        store.branches.rewind(MAIN_BRANCH, to_step=store.next_step - 1)

        assert not any(entry.settled for entry in store.journal.replay())

    def test_rewind_brings_a_deleted_cell_back(self, store: FlowStore) -> None:
        features = accept(store, "features")
        run = record_run(store, features)
        checkpoint = last(store).step
        store.branches.delete("features", branch=MAIN_BRANCH)

        store.branches.rewind(MAIN_BRANCH, to_step=checkpoint)

        assert selections(store, MAIN_BRANCH) == {features.uid: features.version_id}
        assert baselines(store, MAIN_BRANCH) == {features.uid: run.mat_id}

    def test_a_second_rewind_replays_the_first(self, store: FlowStore) -> None:
        features = accept(store, "features")
        record_run(store, features)
        checkpoint = last(store).step
        accept(store, "plot")
        store.branches.rewind(MAIN_BRANCH, to_step=checkpoint)
        rewind_step = last(store).step
        accept(store, "metrics")

        store.branches.rewind(MAIN_BRANCH, to_step=rewind_step)

        assert selections(store, MAIN_BRANCH) == {features.uid: features.version_id}

    def test_rewind_leaves_other_branches_where_they_are(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        checkpoint = last(store).step
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        edited = accept(
            store, "features", uid=features.uid, source="class F: v2", branch="sweep"
        )
        accept(store, "plot")

        store.branches.rewind(MAIN_BRANCH, to_step=checkpoint)

        assert selections(store, "sweep") == {features.uid: edited.version_id}

    def test_a_step_outside_the_journal_is_refused(self, store: FlowStore) -> None:
        with pytest.raises(RewindTargetNotFound):
            store.branches.rewind(MAIN_BRANCH, to_step=store.next_step)
        with pytest.raises(RewindTargetNotFound):
            store.branches.rewind(MAIN_BRANCH, to_step=0)

    def test_a_branch_cannot_rewind_past_its_own_fork(self, store: FlowStore) -> None:
        accept(store, "features")
        before_fork = last(store).step
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        with pytest.raises(RewindTargetNotFound, match="sweep"):
            store.branches.rewind("sweep", to_step=before_fork)


class TestAdopt:
    @pytest.fixture
    def sweep(self, store: FlowStore) -> str:
        accept(store, "train_model")
        store.branches.fork("sweep/lr3", from_branch=MAIN_BRANCH)
        return "sweep/lr3"

    def test_adopting_the_winner_points_the_selection_at_its_version(
        self, store: FlowStore, sweep: str
    ) -> None:
        uid = store.branches.resolve(MAIN_BRANCH, "train_model")
        winner = accept(
            store, "train_model", uid=uid, source="class T: lr3", branch=sweep
        )

        result = store.branches.adopt(
            "train_model", from_branch=sweep, to_branch=MAIN_BRANCH
        )

        assert result.version_id == winner.version_id
        assert selections(store, MAIN_BRANCH) == {uid: winner.version_id}
        assert [op.op for op in last(store).ops] == ["adopted"]
        assert last(store).intent == "adopted train_model from sweep/lr3"

    def test_edits_on_both_sides_stop_at_a_conflict(
        self, store: FlowStore, sweep: str
    ) -> None:
        uid = store.branches.resolve(MAIN_BRANCH, "train_model")
        accept(store, "train_model", uid=uid, source="class T: lr3", branch=sweep)
        mine = accept(store, "train_model", uid=uid, source="class T: mine")
        step = store.next_step

        with pytest.raises(AdoptConflict) as raised:
            store.branches.adopt(
                "train_model", from_branch=sweep, to_branch=MAIN_BRANCH
            )

        assert raised.value.definition is True
        assert "pick a side" in str(raised.value)
        assert store.next_step == step
        assert selections(store, MAIN_BRANCH) == {uid: mine.version_id}

    def test_a_conflict_resolves_by_taking_the_incoming_side(
        self, store: FlowStore, sweep: str
    ) -> None:
        uid = store.branches.resolve(MAIN_BRANCH, "train_model")
        theirs = accept(
            store, "train_model", uid=uid, source="class T: lr3", branch=sweep
        )
        accept(store, "train_model", uid=uid, source="class T: mine")

        store.branches.adopt(
            "train_model", from_branch=sweep, to_branch=MAIN_BRANCH, force=True
        )

        assert selections(store, MAIN_BRANCH) == {uid: theirs.version_id}

    def test_an_edit_that_changes_no_behaviour_is_not_a_conflict(
        self, store: FlowStore, sweep: str
    ) -> None:
        uid = store.branches.resolve(MAIN_BRANCH, "train_model")
        theirs = accept(
            store, "train_model", uid=uid, source="class T: lr3", branch=sweep
        )
        accept(store, "train_model", uid=uid, source="class Train_Model: pass")

        store.branches.adopt("train_model", from_branch=sweep, to_branch=MAIN_BRANCH)

        assert selections(store, MAIN_BRANCH) == {uid: theirs.version_id}

    def test_siblings_diff_against_the_state_they_both_forked_from(
        self, store: FlowStore
    ) -> None:
        original = accept(store, "train_model")
        store.branches.fork("left", from_branch=MAIN_BRANCH)
        store.branches.fork("right", from_branch=MAIN_BRANCH)
        accept(
            store,
            "train_model",
            uid=original.uid,
            source="class T: left",
            branch="left",
        )
        accept(
            store,
            "train_model",
            uid=original.uid,
            source="class T: right",
            branch="right",
        )

        with pytest.raises(AdoptConflict):
            store.branches.adopt("train_model", from_branch="left", to_branch="right")

    def test_siblings_that_split_at_different_steps_share_the_earlier_state(
        self, store: FlowStore
    ) -> None:
        original = accept(store, "train_model")
        store.branches.fork("left", from_branch=MAIN_BRANCH)
        newer = accept(store, "train_model", uid=original.uid, source="class T: main2")
        store.branches.fork("right", from_branch=MAIN_BRANCH)

        store.branches.adopt("train_model", from_branch="left", to_branch="right")

        assert selections(store, "right") == {original.uid: original.version_id}
        assert newer.version_id != original.version_id

    def test_a_fork_of_a_fork_adopts_back_onto_an_untouched_trunk(
        self, store: FlowStore
    ) -> None:
        original = accept(store, "train_model")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        accept(
            store,
            "train_model",
            uid=original.uid,
            source="class T: swept",
            branch="sweep",
        )
        store.branches.fork("sweep/lr3", from_branch="sweep")
        winner = accept(
            store,
            "train_model",
            uid=original.uid,
            source="class T: lr3",
            branch="sweep/lr3",
        )

        store.branches.adopt(
            "train_model", from_branch="sweep/lr3", to_branch=MAIN_BRANCH
        )

        assert selections(store, MAIN_BRANCH) == {original.uid: winner.version_id}

    def test_one_sibling_editing_is_not_a_conflict(self, store: FlowStore) -> None:
        original = accept(store, "train_model")
        store.branches.fork("left", from_branch=MAIN_BRANCH)
        store.branches.fork("right", from_branch=MAIN_BRANCH)
        winner = accept(
            store,
            "train_model",
            uid=original.uid,
            source="class T: left",
            branch="left",
        )

        store.branches.adopt("train_model", from_branch="left", to_branch="right")

        assert selections(store, "right") == {original.uid: winner.version_id}

    def test_a_cell_the_target_never_had_is_adopted_without_a_conflict(
        self, store: FlowStore, sweep: str
    ) -> None:
        extra = accept(store, "holdout_eval", branch=sweep)

        result = store.branches.adopt(
            "holdout_eval", from_branch=sweep, to_branch=MAIN_BRANCH
        )

        assert result.version_id == extra.version_id
        assert extra.uid in selections(store, MAIN_BRANCH)

    def test_a_reference_naming_a_different_cell_here_is_a_conflict(
        self, store: FlowStore
    ) -> None:
        theirs = accept(store, "features", branch=MAIN_BRANCH)
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        accept(
            store,
            "holdout_eval",
            branch="sweep",
            consumes={"train": "features.data"},
            bound_to={"train": theirs.uid},
        )
        store.branches.delete("features", branch=MAIN_BRANCH)
        accept(store, "features", branch=MAIN_BRANCH)

        with pytest.raises(AdoptConflict) as raised:
            store.branches.adopt(
                "holdout_eval", from_branch="sweep", to_branch=MAIN_BRANCH
            )

        assert raised.value.namespace == ("features.data",)
        assert "features.data names a different cell on main" in str(raised.value)

    def test_an_adopt_that_moves_a_name_reports_the_consumers_to_re_accept(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        accept(
            store,
            "plot_curves",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        accept(store, "raw_features", uid=features.uid, branch="sweep")

        result = store.branches.adopt(
            "raw_features", from_branch="sweep", to_branch=MAIN_BRANCH
        )

        assert result.slug == "raw_features"
        assert result.reaccept == ["plot_curves"]

    def test_an_adopt_that_keeps_the_name_re_accepts_nobody(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        accept(
            store,
            "plot_curves",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        accept(
            store, "features", uid=features.uid, source="class F: v2", branch="sweep"
        )

        result = store.branches.adopt(
            "features", from_branch="sweep", to_branch=MAIN_BRANCH
        )

        assert result.reaccept == []

    def test_a_cell_created_after_the_fork_still_gets_a_three_way_conflict(
        self, store: FlowStore
    ) -> None:
        store.branches.fork("exp", from_branch=MAIN_BRANCH)
        original = accept(store, "train_model")
        store.branches.adopt("train_model", from_branch=MAIN_BRANCH, to_branch="exp")
        mine = accept(store, "train_model", uid=original.uid, source="class T: mine")
        accept(
            store, "train_model", uid=original.uid, source="class T: exp", branch="exp"
        )

        with pytest.raises(AdoptConflict) as raised:
            store.branches.adopt(
                "train_model", from_branch=MAIN_BRANCH, to_branch="exp"
            )

        assert raised.value.definition is True
        assert selections(store, MAIN_BRANCH) == {original.uid: mine.version_id}

    def test_an_earlier_adopt_moves_the_base_forward(self, store: FlowStore) -> None:
        original = accept(store, "train_model")
        store.branches.fork("exp", from_branch=MAIN_BRANCH)
        store.branches.adopt("train_model", from_branch=MAIN_BRANCH, to_branch="exp")
        newer = accept(store, "train_model", uid=original.uid, source="class T: v2")

        store.branches.adopt("train_model", from_branch=MAIN_BRANCH, to_branch="exp")

        assert selections(store, "exp") == {original.uid: newer.version_id}

    def test_a_name_already_taken_here_is_a_conflict(self, store: FlowStore) -> None:
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        accept(store, "features", branch="sweep")
        mine = accept(store, "features", branch=MAIN_BRANCH)

        with pytest.raises(AdoptConflict) as raised:
            store.branches.adopt("features", from_branch="sweep", to_branch=MAIN_BRANCH)

        assert raised.value.namespace == ("features",)
        assert store.branches.resolve(MAIN_BRANCH, "features") == mine.uid

    def test_a_name_forced_in_over_another_asks_to_be_re_accepted(
        self, store: FlowStore
    ) -> None:
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        theirs = accept(store, "features", branch="sweep")
        accept(store, "features", branch=MAIN_BRANCH)

        result = store.branches.adopt(
            "features", from_branch="sweep", to_branch=MAIN_BRANCH, force=True
        )

        assert result.reaccept == ["features"]
        assert theirs.uid in selections(store, MAIN_BRANCH)

    def test_an_upstream_missing_here_adopts_but_asks_to_re_accept(
        self, store: FlowStore
    ) -> None:
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        features = accept(store, "features", branch="sweep")
        accept(
            store,
            "holdout_eval",
            branch="sweep",
            consumes={"train": "features.data"},
            bound_to={"train": features.uid},
        )

        result = store.branches.adopt(
            "holdout_eval", from_branch="sweep", to_branch=MAIN_BRANCH
        )

        assert result.namespace_conflicts == []
        assert result.reaccept == ["holdout_eval"]

    def test_a_reference_that_only_resolves_here_asks_to_be_re_accepted(
        self, store: FlowStore
    ) -> None:
        accept(store, "features", branch=MAIN_BRANCH)
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        store.branches.delete("features", branch="sweep")
        accept(
            store,
            "holdout_eval",
            branch="sweep",
            consumes={"train": "features.data"},
            bound_to={"train": None},  # dangling where it was written
        )

        result = store.branches.adopt(
            "holdout_eval", from_branch="sweep", to_branch=MAIN_BRANCH
        )

        assert result.namespace_conflicts == []
        assert result.reaccept == ["holdout_eval"]

    def test_a_forced_rebind_re_accepts_the_adopted_cell_itself(
        self, store: FlowStore
    ) -> None:
        theirs = accept(store, "features", branch=MAIN_BRANCH)
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        accept(
            store,
            "holdout_eval",
            branch="sweep",
            consumes={"train": "features.data"},
            bound_to={"train": theirs.uid},
        )
        store.branches.delete("features", branch=MAIN_BRANCH)
        accept(store, "features", branch=MAIN_BRANCH)

        result = store.branches.adopt(
            "holdout_eval", from_branch="sweep", to_branch=MAIN_BRANCH, force=True
        )

        assert result.reaccept == ["holdout_eval"]

    def test_an_unknown_cell_is_named_in_the_error(
        self, store: FlowStore, sweep: str
    ) -> None:
        with pytest.raises(CellNotFound, match="holdout_eval"):
            store.branches.adopt(
                "holdout_eval", from_branch=sweep, to_branch=MAIN_BRANCH
            )

    def test_adopt_needs_two_branches(self, store: FlowStore) -> None:
        accept(store, "train_model")

        with pytest.raises(ValueError):
            store.branches.adopt(
                "train_model", from_branch=MAIN_BRANCH, to_branch=MAIN_BRANCH
            )


class TestDelete:
    def test_delete_is_local_to_the_branch_and_names_the_danglers(
        self, store: FlowStore
    ) -> None:
        metrics = accept(store, "metrics")
        accept(
            store,
            "plot_curves",
            consumes={"summary": "metrics.data"},
            bound_to={"summary": metrics.uid},
        )
        store.branches.fork("b", from_branch=MAIN_BRANCH)

        result = store.branches.delete("metrics", branch=MAIN_BRANCH)

        assert result.dangling == ["plot_curves"]
        assert metrics.uid not in selections(store, MAIN_BRANCH)
        assert metrics.uid in selections(store, "b")
        assert last(store).intent == "deleted metrics from main"

    def test_delete_drops_the_branchs_baseline_too(self, store: FlowStore) -> None:
        metrics = accept(store, "metrics")
        record_run(store, metrics)

        store.branches.delete("metrics", branch=MAIN_BRANCH)

        assert baselines(store, MAIN_BRANCH) == {}

    def test_a_consumer_using_a_bare_reference_is_named_too(
        self, store: FlowStore
    ) -> None:
        metrics = accept(store, "metrics")
        accept(
            store,
            "plot_curves",
            consumes={"summary": "summary"},
            bound_to={"summary": metrics.uid},
        )

        result = store.branches.delete("metrics", branch=MAIN_BRANCH)

        assert result.dangling == ["plot_curves"]

    def test_deleting_an_unknown_cell_is_refused(self, store: FlowStore) -> None:
        with pytest.raises(CellNotFound, match="ghost"):
            store.branches.delete("ghost", branch=MAIN_BRANCH)


class TestSettled:
    def test_a_whole_materialized_slice_settles_its_transaction(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        assert last(store).settled is False

        record_run(store, features)

        assert last(store).settled is True

    def test_an_unmaterialized_cell_unsettles_the_branch(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        record_run(store, features)

        accept(store, "expensive_leaf")

        assert last(store).settled is False

    def test_a_rematerialized_parent_unsettles_its_consumer(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        first = record_run(store, features, content=b"first")
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        record_run(store, plot, inputs={"rows": input_ref(first)})
        assert last(store).settled is True

        record_run(store, features, content=b"second")

        assert last(store).settled is False

    def test_a_rerun_producing_the_same_bytes_stays_settled(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        first = record_run(store, features, content=b"same")
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        record_run(store, plot, inputs={"rows": input_ref(first)})

        record_run(store, features, content=b"same")

        assert last(store).settled is True

    def test_a_comment_only_edit_leaves_the_branch_whole(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features", source="class F: pass")
        record_run(store, features)

        accept(store, "features", uid=features.uid, source="class F: pass")

        assert last(store).settled is True

    def test_a_selection_ahead_of_its_materialization_is_not_settled(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        record_run(store, features)

        accept(store, "features", uid=features.uid, source="class F: v2")

        assert last(store).settled is False

    def test_a_workspace_code_change_unsettles_what_ran_before_it(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        record_run(store, features)
        main = store.branches.get(MAIN_BRANCH).branch_id

        store.commit(
            [WorkspaceCodeChanged(tree_hash="h2" * 32, changed_paths=["helpers.py"])],
            intent="helpers.py changed",
            actor="user",
        )
        store.commit(
            [
                SelectionSet(
                    branch_id=main, uid=features.uid, version_id=features.version_id
                )
            ],
            intent="touch the branch",
            actor="user",
            branch=main,
        )

        assert last(store).settled is False

    def test_a_memo_hit_baseline_leaves_the_branch_whole(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        shared = record_run(store, features)
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        twin = accept(store, "features", uid=features.uid, branch="sweep")
        sweep = store.branches.get("sweep").branch_id

        store.commit(
            [
                MemoHit(
                    branch_id=sweep,
                    uid=features.uid,
                    version_id=twin.version_id,
                    memo_key=shared.memo_key,
                    mat_id=shared.mat_id,
                )
            ],
            intent="reused the cached features",
            actor="user",
            branch=sweep,
        )

        assert last(store).settled is True

    def test_an_empty_branch_is_no_checkpoint(self, store: FlowStore) -> None:
        assert last(store).settled is False

        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        assert last(store).settled is False

    def test_a_fork_of_a_settled_branch_is_settled(self, store: FlowStore) -> None:
        features = accept(store, "features")
        record_run(store, features)

        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        assert last(store).settled is True

    def test_a_failed_run_settles_nothing(self, store: FlowStore) -> None:
        features = accept(store, "features")

        record_run(store, features, state="failed")

        assert last(store).settled is False

    def test_a_failed_rerun_unsettles_a_whole_branch(self, store: FlowStore) -> None:
        features = accept(store, "features")
        record_run(store, features)
        assert last(store).settled is True

        failed = record_run(store, features, state="failed")

        assert last(store).settled is False
        assert baselines(store, MAIN_BRANCH) == {features.uid: failed.mat_id}

    def test_a_run_that_started_before_a_code_change_is_not_current(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        main = store.branches.get(MAIN_BRANCH).branch_id
        started = last(store).step
        store.commit(
            [WorkspaceCodeChanged(tree_hash="h2" * 32, changed_paths=["helpers.py"])],
            intent="helpers.py changed",
            actor="user",
        )
        store.values.put(b"rows")
        spanning = run_recorded(
            uid=features.uid, version_id=features.version_id, branch_id=main
        ).model_copy(update={"started_step": started, "finished_step": store.next_step})

        store.commit([spanning], intent="ran features", actor="user", branch=main)

        assert last(store).settled is False


class TestCheckpoint:
    """The deliberate marker beside the computed `settled` badge.

    A marker is one journal line and nothing else — no value is copied, no
    selection moves — so what these assert is that the line lands, that it
    reaches the brief the same way the badge does, and that the two never
    shadow each other by class rather than by recency.
    """

    def marked(self, store: FlowStore, branch: str = MAIN_BRANCH) -> int | None:
        found = store.index.checkpoint(store.branches.get(branch).branch_id)
        return found.step if found else None

    def test_marking_a_point_journals_the_intent_as_the_transaction(
        self, store: FlowStore
    ) -> None:
        accept(store, "features")

        marked = store.branches.checkpoint(MAIN_BRANCH, intent="before the rewrite")

        assert last(store).step == marked.step
        assert last(store).intent == "before the rewrite"
        assert [op.op for op in last(store).ops] == ["checkpointed"]

    def test_a_marker_becomes_the_branchs_checkpoint(self, store: FlowStore) -> None:
        accept(store, "features")
        assert self.marked(store) is None

        marked = store.branches.checkpoint(MAIN_BRANCH, intent="before the rewrite")

        assert self.marked(store) == marked.step

    def test_the_newest_of_the_marker_and_the_settled_step_wins(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        store.branches.checkpoint(MAIN_BRANCH, intent="before running it")

        record_run(store, features)

        # Settling afterwards moves the branch on: the marker is where it was,
        # not where it is.
        assert self.marked(store) == last(store).step

        moved = store.branches.checkpoint(MAIN_BRANCH, intent="the good one")

        assert self.marked(store) == moved.step

    def test_a_marker_belongs_to_the_branch_it_was_made_on(
        self, store: FlowStore
    ) -> None:
        accept(store, "features")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        store.branches.checkpoint("sweep", intent="swept")

        assert self.marked(store, "sweep") == last(store).step
        assert self.marked(store, MAIN_BRANCH) is None

    def test_a_marker_is_a_rewind_target_like_any_other_step(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        marked = store.branches.checkpoint(MAIN_BRANCH, intent="before the rewrite")
        accept(store, "features", uid=features.uid, source="class F: v2")

        restored = store.branches.rewind(MAIN_BRANCH, to_step=marked.step)

        assert restored.selections == {features.uid: features.version_id}

    def test_a_checkpoint_without_words_is_refused(self, store: FlowStore) -> None:
        accept(store, "features")

        with pytest.raises(ValueError):
            store.branches.checkpoint(MAIN_BRANCH, intent="   ")

    def test_marking_an_unknown_branch_is_refused(self, store: FlowStore) -> None:
        with pytest.raises(BranchNotFound):
            store.branches.checkpoint("nowhere", intent="here")

    def test_a_marker_survives_an_index_rebuild(
        self, flow_dir: Path, store: FlowStore
    ) -> None:
        accept(store, "features")
        marked = store.branches.checkpoint(MAIN_BRANCH, intent="before the rewrite")
        store.close()

        reopened = FlowStore.open(flow_dir)

        assert self.marked(reopened) == marked.step


def test_a_rebuild_from_the_journal_reproduces_every_branch_row(
    flow_dir: Path, store: FlowStore
) -> None:
    features = accept(store, "features")
    record_run(store, features)
    accept(
        store,
        "plot_curves",
        consumes={"rows": "features.data"},
        bound_to={"rows": features.uid},
    )
    checkpoint = last(store).step
    store.branches.fork("sweep", from_branch=MAIN_BRANCH)
    store.branches.switch("sweep")
    edited = accept(
        store, "features", uid=features.uid, source="class F: v2", branch="sweep"
    )
    record_run(store, edited, branch="sweep", content=b"swept")
    store.branches.adopt("features", from_branch="sweep", to_branch=MAIN_BRANCH)
    store.branches.delete("plot_curves", branch="sweep")
    store.branches.rewind(MAIN_BRANCH, to_step=checkpoint)
    store.branches.archive("sweep")
    before = snapshot(store.index)
    store.close()
    (flow_dir / ".lumlflow" / "store.sqlite").unlink()

    reopened = FlowStore.open(flow_dir)

    assert snapshot(reopened.index) == before
