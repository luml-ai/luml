"""The flow verbs, mounted on `lumlflow`.

Three of these are the whole product: edit a cell file, `lumlflow run <cell>`,
`lumlflow status`. Everything else is progressive disclosure, and everything
goes through the workspace daemon — which the first verb to need one starts, so
no session has to be connected, selected, or configured anywhere.

Two rules hold across every verb. `--json` gives a program the answer verbatim,
including the identifiers the printed form leaves out. `-m/--intent` says why a
mutation happened, and rides into the journal beside it: a history of *what*
changed, with no *why*, is not a history anybody reads twice.

A flow lives inside somebody's git repository, so no verb here may be spelled
the way git spells one, and no verb may be spelled the way the rest of this
platform spells one either. The four that were — `fork`, `switch`, `tree` and
`archive` — are now `lumlflow lane new / use / list / archive`. Every earlier
spelling still answers and none is shown: the `variant` group, those four
top-level verbs, and the `--variant`, `--branch` and `--unsynced` options. What
the wire calls these operations did not move; see `frontend/DESIGN.md` for the
boundary.
"""

import contextlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import typer

from lumlflow.flow import render
from lumlflow.flow.dsl import portable
from lumlflow.flow.errors import FlowError

ACTOR_ENV = "LUMLFLOW_ACTOR"

cells_app = typer.Typer(help="Add, read, edit and remove cells.", no_args_is_help=True)
asset_app = typer.Typer(help="Read what a cell produced.", no_args_is_help=True)
lane_app = typer.Typer(
    help="Make, use, list and retire this flow's lanes.", no_args_is_help=True
)
agent_app = typer.Typer(
    help="Register an agent session by hand. An MCP client needs none of this.",
    no_args_is_help=True,
)
secrets_app = typer.Typer(help="Secrets a cell can ask for.", no_args_is_help=True)
env_app = typer.Typer(help="The workspace's packages.", no_args_is_help=True)
flow_app = typer.Typer(help="Manage flows in this workspace.", no_args_is_help=True)
# Plumbing, kept reachable for tests and power users and shown to nobody: the
# product has no background process the user is asked to know about.
daemon_app = typer.Typer(
    help="The background server for this workspace.", no_args_is_help=True
)

_JSON = typer.Option(False, "--json", help="Answer as JSON, verbatim.")
_FLOW = typer.Option(None, "--flow", help="Which flow, when the workspace has several.")
_LANE = typer.Option(None, "--lane", help="Which lane. Defaults to the one on disk.")
# The two spellings this option had before lanes got their word. Declared
# separately rather than as further names, because click prints every name a
# parameter answers to and neither of these must be taught.
_LANE_WAS = typer.Option(None, "--variant", hidden=True)
_BRANCH_WAS = typer.Option(None, "--branch", hidden=True)
_INTENT = typer.Option(None, "-m", "--intent", help="Why. Recorded in the journal.")
_FORCE = typer.Option(
    False, "--force", help="Proceed even if an agent holds the files."
)

def register(app: typer.Typer) -> None:
    """Mount the flow verbs on the top-level app."""
    for command in (
        init,
        status,
        context,
        graph,
        run,
        eval,
        preflight,
        cancel,
        rewind,
        adopt,
        diff,
        rename,
        promote,
        export,
        root,
        mcp,
    ):
        app.command()(command)
    # `import` is a keyword, so the verb and the function that serves it cannot
    # share a name.
    app.command("import")(import_cells)
    # The spellings these four had before lanes got their word. Each is a git
    # verb, which is why it moved; each still answers, so no script and no habit
    # breaks on the rename.
    for spelling, retired in (
        ("fork", lane_new),
        ("switch", lane_use),
        ("tree", lane_list),
        ("archive", lane_archive),
    ):
        app.command(spelling, hidden=True)(retired)
    app.add_typer(cells_app, name="cells")
    app.add_typer(asset_app, name="asset")
    app.add_typer(lane_app, name="lane")
    # The group's own earlier spelling, mounted a second time and taught to
    # nobody. `variant` is the platform's word for something else.
    app.add_typer(lane_app, name="variant", hidden=True)
    app.add_typer(agent_app, name="agent")
    app.add_typer(secrets_app, name="secrets")
    app.add_typer(env_app, name="env")
    app.add_typer(flow_app, name="flow")
    app.add_typer(daemon_app, name="daemon", hidden=True)


