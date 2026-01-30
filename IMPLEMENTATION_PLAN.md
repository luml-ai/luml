

# Satellite Development Kit (SDK) Implementation Plan

## Project Overview

Extract the platform communication layer from the existing satellite (`/satellite/`) into a standalone Python library (`luml-satellite-sdk`) located at `/satellite-sdk/`. This SDK will enable developers to build custom workers for the LUML platform while the existing satellite continues to handle Docker-based model deployments.

**Package Name:** `luml-satellite-sdk`
**Python Version:** 3.12+
**Key Dependencies:** httpx, pydantic, pydantic-settings

---

## Implementation Items

### Phase 1: SDK Package Foundation

- [X] Create `/satellite-sdk/` directory structure
  ```
  satellite-sdk/
  ├── pyproject.toml
  ├── README.md
  ├── src/
  │   └── luml_satellite_sdk/
  │       ├── __init__.py
  │       ├── py.typed
  │       ├── client/
  │       ├── config/
  │       ├── handlers/
  │       ├── health/
  │       ├── polling/
  │       ├── schemas/
  │       ├── testing/
  │       └── utils/
  └── tests/
  ```

- [ ] Create `/satellite-sdk/pyproject.toml` with:
  - Package metadata (name: `luml-satellite-sdk`)
  - Dependencies: httpx, pydantic, pydantic-settings
  - Optional extras: `[dev]` for testing tools (pytest, respx, pytest-asyncio)
  - Build system configuration (hatchling or setuptools)
  - Ruff and mypy configuration matching existing SDK patterns

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/__init__.py` with public API exports


---

### Phase 2: SDK Core - Configuration

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/config/settings.py`
  - Pydantic Settings class with environment variable support
  - Settings: `SATELLITE_TOKEN`, `PLATFORM_URL`, `POLL_INTERVAL`, `HEALTH_PORT`
  - Use `LUML_` prefix for environment variables (matching existing SDK)
  - Reference: `/satellite/agent/settings.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/config/__init__.py`

---

### Phase 3: SDK Core - Schemas

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/schemas/task.py`
  - `TaskStatus` enum (QUEUED, IN_PROGRESS, COMPLETED, FAILED)
  - `TaskType` base (extensible for custom types)
  - `SatelliteTask` Pydantic model
  - `TaskResult` model for handler responses
  - Reference: `/satellite/agent/schemas/task.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/schemas/deployment.py`
  - `DeploymentStatus` enum
  - `Deployment` Pydantic model
  - `DeploymentUpdate` model
  - Reference: `/satellite/agent/schemas/deployments.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/schemas/satellite.py`
  - `SatelliteCapability` model
  - `SatellitePairRequest` and `SatellitePairResponse` models
  - Reference: `/satellite/agent/agent_manager.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/schemas/artifact.py`
  - `ModelArtifact` Pydantic model
  - `ModelArtifactDownloadUrl` model
  - Reference: `/satellite/agent/clients/platform_client.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/schemas/secret.py`
  - `OrbitSecret` Pydantic model
  - Reference: `/satellite/agent/clients/platform_client.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/schemas/__init__.py` with all exports

---

### Phase 4: SDK Core - Exceptions

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/exceptions.py`
  - `SatelliteSDKError` base exception
  - `PlatformConnectionError` for network issues
  - `PlatformAPIError` for API error responses
  - `PairingError` for satellite pairing failures
  - `TaskExecutionError` for handler failures
  - `ConfigurationError` for invalid settings
  - Reference: `/sdk/python/src/luml/_exceptions.py`

---

