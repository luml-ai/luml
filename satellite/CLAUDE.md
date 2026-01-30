# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

The Satellite is a general-purpose external worker agent for the LUML platform. It connects to the platform API, polls for tasks, and executes them locally. Currently it handles model deployments (managing Docker containers running model servers), but the architecture supports any job type—batch processing, data pipelines, etc.

## Build/Run Commands

```bash
# Setup
uv venv && source .venv/bin/activate && uv sync

# Run agent locally
python -m agent

# Lint and format
uv run ruff format --check agent
uv run ruff check agent

# Build Docker images
docker compose build

# Run with Docker Compose (requires .env with SATELLITE_TOKEN)
docker compose up
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Satellite Agent                             │
│  agent/main.py                                                  │
│  ├── PlatformClient: communicates with LUML backend API         │
│  ├── DockerService: manages model containers via aiodocker      │
│  ├── PeriodicController: polls for tasks at POLL_INTERVAL_SEC   │
│  └── SatelliteManager: handles pairing with platform            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ spawns
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                  Model Server Container (per deployment)         │
│  model_server/                                                   │
│  ├── ModelHandler: downloads & extracts model artifacts          │
│  ├── CondaLikeEnvManager: creates conda env from model's env.json│
│  └── ModelCondaManager: runs model in isolated conda environment │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Structure (`agent/`)
- **main.py**: Entry point, orchestrates startup and polling loop
- **agent_manager.py**: SatelliteManager handles pairing and capability reporting
- **clients/platform_client.py**: HTTP client for LUML backend API (tasks, deployments, secrets)
- **clients/docker_client.py**: DockerService wrapper for aiodocker operations
- **tasks/deploy.py**: DeployTask handles container creation, health checks, and status updates
- **tasks/undeploy.py**: UndeployTask handles container removal and cleanup
- **handlers/model_server_handler.py**: Proxies requests to running model containers
- **controllers/periodic.py**: PeriodicController polls platform for pending tasks

### Model Server Structure (`model_server/`)
- **main.py**: Entry point for model server container
- **handlers/model_handler.py**: Downloads model artifacts, creates conda environments
- **conda_manager.py** / **conda_worker.py**: Manages model execution in isolated conda env
- **openapi_generator.py**: Generates OpenAPI schemas from model dtypes

## Key Flows

**Deployment Flow:**
1. Agent polls platform for tasks with status `pending`
2. DeployTask fetches deployment details and presigned artifact URL
3. Creates Docker container with `sat-{deployment_id}` name
4. Container downloads model, creates conda env, starts serving
5. Agent polls container `/healthz` endpoint until healthy
6. Agent reports success with inference URL to platform

**Container Naming:** All model containers are named `sat-{deployment_id}` and labeled with `df.deployment_id` and `df.model_id`.

## Configuration

Environment variables (see `.env.example`):
- `SATELLITE_TOKEN` (required): Bearer token for platform API auth
- `PLATFORM_URL`: Backend API URL (default: https://api.luml.ai)
- `BASE_URL`: Public URL of this satellite (reported to platform)
- `MODEL_IMAGE`: Docker image for model server (default: df-random-svc:latest)
- `POLL_INTERVAL_SEC`: Task polling interval (default: 2)

## Code Quality

Ruff format and lint with line-length 100. Type annotations required (ANN rules enabled, except for `*args`/`**kwargs`).
