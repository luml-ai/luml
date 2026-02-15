# Migration Spec: Adopt `luml-satellite-kit` in `satellite/`

## Overview

Replace the satellite agent's hand-rolled framework layer with the `luml-satellite-kit` SDK. The kit already provides identical implementations of the generic satellite infrastructure (polling, dispatching, pairing, platform client, schemas, settings, app factory). The agent becomes a thin consumer that only contains deploy/undeploy-specific logic.

## Current State

The `satellite/agent/` codebase has two layers interleaved:

1. **Generic satellite framework** — task polling, dispatching, pairing, platform HTTP client, base settings, shared schemas, health endpoint
2. **Deploy-specific logic** — Docker container management, model server communication, OpenAPI schema merging, inference proxying, deployment sync

The `satellite-kit/` package already extracted layer (1) into a standalone SDK with the same interfaces, same method signatures, and same behavior. The implementations are functionally identical (verified by line-by-line comparison). The only differences are import paths and a few minor API shape changes.

## What the Kit Provides (drop-in replacements)

| Kit export | Replaces in agent | Status |
|---|---|---|
| `PlatformClient` | `agent.clients.platform_client.PlatformClient` | Identical implementation |
| `BaseSatelliteTask` | `agent.tasks.base.Task` | Same ABC, minus `docker` param in base `__init__` |
| `TaskDispatcher` | `agent.handlers.tasks.TaskHandler` | Same dispatch logic, takes handlers dict instead of hardcoding |
| `PeriodicController` | `agent.controllers.periodic.PeriodicController` | Identical, accepts `TaskDispatcher` instead of `TaskHandler` |
| `SatelliteManager` | `agent.agent_manager.SatelliteManager` | Same, but `capabilities`/`slug`/`base_url` passed in instead of hardcoded |
| `BaseSatelliteSettings` | `agent.settings.Settings` (base fields only) | Same 4 base fields |
| `create_satellite_app()` | `agent.agent_api.create_agent_app()` (healthz only) | Thin app factory with `/healthz` and extra routers |
| `SatelliteQueueTask` | `agent.schemas.task.SatelliteQueueTask` | Identical |
| `SatelliteTaskType` | `agent.schemas.task.SatelliteTaskType` | Identical |
| `SatelliteTaskStatus` | `agent.schemas.task.SatelliteTaskStatus` | Identical |
| `Deployment` | `agent.schemas.deployments.Deployment` | Identical |
| `DeploymentUpdate` | `agent.schemas.deployments.DeploymentUpdate` | Identical |
| `DeploymentStatus` | `agent.schemas.deployments.DeploymentStatus` | Identical |
| `Secret` | `agent.schemas.deployments.Secret` | Identical |
| `ErrorMessage` | `agent.schemas.deployments.ErrorMessage` | Identical |

## What Stays in the Agent (deploy-specific)

| Module | Reason |
|---|---|
| `clients/docker_client.py` (`DockerService`) | Docker is deploy-specific |
| `clients/model_server_client.py` (`ModelServerClient`) | Talks to model containers |
| `handlers/model_server_handler.py` (`ModelServerHandler`) | In-memory deployment cache, secret injection, inference proxying |
| `handlers/openapi_handler.py` (`OpenAPIHandler`) | Merges per-deployment OpenAPI schemas |
| `handlers/handler_instances.py` | Singleton `ms_handler` |
| `tasks/deploy.py` (`DeployTask`) | Deploy orchestration |
| `tasks/undeploy.py` (`UndeployTask`) | Undeploy orchestration |
| `agent_api.py` (deploy routes) | `/compute`, `/deployments`, `/inference-access`, custom OpenAPI, lifespan |
| `schemas/deployments.py` (deploy-only models) | `LocalDeployment`, `InferenceAccessIn`, `InferenceAccessOut`, `DeploymentInfo`, `Healthz` |
| `_exceptions.py` | `ContainerNotFoundError`, `ContainerNotRunningError` |
| `model_server/` | Unchanged, zero coupling to agent |