### Phase 5: SDK Core - Platform Client

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/client/base.py`
  - Abstract base class `BasePlatformClient`
  - Define interface for all platform operations
  - Reference: `/sdk/python/src/luml/_base.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/client/sync_client.py`
  - `PlatformClient` synchronous implementation using httpx
  - Methods:
    - `pair(capabilities: list[SatelliteCapability]) -> SatellitePairResponse`
    - `get_tasks() -> list[SatelliteTask]`
    - `update_task_status(task_id: str, status: TaskStatus, result: dict | None)`
    - `get_deployments() -> list[Deployment]`
    - `get_deployment(deployment_id: str) -> Deployment`
    - `update_deployment(deployment_id: str, update: DeploymentUpdate)`
    - `delete_deployment(deployment_id: str)`
    - `get_model_artifact(artifact_id: str) -> ModelArtifact`
    - `get_model_artifact_download_url(artifact_id: str) -> str`
    - `get_secrets() -> list[OrbitSecret]`
    - `get_secret(key: str) -> OrbitSecret`
    - `authorize_inference_access(deployment_id: str, token: str) -> bool`
  - Reference: `/satellite/agent/clients/platform_client.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/client/async_client.py`
  - `AsyncPlatformClient` async implementation using httpx.AsyncClient
  - Same methods as sync client but async
  - Reference: `/sdk/python/src/luml/_async_client.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/client/__init__.py`

---

### Phase 6: SDK Core - Handler System

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/handlers/registry.py`
  - `HandlerRegistry` class to store task type → handler mappings
  - `register(task_type: str)` method
  - `get_handler(task_type: str)` method
  - `list_capabilities() -> list[SatelliteCapability]`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/handlers/decorator.py`
  - `@handler("task_type")` decorator implementation
  - Decorator registers function with global registry
  - Supports both sync and async handlers
  - Handler signature: `(task: SatelliteTask, client: PlatformClient) -> TaskResult`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/handlers/context.py`
  - `TaskContext` class providing utilities to handlers
  - Properties: `task`, `client`, `settings`
  - Methods: `download_file()`, `temp_directory()`, `get_secret()`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/handlers/__init__.py`

---

### Phase 7: SDK Core - Polling Loop

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/polling/loop.py`
  - `PollingLoop` class implementing task polling
  - Configurable poll interval (default: 5 seconds)
  - Single task execution (blocking)
  - Automatic task status updates (IN_PROGRESS → COMPLETED/FAILED)
  - Graceful shutdown handling (SIGINT, SIGTERM)
  - Error handling with optional retry
  - Reference: `/satellite/agent/controllers/periodic.py`

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/polling/__init__.py`

---

### Phase 8: SDK Core - Health Server

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/health/server.py`
  - Lightweight HTTP server (using httpx or built-in http.server)
  - Endpoints:
    - `GET /healthz` - Liveness probe (always 200)
    - `GET /readyz` - Readiness probe (200 if paired and polling)
  - Configurable port (default: 8080)
  - Runs in background thread

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/health/__init__.py`

---

### Phase 9: SDK Core - Worker Class

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/worker.py`
  - Main `Worker` class that ties everything together
  - Constructor: `Worker(settings: Settings | None = None)`
  - Methods:
    - `register_handler(task_type: str, handler: Callable)` - manual registration
    - `start()` - pairs with platform, starts polling loop and health server
    - `stop()` - graceful shutdown
  - Auto-discovers handlers decorated with `@handler`
  - Example usage:
    ```python
    from luml_satellite_sdk import Worker, handler

    @handler("my_task")
    def handle_my_task(task, client):
        return {"status": "done"}

    worker = Worker()
    worker.start()
    ```

---

### Phase 10: SDK Utilities (Optional Extras)

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/utils/download.py`
  - `download_file(url: str, dest: Path) -> Path` utility
  - Progress callback support
  - Resume support for large files

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/utils/temp.py`
  - `temp_directory()` context manager
  - Auto-cleanup on exit

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/utils/retry.py`
  - `@retry(max_attempts, backoff)` decorator
  - Configurable retry strategies

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/utils/__init__.py`

---

### Phase 11: SDK Testing Utilities

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/testing/__init__.py`
  - `MockPlatformClient` class for unit testing handlers
  - Pre-configured responses for common operations
  - Assertion helpers for verifying API calls

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/testing/fixtures.py`
  - Pytest fixtures for common test scenarios
  - `mock_platform_client` fixture
  - `sample_task` fixture
  - `sample_deployment` fixture

- [ ] Create `/satellite-sdk/src/luml_satellite_sdk/testing/factories.py`
  - Factory functions for creating test data
  - `create_task()`, `create_deployment()`, etc.

---

### Phase 12: SDK Tests

- [ ] Create `/satellite-sdk/tests/__init__.py`

- [ ] Create `/satellite-sdk/tests/conftest.py`
  - Shared pytest fixtures
  - respx mock setup

- [ ] Create `/satellite-sdk/tests/unit/test_client.py`
  - Tests for PlatformClient (sync and async)
  - Mock HTTP responses with respx
  - Reference: `/sdk/python/tests/`

- [ ] Create `/satellite-sdk/tests/unit/test_handlers.py`
  - Tests for handler decorator
  - Tests for handler registry
  - Tests for TaskContext

- [ ] Create `/satellite-sdk/tests/unit/test_polling.py`
  - Tests for PollingLoop
  - Verify task execution flow

- [ ] Create `/satellite-sdk/tests/unit/test_health.py`
  - Tests for health server endpoints

- [ ] Create `/satellite-sdk/tests/unit/test_worker.py`
  - Integration tests for Worker class

- [ ] Create `/satellite-sdk/tests/unit/test_schemas.py`
  - Pydantic model validation tests

---

### Phase 13: Satellite Refactoring

**Dependencies:** Phases 1-9 must be complete

- [ ] Add `luml-satellite-sdk` as dependency in `/satellite/pyproject.toml`

- [ ] Refactor `/satellite/agent/clients/platform_client.py`
  - Import `PlatformClient` from `luml_satellite_sdk`
  - Remove duplicated code, keep only satellite-specific extensions if any
  - Or replace entirely with SDK client

- [ ] Refactor `/satellite/agent/agent_manager.py`
  - Use SDK's `Worker` or `PlatformClient` for pairing
  - Delegate capability registration to SDK

