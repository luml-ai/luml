# LUML — Frontend

LUML platform frontend — a Vue 3 + Vite SPA for managing the complete AI/ML lifecycle: experiment tracking, model registry, deployments, notebooks, and LLM tracing.

Part of an **npm workspaces monorepo**. The repo root contains two shared Vue component libraries (`@luml/experiments`, `@luml/attachments`) that must be built before this app can run.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Commands Reference](#commands-reference)
- [Project Structure](#project-structure)
- [Key Features & Architecture](#key-features--architecture)

---

## Prerequisites

- **Node.js** `^22`
- **npm** (the repo uses npm workspaces and a committed `package-lock.json`)

---

## Getting Started

All steps below are run from the **repository root** (one level above this folder).

### 1. Install dependencies

npm workspaces install everything in one pass — the main app, shared libraries, and all dev tooling.

```bash
npm install
```

### 2. Build the shared libraries

The app resolves `@luml/experiments` and `@luml/attachments` from local `dist/` folders. Build them once before starting the dev server:

```bash
npm run build --workspace=extras/js/packages/experiments
npm run build --workspace=extras/js/packages/attachments
```

Rebuild only when you change source files inside those packages.

### 3. Configure environment variables

Create a local env file inside this directory:

```bash
cp frontend/.env frontend/.env.local
```

Set the API URL for your target environment:

```
VITE_API_URL=https://dev-api.luml.ai
VITE_DOCS_URL=https://dev-docs.luml.ai
```

See [Environment Variables](#environment-variables) for a full reference.

### 4. Start the development server

```bash
npm run dev --workspace=frontend
```

Or, from inside the `frontend/` directory:

```bash
npm run dev
```

Vite starts with HMR on `http://localhost:5173`.

> **Jupyter proxy:** the dev server proxies `/jupyter` → `http://localhost:8000`. Run a local JupyterLite server on that port to develop the Notebooks module locally.

---

## Environment Variables

All variables are prefixed with `VITE_` so Vite includes them in the browser bundle.

| Variable | Description | Example |
|---|---|---|
| `VITE_API_URL` | Base URL for the LUML backend API | `https://dev-api.luml.ai` |
| `VITE_DOCS_URL` | URL for the documentation site | `https://dev-docs.luml.ai` |

Vite loads files in priority order: `.env.local` > `.env.[mode].local` > `.env.[mode]` > `.env`. Use `.env.local` for personal overrides (git-ignored).

---

## Commands Reference

Run these from inside `frontend/`, or append `--workspace=frontend` from the repo root.

### Development

| Command | What it does |
|---|---|
| `npm run dev` | Starts the Vite dev server with hot module replacement |
| `npm run preview` | Serves the last production build locally |
| `npm run storybook` | Opens the Storybook component explorer on port `6006` |

### Building

| Command | What it does |
|---|---|
| `npm run build` | Type-checks **and** builds for production (runs in parallel via `npm-run-all2`) |
| `npm run build-only` | Vite build only — skips TypeScript checking |
| `npm run build-storybook` | Builds a static Storybook site to `storybook-static/` |
| `npm run style` | Regenerates theme CSS variables from design tokens in `tokens/` |

> `npm run build` is equivalent to running `vue-tsc --build --force` and `vite build` concurrently.

### Code quality

| Command | What it does |
|---|---|
| `npm run lint` | Runs ESLint across the project |
| `npm run lint:fix` | Runs ESLint and auto-fixes all fixable issues |
| `npm run format` | Formats all files in `src/` with Prettier |
| `npm run format:check` | Checks formatting without writing (used in CI) |
| `npm run type-check` | Runs `vue-tsc` for type checking only |

### Testing

| Command | What it does |
|---|---|
| `npm run test` | Starts Vitest in interactive watch mode |
| `npm run test:ci` | Runs the full test suite once with jsdom (used in CI) |
| `npm run test:ui` | Opens the Vitest browser UI dashboard |

---

## Project Structure

```
frontend/
├── src/
│   ├── main.ts                  # App bootstrap — Vue, Pinia, Router, PrimeVue setup
│   ├── App.vue                  # Root component
│   │
│   ├── assets/                  # Global styles and compiled design tokens
│   │   ├── main.css             # Global styles
│   │   ├── base.css             # Base reset
│   │   ├── null.css             # Additional reset
│   │   ├── tables.css           # Table styles
│   │   └── theme/               # Generated CSS variables (output of `npm run style`)
│   │       ├── light-theme.css
│   │       └── dark-theme.css
│   │
│   ├── components/              # Reusable Vue components grouped by feature
│   │   ├── ui/                  # Primitive presentational components — no business logic
│   │   ├── layout/              # Structural parts: header, sidebar, navigation
│   │   ├── authorization/       # Auth forms and flows
│   │   ├── datasets/            # Dataset upload and management
│   │   ├── deployments/         # Deployment creation and monitoring
│   │   ├── express-tasks/       # AutoML wizard (tabular classification/regression)
│   │   │   └── tabular/
│   │   │       ├── first-step/
│   │   │       ├── second-step/
│   │   │       └── third-step/
│   │   ├── model/               # Model inspection and metadata
│   │   ├── model-upload/        # Model upload flow
│   │   ├── notebooks/           # JupyterLite notebook interface
│   │   ├── orbits/              # Orbit (project workspace) management
│   │   ├── organizations/       # Organization management
│   │   ├── prisma/              # LLM tracing and run inspection
│   │   ├── satellites/          # Compute node management
│   │   ├── predict/             # Inference/prediction UI
│   │   ├── openapi/             # OpenAPI / Scalar API reference viewer
│   │   ├── runtime/             # Runtime execution interface
│   │   ├── table/               # Base data table component
│   │   ├── table-view/          # Data table viewer with column controls
│   │   └── user/                # User profile components
│   │
│   ├── pages/                   # Full-page route components
│   │   ├── HomePage.vue
│   │   ├── SignInPage.vue
│   │   ├── SignUpPage.vue
│   │   ├── NotebooksPage.vue
│   │   ├── FlowPage.vue
│   │   ├── PrismaPage.vue
│   │   ├── RuntimePage.vue
│   │   ├── DeploymentSchemaPage.vue
│   │   ├── orbits/
│   │   ├── organization/
│   │   └── collection/
│   │
│   ├── router/                  # Vue Router — routes, lazy loading, auth middleware
│   │   ├── index.ts
│   │   ├── router.type.ts
│   │   └── middlewares/
│   │
│   ├── stores/                  # Pinia global state stores
│   │   ├── artifacts/
│   │   ├── datasets/
│   │   └── tests-orbit/
│   │
│   ├── lib/                     # Framework-level services
│   │   ├── api/                 # Axios HTTP client + per-feature endpoint modules
│   │   │   ├── api.ts           # Main Axios instance
│   │   │   ├── api.interceptors.ts
│   │   │   ├── artifacts/
│   │   │   ├── deployments/
│   │   │   ├── satellites/
│   │   │   └── ...
│   │   ├── data-processing/     # Web Worker + Pyodide/WASM data pipeline
│   │   ├── primevue/            # PrimeVue config and custom theme preset
│   │   ├── fnnx/                # FNNX AI SDK integration
│   │   ├── onnx/                # ONNX model runner (in-browser inference)
│   │   ├── bucket-service/      # Cloud storage (client-side transfers)
│   │   ├── github/              # GitHub integration
│   │   ├── apex-charts/         # ApexCharts global setup
│   │   └── tar-handler/         # TAR archive handling
│   │
│   ├── hooks/                   # Vue composable functions
│   ├── helpers/                 # Pure utility functions
│   ├── utils/                   # Form utilities, observables, service helpers
│   ├── constants/               # Application-wide constants
│   ├── workers/                 # Web Workers (experiment snapshot processing)
│   └── stories/                 # Storybook stories
│
├── public/                      # Static assets — served as-is, not processed by Vite
│   ├── *.whl                    # Python wheels for Pyodide (onnx, scikit-learn, …)
│   ├── *.wasm                   # WebAssembly binaries (SQL.js, Parquet)
│   ├── webworker.js             # Data processing Web Worker
│   └── data/                    # Sample datasets
│
├── tokens/                      # Design token source files (JSON, synced from Figma)
│   ├── tokens-styles-light.json
│   └── tokens-styles-dark.json
│
├── tests/                       # Vitest global setup
│   └── setup.ts                 # Clears mocks between test runs
│
├── .storybook/                  # Storybook configuration
│   ├── main.ts
│   └── preview.ts               # Theme decorators, router mocking
│
├── vite.config.ts               # Vite build config, dev proxy, CORS headers, aliases
├── vitest.config.ts             # Test environment, coverage, inline deps
├── tsconfig.json                # References tsconfig.app.json and tsconfig.node.json
├── tsconfig.app.json            # App TypeScript config — paths, DOM target
├── eslint.config.js             # ESLint 9 flat config
├── .prettierrc.json             # Prettier: no semis, single quotes, 100 char width
├── style-dictionary.config.mjs  # Design token build config
└── .env                         # Default environment variables (dev)
```

---

## Key Features & Architecture

### Tech stack

| Concern | Library |
|---|---|
| Framework | Vue 3 (Composition API + `<script setup>`) |
| Build tool | Vite 6 |
| State management | Pinia |
| Routing | Vue Router 4 with lazy-loaded routes |
| UI components | PrimeVue 4 with a custom theme preset |
| Icons | Lucide Vue Next |
| HTTP client | Axios with request/response interceptors |
| Charts | ApexCharts + Plotly.js |
| Flow / graph editor | Vue Flow |
| Terminal emulator | xterm.js |
| Drag-and-drop | vuedraggable |
| Schema validation | Zod |
| Composition utilities | VueUse |

### Monorepo shared libraries

Two internal packages are consumed as workspace dependencies:

- **`@luml/experiments`** — experiment snapshot viewer, metric charts, run comparison tables, parameter logging UI. Exports ESM + UMD + CSS.
- **`@luml/attachments`** — file attachment upload and management components. Exports ESM + UMD + CSS.

Both must be **built before starting the dev server** (see [Getting Started](#getting-started) step 2).

### Client-side data processing

Heavy computation runs entirely in the browser:

- **Web Workers** offload processing from the main thread.
- **Pyodide** (WebAssembly Python runtime) powers the Notebooks module — no backend execution needed.
- **SQL.js** and **Parquet-WASM** handle SQL queries and Parquet files in-browser.
- **Apache Arrow** and **Arquero** provide efficient in-memory data transformation.

Python wheels and WASM binaries are pre-bundled in `public/` and loaded on demand.

### Design tokens

CSS variables for light and dark themes are generated from JSON token files using **Style Dictionary**. Source files live in `tokens/` and are synced from Figma. To regenerate after editing them:

```bash
npm run style
```

Output is written to `src/assets/theme/light-theme.css` and `src/assets/theme/dark-theme.css`.

### API layer

All backend requests go through `src/lib/api/api.ts` (a configured Axios instance with interceptors). Feature-specific endpoint modules are organized under `src/lib/api/` by domain — `deployments/`, `satellites/`, `artifacts/`, etc. The base URL is injected at build time via `VITE_API_URL`.

### Cross-origin isolation

The dev server sets `Cross-Origin-Embedder-Policy: require-corp` and `Cross-Origin-Opener-Policy: same-origin`. These headers are required to enable `SharedArrayBuffer`, which Pyodide depends on. If you fetch cross-origin resources in development and hit CORS errors, those headers are the cause — the resource must respond with appropriate `Cross-Origin-Resource-Policy` headers.

### Linting and formatting

- **ESLint 9** flat config with `eslint-plugin-vue` (Vue 3 + TypeScript strict rules).
- **Prettier**: no semicolons, single quotes, 100-character line width.
- `dist/`, `coverage/`, `.storybook/`, and test files are excluded from linting.

### CI

Two GitHub Actions workflows trigger on `frontend/**` changes:

- **Tests and linters** — runs `lint`, `format:check`, and `test:ci` on Node 22.
- **Deployment** — triggers a DigitalOcean app deploy on pushes to `main`, `staging`, and `production`.
