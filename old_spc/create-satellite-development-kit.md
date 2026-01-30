# Satellite Development Kit (SDK) Specification

## Overview

Extract the platform communication layer from the satellite into a separate Python library (`luml-satellite-sdk`) that enables developers to build custom workers for the LUML platform. The current satellite will be refactored to use this SDK while retaining its Docker/model-serving logic.

## Package Details

| Attribute | Value |
|-----------|-------|
| **Package name** | `luml-satellite-sdk` |
| **Location** | `/satellite-sdk/` folder in monorepo |
| **Python version** | 3.12+ |
| **HTTP client** | httpx |
| **Versioning** | Independent semver (not locked to platform) |

## Architecture Decisions

### Core Model
- **Single orbit binding**: One SDK instance connects to one orbit (1:1 relationship)
- **Polling transport**: HTTP polling only (no WebSocket/SSE). Configurable interval via `LUML_POLL_INTERVAL_SEC`
- **Blocking execution**: SDK executes one task at a time; handler blocks until complete
- **Sync-default**: Handlers are sync functions by default; async handlers supported as opt-in

### Task System
- **Platform-first registration**: Task types must exist in the platform before workers can handle them
- **Config-based capabilities**: Developer lists supported task types in SDK config; reported on connect
- **Platform handles claiming**: Platform uses atomic claim (first worker to poll gets task); SDK just polls
- **No crash recovery**: If a worker crashes mid-task, the task stays in 'processing' state (manual intervention required)
- **No timeout enforcement**: SDK doesn't enforce task timeouts; developers handle this in their handlers

### Authentication
- **Static token**: Long-lived `LUML_SATELLITE_TOKEN`; worker crashes on 401
- **SDK handles pairing**: SDK provides `pair(code)` method to exchange pairing code for token
- **Lazy validation**: No startup token validation; first poll will fail if token is invalid

### Error Handling
- **Report & continue**: SDK catches handler exceptions, reports failure to platform, continues polling
- **Simple fail**: Reports 'failed' with error message string; no error categorization
- **Exponential backoff**: On network failures/5xx, SDK retries with exponential backoff (1s, 2s, 4s... up to configurable max)

### Shutdown
- **Immediate stop**: On SIGTERM/SIGINT, cancel in-flight tasks immediately and exit

## Public API

### Entry Point (Functional Module Style)

```python
from luml_satellite_sdk import handler, run, pair, get_client

# Optional: Pairing flow (if no token exists)
# token = pair(code="ABC123", platform_url="https://api.luml.ai")

@handler("deploy")
def handle_deploy(task_id: str, payload: dict, client: PlatformClient) -> None:
    """Handler receives task_id, payload dict, and full platform client."""
    deployment = client.get_deployment(payload["deployment_id"])
    # ... do work ...
    client.update_task_status(task_id, "completed")

@handler("batch_inference")
def handle_batch(task_id: str, payload: BatchPayload, client: PlatformClient) -> None:
    """Payload can be Pydantic model (SDK validates) or dict."""
    pass

# Async handlers also supported
@handler("async_task")
async def handle_async(task_id: str, payload: dict, client: PlatformClient) -> None:
    pass

if __name__ == "__main__":
    run()  # Starts polling loop, health server
```

### Configuration (Pydantic Settings)

```python
from pydantic_settings import BaseSettings

class SatelliteSDKSettings(BaseSettings):
    """All settings auto-load from env vars with LUML_ prefix."""

    model_config = {"env_prefix": "LUML_"}

    # Required
    satellite_token: str

    # Platform
    platform_url: str = "https://api.luml.ai"

    # Polling
    poll_interval_sec: int = 2
    max_backoff_sec: int = 60

    # Capabilities
    supported_task_types: list[str] = []

    # Health server
    health_port: int = 8080
    health_enabled: bool = True

    # Base URL (reported to platform)
    base_url: str | None = None
```

Environment variables:
- `LUML_SATELLITE_TOKEN` (required)
- `LUML_PLATFORM_URL`
- `LUML_POLL_INTERVAL_SEC`
- `LUML_SUPPORTED_TASK_TYPES` (comma-separated)
- `LUML_HEALTH_PORT`
- `LUML_HEALTH_ENABLED`
- `LUML_BASE_URL`

### Platform Client (Extensible Base)

```python
class PlatformClient:
    """Core endpoints built-in; developer can extend for additional endpoints."""

    # Built-in task endpoints
    def poll_tasks(self) -> list[Task]: ...
    def claim_task(self, task_id: str) -> bool: ...
    def update_task_status(self, task_id: str, status: str, message: str = "") -> None: ...

    # Built-in secrets
    def fetch_secrets(self, deployment_id: str) -> dict[str, str]: ...

    # Built-in pairing
    def pair(self, code: str) -> str: ...  # Returns token

    # Built-in deployment info (commonly needed)
    def get_deployment(self, deployment_id: str) -> Deployment: ...

    # Extensibility - raw HTTP methods
    def get(self, path: str, **kwargs) -> httpx.Response: ...
    def post(self, path: str, **kwargs) -> httpx.Response: ...
    def put(self, path: str, **kwargs) -> httpx.Response: ...
    def delete(self, path: str, **kwargs) -> httpx.Response: ...
```

