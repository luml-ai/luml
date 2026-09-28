import re
from pathlib import Path

import pytest
from lumlflow.flow.errors import CellNotFound, FlowError

from tests.daemon.helpers import (
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    make_workspace,
    transactions,
    write_cell,
)

BROKEN_CONTEXT_CELL = '''
class Score:
    """Score the held-out rows."""
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": self.outer()}

    def outer(self):
        return self.inner()

    def inner(self):
        raise ValueError("threshold must be in (0, 1)")
'''

_HASH = re.compile(r"\b[0-9a-f]{16,}\b")
_ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")


async def test_payload_carries_the_cell_context_without_a_gesture(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        handed = await api.agent_payload({"slug": "score"})

    assert set(handed) == {"flow", "branch", "slug", "text"}
    assert handed["flow"] == "churn"
    assert handed["branch"] == "main"
    assert handed["slug"] == "score"
    text = str(handed["text"])
    assert "lane: main" in text
    assert "slug: score" in text
    assert re.search(r"^step: \d+$", text, re.MULTILINE)
    assert "doc: |\n  The headline metric." in text
    assert "gesture:" not in text


async def test_failed_payload_keeps_frames_and_only_the_final_exception_line(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", BROKEN_CONTEXT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "score"})
        handed = await api.agent_payload({"slug": "score"})

    text = str(handed["text"])
    assert text.count("file: <cell score>") == 3
    assert text.count("line: ") == 3
    assert "function: materialize" in text
    assert "function: outer" in text
    assert "function: inner" in text
    assert "exception: ValueError: threshold must be in (0, 1)" in text
    assert "Traceback (most recent call last)" not in text
    assert "return self.inner()" not in text
    assert 'raise ValueError("threshold must be in (0, 1)")' not in text


async def test_payload_on_an_unchecked_lane_names_that_lane(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.fork({"name": "sweep"})
        handed = await api.agent_payload({"slug": "score", "branch": "sweep"})

    assert handed["branch"] == "sweep"
    assert "lane: sweep" in str(handed["text"])


async def test_payload_is_a_read_and_leaks_no_internal_identifiers(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        before = len(transactions(session))
        handed = await api.agent_payload({"slug": "report"})
        after = len(transactions(session))

    text = str(handed["text"])
    assert after == before
    assert not _ULID.search(text)
    assert not _HASH.search(text)


async def test_payload_requires_a_known_cell(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

        with pytest.raises(FlowError, match="name it"):
            await api.agent_payload({})
        with pytest.raises(CellNotFound):
            await api.agent_payload({"slug": "nope"})


async def test_settings_write_what_a_panel_renders_without_journaling(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        before = len(transactions(session))

        written = await api.settings_set({"reactivity": "lazy"})
        threshold = await api.settings_set({"eager_cost_threshold_s": 30})

        after = len(transactions(session))
        reread = api.hub.open(session.ref).store.manifest.settings

    assert written["settings"] == {
        "reactivity": "lazy",
        "eager_cost_threshold_s": 5.0,
    }
    assert threshold["settings"]["eager_cost_threshold_s"] == 30.0
    assert reread.reactivity == "lazy"
    assert after == before


async def test_reactivity_only_takes_the_words_it_has(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

        with pytest.raises(FlowError) as refused:
            await api.settings_set({"reactivity": "restart"})

        settings = api.hub.session("churn").store.manifest.settings

    assert "`auto`" in str(refused.value)
    assert settings.reactivity == "auto"
