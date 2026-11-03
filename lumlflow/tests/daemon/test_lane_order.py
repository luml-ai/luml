"""Each lane keeps its own cell order; flow.yaml mirrors the root lane's."""

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.errors import FlowError
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, MANIFEST_NAME

from tests.daemon.helpers import daemon_api, make_workspace, transactions

NOTE = '''
class Note:
    """A note placed among the compute cells."""
'''


async def _cells(api: Api, branch: str = "main") -> list[str]:
    listed = await api.cells_list({"flow": "churn", "branch": branch})
    return [cell["slug"] for cell in listed["cells"]]


async def _three_cells(api: Api) -> None:
    await api.flow_open({"flow": "churn"})
    for slug in ("first", "middle", "last"):
        await api.cells_new({"flow": "churn", "slug": slug, "source": NOTE})


def _mirrored(flow: Path) -> dict[str, Any]:
    return yaml.safe_load((flow / MANIFEST_NAME).read_text())["order"]


def _intents(api: Api) -> list[str]:
    return [entry.intent for entry in transactions(api.hub.session("churn"))]


async def test_moving_a_cell_on_one_lane_leaves_the_other_alone(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.fork({"flow": "churn", "name": "exp"})
        await api.cells_reorder(
            {"flow": "churn", "branch": "exp", "slug": "first", "after": "last"}
        )

        assert await _cells(api, "exp") == ["middle", "last", "first"]
        assert await _cells(api, "main") == ["first", "middle", "last"]


async def test_a_lane_keeps_the_order_it_was_forked_with(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.cells_reorder({"flow": "churn", "slug": "last", "before": "first"})
        await api.fork({"flow": "churn", "name": "exp"})
        await api.cells_reorder({"flow": "churn", "slug": "first", "before": "last"})

        assert await _cells(api, "exp") == ["last", "first", "middle"]
        assert await _cells(api, "main") == ["first", "last", "middle"]


async def test_a_cell_made_on_a_lane_stays_off_its_parent(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.fork({"flow": "churn", "name": "exp"})
        await api.cells_new(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "extra",
                "source": NOTE,
                "anchor": "first",
            }
        )

        assert await _cells(api, "exp") == ["first", "extra", "middle", "last"]
        assert await _cells(api, "main") == ["first", "middle", "last"]


async def test_opening_fixes_lane_orders_once(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        fixed = [i for i in _intents(api) if i == "fixed lane orders"]
    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        again = [i for i in _intents(api) if i == "fixed lane orders"]

    assert fixed == ["fixed lane orders"]
    assert again == fixed


async def test_a_reorder_is_refused_behind_the_lanes_newest_step(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        session = api.hub.session("churn")
        main = session.store.branches.get("main").branch_id
        older = session.store.index.newest_step(main) - 1
        await api.rewind({"flow": "churn", "to_step": older})
        head = session.store.index.head_step(main)
        journal = len(transactions(session))

        with pytest.raises(FlowError, match="behind its newest step"):
            await api.cells_reorder(
                {"flow": "churn", "slug": "first", "after": "middle"}
            )

        assert len(transactions(session)) == journal
        assert session.store.index.head_step(main) == head


async def test_a_rewind_round_trip_keeps_a_reorder_made_after_the_step(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        session = api.hub.session("churn")
        main = session.store.branches.get("main").branch_id
        newest = session.store.index.newest_step(main)
        await api.cells_reorder({"flow": "churn", "slug": "first", "after": "last"})
        moved = await _cells(api)

        await api.rewind({"flow": "churn", "to_step": newest - 1})
        await api.rewind({"flow": "churn", "to_step": newest})

        assert moved == ["middle", "last", "first"]
        assert await _cells(api) == moved


async def test_a_reorder_adds_no_step_and_is_never_the_checkpoint(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        session = api.hub.session("churn")
        main = session.store.branches.get("main").branch_id
        newest = session.store.index.newest_step(main)
        checkpoint = session.store.index.checkpoint(main)

        await api.cells_reorder({"flow": "churn", "slug": "first", "after": "last"})

        assert session.store.index.newest_step(main) == newest
        assert session.store.index.head_step(main) == newest
        assert session.store.index.checkpoint(main) == checkpoint


async def test_editing_a_moved_cell_keeps_its_place(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.cells_reorder({"flow": "churn", "slug": "first", "after": "last"})
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "first",
                "source": NOTE.replace("A note", "An edited note"),
            }
        )
        await api.rename({"flow": "churn", "slug": "first", "to": "renamed"})

        assert await _cells(api) == ["middle", "last", "renamed"]


async def test_flow_yaml_mirrors_only_the_root_lane(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.fork({"flow": "churn", "name": "exp"})
        before = _mirrored(flow)
        await api.cells_reorder(
            {"flow": "churn", "branch": "exp", "slug": "first", "after": "last"}
        )
        after_exp = _mirrored(flow)
        await api.cells_reorder({"flow": "churn", "slug": "last", "before": "first"})
        after_main = _mirrored(flow)
        listed = await api.cells_list({"flow": "churn"})

    assert after_exp == before
    assert after_main != before
    assert after_main == {cell["uid"]: cell["order"] for cell in listed["cells"]}


async def test_an_outside_edit_of_flow_yaml_reorders_the_root_lane_once(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.fork({"flow": "churn", "name": "exp"})
        listed = await api.cells_list({"flow": "churn"})
        first = next(c for c in listed["cells"] if c["slug"] == "first")
        manifest = yaml.safe_load((flow / MANIFEST_NAME).read_text())
        manifest["order"][first["uid"]] = "1000"
        (flow / MANIFEST_NAME).write_text(yaml.safe_dump(manifest, sort_keys=False))

        main_cells = await _cells(api)
        await _cells(api)
        imports = [i for i in _intents(api) if i == "order from flow.yaml"]
        exp_cells = await _cells(api, "exp")

    assert main_cells == ["middle", "last", "first"]
    assert imports == ["order from flow.yaml"]
    assert exp_cells == ["first", "middle", "last"]


async def test_an_outside_edit_waits_while_the_root_lane_is_behind(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"

    async with daemon_api(root) as api:
        await _three_cells(api)
        session = api.hub.session("churn")
        main = session.store.branches.get("main").branch_id
        newest = session.store.index.newest_step(main)
        listed = await api.cells_list({"flow": "churn"})
        first = next(c for c in listed["cells"] if c["slug"] == "first")
        await api.rewind({"flow": "churn", "to_step": newest - 1})

        manifest = yaml.safe_load((flow / MANIFEST_NAME).read_text())
        manifest["order"][first["uid"]] = "1000"
        (flow / MANIFEST_NAME).write_text(yaml.safe_dump(manifest, sort_keys=False))
        await _cells(api)
        waiting = [i for i in _intents(api) if i == "order from flow.yaml"]

        await api.rewind({"flow": "churn", "to_step": newest})
        await _cells(api)
        landed = [i for i in _intents(api) if i == "order from flow.yaml"]
        cells = await _cells(api)

    assert waiting == []
    assert landed == ["order from flow.yaml"]
    assert cells[-1] == "first"


async def test_a_fresh_clone_takes_the_root_order_from_flow_yaml(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    clone_root = make_workspace(tmp_path / "clone", flows=())
    clone = clone_root / "churn.flow"

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.cells_reorder({"flow": "churn", "slug": "first", "after": "last"})
        original = await _cells(api)

    clone.mkdir()
    shutil.copy(flow / MANIFEST_NAME, clone / MANIFEST_NAME)
    shutil.copytree(flow / CELLS_DIRNAME, clone / CELLS_DIRNAME)

    async with daemon_api(clone_root) as api:
        await api.flow_open({"flow": "churn"})
        cloned = await _cells(api)

    assert original == ["middle", "last", "first"]
    assert cloned == original


async def test_an_adopted_cell_keeps_its_place_when_it_is_free(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        await api.fork({"flow": "churn", "name": "exp"})
        await api.cells_new(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "extra",
                "source": NOTE,
                "anchor": "first",
            }
        )
        await api.adopt({"flow": "churn", "slug": "extra", "from_branch": "exp"})

        assert await _cells(api) == ["first", "extra", "middle", "last"]


async def test_a_reorder_survives_a_second_round_trip_after_an_earlier_one(
    tmp_path: Path,
):
    # Found by hand on a real flow: the lane had been rewound away and back
    # before the move, so the later round trip replayed the earlier rewind.
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        session = api.hub.session("churn")
        main = session.store.branches.get("main").branch_id
        newest = session.store.index.newest_step(main)
        await api.rewind({"flow": "churn", "to_step": newest - 1})
        await api.rewind({"flow": "churn", "to_step": newest})
        await api.cells_reorder({"flow": "churn", "slug": "first", "after": "last"})

        await api.rewind({"flow": "churn", "to_step": newest - 1})
        await api.rewind({"flow": "churn", "to_step": newest})

        assert await _cells(api) == ["middle", "last", "first"]


async def test_reorders_made_on_every_visit_to_a_step_add_up(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await _three_cells(api)
        session = api.hub.session("churn")
        main = session.store.branches.get("main").branch_id
        newest = session.store.index.newest_step(main)
        await api.cells_reorder({"flow": "churn", "slug": "first", "after": "last"})
        await api.rewind({"flow": "churn", "to_step": newest - 1})
        await api.rewind({"flow": "churn", "to_step": newest})
        await api.cells_reorder({"flow": "churn", "slug": "last", "before": "middle"})

        await api.rewind({"flow": "churn", "to_step": newest - 1})
        await api.rewind({"flow": "churn", "to_step": newest})

        assert await _cells(api) == ["last", "middle", "first"]
