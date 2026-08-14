import asyncio
from pathlib import Path

import pytest
from lumlflow.flow.errors import InputUnavailable
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.models import MemoHit, RunRecorded

from tests.flow.harness import Flow, settle


@pytest.fixture
def flow(tmp_path: Path) -> Flow:
    return Flow(tmp_path / "churn.flow")


def baseline_mat(flow: Flow, slug: str, branch: str = MAIN_BRANCH) -> str | None:
    branch_id = flow.store.branches.get(branch).branch_id
    for uid, version in flow.store.index.slice_versions(branch_id).items():
        if version.slug == slug:
            return flow.store.index.baselines(branch_id).get(uid)
    return None


class TestRunning:
    async def test_a_run_records_the_materialization_and_clears_staleness(
        self, flow: Flow
    ) -> None:
        flow.add("features")

        outcome = await flow.run("features")

        assert outcome.executed == ("features",)
        assert flow.verdicts()["features"].state == "synced"

    async def test_a_stale_ancestor_runs_before_the_target(self, flow: Flow) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})

        outcome = await flow.run("plot")

        assert outcome.executed == ("features", "plot")
        assert flow.executor.slugs == ["features", "plot"]

    async def test_nothing_reruns_when_nothing_changed(self, flow: Flow) -> None:
        flow.add("features")
        await flow.run("features")

        outcome = await flow.run("features")

        assert (outcome.executed, outcome.pruned) == ((), ("features",))
        assert flow.executor.slugs == ["features"]

    async def test_a_failure_stops_the_plan_and_is_recorded(self, flow: Flow) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        flow.executor.failing.add("features")

        outcome = await flow.run("plot")

        assert (outcome.failed, outcome.executed) == ("features", ())
        assert flow.executor.slugs == ["features"]
        assert flow.verdicts()["features"].state == "failed"

    async def test_a_cell_pointing_at_nothing_says_so_in_names(
        self, flow: Flow
    ) -> None:
        flow.add("plot", consumes={"rows": "features.data"})

        with pytest.raises(InputUnavailable, match="`plot` needs `features.data`"):
            await flow.run("plot")


class TestEarlyCutoff:
    async def test_a_consumer_of_an_unchanged_output_never_reruns(
        self, flow: Flow
    ) -> None:
        """`train` reruns; only the consumer of the output that moved follows."""
        flow.add("train", produces={"run": "experiment", "checkpoint": "asset"})
        flow.add("uses_run", consumes={"rows": "train.run"})
        flow.add("uses_ckpt", consumes={"rows": "train.checkpoint"})
        flow.executor.content[("train", "checkpoint")] = b"identical every time"
        await flow.run("uses_run")
        await flow.run("uses_ckpt")
        flow.executor.requests.clear()
        flow.edit("train", "v2")

        after_ckpt = await flow.run("uses_ckpt")
        after_run = await flow.run("uses_run")

        assert (after_ckpt.executed, after_ckpt.pruned) == (("train",), ("uses_ckpt",))
        assert after_run.executed == ("uses_run",)
        assert flow.executor.slugs == ["train", "uses_run"]

    async def test_a_swapped_pair_of_inputs_is_not_a_hit(self, flow: Flow) -> None:
        """A named map, not a bag: same hashes, different names, different key."""
        flow.add("splits", produces={"a": "asset", "b": "asset"})
        flow.add("consumer", consumes={"train": "splits.a", "test": "splits.b"})
        flow.executor.content[("splits", "a")] = b"first"
        flow.executor.content[("splits", "b")] = b"second"
        await flow.run("consumer")
        flow.executor.content[("splits", "a")] = b"second"
        flow.executor.content[("splits", "b")] = b"first"
        flow.edit("splits", "swapped")
        flow.executor.requests.clear()

        outcome = await flow.run("consumer")

        assert outcome.executed == ("splits", "consumer")


