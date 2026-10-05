### codie review of `1de9a43` on `feature/LM-653-notebooks` against `origin/main`

**Verdict: changes requested**

The branch adds a persistent flow engine with cell execution, caching, lanes, history, and agent integration. It also adds browser workbenches and CLI/MCP interfaces, alongside tracker and packaging changes.

### Correctness bugs

1. **`lumlflow/frontend/src/api/slices/workspace/workspace.api.ts:214` — Preserve the notebook editor’s original edit context.**  
   `editCell` never sends `base`, and `fetchCellSource` discards the returned `definition_hash`. Consequently, the backend’s conflict check is bypassed for every notebook save. Preserve the loaded hash and flow/lane identity through the editing session.
   
   Trigger → consequence: A user edits a cell while a paired agent updates it, then saves → the agent’s newer source is silently overwritten instead of producing an edit conflict.

2. **`lumlflow/lumlflow/flow/scheduler/queue.py:382` — Fence run completion against lane movement.**  
   Selection is checked before execution, but the result is recorded unconditionally afterward. Rewinding does not detach the pending run, so its eventual `RunRecorded` replaces the restored baseline and advances the rewound lane.
   
   Trigger → consequence: Start a long-running cell, rewind its lane to an earlier result, then let execution finish → the old request moves the lane forward again and installs a result for the version the user left.

3. **`lumlflow/lumlflow/flow/scheduler/staleness.py:170` — Account for the current environment when planning sensitive ancestors.**  
   The comparison uses the materialization’s old environment hash even when `env_sensitive=True`. Such ancestors remain `synced`, so the planner excludes them and never reaches the memo-key check that would require recomputation.
   
   Trigger → consequence: Run an environment-sensitive producer and its consumer, change the lockfile and restart the kernel, then run the consumer → the producer is skipped and the consumer can return its old cached result.

4. **`lumlflow/lumlflow_kernel/executor.py:465` — Retain unpersisted outputs long enough to feed consumers.**  
   This branch discards the value and returns `value_ref=None`, while `_load_inputs` accepts only stored references. Scheduling the producer again cannot resolve this: its next successful run returns another unreadable reference. The scheduler’s unpersisted-output tests bypass this failure through their stub executor.
   
   Trigger → consequence: Declare an output with `persist=False` and consume it downstream → the producer succeeds, but the consumer always fails with “whose value is not stored.”

5. **`lumlflow/frontend/src/components/notebooks/cell/NotebookOutput.vue:18` — Refresh mounted notebook panels when their data changes.**  
   Output loading runs only in `onBeforeMount`; `NotebookCode` and `NotebookLogs` use the same pattern. Cards remain mounted under the same slug across runs and lane switches, so updated summaries do not refresh the displayed payloads. Invalidate these panels on lane and relevant version/materialization changes.
   
   Trigger → consequence: Keep an output panel open while rerunning its cell or switching lanes → the card shows the updated lane/status with the previous result. The code panel similarly continues displaying the previous lane’s source.

6. **`lumlflow/lumlflow/flow/daemon/hub.py:407` — Exclude transient kernel files when duplicating a flow.**  
   `copytree` includes `.lumlflow/kernel/kernel.sock`. With the default Unix transport, that socket remains present until kernel teardown, and copying it raises an error. Quiescing the flow does not stop the kernel or remove the socket.
   
   Trigger → consequence: Run a flow on Linux/macOS at a path short enough for Unix sockets, then duplicate it → duplication fails and leaves a partial destination that prevents retrying the same name.

7. **`lumlflow/lumlflow/flow/daemon/api.py:864` — Resolve environment status for the requested workspace.**  
   `env_status` ignores its parameters, and `_env` uses `self.directory` for packages, interpreter selection, and kernel filtering. The per-user daemon retains its launch directory even though CLI calls supply their current directory.
   
   Trigger → consequence: Start the daemon in one project, then run `lumlflow env status` from another → it reports the first project’s environment and omits the requested project’s kernels and restart requirements.
