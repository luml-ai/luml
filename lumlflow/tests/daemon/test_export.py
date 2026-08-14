"""Export and import: a flow's travelling form, and the trip back.

The claim under test is that the round trip is one — the same cells, under the
same identities, hashing to the same definitions on the other side. Anything
less and an export would be a copy of a flow's text rather than the flow, and
importing one back would read as twelve new cells rather than the twelve that
left.
"""

from pathlib import Path

import pytest
from lumlflow.flow.dsl import portable
from lumlflow.flow.errors import FlowError, WorktreeLocked
from lumlflow.flow.store.models import CellAccepted, Transaction

from tests.daemon.helpers import (
    REPORT_CELL,
    SCORE_CELL,
    cell_files,
    daemon_api,
    make_workspace,
    slice_of,
    source_of,
    transactions,
    write_cell,
)


async def test_a_round_trip_keeps_each_cells_identity_and_definition(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "copy"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        exported = await api.export({"flow": "churn"})
        await api.import_cells({"flow": "copy", "source": exported["source"]})
        left = slice_of(api.hub.session("churn"), "main")
        arrived = slice_of(api.hub.session("copy"), "main")

    assert set(arrived) == set(left) == {"score", "report"}
    assert {slug: cell.uid for slug, cell in arrived.items()} == {
        slug: cell.uid for slug, cell in left.items()
    }
    assert {slug: cell.definition_hash for slug, cell in arrived.items()} == {
        slug: cell.definition_hash for slug, cell in left.items()
    }
    # The wiring came with them: `report` reads the `score` that arrived beside
    # it, not a name that resolved to nothing.
    assert arrived["report"].manifest.consumes["summary"].uid == arrived["score"].uid
    assert not arrived["report"].flags


async def test_the_export_reads_producers_first_and_renders_the_same_bytes_twice(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "report", REPORT_CELL)
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        once = await api.export({"flow": "churn"})
        twice = await api.export({"flow": "churn"})

    # By name `report` comes first; by wiring it cannot.
    assert once["cells"] == ["score", "report"]
    assert once["source"].index(f"{portable.MARKER}score") < once["source"].index(
        f"{portable.MARKER}report"
    )
    assert once["source"] == twice["source"]


async def test_a_branch_nobody_checked_out_exports_from_the_store(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        await api.fork({"flow": "churn", "name": "sweep"})
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "sweep",
                "slug": "score",
                "source": SCORE_CELL.replace("0.91", "0.99"),
            }
        )
        exported = await api.export({"flow": "churn", "branch": "sweep"})
        checked_out = await api.export({"flow": "churn"})

    assert "0.99" in exported["source"]
    assert "branch `sweep`" in exported["source"]
    assert "0.91" in checked_out["source"]