## API Differences to Reconcile

### 1. Task Base Class

**Current**: `Task.__init__(self, *, platform: PlatformClient, docker: DockerService)` — both params in base class.

**Kit**: `BaseSatelliteTask` has no `__init__` params; just declares `task_type` and abstract `run()`.

**Resolution**: `DeployTask` and `UndeployTask` define their own `__init__` that accepts `platform` and `docker`. No behavior change, just where the constructor lives.

### 2. TaskHandler vs TaskDispatcher

**Current**: `TaskHandler.__init__(self, platform, docker)` — creates `DeployTask` and `UndeployTask` internally, hardcodes the handler map.

**Kit**: `TaskDispatcher.__init__(self, *, handlers: dict, platform: PlatformClient)` — receives a pre-built handler map.

**Resolution**: Build the handler map in `main.py` and pass it to `TaskDispatcher`. The dispatch logic is identical.

### 3. SatelliteManager

**Current**: Hardcodes `slug = "docker-2026.01-v1-debian12"`, reads `config.BASE_URL`, has `get_capabilities()` and `_generate_form_spec()` static methods.

**Kit**: Takes `capabilities`, `slug`, and `base_url` as constructor params.

**Resolution**: Move `get_capabilities()`, `_generate_form_spec()`, and the slug constant into `main.py` (or a local constants module). Pass them to `SatelliteManager(platform, capabilities=..., slug=..., base_url=...)`.

### 4. Settings

**Current**: `Settings` has 6 fields (4 base + `MODEL_IMAGE` + `MODEL_SERVER_PORT`).

**Kit**: `BaseSatelliteSettings` has 4 base fields.

**Resolution**: Create a local `Settings(BaseSatelliteSettings)` that adds `MODEL_IMAGE` and `MODEL_SERVER_PORT`.

### 5. App Factory

**Current**: `create_agent_app(authorize_access)` — takes an auth callback, sets up lifespan (sync_deployments), creates deploy-specific routes (`/compute`, `/deployments`, `/inference-access`), custom OpenAPI generation, security scheme.

**Kit**: `create_satellite_app(extra_routers)` — only `/healthz` + routers.

**Resolution**: Extract deploy-specific routes into an `APIRouter`. Pass the auth callback via FastAPI dependency injection. Handle lifespan in `main.py` or via the router. Pass the router to `create_satellite_app(extra_routers=[deploy_router])`.

### 6. PeriodicController

**Current**: `__init__(self, *, handler: TaskHandler, poll_interval_s: float)` — references `handler.platform` to access the platform client.

**Kit**: `__init__(self, *, handler: TaskDispatcher, poll_interval_s: float)` — same pattern, `handler.platform`.

**Resolution**: Drop-in replacement, no changes needed beyond the type.

### 7. Schemas Split

**Current**: `agent/schemas/deployments.py` has both platform API models (`Deployment`, `DeploymentUpdate`, etc.) and deploy-specific models (`LocalDeployment`, `InferenceAccessIn`, etc.).

**Kit**: Only has platform API models.

**Resolution**: Import platform models from kit. Keep `LocalDeployment`, `InferenceAccessIn`, `InferenceAccessOut`, `DeploymentInfo`, `Healthz` in a local `schemas/` module.

## Files to Delete After Migration

These modules are fully replaced by the kit:

- `agent/clients/platform_client.py`
- `agent/tasks/base.py`
- `agent/handlers/tasks.py`
- `agent/controllers/periodic.py`
- `agent/agent_manager.py`
- `agent/schemas/task.py`

## Files to Modify

