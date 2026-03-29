# Proposals

## Problem

luml-agent is an autonomous ML engineer that orchestrates coding agents (Claude Code, Codex) across git worktrees to implement, test, debug, and iterate on ML solutions. The basic orchestration pipeline (implement → run → debug → fork) works, but is not production-ready due to four major gaps:

### 1. Node instructions are placeholders (→ workstreams 4, 5)

The prompts injected into each node type are minimal and lack the context an agent needs to do useful ML work:

- **Implement node**: passes the user's objective verbatim with zero framing — no information about the repo structure, available data, expected output format, evaluation criteria, or how to use `luml` for tracking.
- **Debug node**: includes only the last 3,000 chars of failure logs and the original objective — no visibility into what the implement step actually changed, no structured error analysis guidance.
- **Fork node**: asks the agent to "decompose into atomic changes" with a JSON-stringified context blob — no guidance on what constitutes a good decomposition for ML iteration (e.g., hyperparameter search vs. architecture changes vs. data preprocessing).
- **Run node**: executes a shell command but has no structured way to communicate success criteria or metric thresholds back to the orchestrator.

### 2. No unified IO convention (→ workstream 0)

Agent-generated files (`result.json`, fork proposals, experiment DBs) are written to the worktree root, risking collisions with user files and scattering orchestrator artifacts across multiple locations.

### 3. No luml-sdk integration (→ workstream 2)

The agent operates in complete isolation from the LUML platform:

- Experiments are not tracked — no `ExperimentTracker` usage, no metrics logged beyond a single stdout JSON line.
- Models are not saved as artifacts — training output stays in worktrees and is never uploaded.
- No connection to LUML's organization/orbit/collection hierarchy.
- The generated `template/main.py` is a dummy that sleeps and returns a random number.

### 4. No artifact upload to LUML collections (→ workstream 3)

Users cannot connect a run to a LUML collection. When a run produces a trained model or experiment data, there's no mechanism to:

- Upload model files as artifacts to a user-selected collection.
- Link experiment tracking data to those artifacts.
- Surface results in the LUML platform UI alongside other team artifacts.

### 5. General UX and stability gaps (→ workstream 1)

- Error messages from failed nodes are often truncated or opaque.
- Multiple failure modes can cause nodes to hang indefinitely (no timeouts, PTY crash recovery gaps).
- Silent failures in fork proposal reading, worktree creation, and PTY spawn are not surfaced.
- The `best_node_id` selection is simplistic (highest single metric).

## Proposed Solution

Address these gaps in five workstreams, ordered by priority:

1. **Error handling and stability** (foundation — the pipeline must not hang or silently fail before we add features): Fix node execution timeouts, PTY crash recovery, worktree cleanup on failure, and surface errors properly through events and API.

2. **SDK integration and experiment tracking** (core data flow — agents use ExperimentTracker, experiment IDs propagate through the node graph, fork agents can inspect experiments themselves): Auto-inject `luml` dependency, define `.luml-agent/result.json` contract with experiment IDs, propagate IDs through payloads, give the fork agent the tooling to investigate experiments independently.

3. **Collection-linked uploads** (requires SDK integration — when a user selects a collection at run creation, successful run nodes auto-upload packaged models with linked experiments): Frontend-brokered auth — the agent-backend has no LUML API credentials. Instead, the frontend creates artifacts and obtains presigned upload URLs from the main LUML backend, then passes the URL to the agent-backend which performs the actual file upload. Upload queue on the agent-backend ensures robustness across frontend disconnects and multi-tab scenarios.

4. **`luml-inspect` CLI and agent guide** (agent-facing tooling — a read-only CLI for exploring experiment data with token-safe defaults, plus a `guide.md` reference file placed in `.luml-agent/` that documents CLI usage, output contracts, and conventions for any agent): Build `luml-inspect` CLI with subsampled/bucketed output, create `guide.md` template.

5. **Node instructions** (last — the prompt text can be iterated on independently once the data flow and stability are solid; testable with mock agents first): Build structured prompts for implement, debug, and fork nodes with proper context injection. Prompts reference `.luml-agent/guide.md` rather than inlining tool instructions.

---

# Design

## Dependency Order

