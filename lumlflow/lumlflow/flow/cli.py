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
the way git spells one. Lane operations live under `lumlflow lane`, and the
wire keeps its internal branch vocabulary at the daemon boundary.
"""

import contextlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Never

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
agents_app = typer.Typer(
    help="Connect installed agent harnesses to lumlflow.", no_args_is_help=True
)
env_app = typer.Typer(help="The workspace's packages.", no_args_is_help=True)
flow_app = typer.Typer(help="Manage flows in this workspace.", no_args_is_help=True)
daemon_app = typer.Typer(
    help="Inspect or stop the lumlflow daemon.", no_args_is_help=True
)

_JSON = typer.Option(False, "--json", help="Answer as JSON, verbatim.")
_FLOW = typer.Option(None, "--flow", help="Which flow, when the workspace has several.")
_LANE = typer.Option(None, "--lane", help="Which lane. Defaults to the one on disk.")
_INTENT = typer.Option(None, "-m", "--intent", help="Why. Recorded in the journal.")


def register(app: typer.Typer) -> None:
    """Mount the flow verbs on the top-level app."""
    for command in (
        init,
        status,
        context,
        doctor,
        gc,
        guide,
        graph,
        run,
        eval,
        preflight,
        cancel,
        rewind,
        checkpoint,
        adopt,
        diff,
        rename,
        export,
        mcp,
    ):
        app.command()(command)
    # `import` is a keyword, so the verb and the function that serves it cannot
    # share a name.
    app.command("import")(import_cells)
    app.add_typer(cells_app, name="cells")
    app.add_typer(asset_app, name="asset")
    app.add_typer(lane_app, name="lane")
    app.add_typer(agent_app, name="agent")
    app.add_typer(agents_app, name="agents")
    app.add_typer(env_app, name="env")
    app.add_typer(flow_app, name="flow")
    app.add_typer(daemon_app, name="daemon")


def init(
    name: str | None = typer.Argument(
        None, help="The flow's name. Defaults to this directory's."
    ),
    directory: Path | None = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Directory in which to create the flow. Defaults to the current one.",
    ),
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Scaffold a flow here and put `main` on disk."""
    with _daemon(as_json, directory=directory) as daemon:
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


def status(
    directory: Path | None = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Directory whose flows to list. Defaults to the current one.",
    ),
    flow: str | None = _FLOW,
    as_json: bool = _JSON,
) -> None:
    """The workspace, its flows, and what is stale in each."""
    requested = (directory or Path.cwd()).resolve()
    result = _call(
        "status",
        {"directory": str(requested)},
        flow=flow,
        as_json=as_json,
        scoped=flow is not None,
        directory=requested,
    )
    _emit(result, as_json, render.status)