- `agent/settings.py` — extend `BaseSatelliteSettings` instead of `BaseSettings`
- `agent/main.py` — change imports, build handler map explicitly, pass capabilities/slug/base_url to `SatelliteManager`
- `agent/agent_api.py` — extract deploy routes into `APIRouter`, adapt to `create_satellite_app()`
- `agent/tasks/deploy.py` — extend `BaseSatelliteTask`, own `__init__`
- `agent/tasks/undeploy.py` — extend `BaseSatelliteTask`, own `__init__`
- `agent/schemas/deployments.py` — remove models that now come from kit
- `agent/schemas/__init__.py` — re-export from kit + local models
- `agent/clients/__init__.py` — remove `PlatformClient` re-export
- `agent/handlers/__init__.py` — remove `TaskHandler` re-export
- `agent/tasks/__init__.py` — remove `Task` re-export
- `agent/controllers/__init__.py` — remove `PeriodicController` re-export (or delete the module)
- `agent/handlers/model_server_handler.py` — import `PlatformClient`, `Secret`, etc. from kit
- `pyproject.toml` — add `luml-satellite-kit` dependency, drop redundant deps

## Resulting Structure

```
satellite/
├── pyproject.toml                     # adds luml-satellite-kit dependency
├── agent/
│   ├── __init__.py
│   ├── main.py                        # wires kit components + deploy specifics
│   ├── settings.py                    # Settings(BaseSatelliteSettings) + MODEL_IMAGE, MODEL_SERVER_PORT
│   ├── agent_api.py                   # deploy-specific APIRouter + lifespan
│   ├── _exceptions.py                 # unchanged
│   ├── clients/
│   │   ├── __init__.py                # DockerService, ModelServerClient only
│   │   ├── docker_client.py           # unchanged
│   │   └── model_server_client.py     # unchanged
│   ├── handlers/
│   │   ├── __init__.py                # ModelServerHandler only
│   │   ├── handler_instances.py       # unchanged
│   │   ├── model_server_handler.py    # imports from kit
│   │   └── openapi_handler.py         # unchanged
│   ├── schemas/
│   │   ├── __init__.py                # re-exports from kit + local
│   │   └── deployments.py             # LocalDeployment, InferenceAccessIn/Out, DeploymentInfo, Healthz only
│   └── tasks/
│       ├── __init__.py                # DeployTask, UndeployTask only
│       ├── deploy.py                  # extends BaseSatelliteTask
│       └── undeploy.py                # extends BaseSatelliteTask
└── model_server/                      # unchanged
```

---

## Step-by-Step Plan

### Step 1: Add `luml-satellite-kit` as a dependency

- Add `luml-satellite-kit` as a path dependency in `satellite/pyproject.toml`
- Remove dependencies that are now transitively provided by the kit (`httpx`, `pydantic`, `pydantic-settings`, `fastapi`, `cashews`) — keep only `aiodocker` and `uvicorn` as direct deps
- Run `uv sync` to install

### Step 2: Update `agent/settings.py`

- Replace `BaseSettings` import with `BaseSatelliteSettings` from `luml_satellite_kit`
- Make `Settings` extend `BaseSatelliteSettings`
- Remove the 4 base fields (`SATELLITE_TOKEN`, `PLATFORM_URL`, `BASE_URL`, `POLL_INTERVAL_SEC`) and `model_config` — they come from the parent
- Keep only `MODEL_IMAGE` and `MODEL_SERVER_PORT`

### Step 3: Update `agent/schemas/`

- In `agent/schemas/deployments.py`: remove `Deployment`, `DeploymentUpdate`, `DeploymentStatus`, `ErrorMessage`, `Secret` (now from kit). Keep only `LocalDeployment`, `InferenceAccessIn`, `InferenceAccessOut`, `DeploymentInfo`, `Healthz`
- Delete `agent/schemas/task.py` entirely
- In `agent/schemas/__init__.py`: re-export kit schemas (`Deployment`, `DeploymentStatus`, `DeploymentUpdate`, `ErrorMessage`, `Secret`, `SatelliteQueueTask`, `SatelliteTaskStatus`, `SatelliteTaskType`) alongside local models (`LocalDeployment`, `InferenceAccessIn`, `InferenceAccessOut`, `DeploymentInfo`, `Healthz`)

