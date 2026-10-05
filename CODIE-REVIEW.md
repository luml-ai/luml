### codie review of `f14c154` on `OKUA1/noteboo` against `origin/main`

**Verdict: changes requested**

This branch adds persistent flows, lane history, a per-user daemon, and workspace kernels. It also adds CLI/MCP controls and notebook interfaces integrated with experiment tracking.

### Correctness bugs

1. **`lumlflow/lumlflow/flow/daemon/kernel_proc.py:702` — Kernel injection overrides workspace dependencies.** In a wheel installation, the kernel package’s parent is the daemon’s entire `site-packages` directory. Prepending it to `PYTHONPATH` makes workspace imports resolve the daemon’s dependencies before the workspace’s own versions. Expose only the kernel package to the child interpreter.

   Trigger → consequence: Run a flow in a workspace with different dependency versions from the installed tool → cells use the tool’s packages despite the workspace’s pins; native dependencies can also fail when the Python minor versions differ.

2. **`lumlflow/lumlflow/flow/daemon/api.py:527` — Adding a producer leaves existing consumers unresolved on lanes without files.** Creation accepts only the new cell, and `_edited` projects files without reaccepting consumers. Bindings are recorded during acceptance; the subsequent reconciliation only processes the checked-out lane. Rebind affected consumers when the lane’s namespace changes.

   Trigger → consequence: Through MCP, create a consumer referencing `score.result` on an unbound or off-disk lane, then create `score` → running the consumer still raises `InputUnavailable`, although its producer now exists.

3. **`lumlflow/lumlflow/flow/dsl/scaffold.py:73` — Accepted cell names generate invalid Python.** Both the creation dialog and backend accept names containing spaces or hyphens and names beginning with digits. `class_name` only removes underscores, so names such as `train-model`, `my cell`, and `2d_plot` produce syntactically invalid class declarations. Generate a valid Python identifier or reject these names before creating the cell.

   Trigger → consequence: Enter one of these permitted names in “New cell” → creation reports success but stores an unparseable scaffold whose generated `materialize` method cannot run.

4. **`lumlflow/frontend/src/store/flow/index.ts:514` — The notebook ignores changes announced exclusively through state events.** Dropping every `state` frame discards `order_changed` and `experiment_removed`. These changes do not generate journal transactions, so the notebook has no subsequent refresh to rely on. Schedule the relevant data refresh for these events.

   Trigger → consequence: Move independent cells with `lumlflow cells move` while their notebook is open → the notebook retains the old order until unrelated activity or a reload. Experiment deletion likewise leaves its displayed availability stale.

5. **`lumlflow/frontend/src/flow/workbench/live/useWorkbench.ts:77` — The Packages panel queries the wrong workspace.** The empty `env.status` request defaults to the daemon’s launch directory. The daemon supports flows from multiple directories, but this request never supplies the viewed flow’s workspace. Scope it to that workspace.

   Trigger → consequence: Start the daemon in workspace A, then open a flow from workspace B → the workbench displays A’s interpreter and package pins, and B’s current kernel drift is absent from the response.
