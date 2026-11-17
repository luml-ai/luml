# Looking at experiments

Flow shows the experiments in an SDK store: params, metrics over steps, evals with
their scores, traces, models and attachments. Experiments from scripts, from flow
cells and from the MLflow plugin all appear here.

## In the browser

```bash
lumlflow ui                          # ~/.luml/experiments, http://127.0.0.1:5000
lumlflow ui --path ./experiments     # a project's own store
lumlflow ui --port 5050 --no-browser
```

- `--path` takes the store folder or a `sqlite://` URI. The SDK's
  `ExperimentTracker()` writes to `./experiments` unless told otherwise, so a
  project that keeps that default needs `--path ./experiments`.
- `LUML_BACKEND_STORE_URI` sets the same thing for every command.
- When Flow is already running, `lumlflow ui` opens the running one. A running
  Flow keeps its store: to open another store, run `lumlflow daemon stop`
  first.
- Flow listens on 127.0.0.1. Do not pass `--host` with a public address unless
  the user asks; anyone who reaches it can see the experiments.

## In the terminal, for example over SSH

The terminal view is for following experiments on a remote server, in an SSH
session, where no browser can reach Flow. On your own machine the browser view
is better.

```bash
lumlflow tui                         # browse the store
lumlflow tui --path ./experiments train.py --epochs 10   # run a script and follow it live
```

`lumlflow tui <script>` runs the script, finds the experiment it creates and
follows its metrics. Arguments after the script go to the script. To follow the
same job from the LUML web app instead, see [relayed.md](relayed.md).

- The terminal view needs the `tui` extra: `pip install 'lumlflow[tui]'`.
- The script runs with the Python that runs `lumlflow`. To run a script,
  install `lumlflow[tui]` in the project's environment and start it there, for
  example `uv run lumlflow tui ...`. A `uv tool` or `pipx` install does not
  have the project's packages.
- `--path` must name the store the script tracks to. The terminal view does
  not change where the script writes, and it stops waiting for the experiment
  after 60 seconds (`--attach-timeout`).

## Uploading to LUML

The experiment view can upload an experiment, or a model with its experiment embedded, to a
collection on the LUML platform. An embedded experiment goes into a copy of the model
file, so the stored model is left as it was. It needs a LUML API key, which
Flow asks for once and keeps in the system keyring, or in `~/.luml.json` when
there is no keyring. To upload from code instead, see
`python -m luml skills show luml-sdk references/upload.md`.