### Step 4: Delete replaced framework modules

- Delete `agent/clients/platform_client.py`
- Delete `agent/tasks/base.py`
- Delete `agent/handlers/tasks.py`
- Delete `agent/controllers/periodic.py`
- Delete `agent/agent_manager.py`

### Step 5: Update `agent/clients/__init__.py`

- Remove `PlatformClient` import (now from kit)
- Keep only `DockerService` and `ModelServerClient`

### Step 6: Update `agent/tasks/`

- In `deploy.py`: change `from agent.tasks.base import Task` to `from luml_satellite_kit import BaseSatelliteTask`. Change `class DeployTask(Task)` to `class DeployTask(BaseSatelliteTask)`. Add own `__init__(self, *, platform: PlatformClient, docker: DockerService)` that stores both. Update all schema/client imports to source from kit where applicable.
- In `undeploy.py`: same changes as deploy.
- In `__init__.py`: remove `Task` export, keep `DeployTask` and `UndeployTask`.

### Step 7: Update `agent/handlers/`

- In `model_server_handler.py`: change `from agent.clients import ... PlatformClient` to `from luml_satellite_kit import PlatformClient`. Update all schema imports (`Deployment`, `DeploymentStatus`, `DeploymentUpdate`, `Secret`) to source from kit. Keep local imports for `LocalDeployment`.
- In `__init__.py`: remove `TaskHandler` export, keep `ModelServerHandler`.
- `handler_instances.py` and `openapi_handler.py`: unchanged.

### Step 8: Refactor `agent/agent_api.py`

- Extract deploy-specific routes (`/compute`, `/deployments`, `/inference-access`) and the auth dependency into an `APIRouter`
- Move lifespan (sync_deployments on startup) to either the router or `main.py`
- Keep the custom OpenAPI generation and security scheme logic attached to the router or handled in `main.py`
- The module should export a router and any lifespan setup, rather than a full app factory

### Step 9: Rewrite `agent/main.py`

- Import `create_satellite_app`, `TaskDispatcher`, `PeriodicController`, `SatelliteManager`, `PlatformClient`, `SatelliteTaskType` from `luml_satellite_kit`
- Import `DeployTask`, `UndeployTask` from local tasks
- Import `DockerService` from local clients
- Import deploy router from refactored `agent_api`
- Move capabilities dict and slug constant here (from old `SatelliteManager`)
- Build the app: `create_satellite_app(extra_routers=[deploy_router])`
- Build tasks explicitly: `deploy = DeployTask(platform=platform, docker=docker)`, same for undeploy
- Build dispatcher: `TaskDispatcher(handlers={DEPLOY: deploy, UNDEPLOY: undeploy}, platform=platform)`
- Build controller: `PeriodicController(handler=dispatcher, poll_interval_s=...)`
- Build manager: `SatelliteManager(platform, capabilities=..., slug=..., base_url=...)`
- Rest of the startup flow stays the same (uvicorn, pair, run_forever)

### Step 10: Delete empty directories / update remaining `__init__` files

- If `agent/controllers/` is now empty (after deleting `periodic.py`), delete the directory
- Clean up any remaining `__init__.py` files that reference deleted modules

### Step 11: Update imports across all remaining files

- Grep for any remaining `from agent.clients import PlatformClient` or `from agent.schemas import SatelliteTaskStatus` etc. and update to kit imports
- Grep for `from agent.handlers.tasks import TaskHandler` and remove
- Grep for `from agent.controllers import PeriodicController` and remove
- Grep for `from agent.agent_manager import SatelliteManager` and remove

### Step 12: Run linter and verify

- Run `ruff check agent/` and `ruff format agent/` to fix any import ordering or style issues
- Run `uv sync` to verify dependency resolution
- Verify the app starts correctly with `uv run python -m agent`
