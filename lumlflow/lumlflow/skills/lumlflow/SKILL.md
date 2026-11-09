---
name: lumlflow
description: Look at LUML experiments in a local app, work with the user in Flow notebooks, or follow a remote job, with Flow (the lumlflow package). Use when the user wants to see experiments, metrics, evals or traces in a browser, mentions Flow, lumlflow or a .flow folder, or wants an agent to build a model step by step in a notebook.
---

# Flow

Flow is LUML's local app. Its package and command are `lumlflow`; in LUML it
is called Flow. It is optional: the SDK tracks and packages everything without
it, and experiments can always be read from code. Use Flow when it helps the user see
or steer the work.

It does three things:

- **Experiments.** A browser view of the experiments the SDK recorded: metrics,
  evals, traces, models and attachments, with comparisons. See
  [references/experiments.md](references/experiments.md).
- **Flow notebooks.** A *flow* is a notebook: a `<name>.flow` folder of cells
  that the user and agents edit and run together. Alternatives run side by
  side as lanes, and every change is versioned with who made it. See
  [references/flows.md](references/flows.md).
- **Following a remote job.** Two ways. A job on a cluster shows up live on
  the orbit's Flow page in the LUML web app, through `RelayedFlow` from the
  SDK ([references/relayed.md](references/relayed.md)). Or follow it in the
  terminal over SSH with `lumlflow tui`
  ([references/experiments.md](references/experiments.md)).

Install it with `uv tool install lumlflow` or `pipx install lumlflow`. Start it
with `lumlflow ui`.

## Which one fits

- **The user writes the code.** Keep their scripts. Track with the SDK
  (`python -m luml skills show luml-sdk`) and offer `lumlflow ui` to look at
  the results. Do not move their work into notebooks.
- **The agent writes the code, or the user directs it step by step.** Use a
  flow. Connect over MCP ([references/agents.md](references/agents.md)) and
  follow [references/flows.md](references/flows.md).
- **A long job runs where nobody can open a browser.** Wrap it in
  `RelayedFlow` to follow it from the web app, or follow it over SSH with
  `lumlflow tui`.

After you add tracking or run an experiment, offer to open the results in
Flow. Do not insist; reading them from code is as good. Experiments worth
keeping should also be uploaded to the platform, where the registry shows each
one as a snapshot, also inside the model it produced. Flow uploads from its UI
([references/experiments.md](references/experiments.md)).

## Rules

1. Flow reads `~/.luml/experiments` by default. A script that tracks to
   another store is opened with `lumlflow ui --path <store>`.
2. Inside a flow cell, use `ctx.tracker`. It is already bound to the cell's
   experiment. Do not create an `ExperimentTracker` there.
3. In a flow, call `context` (or `lumlflow context`) before you change
   anything, and address flows, cells, outputs and lanes by name.
4. Cells never ask for input. Take values through `params`.

## References

- [references/experiments.md](references/experiments.md): open experiments in the
  browser or the terminal, and upload them to the platform.
- [references/flows.md](references/flows.md): the flow guide: cells, values,
  lanes, workspace files, MCP tools and CLI verbs. `lumlflow guide` prints the
  same text.
- [references/agents.md](references/agents.md): connect a coding agent to
  Flow.
- [references/relayed.md](references/relayed.md): follow a remote job from the
  web app.
