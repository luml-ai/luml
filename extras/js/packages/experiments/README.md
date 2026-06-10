# @luml/experiments

Vue 3 component library for visualizing and analysing ML experiment snapshots. Provides evaluation tables, trace inspection, dynamic metric charts, annotation management, and multi-model comparison — all driven through a pluggable data-source provider.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Commands Reference](#commands-reference)
- [Public API](#public-api)
- [Providers](#providers)
- [Project Structure](#project-structure)

---

## Prerequisites

- **Node.js** `^20.19.0 || >=22.12.0`
- **npm** (workspace managed from the repo root)

**Peer dependencies** — must be installed in the consuming application:

| Package | Version |
|---|---|
| `vue` | `^3.5.12` |
| `primevue` | `^4.4.1` |
| `@primevue/themes` | `^4.3.9` |
| `pinia` | `>=2.2.6` |
| `@vueuse/core` | `^14.2.1` |
| `plotly.js-dist` | `^3.0.3` |
| `sql.js` | `^1.13.0` |
| `arquero` | `^7.2.1` |
| `lucide-vue-next` | `^0.460.0` |
| `marked` | `^16.2.0` |
| `dompurify` | `^3.2.7` |
| `github-markdown-css` | `^5.8.1` |
| `jszip` | `^3.10.1` |
| `uuid` | `^14.0.0` |

---

## Getting Started

### Build the library

Run from the **repository root**. The consuming app (`frontend`) resolves this package from its `dist/` folder, so it must be built before starting the dev server.

```bash
npm run build --workspace=extras/js/packages/experiments
```

### Develop with the demo app

A standalone demo app is bundled inside `src/demo/` for local development.

```bash
# From inside extras/js/packages/experiments/
npm run dev
```

### Use in the consuming app

```typescript
import { ExperimentSnapshot, ExperimentSnapshotApiProvider } from '@luml/experiments'
import '@luml/experiments/style.css'
```

```vue
<script setup lang="ts">
import { ExperimentSnapshot, ExperimentSnapshotApiProvider } from '@luml/experiments'

const provider = new ExperimentSnapshotApiProvider(myApiService)
await provider.init({ artifacts: [...] })
</script>

<template>
  <ExperimentSnapshot
    :provider="provider"
    :models-ids="['model-a', 'model-b']"
    :models-info="{ 'model-a': { name: 'Model A', color: '#6366f1' } }"
    theme="light"
  />
</template>
```

---

## Commands Reference

Run from inside `extras/js/packages/experiments/`, or use `--workspace=extras/js/packages/experiments` from the repo root.

| Command | What it does |
|---|---|
| `npm run dev` | Starts the Vite dev server for the demo app |
| `npm run build` | Type-checks **and** builds the library to `dist/` (parallel) |
| `npm run build-only` | Vite build only — skips TypeScript checking |
| `npm run preview` | Serves the last demo build locally |
| `npm run type-check` | Runs `vue-tsc` for type checking only |
| `npm run lint` | Runs ESLint with auto-fix |
| `npm run format` | Formats `src/` with Prettier |
| `npm run style` | Regenerates demo theme CSS variables from design tokens in `tokens/` |

> `npm run build` runs `vue-tsc --build` and `vite build` concurrently via `npm-run-all2`.

### Build outputs

```
dist/
├── luml-experiments.es.js     # ES module — for bundlers
├── luml-experiments.umd.js    # UMD — for browser globals
├── experiments.css            # Bundled component styles
├── index.d.ts                 # TypeScript declarations entry
└── sql-wasm.wasm              # SQL.js WebAssembly binary
```

Import styles separately: `import '@luml/experiments/style.css'`

Enable sourcemaps by setting `LUML_BUILD_SOURCEMAP=1` before building.

---

## Public API

### Components

| Component | Props | Description |
|---|---|---|
| `ExperimentSnapshot` | `provider`, `modelsIds`, `modelsInfo`, `theme` | Root orchestrator — mounts the full UI |
| `ComparisonHeader` | — | Header bar for multi-model comparison view |
| `ComparisonModelsList` | — | List of models in the active comparison |
| `EvalsDatasetsList` | `modelsInfo`, `loaderHeight` | Browsable list of evaluation datasets |
| `DynamicMetrics` | `metricsNames`, `modelsInfo` | Plotly metric charts per training run |
| `TracesWrapper` | `artifactId`, `showEmptyTable` | Trace table with search and pagination |
| `TracesDialog` | — | Modal showing traces for a selected eval row |
| `TraceDialog` | — | Span hierarchy viewer for a single trace |

#### `ExperimentSnapshot` props

| Prop | Type | Description |
|---|---|---|
| `provider` | `ExperimentSnapshotProvider` | Data source — see [Providers](#providers) |
| `modelsIds` | `string[]` | IDs of the models/runs to display |
| `modelsInfo` | `ModelsInfo` | Display names and colors keyed by model ID |
| `theme` | `'light' \| 'dark'` | Visual theme |

### Composables

#### `useEvalsTable(evals, search, datasetId, visibleColumns, filters)`

Manages the evaluation data table: sorting, column visibility, CSV export.

```typescript
const { data, sortParams, onSort, exportCSV, exportLoading, selectedColumns, setSelectedColumns } =
  useEvalsTable(evals, search, datasetId, visibleColumns, filters)
```

#### `useTracesTable(traces, selectedColumns, requestParams)`

Manages the traces table: column visibility, CSV export.

```typescript
const { data, exportCSV, exportLoading } = useTracesTable(traces, selectedColumns, requestParams)
```

### Pinia stores

All stores must be used inside a component tree where Pinia is installed.

| Store | Key state | Key methods |
|---|---|---|
| `useEvalsStore()` | `datasets`, `currentEvalData`, `loading` | `setProvider()`, `initDatasets()`, `initDataset()`, `refresh()` |
| `useTraceStore()` | `traces`, `requestParams`, `loading` | `getNextPage()`, `setRequestParams()`, `refresh()` |
| `useDynamicMetricsStore()` | `metrics`, `metricsNames`, `page` | `setMetricsNames()`, `setPage()`, `refresh()`, `reset()` |
| `useAnnotationsStore()` | `evalAnnotations`, `spanAnnotations` | `addEvalAnnotation()`, `updateEvalAnnotation()`, `deleteEvalAnnotation()` |

### Utilities

| Export | Description |
|---|---|
| `provideTheme(theme)` | Injects the active light/dark theme into the component tree |

---

## Providers

Providers are the data layer. Pass a provider instance to `ExperimentSnapshot` (or directly to a store) to control where data comes from.

### `ExperimentSnapshotApiProvider`

Fetches data from the LUML HTTP API. Use this in the main application.

```typescript
import { ExperimentSnapshotApiProvider } from '@luml/experiments'

const provider = new ExperimentSnapshotApiProvider(apiService)
await provider.init({ artifacts: [artifact1, artifact2] })
```

### `ExperimentSnapshotDatabaseProvider`

Queries a local SQL.js in-memory database. Use this when the snapshot is loaded from a `.db` file uploaded by the user.

```typescript
import { ExperimentSnapshotDatabaseProvider } from '@luml/experiments'

const provider = new ExperimentSnapshotDatabaseProvider()
await provider.init({ buffer: arrayBuffer })
```

### `ExperimentSnapshotWorkerProxy`

Proxies provider calls to a Web Worker to keep the main thread free. Wrap any provider with this when processing large datasets.

```typescript
import { ExperimentSnapshotWorkerProxy } from '@luml/experiments'

const proxy = new ExperimentSnapshotWorkerProxy(worker)
await proxy.init(initData)
```

### Custom provider

Implement the `ExperimentSnapshotProvider` interface to connect any data source:

```typescript
import type { ExperimentSnapshotProvider } from '@luml/experiments'

class MyProvider implements ExperimentSnapshotProvider {
  async init(data: any) { /* ... */ }
  async getDynamicMetricsNames(signal?: AbortSignal) { return [] }
  async getEvalsColumns(datasetId: string, signal?: AbortSignal) { /* ... */ }
  // ... implement remaining interface methods
}
```

---

## Project Structure

```
extras/js/packages/experiments/
├── src/
│   ├── index.ts                      # Public API barrel
│   ├── ExperimentSnapshot.vue        # Root component
│   ├── interfaces/
│   │   └── interfaces.ts             # Core type definitions
│   ├── components/
│   │   ├── ui/                       # Generic presentational primitives
│   │   ├── evals/                    # Evaluation table, dataset list, feedback
│   │   │   ├── traces/               # Trace dialogs and span tree
│   │   │   └── scores/               # Score columns (single / multiple model)
│   │   ├── traces/                   # Standalone traces table and toolbar
│   │   ├── annotations/              # Add, edit, view annotations
│   │   ├── dynamic-metrics/          # Plotly metric charts
│   │   ├── static-parameters/        # Static parameter tables
│   │   ├── comparison/               # Multi-model comparison header/list
│   │   └── table/                    # Shared table utilities (filters, column editor)
│   ├── store/                        # Pinia stores
│   │   ├── evals/
│   │   ├── trace/
│   │   ├── dynamic-metrics/
│   │   └── annotations.ts
│   ├── providers/                    # Data source implementations
│   │   ├── ExperimentSnapshotApiProvider.ts
│   │   ├── ExperimentSnapshotDatabaseProvider.ts
│   │   ├── ExperimentSnapshotWorkerProxy.ts
│   │   └── ExperimentSnapshotApiProvider.interface.ts
│   ├── hooks/                        # Vue composables
│   ├── helpers/                      # Pure utility functions
│   ├── services/
│   │   └── PlotlyService.ts          # Plotly chart configuration
│   ├── lib/
│   │   ├── theme/ThemeProvider.ts
│   │   └── plotly/                   # Layout definitions
│   ├── constants/                    # Colors, column names
│   ├── utils/                        # Search, exception helpers
│   └── demo/                         # Standalone demo app (not published)
├── tokens/                           # Design token JSON files
│   ├── tokens-styles-light.json
│   └── tokens-styles-dark.json
├── dist/                             # Build output
├── vite.config.ts
├── tsconfig.app.json
├── tsconfig.build.json
├── style-dictionary.config.mjs
└── package.json
```
