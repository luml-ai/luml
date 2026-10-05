"""An agent's change never lands on a lane that was moved under it.

The lane's position is where every change goes. A person who rewinds it and
then edits is asked first whether to move it on from there; an agent mid-task
read where the lane stood when it began, and would move it on from somewhere
it never saw. So its change is refused, nothing lands, and it is told what
moved — after which the same call goes through, because now it knows.
"""

from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.errors import LaneMoved

from tests.daemon.helpers import daemon_api, make_workspace

NOTE = '''
class Note:
    """A note on the lane."""
'''

AGENT = "codex-1"


def _as_agent(**params: Any) -> dict[str, Any]:
    return {"flow": "churn", "actor": AGENT} | params


async def _lane_with_two_steps(api: Api) -> tuple[int, int]:
    """Two notes on main; the steps each one was added at."""
    await api.flow_open({"flow": "churn"})
    await api.cells_new({"flow": "churn", "slug": "first", "source": NOTE})
    await api.cells_new({"flow": "churn", "slug": "second", "source": NOTE})
    first = await api.cells_show({"flow": "churn", "slug": "first"})
    second = await api.cells_show({"flow": "churn", "slug": "second"})
    return int(first["created_step"]), int(second["created_step"])


async def _agent_reads_context(api: Api) -> None:
    await api.context(_as_agent())
    api.observed("context", _as_agent())


async def test_a_change_after_somebody_rewound_the_lane_is_refused_once(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await _agent_reads_context(api)
        await api.rewind({"flow": "churn", "to_step": first})

        with pytest.raises(LaneMoved) as refused:
            api.fence("cells.new", _as_agent(slug="third"))
        # Told, so caught up: the same call made again goes through.
        api.fence("cells.new", _as_agent(slug="third"))

    message = str(refused.value)
    assert refused.value.to_step == first
    assert refused.value.by == "user"
    assert f"moved to step {first} by user" in message
    assert "Nothing was changed" in message
    assert "`new-lane`" in message


async def test_every_change_is_fenced_and_reading_or_moving_it_is_not(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await _agent_reads_context(api)
        await api.rewind({"flow": "churn", "to_step": first})

        # Looking, and the remedies, are never refused.
        for method in ("context", "cells.show", "asset.preview", "fork", "rewind"):
            api.fence(method, _as_agent())
        with pytest.raises(LaneMoved):
            api.fence("run", _as_agent(target="first"))


async def test_a_person_editing_at_the_newest_step_does_not_stop_the_agent(
    tmp_path: Path,
) -> None:
    """Two people on one lane is what pairing is; only a move is a surprise."""
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await _lane_with_two_steps(api)
        await _agent_reads_context(api)
        await api.cells_new({"flow": "churn", "slug": "by_hand", "source": NOTE})

        api.fence("cells.edit", _as_agent(slug="first"))


async def test_the_agents_own_rewind_and_a_return_to_where_it_was_are_not_moves(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, second = await _lane_with_two_steps(api)
        await _agent_reads_context(api)

        await api.rewind(_as_agent(to_step=first))
        api.observed("rewind", _as_agent(to_step=first))
        api.fence("cells.new", _as_agent(slug="third"))

        # Somebody moves it away and back before the agent's next change.
        await api.rewind({"flow": "churn", "to_step": second})
        await api.rewind({"flow": "churn", "to_step": first})
        api.fence("cells.new", _as_agent(slug="third"))


async def test_an_agent_that_was_shown_nothing_is_held_to_nothing(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        first, _ = await _lane_with_two_steps(api)
        await api.rewind({"flow": "churn", "to_step": first})

        api.fence("cells.new", _as_agent(slug="third"))
        api.forget_agent(AGENT)
        api.fence("cells.new", _as_agent(slug="third"))
