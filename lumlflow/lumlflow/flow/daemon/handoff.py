"""Send-to-agent payloads: the context a handoff carries, built where the facts are.

Every gesture — fix this, explain this diff, summarize this branch — is a
question whose answer the store already holds, so the payload is assembled here
rather than in the surface that asked. That is what lets a *fix this* carry the
traceback of a run nobody opened the logs of, and what keeps the browser, the
CLI and MCP handing an agent the same context for the same gesture.

Addresses only. Slugs, branch names, output names and the words a verdict is
already stated in — a uid or a content hash in a prompt is an identifier the
agent would have to spell back, and nothing on the other side answers to one.
"""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from lumlflow.flow.daemon import queries
from lumlflow.flow.errors import FlowError
from lumlflow.flow.store.flowstore import CELLS_DIRNAME

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

FENCE = "lumlflow-context"

#: Budgeted like `context`: an agent that has to page through its own briefing
#: reads none of it, and every one of these lists is unbounded in principle.
_LISTED_CELLS = 20
_LISTED_INTENTS = 8
_LISTED_ROWS = 10
_BLOCK_LINES = 12

Builder = Callable[["FlowSession", str, str | None, list[str]], tuple[str, list[str]]]


def payload(
    session: "FlowSession",
    *,
    gesture: str,
    branch: str,
    slug: str | None = None,
    branches: Sequence[str] = (),
) -> dict[str, Any]:
    """One handoff: the ask in a sentence, the facts in a fenced block."""
    build = _BUILDERS.get(gesture)
    if build is None:
        raise FlowError(
            f"no handoff called `{gesture}`. the gestures are "
            f"{_listed(sorted(_BUILDERS))}"
        )
    ask, facts = build(session, branch, slug, [str(name) for name in branches])
    block = "\n".join(
        [
            f"```{FENCE}",
            f"gesture: {gesture}",
            f"flow: {session.ref.name}",
            f"lane: {branch}",
            *facts,
            "```",
        ]
    )
    return {
        "gesture": gesture,
        "flow": session.ref.name,
        "branch": branch,
        "text": f"{ask}\n\n{block}",
    }


def _fix(
    session: "FlowSession", branch: str, slug: str | None, _branches: list[str]
) -> tuple[str, list[str]]:
    """What broke, and where the reader can watch it break again."""
    named = _named(slug)
    detail = queries.show(session, branch, named)
    facts = [f"cell: {named}", *_address(session, branch, named, detail)]
    facts.append(f"state: {detail['state']}")
    facts.extend(_lines("causes", detail["causes"]))
    facts.extend(_block("traceback", detail["error"], keep="tail"))
    facts.append(f"check: lumlflow run {named}")
    return (
        f"Fix `{named}` on lane `{branch}`. The block below holds the "
        f"traceback from the run this lane observed.",
        facts,
    )


def _explain(
    session: "FlowSession", branch: str, slug: str | None, _branches: list[str]
) -> tuple[str, list[str]]:
    named = _named(slug)
    detail = queries.show(session, branch, named)
    lines = [f"cell: {named}", *_address(session, branch, named, detail)]
    lines.append(f"state: {detail['state']}")
    lines.extend(_lines("consumes", list(detail["consumes"].values())))
    lines.extend(
        _lines(
            "produces",
            [f"{name}: {kind}" for name, kind in detail["kinds"].items()],
        )
    )
    lines.extend(_block("doc", detail["doc"]))
    return (
        f"Explain what `{named}` does on lane `{branch}`. Say how it fits "
        f"the rest of the flow.",
        lines,
    )


def _diff(
    session: "FlowSession", _branch: str, _slug: str | None, branches: list[str]
) -> tuple[str, list[str]]:
    """The divergence structure in words — the same split the compare view draws.

    Definition divergence is someone having edited the cell; materialization
    divergence is the same code fed different inputs. Collapsing them into one
    list would hand the agent a wall of rows and no branching point.
    """
    compared = queries.diff(session, branches)
    lines = [f"comparing: {_listed(branches)}"]
    lines.extend(
        _lines(
            "definition-divergence",
            [
                f"{row['slug']}: edited on {_listed(_sides(row['versions']))}"
                for row in compared["definition"]
            ],
        )
    )
    lines.extend(
        _lines(
            "materialization-divergence",
            [
                f"{row['slug']}: same code, different results"
                for row in compared["materialization"]
            ],
        )
    )
    lines.extend(
        _lines(
            "absent-or-renamed",
            [
                f"{row['slug']}: " + ", ".join(_carried(row["branches"]))
                for row in compared["shapeless"]
            ],
        )
    )
    lines.extend(
        _lines("comparability", [row["message"] for row in compared["integrity"]])
    )
    return (
        f"Explain how {_listed(branches)} differ. Say which one to keep.",
        lines,
    )


