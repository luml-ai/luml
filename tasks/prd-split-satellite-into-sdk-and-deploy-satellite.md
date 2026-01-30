# PRD: Split Satellite into SDK and Deploy Satellite

## Overview
The current satellite implementation is tightly coupled to model deployment functionality. This PRD defines the split of the satellite codebase into two packages:
1. **luml-satellite-sdk** - A reusable SDK for building any type of satellite worker
2. **satellites/deploy** - The model deployment satellite that uses the SDK

This is a pure refactoring effort with no new features. The goal is to enable future satellites (e.g., training, data processing) to reuse the common infrastructure.

## Goals
- Extract common satellite infrastructure into a standalone, publishable SDK
- Maintain exact current functionality after the split
- Enable future satellite development using the SDK
- Keep the SDK minimal and focused on core abstractions

## Quality Gates

These commands must pass for every user story:
- `cd luml-satellite-sdk && uv run ruff format --check . && uv run ruff check . && uv run mypy .`
- `cd satellites/deploy && uv run ruff format --check . && uv run ruff check . && uv run mypy .`

## User Stories

### US-001: Create luml-satellite-sdk package structure
As a developer, I want the SDK package scaffolded with proper Python packaging so that it can be installed as an independent dependency.

**Acceptance Criteria:**
- [ ] Create `luml-satellite-sdk/` directory in monorepo root
- [ ] Create `pyproject.toml` with package metadata (name: `luml-satellite-sdk`)
- [ ] Create `src/luml_satellite_sdk/` source directory (src layout)
- [ ] Create `__init__.py` with version and public exports
- [ ] Create `py.typed` marker for type checking support
- [ ] Package is installable via `uv pip install -e ./luml-satellite-sdk`

### US-002: Extract base abstractions to SDK
As a developer, I want abstract base classes in the SDK so that satellites can implement their specific behavior.

**Acceptance Criteria:**
- [ ] Create `src/luml_satellite_sdk/base.py` with `BaseSatellite` abstract class
- [ ] Create `src/luml_satellite_sdk/task.py` with `BaseTask` abstract class
- [ ] Create `src/luml_satellite_sdk/client.py` with `BasePlatformClient` abstract class
- [ ] `BaseSatellite` defines abstract methods: `start()`, `stop()`, `register_capabilities()`
- [ ] `BaseTask` defines abstract methods: `execute()`, `get_task_type()`
- [ ] `BasePlatformClient` defines abstract methods for API communication
- [ ] All abstract classes use Python's `abc.ABC` and `@abstractmethod`

### US-003: Move PlatformClient to SDK
As a developer, I want the platform client in the SDK so that all satellites can communicate with the LUML backend.

**Acceptance Criteria:**
- [ ] Move `PlatformClient` class from `satellite/` to `luml-satellite-sdk/src/luml_satellite_sdk/client.py`
- [ ] `PlatformClient` extends `BasePlatformClient` with concrete implementations
- [ ] HTTP methods for task polling, status updates, secrets retrieval are preserved
- [ ] Authentication logic (API key, satellite ID) is preserved
- [ ] Export `PlatformClient` from SDK's `__init__.py`

### US-004: Move PeriodicController to SDK
As a developer, I want the polling controller in the SDK so that satellites can use the same polling pattern.

**Acceptance Criteria:**
- [ ] Move `PeriodicController` class to `luml-satellite-sdk/src/luml_satellite_sdk/controller.py`
- [ ] Preserve the async polling loop logic
- [ ] Preserve configurable polling interval
- [ ] Export `PeriodicController` from SDK's `__init__.py`

### US-005: Move TaskHandler and task registry to SDK
As a developer, I want the task dispatcher in the SDK so that satellites can register and dispatch their task types.

**Acceptance Criteria:**
- [ ] Move `TaskHandler` class to `luml-satellite-sdk/src/luml_satellite_sdk/handler.py`
- [ ] Preserve task type registry pattern
- [ ] Preserve task dispatch logic
- [ ] Make task registry configurable (satellites pass their task mappings)
- [ ] Export `TaskHandler` from SDK's `__init__.py`

### US-006: Move SatelliteManager pairing logic to SDK
As a developer, I want satellite pairing in the SDK so that all satellites can pair with orbits.

