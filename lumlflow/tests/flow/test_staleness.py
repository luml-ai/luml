from pathlib import Path

import pytest
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.scheduler import memo, staleness
from lumlflow.flow.scheduler.planner import Planner
from lumlflow.flow.scheduler.staleness import Verdict
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import InputRef, WorkspaceCodeChanged

from tests.flow.helpers import accept, input_ref, output_record, record_run


@pytest.fixture
def store(tmp_path: Path) -> FlowStore:
    return FlowStore.init(tmp_path / "churn.flow")


def verdicts(store: FlowStore, branch: str = MAIN_BRANCH) -> dict[str, Verdict]:
    """Verdicts keyed by slug — the address every surface uses."""
    branch_id = store.branches.get(branch).branch_id
    return {
        verdict.slug: verdict
        for verdict in staleness.derive_all(store.index, branch_id).values()
    }


def causes(verdict: Verdict) -> list[tuple[str, str]]:
    return [(cause.kind, cause.detail) for cause in verdict.causes]


class TestStates:
    def test_a_never_run_cell_is_unmaterialized_not_unsynced(
        self, store: FlowStore
    ) -> None:
        accept(store, "features")

        assert verdicts(store)["features"].state == "unmaterialized"

    def test_a_run_cell_with_nothing_changed_is_synced(self, store: FlowStore) -> None:
        record_run(store, accept(store, "features"))

        verdict = verdicts(store)["features"]
        assert (verdict.state, verdict.causes) == ("synced", ())

    def test_a_failed_run_is_its_own_state(self, store: FlowStore) -> None:
        record_run(store, accept(store, "features"), state="failed")

        assert verdicts(store)["features"].state == "failed"

    def test_a_version_that_hashes_the_same_dirties_nothing(
        self, store: FlowStore
    ) -> None:
        """What a comment-only edit leaves behind: a new version, the same hash."""
        source = "class Features: pass"
        features = accept(store, "features", source=source)
        record_run(store, features)

        again = accept(store, "features", uid=features.uid, source=source)

        assert again.version_id != features.version_id
        verdict = verdicts(store)["features"]
        assert (verdict.state, verdict.causes) == ("synced", ())


class TestCauses:
    def test_an_edit_names_the_cell_in_words(self, store: FlowStore) -> None:
        features = accept(store, "features")
        record_run(store, features)
        accept(store, "features", uid=features.uid, source="class Features: v2 = 1")

        verdict = verdicts(store)["features"]
        assert verdict.state == "unsynced"
        assert causes(verdict) == [("definition-changed", "`features` was edited")]

    def test_a_rematerialized_parent_names_itself(self, store: FlowStore) -> None:
        features = accept(store, "features")
        first = record_run(store, features, content=b"one")
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        record_run(store, plot, inputs={"rows": input_ref(first)})
        record_run(store, features, content=b"two")

        verdict = verdicts(store)["plot"]
        assert verdict.state == "unsynced"
        assert causes(verdict) == [
            ("parent-rematerialized", "parent `features` rematerialized")
        ]

    def test_a_rewired_input_reads_as_rewired(self, store: FlowStore) -> None:
        features = accept(store, "features")
        run = record_run(store, features)
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        stranger = InputRef(
            uid=new_ulid(),
            output="data",
            content_hash=run.outputs["data"].content_hash,
            mat_id=run.mat_id,
        )
        record_run(store, plot, inputs={"rows": stranger})

        verdict = verdicts(store)["plot"]
        assert verdict.state == "unsynced"
        assert causes(verdict) == [
            ("deps-rewired", "`rows` now comes from a different cell")
        ]

    def test_a_workspace_code_change_names_the_file(self, store: FlowStore) -> None:
        record_run(store, accept(store, "features"))
        store.commit(
            [WorkspaceCodeChanged(tree_hash="a" * 64, changed_paths=["helpers.py"])],
            intent="shared code changed",
            actor="system",
        )

        verdict = verdicts(store)["features"]
        assert verdict.state == "unsynced"
        assert causes(verdict) == [("workspace-code-changed", "`helpers.py` changed")]

    def test_reverting_workspace_code_to_the_run_tree_clears_staleness(
        self, store: FlowStore
    ) -> None:
        tree_a = "a" * 64
        tree_b = "b" * 64
        store.commit(
            [WorkspaceCodeChanged(tree_hash=tree_a, changed_paths=["helpers.py"])],
            intent="shared code discovered",
            actor="system",
        )
        features = accept(store, "features")
        version = store.index.version(features.version_id)
        assert version is not None
        record_run(store, features, memo_key=memo.key_for(store.index, version, {}))
        store.commit(
            [
                WorkspaceCodeChanged(
                    tree_hash=tree_b,
                    previous_tree_hash=tree_a,
                    changed_paths=["helpers.py"],
                )
            ],
            intent="shared code changed",
            actor="system",
        )

        changed = verdicts(store)["features"]
        assert changed.state == "unsynced"
        assert causes(changed) == [("workspace-code-changed", "`helpers.py` changed")]
        assert Planner(store).auto_targets(MAIN_BRANCH) == ["features"]

        store.commit(
            [
                WorkspaceCodeChanged(
                    tree_hash=tree_a,
                    previous_tree_hash=tree_b,
                    changed_paths=["helpers.py"],
                )
            ],
            intent="shared code restored",
            actor="system",
        )

        restored = verdicts(store)["features"]
        assert (restored.state, restored.causes) == ("synced", ())
        assert Planner(store).auto_targets(MAIN_BRANCH) == []

    def test_a_parent_with_no_baseline_raises_no_cause_of_its_own(
        self, store: FlowStore
    ) -> None:
        """A parent nothing was observed of proves nothing — `upstream` says it."""
        features = accept(store, "features")
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        record_run(
            store,
            plot,
            inputs={
                "rows": InputRef(
                    uid=features.uid,
                    output="data",
                    content_hash=output_record().content_hash,
                    mat_id=new_ulid(),
                )
            },
        )

        verdict = verdicts(store)["plot"]
        assert (verdict.state, verdict.causes) == ("synced", ())
        assert verdict.upstream == ("features",)


