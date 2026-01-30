# Satellite SDK Split Specification

Split the current `satellite/` directory into two separate components: a reusable SDK package and a model deployment satellite implementation.

## Motivation

The current satellite codebase mixes platform communication and task orchestration logic with model-deployment-specific code. Extracting the reusable parts into an SDK enables building other satellite types (e.g., batch job runners) without duplicating platform integration code.

## Components

### 1. `luml-satellite-sdk/` (new, installable package)

A new top-level directory containing a Python package that provides the foundational building blocks for any satellite implementation.

#### What moves here

- **PlatformClient** — HTTP client for communicating with the LUML backend API. Handles authentication, task fetching, status updates, satellite pairing, artifact URL retrieval, secret fetching, and inference access authorization. Includes the caching layer.
- **PeriodicController** — Async polling loop that periodically fetches pending tasks from the platform and dispatches them to handlers.
- **TaskHandler** — Dispatches tasks to the appropriate `Task` implementation based on task type. Manages the mapping of task types to handler classes.
- **Task base class** — Abstract base class defining the interface that concrete task implementations must follow.
- **SatelliteManager** — Handles satellite registration (pairing) with the platform and capability reporting.
- **Base Settings** — Pydantic Settings base class with common configuration fields: `SATELLITE_TOKEN`, `PLATFORM_URL`, `POLL_INTERVAL_SEC`. Designed to be subclassed by specific satellite implementations to add their own settings.
- **Task schemas** — `SatelliteQueueTask` model, `SatelliteTaskType` enum, `SatelliteTaskStatus` enum, and related task data structures.

#### Package structure

This is a proper Python package with its own `pyproject.toml`, installable via `uv` / `pip`. Other satellite implementations list it as a dependency.

### 2. `luml-satellite-model-deployment/` (renamed from `satellite/`, not a package)

The current `satellite/` directory gets renamed and restructured. It contains the model deployment satellite implementation that depends on `luml-satellite-sdk`.

#### What stays here

- **AgentAPI** — FastAPI application setup including the `/healthz` endpoint, authentication middleware, deployment listing, inference proxy endpoints, and OpenAPI schema serving.
- **DockerService** — `aiodocker` wrapper for creating, starting, stopping, and removing model-serving Docker containers. Includes container labeling, network configuration, and health monitoring.
- **ModelServerClient** — HTTP client for communicating with model containers (health checks, manifest retrieval, inference forwarding).
- **ModelServerHandler** — In-memory registry of active deployments. Manages deployment lifecycle, schema caching, and inference request proxying.
- **OpenAPIHandler** — Merges individual deployment OpenAPI schemas into a unified spec for the satellite's API surface.
- **DeployTask** — Concrete `Task` implementation for deploying a model: fetches deployment details, creates a Docker container, polls for health, registers the deployment, and reports status to the platform.
- **UndeployTask** — Concrete `Task` implementation for removing a deployment: stops and removes the container, cleans up the registry, and reports status.
- **Deployment schemas** — `Deployment`, `DeploymentStatus`, `LocalDeployment`, and related deployment-specific data structures.
- **Extended Settings** — Subclass of the SDK's base Settings, adding model-deployment-specific fields: `BASE_URL`, `MODEL_IMAGE`, `MODEL_SERVER_PORT`.
- **Exceptions** — `ContainerNotFoundError`, `ContainerNotRunningError`, and any other container/Docker-specific error types.
- **`model_server/` subdirectory** — The containerized model inference server code. This remains unchanged — it runs inside Docker containers, not in the satellite agent process, and includes model downloading, conda environment setup, FNNX runtime integration, and the inference FastAPI app.

#### Dependency on SDK

The model deployment satellite imports from `luml-satellite-sdk` for platform communication, task orchestration, and base configuration. It is not itself an installable package — it runs directly (e.g., via Docker or `python -m agent`).

## Migration Steps

1. Create the `luml-satellite-sdk/` directory at the repo root with its own `pyproject.toml`.
2. Move the identified SDK components from `satellite/agent/` into the SDK package, updating module paths and imports.
3. Rename `satellite/` to `luml-satellite-model-deployment/`.
4. Update `luml-satellite-model-deployment/` to import from the SDK package instead of its own internal modules for the moved components.
5. Add `luml-satellite-sdk` as a dependency in the model deployment's `pyproject.toml`.
6. Make the SDK's base Settings class extendable — the model deployment subclasses it to add its own fields.
7. Update the Dockerfile and `docker-compose.yml` to reflect the new directory name and any changed paths.
8. Update CI configuration, CLAUDE.md, and any other references to the old `satellite/` path.
9. Verify that `python -m agent` still works from within `luml-satellite-model-deployment/`.
10. Verify that the model server Docker containers still build and run correctly.

## Out of Scope

- No new features or capabilities are added.
- No changes to the backend API that the satellite communicates with.
- No changes to the `model_server/` internals.
- No changes to the SDK under `sdk/python/` (the existing LUML Python client SDK).