**Acceptance Criteria:**
- [ ] Move `SatelliteManager` to `luml-satellite-sdk/src/luml_satellite_sdk/manager.py`
- [ ] Preserve pairing flow with LUML backend
- [ ] Add `register_capabilities(capabilities: list)` method that satellites call
- [ ] Capability list is passed by the satellite, not hardcoded
- [ ] Export `SatelliteManager` from SDK's `__init__.py`

### US-007: Move base Settings class to SDK
As a developer, I want base configuration in the SDK so that satellites extend it with their specific settings.

**Acceptance Criteria:**
- [ ] Create `luml-satellite-sdk/src/luml_satellite_sdk/settings.py` with `BaseSettings` class
- [ ] Include common settings: `api_url`, `api_key`, `satellite_id`, `polling_interval`
- [ ] Use Pydantic Settings for environment variable loading
- [ ] Export `BaseSettings` from SDK's `__init__.py`

### US-008: Move common schemas to SDK
As a developer, I want shared schemas in the SDK so that all satellites use consistent data models.

**Acceptance Criteria:**
- [ ] Create `luml-satellite-sdk/src/luml_satellite_sdk/schemas.py`
- [ ] Move `SatelliteQueueTask` schema
- [ ] Move `SatelliteTaskType` enum (as base, extensible by satellites)
- [ ] Move `SatelliteTaskStatus` enum
- [ ] Move any other shared Pydantic models used in API communication
- [ ] Export schemas from SDK's `__init__.py`

### US-009: Move exception classes to SDK
As a developer, I want common exceptions in the SDK so that error handling is consistent.

**Acceptance Criteria:**
- [ ] Create `luml-satellite-sdk/src/luml_satellite_sdk/exceptions.py`
- [ ] Move `SatelliteException` base class
- [ ] Move `PairingException`, `TaskException`, and other common exceptions
- [ ] Export exceptions from SDK's `__init__.py`

### US-010: Create satellites/deploy directory structure
As a developer, I want the deploy satellite in its own package so that it's separate from the SDK.

**Acceptance Criteria:**
- [ ] Create `satellites/deploy/` directory
- [ ] Create `pyproject.toml` with dependency on `luml-satellite-sdk`
- [ ] Create `src/deploy_satellite/` source directory
- [ ] Create `__init__.py` with version
- [ ] Dependency on SDK uses path: `luml-satellite-sdk = {path = "../../luml-satellite-sdk"}`

### US-011: Move Docker service to deploy satellite
As a developer, I want Docker management in the deploy satellite since it's deployment-specific.

**Acceptance Criteria:**
- [ ] Move `DockerService` class to `satellites/deploy/src/deploy_satellite/docker.py`
- [ ] Preserve all container lifecycle methods (create, start, stop, remove)
- [ ] Preserve aiodocker usage
- [ ] Update imports to use SDK base classes where applicable

### US-012: Move deployment tasks to deploy satellite
As a developer, I want deployment task implementations in the deploy satellite.

**Acceptance Criteria:**
- [ ] Move `DeployTask` to `satellites/deploy/src/deploy_satellite/tasks/deploy.py`
- [ ] Move `UndeployTask` to `satellites/deploy/src/deploy_satellite/tasks/undeploy.py`
- [ ] Tasks extend `BaseTask` from SDK
- [ ] Tasks implement `execute()` and `get_task_type()` methods
- [ ] Create `satellites/deploy/src/deploy_satellite/tasks/__init__.py` with exports

### US-013: Move model server components to deploy satellite
As a developer, I want model server handling in the deploy satellite since it's deployment-specific.

**Acceptance Criteria:**
- [ ] Move `ModelServerHandler` to `satellites/deploy/src/deploy_satellite/model_server/handler.py`
- [ ] Move `ModelServerClient` to `satellites/deploy/src/deploy_satellite/model_server/client.py`
- [ ] Move entire `model_server/` directory structure
- [ ] Preserve all inference proxying logic
- [ ] Update imports appropriately

### US-014: Move agent API to deploy satellite
As a developer, I want the FastAPI app in the deploy satellite since it exposes deployment-specific endpoints.

