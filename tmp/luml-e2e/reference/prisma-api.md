# Prisma engine REST reference (luml-prisma 0.2.0, source checkout)

Engine: `uvicorn` app at `http://127.0.0.1:8420`, hardcoded host/port
(`luml_prisma/server.py`); run `uvicorn luml_prisma.server:app --port N` for a
different port. No auth. Health: `GET /api/health/` (trailing slash) ->
`{"service": "luml-prisma", "version": ...}`.

State: `~/.luml/prisma/` (engine DB, session logs, `config.toml`). The
experiment store is separate: `~/.luml/experiments/`.

## Repositories

- `POST /api/repositories` body `{"name": ..., "path": "/abs/path"}` -> 201
  `{id, name, path}`. Path is resolved and must contain `.git` (else 400).
- `GET /api/repositories`, `DELETE /api/repositories/{id}`.

## Runs (the optimization loop)

`POST /api/runs` -> 201. Fields of `RunCreateIn` with defaults:

| field | default | notes |
| --- | --- | --- |
| `repository_id` | required | |
| `name` | required | board label + branch slug |
| `objective` | required | becomes the root Implement prompt |
| `base_branch` | `"main"` | worktrees fork from here |
| `agent_id` | `"claude"` | `claude` / `codex` / `gemini` / `cursor` / `copilot` / `opencode` (see `GET /api/agents/available`) |
| `run_command` | `"uv run main.py"` | executed by every Run node; must write `.prisma/result.json` |
| `max_depth` | 2 | fork depth cap |
| `max_children_per_fork` | 2 | proposals per Fork node |
| `max_debug_retries` | 2 | Debug nodes per branch |
| `max_concurrency` | 1 | parallel nodes |
| `auto_mode` | false | REQUIRED true for unattended runs: adds permission bypass + "no human available" prompt + idle auto-terminate |
| `auto_terminate_timeout` | 30 | seconds of terminal silence => agent done |
| `implement_timeout` / `run_timeout` / `debug_timeout` / `fork_timeout` | — | **silently ignored by the engine (bug)**; defaults 3600/0/1800/1200s apply |
| `max_log_tail` | 10000 | chars of failing log fed to Debug |
| `primary_metric` | `"metric"` | winner = argmax of this key in result.json metrics |
| `luml_collection_id` / `luml_organization_id` / `luml_orbit_id` | null | only for artifact upload via the platform UI |

Lifecycle:
- `POST /api/runs/{id}/start`, `/cancel`, `/restart`, `DELETE /api/runs/{id}`
- `GET /api/runs?repository_id=...`, `GET /api/runs/{id}`
- `GET /api/runs/{id}/graph` -> `{nodes, edges}`; node fields include
  `node_type` (implement/run/fork/debug), `status`, `depth`, `worktree_path`,
  `branch`, `result`
- `GET /api/runs/{id}/events?after_seq=0` -> poll-friendly event log
- `POST /api/runs/{id}/merge/preview`, `POST /api/runs/{id}/merge` -> merges
  the best node's branch into `base_branch`; refused if no best node
- WebSockets: `ws://.../ws/runs/{run_id}`, `ws://.../ws/terminal/{session_id}`
- `POST /api/nodes/{node_id}/input` body `{"text": ...}` writes into the live
  agent PTY; `POST /api/nodes/{node_id}/action` with `cancel`/`approve_fork`

## Execution model (what to expect while watching)

- Root node is Implement (the objective). Success -> Run node executes
  `run_command` in the worktree, deleting any stale `.prisma/result.json`
  first. Run success -> Fork node proposes up to `max_children_per_fork`
  approaches (skipped when depth cap reached); each becomes a child Implement.
  Run failure -> Debug node with the log tail, up to `max_debug_retries`.
- Worktrees are created NEXT to the repo (`<repo_parent>/worktrees/<slug>`),
  branch `prisma/<slug>-<hex>`. `.env*` files are copied in; `data/` (default
  `shared_paths`) is symlinked; uncommitted agent changes are auto-committed
  after each node.
- If the repo's `pyproject.toml` lacks a `luml`/`luml-sdk` dep, the engine
  runs `uv add luml-sdk` in the worktree.
- Agents inherit the engine process's PATH (VIRTUAL_ENV/CONDA_PREFIX are
  stripped) — launch the engine from an env whose bin dir has `luml-inspect`.
- Metric ingestion: `.prisma/result.json`
  `{"success": bool, "experiment_id" | "experiment_ids", "metrics": {k: float}}`;
  fallback: last stdout line matching
  `{"type": "prisma-message", "metric": <number>}`; else success = exit 0 with
  no metrics (node can't win).
- Experiment ids from result.json are propagated into Fork prompts and
  fork-child Implement prompts, which tell agents to use
  `luml-inspect show/metrics/params/compare` (and, per your AGENTS.md,
  `tools/traces.py`).