class TestCarriedPointers:
    """Fork and rewind move baselines; the verdicts follow with no flag to set."""

    def test_a_fork_inherits_its_parents_verdicts(self, store: FlowStore) -> None:
        features = accept(store, "features")
        record_run(store, features)
        accept(store, "plot")

        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        assert {
            slug: verdict.state for slug, verdict in verdicts(store, "sweep").items()
        } == {
            "features": "synced",
            "plot": "unmaterialized",
        }

    def test_a_rewound_branch_does_not_light_up_wholesale(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        record_run(store, features, content=b"first")
        checkpoint = store.next_step - 1
        second = accept(
            store, "features", uid=features.uid, source="class Features: v2 = 1"
        )
        record_run(store, second, content=b"second")

        store.branches.rewind(MAIN_BRANCH, to_step=checkpoint)

        verdict = verdicts(store)["features"]
        assert (verdict.state, verdict.causes) == ("synced", ())


class TestPerBranch:
    """A verdict belongs to one branch: deriving is a read of its own pointers."""

    def test_an_edit_on_a_fork_marks_the_fork_and_not_the_parent(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        run = record_run(store, features)
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        record_run(store, plot, inputs={"rows": input_ref(run)})
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        accept(
            store,
            "features",
            branch="sweep",
            uid=features.uid,
            source="class Features: v2 = 1",
        )

        assert verdicts(store, "sweep")["features"].state == "unsynced"
        assert verdicts(store, "sweep")["plot"].upstream == ("features",)
        assert verdicts(store)["features"].state == "synced"
        assert verdicts(store)["plot"].upstream == ()

    def test_adopting_a_winner_marks_its_consumers_on_the_target(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        run = record_run(store, features)
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        record_run(store, plot, inputs={"rows": input_ref(run)})
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        accept(
            store,
            "features",
            branch="sweep",
            uid=features.uid,
            source="class Features: tuned = 1",
        )

        store.branches.adopt("features", from_branch="sweep", to_branch=MAIN_BRANCH)

        assert causes(verdicts(store)["features"]) == [
            ("definition-changed", "`features` was edited")
        ]
        assert verdicts(store)["plot"].upstream == ("features",)


class TestTransitiveView:
    def test_a_consumer_of_an_edited_parent_is_current_but_named_below_it(
        self, store: FlowStore
    ) -> None:
        features = accept(store, "features")
        run = record_run(store, features)
        plot = accept(
            store,
            "plot",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        record_run(store, plot, inputs={"rows": input_ref(run)})
        accept(store, "features", uid=features.uid, source="class Features: v2 = 1")

        marked = verdicts(store)
        assert marked["features"].state == "unsynced"
        assert marked["plot"].state == "synced"
        assert marked["plot"].transitive is True
        assert marked["plot"].upstream == ("features",)

    def test_upstream_reaches_through_the_whole_chain(self, store: FlowStore) -> None:
        features = accept(store, "features")
        middle = accept(
            store,
            "middle",
            consumes={"rows": "features.data"},
            bound_to={"rows": features.uid},
        )
        accept(
            store,
            "leaf",
            consumes={"rows": "middle.data"},
            bound_to={"rows": middle.uid},
        )

        assert verdicts(store)["leaf"].upstream == ("features", "middle")

    def test_a_cycle_in_consumes_does_not_hang_the_view(self, store: FlowStore) -> None:
        first = accept(store, "first")
        second = accept(
            store,
            "second",
            consumes={"rows": "first.data"},
            bound_to={"rows": first.uid},
        )
        accept(
            store,
            "first",
            uid=first.uid,
            consumes={"rows": "second.data"},
            bound_to={"rows": second.uid},
        )

        assert set(verdicts(store)) == {"first", "second"}