- [ ] Refactor `/satellite/agent/controllers/periodic.py`
  - Use SDK's `PollingLoop` or keep custom implementation
  - Integrate with SDK's handler system

- [ ] Convert existing task handlers to use `@handler` decorator
  - `/satellite/agent/tasks/deploy.py` → `@handler("deploy")`
  - `/satellite/agent/tasks/undeploy.py` → `@handler("undeploy")`

- [ ] Update `/satellite/agent/settings.py`
  - Import and extend SDK's Settings class
  - Add satellite-specific settings (Docker, model server)

- [ ] Update satellite imports throughout codebase
  - Grep for old imports and update to SDK imports

- [ ] Run satellite tests and fix any breaking changes
  - `/satellite/tests/`

---

### Phase 14: Documentation

- [ ] Create `/satellite-sdk/README.md`
  - Quick start guide
  - Installation instructions
  - Basic usage example
  - Link to full documentation

- [ ] Create `/satellite-sdk/docs/` directory

- [ ] Create `/satellite-sdk/docs/getting-started.md`
  - Detailed setup instructions
  - Environment variable reference
  - First worker tutorial

- [ ] Create `/satellite-sdk/docs/handlers.md`
  - Handler decorator usage
  - TaskContext API
  - Error handling

- [ ] Create `/satellite-sdk/docs/client.md`
  - PlatformClient API reference
  - Sync vs Async usage
  - All available methods

- [ ] Create `/satellite-sdk/docs/testing.md`
  - MockPlatformClient usage
  - Pytest fixtures
  - Example test patterns

- [ ] Create `/satellite-sdk/docs/examples/` directory with example workers

- [ ] Update `/satellite/README.md` to reference SDK

---

### Phase 15: CI/CD Integration

- [ ] Add satellite-sdk to CI workflow
  - Lint (ruff)
  - Type check (mypy)
  - Tests (pytest)
  - Reference: existing backend/frontend CI

- [ ] Add satellite-sdk build step
  - Build wheel
  - Verify package structure

- [ ] Configure package publishing (if applicable)
  - PyPI or private registry

---

## Dependencies Graph

```
Phase 1 (Foundation)
    ↓
Phase 2-4 (Config, Schemas, Exceptions) [parallel]
    ↓
Phase 5 (Platform Client) - depends on schemas, exceptions
    ↓
Phase 6-8 (Handlers, Polling, Health) [parallel] - depend on client
    ↓
Phase 9 (Worker) - depends on all above
    ↓
Phase 10-12 (Utils, Testing, Tests) [parallel]
    ↓
Phase 13 (Satellite Refactoring) - depends on Phase 9
    ↓
Phase 14-15 (Docs, CI) [parallel]
```

---

## Key Files Reference

### Files to Create (New SDK)
| Path | Purpose |
|------|---------|
| `/satellite-sdk/pyproject.toml` | Package configuration |
| `/satellite-sdk/src/luml_satellite_sdk/worker.py` | Main Worker class |
| `/satellite-sdk/src/luml_satellite_sdk/client/sync_client.py` | Sync platform client |
| `/satellite-sdk/src/luml_satellite_sdk/client/async_client.py` | Async platform client |
| `/satellite-sdk/src/luml_satellite_sdk/handlers/decorator.py` | @handler decorator |
| `/satellite-sdk/src/luml_satellite_sdk/polling/loop.py` | Task polling loop |
| `/satellite-sdk/src/luml_satellite_sdk/health/server.py` | Health endpoints |
| `/satellite-sdk/src/luml_satellite_sdk/testing/__init__.py` | MockPlatformClient |

### Files to Modify (Existing Satellite)
| Path | Change |
|------|--------|
| `/satellite/pyproject.toml` | Add SDK dependency |
| `/satellite/agent/clients/platform_client.py` | Replace with SDK import |
| `/satellite/agent/agent_manager.py` | Use SDK components |
| `/satellite/agent/controllers/periodic.py` | Use SDK polling |
| `/satellite/agent/tasks/deploy.py` | Add @handler decorator |
| `/satellite/agent/tasks/undeploy.py` | Add @handler decorator |
| `/satellite/agent/settings.py` | Extend SDK settings |

### Files to Reference (Patterns)
| Path | Pattern |
|------|---------|
| `/sdk/python/src/luml/_client.py` | Sync client structure |
| `/sdk/python/src/luml/_async_client.py` | Async client structure |
| `/sdk/python/src/luml/_exceptions.py` | Exception hierarchy |
| `/sdk/python/pyproject.toml` | Package configuration |
| `/satellite/agent/schemas/task.py` | Task schema definitions |

---

## Notes

1. **Backward Compatibility:** The refactored satellite must maintain full backward compatibility with existing deployments.

2. **Testing Strategy:** Each phase should include tests before moving to the next phase.

3. **Incremental Rollout:** The satellite refactoring (Phase 13) can be done incrementally, one component at a time.

4. **Known Gaps:** The backend currently lacks batch task operations and task cancellation - these can be added later as SDK extensions.