class TestMemoHits:
    async def test_a_fork_reuses_the_other_branchs_run_without_executing(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        await flow.run("plot")
        flow.executor.requests.clear()

        outcome = await flow.queue.submit("plot", branch="sweep")

        assert (outcome.cached, flow.executor.requests) == (
            ("features", "plot"),
            [],
        )
        assert baseline_mat(flow, "plot", "sweep") == baseline_mat(flow, "plot")
        assert flow.verdicts("sweep")["plot"].state == "synced"

    async def test_a_hit_is_journaled_rather_than_read_as_a_free_run(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        await flow.run("features")

        await flow.queue.submit("features", branch="sweep")

        sweep = flow.store.branches.get("sweep").branch_id
        assert [op.branch_id for op in flow.ops(MemoHit)] == [sweep]
        assert len(flow.ops(RunRecorded)) == 1

    async def test_an_identity_dependent_cell_reruns_under_its_own_branch(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.executor.identity.add("features")
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        await flow.run("features")

        outcome = await flow.queue.submit("features", branch="sweep")

        assert outcome.executed == ("features",)
        assert flow.executor.slugs == ["features", "features"]

    async def test_an_external_cell_never_memoizes(self, flow: Flow) -> None:
        flow.add("features")
        flow.executor.external.add("features")
        await flow.run("features")

        outcome = await flow.run("features")

        assert outcome.executed == ("features",)
        assert flow.executor.slugs == ["features", "features"]


class TestForcedRuns:
    """`--force` is the labeled modifier: it buys back a suspect result by
    spending the closure's cost again, and buys nothing else."""

    async def test_forcing_recomputes_what_early_cutoff_would_have_skipped(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        await flow.run("features")

        outcome = await flow.run("features", force=True)

        assert (outcome.executed, outcome.pruned) == (("features",), ())
        assert flow.executor.slugs == ["features", "features"]

    async def test_forcing_recomputes_what_the_memo_would_have_served(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        await flow.run("features")

        outcome = await flow.queue.submit("features", branch="sweep", force=True)

        assert outcome.executed == ("features",)
        # A forced run is a run, not a hit — the journal says so too.
        assert flow.ops(MemoHit) == []
        assert len(flow.ops(RunRecorded)) == 2

    async def test_forcing_reaches_every_step_of_the_plan(self, flow: Flow) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        await flow.run("plot")
        flow.executor.requests.clear()

        outcome = await flow.queue.submit("plot", branch="sweep", force=True)

        # Both would have been hits on the fork; forcing runs the pair.
        assert outcome.executed == ("features", "plot")
        assert flow.executor.slugs[-2:] == ["features", "plot"]

    async def test_forcing_does_not_reach_an_ancestor_the_branch_has_current(
        self, flow: Flow
    ) -> None:
        """Forcing is scoped to the closure the request is about. A parent this
        branch already holds is not part of that closure, and rerunning the flow
        from its roots is not what one click asked for."""
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        await flow.run("plot")
        flow.executor.requests.clear()

        outcome = await flow.run("plot", force=True)

        assert outcome.executed == ("plot",)
        assert flow.executor.slugs[-1:] == ["plot"]

    async def test_an_ordinary_run_after_a_forced_one_is_cheap_again(
        self, flow: Flow
    ) -> None:
        """Forcing spends once. It does not put the branch into a state where
        everything reruns from then on."""
        flow.add("features")
        await flow.run("features", force=True)
        flow.executor.requests.clear()

        outcome = await flow.run("features")

        assert (outcome.pruned, flow.executor.requests) == (("features",), [])


class TestUnpersistedValues:
    async def test_demand_for_bytes_that_were_never_kept_reruns_the_producer(
        self, flow: Flow
    ) -> None:
        flow.add("sampler", produces={"data": {"type": "asset", "persist": False}})
        flow.add("consumer", consumes={"rows": "sampler.data"})
        await flow.run("consumer")
        flow.executor.requests.clear()

        outcome = await flow.run("consumer")

        assert outcome.executed == ("sampler", "consumer")

    async def test_the_producer_alone_still_settles(self, flow: Flow) -> None:
        flow.add("sampler", produces={"data": {"type": "asset", "persist": False}})
        await flow.run("sampler")
        flow.executor.requests.clear()

        outcome = await flow.run("sampler")

        assert (outcome.executed, outcome.pruned) == ((), ("sampler",))


class TestCoalescing:
    async def test_one_run_serves_every_branch_asking_for_it(self, flow: Flow) -> None:
        flow.add("train")
        flow.executor.holding.add("train")
        main = asyncio.create_task(flow.run("train"))
        await flow.executor.started.wait()
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        flow.store.branches.fork("late", from_branch=MAIN_BRANCH)
        joined = [
            asyncio.create_task(flow.queue.submit("train", branch=branch))
            for branch in ("sweep", "late")
        ]
        await settle()
        flow.executor.release()

        outcomes = await asyncio.gather(main, *joined)
        assert flow.executor.slugs == ["train"]
        assert outcomes[0].executed == ("train",)
        assert [outcome.cached for outcome in outcomes[1:]] == [("train",), ("train",)]
        assert {op.branch_id for op in flow.ops(MemoHit)} == {
            flow.store.branches.get(name).branch_id for name in ("sweep", "late")
        }

    async def test_a_waiter_runs_its_own_when_the_shared_one_reads_identity(
        self, flow: Flow
    ) -> None:
        """Coalescing has to unwind: identity dependence is only known after."""
        flow.add("train")
        flow.executor.identity.add("train")
        flow.executor.holding.add("train")
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        main = asyncio.create_task(flow.run("train"))
        await flow.executor.started.wait()
        joined = asyncio.create_task(flow.queue.submit("train", branch="sweep"))
        await settle()
        flow.executor.release()

        assert (await main).executed == ("train",)
        assert (await joined).executed == ("train",)
        assert [request.branch for request in flow.executor.requests] == [
            MAIN_BRANCH,
            "sweep",
        ]
        assert baseline_mat(flow, "train", "sweep") != baseline_mat(flow, "train")

    async def test_a_waiter_runs_its_own_when_the_shared_one_reads_outside(
        self, flow: Flow
    ) -> None:
        """Same unwind for `external`: nothing here knows what it read."""
        flow.add("train")
        flow.executor.external.add("train")
        flow.executor.holding.add("train")
        main = asyncio.create_task(flow.run("train"))
        await flow.executor.started.wait()
        joined = asyncio.create_task(flow.run("train"))
        await settle()
        flow.executor.release()

        assert (await main).executed == ("train",)
        assert (await joined).executed == ("train",)
        assert flow.executor.slugs == ["train", "train"]

    async def test_the_run_survives_one_branch_walking_away(self, flow: Flow) -> None:
        flow.add("train")
        flow.executor.holding.add("train")
        main = asyncio.create_task(flow.run("train"))
        await flow.executor.started.wait()
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        joined = asyncio.create_task(flow.queue.submit("train", branch="sweep"))
        await settle()

        left = flow.queue.abandon(MAIN_BRANCH)
        await settle()
        assert flow.executor.cancelled == []
        flow.executor.release()

        assert (await main).abandoned is True
        assert (await joined).cached == ("train",)
        # Leaving is not stopping, and the report says which one happened so a
        # surface never claims a run ended that is still going.
        assert (left.stopped, left.awaiting) == (False, 1)

    async def test_the_last_branch_leaving_preempts_the_run(self, flow: Flow) -> None:
        flow.add("train")
        flow.executor.holding.add("train")
        main = asyncio.create_task(flow.run("train"))
        await flow.executor.started.wait()

        left = flow.queue.abandon(MAIN_BRANCH)
        outcome = await main

        assert (outcome.abandoned, len(flow.executor.cancelled)) == (True, 1)
        assert (left.stopped, left.awaiting) == (True, 0)
        await settle()
        assert flow.verdicts()["train"].state == "unmaterialized"

    async def test_leaving_a_run_nobody_asked_for_says_so(self, flow: Flow) -> None:
        flow.add("train")

        assert flow.queue.abandon(MAIN_BRANCH).left == 0

    async def test_the_awaiter_count_is_announced_as_branches_join_and_leave(
        self, flow: Flow
    ) -> None:
        """The stop button's wording moves while the run is in flight, and no
        journal line carries it — only this."""
        flow.add("train")
        flow.executor.holding.add("train")
        main = asyncio.create_task(flow.run("train"))
        await flow.executor.started.wait()
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        joined = asyncio.create_task(flow.queue.submit("train", branch="sweep"))
        await settle()
        flow.queue.abandon("sweep")
        await settle()
        flow.executor.release()
        await main
        await joined

        counts = [
            params["awaiting"] for event, params in flow.events if event == "awaiting"
        ]
        assert counts == [1, 2, 1]
        assert {params["slug"] for _, params in flow.events} == {"train"}


class TestQueueOrder:
    async def test_the_watched_branch_goes_first_when_the_gate_frees(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        for name in ("early", "watched"):
            flow.store.branches.fork(name, from_branch=MAIN_BRANCH)
            flow.edit("features", f"{name} edit", branch=name)
        flow.add("blocker")
        flow.executor.holding.add("blocker")
        blocking = asyncio.create_task(flow.run("blocker"))
        await flow.executor.started.wait()
        flow.queue.focus("watched")

        waiting = [
            asyncio.create_task(flow.queue.submit("features", branch=name))
            for name in ("early", "watched")
        ]
        await settle()
        flow.executor.release()

        await asyncio.gather(blocking, *waiting)
        assert [request.branch for request in flow.executor.requests] == [
            MAIN_BRANCH,
            "watched",
            "early",
        ]


class TestSafetyModes:
    """The flow's settings ride on each run, and strict mode says which values
    a copy is owed on — a question only the store can answer."""

    async def test_the_modes_a_flow_is_set_to_ride_on_every_run(
        self, flow: Flow
    ) -> None:
        flow.store.manifest.settings.paranoid = True
        flow.store.manifest.settings.strict = True
        flow.add("features")

        await flow.run("features")

        request = flow.executor.requests[-1]
        assert (request.paranoid, request.strict) == (True, True)

    async def test_strict_mode_marks_the_inputs_a_second_branch_is_live_on(
        self, flow: Flow
    ) -> None:
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        await flow.run("plot")
        # The fork copies main's baselines, so both branches now read the one
        # materialization of `features` — and the kernel caches it once.
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        flow.store.manifest.settings.strict = True
        flow.edit("plot", "again")

        await flow.run("plot")

        assert flow.executor.requests[-1].inputs["rows"].shared is True

    async def test_a_value_only_one_branch_reads_is_not_marked_shared(
        self, flow: Flow
    ) -> None:
        flow.store.manifest.settings.strict = True
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})

        await flow.run("plot")

        assert flow.executor.requests[-1].inputs["rows"].shared is False

    async def test_the_question_is_not_asked_when_strict_mode_is_off(
        self, flow: Flow
    ) -> None:
        """Off is off: an input is unmarked whatever the branches are doing."""
        flow.add("features")
        flow.add("plot", consumes={"rows": "features.data"})
        await flow.run("plot")
        flow.store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        flow.edit("plot", "again")

        await flow.run("plot")

        assert flow.executor.requests[-1].inputs["rows"].shared is False