async def test_an_import_lands_as_one_transaction_and_writes_the_files(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "copy"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        exported = await api.export({"flow": "churn"})
        await api.flow_checkout({"flow": "copy", "branch": "main"})
        before = len(transactions(api.hub.session("copy")))
        result = await api.import_cells(
            {
                "flow": "copy",
                "source": exported["source"],
                "intent": "took the churn cells",
            }
        )
        landed = _accepting(transactions(api.hub.session("copy"))[before:])

    assert [cell["slug"] for cell in result["cells"]] == ["score", "report"]
    assert [entry.intent for entry in landed] == ["took the churn cells"]
    assert len([op for op in landed[0].ops if isinstance(op, CellAccepted)]) == 2
    assert cell_files(root / "copy.flow") == ["report", "score"]
    assert sorted(result["projected"]["written"]) == ["report", "score"]


async def test_importing_an_edited_export_edits_the_cell_it_names(tmp_path: Path):
    """The same cell, a version further on — never a second cell beside it."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        exported = await api.export({"flow": "churn"})
        before = slice_of(api.hub.session("churn"), "main")["score"]
        await api.import_cells(
            {"flow": "churn", "source": exported["source"].replace("0.91", "0.99")}
        )
        after = slice_of(api.hub.session("churn"), "main")

    assert list(after) == ["score"]
    assert after["score"].uid == before.uid
    assert after["score"].version_id != before.version_id
    assert "0.99" in source_of(root / "churn.flow", "score")


async def test_reimporting_an_untouched_export_writes_no_version(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        exported = await api.export({"flow": "churn"})
        before = len(transactions(api.hub.session("churn")))
        await api.import_cells({"flow": "churn", "source": exported["source"]})
        after = _accepting(transactions(api.hub.session("churn"))[before:])

    assert after == []


async def test_a_hand_reordered_file_still_binds_its_references(tmp_path: Path):
    """The format writes producers first; a file somebody rearranged need not."""
    root = make_workspace(tmp_path / "project")
    upside_down = (
        f"{portable.MARKER}report\n{REPORT_CELL.strip()}\n\n"
        f"{portable.MARKER}score\n{SCORE_CELL.strip()}\n"
    )

    async with daemon_api(root) as api:
        result = await api.import_cells({"flow": "churn", "source": upside_down})
        landed = slice_of(api.hub.session("churn"), "main")

    assert [cell["slug"] for cell in result["cells"]] == ["report", "score"]
    assert landed["report"].manifest.consumes["summary"].uid == landed["score"].uid
    assert not landed["report"].flags


async def test_a_name_that_is_a_path_is_refused_and_nothing_lands(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    doctored = f"{portable.MARKER}../../escape\n{SCORE_CELL.strip()}\n"

    async with daemon_api(root) as api:
        with pytest.raises(FlowError, match="not a name a cell can have"):
            await api.import_cells({"flow": "churn", "source": doctored})
        landed = slice_of(api.hub.session("churn"), "main")

    assert landed == {}
    assert not (tmp_path / "escape.py").exists()
    assert cell_files(root / "churn.flow") == []


async def test_an_import_waits_for_the_agent_holding_the_files(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "copy"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        exported = await api.export({"flow": "churn"})
        await api.flow_checkout({"flow": "copy", "branch": "main"})
        await api.agent_begin({"flow": "copy", "label": "claude-1"})
        with pytest.raises(WorktreeLocked, match="claude-1"):
            await api.import_cells({"flow": "copy", "source": exported["source"]})
        withheld = slice_of(api.hub.session("copy"), "main")
        forced = await api.import_cells(
            {"flow": "copy", "source": exported["source"], "force": True}
        )

    assert withheld == {}
    assert [cell["slug"] for cell in forced["cells"]] == ["score"]
    assert cell_files(root / "copy.flow") == ["score"]


async def test_a_block_duplicated_under_a_new_name_is_refused_not_collapsed(
    tmp_path: Path,
):
    """Both blocks name one cell, so importing both would land one — and say two."""
    root = make_workspace(tmp_path / "project", flows=("churn", "copy"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        exported = await api.export({"flow": "churn"})
        variant = _duplicated(exported["source"], as_slug="score_hi")
        with pytest.raises(FlowError, match="`score` and `score_hi` as one cell"):
            await api.import_cells({"flow": "copy", "source": variant})
        with pytest.raises(FlowError, match="holds `score` twice"):
            await api.import_cells(
                {"flow": "copy", "source": _duplicated(exported["source"])}
            )
        landed = slice_of(api.hub.session("copy"), "main")
        # The remedy the message names: a block of its own arrives as its own cell.
        await api.import_cells(
            {"flow": "copy", "source": _without_uid(variant, slug="score_hi")}
        )
        both = slice_of(api.hub.session("copy"), "main")

    assert landed == {}
    assert sorted(both) == ["score", "score_hi"]
    assert both["score"].uid != both["score_hi"].uid


async def test_an_empty_flow_exports_and_imports_as_nothing(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "copy"))

    async with daemon_api(root) as api:
        exported = await api.export({"flow": "churn"})
        imported = await api.import_cells(
            {"flow": "copy", "source": exported["source"]}
        )

    assert exported["cells"] == []
    assert imported["cells"] == []


def _duplicated(source: str, *, as_slug: str | None = None) -> str:
    """The file with its last block written twice — a variant made by hand."""
    slug, block = source.rsplit(portable.MARKER, 1)[1].split("\n", 1)
    name = as_slug or slug
    return f"{source}\n\n{portable.MARKER}{name}\n{block}"


def _without_uid(source: str, *, slug: str) -> str:
    """One block's uid line dropped — what the refusal tells the user to do."""
    head, block = source.rsplit(f"{portable.MARKER}{slug}\n", 1)
    kept = [line for line in block.split("\n") if not line.strip().startswith("uid =")]
    return f"{head}{portable.MARKER}{slug}\n" + "\n".join(kept)


def _accepting(entries: list[Transaction]) -> list[Transaction]:
    """The transactions that took a cell in — never the housekeeping around them."""
    return [
        entry
        for entry in entries
        if any(isinstance(op, CellAccepted) for op in entry.ops)
    ]