1. **Error handling and stability** (foundation — must not hang or silently fail)
2. **SDK integration and experiment ID propagation** (core data flow)
3. **Collection-linked uploads** (requires #2)
4. **`luml-inspect` CLI + `guide.md`** (requires #2 for experiment data; testable independently with seeded experiment DBs)
5. **Node instructions / prompt construction** (requires #4 for guide.md references; can iterate independently once #1-#3 are solid)

## 0. `.luml-agent/` Directory Convention

Orchestrator IO is split across two locations:

**Per-worktree** (`{worktree}/.luml-agent/`): Files specific to a single node's execution. Written by the training code (authored by the implement agent, executed by the run node) or the fork agent.

```
{worktree}/.luml-agent/
├── guide.md             # static reference for agents (CLI usage, output contracts)
├── result.json          # training code writes run results here (during run node execution)
├── fork.json            # fork agent writes proposals here
└── proposals/           # alternative: one file per proposal
```

**Global home** (`~/.luml-agent/`): Shared resources independent of any git repo or worktree.

```
~/.luml-agent/
├── experiments/         # shared ExperimentTracker SQLite DB
│   ├── meta.db          # experiment index
│   └── {experiment_id}/ # per-experiment data
│       └── exp.db
└── uploads.db           # upload queue (persistent across frontend disconnects)
```

### Result file lifecycle

The `.luml-agent/result.json` file is written by the **training code**, not by the agent directly:

1. The **implement agent** writes training code that, when executed, outputs `.luml-agent/result.json` with experiment IDs, metrics, and model_path.
2. The **run node** executes the training command in the worktree.
3. The **run node** reads `.luml-agent/result.json` after execution completes.

The implement and debug nodes do NOT write result files — their success/failure is determined by the agent's exit code.

### `luml-inspect` availability

`luml-inspect` is an entry point in the `luml-agent` package (same package, separate script). Since `luml-agent` is installed on the host, `luml-inspect` is available on the host's PATH. The agent spawned in the PTY inherits this PATH, so `luml-inspect` is available without any injection into the worktree's venv — it's a host-level tool like `git` or `uv`.

```toml
# luml-agent/pyproject.toml
[project.scripts]
luml-agent = "luml_agent.server:main"
mock-agent = "luml_agent.mock_agent:main"
luml-inspect = "luml_agent.cli.inspect:main"
```

### Directory creation

- **Per-worktree:** Each node handler ensures `.luml-agent/` exists before spawning the agent: `Path(worktree_path) / ".luml-agent").mkdir(exist_ok=True)`. The `guide.md` template is copied here at the same time.
- **Global home:** The engine ensures `~/.luml-agent/experiments/` exists at startup: `Path.home() / ".luml-agent" / "experiments").mkdir(parents=True, exist_ok=True)`.

### `.gitignore`

A single `.luml-agent/` entry is added to the worktree's `.gitignore`. No repo-root `.gitignore` changes needed (the global home is outside the repo).

**Files:** `fork.py`, `implement.py`, `debug.py`, `run_node.py` — ensure per-worktree dir exists + copy `guide.md`. `engine.py` — ensure global home dirs at startup. `worktree.py` — add `.luml-agent/` to `.gitignore` on worktree creation.

## 1. Error Handling and Stability

### 1.1 Node Execution Timeouts

**Problem:** All four node handlers call `exit_event.wait()` with no timeout. If a PTY session dies without notifying, the node hangs forever.

**Fix:** Per-node-type timeouts in `RunConfig`:

```python
@dataclass
class RunConfig:
    # ... existing fields ...
    implement_timeout: int = 1800   # 30 min — agent coding session
    run_timeout: int = 0            # 0 = no timeout — training/grid search can take hours
    debug_timeout: int = 1800       # 30 min — similar to implement
    fork_timeout: int = 900         # 15 min — decomposition is lighter
```

Each node handler reads its own timeout from `ctx.run_config` and calls `exit_event.wait(timeout=...)`. A value of `0` means no timeout (for run nodes where training duration is unpredictable).

On timeout:
- Mark node as FAILED with `error_message = "Node execution timed out after {timeout}s"`.
- Terminate the PTY session if still alive.
- Emit `node_completed` event with timeout error.

Frontend: expose these in WorkflowForm.vue advanced options so users can override per run.

**Files:** `implement.py`, `run_node.py`, `debug.py`, `fork.py` — each `exit_event.wait()` call. `models.py` — add fields to `RunConfig`. `schemas/run.py` — add to `RunCreateIn`.

### 1.2 PTY Crash Recovery

**Problem:** If a PTY process crashes between death and `notify_session_exit()`, the node waits forever. The reader thread can crash silently.

**Fix:**
- In `pty_manager.py` `cleanup_dead()`: after detecting a dead process, always call `notify_session_exit()` with the process return code. Currently `cleanup_dead()` calls `terminate()` but doesn't guarantee notification.
- Add a safety net in the reader thread: on any unhandled exception, log it AND call `notify_session_exit()` with exit code -1.
- In `terminate()`: wrap `proc.wait(timeout=2)` after SIGKILL in try/except for `TimeoutExpired` — force-close the FD and notify anyway.

**Files:** `pty_manager.py` — `cleanup_dead()`, `_reader_thread()`, `terminate()`.

### 1.3 Worktree Cleanup on Failure

**Problem:** If worktree creation partially succeeds (directory created, git command fails) or if `preserve_env_files()` raises, the worktree directory is left behind.

**Fix:** Wrap `create_worktree()` body in try/except. On failure, attempt cleanup of the partially created worktree directory and re-raise. Similarly, wrap `preserve_env_files()` — if env file copy fails, log a warning but don't fail the worktree creation.

**Files:** `worktree.py` — `create_worktree()`, `preserve_env_files()`.

### 1.4 Node Handler Exception Logging

**Problem:** When a node handler raises, `engine.py` catches it and converts to `NodeResult(success=False)` but only logs the node_id — not the stack trace.

**Fix:** Log the full exception with `logger.exception()` instead of `logger.error()`.

**Files:** `engine.py` — the `except Exception` block in `_run_node()`.

### 1.5 Fork Node Robustness

**Problem:** Fork node has multiple fallback paths for reading proposals (`.luml-agent/fork.json`, `.luml-agent/result.json`, `.luml-agent/proposals/` dir) but file I/O errors are not caught. Directory creation and `.gitignore` updates are unwrapped.

**Fix:** Wrap file operations in try/except. If proposal reading fails entirely, return `NodeResult(success=False, error_message="Failed to read fork proposals: {err}")`.

**Files:** `fork.py` — the proposal reading section and directory setup.

### 1.6 PTY Spawn Error Handling

**Problem:** `pty.spawn()` in node handlers is not wrapped in try/except. `pty_manager.py` `spawn()` itself doesn't catch `OSError` from `pty.openpty()` or `Popen()`.

**Fix:**
- In `pty_manager.py` `spawn()`: wrap `openpty()` and `Popen()` in try/except, clean up FDs on failure, raise a clear error.
- In each node handler: the existing engine-level `except Exception` covers this, but add specific error messages (e.g., "Failed to spawn agent session").

**Files:** `pty_manager.py` — `spawn()`.

### 1.7 Scheduler Resilience

**Problem:** `_schedule_tick()` exceptions are caught and logged but the scheduler continues silently with potentially corrupt state.

**Fix:** Distinguish recoverable errors (single node failure) from unrecoverable ones (DB connection lost). For recoverable: log and continue (current behavior). For unrecoverable: mark all running runs as FAILED and stop the scheduler, emitting `run_status_changed` events.

**Files:** `engine.py` — `_scheduler_loop()`, `_schedule_tick()`.

### 1.8 Worktree Lifecycle Management

The current worktree handling has several gaps: worktrees are never cleaned up (they accumulate forever), large data files are fully copied into each worktree, new worktrees don't carry over uncommitted work, and merge conflict resolution is not supported in the UI.

#### 1.8.1 Worktree Cleanup

**Problem:** Worktrees persist on disk after merge, run completion, run deletion, and run cancellation. Only task deletion cleans up worktrees. Over time, worktrees accumulate and consume disk space (each is a full checkout).

**Fix:** Add cleanup at three points:

1. **After merge** (`handlers/run.py` `merge()`): After successful merge of the best node's branch, remove all worktrees belonging to that run. Iterate all run nodes, call `remove_worktree()` for each that has a `worktree_path`. This is safe because merge already incorporated the changes.

2. **On run deletion** (`handlers/run.py` `delete()`): Before deleting DB records, iterate all run nodes and remove their worktrees.

3. **On run cancellation** (`handlers/run.py` `cancel()`): After all nodes are canceled and sessions terminated, clean up worktrees. The user explicitly chose to discard this work.

Cleanup errors are logged but do not fail the parent operation (merge/delete/cancel).

**Upload-aware cleanup:** Before removing worktrees, check the upload queue (`~/.luml-agent/uploads.db`) for PENDING or IN_PROGRESS uploads referencing any of the run's nodes. If pending uploads exist:
- **Defer** worktree cleanup for those nodes' worktrees (the model file must remain on disk until the upload completes).
- Emit `worktrees_pending_upload` event via WebSocket so the frontend can display the status (e.g., "Worktrees will be cleaned up after uploads complete").
- The `upload_completed` / `upload_failed` handler checks if all uploads for the run are resolved and triggers deferred cleanup.
- On run **deletion**: cancel any PENDING uploads (the user explicitly wants everything gone), then clean up immediately.
- On run **cancellation**: same as deletion — cancel pending uploads, clean up.

**Files:** `handlers/run.py` — `merge()`, `delete()`, `cancel()`. `worktree.py` — `remove_worktree()` already exists. `upload_queue.py` — `get_pending(run_id)`, `cancel_pending(run_id)`.

#### 1.8.2 Shared Data via Symlinks

**Problem:** `git worktree add` creates a full checkout. If the repo contains large data directories (datasets, model checkpoints), each worktree gets its own copy, wasting disk space and slowing creation.

**Fix:** Introduce a `shared_paths` pattern. Certain paths are symlinked to the main repo instead of being copied/checked out.

Config addition:
```python
@dataclass
class AppConfig:
    # ... existing fields ...
    shared_paths: list[str] = field(default_factory=lambda: ["data"])
```

After `create_worktree()` completes the `git worktree add`:
1. For each path in `shared_paths`:
   - If the path exists in the main repository, remove it from the worktree (if checked out).
   - Create a symlink: `{worktree_path}/{path}` → `{repo_path}/{path}`.
2. Add shared paths to the worktree's `.gitignore` (so agents don't accidentally commit symlinks).

This is opt-in via config. The default `["data"]` covers the common convention. Users can add more paths (e.g., `["data", "checkpoints", "models"]`).

**Files:** `worktree.py` — new `_setup_shared_paths()` helper called after `create_worktree()`. `config.py` — new field.

#### 1.8.3 Uncommitted Changes and New Worktrees

**Problem:** `git worktree add` creates a clean checkout of the branch. If the parent worktree has uncommitted changes (e.g., from a previous implement node that didn't commit everything), child worktrees don't see them.

**Current behavior:** This is actually correct for the implement → run → fork → implement flow because:
- The implement node's agent should commit its work.
- The run node uses the parent's worktree directly (no new worktree).
- Fork-child implement nodes create new worktrees branched from the parent's branch — they see all committed changes.

The gap is when an agent leaves uncommitted changes. The implement node handler should ensure changes are committed before marking the node as succeeded.

**Fix:** After the agent exits in `implement.py` (and `debug.py`), before returning `NodeResult`:
1. Check for uncommitted changes in the worktree: `git status --porcelain`.
2. If uncommitted changes exist, auto-commit them: `git add -A && git commit -m "luml-agent: auto-commit uncommitted changes"`.
3. This ensures fork-child worktrees (branched from this branch) see all work.

**Files:** `implement.py`, `debug.py` — after agent exits, before result parsing. New helper `_auto_commit_changes(worktree_path: str) -> None` in `worktree.py`.

#### 1.8.4 Preserve Patterns for Non-Git Files

**Current state:** `preserve_patterns` copies `.env*` files from main repo to worktrees. `exclude_patterns` is defined in config but never used.

**Fix:** Keep `preserve_patterns` for env files (working correctly). Repurpose `exclude_patterns` — these are not needed since `git worktree add` already handles `.gitignore`. Remove the unused `exclude_patterns` from config to avoid confusion.

**Files:** `config.py` — remove `exclude_patterns`.

#### 1.8.5 Merge Conflict Handling

**Problem:** If `git merge` fails with conflicts, the current code calls `git merge --abort` and raises `RuntimeError`. The frontend (MergeDialog.vue) shows a generic error but has no conflict resolution UI.

**Fix (two parts):**

1. **Backend — detect and report conflicts:** In `merge.py`, when merge fails, check if it's a conflict (vs. other errors). If conflicts, parse `git diff --name-only --diff-filter=U` to get conflicting file paths. Return them in the error response as structured data:
   ```python
   class MergeConflictError(ApplicationError):
       def __init__(self, conflicting_files: list[str]):
           super().__init__("Merge conflicts detected", status_code=409)
           self.conflicting_files = conflicting_files
   ```

2. **Frontend — display conflicts clearly:** In MergeDialog.vue, if the error response has status 409 and `conflicting_files`, display the list of conflicting files. For now, the user must resolve conflicts manually (the worktree path is shown in the UI). A full in-browser conflict editor is out of scope for this spec.

**Files:** `merge.py` — detect conflicts, return structured error. `infra/exceptions.py` — new `MergeConflictError`. Frontend: `MergeDialog.vue` — display conflict file list.

## 2. SDK Integration and Experiment ID Propagation

### 2.1 Result File Contract

Extend the `.luml-agent/result.json` schema to include experiment tracking data:

```json
{
  "success": true,
  "experiment_id": "single-id",
  "experiment_ids": ["id1", "id2"],
  "metrics": {"accuracy": 0.92, "f1_score": 0.88},
  "artifacts": {"model_path": "model.luml"},
  "error_message": ""
}
```

- `experiment_id` (string) — for single-experiment runs.
- `experiment_ids` (list of strings) — for multi-experiment runs (grid search).
- The run node normalizes both forms to `artifacts["experiment_ids"]: list[str]`.
- `metrics` is a dict of named metrics (replaces the single `metric` float).
- Backward compat: if only `metric` (float) is present, treat it as `{"metric": value}`.

**Files:** `result_file.py` — `read_result_file()` updated to read from `.luml-agent/result.json`. `run_node.py` — store normalized experiment IDs and metrics dict in artifacts.

### 2.2 Global Experiment Database

All experiments across all runs and nodes are stored in a single global location: `~/.luml-agent/experiments/`.

**Why global home:** ExperimentTracker uses per-experiment isolation (each experiment gets its own `{experiment_id}/exp.db` file, with a shared `meta.db` index). Concurrent agents writing to different experiments don't contend. The only shared write target is `meta.db` on experiment creation, which WAL mode handles well for the expected concurrency (a handful of parallel agents).

Using `~/.luml-agent/` (independent of any git repo) means:
- Training code in any worktree writes to the same place without needing to know the repo root.
- No git worktree path detection issues — `~` is always `~`.
- Fork agents read parent experiments without path propagation.
- Experiment data survives worktree cleanup.
- `luml-inspect` defaults to this location — no flags needed.

**Connection string convention:** `sqlite://~/.luml-agent/experiments` — the `guide.md` documents this. Training code uses `ExperimentTracker("sqlite://~/.luml-agent/experiments")` or the SDK can be updated to use this as the default when `LUML_EXPERIMENTS_PATH` is not set.

**Cleanup:** On run deletion, the engine iterates all experiment IDs associated with that run's nodes and deletes them from the tracker. The global DB directory itself is not removed (other runs may share it).

### 2.3 Experiment ID Propagation Through Node Graph

The experiment IDs must flow through the node graph so downstream nodes (especially fork) can access them.

**Flow:**
1. **Implement node** → agent writes `experiment_id`/`experiment_ids` in `.luml-agent/result.json`.
2. **Run node** → reads result file, normalizes to `artifacts["experiment_ids"]` and `artifacts["metrics"]`.
3. **Engine `_process_result()`** → when spawning fork node, passes `experiment_ids` in the fork payload (alongside existing `objective` and `context`).
4. **Fork node** → receives experiment IDs in payload. The fork **agent** (not the orchestrator) is responsible for investigating experiments — it opens the global experiment DB and uses `ExperimentTracker` to read the data. The orchestrator does NOT pre-parse and summarize experiments for the fork prompt.
5. **Child implement nodes** → receive fork proposals as their primary instruction (via `payload["prompt"]`), plus the original objective as context, plus parent experiment IDs. They create new experiments with new IDs.

**Key design decision:** The fork agent investigates experiments itself. The orchestrator's job is only to propagate IDs. This keeps the orchestrator simple and lets the agent use its judgment about what to look at.

### 2.4 Fork Payload Enhancement

**Fork node payload** (from engine to fork node):

Current: `{"objective": str, "context": str}`.

New:
```python
{
    "objective": str,           # original user objective
    "context": str,             # existing: JSON-stringified run artifacts
    "experiment_ids": list[str],
    "discovered_metric_keys": list[str],  # metric names from parent run node
}
```

The fork node handler passes `experiment_ids` to the agent via the prompt. The agent opens the global experiment DB itself (`ExperimentTracker("sqlite://~/.luml-agent/experiments")`).

**Fork-child implement payload** (from fork node to child implement nodes):

Current: `{"prompt": str}` (just the proposal text).

New:
```python
{
    "prompt": str,              # fork proposal prompt — the PRIMARY instruction
    "objective": str,           # original user objective — background context only
    "experiment_ids": list[str],
    "discovered_metric_keys": list[str],
}
```

The fork node handler copies `objective`, `experiment_ids`, and `discovered_metric_keys` from its own payload into each child's payload (alongside the proposal `prompt`). The implement prompt builder uses the presence of `prompt` + `objective` together to distinguish fork-child from root.

**Files:** `engine.py` — `_process_result()` fork payload construction. `fork.py` — child payload construction (line 113). `implement.py` / `prompts.py` — detect root vs. fork-child.

### 2.5 Auto-Dependency Injection

Before spawning the agent in the implement node, ensure `luml` is available:

1. Check if `pyproject.toml` exists in the worktree.
2. If yes, check if `luml` is in `[project.dependencies]` or `[tool.uv.dependencies]`.
3. If not, run `uv add luml` in the worktree via subprocess.
4. If any step fails (no pyproject.toml, uv not available, network error), log a warning and continue — the agent can add the dependency itself.

Helper: `_ensure_luml_dependency(worktree_path: str) -> None` in a new shared utility or in `implement.py`.

**Files:** `implement.py` — call before `pty.spawn()`.

### 2.6 Run Node: Enhanced Metric Extraction

The run node currently parses a single `metric` from stdout. Enhance to:

1. After execution, read `.luml-agent/result.json` for `experiment_id`/`experiment_ids` and `metrics` dict.
2. Normalize experiment IDs to a list. Normalize metrics to a dict.
3. Fall back to stdout parsing (`parse_stdout_metric()`) for backward compatibility.
4. Store in artifacts: `experiment_ids` (list), `metrics` (dict), `metric` (float, primary — for backward compat with `_compute_best_node()`).

**Files:** `run_node.py` — after execution, before returning NodeResult.

### 2.7 Metric Consistency Across Nodes

The metric definition, name, and calculation must remain consistent across ALL run nodes in a single run. Otherwise experiments are not comparable.

**Enforcement:**
- The fork agent has access to parent experiment data and can see which metrics were used.
- The fork prompt instructs the agent to preserve the same metric name and calculation in its proposals.
- The engine records `discovered_metric_keys: list[str]` on the Run DB model after the first successful run node (for frontend display purposes).
- Child implement prompts include a "Metric Consistency" section with the metric name(s) from the parent.

**Files:** `models/run.py` — new field on RunOrm. `engine.py` — set on first successful run node. Migration needed.

### 2.8 Best Node Selection

`_compute_best_node()` compares nodes, not individual experiments within a node:

- Iterates all successful RUN nodes.
- For each node, reads `artifacts["metrics"][primary_metric]`.
- The best is the node with the highest (or lowest, per `metric_direction`) primary metric.
- Store `best_node_id` on the Run.

For grid search nodes (multiple `experiment_ids`), the **training script** is responsible for picking the best experiment and reporting its metrics in `.luml-agent/result.json`. The engine treats each node as a single result. The full `experiment_ids` list is preserved in artifacts for traceability — the fork agent can use `luml-inspect` to dig into per-experiment data.

**Config:**
- `primary_metric: str = "metric"` — the metric key used for comparison.
- `metric_direction: str = "max"` — `"max"` (higher is better, e.g., accuracy) or `"min"` (lower is better, e.g., loss).

**Files:** `engine.py` — `_compute_best_node()`. `models.py` — add `primary_metric` and `metric_direction` to RunConfig.

## 3. Collection-Linked Uploads

### 3.1 Architecture Overview

The agent-backend has no direct auth with the LUML platform. Instead, the frontend acts as an auth broker: it creates artifacts, obtains presigned upload URLs, and confirms uploads — while the agent-backend performs the actual file transfer.

**Flow:**
1. **Run creation**: User picks a collection in the frontend (queried from main LUML backend via existing auth session). Collection IDs are stored on the run config.
2. **Artifact ready**: Agent-backend detects a successful RUN node with `model_path`. It links the experiment to the model locally (via ExperimentTracker), then emits an `upload_ready` event to the frontend via the existing WebSocket event stream.
3. **Presigned URL**: Frontend receives the event, calls the main LUML backend to create an artifact record and obtain a presigned upload URL.
4. **Upload**: Frontend sends the presigned URL back to the agent-backend via a REST endpoint. Agent-backend uploads the file to the presigned URL.
5. **Confirmation**: Frontend confirms the upload to the main LUML backend (marks artifact as uploaded).

**Key principle:** Upload failures never block the pipeline. The engine continues to fork/next nodes regardless of upload status.

### 3.2 Schema Changes

**Backend — RunCreateIn** (`schemas/run.py`):
```python
class RunCreateIn(BaseModel):
    # ... existing fields ...
    luml_collection_id: str | None = None
    luml_organization_id: str | None = None
    luml_orbit_id: str | None = None
```

**Backend — RunConfig** (`models.py`):
```python
@dataclass
class RunConfig:
    # ... existing fields ...
    luml_collection_id: str | None = None
    luml_organization_id: str | None = None
    luml_orbit_id: str | None = None
```

**Frontend — WorkflowForm.vue**: Add optional collection selector in the advanced options section. Fetches the user's collections from the main LUML backend (via the existing collection service). Only shown if the user is authenticated.

**Frontend — data-agent.interfaces.ts**: Add `luml_collection_id`, `luml_organization_id`, `luml_orbit_id` to `RunConfig` interface.

**Frontend — API client** (`data-agent/index.ts`): Pass new fields in `createRun()`.

### 3.3 Upload Queue (Agent-Backend)

New module: `src/luml_agent/services/upload_queue.py`

The agent-backend maintains a persistent upload queue in `~/.luml-agent/uploads.db`. This ensures uploads survive frontend disconnects, server restarts, and are not duplicated across multiple browser tabs.

```python
@dataclass
class PendingUpload:
    id: str                     # unique upload ID (uuid)
    run_id: str
    node_id: str
    model_path: str             # absolute path to the artifact file
    experiment_ids: list[str]
    file_size: int
    status: UploadStatus        # pending | in_progress | completed | failed
    error: str | None = None
    retry_count: int = 0            # incremented on each failure, max 3
    created_at: datetime
    updated_at: datetime

class UploadStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
```

**Queue operations:**
- `enqueue(run_id, node_id, model_path, experiment_ids) -> PendingUpload` — creates a new entry with status=PENDING.
- `claim(upload_id) -> bool` — atomically transitions PENDING → IN_PROGRESS. Returns False if already claimed (prevents duplicate uploads from multiple tabs).
- `complete(upload_id)` — marks as COMPLETED.
- `fail(upload_id, error)` — marks as FAILED.
- `get_pending(run_id) -> list[PendingUpload]` — returns all PENDING uploads for a run (used on frontend reconnect).
- `cleanup_resolved()` — deletes COMPLETED and FAILED entries older than 24 hours. Called periodically by the engine (e.g., on startup and every hour).

### 3.4 Experiment Linking (Pre-Upload)

Before enqueuing the upload, the engine links the experiment to the model locally:

1. Open experiment tracker: `ExperimentTracker("sqlite://~/.luml-agent/experiments")`.
2. If multiple experiment IDs: read all, pick best by `primary_metric`.
3. Link experiment to model: `tracker.link_to_model(model_ref)` — this embeds experiment data into the model artifact.
4. The resulting file (at `model_path`) is the upload payload — it contains both the model and the linked experiment.

This happens synchronously in `_process_result()` before the upload is enqueued. If linking fails, the upload is not enqueued and the error is logged.

### 3.5 WebSocket Event: `upload_ready`

Emitted by the agent-backend when a new upload is enqueued. Sent over the existing WebSocket event stream (same channel as `node_completed`, `run_status_changed`, etc.).

```python
{
    "type": "upload_ready",
    "upload_id": str,
    "run_id": str,
    "node_id": str,
    "file_size": int,
    "experiment_ids": list[str],
    "collection_id": str,
    "organization_id": str,
    "orbit_id": str,
}
```

**On frontend reconnect:** The frontend calls a REST endpoint to get pending uploads for active runs. For each pending upload, the frontend resumes the presigned URL flow. This handles the case where the user closed the tab and reopened it later.

### 3.6 REST Endpoint: Upload URL Callback

New endpoint on the agent-backend:

```
POST /api/runs/{run_id}/uploads/{upload_id}/url
Body: {"presigned_url": str}
```

**Behavior:**
1. Call `claim(upload_id)`. If returns False (already claimed), respond 409 Conflict. This prevents multiple tabs from uploading the same artifact.
2. Start the file upload to the presigned URL in a background task (not blocking the response).
3. Respond 202 Accepted.
4. On upload success: `complete(upload_id)`, emit `upload_completed` event via WebSocket.
5. On upload failure: `fail(upload_id, error)`, emit `upload_failed` event via WebSocket.

### 3.7 REST Endpoint: Pending Uploads

```
GET /api/runs/{run_id}/uploads?status=pending
Response: [PendingUpload, ...]
```

Used by the frontend on reconnect to discover uploads that need presigned URLs.

### 3.8 Frontend Upload Flow

**On `upload_ready` WebSocket event:**
1. Call main LUML backend: create artifact record, get presigned upload URL.
2. POST the presigned URL to agent-backend: `POST /api/runs/{run_id}/uploads/{upload_id}/url`.
3. If 409 (already claimed by another tab): ignore — another tab is handling it.
4. Wait for `upload_completed` or `upload_failed` event.
5. On `upload_completed`: confirm upload to main LUML backend (finalize artifact).
6. On `upload_failed`: show error in UI, optionally allow retry.

**On page load / reconnect:**
1. For each active run with `luml_collection_id`, call `GET /api/runs/{run_id}/uploads?status=pending`.
2. For each pending upload, resume from step 1 above.

**Multi-tab deduplication:** The `claim()` mechanism ensures only one tab performs the upload. Other tabs receive a 409 and can show "Upload in progress from another session" or simply ignore the event.

### 3.9 Integration Point in Engine

In `engine.py` `_process_result()`, after existing RUN success handling:

```python
if node.node_type == NodeType.RUN and result.success:
    config = self._get_run_config(run_id)
    if config.luml_collection_id:
        experiment_ids = result.artifacts.get("experiment_ids", [])
        model_path = result.artifacts.get("model_path")
        if experiment_ids and model_path:
            # 1. Link experiment to model (local, synchronous)
            _link_experiment_to_model(repo_path, experiment_ids, model_path, config.primary_metric)
            # 2. Enqueue upload (non-blocking)
            upload = upload_queue.enqueue(run_id, node_id, model_path, experiment_ids)
            # 3. Emit event to frontend
            emit("upload_ready", {...})
    # Pipeline continues immediately — upload is async
```

Upload never blocks the pipeline. The engine continues to fork spawning regardless.

## 4. `luml-inspect` CLI

### 4.1 Overview

A read-only CLI for agents to explore experiment data. Lives in `luml-agent/` (`src/luml_agent/cli/inspect.py`). Entry point: `luml-inspect` (registered in `pyproject.toml` `[project.scripts]`).

**Design principles:**
- Token-efficient output — compact tables, no JSON, no decorative formatting.
- Safe by default — subsampling is always on unless explicitly overridden with `--all`. This prevents an agent from accidentally dumping 50k metric rows into its context.
- Read-only — writes go through ExperimentTracker Python API.

All commands take `--db <path>` to override the experiment DB location. Default: `~/.luml-agent/experiments`.

### 4.2 Commands

#### `luml-inspect list`

List experiments. Default cap: 20 rows.

```
$ luml-inspect list
ID         NAME           STATUS     CREATED     TAGS         METRICS(final)
abc-123    baseline-lr    completed  2026-03-28  [gbt,v1]     accuracy=0.92 loss=0.08
def-456    high-lr        completed  2026-03-28  [gbt,v1]     accuracy=0.88 loss=0.12
(2 of 2 experiments)
```

Flags: `--all` (no cap), `--limit N`, `--group <name>`, `--tag <tag>`.

#### `luml-inspect show <id>`

Full experiment details: metadata, static params, and per-metric summary.

```
$ luml-inspect show abc-123
EXPERIMENT abc-123 "baseline-lr" (completed)
Created: 2026-03-28  Group: default  Tags: gbt, v1

PARAMS
  learning_rate    0.01
  batch_size       32
  model_type       gradient_boosting

METRICS SUMMARY
  KEY        STEPS  FINAL   MIN     MAX     MEAN
  accuracy   500    0.92    0.41    0.92    0.78
  loss       500    0.08    0.08    1.24    0.31
```

#### `luml-inspect metrics <id> <key>`

Time-series for one metric. Default: subsample to ~20 rows. Each row covers a bucket of steps and shows the sampled value plus the min/max within that bucket.

```
$ luml-inspect metrics abc-123 accuracy
accuracy (500 steps, showing 20 buckets)
  STEP     VALUE   MIN     MAX
  1        0.41    0.41    0.53
  25       0.58    0.52    0.61
  50       0.64    0.60    0.67
  ...
  500      0.92    0.91    0.92
```

When subsampled, `STEP` is the representative step for the bucket (e.g., the midpoint or last step). `MIN`/`MAX` are the range across all steps in that bucket. This lets the agent see both the trend and the variance within each bucket.

Flags:
- `--all` — show every step (no subsampling, no bucketing)
- `--last N` — last N data points (raw, no bucketing)
- `--every N` — every Nth step (raw, no bucketing)
- `--summary` — only the summary line (final/min/max/mean), no rows
- `--buckets N` — override default bucket count (default: 20)

#### `luml-inspect compare <id1> <id2> [...]`

Side-by-side metric comparison. Same bucketing as `metrics` — applied per metric key across all experiments.

```
$ luml-inspect compare abc-123 def-456
PARAMS DIFF
  KEY              abc-123    def-456
  learning_rate    0.01       0.1
  batch_size       32         32       (same)

METRIC: accuracy (500 steps, 20 buckets)
  STEP    abc-123         def-456
          VAL  MIN  MAX   VAL  MIN  MAX
  1       0.41 0.41 0.53  0.39 0.39 0.51
  25      0.58 0.52 0.61  0.55 0.50 0.58
  ...
  500     0.92 0.91 0.92  0.88 0.87 0.88

METRIC: loss (500 steps, 20 buckets)
  STEP    abc-123         def-456
          VAL  MIN  MAX   VAL  MIN  MAX
  1       1.24 1.10 1.24  1.30 1.15 1.30
  ...
  500     0.08 0.08 0.09  0.12 0.11 0.13
```

Same flags as `metrics`: `--all`, `--last N`, `--every N`, `--summary`, `--buckets N`.

#### `luml-inspect params <id>`

Static params dump (compact).

```
$ luml-inspect params abc-123
learning_rate    0.01
batch_size       32
model_type       gradient_boosting
```

#### `luml-inspect evals <id>`

Eval samples. Default cap: 10 rows.

```
$ luml-inspect evals abc-123
DATASET    EVAL_ID    SCORES                    INPUTS(trunc)
ds-01      eval-001   f1=0.91 em=0.85           {"query": "what is..."}
ds-01      eval-002   f1=0.78 em=0.70           {"query": "how does..."}
(2 of 2 samples)
```

Flags: `--all`, `--limit N`, `--dataset <id>`.

### 4.3 `guide.md` — Agent Reference File

A static reference file shipped as a template in `luml-agent/template/guide.md`. Copied into `.luml-agent/guide.md` on worktree creation (alongside the `.luml-agent/` directory setup).

**Contents:**
- `luml-inspect` CLI reference: all commands, flags, and example outputs
- Output contract: `.luml-agent/result.json` schema (fields, types, examples)
- Fork output contract: `.luml-agent/fork.json` schema
- ExperimentTracker convention: `sqlite://~/.luml-agent/experiments` connection string, how to create/log experiments in Python code
- Metric consistency rules

The file is static — it does not contain run-specific context (experiment IDs, objective, etc.). Dynamic context is injected by the prompt builder. The prompt builder adds a line like: `"Refer to .luml-agent/guide.md for available tools and output format conventions."`

**Files:** `luml-agent/src/luml_agent/data/guide.md` — source template (packaged as package data, accessed via `importlib.resources`). `worktree.py` or node handlers — copy to `.luml-agent/guide.md` on worktree creation.

## 5. Node Instructions (Prompt Construction)

### 5.1 Approach

Create `src/luml_agent/services/orchestrator/prompts.py` — pure functions that build prompt strings from structured inputs. Each node handler calls the appropriate builder. Prompts are testable in isolation (no I/O, no side effects).

### 5.2 Implement Node Prompt

Two distinct variants — the agent inspects the repo itself in both cases, we do NOT auto-inject repo structure.

**Root implement** (depth 0, no parent fork):
- Objective (from user's run objective)
- Environment info (worktree path, base branch, `uv` as package manager)
- Reference to `.luml-agent/guide.md` for tooling and output conventions
- Guidelines (inspect repo, keep persistent entrypoint, prefer simple solutions)

**Fork-child implement** (spawned by a fork node):
- Proposed approach (from the fork proposal's `prompt` field — this is the primary instruction, NOT the original user objective)
- Original objective (included as background context only, clearly labeled as such)
- Environment info (same as root)
- Reference to `.luml-agent/guide.md`
- Metric consistency requirement (metric name(s) from the parent experiment — the agent must use the same metric name and calculation)
- Parent experiment IDs (for reference via `luml-inspect`)

The prompt builder distinguishes the two cases based on whether `payload` contains a fork proposal or the original objective. The fork proposal's `prompt` field is the agent's primary task — the original objective is secondary context.

### 5.3 Debug Node Prompt

- Failure details (exit code, original objective)
- Git diff: `git diff {base_branch}...HEAD` computed by the handler before spawning
- Failure logs: last `max_log_tail` chars (configurable via RunConfig, default 10000)
- Reference to `.luml-agent/guide.md`
- Experiment tracking preservation reminder

### 5.4 Fork Node Prompt

- Original objective
- Parent experiment IDs (for investigation via `luml-inspect`)
- Reference to `.luml-agent/guide.md` (which documents `luml-inspect` CLI usage)
- Run artifacts context (from parent run node)
- Guidelines: explore diverse strategies, preserve metric consistency, each proposal is self-contained
- Output format: `.luml-agent/fork.json` as array of `{"prompt": str, "title": str}`

### 5.5 RunConfig Additions (Summary)

```python
@dataclass
class RunConfig:
    # ... existing fields ...
    implement_timeout: int = 1800   # 30 min
    run_timeout: int = 0            # no timeout (training can be long)
    debug_timeout: int = 1800       # 30 min
    fork_timeout: int = 900         # 15 min
    max_log_tail: int = 10000
    primary_metric: str = "metric"
    metric_direction: str = "max"       # "max" or "min"
    luml_collection_id: str | None = None
    luml_organization_id: str | None = None
    luml_orbit_id: str | None = None
```

Corresponding additions to `RunCreateIn` and frontend `RunConfig` interface (WorkflowForm.vue advanced options).

---

# Scenarios

## `.luml-agent/` Directory Convention

### Scenario: `.luml-agent/` directory created before agent spawn
**Given** an implement node is about to spawn an agent in a worktree
**When** the handler runs its pre-spawn setup
**Then** `.luml-agent/` directory exists in the worktree root
**And** the agent can write `result.json` directly into it

### Scenario: Global experiments directory created at run start
**Given** a new run is started
**When** the engine initializes the run
**Then** `~/.luml-agent/experiments/` directory exists
**And** all nodes in the run can use `ExperimentTracker("sqlite://~/.luml-agent/experiments")` without path errors

### Scenario: `.gitignore` updated with single entry
**Given** a new worktree is created
**When** the worktree setup runs
**Then** `.luml-agent/` is added to the worktree's `.gitignore`
**And** no separate entries exist for `result.json`, `fork.json`, or `proposals/`

## Error Handling and Stability

### Scenario: Implement node times out
**Given** a run is configured with `implement_timeout = 60`
**When** an implement node's agent hangs and does not exit within 60 seconds
**Then** the node is marked FAILED with `error_message = "Node execution timed out after 60s"`
**And** the PTY session is terminated
**And** the run continues processing other nodes

### Scenario: Run node has no timeout by default
**Given** a run is created with default config (`run_timeout = 0`)
**When** a run node executes a long-running training job (e.g., 3 hours)
**Then** the run node waits indefinitely for the process to complete
**And** does not time out

### Scenario: Run node with custom timeout
**Given** a run is configured with `run_timeout = 7200` (2 hours)
**When** a run node exceeds 2 hours
**Then** the node is marked FAILED with timeout error
**And** the PTY session is terminated

### Scenario: PTY process crashes mid-execution
**Given** an implement node is running and its PTY process is killed externally (e.g., OOM)
**When** `cleanup_dead()` detects the dead process
**Then** `notify_session_exit()` is called with the process return code
**And** the node's `exit_event` is set, unblocking the handler
**And** the node is marked FAILED with the exit code in artifacts

### Scenario: PTY reader thread crashes
**Given** a node is running and its PTY reader thread encounters an unhandled exception
**When** the exception occurs
**Then** the reader thread logs the exception
**And** calls `notify_session_exit()` with exit code -1
**And** the node handler is unblocked and marks the node as FAILED

### Scenario: Worktree creation fails
**Given** a git worktree creation fails (e.g., branch already exists, disk full)
**When** the implement node handler catches the error
**Then** any partially created worktree directory is cleaned up
**And** the node is marked FAILED with a clear error message including the git stderr
**And** the run continues processing other queued nodes

### Scenario: PTY spawn fails
**Given** `pty.openpty()` or `subprocess.Popen()` fails (e.g., too many open FDs)
**When** the spawn error is raised
**Then** any opened FDs are closed
**And** a clear error is raised to the node handler
**And** the node is marked FAILED with the spawn error message

### Scenario: Fork proposal reading fails
**Given** a fork node's agent exits successfully but `.luml-agent/fork.json` is malformed JSON
**When** the fork handler tries to parse proposals
**Then** it falls back to `.luml-agent/result.json` proposals, then `.luml-agent/proposals/` directory
**And** if all fallbacks fail, the node is marked FAILED with `"Failed to read fork proposals: {error}"`

### Scenario: Scheduler encounters unrecoverable error
**Given** the database connection is lost during a scheduler tick
**When** the scheduler catches the database error
**Then** all currently RUNNING runs are marked as FAILED
**And** `run_status_changed` events are emitted for each
**And** the scheduler stops (does not loop with corrupt state)

### Scenario: Node handler exception includes stack trace
**Given** a node handler raises an unexpected exception
**When** the engine catches it in `_run_node()`
**Then** the full stack trace is logged via `logger.exception()`
**And** the exception message is stored in the node's `error_message`

### Scenario: Terminate after SIGKILL timeout
**Given** a PTY process does not exit after SIGKILL
**When** `proc.wait(timeout=2)` raises `TimeoutExpired`
**Then** the FD is force-closed
**And** `notify_session_exit()` is called with exit code -9
**And** the node is unblocked

## Worktree Lifecycle

### Scenario: Worktrees cleaned up after merge
**Given** a run completed with 5 nodes across 3 worktrees, and the best node is merged
**When** merge succeeds
**Then** all worktrees belonging to that run are removed from disk
**And** associated branches are deleted
**And** if any worktree removal fails, the error is logged but merge is not rolled back

### Scenario: Worktrees cleaned up on run deletion
**Given** a run with 3 worktrees exists
**When** the user deletes the run
**Then** all worktrees are removed before DB records are deleted
**And** cleanup errors are logged but do not prevent deletion

### Scenario: Worktrees cleaned up on run cancellation
**Given** a run with active nodes and worktrees
**When** the user cancels the run
**Then** all sessions are terminated first
**And** then all worktrees are removed

### Scenario: Shared data directory is symlinked
**Given** a repository with a `data/` directory containing 2GB of training data and `shared_paths = ["data"]` in config
**When** a new worktree is created for an implement node
**Then** `{worktree}/data` is a symlink to `{repo}/data` (not a copy)
**And** `data/` is added to the worktree's `.gitignore`
**And** the agent can read/write data through the symlink

### Scenario: Shared path does not exist in repo
**Given** `shared_paths = ["data"]` in config but the repo has no `data/` directory
**When** a worktree is created
**Then** no symlink is created for `data/` (skipped silently)
**And** worktree creation succeeds normally

### Scenario: Auto-commit uncommitted changes after implement
**Given** an implement node's agent exits successfully but leaves uncommitted changes (modified files not staged/committed)
**When** the implement handler processes the result
**Then** it runs `git add -A && git commit -m "luml-agent: auto-commit uncommitted changes"` in the worktree
**And** the changes are committed on the node's branch
**And** fork-child worktrees (branched from this branch) will see the changes

### Scenario: Auto-commit with no uncommitted changes
**Given** an implement node's agent committed all its changes before exiting
**When** the implement handler checks for uncommitted changes
**Then** `git status --porcelain` returns empty
**And** no auto-commit is performed

### Scenario: Auto-commit after debug node
**Given** a debug node's agent fixes code but doesn't commit
**When** the debug handler processes the result
**Then** uncommitted changes are auto-committed (same as implement)

### Scenario: Merge conflict detection
**Given** a run's best branch has changes that conflict with the base branch
**When** the user clicks Merge in the frontend
**Then** `git merge` fails with conflicts
**And** the backend returns a 409 response with `conflicting_files: ["path/to/file1.py", "path/to/file2.py"]`
**And** `git merge --abort` is called to restore clean state

### Scenario: Merge conflict display in frontend
**Given** the backend returns a 409 merge conflict response
**When** MergeDialog.vue receives the error
**Then** it displays the list of conflicting files
**And** shows the worktree path where the user can resolve conflicts manually

### Scenario: Env files preserved in new worktrees
**Given** a repo with `.env` and `.env.local` files
**When** a worktree is created
**Then** both files are copied to the new worktree (not symlinked — env files may differ per branch)

### Scenario: Worktree cleanup deferred for pending uploads
**Given** a run with `luml_collection_id` has a successful run node with a PENDING upload
**When** the user merges the best node
**Then** merge succeeds
**And** worktrees for nodes with pending uploads are NOT removed
**And** `worktrees_pending_upload` event is emitted via WebSocket
**And** the frontend displays "Worktrees will be cleaned up after uploads complete"

### Scenario: Deferred worktree cleanup completes after upload
**Given** worktree cleanup was deferred due to a pending upload
**When** the upload completes (COMPLETED or FAILED)
**Then** the deferred worktree is removed
**And** the frontend is notified via `worktree_cleaned` event

### Scenario: Run deletion cancels pending uploads and cleans up immediately
**Given** a run with a PENDING upload
**When** the user deletes the run
**Then** pending uploads are cancelled (status → FAILED)
**And** all worktrees are removed immediately
**And** DB records are deleted

## SDK Integration and Experiment ID Propagation

### Scenario: Result file with single experiment ID
**Given** a training script writes `.luml-agent/result.json` with `"experiment_id": "abc-123"` and `"metrics": {"accuracy": 0.92}`
**When** the run node reads the result file
**Then** `artifacts["experiment_ids"]` is `["abc-123"]`
**And** `artifacts["metrics"]` is `{"accuracy": 0.92}`
**And** `artifacts["metric"]` is `0.92` (first value, for backward compat)

### Scenario: Result file with multiple experiment IDs (grid search)
**Given** a training script writes `.luml-agent/result.json` with `"experiment_ids": ["exp-1", "exp-2", "exp-3"]` and `"metrics": {"accuracy": 0.95}`
**When** the run node reads the result file
**Then** `artifacts["experiment_ids"]` is `["exp-1", "exp-2", "exp-3"]`
**And** `artifacts["metrics"]` is `{"accuracy": 0.95}`

### Scenario: Experiment IDs propagate to fork payload
**Given** a run node succeeds with `artifacts["experiment_ids"] = ["exp-1"]`
**When** the engine spawns a fork node
**Then** the fork payload contains `experiment_ids: ["exp-1"]`
**And** the fork agent receives the IDs in its prompt and uses `luml-inspect` to investigate

### Scenario: Fork agent investigates experiments independently
**Given** a fork node receives `experiment_ids` in its payload
**When** the fork agent runs
**Then** the prompt provides experiment IDs and references `.luml-agent/guide.md` which documents `luml-inspect`
**And** the agent uses `luml-inspect` commands to explore metrics, params, and traces on its own
**And** the orchestrator does NOT pre-parse or summarize experiments

### Scenario: Auto-dependency injection — luml not in pyproject.toml
**Given** a fresh repo with a `pyproject.toml` that does not list `luml`
**When** the implement node creates a worktree
**Then** it runs `uv add luml` before spawning the agent
**And** if `uv add` fails (e.g., network error), the failure is logged but the agent is still spawned

### Scenario: Auto-dependency injection — no pyproject.toml
**Given** a repo with no `pyproject.toml`
**When** the implement node creates a worktree
**Then** the `uv add luml` step is skipped (logged as info)
**And** the agent is spawned normally (it can create pyproject.toml itself)

### Scenario: Auto-dependency injection — luml already present
**Given** a repo where `luml` is already in `pyproject.toml`
**When** the implement node creates a worktree
**Then** it skips the `uv add luml` step

### Scenario: Backward-compatible result file (no experiment data)
**Given** a training script writes `.luml-agent/result.json` with only `"success": true` and no experiment fields
**When** the run node reads the result file
**Then** `artifacts["experiment_ids"]` is `[]`
**And** metrics fall back to stdout parsing (`parse_stdout_metric()`)
**And** the pipeline continues normally

### Scenario: Backward-compatible stdout metric
**Given** a run produces no `.luml-agent/result.json` but prints `{"type": "luml-agent-message", "metric": 0.5}` to stdout
**When** the run node completes
**Then** `artifacts["metric"]` is `0.5`
**And** `artifacts["experiment_ids"]` is `[]`
**And** best-node selection works using `artifacts["metric"]`

### Scenario: Best node selection with primary_metric config
**Given** a run is created with `primary_metric = "f1_score"`
**When** run nodes succeed with `metrics: {"f1_score": 0.85}` and `metrics: {"f1_score": 0.88}`
**Then** `_compute_best_node()` selects the node with `f1_score = 0.88`

### Scenario: Best node selection fallback
**Given** a run with `primary_metric = "f1_score"` but run nodes only have `artifacts["metric"]` (no metrics dict)
**When** `_compute_best_node()` runs
**Then** it falls back to `artifacts["metric"]` for comparison

### Scenario: Metric consistency via fork prompt
**Given** a fork node runs after a run that tracked metrics `["accuracy", "loss"]`
**When** child implement nodes receive their prompts
**Then** each prompt contains the metric names from the parent and instructs the agent to use the same metric name and calculation

### Scenario: Discovered metric keys recorded on first success
**Given** a run's first run node succeeds with `metrics: {"accuracy": 0.92, "loss": 0.08}`
**When** the engine processes the result
**Then** the Run's `discovered_metric_keys` is set to `["accuracy", "loss"]`
**And** subsequent run nodes do not overwrite this field

## Collection-Linked Uploads

### Scenario: Successful end-to-end upload
**Given** a run with `luml_collection_id` set and frontend connected
**When** a run node succeeds with `experiment_ids: ["exp-1"]` and `model_path: "model.luml"`
**Then** the engine links the experiment to the model locally via `tracker.link_to_model()`
**And** enqueues an upload with status PENDING
**And** emits `upload_ready` via WebSocket
**And** the frontend creates an artifact on the main LUML backend and gets a presigned URL
**And** the frontend POSTs the presigned URL to `POST /api/runs/{run_id}/uploads/{upload_id}/url`
**And** the agent-backend uploads the file to the presigned URL
**And** on success, emits `upload_completed` via WebSocket
**And** the frontend confirms the upload to the main LUML backend
**And** the pipeline continues to fork node without waiting for any of this

### Scenario: Upload with missing model_path
**Given** a run node succeeds with `experiment_ids: ["exp-1"]` but no `model_path` in artifacts
**When** the engine checks upload conditions
**Then** no upload is enqueued (both `experiment_ids` and `model_path` are required)

### Scenario: Experiment linking fails
**Given** a run node succeeds with `experiment_ids` and `model_path`
**When** `tracker.link_to_model()` raises an error (e.g., corrupt experiment DB)
**Then** the upload is not enqueued
**And** the error is logged as a warning
**And** the pipeline continues normally

### Scenario: Frontend disconnected when artifact is ready
**Given** a run with `luml_collection_id` and no frontend connected
**When** a run node succeeds and an upload is enqueued
**Then** the `upload_ready` event is emitted but not received by anyone
**And** the upload stays in PENDING status
**And** the pipeline continues normally

### Scenario: Frontend reconnects and resumes pending uploads
**Given** an upload is in PENDING status (frontend was disconnected)
**When** a frontend tab connects and loads the run
**Then** it calls `GET /api/runs/{run_id}/uploads?status=pending`
**And** receives the pending upload
**And** resumes the presigned URL flow (create artifact, get URL, POST to agent-backend)

### Scenario: Multiple tabs — only one handles upload
**Given** two browser tabs are open for the same run
**When** an `upload_ready` event is received by both tabs
**And** both tabs request presigned URLs and POST them to the agent-backend
**Then** the first tab's POST succeeds (200 Accepted) and `claim()` transitions the upload to IN_PROGRESS
**And** the second tab's POST receives 409 Conflict
**And** the second tab shows "Upload in progress" or silently ignores
**And** only one upload occurs

### Scenario: Upload failure (presigned URL upload fails)
**Given** the agent-backend is uploading a file to the presigned URL
**When** the upload fails (network error, timeout, storage error)
**Then** the upload status is set back to PENDING (not FAILED) with error message
**And** `upload_failed` event is emitted via WebSocket with the error
**And** the frontend shows the error and a retry button
**And** on retry, the frontend requests a new presigned URL (the old one may have expired) and POSTs it again
**And** after 3 consecutive failures, the upload status is set to FAILED permanently

### Scenario: Multi-experiment upload (grid search)
**Given** a run node succeeds with `experiment_ids: ["exp-1", "exp-2", "exp-3"]` and `model_path: "model.luml"` and `primary_metric = "accuracy"`
**When** the engine links experiments before enqueuing
**Then** it reads all 3 experiments from the tracker DB
**And** identifies the experiment with the best `accuracy`
**And** links that experiment to the model
**And** enqueues a single upload for the model file (which now embeds the best experiment)

### Scenario: Upload happens for each successful run node
**Given** a run with `luml_collection_id` and multiple fork branches
**When** run nodes on branch A and branch B both succeed
**Then** each successful run node enqueues its own upload independently
**And** the frontend handles each `upload_ready` event separately
**And** both models are uploaded to the collection

### Scenario: Frontend collection selector in workflow form
**Given** an authenticated user opens the "New Workflow" dialog
**When** the advanced options section is expanded
**Then** a collection dropdown is shown (populated from the main LUML backend via existing collection service)
**And** selecting a collection sets `luml_collection_id`, `luml_organization_id`, `luml_orbit_id` on the run
**And** leaving it empty creates a run without collection linking

## `luml-inspect` CLI

### Scenario: Default metric subsampling
**Given** an experiment `abc-123` with 5000 steps of `accuracy` data
**When** the agent runs `luml-inspect metrics abc-123 accuracy`
**Then** output shows ~20 bucketed rows, each with STEP, VALUE, MIN, MAX columns
**And** MIN/MAX reflect the range within that bucket (not global)
**And** a header line says `(500 steps, showing 20 buckets)`
**And** no flag is needed — subsampling is the default

### Scenario: Full metric dump with --all
**Given** an experiment with 5000 steps of `loss` data
**When** the agent runs `luml-inspect metrics abc-123 loss --all`
**Then** all 5000 rows are printed (no bucketing, no MIN/MAX columns)

### Scenario: Last N data points
**Given** an experiment with 5000 steps
**When** the agent runs `luml-inspect metrics abc-123 accuracy --last 10`
**Then** only the last 10 raw data points are shown (no bucketing)

### Scenario: Compare with subsampling
**Given** experiments `abc-123` and `def-456` each with 5000 steps
**When** the agent runs `luml-inspect compare abc-123 def-456`
**Then** output shows a params diff table followed by per-metric bucketed comparison
**And** each metric row shows VAL/MIN/MAX per experiment per bucket
**And** subsampling defaults to 20 buckets

### Scenario: Compare --summary
**Given** experiments `abc-123` and `def-456`
**When** the agent runs `luml-inspect compare abc-123 def-456 --summary`
**Then** output shows params diff and per-metric summary (final/min/max/mean) only, no step rows

### Scenario: List experiments with default cap
**Given** 50 experiments in the global DB
**When** the agent runs `luml-inspect list`
**Then** only 20 experiments are shown
**And** a footer says `(20 of 50 experiments, use --all for full list)`

### Scenario: Show experiment details
**Given** an experiment `abc-123` with static params and 3 metric keys
**When** the agent runs `luml-inspect show abc-123`
**Then** output shows metadata, all static params, and a metric summary table (STEPS, FINAL, MIN, MAX, MEAN per key)

### Scenario: Evals with default cap
**Given** an experiment with 100 eval samples
**When** the agent runs `luml-inspect evals abc-123`
**Then** only 10 samples are shown
**And** a footer indicates truncation

### Scenario: Default experiment DB path
**Given** the agent is in a worktree at `/repo/.worktrees/branch-1`
**When** the agent runs `luml-inspect list` without `--db`
**Then** the CLI uses `~/.luml-agent/experiments` (no git detection needed)

### Scenario: Custom DB path
**Given** experiments stored at `/tmp/my-experiments`
**When** the agent runs `luml-inspect list --db /tmp/my-experiments`
**Then** the CLI uses the specified path instead of the auto-detected one

## `guide.md` Agent Reference

### Scenario: guide.md copied to worktree on creation
**Given** a new worktree is created for an implement node
**When** the `.luml-agent/` directory setup runs
**Then** `guide.md` is copied from the `luml-agent` package data to `{worktree}/.luml-agent/guide.md`

### Scenario: guide.md is static and agent-agnostic
**Given** a `guide.md` in `.luml-agent/`
**When** any agent (Claude Code, Codex, etc.) reads it
**Then** it contains the full `luml-inspect` CLI reference, `.luml-agent/result.json` schema, `.luml-agent/fork.json` schema, ExperimentTracker conventions, and metric consistency rules
**And** it contains NO run-specific context (no experiment IDs, no objective, no metric names)

### Scenario: Prompt references guide.md
**Given** any node prompt is constructed (implement, debug, fork)
**When** the prompt builder runs
**Then** the prompt includes a line directing the agent to `.luml-agent/guide.md` for tooling and output conventions
**And** run-specific context (experiment IDs, objective, metrics) is in the prompt itself, not in guide.md

## Node Instructions

### Scenario: Root implement prompt uses user objective
**Given** a root implement node is spawned with the user's run objective
**When** the prompt is constructed
**Then** it includes the user objective as the primary instruction
**And** environment info and a reference to `.luml-agent/guide.md`
**And** does NOT include auto-detected repo structure (agent inspects repo itself)
**And** does NOT inline CLI usage or output contracts (those are in guide.md)

### Scenario: Fork-child implement prompt uses proposal, not user objective
**Given** a fork node produced a proposal `{"prompt": "Try gradient boosting with learning_rate=0.01", "title": "GBM low LR"}`
**And** the parent experiment used metrics `["accuracy"]`
**When** the child implement node prompt is constructed
**Then** the proposal prompt ("Try gradient boosting with learning_rate=0.01") is the primary instruction
**And** the original user objective is included as background context only
**And** a "Metric Consistency" section specifies `accuracy` as the required metric
**And** parent experiment IDs are included for reference (agent uses `luml-inspect` to explore them)

### Scenario: Debug prompt includes git diff
**Given** an implement node modified files and the subsequent run node failed
**When** the debug node prompt is constructed
**Then** it includes the `git diff {base_branch}...HEAD` output
**And** the last `max_log_tail` chars of failure logs (default 10000)
**And** the original objective and output contract

### Scenario: Configurable log truncation in debug
**Given** a run with `max_log_tail = 20000`
**When** a debug node is spawned after a failure producing 50,000 chars of logs
**Then** the debug prompt includes the last 20,000 chars

### Scenario: Fork prompt gives agent experiment investigation tools
**Given** a fork node receives `experiment_ids: ["exp-1"]` in payload
**When** the fork prompt is constructed
**Then** it provides the experiment IDs and references `.luml-agent/guide.md` for `luml-inspect` CLI usage
**And** the agent uses `luml-inspect show exp-1` and `luml-inspect metrics exp-1 <key>` to explore results
**And** the agent decides what metrics/params to look at and how to decompose the next iteration

---

# Tasks

- [x] Task 1: `.luml-agent/` directory convention + `.gitignore` — Foundation task, all subsequent tasks depend on this.
  - [x] Create utility function `ensure_luml_agent_dir(worktree_path: str) -> Path` in `src/luml_agent/services/orchestrator/utils.py` that creates `{worktree_path}/.luml-agent/` and returns the path
  - [x] Create utility function `ensure_global_luml_dir() -> Path` that creates `~/.luml-agent/experiments/` (with `parents=True`) and returns `~/.luml-agent/`
  - [x] Update `worktree.py` — on worktree creation, add `.luml-agent/` to the worktree's `.gitignore` (remove any old entries for `.luml-fork.json`, `.proposals/`, `result.json`)
  - [x] Call `ensure_luml_agent_dir()` in each node handler (`implement.py`, `fork.py`, `debug.py`, `run_node.py`) before spawning the agent
  - [x] Call `ensure_global_luml_dir()` in engine startup
  - [x] Tests: verify directory creation (idempotent), `.gitignore` content, old entries removed
- [x] Task 2: Error handling — node execution timeout + PTY crash recovery
  - [x] Add per-node-type timeout fields to `RunConfig` (`implement_timeout`, `run_timeout`, `debug_timeout`, `fork_timeout`). Add to `RunCreateIn` schema, frontend `RunConfig` interface, and API client
  - [x] In each node handler, call `exit_event.wait(timeout=...)`. On timeout: mark node FAILED, terminate PTY session, emit `node_completed` event with timeout error
  - [x] PTY crash recovery in `pty_manager.py`: `cleanup_dead()` always calls `notify_session_exit()`, reader thread catches unhandled exceptions and calls `notify_session_exit(exit_code=-1)`, `terminate()` handles `TimeoutExpired` after SIGKILL
  - [x] PTY spawn error handling: wrap `openpty()` and `Popen()` in try/except, clean up FDs on failure
  - [x] Log full stack traces via `logger.exception()` in engine's `_run_node()` exception handler
  - [x] Tests: mock a hanging process → verify timeout fires. Mock a crashing process → verify error propagation. Mock spawn failure → verify FD cleanup. Verify `logger.exception()` called
- [x] Task 3: Worktree lifecycle — cleanup, shared paths, auto-commit, merge conflicts
  - [x] Add worktree cleanup after merge, on run deletion, and on run cancellation (`handlers/run.py`). Cleanup errors logged but don't fail the parent operation
  - [x] Implement shared data symlinks: `shared_paths` config in `AppConfig`, `_setup_shared_paths()` in `worktree.py`. Add shared paths to worktree `.gitignore`
  - [x] Implement auto-commit in `implement.py` and `debug.py`: after agent exits, check `git status --porcelain`, if dirty run `git add -A && git commit -m "luml-agent: auto-commit uncommitted changes"`
  - [x] Remove unused `exclude_patterns` from config
  - [x] Merge conflict detection: in `merge.py`, detect conflicts, return `MergeConflictError` with `conflicting_files` list (409 response). Frontend `MergeDialog.vue` displays the list
  - [x] Scheduler resilience: distinguish recoverable vs unrecoverable errors in `_schedule_tick()`. On unrecoverable: mark all running runs as FAILED and stop
  - [x] Tests: verify cleanup on merge/delete/cancel, verify symlink creation, verify auto-commit, verify no auto-commit when clean, verify merge conflict detection and 409 response, verify scheduler stops on unrecoverable error
- [x] Task 4: Result file contract + `result_file.py`
  - [x] Create `src/luml_agent/services/orchestrator/result_file.py` with `read_result_file(worktree_path: str) -> ResultData`
  - [x] `ResultData` dataclass: `success: bool`, `experiment_id: str | None`, `experiment_ids: list[str]`, `metrics: dict[str, float]`, `model_path: str | None`, `error_message: str | None`
  - [x] Parse `.luml-agent/result.json` — normalize `experiment_id` (singular) to `experiment_ids` (list). Normalize `metric` (float) to `metrics: {"metric": value}` for backward compat
  - [x] Integrate into `run_node.py`: after run command execution, call `read_result_file()` and store normalized data in `result.artifacts`
  - [x] Fall back to stdout parsing (`parse_stdout_metric()`) when result file is missing
  - [x] Tests: test all result file variants (single ID, multiple IDs, legacy `metric` float, missing file, malformed JSON, missing fields, stdout fallback)
- [x] Task 5: Experiment ID propagation through node graph
  - [x] Add `primary_metric: str = "metric"` and `metric_direction: str = "max"` to `RunConfig`, `RunCreateIn`, frontend interfaces
  - [x] Add `discovered_metric_keys: list[str]` field on Run DB model. Set on first successful run node. DB migration needed
  - [x] In `engine.py` `_process_result()`: when spawning a fork node after a successful run, include `experiment_ids` and `discovered_metric_keys` in the fork payload
  - [x] In `fork.py`: when creating child implement node payloads, copy `objective`, `experiment_ids`, and `discovered_metric_keys` from the fork's own payload
  - [x] Implement `_compute_best_node()` in `engine.py`: compare successful RUN nodes by `artifacts["metrics"][primary_metric]` using `metric_direction`. Store `best_node_id` on the Run. Fall back to `artifacts["metric"]` when metrics dict is missing
  - [x] Tests: verify fork payload contains experiment IDs. Verify child payloads contain parent data. Verify best-node selection with max and min direction. Verify fallback behavior
- [x] Task 6: Auto-dependency injection (`luml` SDK)
  - [x] Create helper `_ensure_luml_dependency(worktree_path: str) -> None` in `implement.py` or shared utility
  - [x] Check `pyproject.toml` for `luml` in dependencies. If missing, run `uv add luml` via subprocess
  - [x] Handle edge cases: no `pyproject.toml` (skip with info log), `uv` not available (skip with warning), network error (skip with warning), `luml` already present (no-op)
  - [x] Call before `pty.spawn()` in `implement.py`
  - [x] Tests: verify injection into a fresh worktree, verify no-op when already present, verify skip when no `pyproject.toml`, verify graceful handling of `uv` failure
- [x] Task 7: `luml-inspect` CLI — core commands (`list`, `show`, `params`)
  - [x] Create `src/luml_agent/cli/inspect.py` with Typer app
  - [x] Register `luml-inspect` entry point in `pyproject.toml`
  - [x] Implement `list` command: query ExperimentTracker at `~/.luml-agent/experiments`, format as compact table, default cap 20, `--all`/`--limit`/`--group`/`--tag` flags. Include final metric values per experiment
  - [x] Implement `show <id>` command: metadata + static params + per-metric summary (STEPS, FINAL, MIN, MAX, MEAN)
  - [x] Implement `params <id>` command: compact key-value dump
  - [x] Global `--db` flag, default `~/.luml-agent/experiments`
  - [x] Tests: seed an experiment DB with known data, verify output formatting, verify default caps, verify `--all` override, verify `--db` flag
- [ ] Task 8: `luml-inspect` CLI — `metrics` command with bucketing
  - [ ] Implement `metrics <id> <key>` command
  - [ ] Implement bucketing logic: divide steps into N buckets (default 20), each row shows representative STEP + VALUE at that step + MIN/MAX across the bucket. Header shows total steps and bucket count
  - [ ] Implement flags: `--all` (raw, no bucketing), `--last N` (last N raw points), `--every N` (every Nth step, raw), `--summary` (only final/min/max/mean), `--buckets N` (override bucket count)
  - [ ] Tests: verify bucketing with known data (exact step/min/max values), verify all flags, edge cases (fewer steps than buckets, single step, empty metrics)
- [ ] Task 9: `luml-inspect` CLI — `compare` and `evals` commands
  - [ ] Implement `compare <id1> <id2> [...]` command: params diff table (highlight differences, mark same values), per-metric bucketed comparison with VAL/MIN/MAX per experiment per bucket. Same subsampling flags as `metrics`
  - [ ] Implement `evals <id>` command: tabular eval samples, default cap 10, `--all`/`--limit`/`--dataset` flags, truncate long input/output strings
  - [ ] Tests: verify compare output with 2 and 3 experiments, verify params diff formatting, verify evals truncation and caps
- [ ] Task 10: `guide.md` template + worktree injection
  - [ ] Create `src/luml_agent/data/guide.md` with: `luml-inspect` CLI reference (all commands, flags, examples), `.luml-agent/result.json` schema, `.luml-agent/fork.json` schema, ExperimentTracker connection string convention (`sqlite://~/.luml-agent/experiments`), metric consistency rules
  - [ ] Register `data/guide.md` as package data in `pyproject.toml`
  - [ ] Update `ensure_luml_agent_dir()` (from Task 1) to also copy `guide.md` into `{worktree}/.luml-agent/guide.md` using `importlib.resources`
  - [ ] Tests: verify `guide.md` is accessible via `importlib.resources`, verify it's copied to worktree, verify content includes all required sections
- [ ] Task 11: Upload queue + REST endpoints
  - [ ] Create `src/luml_agent/services/upload_queue.py` with `PendingUpload` dataclass and `UploadStatus` enum
  - [ ] Implement SQLite-backed queue at `~/.luml-agent/uploads.db`: `enqueue()`, `claim()` (atomic PENDING→IN_PROGRESS), `complete()`, `fail()`, `get_pending()`, `cleanup_resolved()`
  - [ ] Add REST endpoint `POST /api/runs/{run_id}/uploads/{upload_id}/url` — claims upload, starts background file upload to presigned URL, returns 202 or 409
  - [ ] Add REST endpoint `GET /api/runs/{run_id}/uploads?status=pending` — returns pending uploads for reconnect
  - [ ] Implement retry logic: on upload failure, increment `retry_count`, set back to PENDING if < 3, FAILED if >= 3
  - [ ] Tests: verify enqueue/claim/complete/fail state transitions, verify claim is atomic (concurrent claims), verify retry count behavior, verify cleanup of old entries, verify REST endpoint responses (202, 409)
- [ ] Task 12: Upload integration — engine + WebSocket events + worktree deferral
  - [ ] In `engine.py` `_process_result()`: after successful RUN node with `luml_collection_id`, link experiment to model via `ExperimentTracker("sqlite://~/.luml-agent/experiments")`, then enqueue upload
  - [ ] Emit `upload_ready` event via WebSocket (with upload_id, run_id, node_id, file_size, experiment_ids, collection/org/orbit IDs)
  - [ ] Emit `upload_completed` and `upload_failed` events from the upload background task
  - [ ] Implement upload-aware worktree cleanup: check upload queue before removing worktrees, defer if pending, emit `worktrees_pending_upload`. On `upload_completed`/`upload_failed`, trigger deferred cleanup if all uploads resolved
  - [ ] On run deletion/cancellation: cancel pending uploads, clean up immediately
  - [ ] Tests: verify upload enqueue on successful RUN with collection ID, verify no enqueue without collection ID or model_path, verify worktree deferral, verify cleanup after upload completion, verify deletion cancels uploads
- [ ] Task 13: Collection-linked uploads — frontend
  - [ ] Add `luml_collection_id`, `luml_organization_id`, `luml_orbit_id` to frontend `RunConfig` interface (`data-agent.interfaces.ts`)
  - [ ] Add collection selector dropdown to WorkflowForm.vue (advanced options section): fetch collections from main LUML backend, only show if authenticated
  - [ ] Add `metric_direction` dropdown to WorkflowForm.vue (advanced options)
  - [ ] Pass new fields in `createRun()` API client
  - [ ] Handle `upload_ready` WebSocket event: create artifact on main LUML backend, get presigned URL, POST to agent-backend. Handle 409 (another tab claimed it)
  - [ ] Handle `upload_completed`: confirm upload to main LUML backend
  - [ ] Handle `upload_failed`: show error, offer retry button
  - [ ] On page load/reconnect: call `GET /api/runs/{run_id}/uploads?status=pending`, resume flow for each
  - [ ] Handle `worktrees_pending_upload` event: display status message
  - [ ] Tests: verify form fields, verify WebSocket event handling, verify 409 handling, verify reconnect flow
- [ ] Task 14: Prompt construction — implement + debug
  - [ ] Create `src/luml_agent/services/orchestrator/prompts.py` with pure functions (no I/O)
  - [ ] `build_implement_prompt(payload, run_config) -> str`: root variant (objective + environment + guide.md reference) and fork-child variant (proposal as primary instruction + objective as context + metric consistency + parent experiment IDs)
  - [ ] `build_debug_prompt(payload, git_diff, failure_logs, run_config) -> str`: failure details + diff + truncated logs + guide.md reference
  - [ ] Integrate into `implement.py` and `debug.py` — call prompt builders, pass result to agent
  - [ ] In `debug.py` handler: compute `git diff {base_branch}...HEAD` before spawning agent
  - [ ] Tests: verify root vs fork-child prompt differentiation, verify metric consistency section in fork-child, verify log truncation at `max_log_tail`, verify guide.md reference in all prompts
- [ ] Task 15: Prompt construction — fork
  - [ ] `build_fork_prompt(payload, run_config) -> str`: objective + experiment IDs + guide.md reference + decomposition guidelines + output format (`.luml-agent/fork.json`)
  - [ ] Integrate into `fork.py` — call prompt builder, pass result to agent
  - [ ] Update fork node handler: read proposals from `.luml-agent/fork.json` (primary), fall back to `.luml-agent/result.json`, fall back to `.luml-agent/proposals/` directory. All reads wrapped in try/except
  - [ ] Update child payload construction: copy `objective`, `experiment_ids`, `discovered_metric_keys` from fork's payload into each child's payload alongside the proposal `prompt`
  - [ ] Tests: verify prompt includes experiment IDs and guide.md reference, verify proposal reading from all three sources, verify fallback order, verify child payload construction
