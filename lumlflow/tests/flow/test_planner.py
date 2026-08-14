from pathlib import Path

import pytest
from lumlflow.flow.errors import CellNotFound
from lumlflow.flow.store.branches import MAIN_BRANCH

from tests.flow.harness import Flow


@pytest.fixture
def flow(tmp_path: Path) -> Flow:
    return Flow(tmp_path / "churn.flow")


def slugs(flow: Flow, target: str, branch: str = MAIN_BRANCH) -> list[str]:
    return [step.slug for step in flow.planner.plan(target, branch=branch).steps]


class TestClosure:
    async def test_the_closure_is_the_stale_ancestors_and_the_path_down(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        flow.add("unrelated")
        await flow.run("plot")
        await flow.run("unrelated")
        flow.edit("features", "v2")

        assert slugs(flow, "plot") == ["features", "plot"]

    async def test_a_current_ancestor_stays_out_of_the_closure(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        await flow.run("plot")
        flow.edit("plot", "v2")

        assert slugs(flow, "plot") == ["plot"]

    async def test_a_note_is_never_scheduled(self, flow: Flow) -> None:
        flow.note("readme")

        assert slugs(flow, "readme") == []

    def test_an_unknown_target_is_named_in_the_error(self, flow: Flow) -> None:
        with pytest.raises(CellNotFound, match="nowhere"):
            flow.planner.plan("nowhere", branch=MAIN_BRANCH)


class TestPreflight:
    async def test_it_names_the_recomputes_and_totals_their_seconds(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.add("train_model", consumes={"rows": "features.data"})
        flow.add("holdout_eval", consumes={"rows": "train_model.data"})
        flow.executor.costs.update(
            {"features": 1.0, "train_model": 2.0, "holdout_eval": 0.5}
        )
        await flow.run("holdout_eval")
        flow.edit("features", "v2")

        preflight = flow.preflight("holdout_eval")

        assert preflight.recompute == ("features", "train_model", "holdout_eval")
        assert (preflight.cached, preflight.estimate_seconds) == ((), 3.5)
        assert (await flow.run("holdout_eval")).executed == preflight.recompute

    async def test_what_the_store_can_answer_reads_as_cached(self, flow: Flow) -> None:
        flow.add("features")
        await flow.run("features")

        preflight = flow.preflight("features")

        assert (preflight.cached, preflight.recompute) == (("features",), ())
        assert preflight.estimate_seconds == 0.0

    def test_a_cell_this_store_has_never_timed_is_named_not_guessed(
        self, flow: Flow
    ) -> None:
        flow.add("fresh")

        preflight = flow.preflight("fresh")

        assert (preflight.recompute, preflight.unknown) == (("fresh",), ("fresh",))
        assert preflight.estimate_seconds == 0.0


class TestBatchPreflight:
    """Rerunning a branch is one closure over its leaves, not a preflight each."""

    async def test_a_shared_ancestor_is_counted_once_across_targets(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        flow.add("train", consumes={"rows": "features.data"})
        flow.executor.costs.update({"features": 10.0, "plot": 1.0, "train": 2.0})
        await flow.run("plot")
        await flow.run("train")
        flow.edit("features", "v2")

        batch = flow.planner.preflight("plot", "train", branch=MAIN_BRANCH)

        assert batch.recompute == ("features", "plot", "train")
        # Preflighting each leaf on its own would bill `features` twice.
        assert batch.estimate_seconds == 13.0

    async def test_one_target_reads_the_same_either_way(self, flow: Flow) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})

        assert flow.planner.preflight("plot", "plot", branch=MAIN_BRANCH).recompute == (
            flow.preflight("plot").recompute
        )


class TestReactivity:
    async def test_a_change_marks_everything_and_runs_only_the_cheap_closure(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        flow.add("train", consumes={"rows": "features.data"})
        flow.executor.costs.update({"features": 1.0, "plot": 0.2, "train": 600.0})
        await flow.run("plot")
        await flow.run("train")
        flow.executor.requests.clear()

        flow.edit("features", "v2")
        marked = flow.verdicts()

        assert marked["features"].state == "unsynced"
        assert marked["plot"].upstream == marked["train"].upstream == ("features",)
        assert flow.planner.auto_targets(MAIN_BRANCH) == ["features", "plot"]
        assert flow.executor.requests == []

    async def test_running_the_auto_targets_recomputes_the_parent_on_the_way(
        self, flow: Flow
    ) -> None:
        """The list is only half the claim — the cheap closure has to be runnable."""
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        flow.add("train", consumes={"rows": "features.data"})
        flow.executor.costs.update({"features": 1.0, "plot": 0.2, "train": 600.0})
        await flow.run("plot")
        await flow.run("train")
        flow.edit("features", "v2")
        flow.executor.requests.clear()

        for target in flow.planner.auto_targets(MAIN_BRANCH):
            await flow.run(target)

        assert flow.executor.slugs == ["features", "plot"]
        assert flow.verdicts()["plot"].state == "synced"
        assert flow.verdicts()["train"].state == "unsynced"

    async def test_lazy_runs_nothing_by_itself(self, flow: Flow) -> None:
        flow.store.manifest.settings.reactivity = "lazy"
        flow.add("features")

        assert flow.planner.auto_targets(MAIN_BRANCH) == []

    async def test_an_eager_cell_runs_however_long_it_takes(self, flow: Flow) -> None:
        flow.add("features")
        train = flow.add("train", consumes={"rows": "features.data"})
        flow.executor.costs.update({"features": 1.0, "train": 600.0})
        await flow.run("train")
        flow.edit("features", "v2")
        assert flow.planner.auto_targets(MAIN_BRANCH) == ["features"]

        flow.store.manifest.settings.eager.append(train.uid)

        assert flow.planner.auto_targets(MAIN_BRANCH) == ["features", "train"]

    async def test_a_failure_is_retried_after_an_edit_and_not_before(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        # Run it once before breaking it: reactivity weighs a closure it has
        # timed, and one it has never timed is declined for that reason
        # instead — which would pass this test for the wrong reason.
        await flow.run("features")
        flow.executor.failing.add("features")
        flow.edit("features", "a break")
        await flow.run("features")

        assert flow.planner.auto_targets(MAIN_BRANCH) == []

        flow.executor.failing.discard("features")
        flow.edit("features", "the fix")

        assert flow.planner.auto_targets(MAIN_BRANCH) == ["features"]

    async def test_a_consumer_does_not_retry_the_failure_under_it_either(
        self, flow: Flow
    ) -> None:
        """Otherwise the guard is hollow: the consumer's closure reruns it."""
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        await flow.run("plot")
        flow.executor.failing.add("features")
        flow.edit("features", "a break")
        await flow.run("plot")
        flow.executor.requests.clear()

        assert flow.planner.auto_targets(MAIN_BRANCH) == []

        flow.executor.failing.discard("features")
        flow.edit("features", "the fix")

        assert flow.planner.auto_targets(MAIN_BRANCH) == ["features", "plot"]

    async def test_a_closure_it_has_never_timed_is_left_for_the_user(
        self, flow: Flow
    ) -> None:
        """The rule that keeps opening a flow from starting its training run.

        A preflight counts an unmeasured cell as nothing, so without this a
        six-hour cell nobody has ever run reads as free and clears any
        threshold.
        """
        flow.add("features")
        flow.add("train", consumes={"rows": "features.data"})
        flow.executor.costs.update({"features": 0.1, "train": 600.0})

        assert flow.planner.auto_targets(MAIN_BRANCH) == []
        assert flow.executor.requests == []

        declined = flow.planner.auto_verdicts(MAIN_BRANCH)

        assert {verdict.reason for verdict in declined.values()} == {"never-timed"}
        assert sorted(
            slug for verdict in declined.values() for slug in verdict.untimed
        ) == ["features", "features", "train"]

    async def test_a_cell_it_has_timed_refreshes_itself_after_that(
        self, flow: Flow
    ) -> None:
        """The other half: running it once is what teaches the flow its cost."""
        flow.add("features")
        await flow.run("features")
        flow.edit("features", "v2")

        assert flow.planner.auto_targets(MAIN_BRANCH) == ["features"]

    async def test_eager_takes_a_cell_no_estimate_could_have_admitted(
        self, flow: Flow
    ) -> None:
        train = flow.add("train")
        flow.store.manifest.settings.eager.append(train.uid)

        assert flow.planner.auto_targets(MAIN_BRANCH) == ["train"]

    async def test_the_verdict_says_what_it_declined_on(self, flow: Flow) -> None:
        flow.add("features")
        flow.add("train", consumes={"rows": "features.data"})
        flow.executor.costs.update({"features": 1.0, "train": 600.0})
        await flow.run("train")
        flow.edit("features", "v2")

        verdicts = flow.planner.auto_verdicts(MAIN_BRANCH)
        by_slug = {verdict.slug: verdict for verdict in verdicts.values()}

        assert by_slug["features"].taken
        assert not by_slug["train"].taken
        assert by_slug["train"].reason == "too-expensive"
        assert by_slug["train"].estimate_seconds == 601.0

    async def test_lazy_has_no_opinion_about_any_cell(self, flow: Flow) -> None:
        """Not "declined everything" — off. A card renders nothing about it."""
        flow.store.manifest.settings.reactivity = "lazy"
        flow.add("features")
        await flow.run("features")
        flow.edit("features", "v2")

        assert flow.planner.auto_verdicts(MAIN_BRANCH) == {}

    async def test_an_eager_cell_still_waits_on_a_failure_below_it(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        plot = flow.add("plot", consumes={"rows": "features.data"})
        flow.executor.failing.add("features")
        await flow.run("plot")
        flow.store.manifest.settings.eager.append(plot.uid)

        assert flow.planner.auto_targets(MAIN_BRANCH) == []

    async def test_a_note_is_never_an_auto_target(self, flow: Flow) -> None:
        flow.note("readme")

        assert flow.planner.auto_targets(MAIN_BRANCH) == []