### Payload Typing (Optional Pydantic)

```python
from pydantic import BaseModel

class DeployPayload(BaseModel):
    deployment_id: str
    model_id: str
    artifact_url: str

# SDK validates payload against model if type hint is Pydantic
@handler("deploy")
def handle_deploy(task_id: str, payload: DeployPayload, client: PlatformClient) -> None:
    print(payload.deployment_id)  # Type-safe access

# dict also works - no validation
@handler("flexible")
def handle_flexible(task_id: str, payload: dict, client: PlatformClient) -> None:
    print(payload["whatever"])
```

### Health Server

Built-in lightweight HTTP server (default port 8080):

- `GET /healthz` - Returns 200 if SDK is running
- `GET /readyz` - Returns 200 if SDK is connected and polling

No Prometheus metrics (out of scope).

### Testing Utilities

```python
# luml_satellite_sdk.testing module
from luml_satellite_sdk.testing import MockPlatformClient, mock_task

def test_my_handler():
    client = MockPlatformClient()
    client.add_task(mock_task(
        task_id="test-1",
        task_type="deploy",
        payload={"deployment_id": "dep-123"}
    ))

    handle_deploy("test-1", {"deployment_id": "dep-123"}, client)

    assert client.task_statuses["test-1"] == "completed"
```

## Logging

- Uses Python standard `logging` module
- Logger name: `luml_satellite_sdk`
- Sensible defaults (INFO level, includes task_id in records)
- Debug level logging for empty polls (visible only if DEBUG enabled)
- Developer configures their own handlers/formatters

## Optional Extras

Install with `pip install luml-satellite-sdk[extras]` for utility helpers:

```python
from luml_satellite_sdk.extras import (
    download_file,      # Download from presigned URL with progress
    temp_directory,     # Context manager for temp dirs with cleanup
    retry,              # Retry decorator with backoff
)
```

Core SDK has no dependency on extras.

## Folder Structure

```
satellite-sdk/
├── pyproject.toml
├── README.md
├── src/
│   └── luml_satellite_sdk/
│       ├── __init__.py          # Public API: handler, run, pair, get_client
│       ├── sdk.py               # Core SDK class, polling loop
│       ├── client.py            # PlatformClient implementation
│       ├── config.py            # Pydantic Settings
│       ├── handlers.py          # Handler registry, decorator
│       ├── health.py            # Health server (built-in HTTP)
│       ├── pairing.py           # Pairing flow
│       ├── models.py            # Task, Deployment Pydantic models
│       ├── testing/
│       │   ├── __init__.py
│       │   └── mocks.py         # MockPlatformClient, fixtures
│       └── extras/              # Optional utilities
│           ├── __init__.py
│           ├── download.py
│           ├── tempdir.py
│           └── retry.py
└── tests/
    ├── test_sdk.py
    ├── test_client.py
    └── test_handlers.py
```

## Satellite Refactoring

After SDK extraction, the satellite becomes a **feature layer**:

```
satellite/
├── agent/
│   ├── main.py              # Uses SDK: @handler decorators, run()
│   ├── handlers/
│   │   ├── deploy.py        # DeployTask logic (Docker management)
│   │   └── undeploy.py      # UndeployTask logic
│   └── docker_client.py     # DockerService (aiodocker wrapper)
├── model_server/            # Unchanged - stays satellite-specific
└── ...
```

The satellite:
- Imports `luml-satellite-sdk`
- Registers `deploy` and `undeploy` handlers
- Keeps all Docker container management logic
- Keeps `model_server/` entirely (not part of SDK)

### Migration

- **Clean break**: Satellite v2 requires SDK; no backwards compatibility
- Satellite v1 code can be archived/tagged before refactoring
- No adapter layer or gradual migration

## Documentation

- **README.md**: Comprehensive with installation, quick start, configuration, examples
- **Docstrings**: Detailed docstrings on all public APIs for IDE autocomplete
- No dedicated docs site initially

## What's NOT Included

| Feature | Reason |
|---------|--------|
| WebSocket/SSE transport | Polling is simpler, works through all firewalls |
| CLI tool | Developers write their own entrypoints |
| Prometheus metrics | Keeps SDK minimal; developers instrument manually |
| Crash recovery / heartbeating | Platform handles task state; manual intervention for stuck tasks |
| Task timeout enforcement | Developers handle timeouts in their handlers |
| Strict typing / py.typed | Not a priority; types added opportunistically |
| Multi-orbit support | One SDK instance = one orbit |
| Token refresh | Static tokens; worker crashes on 401 |
| Concurrency control | Blocking execution; developers manage their own if needed |

## API Versioning

- **Graceful degradation**: SDK ignores unknown fields in responses; fails gracefully on missing endpoints
- Changelog documents platform API compatibility matrix
- SDK version independent of platform version

## Dependencies

### Core
- `httpx` - HTTP client
- `pydantic` - Payload validation, models
- `pydantic-settings` - Configuration

### Extras (optional)
- TBD based on utility implementations

### Dev
- `pytest` - Testing
- `ruff` - Linting/formatting

