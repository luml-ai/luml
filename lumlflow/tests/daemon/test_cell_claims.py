from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import harnesses
from lumlflow.flow.daemon.api import CLAIM_IDLE_S, Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.errors import CellClaimed

from tests.daemon.helpers import daemon_api, make_workspace

NOTE = '''
class Note:
    """A note on the lane."""
'''


def _by(actor: str, **params: Any) -> dict[str, Any]:
    return {"flow": "churn", "actor": actor} | params


async def _lane(api: Api) -> int:
    await api.flow_open({"flow": "churn"})
    for slug in ("first", "second"):
        await api.cells_new({"flow": "churn", "slug": slug, "source": NOTE})
    shown = await api.cells_show({"flow": "churn", "slug": "first"})
    return int(shown["created_step"])


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


async def test_another_agent_cannot_change_or_run_a_held_cell(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane(api)
        api.claim("cells.show", _by("codex-1", slug="first"), label="codex")

        for method, params in (
            ("cells.edit", {"slug": "first"}),
            ("cells.delete", {"slug": "first"}),
            ("rename", {"slug": "first", "to": "renamed"}),
            ("cells.reorder", {"slug": "first", "after": "second"}),
            ("run", {"target": "first.summary"}),
        ):
            with pytest.raises(CellClaimed) as refused:
                api.claim(method, _by("claude-1", **params), label="claude-code")
            assert refused.value.label == "codex"

        api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")
        api.claim("cells.show", _by("claude-1", slug="first"), label="claude-code")
        with pytest.raises(CellClaimed):
            api.claim("cells.edit", _by("claude-1", slug="first"), label="claude-code")

    message = str(refused.value)
    assert "`first` is being worked on by codex" in message
    assert "Nothing was changed" in message
    assert "you can still read this one" in message


async def test_the_hold_moves_with_the_agent_and_frees_the_cell_it_left(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane(api)
        api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")
        api.claim("context", _by("codex-1"), label="codex")
        with pytest.raises(CellClaimed):
            api.claim("cells.edit", _by("claude-1", slug="first"), label="claude-code")

        api.claim("cells.edit", _by("codex-1", slug="second"), label="codex")
        api.claim("cells.edit", _by("claude-1", slug="first"), label="claude-code")
        with pytest.raises(CellClaimed):
            api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")


async def test_a_hold_lapses_after_the_agent_leaves_the_cell_alone(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane(api)
        clock = _Clock()
        api.clock = clock
        api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")

        clock.now += CLAIM_IDLE_S - 1
        with pytest.raises(CellClaimed):
            api.claim("cells.edit", _by("claude-1", slug="first"), label="claude-code")
        clock.now += 1
        api.claim("cells.edit", _by("claude-1", slug="first"), label="claude-code")


async def test_disconnecting_or_a_rewind_frees_every_held_cell(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first_step = await _lane(api)
        api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")
        api.forget_agent("codex-1")
        api.claim("cells.edit", _by("claude-1", slug="first"), label="claude-code")

        await api.rewind({"flow": "churn", "to_step": first_step})
        api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")


async def test_a_rename_or_delete_by_the_holder_follows_the_cell(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane(api)
        api.claim("rename", _by("codex-1", slug="first", to="renamed"), label="codex")
        await api.rename(_by("codex-1", slug="first", to="renamed"))
        api.settled("rename", _by("codex-1", slug="first", to="renamed"))

        with pytest.raises(CellClaimed):
            api.claim(
                "cells.edit", _by("claude-1", slug="renamed"), label="claude-code"
            )

        api.claim("cells.delete", _by("codex-1", slug="renamed"), label="codex")
        api.settled("cells.delete", _by("codex-1", slug="renamed"))
        api.claim("cells.new", _by("claude-1", slug="renamed"), label="claude-code")


async def test_dotted_cells_are_held_apart(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        for slug in ("train.v1", "train.v2"):
            await api.cells_new({"flow": "churn", "slug": slug, "source": NOTE})
        api.claim("cells.edit", _by("codex-1", slug="train.v1"), label="codex")
        api.claim("cells.edit", _by("claude-1", slug="train.v2"), label="claude")

        with pytest.raises(CellClaimed):
            api.claim("run", _by("claude-1", target="train.v1"), label="claude")
        with pytest.raises(CellClaimed):
            api.claim("run", _by("claude-1", target="train.v1.out"), label="claude")


async def test_the_same_cell_on_another_lane_is_another_cell(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane(api)
        await api.fork({"flow": "churn", "name": "sweep", "intent": "try"})
        api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")
        api.claim(
            "cells.edit", _by("claude-1", slug="first", branch="sweep"), label="claude"
        )


async def test_a_second_window_of_the_same_harness_gets_a_number(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    hub = Hub()
    leases: set[tuple[str | None, str, str]] = set()
    api = Api(hub, directory=root, leases=lambda: set(leases))
    try:
        opened = await api.flow_open({"flow": "churn"})
        first = await api.agent_begin(
            {"flow": "churn", "actor": "codex-1", "label": "codex", "lease": True}
        )
        leases.add((opened["path"], "codex-1", first["label"]))
        second = await api.agent_begin(
            {"flow": "churn", "actor": "codex-2", "label": "codex", "lease": True}
        )
        leases.add((opened["path"], "codex-2", second["label"]))
        third = await api.agent_begin(
            {"flow": "churn", "actor": "codex-3", "label": "codex", "lease": True}
        )
        by_hand = await api.agent_begin(
            {"flow": "churn", "actor": "manual", "label": "codex"}
        )
    finally:
        await hub.close()

    assert [first["label"], second["label"], third["label"]] == [
        "codex",
        "codex 2",
        "codex 3",
    ]
    assert by_hand["label"] == "codex"


def test_codex_is_known_by_the_name_it_gives_in_the_handshake() -> None:
    assert harnesses.client_harness_id("codex-mcp-client") == "codex"
    assert harnesses.client_harness_id("Claude Code") == "claude-code"


async def test_a_lapsed_claim_is_let_go_of_without_another_call(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane(api)
        clock = _Clock()
        api.clock = clock
        api.claim("cells.edit", _by("codex-1", slug="first"), label="codex")
        held = list(api._claims)

        clock.now += CLAIM_IDLE_S - 1
        api.expire_claims()
        still = list(api._claims)
        clock.now += 1
        api.expire_claims()

    assert held == still
    assert len(held) == 1
    assert list(api._claims) == []
