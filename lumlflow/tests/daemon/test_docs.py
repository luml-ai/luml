"""The generated docs: the workspace cheatsheet and the per-flow sidecar.

The quickstart's length is a contract, not a preference — Tier-0 says an agent
learns the whole loop from it, and a cheatsheet nobody finishes reading teaches
nothing. The sidecar's contract is that it is true whenever anyone looks.
"""

from pathlib import Path

from lumlflow.flow.daemon import docs
from lumlflow.flow.store.flowstore import store_dir

from tests.daemon.helpers import (
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    make_workspace,
    no_git_words,
    write_cell,
)

QUICKSTART_LINES = 22


def test_the_quickstart_fits_in_about_twenty_lines_and_names_the_three_gestures():
    lines = docs.QUICKSTART.strip().splitlines()

    assert len(lines) <= QUICKSTART_LINES
    assert "lumlflow run <cell>" in docs.QUICKSTART
    assert "lumlflow status" in docs.QUICKSTART
    assert "lumlflow context" in docs.QUICKSTART


async def test_agents_md_lands_at_the_workspace_root_and_names_every_flow(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})

    generated = (root / docs.AGENTS_NAME).read_text("utf-8")
    assert "`churn`" in generated and "`sales`" in generated
    assert docs.QUICKSTART in generated
    # The authoring defaults an agent has to know before it writes a cell.
    assert "Declare `asset` unless you mean to publish" in generated
    assert "Always name a cell" in generated
    assert "immutable" in generated


async def test_a_teams_own_instructions_survive_the_generated_block(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    (root / docs.AGENTS_NAME).write_text(
        "# Our house rules\n\nRun the linter before you finish.\n", encoding="utf-8"
    )

    async with daemon_api(root) as api:
        await api.status({})
        first = (root / docs.AGENTS_NAME).read_text("utf-8")
        await api.status({})
        again = (root / docs.AGENTS_NAME).read_text("utf-8")

    assert first.startswith("# Our house rules")
    assert "Run the linter before you finish." in first
    assert docs.BEGIN_MARKER in first and docs.END_MARKER in first
    # Regenerating is idempotent, or every verb would rewrite a watched file.
    assert again == first


async def test_the_sidecar_is_true_the_moment_the_checkout_lands(tmp_path: Path):
    """Written on the way out of the op, not at the next one — a file that says
    the flow is not checked out while it is teaches an agent to distrust it."""
    root = make_workspace(tmp_path / "project", flows=())
    sidecar = store_dir(root / "churn.flow") / docs.CHECKOUT_NAME

    async with daemon_api(root) as api:
        await api.flow_init({"name": "churn"})
        unbound = sidecar.read_text("utf-8")
        await api.flow_checkout({"flow": "churn", "branch": "main"})
        bound = sidecar.read_text("utf-8")

    # The API path creates a flow unbound, and says so.
    assert "(not on disk)" in unbound
    assert "(not on disk)" not in bound
    assert "lane: `main`" in bound


async def test_the_checkout_sidecar_says_where_the_flow_is_and_what_is_not_current(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        before = (store_dir(flow) / docs.CHECKOUT_NAME).read_text("utf-8")
        await api.run({"flow": "churn", "target": "report"})
        after = (store_dir(flow) / docs.CHECKOUT_NAME).read_text("utf-8")

    assert "lane: `main`" in before
    assert "## Stale (2)" in before
    assert "`report`: never run" in before
    # A run is what moves staleness, and the sidecar follows it without a verb.
    assert "Everything on this lane is current." in after
    assert "checkpoint: step" in after


async def test_the_generated_block_never_speaks_the_vocabulary_git_owns(
    tmp_path: Path,
):
    """`AGENTS.md` sits at the root of a git repository. It teaches our words."""
    root = make_workspace(tmp_path / "project", flows=("churn",))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

    no_git_words((root / docs.AGENTS_NAME).read_text("utf-8"), "AGENTS.md")
    no_git_words(docs.QUICKSTART, "the quickstart")
    no_git_words(docs.CHEATSHEET, "the cheatsheet")


async def test_the_sidecar_never_speaks_the_vocabulary_git_owns(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})

    sidecar = (store_dir(flow) / docs.CHECKOUT_NAME).read_text("utf-8")
    no_git_words(sidecar, "the on-disk sidecar")
