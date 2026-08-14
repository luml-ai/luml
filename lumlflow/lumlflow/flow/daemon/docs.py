"""The two files an agent that only reads files still learns everything from.

`AGENTS.md` at the workspace root is the DSL cheatsheet and the ~20-line
quickstart the Tier-0 contract is measured against: read `context`, edit a cell,
`run` it, and everything else is progressive disclosure. It leads with the MCP
tools because that is how an agent reaches this workspace once it has connected;
the verbs are the same operations spelled for an agent that is itself a CLI.
`.lumlflow/CHECKOUT.md` is the per-flow sidecar — which lane is on disk,
where its last checkpoint was, what is stale — so an agent that never calls
anything still knows where it is. Its filename predates the vocabulary and does
not move: a path is not something a user reads for its wording.

The workspace file is written between markers rather than wholesale: `AGENTS.md`
is where a team keeps its own instructions to agents, and a generated file that
eats them would teach everyone to delete it.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from lumlflow.flow import render
from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.daemon import queries
from lumlflow.flow.store.flowstore import store_dir

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

AGENTS_NAME = "AGENTS.md"
CHECKOUT_NAME = "CHECKOUT.md"

BEGIN_MARKER = "<!-- lumlflow:begin -->"
END_MARKER = "<!-- lumlflow:end -->"

QUICKSTART = """\
## lumlflow quickstart

Cells are Python files under `<flow>.flow/cells/`. The filename names the cell.
A cell imports nothing. It is one class, declarations, and a `materialize`:

```python
class TrainModel:
    \"\"\"What this cell is for.\"\"\"
    consumes = {"train": "features.train_split"}
    produces = {"model": "asset"}

    def materialize(self, ctx, train):
        return {"model": fit(train)}
```

Drive the flow through the `lumlflow` MCP tools. Call `context` first. It names
the lane you are on, what is stale and why, and what failed. Then use
`new-cell`, `edit-cell` and `run`. Editing a cell file does the same thing as
`edit-cell`. Every change takes an `intent` saying why.

Not connected? Every tool is also a verb: `lumlflow context`, `lumlflow status`,
`lumlflow run <cell>`. Each takes `--json`, and `-m "why"` where it writes.
"""

CHEATSHEET = """\
## Writing cells

- One class per file under `cells/`, with a `materialize(self, ctx, **inputs)`.
  Declarations are literals. lumlflow reads them by parsing the file, never by
  importing it. Nothing in a cell file runs at edit time.
- `consumes = {"name": "producer.output"}` wires inputs. A bare `"output"`
  resolves when exactly one cell on the lane produces it. lumlflow then
  rewrites it to the full spelling for you.
- `produces = {"name": "asset"}` declares outputs. The four words are `model`,
  `dataset`, `experiment` and `asset`. They say what leaves the flow, not what
  the value is. **Declare `asset` unless you mean to publish. Promote later.**
  lumlflow infers the rendered kind from the value itself.
- A class with only a docstring is a note cell. It renders as markdown.
- Always name a cell. The filename is the name everything addresses it by.
- Params live in `params = {...}`. `ctx.seed()` applies `params["seed"]`.

## Values

- Assets are immutable. Never mutate a consumed input in place. Copy it first.
  Downstream cells and other lanes hold the same value.
- Two dict shapes get rich rendering. A `metric` is a flat dict of names to
  numbers (`{"auc": 0.91}`). An `eval` is a list of same-keyed row dicts with
  at least one numeric or boolean score per row.
- `ctx.tracker` records a run through `log_param(s)` and `log_metric(s)`.
  Return `ctx.tracker.record` as an output to store it as an `experiment`.
- Cells are non-interactive. `input()` fails immediately. Take values through
  `params`, and secrets through `ctx.secret("NAME")`.
- Each run gets a scratch working directory. Return every file you want kept as
  a declared output.

## Workspace files

- Shared code such as `helpers.py` sits next to the flows. Import it normally.
  lumlflow watches it. Editing it marks every cell stale and names the file as
  the cause.
- Reach data files through `ctx.workspace_dir` and `ctx.flow_dir`. Reading them
  marks the run `external`. lumlflow never memoizes a run after that.
- Workspace files do not belong to a lane. Starting a lane, putting one
  on disk, and rewinding never touch them.

## Tools

Connected over MCP, this workspace serves `context` · `status` · `init-flow` ·
`new-cell` · `edit-cell` · `run` · `asset-preview` · `new-lane` ·
`use-lane` · `rewind` · `adopt` · `diff`. It reads back through
`session://focus`, `flow://<flow>/manifest`, `flow://<flow>/cells/<cell>` and
`flow://<flow>/previews/<cell>.<output>`.

Address a cell by name (`features`), an output as `cell.output`, and a lane
by name. Nothing else is an address. There are no ids and no hashes.