def _summarize(
    session: "FlowSession", branch: str, _slug: str | None, _branches: list[str]
) -> tuple[str, list[str]]:
    """The branch's story: where it split, what is on it, what happened here.

    The ask is deliberately a note cell (decision 4): no store field holds a
    branch description, and a note is a real versioned asset that travels with
    the flow instead of a caption nothing owns.
    """
    here = queries.read(session, branch)
    ordered = here.ordered()
    facts = [queries.cell(here, uid) for uid in ordered[:_LISTED_CELLS]]
    lines = [_origin(session, here)]
    lines.append(f"cells: {len(ordered)}")
    lines.extend(_focus(session))
    lines.extend(
        _lines(
            "assets",
            [
                f"{row['slug']}: {row['state']}"
                + (f", {row['kinds'][row['primary']]}" if row["primary"] else "")
                for row in facts
                if not row["note"]
            ],
            limit=_LISTED_CELLS,
        )
    )
    lines.extend(_lines("notes", [row["slug"] for row in facts if row["note"]]))
    lines.extend(
        _lines(
            "recent",
            [
                f"{entry.intent}, by {entry.actor}"
                for entry in session.store.index.history(
                    limit=_LISTED_INTENTS,
                    branch_id=here.branch.branch_id,
                    shared=True,
                )
            ],
            limit=_LISTED_INTENTS,
        )
    )
    return (
        f"Summarize lane `{branch}`. Write the summary into this flow as a "
        f"note cell. A note cell is a class under `{CELLS_DIRNAME}/` whose "
        f"whole body is a docstring holding the markdown.",
        lines,
    )


_BUILDERS: dict[str, Builder] = {
    "fix": _fix,
    "explain": _explain,
    "diff": _diff,
    "summarize": _summarize,
}


def _named(slug: str | None) -> str:
    if not slug:
        raise FlowError("this handoff is about one cell. name it")
    return slug


def _address(
    session: "FlowSession", branch: str, slug: str, detail: dict[str, Any]
) -> list[str]:
    """Where the cell is, and which of its versions this is about.

    The file only when this branch is the one the files hold: a branch nobody
    checked out has no file to open, and naming one would send the agent to
    another branch's copy of the cell. The version is a **step**, which is what
    a rewind and the timeline take — a version id is neither.
    """
    lines = []
    if session.worktree.bound() is not None and branch == session.branch:
        lines.append(f"file: {session.ref.relpath}/{CELLS_DIRNAME}/{slug}.py")
    lines.append(f"version: accepted at step {detail['provenance']['step']}")
    return lines


def _focus(session: "FlowSession") -> list[str]:
    """What the reader is looking at, when a surface has said.

    Only the branch-wide gestures carry it: a payload about one cell already
    names the thing being looked at, and repeating it there would be a line the
    agent spends learning nothing.
    """
    focus = session.focus
    if focus is None or not focus.asset:
        return []
    return [f"focus: the reader is looking at {focus.asset}"]


def _origin(session: "FlowSession", here: queries.Slice) -> str:
    parent = here.branch.parent_branch_id
    above = session.store.index.branch_by_id(parent) if parent else None
    if above is None:
        return "started-from: nothing. this lane is a root"
    return f"started-from: {above.name} at step {here.branch.fork_step}"


def _sides(versions: list[dict[str, Any]]) -> list[str]:
    return [str(side["branch"]) for side in versions]


def _carried(branches: dict[str, str | None]) -> list[str]:
    return [
        f"{name}: {slug if slug is not None else 'absent'}"
        for name, slug in branches.items()
    ]


def _lines(label: str, rows: list[str], *, limit: int = _LISTED_ROWS) -> list[str]:
    """A labelled list, omitted when empty and honest when it was cut short."""
    if not rows:
        return []
    shown = rows[:limit]
    listed = [f"{label}:", *(f"  - {row}" for row in shown)]
    if len(rows) > len(shown):
        listed.append(f"  - … and {len(rows) - len(shown)} more")
    return listed


def _block(label: str, body: str | None, *, keep: str = "head") -> list[str]:
    """A multi-line value, capped at the end that carries it: a traceback is
    read from its last frames, prose from its first lines."""
    if not body:
        return []
    lines = body.splitlines()
    kept = lines[-_BLOCK_LINES:] if keep == "tail" else lines[:_BLOCK_LINES]
    return [f"{label}: |", *(f"  {line}" for line in kept)]


def _listed(names: Sequence[str]) -> str:
    quoted = [f"`{name}`" for name in names]
    if len(quoted) <= 1:
        return "".join(quoted)
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"
