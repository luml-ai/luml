"""The in-memory guide served to agents over MCP and the CLI."""

CHEATSHEET = """\
# lumlflow agent guide

Call `context` first. It names the lane you are on, what is stale and why, what
failed, and the last whole rewrite of `cells/`. An edit on the checked-out lane
is written to `cells/` at once; an edit on another lane stays in the flow store.
`lumlflow lane use` rewrites `cells/` for the lane it checks out. `lumlflow
rewind` and `lumlflow adopt` rewrite them at once when they target the
checked-out lane.

## Writing cells

- One class per file under `cells/`, with a `materialize(self, ctx, **inputs)`.
  Declarations are literals. lumlflow reads them by parsing the file, never by
  importing it. Nothing in a cell file runs at edit time.
- `consumes = {"name": "producer.output"}` wires inputs. A bare `"output"`
  resolves when exactly one cell on the lane produces it. lumlflow then
  rewrites it to the full spelling for you.
- `produces = {"name": "asset"}` declares outputs. The four words are `model`,
  `dataset`, `experiment` and `asset`. They classify the output; lumlflow infers
  the rendered kind from the value itself.
- A class with only a docstring is a note cell. It renders as markdown.
- Always name a cell. The filename is the name everything addresses it by.
- Params live in `params = {...}`. `ctx.seed()` applies `params["seed"]`.

## Values

- Assets are immutable. Never mutate a consumed input in place. Copy it first.
  Downstream cells and other lanes hold the same value.
- Two dict shapes get rich rendering. A `metric` is a flat dict of names to
  numbers (`{"auc": 0.91}`). An `eval` is a list of same-keyed row dicts with
  at least one numeric or boolean score per row.
- `ctx.tracker` records directly to the Experiments tracker through
  `log_param(s)` and `log_metric(s)`. Return `ctx.tracker.record` as an
  `experiment` output; it returns a reference to the tracker experiment, not
  the logged numbers.
- Cells are non-interactive. `input()` fails immediately. Take values through
  `params`.
- Each run gets a scratch working directory. Return every file you want kept as
  a declared output.

## Workspace files

- Shared code such as `helpers.py` sits next to the flows. Import it normally.
  lumlflow watches it. Editing it marks every cell stale and names the file as
  the cause.
- Reach data files through `ctx.workspace_dir` and `ctx.flow_dir`. Reading them
  marks the run `external`. lumlflow never memoizes a run after that.
- Workspace files do not belong to a lane. Starting a lane, putting one on
  disk, and rewinding never touch them.

## Tools

Connected over MCP, lumlflow serves `context` · `status` · `init-flow` ·
`new-cell` · `edit-cell` · `move-cell` · `run` · `asset-preview` ·
`new-lane` · `use-lane` · `rewind` · `checkpoint` · `adopt` · `diff`. It reads
back through `lumlflow://guide`, `flow://<path>/manifest`,
`flow://<path>/cells/<cell>` and `flow://<path>/previews/<cell>.<output>`.

Mark a step with `checkpoint` before a rewrite you may want to come back from,
or after a result worth finding again. The words sit on the step itself and
add no step. `context` reports the lane's latest one.

`rewind` moves the lane to a step and adds no step either: the lane stands
there, the later steps stay in its history, and `context` says when it is
behind its newest one. A change made from there moves the lane on from that
step. To keep the later steps reachable as they were, start a lane with
`new-lane` first — it starts from where the lane stands.

Address a flow by path, a cell by name (`features`), an output as
`cell.output`, and a lane by name. There are no ids or hashes in the agent
surface.

The Agents panel and `lumlflow agents setup` install one user-level MCP entry.
The server command is `lumlflow mcp` on stdio, with no workspace argument.

## The same, as verbs

For an agent that is itself a CLI:

`lumlflow context` · `lumlflow status [directory]` ·
`lumlflow cells list [--stale]` · `lumlflow cells show <cell>` ·
`lumlflow cells new [cell] [--after <producer>] [--anchor <cell>]
[--all-outputs]` · `lumlflow cells move <cell> (--before <cell> | --after
<cell>)` · `lumlflow rename <cell> <new-name>` ·
`lumlflow cells delete <cell>` · `lumlflow run [cell[.output]]` ·
`lumlflow preflight <cell>` · `lumlflow asset preview <cell[.output]>` ·
`lumlflow lane list` · `lumlflow graph` · `lumlflow lane new <lane>` ·
`lumlflow lane use <lane>` · `lumlflow diff <a> <b>` ·
`lumlflow adopt <cell> --from <lane>` · `lumlflow rewind <step>` ·
`lumlflow checkpoint -m "why" [--step <step>]` ·
`lumlflow agents list` · `lumlflow agents setup <harness>` ·
`lumlflow agents remove <harness>` · `lumlflow guide`

Renaming a cell is free. References bind to identity, so nothing goes stale and
no cache is lost. `mv` on the file does the same thing.

Daemon-backed verbs take `--json`. Definition and lane-history changes take
`-m "why"`, which is what the history reads back.
"""