If your harness is not connected yet, the workbench hands out the configuration
under *pair an agent*. The server behind it is `lumlflow mcp --workspace <dir>`
on stdio.

## The same, as verbs

For an agent that is itself a CLI:

`lumlflow context` · `lumlflow status` · `lumlflow cells list [--stale]` ·
`lumlflow cells show <cell>` · `lumlflow cells new <cell> [--after <producer>]` ·
`lumlflow rename <cell> <new-name>` · `lumlflow cells delete <cell>` ·
`lumlflow run <cell[.output]>` · `lumlflow preflight <cell>` ·
`lumlflow asset preview <cell[.output]>` · `lumlflow promote <cell[.output]>` ·
`lumlflow lane list` · `lumlflow graph` ·
`lumlflow lane new <lane>` · `lumlflow lane use <lane>` ·
`lumlflow diff <a> <b>` ·
`lumlflow adopt <cell> --from <lane>` · `lumlflow rewind <step>`

Renaming a cell is free. References bind to identity, so nothing goes stale and
no cache is lost. `mv` on the file does the same thing.

Every verb takes `--json`. Every verb that changes a cell or a lane takes
`-m "why"`, which is what the history reads back.
"""


def refresh_workspace(root: Path, flows: list[str]) -> Path:
    """Write the workspace's `AGENTS.md`, keeping anything a human put there."""
    path = root / AGENTS_NAME
    existing = path.read_text("utf-8") if path.exists() else ""
    updated = _merge(existing, _generated(root, flows))
    if updated != existing:
        atomic_write_bytes(path, updated.encode("utf-8"))
    return path


def refresh_checkout(session: "FlowSession") -> Path:
    """Write the flow's `CHECKOUT.md` sidecar, if the state it names moved."""
    path = store_dir(session.ref.path) / CHECKOUT_NAME
    body = _checkout(session)
    existing = path.read_text("utf-8") if path.exists() else ""
    if body != existing:
        atomic_write_bytes(path, body.encode("utf-8"))
    return path


def _generated(root: Path, flows: list[str]) -> str:
    here = ", ".join(f"`{name}`" for name in sorted(flows)) or "none yet"
    return "\n".join(
        [
            f"# {root.name}, a lumlflow workspace",
            "",
            f"Flows here: {here}. lumlflow generates everything below. "
            "It overwrites your edits to it.",
            "",
            QUICKSTART.rstrip(),
            "",
            CHEATSHEET.rstrip(),
            "",
        ]
    )


def _merge(existing: str, generated: str) -> str:
    """Replace what lies between the markers, and nothing else."""
    block = f"{BEGIN_MARKER}\n{generated}{END_MARKER}\n"
    start = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        prefix = (
            existing if not existing or existing.endswith("\n") else existing + "\n"
        )
        return f"{prefix}{block}"
    return existing[:start] + block + existing[end + len(END_MARKER) :].lstrip("\n")


def _checkout(session: "FlowSession") -> str:
    """The same facts `context` opens with, read the cheap way.

    Not `queries.context`, deliberately: that brief preflights every stale cell
    to cost the pending work, and this file is rewritten after every verb.
    What the sidecar promises is where you are and what is stale.
    """
    branch = session.branch
    here = queries.read(session, branch)
    checkpoint = session.store.index.checkpoint(here.branch.branch_id)
    dirty = [uid for uid in here.ordered() if not here.verdicts[uid].synced]
    lines = [
        f"# {session.ref.name}, on disk",
        "",
        f"- lane: `{branch}`"
        + (
            ""
            if session.store.branches.bound_branch() is not None
            else " (not on disk)"
        ),
        f"- cells: {len(here.versions)}",
        "- checkpoint: "
        + (
            f"step {checkpoint.step}, {checkpoint.intent}"
            if checkpoint is not None
            else "none yet. this lane has not been whole and current"
        ),
        "",
    ]
    if not dirty:
        lines.append("Everything on this lane is current.")
    else:
        lines.append(f"## Stale ({len(dirty)})")
        lines.append("")
        lines.extend(
            f"- `{here.versions[uid].slug}`: {render.STATES[here.verdicts[uid].state]}"
            + _because(here, uid)
            for uid in dirty[: queries.LISTED_UNSYNCED]
        )
        if len(dirty) > queries.LISTED_UNSYNCED:
            lines.append(f"- … and {len(dirty) - queries.LISTED_UNSYNCED} more")
    lines += ["", "Run `lumlflow status` for the live picture.", ""]
    return "\n".join(lines)


def _because(here: queries.Slice, uid: str) -> str:
    causes = here.verdicts[uid].causes
    return f": {'; '.join(cause.detail for cause in causes)}" if causes else ""
