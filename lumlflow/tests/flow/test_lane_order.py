"""Fixing lane orders: an old flow's shared order becomes each lane's own."""

from decimal import Decimal
from pathlib import Path

import pytest
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import CellsOrdered

from tests.flow.helpers import accept


@pytest.fixture
def store(tmp_path: Path) -> FlowStore:
    return FlowStore.init(tmp_path / "churn.flow")


def lane(store: FlowStore, name: str = MAIN_BRANCH) -> str:
    return store.branches.get(name).branch_id


def ordered(store: FlowStore, name: str = MAIN_BRANCH) -> list[str]:
    order = store.effective_order(lane(store, name))
    slugs = {
        uid: version.slug
        for uid, version in store.index.slice_versions(lane(store, name)).items()
    }
    return [slugs[uid] for uid in sorted(order, key=lambda uid: (order[uid], uid))]


def move(store: FlowStore, uid: str, key: str, name: str = MAIN_BRANCH) -> None:
    store.commit(
        [CellsOrdered(branch_id=lane(store, name), orders={uid: key})],
        intent="moved",
        actor="user",
        branch=lane(store, name),
    )


def test_fixing_keeps_the_order_every_lane_showed(store: FlowStore) -> None:
    first = accept(store, "first")
    second = accept(store, "second")
    third = accept(store, "third")
    store.branches.fork("exp", from_branch=MAIN_BRANCH)
    store.manifest.order = {third.uid: "1.5", first.uid: "not-a-number"}
    before = {name: ordered(store, name) for name in (MAIN_BRANCH, "exp")}

    store.ensure_lane_orders_fixed()

    assert store.index.lane_orders_fixed()
    assert {name: ordered(store, name) for name in (MAIN_BRANCH, "exp")} == before
    assert before[MAIN_BRANCH] == ["third", "first", "second"]
    assert second.uid in store.index.orders(lane(store, "exp"))


def test_fixing_keeps_how_colliding_keys_resolved_across_lanes(
    store: FlowStore,
) -> None:
    first = accept(store, "first")
    store.branches.fork("exp", from_branch=MAIN_BRANCH)
    only_exp = accept(store, "only_exp", branch="exp")
    # `first` claims the step `only_exp` was created at: across the lanes'
    # union that collides, so `first` keeps its creation step everywhere.
    born = store.index.creation_steps()
    store.manifest.order = {first.uid: str(born[only_exp.uid])}
    before = store.effective_order(lane(store, MAIN_BRANCH))

    store.ensure_lane_orders_fixed()

    assert store.effective_order(lane(store, MAIN_BRANCH)) == before
    assert before[first.uid] == Decimal(born[first.uid])


def test_fixing_twice_never_undoes_a_move(store: FlowStore) -> None:
    first = accept(store, "first")
    accept(store, "second")
    racing = store.fix_lane_orders()
    store.ensure_lane_orders_fixed()
    move(store, first.uid, "1000")

    store.commit(racing, intent="fixed lane orders", actor="auto")

    assert ordered(store) == ["second", "first"]


def test_fixing_covers_archived_lanes_and_their_forks(store: FlowStore) -> None:
    first = accept(store, "first")
    accept(store, "second")
    store.manifest.order = {first.uid: "100"}
    store.branches.fork("old", from_branch=MAIN_BRANCH)
    store.branches.archive("old")

    store.ensure_lane_orders_fixed()
    store.branches.fork("revived", from_branch="old")

    assert ordered(store, "old") == ["second", "first"]
    assert ordered(store, "revived") == ["second", "first"]


def test_the_root_lane_stays_root_when_archived(store: FlowStore) -> None:
    store.ensure_lane_orders_fixed()
    root = store.index.root_branch()
    store.branches.archive(MAIN_BRANCH)

    assert root is not None
    assert store.index.root_branch() == store.index.branch_by_id(root.branch_id)


def test_a_rewind_before_the_fixing_takes_the_order_it_recorded(
    store: FlowStore,
) -> None:
    first = accept(store, "first")
    accept(store, "second")
    old_step = store.next_step - 1
    store.manifest.order = {first.uid: "100"}
    store.ensure_lane_orders_fixed()
    accept(store, "third")

    store.branches.rewind(MAIN_BRANCH, to_step=old_step)

    assert ordered(store) == ["second", "first"]


def test_a_flow_with_fixed_orders_is_fixed_after_a_rebuild(
    tmp_path: Path, store: FlowStore
) -> None:
    first = accept(store, "first")
    accept(store, "second")
    store.ensure_lane_orders_fixed()
    move(store, first.uid, "1000")
    store.close()
    (tmp_path / "churn.flow" / ".lumlflow" / "store.sqlite").unlink()

    reopened = FlowStore.open(tmp_path / "churn.flow")

    assert reopened.index.lane_orders_fixed()
    assert ordered(reopened) == ["second", "first"]