**Acceptance Criteria:**
- [ ] Move `agent_api.py` to `satellites/deploy/src/deploy_satellite/api.py`
- [ ] Preserve all FastAPI routes for inference
- [ ] Move `OpenAPIHandler` to deploy satellite
- [ ] Update imports to use SDK for base functionality

### US-015: Create deploy satellite Settings class
As a developer, I want deploy-specific settings that extend the SDK base settings.

**Acceptance Criteria:**
- [ ] Create `satellites/deploy/src/deploy_satellite/settings.py`
- [ ] Create `DeploySettings` class extending SDK's `BaseSettings`
- [ ] Add deployment-specific settings (Docker config, model server config, etc.)
- [ ] Preserve all existing environment variable names for backwards compatibility

### US-016: Create deploy satellite main entry point
As a developer, I want a main entry point that wires everything together.

**Acceptance Criteria:**
- [ ] Create `satellites/deploy/src/deploy_satellite/__main__.py`
- [ ] Instantiate SDK components (PlatformClient, PeriodicController, TaskHandler)
- [ ] Register deploy and undeploy tasks with TaskHandler
- [ ] Register deployment capabilities via SatelliteManager
- [ ] Preserve `python -m deploy_satellite` as the run command
- [ ] Current `python -m agent` command should map to new structure

### US-017: Move and split tests
As a developer, I want tests organized by package so that each package is independently testable.

**Acceptance Criteria:**
- [ ] Create `luml-satellite-sdk/tests/` directory
- [ ] Move tests for SDK components (client, controller, handler, manager) to SDK tests
- [ ] Create `satellites/deploy/tests/` directory
- [ ] Move tests for deployment components (docker, tasks, model server) to deploy tests
- [ ] Both test suites pass independently
- [ ] Update any test fixtures and mocks for new import paths

### US-018: Update CI configuration
As a developer, I want CI to test both packages so that quality is maintained.

**Acceptance Criteria:**
- [ ] Update CI workflow to run SDK quality checks
- [ ] Update CI workflow to run deploy satellite quality checks
- [ ] Both packages must pass formatting, linting, and type checking
- [ ] Tests run for both packages

### US-019: Remove old satellite directory
As a developer, I want the old satellite directory cleaned up after migration.

**Acceptance Criteria:**
- [ ] Verify all code has been migrated to SDK or deploy satellite
- [ ] Verify all tests pass in new locations
- [ ] Remove `satellite/` directory
- [ ] Update any documentation references to new paths
- [ ] Update root-level scripts or configs that reference old path

## Functional Requirements
- FR-1: The SDK must be installable as a standalone Python package
- FR-2: The SDK must provide abstract base classes for Satellite, Task, and PlatformClient
- FR-3: The SDK must provide concrete implementations for PlatformClient, PeriodicController, TaskHandler, and SatelliteManager
- FR-4: The deploy satellite must depend on the SDK as an external package
- FR-5: The deploy satellite must implement BaseTask for deploy and undeploy operations
- FR-6: The deploy satellite must register its capabilities (model deployment) via SDK's SatelliteManager
- FR-7: All existing functionality must work identically after the split
- FR-8: Environment variables and configuration must remain backwards compatible

## Non-Goals
- Adding new features to the satellite
- Changing the API contract with the LUML backend
- Publishing the SDK to PyPI (just structure for future publishing)
- Creating additional satellite types (future work)
- Modifying the backend to support the split

## Technical Considerations
- Use Python src layout for both packages (`src/package_name/`)
- SDK should have minimal dependencies (httpx, pydantic, pydantic-settings)
- Deploy satellite adds aiodocker and FastAPI dependencies
- Abstract classes should use Python's `abc` module
- Maintain Python 3.14 compatibility as per project standards
- Use `uv` for dependency management in both packages

## Success Metrics
- All existing satellite tests pass after migration
- Quality gates pass for both packages (ruff format, ruff check, mypy)
- Deploy satellite functions identically to current satellite
- SDK can be installed independently without deploy satellite code

## Open Questions
- Should we add a `satellites/` entry to the root `pyproject.toml` workspace configuration?
- Should the SDK include any async utilities beyond what's currently in satellite?