def _lane(*spellings: str | None) -> str | None:
    """One lane name out of the three spellings this CLI accepts."""
    return next((named for named in spellings if named is not None), None)


def init(
    name: str | None = typer.Argument(
        None, help="The flow's name. Defaults to this directory's."
    ),
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Scaffold a flow here and put `main` on disk."""
    with _daemon(as_json) as daemon:
        workspace_root = daemon.root
        created = daemon.call(
            "flow.init", {"name": name or workspace_root.name}, scoped=False
        )
        opened = daemon.call(
            "flow.checkout",
            {"flow": created["path"], "branch": "main", "intent": intent},
            scoped=False,
        )
    result = created | opened
    _emit(
        result,
        as_json,
        [
            f"created `{result['flow']}` at {result['path']} on `{result['branch']}`",
            *(f"warning: {warning}" for warning in result.get("warnings") or []),
            f"write cells into {result['path']}/cells/, then `lumlflow run <cell>`",
        ],
    )


def status(flow: str | None = _FLOW, as_json: bool = _JSON) -> None:
    """The workspace, its flows, and what is stale in each."""
    result = _call("status", flow=flow, as_json=as_json)
    _emit(result, as_json, render.status)


def context(
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """Where you are, what is stale and why, what broke, and what it costs."""
    params = {"branch": _lane(lane, variant, branch)}
    result = _call("context", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.context)


@lane_app.command("list")
def lane_list(flow: str | None = _FLOW, as_json: bool = _JSON) -> None:
    """Every lane, where it started, and how it stands."""
    result = _call("tree", flow=flow, as_json=as_json)
    _emit(result, as_json, render.tree)


def graph(
    around: str | None = typer.Option(None, "--around", help="Centre on this cell."),
    depth: int = typer.Option(2, "--depth", help="How many hops from `--around`."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """The declared wiring. This is the graph the scheduler runs."""
    params = {"branch": _lane(lane, variant, branch), "around": around, "depth": depth}
    result = _call("graph", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.graph)


def run(
    target: str = typer.Argument(..., help="A cell, as `cell` or `cell.output`."),
    force: bool = typer.Option(
        False, "--force", help="Recompute even what is cached or already current."
    ),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """Run a cell, and whatever it needs, first.

    This verb takes no `-m`. A run records the runtime's own fact instead:
    `ran features`, `features failed`, or `reused a cached features`. That is
    more honest than a sentence typed before anybody knew which it would be.

    `--force` spends the closure's cost again on purpose. It drops memoization
    for this run, so the store serves nothing and every cell computes.
    """
    params = {"target": target, "branch": _lane(lane, variant, branch), "force": force}
    result = _call("run", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.outcome)
    if result.get("failed"):
        raise typer.Exit(1)


def eval(
    code: str = typer.Argument(..., help="Python to run against a lane's values."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """Try something against a lane's values. Nothing is written.

    Cells are in scope by name. A cell's primary output takes the cell's own
    name; every output is also `cell_output`. What you get is a copy. A
    mutation here reaches no other lane, no stored value, and no cell.
    Every lane evaluates, on disk or not.
    """
    params = {"code": code, "branch": _lane(lane, variant, branch)}
    result = _call("eval", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.evaluated)
    if result.get("error"):
        raise typer.Exit(1)


def preflight(
    target: str = typer.Argument(..., help="A cell, as `cell` or `cell.output`."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """What running it recomputes, reuses, and costs. Read this before you run."""
    params = {"target": target, "branch": _lane(lane, variant, branch)}
    result = _call("preflight", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.preflight)


def cancel(
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """Stop waiting on the run this lane asked for."""
    params = {"branch": _lane(lane, variant, branch)}
    result = _call("cancel", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.abandoned(result))


@lane_app.command("new")
def lane_new(
    name: str = typer.Argument(..., help="The new lane's name."),
    from_lane: str | None = typer.Option(
        None, "--from", help="The lane to start from."
    ),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Start a lane. One row. No file and no value is copied."""
    params = {"name": name, "from_branch": from_lane, "intent": intent}
    result = _call("fork", params, flow=flow, as_json=as_json)
    _emit(
        result,
        as_json,
        [
            f"started `{result['branch']}` from `{result['from_branch']}` "
            f"at step {result['forked_at_step']} · {result['cells']} cells, "
            "pinned as they were"
        ],
    )


@lane_app.command("use")
def lane_use(
    lane: str = typer.Argument(..., help="The lane to put on disk."),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    force: bool = _FORCE,
    as_json: bool = _JSON,
) -> None:
    """Put a lane's cells on disk. The files rebind to its selection."""
    params = {"branch": lane, "intent": intent, "force": force}
    result = _call("switch", params, flow=flow, as_json=as_json)
    _emit(result, as_json, [f"on `{result['branch']}`", *_projected(result)])


def rewind(
    to_step: int = typer.Argument(..., help="The step to restore this lane to."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    force: bool = _FORCE,
    as_json: bool = _JSON,
) -> None:
    """Restore a lane to a step. This is instant. Nothing recomputes."""
    params = {
        "to_step": to_step,
        "branch": _lane(lane, variant, branch),
        "intent": intent,
        "force": force,
    }
    result = _call("rewind", params, flow=flow, as_json=as_json)
    _emit(
        result,
        as_json,
        [
            f"`{result['branch']}` is back at step {result['to_step']} · "
            f"{result['cells']} cells",
            *_projected(result),
        ],
    )


def adopt(
    slug: str = typer.Argument(..., help="The cell to take."),
    from_lane: str = typer.Option(..., "--from", help="The lane to take it from."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    force: bool = typer.Option(False, "--force", help="Take the incoming side."),
    as_json: bool = _JSON,
) -> None:
    """Take one cell's version from another lane onto this one."""
    params = {
        "slug": slug,
        "from_branch": from_lane,
        "branch": _lane(lane, variant, branch),
        "intent": intent,
        "force": force,
    }
    result = _call("adopt", params, flow=flow, as_json=as_json)
    rebound = result.get("rebound") or []
    _emit(
        result,
        as_json,
        [
            f"`{result['slug']}` on `{result['branch']}` is now "
            f"`{from_lane}`'s version",
            *(
                [f"rebound, and now pointing at it: {', '.join(rebound)}"]
                if rebound
                else []
            ),
            *_projected(result),
        ],
    )


@lane_app.command("archive")
def lane_archive(
    lane: str = typer.Argument(..., help="The lane to archive."),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Put a lane away. Nothing it produced is deleted."""
    params = {"branch": lane, "intent": intent}
    result = _call("archive", params, flow=flow, as_json=as_json)
    _emit(result, as_json, [f"archived `{result['branch']}`. its results are kept"])


def diff(
    lanes: list[str] = typer.Argument(..., help="Two to five lanes."),
    flow: str | None = _FLOW,
    as_json: bool = _JSON,
) -> None:
    """How lanes differ. Edited cells first, then results, then the rest."""
    result = _call("diff", {"branches": lanes}, flow=flow, as_json=as_json)
    _emit(result, as_json, render.diff)


def rename(
    slug: str = typer.Argument(..., help="The cell to rename."),
    to: str = typer.Argument(..., help="Its new name."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    force: bool = _FORCE,
    as_json: bool = _JSON,
) -> None:
    """Rename a cell. References bind to identity, so this costs nothing."""
    params = {
        "slug": slug,
        "to": to,
        "branch": _lane(lane, variant, branch),
        "intent": intent,
        "force": force,
    }
    result = _call("rename", params, flow=flow, as_json=as_json)
    rewired = result.get("rewired") or []
    _emit(
        result,
        as_json,
        [
            f"`{result['renamed_from']}` is now `{result['slug']}`. nothing went stale",
            *([f"rewritten to match: {', '.join(rewired)}"] if rewired else []),
        ],
    )


def export(
    to: Path = typer.Argument(..., help="The file to write, as `flow.py`."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """Write a lane's cells out as one Python file.

    This exports a file, not the flow. It carries the cells as they stand and
    nothing else: no history, no results, and no other lanes. It is how a
    flow travels. The flow itself stays a directory. `lumlflow import` reads
    the file back, and each cell keeps the identity it left with.
    """
    with _daemon(as_json, flow=flow) as daemon:
        result = daemon.call("export", {"branch": _lane(lane, variant, branch)})
        written = _write_export(Path(to), result["source"])
        note = _shared_code_note(written, daemon.root)
    result = result | {"path": str(written)}
    carried = portable.counted(len(result["cells"]))
    _emit(
        result,
        as_json,
        [
            f"wrote {written} · {carried} from `{result['branch']}`",
            "this file holds the cells. it holds no history and no results",
            *note,
        ],
    )


def import_cells(
    source: Path = typer.Argument(..., help="A file `lumlflow export` wrote."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    force: bool = _FORCE,
    as_json: bool = _JSON,
) -> None:
    """Read an exported file back into a lane, cell for cell.

    This edits a cell the flow already knows. It never duplicates one. The
    file carries each cell's identity, which is what makes the round trip one.
    """
    with _daemon(as_json, flow=flow) as daemon:
        result = daemon.call(
            "import",
            {
                "source": _read_export(Path(source)),
                "branch": _lane(lane, variant, branch),
                "intent": intent,
                "force": force,
            },
        )
    imported = result.get("cells") or []
    landed = portable.counted(len(imported))
    headline = (
        f"imported {landed} into `{result['branch']}`: {_names(imported)}"
        if imported
        else f"{source} holds no cells. nothing was imported"
    )
    _emit(
        result,
        as_json,
        [
            headline,
            *(
                f"  {flag['detail'] or flag['code']}"
                for cell in imported
                for flag in cell["flags"]
            ),
            *_projected(result),
        ],
    )


def root(as_json: bool = _JSON) -> None:
    """The workspace this directory belongs to."""
    from lumlflow.flow.daemon import workspace

    resolved = workspace.resolve_root(Path.cwd())
    _emit({"workspace": str(resolved)}, as_json, [str(resolved)])


def mcp(
    workspace: Path | None = typer.Option(
        None, "--workspace", help="The workspace to serve. Defaults to this one."
    ),
    label: str | None = typer.Option(
        None, "--label", help="What to call the session. Defaults to the client's name."
    ),
) -> None:
    """Serve this workspace to an agent over MCP, on stdio.

    Do not run this verb by hand. An MCP client spawns it and speaks the
    protocol down its stdin. Every tool it offers goes where the verbs go. An
    agent working this way and one running verbs reach the same store.

    `--workspace` is what makes a configuration portable. An MCP client spawns
    its servers from whatever directory it is in. A workspace inferred from
    that directory is a workspace that moves.
    """
    from lumlflow.flow.daemon import mcp as server

    # Nothing is echoed here, ever — stdout is the protocol.
    raise typer.Exit(
        server.serve(
            root=Path(workspace).expanduser().resolve() if workspace else None,
            label=label or os.environ.get(ACTOR_ENV),
        )
    )


@cells_app.command("list")
def cells_list(
    stale: bool = typer.Option(False, "--stale", help="Only what is stale."),
    # The spelling this flag had before `stale` became the one word for it.
    unsynced: bool = typer.Option(False, "--unsynced", hidden=True),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """What this lane holds."""
    params = {"branch": _lane(lane, variant, branch), "unsynced": stale or unsynced}
    result = _call("cells.list", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.cells)


@cells_app.command("show")
def cells_show(
    slug: str = typer.Argument(..., help="The cell to read."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """A cell in full: state, declarations, last run, source."""
    params = {"slug": slug, "branch": _lane(lane, variant, branch)}
    result = _call("cells.show", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.cell)


@cells_app.command("new")
def cells_new(
    slug: str | None = typer.Argument(None, help="The cell's name."),
    after: str | None = typer.Option(
        None, "--after", help="Prefill `consumes` from this cell's outputs."
    ),
    docstring: str | None = typer.Option(None, "--doc", help="The cell's docstring."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Scaffold a cell, wired to what it comes after."""
    params = {
        "slug": slug,
        "after": after,
        "docstring": docstring,
        "branch": _lane(lane, variant, branch),
        "intent": intent,
    }
    result = _call("cells.new", params, flow=flow, as_json=as_json)
    _emit(result, as_json, _edited(result, verb="added"))


@cells_app.command("edit")
def cells_edit(
    slug: str = typer.Argument(..., help="The cell to replace."),
    source: Path | None = typer.Option(
        None, "--source", help="File holding the new source. Reads stdin when absent."
    ),
    base: str | None = typer.Option(
        None, "--base", help="The version this edit started from, from `cells show`."
    ),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    force: bool = typer.Option(False, "--force", help="Overwrite a newer version."),
    as_json: bool = _JSON,
) -> None:
    """Replace a cell's source, attributed to you.

    `--base` opts into the same optimistic lock the editor in the browser
    takes. Hand back the version this edit started from. lumlflow then asks
    you what to do when a newer version landed, instead of overwriting it.
    """
    params = {
        "slug": slug,
        "source": (source.read_text("utf-8") if source else sys.stdin.read()),
        "base": base,
        "branch": _lane(lane, variant, branch),
        "intent": intent,
        "force": force,
    }
    result = _call("cells.edit", params, flow=flow, as_json=as_json)
    _emit(result, as_json, _edited(result, verb="edited"))


@cells_app.command("delete")
def cells_delete(
    slug: str = typer.Argument(..., help="The cell to drop from this lane."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    force: bool = _FORCE,
    as_json: bool = _JSON,
) -> None:
    """Drop a cell from this lane. Every other lane keeps its own."""
    params = {
        "slug": slug,
        "branch": _lane(lane, variant, branch),
        "intent": intent,
        "force": force,
    }
    result = _call("cells.delete", params, flow=flow, as_json=as_json)
    dangling = result.get("dangling") or []
    _emit(
        result,
        as_json,
        [
            f"`{result['slug']}` is gone from `{result['branch']}`. "
            "other lanes are untouched",
            *(
                [f"left pointing at nothing here: {', '.join(dangling)}"]
                if dangling
                else []
            ),
        ],
    )


@asset_app.command("preview")
def asset_preview(
    target: str = typer.Argument(..., help="`cell` or `cell.output`."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """What a cell produced, read from the stored preview. No kernel starts."""
    params = {"target": target, "branch": _lane(lane, variant, branch)}
    result = _call("asset.preview", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.asset)


@asset_app.command("page")
def asset_page(
    target: str = typer.Argument(..., help="`cell` or `cell.output`."),
    offset: int = typer.Option(0, "--offset", help="Where to start."),
    limit: int = typer.Option(20, "--limit", help="How much to read."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """Read into a value. This is the gesture that starts a kernel."""
    params = {
        "target": target,
        "branch": _lane(lane, variant, branch),
        "query": {"offset": offset, "limit": limit},
    }
    result = _call("asset.page", params, flow=flow, as_json=as_json)
    _emit(
        result, as_json, [json.dumps(result.get("page"), indent=2, ensure_ascii=False)]
    )


@asset_app.command("diff")
def asset_diff(
    target: str = typer.Argument(..., help="`cell` or `cell.output`."),
    lanes: list[str] = typer.Option([], "--lane", help="Given twice."),
    # The spellings this option had before lanes got their word.
    variants: list[str] = typer.Option([], "--variant", hidden=True),
    branches: list[str] = typer.Option([], "--branch", hidden=True),
    flow: str | None = _FLOW,
    as_json: bool = _JSON,
) -> None:
    """One cell's code and results across two lanes."""
    named = list(lanes) or list(variants) or list(branches)
    params = {"target": target, "branches": named}
    result = _call("asset.diff", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.asset_diff)


@asset_app.command("download")
def asset_download(
    target: str = typer.Argument(..., help="`cell` or `cell.output`."),
    to: Path | None = typer.Option(None, "--to", help="Where to write it."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    as_json: bool = _JSON,
) -> None:
    """Copy a stored value out of the flow."""
    params = {
        "target": target,
        "branch": _lane(lane, variant, branch),
        "to": str(Path(to).resolve()) if to else str(Path.cwd()),
    }
    result = _call("asset.download", params, flow=flow, as_json=as_json)
    _emit(
        result,
        as_json,
        [f"wrote {result['path']} · {result['kind']}, {result['size']} bytes"],
    )


def promote(
    target: str = typer.Argument(..., help="`cell` or `cell.output`."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    variant: str | None = _LANE_WAS,
    branch: str | None = _BRANCH_WAS,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Publish a stored asset to LUML.

    Declare `asset` unless you mean to publish, then promote later. The bytes
    are staged the moment the cell succeeds. This verb only asks the platform
    to keep a copy of what the flow already holds.
    """
    params = {
        "target": target,
        "branch": _lane(lane, variant, branch),
        "intent": intent,
    }
    result = _call("promote", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.published)


@agent_app.command("begin")
def agent_begin(
    label: str = typer.Option(..., "--label", help="What to call this session."),
    actor: str | None = typer.Option(None, "--actor", help="Defaults to the label."),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Register an agent session. It owns the flow's files until it ends."""
    params = {"label": label, "actor": actor or label, "intent": intent}
    result = _call("agent.begin", params, flow=flow, as_json=as_json)
    _emit(result, as_json, [f"`{result['label']}` is working here"])


@agent_app.command("end")
def agent_end(
    actor: str | None = typer.Option(None, "--actor", help="Whose session ended."),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """End the session, releasing the files it held."""
    params = {"actor": actor or os.environ.get(ACTOR_ENV), "intent": intent}
    result = _call("agent.end", params, flow=flow, as_json=as_json)
    _emit(result, as_json, [f"`{result['label']}` finished"])


@agent_app.command(
    "exec",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def agent_exec(
    ctx: typer.Context,
    label: str | None = typer.Option(None, "--label", help="Defaults to the command."),
    flow: str | None = _FLOW,
) -> None:
    """Wrap an agent that is itself a CLI: `agent exec -- claude`.

    This is the fallback, not the path. An agent that speaks MCP pairs itself
    by connecting to `lumlflow mcp`. It needs nothing to launch it. This verb
    is for the agents that do not speak MCP, and it stays because they exist.
    """
    command = list(ctx.args)
    if not command:
        typer.echo("name the agent to run, after `--`", err=True)
        raise typer.Exit(2)
    actor = _actor_label(label, command)
    _call("agent.begin", {"label": actor, "actor": actor}, flow=flow, as_json=False)
    try:
        code = subprocess.call(command, env={**os.environ, ACTOR_ENV: actor})
    finally:
        _call("agent.end", {"actor": actor}, flow=flow, as_json=False)
    raise typer.Exit(code)


@secrets_app.command("set")
def secrets_set(
    name: str = typer.Argument(..., help="The name a cell asks for."),
    value: str | None = typer.Option(None, "--value", help="Prompted for when absent."),
    flow: str | None = _FLOW,
    as_json: bool = _JSON,
) -> None:
    """Store a secret for this flow. Its cells read it. Nothing else does."""
    params = {"name": name, "value": value or typer.prompt(name, hide_input=True)}
    result = _call("secrets.set", params, flow=flow, as_json=as_json)
    stored = result["name"]
    _emit(
        result,
        as_json,
        [f'`{stored}` is set. a cell reaches it with ctx.secret("{stored}")'],
    )


@secrets_app.command("list")
def secrets_list(flow: str | None = _FLOW, as_json: bool = _JSON) -> None:
    """The names cells can ask for. Values are never shown."""
    result = _call("secrets.list", {}, flow=flow, as_json=as_json)
    names = result.get("names") or []
    _emit(result, as_json, [*names] if names else ["no secrets set here"])


@env_app.command("add")
def env_add(
    packages: list[str] = typer.Argument(..., help="Packages, as uv takes them."),
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Install packages into the workspace env. Every flow here shares it."""
    result = _call(
        "env.add",
        {"packages": packages, "intent": intent},
        as_json=as_json,
        scoped=False,
    )
    _emit(result, as_json, render.env)


@env_app.command("remove")
def env_remove(
    packages: list[str] = typer.Argument(..., help="Packages to drop."),
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Take packages out of the workspace env."""
    result = _call(
        "env.remove",
        {"packages": packages, "intent": intent},
        as_json=as_json,
        scoped=False,
    )
    _emit(result, as_json, render.env)


@env_app.command("status")
def env_status(as_json: bool = _JSON) -> None:
    """What the workspace pins, and any kernel still holding older packages."""
    result = _call("env.status", as_json=as_json, scoped=False)
    _emit(result, as_json, render.env)


@flow_app.command("delete")
def flow_delete(
    name: str = typer.Argument(..., help="The flow to delete, with its history."),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation."),
    as_json: bool = _JSON,
) -> None:
    """Delete a flow, with its cells, its store, and its journal."""
    if not yes:
        typer.confirm(
            f"delete `{name}` and everything it recorded?", abort=True, default=False
        )
    result = _call("flow.delete", {"flow": name}, as_json=as_json, scoped=False)
    _emit(result, as_json, [f"deleted `{result['deleted']}` ({result['path']})"])


@daemon_app.command("start")
def daemon_start(as_json: bool = _JSON) -> None:
    """Start the server for this workspace, if one is not answering."""
    result = _call("ping", as_json=as_json, scoped=False)
    _emit(result, as_json, [f"lumlflow running for {result['workspace']}"])


@daemon_app.command("status")
def daemon_status(as_json: bool = _JSON) -> None:
    """Is a server answering for this workspace?"""
    from lumlflow.flow.daemon import client, workspace

    resolved = workspace.resolve_root(Path.cwd())
    running = client.live_record(resolved) is not None
    _emit(
        {"workspace": str(resolved), "running": running},
        as_json,
        [
            f"lumlflow {'running' if running else 'not running'} for {resolved}"
            + ("" if running else ". any verb starts one")
        ],
    )


@daemon_app.command("stop")
def daemon_stop(as_json: bool = _JSON) -> None:
    """Stop this workspace's server. Nothing recorded is lost."""
    from lumlflow.flow.daemon import client, workspace

    resolved = workspace.resolve_root(Path.cwd())
    record = client.live_record(resolved)
    if record is None:
        _emit(
            {"workspace": str(resolved), "stopped": False},
            as_json,
            ["nothing running here"],
        )
        return
    try:
        # One that died between the check and the call has already done what
        # was asked; a socket that drops mid-shutdown has too. Neither is a
        # traceback the caller can act on.
        with client.attach(record) as live:
            live.call("shutdown")
    except FlowError as unreachable:
        _fail(unreachable, as_json)
    _emit({"workspace": str(resolved), "stopped": True}, as_json, ["lumlflow stopped"])


class _Daemon:
    """A connection, plus the flow this cwd addresses when nobody said."""

    def __init__(self, live: Any, root: Path, flow: str | None) -> None:
        self.live = live
        self.root = root
        self.flow = flow

    def call(
        self, method: str, params: dict[str, Any] | None = None, *, scoped: bool = True
    ) -> Any:
        payload = {
            name: value for name, value in (params or {}).items() if value is not None
        }
        if scoped and self.flow is not None:
            payload.setdefault("flow", self.flow)
        payload.setdefault("actor", os.environ.get(ACTOR_ENV) or "user")
        return self.live.call(method, payload)


@contextlib.contextmanager
def _daemon(as_json: bool, flow: str | None = None) -> Iterator[_Daemon]:
    """The daemon for this directory's workspace, started if none answers.

    Every failure the flow runtime raises lands here, where it becomes a
    sentence and an exit code rather than a traceback: an agent reading a
    Python stack to find out that a branch name was wrong is a Tier-0 failure.
    """
    from lumlflow.flow.daemon import client, workspace

    try:
        resolved = workspace.resolve_root(Path.cwd())
        here = _flow_here(resolved, flow)
        with client.connect(resolved) as live:
            yield _Daemon(live, resolved, here)
    except FlowError as failure:
        _fail(failure, as_json)


def _call(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    flow: str | None = None,
    as_json: bool = False,
    scoped: bool = True,
) -> Any:
    with _daemon(as_json, flow=flow) as daemon:
        return daemon.call(method, params, scoped=scoped)


def _emit(result: Any, as_json: bool, lines: Any) -> None:
    if as_json:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    rendered = lines(result) if callable(lines) else lines
    for line in rendered:
        typer.echo(line)


def _fail(failure: FlowError, as_json: bool) -> None:
    if as_json:
        typer.echo(
            json.dumps({"error": str(failure), "kind": type(failure).__name__}),
            err=True,
        )
    else:
        typer.echo(str(failure), err=True)
    raise typer.Exit(1)


def _flow_here(root: Path, explicit: str | None) -> str | None:
    """Which flow a verb means: the one named, else the one you are standing in.

    Left unanswered otherwise — a single-flow workspace needs no answer, and a
    workspace with several is a question the daemon asks by name.
    """
    from lumlflow.flow.daemon import workspace

    if explicit:
        return explicit
    inside = workspace.flow_here(root, Path.cwd())
    return inside.relpath if inside is not None else None


def _edited(result: dict[str, Any], *, verb: str) -> list[str]:
    written = (
        f"cells/{result['slug']}.py"
        if result.get("written_to_files")
        else "saved · not yet written to files"
    )
    return [
        f"{verb} `{result['slug']}` on `{result['branch']}` · {written}",
        *(f"  {flag['detail'] or flag['code']}" for flag in result.get("flags") or []),
    ]


def _projected(result: dict[str, Any]) -> list[str]:
    projected = result.get("projected")
    if not projected:
        return []
    written, removed = projected.get("written") or [], projected.get("removed") or []
    if not (written or removed):
        return ["files already matched"]
    parts = []
    if written:
        parts.append(f"wrote {len(written)}")
    if removed:
        parts.append(f"removed {len(removed)}")
    return [f"files: {', '.join(parts)}"]


def _actor_label(label: str | None, command: Sequence[str]) -> str:
    return label or Path(command[0]).name


def _names(cells: Sequence[dict[str, Any]]) -> str:
    return ", ".join(f"`{cell['slug']}`" for cell in cells)


def _read_export(path: Path) -> str:
    """A file the user named, read as a message rather than as a traceback."""
    try:
        return path.expanduser().read_text("utf-8")
    except (OSError, UnicodeDecodeError) as unreadable:
        raise FlowError(f"cannot read {path}: {unreadable}") from unreadable


def _shared_code_note(path: Path, root: Path) -> list[str]:
    """An export written into the workspace is watched code like any other `.py`.

    Which marks every cell unsynced, naming this file as the cause — true, and
    baffling to arrive at from a verb that only meant to write a copy out.
    """
    if path.suffix != ".py" or not path.resolve().is_relative_to(root):
        return []
    return [
        f"note: {path.name} sits in the workspace, so lumlflow watches it as "
        "shared code. write the export outside the workspace to keep the "
        "flow's cells current"
    ]


def _write_export(path: Path, source: str) -> Path:
    """Newline-fixed: an export is the same bytes wherever it was written."""
    destination = path.expanduser()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8", newline="\n")
    except OSError as unwritable:
        raise FlowError(f"cannot write {destination}: {unwritable}") from unwritable
    return destination
