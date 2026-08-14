"""Send-to-agent payloads, and the settings a panel writes.

The gesture decides what the agent is handed, so each one is asserted for the
facts it exists to carry — the traceback for *fix this*, the branching point for
*explain this diff*, the branch's story for *summarize this branch* — and all of
them for what none may carry: the identifiers the runtime keys on.
"""

import re
from pathlib import Path

import pytest
from lumlflow.flow.errors import CellNotFound, FlowError

from tests.daemon.helpers import (
    BROKEN_CELL,
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    make_workspace,
    no_git_words,
    transactions,
    write_cell,
)

NOTE_CELL = '''
class BranchNotes:
    """# what this branch is for

    the sweep over learning rates.
    """
'''

_HASH = re.compile(r"\b[0-9a-f]{16,}\b")
_ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")


def _block(payload: dict[str, object]) -> dict[str, str]:
    """The fenced block as `key: value` pairs — what a reader parses back out."""
    text = str(payload["text"])
    body = text.split("```")[1].splitlines()[1:]
    return dict(
        (line.split(":", 1)[0].strip(), line.split(":", 1)[1].strip())
        for line in body
        if line and not line.startswith("  ") and ":" in line
    )


def _listed(payload: dict[str, object], label: str) -> list[str]:
    """The rows under one `label:` heading."""
    rows: list[str] = []
    collecting = False
    for line in str(payload["text"]).splitlines():
        if line.startswith(f"{label}:"):
            collecting = True
            continue
        if collecting and line.startswith("  - "):
            rows.append(line[4:])
        elif collecting and not line.startswith("  "):
            break
    return rows


async def test_fix_carries_the_traceback_of_the_run_the_branch_observed(
    tmp_path: Path,
):
    """The payload is the reason the gesture beats retyping the cell's name.

    Nothing on any surface had to open the logs for this: the failure is a
    recorded fact, and the handoff is built where it is recorded.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", BROKEN_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "score"})

        handed = await api.agent_payload({"gesture": "fix", "slug": "score"})

    fields = _block(handed)
    assert (handed["gesture"], handed["branch"]) == ("fix", "main")
    assert fields["cell"] == "score"
    assert fields["state"] == "failed"
    # Which version, as a step — the one spelling a rewind or the timeline takes.
    assert fields["version"].startswith("accepted at step ")
    # The file, because this branch is the one the files hold.
    assert fields["file"] == "churn.flow/cells/score.py"
    assert "traceback: |" in str(handed["text"])
    assert "Traceback (most recent call last)" in str(handed["text"])
    assert "lumlflow run score" in str(handed["text"])


async def test_fix_on_a_branch_nobody_checked_out_names_no_file(tmp_path: Path):
    """A fork's cells are in the store, not on disk — naming a path would send
    the agent to another branch's copy of the cell."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", BROKEN_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "score"})
        await api.fork({"name": "sweep"})

        handed = await api.agent_payload(
            {"gesture": "fix", "slug": "score", "branch": "sweep"}
        )

    assert handed["branch"] == "sweep"
    assert "file:" not in str(handed["text"])
    assert "traceback: |" in str(handed["text"])


async def test_explain_carries_the_wiring_and_the_docstring(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "report"})

        handed = await api.agent_payload({"gesture": "explain", "slug": "report"})

    fields = _block(handed)
    assert fields["cell"] == "report"
    assert fields["state"] == "synced"
    assert _listed(handed, "consumes") == ["score.summary"]
    assert "doc: |" in str(handed["text"])


async def test_diff_names_the_branching_point_apart_from_the_results(
    tmp_path: Path,
):
    """Definition divergence is the edit; materialization divergence is
    everything the edit moved below it. One list would hide the branching
    point in the noise it caused."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "report"})
        await api.fork({"name": "sweep"})
        await api.cells_edit(
            {
                "branch": "sweep",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.77"),
            }
        )
        await api.run({"target": "report", "branch": "sweep"})

        handed = await api.agent_payload(
            {"gesture": "diff", "branches": ["main", "sweep"]}
        )

    assert handed["gesture"] == "diff"
    assert _listed(handed, "definition-divergence") == [
        "score: edited on `main` and `sweep`"
    ]
    assert _listed(handed, "materialization-divergence") == [
        "report: same code, different results"
    ]


async def test_summarize_asks_for_a_note_cell_and_carries_the_branch_story(
    tmp_path: Path,
):
    """No store field holds a branch description; a note cell is a real
    versioned asset that travels with the flow, so that is what is asked for."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "notes", NOTE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "score"})
        await api.fork({"name": "sweep", "intent": "sweeping learning rates"})
        await api.set_focus({"branch": "sweep", "asset": "score"})

        handed = await api.agent_payload({"gesture": "summarize", "branch": "sweep"})

    fields = _block(handed)
    assert "note cell" in str(handed["text"])
    assert fields["started-from"].startswith("main at step ")
    assert fields["cells"] == "2"
    assert fields["focus"] == "the reader is looking at score"
    assert _listed(handed, "assets") == ["score: synced, metric"]
    assert _listed(handed, "notes") == ["notes"]
    assert "sweeping learning rates, by user" in _listed(handed, "recent")


