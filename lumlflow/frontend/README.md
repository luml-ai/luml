# lumlflow-ui — Frontend

Vue 3 + Vite SPA for the Lumlflow local experiment tracking platform. Provides a dashboard for browsing experiment groups, inspecting metrics, traces, evaluations, and model attachments — all backed by the local Lumlflow FastAPI server.

Part of the **npm workspaces monorepo**. Shares the `@luml/experiments` and `@luml/attachments` component libraries with the main application.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Backend Setup](#backend-setup)
- [Connecting Frontend to Backend](#connecting-frontend-to-backend)
- [Environment Variables](#environment-variables)
- [Commands Reference](#commands-reference)
- [Project Structure](#project-structure)
- [Architecture Overview](#architecture-overview)

---

## Prerequisites

**Frontend:**
- **Node.js** `^22`
- **npm** (monorepo uses npm workspaces)

**Backend:**
- **Python** `>=3.12`
- **uv** — Python package manager ([install guide](https://docs.astral.sh/uv/getting-started/installation/))

---

## Getting Started

All steps below are run from the **repository root** (the monorepo root, two levels above this folder).

### 1. Install Node dependencies

```bash
npm install
```

### 2. Build the shared libraries

This app consumes `@luml/experiments` and `@luml/attachments` from their local `dist/` folders. Build them once before starting the dev server:

```bash
npm run build --workspace=extras/js/packages/experiments
npm run build --workspace=extras/js/packages/attachments
```

Rebuild only when you change source files inside those packages.

### 3. Start the backend

See [Backend Setup](#backend-setup) for full details. The short version:

```bash
cd lumlflow
uv sync
uv run lumlflow ui --no-browser
```

The backend starts on `http://127.0.0.1:5000`.

### 4. Start the frontend dev server

```bash
npm run dev --workspace=lumlflow/frontend
```

Or from inside this directory:

```bash
npm run dev
```

Vite starts on `http://localhost:5173` and proxies all `/api/*` requests to the backend at `http://localhost:5000`.

---

## Backend Setup

The Lumlflow backend is a FastAPI application located in `lumlflow/lumlflow/`. It stores experiment data in a local SQLite database and exposes a REST API consumed by this frontend.

### Install Python dependencies

From the `lumlflow/` directory:

```bash
cd lumlflow
uv venv
source .venv/bin/activate
```

`uv sync` reads `pyproject.toml` and `uv.lock`, creates a virtual environment in `.venv/`, and installs all dependencies — including the local `luml-sdk` and `luml-api` packages.

### Start the server

```bash
uv run lumlflow ui
```

This starts the FastAPI server on **`http://127.0.0.1:5000`** and opens a browser tab automatically.

#### Available CLI options

| Flag | Default | Description |
|---|---|---|
| `--port` | `5000` | Port to listen on |
| `--host` | `127.0.0.1` | Host to bind to |
| `--no-browser` | `false` | Skip auto-opening the browser |
| `--path` | `sqlite://./experiments` | Path to the SQLite experiments database |

```bash
# Examples
uv run lumlflow ui --port 8080
uv run lumlflow ui --host 0.0.0.0 --port 5000
uv run lumlflow ui --no-browser --path /data/my-experiments.db
```

### Database

The backend creates a SQLite database automatically on first run. The default location is `./experiments` (relative to where you run the command). Override it with `--path` or the `BACKEND_STORE_URI` environment variable:

```bash
# Use an absolute path
uv run lumlflow ui --path /Users/me/ml-experiments

# Or via environment variable
BACKEND_STORE_URI=/Users/me/ml-experiments uv run lumlflow ui
```

No manual migration step is needed — the schema is managed by `luml-sdk` and initialised on startup.

### Backend environment variables

Create a `.env` file in the `lumlflow/` directory (next to `pyproject.toml`):

```env
# Path to the experiments SQLite database
BACKEND_STORE_URI=/path/to/your/experiments

# Optional: LUML cloud API key (for uploading models to the cloud registry)
LUML_API_KEY=your-api-key

# Optional: override the LUML cloud endpoint
LUML_BASE_URL=https://api.luml.ai
```

---

## Connecting Frontend to Backend

### Development mode

In development the Vite dev server acts as a proxy. No extra configuration is needed — any request the frontend makes to `/api/*` is automatically forwarded to `http://localhost:5000`.

```
Browser → Vite (5173) → /api/* → FastAPI (5000)
```

The `VITE_API_URL` variable in `.env` is **not used** when the proxy is active, so you do not need to change it for local development.

### Custom backend port

If you start the backend on a port other than `5000`, update the proxy target in `vite.config.ts`:

```ts
// lumlflow/frontend/vite.config.ts
proxy: {
  '/api': {
    target: 'http://localhost:8080',  // change to match your backend port
    changeOrigin: true,
  },
},
```

### Production mode

In production the frontend is compiled and served as static files directly by the FastAPI backend — both run from a single process on a single port. The build hook in `lumlflow/hatch_build.py` automatically:

1. Builds `@luml/experiments` and `@luml/attachments`
2. Builds this frontend (`npm run build`)
3. Copies `frontend/dist/` into `lumlflow/static/`

The backend then mounts these static files and handles SPA client-side routing via a custom `SPAStaticFiles` handler.

---

## Environment Variables

Frontend variables live in `lumlflow/frontend/.env`. All are prefixed with `VITE_`.

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000/api` | Backend API base URL — **only used in production builds** (the dev proxy overrides this) |
| `VITE_LUML_URL` | `http://127.0.0.1:8000` | Base URL for the Lumlflow server — used for direct asset links |

For local development these values are irrelevant as long as the Vite proxy is configured correctly.

---

## Commands Reference

Run from inside `lumlflow/frontend/`, or append `--workspace=lumlflow/frontend` from the repo root.

### Development

| Command | What it does |
|---|---|
| `npm run dev` | Starts the Vite dev server with HMR on port `5173` |
| `npm run preview` | Serves the last production build locally |

### Building

| Command | What it does |
|---|---|
| `npm run build` | Type-checks **and** builds for production — output goes to `dist/` |
| `npm run style` | Regenerates theme CSS variables from design tokens in `tokens/` |

> `npm run build` = `vue-tsc --build` followed by `vite build` (sequential, not parallel — unlike the main app).

### Code quality

| Command | What it does |
|---|---|
| `npm run lint` | Runs ESLint with auto-fix |
| `npm run format` | Formats all files in `src/` with Prettier |
| `npm run type-check` | Runs `vue-tsc --build --force` for type checking only |

---

## Project Structure

```
lumlflow/frontend/
├── src/
│   ├── main.ts                      # App bootstrap — Vue, Pinia, Router, PrimeVue
│   ├── App.vue                      # Root component (router-view + global dialogs/toasts)
│   │
│   ├── api/                         # API client layer
│   │   ├── client.ts                # Axios instance (reads VITE_API_URL)
│   │   ├── api.service.ts           # All API methods organised by resource
│   │   ├── api.interface.ts         # Request / response TypeScript types
│   │   └── slices/
│   │       └── attachments/         # Attachments-specific API calls
│   │
│   ├── router/                      # Vue Router
│   │   ├── index.ts                 # Route definitions and guards
│   │   └── router.const.ts          # Named route constants
│   │
│   ├── store/                       # Pinia stores
│   │   ├── auth/                    # API key authentication state
│   │   ├── experiments/             # Experiments list, filters, pagination
│   │   ├── groups/                  # Experiment groups list
│   │   ├── experiment/              # Single experiment details
│   │   └── theme/                   # Light / dark theme preference
│   │
│   ├── pages/                       # Full-page route components
│   │   ├── home/                    # Home — groups dashboard
│   │   ├── experiment/              # Experiment list within a group
│   │   ├── details/                 # Experiment detail tabs
│   │   │   ├── OverviewView.vue     # Static parameters, summary
│   │   │   ├── MetricsView.vue      # Dynamic metric charts
│   │   │   ├── TracesView.vue       # LLM trace table
│   │   │   ├── EvalsView.vue        # Evaluation dataset viewer
│   │   │   └── AttachmentsView.vue  # File attachment browser
│   │   └── comparison/              # Side-by-side experiment / group comparison
│   │
│   ├── components/                  # Reusable components
│   │   ├── ui/                      # Generic presentational components
│   │   ├── layout/                  # Header, sidebar, navigation
│   │   ├── experiments/             # Experiment card, list items
│   │   ├── table/                   # Shared table utilities
│   │   ├── api-key/                 # API key setup modal
│   │   ├── theme/                   # Theme toggle button
│   │   ├── upload/                  # Model upload modal
│   │   └── card-with-dialog/        # Card + detail dialog pattern
│   │
│   ├── layouts/
│   │   └── MainTemplate.vue         # Shared app shell (header + content slot)
│   │
│   ├── hooks/                       # Vue composables
│   │   ├── useExperimentProvider.ts # Wires up @luml/experiments provider
│   │   ├── usePagination.ts         # Pagination state
│   │   └── useUpload.ts             # File upload flow
│   │
│   ├── helpers/                     # Pure utility functions
│   │   ├── colors.ts
│   │   ├── date.ts
│   │   ├── string.ts
│   │   └── errors.ts
│   │
│   ├── forms/                       # Zod schemas and form resolvers
│   ├── dialogs/                     # Standalone dialog components
│   ├── confirm/                     # Confirmation dialog helpers
│   ├── toasts/                      # Toast notification helpers
│   ├── constants/                   # Application constants
│   ├── composables/                 # Additional composition functions
│   ├── docs/                        # Markdown documentation pages
│   │
│   ├── assets/
│   │   ├── css/
│   │   │   ├── index.css            # CSS entry point
│   │   │   ├── tailwind/            # Tailwind CSS setup
│   │   │   ├── primevue/            # PrimeVue component overrides
│   │   │   ├── fonts/               # Font face definitions
│   │   │   └── theme/               # Generated light / dark CSS variables
│   │   └── img/                     # Logos and images
│   │
│   └── app/
│       └── providers/prime-vue/     # PrimeVue plugin configuration
│
├── tokens/                          # Design token source files (JSON)
│   ├── tokens-styles-light.json
│   └── tokens-styles-dark.json
├── public/                          # Static assets (served as-is)
├── dist/                            # Production build output
├── vite.config.ts                   # Vite config — proxy, aliases, Tailwind plugin
├── tsconfig.app.json                # App TypeScript config
├── eslint.config.ts                 # ESLint 9 flat config
├── .prettierrc.json                 # No semis, single quotes, 100 char width
├── style-dictionary.config.mjs      # Design token build config
└── package.json
```

### Routes

| Path | Component | Description |
|---|---|---|
| `/` | `HomePage` | Groups dashboard |
| `/experiments/:groupId` | `ExperimentPage` | Experiment list within a group |
| `/experiments/:groupId/:experimentId` | `ExperimentDetailsPage` | Experiment detail (redirects to overview) |
| `/experiments/:groupId/:experimentId` + `/metrics` | `MetricsView` | Dynamic metric charts |
| `/experiments/:groupId/:experimentId` + `/traces` | `TracesView` | LLM traces table |
| `/experiments/:groupId/:experimentId` + `/evals` | `EvalsView` | Evaluation datasets |
| `/experiments/:groupId/:experimentId` + `/attachments` | `AttachmentsView` | Model file attachments |
| `/experiments/comparison` | `ExperimentsComparison` | Side-by-side experiment comparison |
| `/groups/comparison` | `GroupsComparison` | Side-by-side group comparison |

---

## Architecture Overview

### Tech stack

| Concern | Library |
|---|---|
| Framework | Vue 3 (Composition API + `<script setup>`) |
| Build tool | Vite 6 |
| State management | Pinia 3 |
| Routing | Vue Router 4 |
| UI components | PrimeVue 4 with `@primeuix/themes` |
| CSS framework | TailwindCSS v4 |
| Icons | Lucide Vue Next |
| HTTP client | Axios |
| Schema validation | Zod 4 |
| Composition utilities | VueUse |

### Key differences from the main `frontend/` app

| | `frontend/` (main app) | `lumlflow/frontend/` |
|---|---|---|
| Theming | PrimeVue preset + Style Dictionary | TailwindCSS v4 + `tailwindcss-primeui` |
| Pinia version | `^2.2.6` | `^3.0.4` |
| Zod version | `^3.23.8` | `^4.3.6` |
| Storybook | Yes | No |
| Tests | Vitest | No test setup |
| Target | Cloud platform UI | Local experiment dashboard |

### Request flow (development)

```
Vue component
    ↓ calls api.service.ts method
Axios (src/api/client.ts)
    ↓ POST/GET /api/...
Vite dev proxy (port 5173)
    ↓ forwards to
FastAPI (port 5000) — lumlflow/lumlflow/api/
    ↓
Handler (lumlflow/lumlflow/handlers/)
    ↓
luml-sdk (SQLite database)
```

### Shared libraries

`@luml/experiments` and `@luml/attachments` are wired in via the `useExperimentProvider` composable (`src/hooks/useExperimentProvider.ts`). This hook instantiates the correct `ExperimentSnapshotApiProvider` or `ExperimentSnapshotDatabaseProvider` depending on context, and passes it to the `ExperimentSnapshot` component from `@luml/experiments`.
