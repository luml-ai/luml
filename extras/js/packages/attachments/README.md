# @luml/attachments

Vue 3 component library for browsing and previewing model attachment files. Renders a file-tree sidebar and a content preview panel that handles images, PDFs, audio/video, code, markdown, HTML, and CSV, XML, Parquet and Arrow tables. Data is loaded through a pluggable provider — a built-in TAR archive provider is included.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Commands Reference](#commands-reference)
- [Public API](#public-api)
- [Providers](#providers)
- [Supported File Types](#supported-file-types)
- [Project Structure](#project-structure)

---

## Prerequisites

- **Node.js** `^20.19.0 || >=22.12.0`
- **npm** (workspace managed from the repo root)

The workspace installs the preview library’s peer dependencies. See the [package manifest](./package.json) for the supported versions.

---

## Getting Started

### Build the library

Run from the **repository root**. The consuming app (`frontend`) resolves this package from its `dist/` folder, so it must be built before starting the dev server.

```bash
npm run build --workspace=extras/js/packages/attachments
```

### Develop with the demo app

A standalone demo app is bundled inside `src/demo/` for local development.

```bash
# From inside extras/js/packages/attachments/
npm run dev
```

### Use in the consuming app

```typescript
import { ModelAttachments, TarAttachmentsProvider } from '@luml/attachments'
import '@luml/attachments/style.css'
```

```vue
<script setup lang="ts">
import { ModelAttachments, TarAttachmentsProvider } from '@luml/attachments'

const provider = new TarAttachmentsProvider({
  downloader: myDownloader,
  fileIndex: indexData,
  findAttachmentsTarPath: (index) => index.attachments_path,
  findAttachmentsIndexPath: (index) => index.attachments_index_path,
})
await provider.init()
</script>

<template>
  <ModelAttachments :provider="provider" />
</template>
```

---

## Commands Reference

Run from inside `extras/js/packages/attachments/`, or use `--workspace=extras/js/packages/attachments` from the repo root.

| Command | What it does |
|---|---|
| `npm run dev` | Starts the Vite dev server for the demo app |
| `npm run build` | Type-checks **and** builds the library to `dist/` (parallel) |
| `npm run build-only` | Vite build only — skips TypeScript checking |
| `npm run preview` | Serves the last demo build locally |
| `npm run type-check` | Runs `vue-tsc` for type checking only |
| `npm test` | Runs SVG preview regression tests (requires `npx playwright install chromium`) |
| `npm run lint` | Runs ESLint with auto-fix |
| `npm run format` | Formats `src/` with Prettier |
| `npm run style` | Regenerates demo theme CSS variables from design tokens in `tokens/` |

> `npm run build` runs `vue-tsc --build` and `vite build` concurrently via `npm-run-all2`.

### Build outputs

```
dist/
├── luml-attachments.es.js     # ES module — for bundlers
├── luml-attachments.umd.js    # UMD — for browser globals
├── attachments.css            # Bundled component styles
└── index.d.ts                 # TypeScript declarations entry
```

Import styles separately: `import '@luml/attachments/style.css'`

Enable sourcemaps by setting `LUML_BUILD_SOURCEMAP=1` before building.

---

## Public API

The browser-global UMD script includes its table-reading helpers and uses Apache Arrow from the `Arrow` peer global.

### Components

#### `ModelAttachments`

The root component. Renders a two-panel layout: a collapsible file-tree on the left and a content preview panel on the right.

```vue
<ModelAttachments :provider="provider" />
```

| Prop | Type | Description |
|---|---|---|
| `provider` | `ModelAttachmentsProvider` | Data source — see [Providers](#providers) |

#### `FilePreview`

Use the preview body on its own with a URL or a browser `Blob`. Supply the byte size when available so the preview can reject oversized files before loading them.

```vue
<FilePreview :file-name="file.name" :file-size="file.size" :source="contentUrl" />
```

Parquet URLs must support HTTP byte ranges. An indexed archive can supply a range reader with `byteLength` and `slice(start, end)` instead. For audio, video and PDF, pass a streamable URL. For a lazy source that returns a streaming URL or range reader, set `supportsPartialPreview` to allow large previews. Providers declare the same capability per path. For a dataset chunk, `totalRows` can supply the split's total row count.

### Interfaces

#### `ModelAttachmentsProvider`

The interface your provider must implement:

```typescript
interface ModelAttachmentsProvider {
  getTree(): FileNode[]
  supportsPartialPreview?(path: string): boolean
  getPreviewSource?(path: string, size?: number): PreviewSource | Promise<PreviewSource>
  getAttachmentContent(path: string): Promise<AttachmentContent>
  isEmpty(): boolean
}
```

#### `FileNode`

Represents a file or folder in the tree:

```typescript
interface FileNode {
  name: string
  path?: string
  type: 'file' | 'folder'
  size?: number
  children?: FileNode[]
}
```

#### `AttachmentContent`

Returned by `getAttachmentContent`:

```typescript
interface AttachmentContent {
  blob: Blob
  size: number
}
```

## Providers

### `TarAttachmentsProvider`

Built-in provider that extracts files from a TAR archive. Receives a downloader callback and index data, then lazily fetches file content on demand.

```typescript
import { TarAttachmentsProvider } from '@luml/attachments'

const provider = new TarAttachmentsProvider({
  downloader: myDownloader,         // async (path: string) => ArrayBuffer
  fileIndex: indexData,             // parsed index object
  findAttachmentsTarPath: (index) => index.tar_path,
  findAttachmentsIndexPath: (index) => index.index_path,
})
await provider.init()
```

#### `TarAttachmentsProviderConfig`

| Field | Type | Description |
|---|---|---|
| `downloader` | `(path: string) => Promise<ArrayBuffer>` | Fetches raw bytes for a given path |
| `fileIndex` | `any` | Parsed index object (format is model-specific) |
| `findAttachmentsTarPath` | `(index: any) => string` | Extracts the TAR file path from the index |
| `findAttachmentsIndexPath` | `(index: any) => string` | Extracts the file listing path from the index |

### Custom provider

Implement `ModelAttachmentsProvider` to load files from any source (S3, IndexedDB, memory, etc.):

```typescript
import type { ModelAttachmentsProvider, FileNode, AttachmentContent } from '@luml/attachments'

class MyProvider implements ModelAttachmentsProvider {
  getTree(): FileNode[] {
    return [{ name: 'model.json', type: 'file', size: 1024 }]
  }

  async getAttachmentContent(path: string): Promise<AttachmentContent> {
    const blob = await fetchFile(path)
    return { blob, size: blob.size }
  }

  isEmpty(): boolean {
    return false
  }
}
```

---

## Supported File Types

| Category | Extensions | Preview method |
|---|---|---|
| Images | `png`, `jpg`, `jpeg`, `gif`, `webp` | `<img>` tag |
| SVG | `svg` | `<img>` tag (scripting disabled) |
| Audio | `mp3`, `wav`, `ogg` | Native `<audio>` controls |
| Video | `mp4`, `webm`, `ogv` | Native `<video>` controls |
| PDF | `pdf` | `<iframe>` embed |
| HTML | `html` | Sandboxed `<iframe>` |
| Code | `py`, `js`, `jsx`, `ts`, `tsx`, `css`, `sql`, `toml`, `ini`, `cfg`, `sh` | Read-only CodeMirror |
| Text | `txt`, `log` | Plain text |
| Markdown | `md` | Rendered or raw |
| Structured text | `json`, `yaml`, `yml` | Pretty or raw |
| Table | `csv`, `xml`, `parquet`, `arrow` | PrimeVue DataTable with pagination |

The **10 MB** limit applies to buffered previews. Audio, video and PDF can stream by URL. Parquet reads byte ranges. Parquet and Arrow tables show the first 1,000 rows. Unrecognised extensions show an "unsupported format" state.

---

## Project Structure

```
extras/js/packages/attachments/
├── src/
│   ├── index.ts                       # Public API barrel
│   ├── ModelAttachments.vue           # Root component
│   ├── components/
│   │   ├── FileTree.vue               # Left sidebar — collapsible file tree
│   │   ├── FileNode.vue               # Recursive folder/file node with icons
│   │   ├── FilePreview.vue            # Right panel — routes to format-specific previews
│   │   └── preview/
│   │       ├── FilePreviewHeader.vue  # File name, size, copy path, download button
│   │       └── PreviewStates.vue      # Loading / error / empty / too-big states
│   ├── hooks/                         # Vue composable functions
│   ├── interfaces/                    # All TypeScript types
│   ├── models/
│   │   └── TarAttachmentsProvider.ts  # Built-in TAR archive provider
│   ├── utils/
│   │   ├── fileTypes.ts               # Extension → type mapping, size formatting
│   │   └── fileContentProcessors.ts   # Blob processing per file type
│   └── demo/                          # Standalone demo app (not published)
├── tokens/                            # Design token JSON files
├── dist/                              # Build output
├── vite.config.ts
├── tsconfig.app.json
├── tsconfig.build.json
├── style-dictionary.config.mjs
└── package.json
```
