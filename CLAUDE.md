# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LUML is an open-source MLOps/LLMOps platform for building, managing, and deploying AI/ML models. The codebase is organized as a monorepo with four main components: backend (FastAPI), frontend (Vue 3), satellite (worker agent), and SDK (Python client).

## Build/Test/Lint Commands

### Backend (Python - FastAPI)
```bash
cd backend
uv venv && source .venv/bin/activate && uv sync
uvicorn luml.server:app --reload           # Run dev server
uv run ruff format --check luml migrations tests utils  # Format check
uv run ruff check luml migrations tests utils           # Lint
uv run mypy luml                                        # Type check
uv run pytest                                           # Run tests
uv run pytest tests/unit/test_file.py::test_name       # Single test
alembic upgrade head                                    # Apply migrations
```

### Frontend (Vue 3 + TypeScript)
```bash
cd frontend
npm install
npm run dev              # Vite dev server (localhost:5173)
npm run build            # Production build
npm run type-check       # vue-tsc
npm run lint             # ESLint
npm run format:check     # Prettier check
npm run test:ci          # Vitest tests
npm run storybook        # Component stories
```

### Satellite (Worker Agent)
```bash
cd satellite
uv venv && source .venv/bin/activate && uv sync
python -m agent          # Run satellite agent
uv run pytest            # Run tests
```

### SDK
```bash
cd sdk/python
uv venv && source .venv/bin/activate && uv sync
uv run pytest            # Run tests
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vue 3)     │   Backend (FastAPI)                 │
│  - Pinia state        │   - JWT auth                        │
│  - PrimeVue UI        │◄──│   - SQLAlchemy async ORM        │
│  - TypeScript         │   - Storage (S3/Azure)              │
└───────────┬───────────┴───────────────┬─────────────────────┘
            │                           │
            │       ┌───────────────────┴────────────┐
            └──────►│   Satellite (Worker Agent)     │
                    │   - Docker management          │
                    │   - Model serving              │
                    └────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────┐
│  Database (PostgreSQL 18)  │  Storage (S3/MinIO/Azure)      │
└─────────────────────────────────────────────────────────────┘
```

### Backend Structure (`backend/luml/`)
- **api/**: Route handlers (FastAPI routers)
- **handlers/**: Business logic layer
- **repositories/**: Data access layer (SQLAlchemy queries)
- **models/**: SQLAlchemy ORM models
- **schemas/**: Pydantic request/response models
- **infra/**: Database connection, security, middleware
- **clients/**: External service clients (S3, Azure, OAuth)

### Frontend Structure (`frontend/src/`)
- **pages/**: Vue route components
- **components/**: Reusable components (feature-based folders)
- **stores/**: Pinia state stores (auth, orbits, deployments, etc.)
- **lib/api/**: Axios API client modules
- **hooks/**: Vue composables

### Key Domain Concepts
- **Orbit**: A workspace that can contain multiple collections (currently model artifacts, expanding later)
- **Collection**: Container for related items within an orbit (e.g., model artifacts)
- **Satellite**: Worker agent attached to a single orbit, handles model deployment tasks
- **Model Artifact**: Trained model file stored in bucket

## Tech Stack

**Backend**: FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 18, Alembic, Pydantic, uv (Python 3.14)

**Frontend**: Vue 3, TypeScript, Vite, Pinia, PrimeVue, Axios, Vitest (Node 22)

**Satellite**: FastAPI, aiodocker, Pydantic Settings

**SDK**: Pydantic, Httpx, FNNX

## Database Migrations

Create a new migration after modifying SQLAlchemy models:
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Code Quality

**Backend**: Ruff (format + lint) and Mypy (strict) must pass. Line length 88.

**Frontend**: ESLint and Prettier (100 char width, single quotes, no semicolons) must pass.

CI runs these checks on all PRs to main.
