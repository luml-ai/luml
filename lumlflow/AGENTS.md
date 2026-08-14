<!-- lumlflow:begin -->
# lumlflow, a lumlflow workspace

Flows here: `churn`. lumlflow generates everything below. It overwrites your edits to it.

## lumlflow quickstart

Cells are Python files under `<flow>.flow/cells/`. The filename names the cell.
A cell imports nothing. It is one class, declarations, and a `materialize`:

```python
class TrainModel:
    """What this cell is for."""
    consumes = {"train": "features.train_split"}
    produces = {"model": "asset"}

    def materialize(self, ctx, train):
        return {"model": fit(train)}
```

Drive the flow through the `lumlflow` MCP tools. Call `context` first. It names
the variant you are on, what is stale and why, and what failed. Then use
`new-cell`, `edit-cell` and `run`. Editing a cell file does the same thing as
`edit-cell`. Every change takes an `intent` saying why.

Not connected? Every tool is also a verb: `lumlflow context`, `lumlflow status`,
`lumlflow run <cell>`. Each takes `--json`, and `-m "why"` where it writes.

## Writing cells

- One class per file under `cells/`, with a `materialize(self, ctx, **inputs)`.
  Declarations are literals. lumlflow reads them by parsing the file, never by
  importing it. Nothing in a cell file runs at edit time.
- `consumes = {"name": "producer.output"}` wires inputs. A bare `"output"`
  resolves when exactly one cell on the variant produces it. lumlflow then
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
  Downstream cells and other variants hold the same value.
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
- Workspace files do not belong to a variant. Starting a variant, putting one
  on disk, and rewinding never touch them.

## Tools

Connected over MCP, this workspace serves `context` · `status` · `init-flow` ·
`new-cell` · `edit-cell` · `run` · `asset-preview` · `new-variant` ·
`use-variant` · `rewind` · `adopt` · `diff`. It reads back through
`session://focus`, `flow://<flow>/manifest`, `flow://<flow>/cells/<cell>` and
`flow://<flow>/previews/<cell>.<output>`.

Address a cell by name (`features`), an output as `cell.output`, and a variant
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
`lumlflow variant list` · `lumlflow graph` ·
`lumlflow variant new <variant>` · `lumlflow variant use <variant>` ·
`lumlflow diff <a> <b>` ·
`lumlflow adopt <cell> --from <variant>` · `lumlflow rewind <step>`

Renaming a cell is free. References bind to identity, so nothing goes stale and
no cache is lost. `mv` on the file does the same thing.

Every verb takes `--json`. Every verb that changes a cell or a variant takes
`-m "why"`, which is what the history reads back.
<!-- lumlflow:end -->