def context(
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Where you are, what is stale and why, what broke, and what it costs."""
    params = {"branch": lane}
    result = _call("context", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.context)


def doctor(
    directory: Path | None = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Directory whose flows to inspect. Defaults to the current one.",
    ),
    as_json: bool = _JSON,
) -> None:
    """The daemon, logs, environment, stores and agent entries."""
    from lumlflow.flow.daemon import doctor as diagnostics

    try:
        result = diagnostics.report((directory or Path.cwd()).resolve())
    except (FlowError, OSError) as failure:
        _fail(
            failure if isinstance(failure, FlowError) else FlowError(str(failure)),
            as_json,
        )
    _emit(result, as_json, render.doctor)


def gc(
    directory: Path | None = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Directory whose flow stores to sweep. Defaults to the current one.",
    ),
    as_json: bool = _JSON,
) -> None:
    """Reclaim values left behind by interrupted runs."""
    requested = (directory or Path.cwd()).resolve()
    result = _call(
        "gc.sweep",
        {"directory": str(requested)},
        as_json=as_json,
        scoped=False,
        directory=requested,
    )
    _emit(result, as_json, render.gc)


def guide() -> None:
    """The cell DSL, lane rules, tools and CLI verbs for an agent."""
    from lumlflow.flow.daemon import docs

    typer.echo(docs.CHEATSHEET, nl=False)


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
    as_json: bool = _JSON,
) -> None:
    """The declared wiring. This is the graph the scheduler runs."""
    params = {"branch": lane, "around": around, "depth": depth}
    result = _call("graph", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.graph)


def run(
    target: str | None = typer.Argument(
        None, help="A cell, as `cell` or `cell.output`. Runs the lane when omitted."
    ),
    force: bool = typer.Option(
        False, "--force", help="Recompute even what is cached or already current."
    ),
    keep_daemon: bool = typer.Option(
        False,
        "--keep-daemon",
        help="Keep a daemon this run had to start.",
    ),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Run a cell, or every leaf on the lane, and whatever they need first.

    This verb takes no `-m`. A run records the runtime's own fact instead:
    `ran features`, `features failed`, or `reused a cached features`. That is
    more honest than a sentence typed before anybody knew which it would be.

    `--force` spends the closure's cost again on purpose. It drops memoization
    for this run, so the store serves nothing and every cell computes.
    """
    from lumlflow.flow.daemon import workspace

    root = Path.cwd().resolve()
    try:
        selected = workspace.select_flow(root, name=flow).address
    except FlowError as failure:
        _fail(failure, as_json)
    params = {"target": target, "branch": lane, "force": force}
    with _daemon(as_json, flow=selected) as daemon:
        result: dict[str, Any] | None = None
        lifecycle: dict[str, Any] | None = None
        try:
            result = daemon.call("run", params)
        finally:
            lifecycle = _finish_run_daemon(
                daemon,
                path=selected,
                keep=keep_daemon,
            )
        if lifecycle is not None:
            result["daemon"] = lifecycle
    assert result is not None
    _emit(result, as_json, _run_lines(result))
    if _run_failed(result):
        raise typer.Exit(1)


def eval(
    code: str = typer.Argument(..., help="Python to run against a lane's values."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Try something against a lane's values. Nothing is written.

    Cells are in scope by name. A cell's primary output takes the cell's own
    name; every output is also `cell_output`. What you get is a copy. A
    mutation here reaches no other lane, no stored value, and no cell.
    Every lane evaluates, on disk or not.
    """
    params = {"code": code, "branch": lane}
    result = _call("eval", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.evaluated)
    if result.get("error"):
        raise typer.Exit(1)


def preflight(
    target: str = typer.Argument(..., help="A cell, as `cell` or `cell.output`."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """What running it recomputes, reuses, and costs. Read this before you run."""
    params = {"target": target, "branch": lane}
    result = _call("preflight", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.preflight)


def cancel(
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Stop waiting on the run this lane asked for."""
    params = {"branch": lane}
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
            f"at step {result['parent_step']} · {result['cells']} cells, "
            "pinned as they were"
        ],
    )


@lane_app.command("use")
def lane_use(
    lane: str = typer.Argument(..., help="The lane to put on disk."),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Put a lane's cells on disk. The files rebind to its selection."""
    params = {"branch": lane, "intent": intent}
    result = _call("switch", params, flow=flow, as_json=as_json)
    _emit(result, as_json, [f"on `{result['branch']}`", *_projected(result)])


def rewind(
    to_step: int = typer.Argument(..., help="The step to restore this lane to."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Move a lane to a step. Instant, nothing recomputes, and no step is
    added: the lane stands there until the next change on it."""
    params = {
        "to_step": to_step,
        "branch": lane,
        "intent": intent,
    }
    result = _call("rewind", params, flow=flow, as_json=as_json)
    _emit(
        result,
        as_json,
        [
            f"`{result['rewound_branch']}` is back at step {result['to_step']} · "
            f"{result['cells']} cells",
            *_projected(result),
        ],
    )


def checkpoint(
    intent: str = typer.Option(
        ..., "-m", "--intent", help="What this point is. Recorded in the journal."
    ),
    step: int | None = typer.Option(
        None, "--step", help="The step to mark. Defaults to the lane's newest step."
    ),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Mark a step on a lane under a one-line intent. Nothing is copied, and
    no step is added: the words attach to the step itself."""
    params = {"branch": lane, "intent": intent, "step": step}
    result = _call("checkpoint", params, flow=flow, as_json=as_json)
    _emit(
        result,
        as_json,
        [f"marked `{result['branch']}` at step {result['step']} · {result['intent']}"],
    )


def adopt(
    slug: str = typer.Argument(..., help="The cell to take."),
    from_lane: str = typer.Option(..., "--from", help="The lane to take it from."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    intent: str | None = _INTENT,
    force: bool = typer.Option(False, "--force", help="Take the incoming side."),
    as_json: bool = _JSON,
) -> None:
    """Take one cell's version from another lane onto this one."""
    params = {
        "slug": slug,
        "from_branch": from_lane,
        "branch": lane,
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
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Rename a cell. References bind to identity, so this costs nothing."""
    params = {
        "slug": slug,
        "to": to,
        "branch": lane,
        "intent": intent,
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
    as_json: bool = _JSON,
) -> None:
    """Write a lane's cells out as one Python file.

    This exports a file, not the flow. It carries the cells as they stand and
    nothing else: no history, no results, and no other lanes. It is how a
    flow travels. The flow itself stays a directory. `lumlflow import` reads
    the file back, and each cell keeps the identity it left with.
    """
    with _daemon(as_json, flow=flow) as daemon:
        result = daemon.call("export", {"branch": lane})
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
    intent: str | None = _INTENT,
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
                "branch": lane,
                "intent": intent,
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


def mcp(
    label: str | None = typer.Option(
        None, "--label", help="What to call the session. Defaults to the client's name."
    ),
) -> None:
    """Serve lumlflow to an agent over MCP, on stdio.

    Do not run this verb by hand. An MCP client spawns it and speaks the
    protocol down its stdin. Every tool it offers goes where the verbs go. An
    agent working this way and one running verbs reach the same store.

    The server keeps its spawn directory for name resolution. Every call reaches
    the same per-user daemon, wherever another client was launched.
    """
    from lumlflow.flow.daemon import mcp as server

    # Nothing is echoed here, ever — stdout is the protocol.
    raise typer.Exit(
        server.serve(
            directory=Path.cwd().resolve(),
            label=label,
        )
    )


@cells_app.command("list")
def cells_list(
    stale: bool = typer.Option(False, "--stale", help="Only what is stale."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """What this lane holds."""
    params = {"branch": lane, "unsynced": stale}
    result = _call("cells.list", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.cells)


@cells_app.command("show")
def cells_show(
    slug: str = typer.Argument(..., help="The cell to read."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """A cell in full: state, declarations, last run, source."""
    params = {"slug": slug, "branch": lane}
    result = _call("cells.show", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.cell)


@cells_app.command("new")
def cells_new(
    slug: str | None = typer.Argument(None, help="The cell's name."),
    after: str | None = typer.Option(
        None, "--after", help="Prefill `consumes` from this cell's outputs."
    ),
    all_outputs: bool = typer.Option(
        False,
        "--all-outputs",
        help="Wire every output instead of the first non-experiment output.",
    ),
    anchor: str | None = typer.Option(
        None, "--anchor", help="Place the new cell directly after this cell."
    ),
    docstring: str | None = typer.Option(None, "--doc", help="The cell's docstring."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Scaffold a cell, wired to what it comes after."""
    params = {
        "slug": slug,
        "after": after,
        "outputs": "all" if all_outputs else None,
        "anchor": anchor,
        "docstring": docstring,
        "branch": lane,
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
        "branch": lane,
        "intent": intent,
        "force": force,
    }
    result = _call("cells.edit", params, flow=flow, as_json=as_json)
    _emit(result, as_json, _edited(result, verb="edited"))


@cells_app.command("move")
def cells_move(
    slug: str = typer.Argument(..., help="The cell to move."),
    before: str | None = typer.Option(
        None, "--before", help="Place it directly before this cell."
    ),
    after: str | None = typer.Option(
        None, "--after", help="Place it directly after this cell."
    ),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Move a cell beside another without changing its code."""
    result = _call(
        "cells.reorder",
        {"slug": slug, "before": before, "after": after, "branch": lane},
        flow=flow,
        as_json=as_json,
    )
    direction = "before" if before else "after"
    neighbour = before or after
    _emit(
        result,
        as_json,
        [f"moved `{result['slug']}` {direction} `{neighbour}` on `{result['branch']}`"],
    )


@cells_app.command("delete")
def cells_delete(
    slug: str = typer.Argument(..., help="The cell to drop from this lane."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Drop a cell from this lane. Every other lane keeps its own."""
    params = {
        "slug": slug,
        "branch": lane,
        "intent": intent,
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
    as_json: bool = _JSON,
) -> None:
    """What a cell produced, read from the stored preview. No kernel starts."""
    params = {"target": target, "branch": lane}
    result = _call("asset.preview", params, flow=flow, as_json=as_json)
    _emit(result, as_json, render.asset)


@asset_app.command("page")
def asset_page(
    target: str = typer.Argument(..., help="`cell` or `cell.output`."),
    offset: int = typer.Option(0, "--offset", help="Where to start."),
    limit: int = typer.Option(20, "--limit", help="How much to read."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    as_json: bool = _JSON,
) -> None:
    """Read into a value. This is the gesture that starts a kernel."""
    params = {
        "target": target,
        "branch": lane,
        "query": {"offset": offset, "limit": limit},
    }
    result = _call("asset.page", params, flow=flow, as_json=as_json)
    _emit(
        result, as_json, [json.dumps(result.get("page"), indent=2, ensure_ascii=False)]
    )


@asset_app.command("download")
def asset_download(
    target: str = typer.Argument(..., help="`cell` or `cell.output`."),
    to: Path | None = typer.Option(None, "--to", help="Where to write it."),
    flow: str | None = _FLOW,
    lane: str | None = _LANE,
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file."),
    as_json: bool = _JSON,
) -> None:
    """Copy a stored value out of the flow."""
    params = {
        "target": target,
        "branch": lane,
        "to": str(Path(to).resolve()) if to else str(Path.cwd()),
        "force": force,
    }
    result = _call("asset.download", params, flow=flow, as_json=as_json)
    _emit(
        result,
        as_json,
        [f"wrote {result['path']} · {result['kind']}, {result['size']} bytes"],
    )


@agent_app.command("begin")
def agent_begin(
    label: str = typer.Option(..., "--label", help="What to call this session."),
    actor: str | None = typer.Option(None, "--actor", help="Defaults to the label."),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """Register an agent session for attribution until it ends."""
    params = {"label": label, "actor": actor or label, "intent": intent}
    result = _call("agent.begin", params, flow=flow, as_json=as_json)
    _emit(result, as_json, [f"`{result['label']}` is working here"])


@agents_app.command("list")
def agents_list(as_json: bool = _JSON) -> None:
    """Detected agent harnesses and whether their MCP entry is current."""
    result = _call("agents.harnesses", as_json=as_json, scoped=False)
    _emit(result, as_json, _agent_harness_lines(result["harnesses"]))


@agents_app.command("setup")
def agents_setup(
    harness: str = typer.Argument(..., help="Harness id from `agents list`."),
    yes: bool = typer.Option(False, "--yes", help="Consent without prompting."),
    as_json: bool = _JSON,
) -> None:
    """Install or update lumlflow's user-level MCP entry."""
    with _daemon(as_json) as daemon:
        listed = daemon.call("agents.harnesses", scoped=False)
        current = _agent_harness(listed["harnesses"], harness)
        if not current["can_setup"]:
            _fail(
                FlowError(
                    f"{current['display_name']} is detect-only; paste the snippet in "
                    f"{current['config_path']}"
                ),
                as_json,
            )
        consent = yes or not current["consent_required"]
        if current["consent_required"] and not consent:
            consent = typer.confirm(str(current["consent_prompt"]), default=False)
        result = daemon.call(
            "agents.setup",
            {"harness": harness, "consent": consent},
            scoped=False,
        )
    if not consent:
        _emit(result, as_json, [f"{result['display_name']} was not set up"])
        return
    if result.get("error"):
        _fail(FlowError(str(result["error"])), as_json)
    _emit(
        result,
        as_json,
        [
            f"{result['display_name']} · {result['state']}",
            str(result["post_write_hint"]),
        ],
    )


@agents_app.command("remove")
def agents_remove(
    harness: str = typer.Argument(..., help="Harness id from `agents list`."),
    as_json: bool = _JSON,
) -> None:
    """Remove every MCP entry lumlflow owns for this harness."""
    result = _call(
        "agents.remove",
        {"harness": harness},
        as_json=as_json,
        scoped=False,
    )
    if result.get("error"):
        _fail(FlowError(str(result["error"])), as_json)
    _emit(result, as_json, [f"removed lumlflow from {result['display_name']}"])


@agent_app.command("end")
def agent_end(
    actor: str | None = typer.Option(None, "--actor", help="Whose session ended."),
    flow: str | None = _FLOW,
    intent: str | None = _INTENT,
    as_json: bool = _JSON,
) -> None:
    """End an agent attribution session."""
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
    result = _call("flow.delete", flow=name, as_json=as_json)
    _emit(result, as_json, [f"deleted `{result['deleted']}` ({result['path']})"])


@daemon_app.command("start", hidden=True)
def daemon_start(as_json: bool = _JSON) -> None:
    """Start the daemon, if one is not answering."""
    result = _call("ping", as_json=as_json, scoped=False)
    _emit(result, as_json, ["lumlflow daemon is running"])


@daemon_app.command("status")
def daemon_status(as_json: bool = _JSON) -> None:
    """Show whether the daemon is answering."""
    from lumlflow.flow.daemon import client

    try:
        record = client.discover()
    except FlowError as failure:
        _fail(failure, as_json)
    running = record is not None
    _emit(
        {
            "running": running,
            "record": record.__dict__ if record is not None else None,
        },
        as_json,
        [
            "lumlflow daemon is running"
            if running
            else "lumlflow daemon is not running. any verb starts it"
        ],
    )


@daemon_app.command("stop")
def daemon_stop(as_json: bool = _JSON) -> None:
    """Stop the daemon. Nothing recorded is lost."""
    from lumlflow.flow.daemon import client, workspace

    record = workspace.read_record()
    if record is None or not workspace.lock_held():
        if record is not None:
            workspace.clear_record(instance_id=record.instance_id)
        _emit(
            {"stopped": False},
            as_json,
            ["no daemon was running"],
        )
        return
    if not client.stop(record):
        _fail(FlowError("the lumlflow daemon did not stop"), as_json)
    _emit({"stopped": True}, as_json, ["lumlflow daemon stopped"])


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
        payload.setdefault("directory", str(self.root))
        from lumlflow.flow.daemon import harnesses

        payload.setdefault("actor", harnesses.shell_actor())
        return self.live.call(method, payload)


def _finish_run_daemon(
    daemon: _Daemon, *, path: str, keep: bool
) -> dict[str, Any] | None:
    if not bool(getattr(daemon.live, "started", False)):
        return None
    lifecycle: dict[str, Any] = {"started": True, "stopped": False}
    if keep:
        lifecycle["kept"] = True
        return lifecycle

    shutdown = daemon.call(
        "shutdown.if_idle",
        {"path": path},
        scoped=False,
    )
    lifecycle.update(shutdown)
    if not shutdown["stopping"]:
        return lifecycle

    from lumlflow.flow.daemon import client

    record = getattr(daemon.live, "record", None)
    if record is None or not client.wait_stopped(record):
        raise FlowError("the lumlflow daemon did not stop after the run")
    lifecycle["stopped"] = True
    return lifecycle


@contextlib.contextmanager
def _daemon(
    as_json: bool,
    flow: str | None = None,
    directory: Path | None = None,
) -> Iterator[_Daemon]:
    """The per-user daemon, started in this directory if none answers.

    Every failure the flow runtime raises lands here, where it becomes a
    sentence and an exit code rather than a traceback: an agent reading a
    Python stack to find out that a branch name was wrong is a Tier-0 failure.
    """
    from lumlflow.flow.daemon import client

    try:
        resolved = (directory or Path.cwd()).resolve()
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
    directory: Path | None = None,
) -> Any:
    with _daemon(as_json, flow=flow, directory=directory) as daemon:
        return daemon.call(method, params, scoped=scoped)


def _emit(result: Any, as_json: bool, lines: Any) -> None:
    if as_json:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    rendered = lines(result) if callable(lines) else lines
    for line in rendered:
        typer.echo(line)


def _run_lines(result: dict[str, Any]) -> list[str]:
    lines = render.outcome(result)
    daemon = result.get("daemon") or {}
    attached = daemon.get("attached") or {}
    if daemon.get("started") and not daemon.get("stopped") and attached:
        parts: list[str] = []
        leased = int(attached.get("leased_sessions") or 0)
        if leased:
            parts.append(f"{leased} leased agent session{'s' if leased != 1 else ''}")
        streams = int(attached.get("stream_subscribers") or 0)
        if streams:
            parts.append(f"{streams} stream subscriber{'s' if streams != 1 else ''}")
        flows = len(attached.get("open_flows") or [])
        if flows:
            parts.append(f"{flows} other open flow{'s' if flows != 1 else ''}")
        if parts:
            lines.append(f"left the daemon running · {', '.join(parts)} attached")
    return lines


def _run_failed(result: dict[str, Any]) -> bool:
    return bool(
        result.get("failed")
        or result.get("failures")
        or result.get("unplanned")
        or result.get("abandoned")
    )


def _fail(failure: FlowError, as_json: bool) -> Never:
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
        return workspace.select_flow(root, name=explicit).address
    here = root.resolve()
    containing = next(
        (
            candidate
            for candidate in (here, *here.parents)
            if candidate.name.endswith(".flow") and candidate.is_dir()
        ),
        None,
    )
    if containing is not None:
        return str(containing.resolve())
    return None


def _edited(result: dict[str, Any], *, verb: str) -> list[str]:
    written = (
        f"cells/{result['slug']}.py"
        if result.get("written_to_files")
        else "cells/ unchanged"
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


def _agent_harness(listed: Sequence[dict[str, Any]], harness_id: str) -> dict[str, Any]:
    for harness in listed:
        if harness["id"] == harness_id:
            return harness
    raise FlowError(f"agent harness `{harness_id}` is not detected on this machine")


def _agent_harness_lines(listed: Sequence[dict[str, Any]]) -> list[str]:
    if not listed:
        return ["no supported agent harnesses detected"]
    lines: list[str] = []
    for harness in listed:
        lines.extend(
            [
                f"{harness['display_name']} ({harness['id']}) · {harness['state']}",
                f"  {harness['config_path']}",
            ]
        )
        if harness.get("shell_hint"):
            lines.append(f"  {harness['shell_hint']}")
        if not harness["can_setup"]:
            lines.append("  paste this configuration:")
            lines.extend(f"    {line}" for line in harness["snippet"].splitlines())
        if harness.get("error"):
            lines.append(f"  {harness['error']}")
    return lines


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