async def test_summarize_omits_a_focus_nobody_reported(tmp_path: Path):
    """A guessed focus is worse than none: the brief omits it the same way."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

        handed = await api.agent_payload({"gesture": "summarize"})

    assert "focus:" not in str(handed["text"])


async def test_a_handoff_records_nothing_and_leaks_no_identifiers(tmp_path: Path):
    """A payload is a read. It is also a string an agent reads back to us, so
    it speaks slugs and branch names and nothing the runtime keys on."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "report"})
        await api.fork({"name": "sweep"})
        session = api.hub.session("churn")
        before = len(transactions(session))

        handed = [
            await api.agent_payload({"gesture": "fix", "slug": "report"}),
            await api.agent_payload({"gesture": "explain", "slug": "score"}),
            await api.agent_payload({"gesture": "diff", "branches": ["main", "sweep"]}),
            await api.agent_payload({"gesture": "summarize"}),
        ]

        after = len(transactions(session))

    assert after == before
    for payload in handed:
        text = str(payload["text"])
        assert not _ULID.search(text), text
        assert not _HASH.search(text), text


async def test_an_unknown_gesture_and_a_nameless_one_are_refused_by_name(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

        with pytest.raises(FlowError) as unknown:
            await api.agent_payload({"gesture": "rewrite", "slug": "score"})
        with pytest.raises(FlowError) as nameless:
            await api.agent_payload({"gesture": "fix"})
        with pytest.raises(CellNotFound):
            await api.agent_payload({"gesture": "fix", "slug": "nope"})

    assert "`summarize`" in str(unknown.value)
    assert "name it" in str(nameless.value)


async def test_settings_write_what_a_panel_renders_and_leave_the_rest(
    tmp_path: Path,
):
    """Config, not history: the panel's three settings land in `flow.yaml` and
    the runtime's own — sandbox, the safety modes — are not this verb's."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        session.store.manifest.settings.paranoid = True
        before = len(transactions(session))

        written = await api.settings_set({"env_policy": "auto", "reactivity": "lazy"})
        threshold = await api.settings_set({"eager_cost_threshold_s": 30})

        after = len(transactions(session))
        reread = api.hub.open(session.ref).store.manifest.settings

    assert written["settings"] == {
        "reactivity": "lazy",
        "eager_cost_threshold_s": 5.0,
        "env_policy": "auto",
    }
    assert threshold["settings"]["eager_cost_threshold_s"] == 30.0
    # Untouched by an env-policy write, and still on after both.
    assert (reread.paranoid, reread.reactivity, reread.env_policy) == (
        True,
        "lazy",
        "auto",
    )
    assert after == before


async def test_a_setting_only_takes_the_words_it_has(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

        with pytest.raises(FlowError) as refused:
            await api.settings_set({"env_policy": "restart"})

        settings = api.hub.session("churn").store.manifest.settings

    assert "`ask`" in str(refused.value)
    assert settings.env_policy == "ask"


async def test_no_gesture_hands_an_agent_the_vocabulary_git_owns(tmp_path: Path):
    """Four payloads, read by an agent working in a git repository."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", BROKEN_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"target": "report"})
        await api.fork({"name": "sweep", "intent": "a lower lr"})
        handed = {
            "fix": await api.agent_payload({"gesture": "fix", "slug": "report"}),
            "explain": await api.agent_payload(
                {"gesture": "explain", "slug": "score"}
            ),
            "diff": await api.agent_payload(
                {"gesture": "diff", "branches": ["main", "sweep"]}
            ),
            "summarize": await api.agent_payload({"gesture": "summarize"}),
        }

    for gesture, payload in handed.items():
        # A traceback is the runtime's own words, and quotes the cell file.
        spoken = str(payload["text"]).split("traceback: |")[0]
        no_git_words(spoken, f"the `{gesture}` handoff")
