# Proposals

## Problem

A data scientist working in Flow keeps data, plots, reports and code next to the flows in
the project folder. The Workspace page lists only notebooks (`.flow` directories) and
folders: `workspace.list` skips plain files (`lumlflow/lumlflow/flow/daemon/workspace.py`,
`list_directory`), and the frontend has a dead `type: 'file'` branch in
`WorkspaceFolderItem.vue` that nothing fills. To look at a file the person has to leave
Flow.

Flow can already preview files: the Attachments tab of an experiment uses the shared
`@luml/attachments` package. The Workspace page does not use it.

This spec follows a product proposal and a UI design approved on 2026-11-17. Both are
internal; everything needed to build the feature is in this file, and the approved screens
are in `codie/design/LM-1113/` (see Frontend). Codes in brackets (`B-#`, `TQ-#`, `S-#`) are
the proposal's item numbers, kept only for traceability.

## Solution (at a glance)

- `workspace.list` also returns plain files (name, size, modified time); a **Show hidden**
  toggle reveals dot entries and the excluded folders (TQ-10). Clicking a file opens a
  preview next to the listing (B-01, B-04).
- The preview is the `@luml/attachments` preview, exported as a standalone component and
  extended once for all places (Workspace, Flow's Attachments tab, LUML's Attachments
  tab): Parquet tables (B-06), syntax highlighting (B-12), Rendered / Raw and Pretty / Raw
  toggles (B-13), more file types (B-02). A file it can't preview shows name, size and date
  (B-05).
- `.luml` files get their own view: manifest as YAML and the archive's files; experiment →
  **Open in Experiments** (read-only, rendered from the archive) and **Upload experiment to
  LUML**; model → **Upload model to LUML**; dataset (tabular and Hugging Face) → data as a
  table, one tab per subset / split, and **Upload dataset to LUML** (B-09, B-10, B-11).
- New daemon RPC methods: rename, move, delete (permanent), new folder, new file (B-14),
  and read / write text with a conflict check (B-15). They work wherever the Workspace
  page can browse. Operations that touch an open notebook ask to close it first.
- A file watcher on the listed folder and the open file locks a file that changes while an
  agent session is active, read-only in the editor until 180 s after its last change
  (B-15, TQ-7).
- Everything stays local; the only network calls are the explicit LUML uploads (B-08).

## Why this approach

- **One preview package.** B-02, B-06, B-12 and B-13 ask for the same behaviour in the
  Workspace and the Attachments tabs, so the work goes into `@luml/attachments` once.
- **Daemon RPC, same transport as flows.** File operations sit next to `flow.rename` /
  `flow.delete` in `Api` and go over `POST /api/flow/rpc` (and the socket). Raw bytes go
  over a plain HTTP `GET`, because previews need blobs and media need range requests.
- **Operations follow what the person can browse.** The Workspace page already navigates
  the whole disk (breadcrumb `WorkspacePath.vue`, `canGoUp` in the workspace store); limiting
  operations to the start folder would show files the person can't touch. The approved
  proposal limited operations to the project root (B-14); this spec lifts that limit.
- **Lock rule modelled on cell claims.** Same idle time (`CLAIM_IDLE_S`), colours and
  "held by" wording as cells. A file watcher is the only way to see agent writes, because
  agents write files through their own shell, not through the daemon (TQ-7).
- **Experiment view from the archive.** The `.luml` experiment holds `exp.db.zip` and its
  attachments, so the view needs no import into the local tracker (TQ-4, closed). The main
  LUML frontend already renders experiments from archives in the browser.

## Out of scope (this version)

- Linking files to the cells that read or produce them (`S-08`); rename, move and
  delete only warn (TQ-6).
- Marking which files an agent changed, beyond the editor lock (`S-09`).
- "Create a cell that loads this file" (`S-10`).
- File operations as MCP tools; moving files to the system Trash.
- Editing binary files, notebooks (`.flow`) or files inside a `.luml` archive.
- Paging a dataset beyond the first chunk of a split.
- Narrow-screen layout with a file open (not designed yet).

# Design

## Architecture overview

```
WorkspacesPage ─► workspace store ─► POST /api/flow/rpc ─► Api (daemon)
     │                               workspace.list {hidden}        ├─ workspace.py helpers
     │                               file.* / flow.move / flow.*    ├─ Hub (sessions)
     │                               file.inspect / file.publish    └─ ArtifactHandler.upload_file
     │
     ├─► WorkspaceFileViewer ─► GET /api/flow/file?path=…            (bytes, Range)
     │                          GET /api/flow/file/entry?path=…&entry=…   (one tar member)
     │
     └─► WS /api/flow/stream {"subscribe":"files", directory, file} ◄─ FileWatch
                              files_changed / file_locks frames
```

Daemon code: `lumlflow/lumlflow/flow/daemon/`. Flow frontend: `lumlflow/frontend/src/`.
Shared preview: `extras/js/packages/attachments/`.

## 1. Paths (every new method and endpoint)

- New helper `Api._file_path(params, key="path") -> Path`: requires an absolute path,
  expands it, resolves the **parent** and keeps the last component as given, so a symlink
  stays the link itself; requires it to exist (`os.path.lexists`; except for targets of
  create). No root confinement: the boundary is what the daemon's OS user can access, the
  same as browsing today.
- **Symlinks:** listed as their target's kind (file or folder) with `is_link: true`;
  previews and `file.read_text` / `file.write_text` read and write the target. Rename,
  move and delete act on the link only (`unlink` for a link to a folder, never
  `rmtree` through it). A broken link is listed as a file with `size: null` and shows the
  no-preview card (Frontend §1).
- **OS errors** (`PermissionError`, read-only filesystem, disk full, …) are returned as kind
  `OsError` with the OS message (e.g. "Permission denied"); the frontend shows an error
  toast. Writes are atomic; a failed cross-filesystem `file.move` removes the partial copy
  and leaves the source in place.
- New names (`name` params) must be one path component: not empty, no `/` or `\`, not `.`
  or `..`. Reuse the checks in `Hub._new_flow_ref`.
- Refused for the `file.*` methods with kind `NotAFile`: a `.flow` directory or a path
  inside one (notebooks go through `flow.*`), and anything inside `.lumlflow`.
- Refused for rename / move / delete with kind `Protected`: the filesystem root, the
  user's home directory itself, and the folder `lumlflow ui` runs in (`Api.directory`)
  itself. Their contents are not protected.
- Errors use the existing `{"error": {message, kind}}` shape of `/api/flow/rpc`; the
  frontend maps `kind` to a toast.

## 2. Listing (`workspace.list`, extended; TQ-10)

- Params: `{directory?, hidden?: bool = false, offset?: int = 0, limit?: int = 2000}`.
- `list_directory(root, hidden)` also collects plain files (`entry.is_file()`), with
  `size` (bytes) and `modified` (ISO 8601, from `st_mtime`, UTC). Folders gain `modified`.
- `hidden = false` (default): skip names starting with `.` and names in `EXCLUDED_DIRS`
  (`flow/dsl/tree.py`), for files and folders. `.gitignore` is not applied.
  `hidden = true`: list everything except `.lumlflow`.
- **Paging (big folders):** entries are ordered as the UI shows them (flows, then
  folders, then files; each by name, case-insensitive) and the page is
  `[offset, offset + limit)` of that order. `limit` is capped at 2000.
- Response: `{directory, flows, folders: [{name, path, modified}], files: [{name, path,
  size: int | null, modified, is_link}], total: int, next_offset: int | null}` (folders
  also carry `is_link`) (`next_offset` is `null` on the
  last page).
- Frontend: `WorkspaceListing` gains `files`, `total`, `next_offset`; the store maps files
  to `type: 'file'` items (`ITEM_TYPE_ORDER` already has `file`). When `next_offset` is set,
  the listing ends with "Showing {n} of {total} items" and **Show more**, which loads the
  next page and appends it. A refresh (`files_changed`, an operation) reloads the pages
  already shown. **Show hidden** toggle in the listing header, remembered in `localStorage`
  (`lumlflow.workspace.showHidden`). Empty text becomes "This directory is empty".

## 3. Reading files

- **`GET /api/flow/file?path=<abs>`** (`web.py`, token as for `/api/flow/download`):
  `_file_path` checks, must be a regular file, then Starlette `FileResponse` with a guessed
  media type and `Content-Disposition: inline`. `FileResponse` serves `Range` requests, so
  audio, video, PDF and Parquet can be read partially.
- **`GET /api/flow/file/entry?path=<abs .luml>&entry=<member>`**: streams one member of a
  `.luml` tar with `tarfile` (no extraction to disk), with `Range` support computed from
  the member's offset and size. Unknown member → 404.
- **`file.inspect {path}`** (RPC, in `_SILENT`) for a `.luml`:

  ```
  {
    kind: "experiment" | "model" | "dataset" | "unknown",
    manifest: object | null,           // manifest.json, parsed
    files: [{path, size}],             // tar members, directories omitted
    dataset?: {
      variant: "tabular" | "hf",
      splits: [{subset, split, format: "parquet" | "csv" | "arrow",
                files: [member, ...], num_rows: int | null}]
    }
  }
  ```

  - `kind` (TQ-2): `manifest.artifact_type` when `"experiment"` or `"dataset"`; else
    `"model"` if `fnnx.extras.reader.Reader` opens the file (as
    `ModelReference.validate`); else `"unknown"` (no-preview card).
  - Tabular splits come from the manifest payload (`subsets → splits → chunk_files`,
    `num_rows`, `-1` → `null`). HF splits come from the payload `subsets: {config:
    [split]}` and the tar members `data/<config>/<split>/*.arrow`, sorted; `num_rows` from
    `data/<config>/<split>/dataset_info.json` if present, else `null`.
  - Reads only `manifest.json`, `dataset_info.json` and the tar index.
- MCP: new tool `file-inspect` → `file.inspect`, scope `workspace`, read-only (B-07).
  Plain files: agents use their shell.

## 4. File and folder operations (B-14, TQ-5)

New RPC methods in `Api.methods`, not in `_SILENT`. Each returns `{path}` (the new path).

| Method | Params | Behaviour |
|---|---|---|
| `file.rename` | `{path, name, close_open?}` | File or folder. `AlreadyExists` if the target exists. |
| `file.move` | `{path, to, close_open?}` | `to` is an existing folder, not `path` or inside it. `AlreadyExists` if `to/<name>` exists. |
| `file.delete` | `{path, close_open?}` | Permanent: `unlink` or `shutil.rmtree`. |
| `file.mkdir` | `{directory, name}` | New empty folder. `AlreadyExists` if the name exists. |
| `file.create` | `{directory, name}` | Empty file, `open(…, "x")`. `AlreadyExists` if the name exists. |
| `flow.move` | `{flow, to, close_open?}` | Moves a `.flow` into folder `to`, like `Hub.rename_flow`. |

- Same filesystem: `Path.rename`; otherwise `shutil.move`.
- **Open notebooks.** A session is open while `Hub.opened()` has it (sessions close only
  after `SESSION_IDLE_S`, 60 min). Before rename / move / delete, collect the open
  sessions whose `ref.path` is the target or inside it.
  - None → proceed.
  - Some and `close_open` is not `true` → refuse with kind `FlowOpen` and
    `{flows: [{name, path}]}`.
  - Some and `close_open: true` → `Hub.close_session` for each, then proceed.
  - **This changes `flow.rename` and `flow.delete`:** they gain `close_open` and refuse with
    `FlowOpen` instead of closing silently. `flow.duplicate` is unchanged. The CLI
    (`lumlflow/lumlflow/flow/cli.py`, `flow delete`) always passes `close_open: true`, so
    its behaviour does not change.
- `AlreadyExists` messages read `"{name}" already exists`; the frontend shows them under
  the name field.
- **Cells that read a renamed / deleted file (TQ-6):** not tracked; dialogs warn (Frontend
  §6).

## 5. Editing text files (B-15, TQ-7)

- Editable: any regular file up to 2 MB whose content decodes as UTF-8, except `.luml`.
  The check is done by `file.read_text`; the frontend shows **Edit** only after it
  succeeds.
- **`file.read_text {path}`** (in `_SILENT`) → `{text, mtime_ns, size}`. Refuses
  `TooLarge` (> 2 MB) and `NotText` (not UTF-8, or contains NUL bytes).
- **`file.write_text {path, text, base_mtime_ns, force?: bool}`**:
  1. Locked by an agent (§6) → refuse `FileLocked {label}`, even with `force`.
  2. `stat().st_mtime_ns != base_mtime_ns` and not `force` → refuse `FileConflict
     {mtime_ns}`.
  3. Write with `atomic_write_bytes` (`flow/atomic.py`), keeping the file's mode; record
     `(path, new mtime_ns)` in `FileWatch.own_writes`; return `{mtime_ns, size}`.

## 6. File watcher and agent locks (B-15, TQ-7)

- **`FileWatch`** (new, `flow/daemon/filewatch.py`), one per daemon. Each `files`
  subscriber registers `{directory, file?}`; the watcher keeps a refcounted watchdog watch
  on each distinct directory, **non-recursive**, plus the parent directory of each open
  file. Uses `TolerantInotifyObserver` on Linux, like `watcher.py`. Ignores `.lumlflow`
  and `.flow` directories (cells have their own watcher and claims).
- **Events** (debounced 300 ms per path):
  1. Any create / delete / move / modify in a watched directory → `{type:
     "files_changed", directory}` to subscribers of that directory.
  2. Modify or create of a file, unless `own_writes` holds that path with the same
     `mtime_ns`, while at least one agent holds a lease (`Daemon._client_leases`):
     - exactly one leased agent → lock owner = that agent (`actor`, `label`);
     - several → lock owner = `{actor: null, label: "an agent"}`.
     Store `FileLock {path, actor, label, since, last}` (refresh `last` on later changes)
     and send `{type: "file_locks", locks: [...], idle_after_s: CLAIM_IDLE_S}` to
     subscribers watching that path's directory.
- **Expiry:** a lock ends `CLAIM_IDLE_S` (180 s) after `last`, or when its actor's lease
  ends (`forget_agent`); a lock with `actor: null` ends when no agent holds a lease. The
  existing claim sweep in `main.py` also sweeps file locks and sends `file_locks`.
- **Stream:** `/api/flow/stream` accepts `{"subscribe": "files", "directory": <abs>,
  "file"?: <abs>}` and answers `{type: "caught_up", channel: "files", locks,
  claim_idle_s}`. The page re-subscribes when the directory or open file changes.
- **Known limits (accepted):** writes by the person's own tools outside Flow while an
  agent is leased are attributed to the agent; an agent write between open and save is
  caught by the `mtime` check, not the lock.

## 7. Upload `.luml` to LUML (B-09, B-10, B-11, TQ-3)

- **`file.publish {path, organization_id, orbit_id, collection_id, artifact: {name,
  description, tags}}`**: must be a `.luml`; `_spawn_upload` with
  `ArtifactHandler.upload_file` (`handlers/luml/artifacts.py`). Returns `{job_id}`;
  progress is followed like `asset.publish`.
- `upload_file` uploads any `.luml` via `luml_api` `artifacts.upload`, which reads the
  manifest generically and supports `artifact_type: "dataset"`. No new upload code for
  datasets (TQ-3).

## Frontend

The approved UI is described here in full and built as a design prototype under
`codie/design/LM-1113/prototype/`. Sample data in the prototype (names, sizes, agent
"Claude") is illustrative.

**Design prototype.** The Vue files of the approved design, one folder per component:
`WorkspacesPage/` (`WorkspacesPage.vue`, `WorkspaceFileViewer.vue`,
`LumlPackagePreview.vue`), `WorkspaceFolder/` (`WorkspaceFolder.vue`,
`WorkspaceFolderItem.vue`) and `AttachmentsView/`. The `*.stories.ts` files list every
drawn state with its props; `sample.ts` holds the sample content. Read the prototype for
**how the UI looks**: markup, layout, spacing, colours, icons, texts and the states drawn.
It does **not** cover the logic:

- it is not working code and does not run in `lumlflow/frontend`: it takes static props
  and sample data, has no API calls, store, routing, stream or events;
- its imports point to the design app: `@/ui` is PrimeVue (plus copies of the app's own
  wrappers such as `LumlflowCard`, `LumlflowDialog`, `LumlflowConfirmDialog`,
  `AttachmentsPreviewDataTable`), `@/components`, `@/blocks` and `@/pages` are copies of
  existing Flow and attachments components; use the real ones in the app;
- `highlight.ts` is a stand-in for syntax highlighting (the app uses CodeMirror, §2), and
  the image, PDF, audio and video samples are placeholders;
- the **Move to…** folder select only lists sample folders (the app's picker can go up,
  §6).

Behaviour, data and edge cases come from this spec. Where the prototype and the text
disagree, the text wins; copy the look, not the code structure. Not in the prototype: **Show hidden**, **Show more**, the "moved or deleted" state, the
`FlowOpen` and unsaved-changes dialogs, the read-only experiment route, and the layout on
narrow screens; build them from existing Flow components in the same style.

Components to reuse (all in `lumlflow/frontend/src/`): the Workspace page frame and tabs,
`WorkspacePath.vue` (breadcrumb), `CreateNewFlow.vue` (**+ New notebook**), the open-flows
summary, `LumlflowCard`, `LumlflowDialog` (the 600 px layout of "Create new notebook"),
`LumlflowConfirmDialog`, `UiCodeEditor`, the PrimeVue `Button`, `SelectButton`, `Select`,
`Message`, `Tabs`, and the attachments table (`AttachmentsPreviewDataTable` in
`@luml/attachments`). Icons are `lucide-vue-next`.

### 1. Workspace page

**Nothing open** — the page as today, with file rows in the listing.

- Order: notebooks, then folders, then files, each by name.
- `WorkspaceFolderItem.vue`, `file` branch: row height and hover as folder rows; icon by
  preview type (`FileCode` code, `Sheet` table, `FileImage` image, `FileAudio` audio,
  `FileVideo` video, `FileText` text / Markdown / PDF, `Package` `.luml`, `File` other),
  16 px; name; size right-aligned in the muted colour (`1.84KB`, `12.6MB`). A symlink adds
  a small `Link` icon after the type icon. A click opens the file; the open file's row
  keeps the selected fill `--p-menu-item-focus-background`.
- Below the listing, in one row: **+ New notebook** (as today), **New folder**
  (`FolderPlus`), **New file** (`FilePlus`), all text buttons.
- **Show hidden**: a small toggle at the right of the listing header, remembered in
  `localStorage` (`lumlflow.workspace.showHidden`, read and written in try/catch).
- **Show more**: when `next_offset` is set, the listing ends with "Showing {n} of {total}
  items" and a text button **Show more**, which loads the next page and appends it.
- Empty directory: "This directory is empty".

**A file open** — the listing becomes a 400 px column on the left and the viewer card
fills the rest; clicking another file swaps the viewer; the viewer's X closes it and the
listing takes the full width again. Route query `?directory=…&file=…` keeps the selection
on reload and back.

`WorkspaceFileViewer.vue` (new), a `LumlflowCard`:

- **Header:** name; then size and "Modified {YYYY-MM-DD HH:mm}" in the muted colour; below,
  the full path with a copy button (`Copy`); an X (`X`, "Close preview") at the right. File
  actions are in the row menu, not in the header.
- **Body** by type:
  - `.luml` → `LumlPackagePreview` (§3);
  - a type the preview supports → `FilePreview` from `@luml/attachments` reading
    `GET /api/flow/file`; text and code also get **Edit** (§4);
  - any other file: try `file.read_text`; if it succeeds, plain text with **Edit**;
    otherwise the no-preview card;
  - **No-preview card:** the header stays and the body says "No preview for this file
    type". Same layout for "File is empty" and, over the preview size limit, "File is too
    large for preview".

- Above text content, one row: on the left the Rendered / Raw (Markdown) or Pretty / Raw
  (JSON, YAML) `SelectButton`, size small, when the type has one; on the right **Edit**
  (text button, `Pencil` icon).
- Images and SVG are centred on a bordered surface; audio and video use the browser's
  player; PDF and HTML fill the body in a frame (HTML in a sandboxed iframe).
- Tables (CSV, XML, Parquet, Arrow) use the attachments table: 10 rows per page, page
  sizes 10 / 20 / 50, small size.
- Listing and viewer refresh on `files_changed`.
- **File gone:** if the open file no longer exists after a refresh (deleted or moved from
  outside), the viewer keeps its header and the body says "This file was moved or
  deleted"; unsaved edits stay visible and copyable; the X returns to the listing.
- **Unsaved edits + operation:** rename, move or delete of the file being edited, or of a
  folder containing it, first asks "You have unsaved changes in {name}. Discard them and
  continue?" (**Discard and continue** / **Cancel**), as a `LumlflowConfirmDialog`.

### 2. `@luml/attachments` (shared)

- **Exports:** `FilePreview`, `useFilePreview(name, getBlob, size)` (no tree needed),
  `getFileType`, `FILE_TYPES`, and the language map for CodeMirror.
- **Types (at least the current ones):** keep all current ones; add images `gif`, `webp`;
  text `log`; code `toml`, `ini`, `cfg`, `sh`, `sql`, `jsx`, `tsx`, `css`; table
  `parquet`, `arrow`. Detection stays by extension.
- **Size:** keep the 10 MB limit, except audio, video and PDF (streamed by URL) and Parquet
  (partial read), which have no limit.
- **Highlighting (B-12, TQ-8):** `CodePreview` uses a read-only CodeMirror 6 view
  (`EditorState.readOnly`, `EditorView.editable.of(false)`) with `python`, `javascript`
  (js, ts, jsx, tsx), `json`, `yaml`, `markdown`, `css`, `sql`, `xml` (xml, html);
  colours from the `--ui-code-*` variables used by Flow's editor
  (`components/ui/code-editor/code-editor.const.ts`). `txt` and `log` stay plain
  monospaced text.
- **Toggles (B-13):** Markdown → Rendered (marked + DOMPurify, as today) / Raw (highlighted).
  JSON → Pretty (`JSON.stringify(…, null, 2)`) / Raw. YAML → Pretty (`js-yaml` load + dump)
  / Raw. Default Rendered / Pretty; invalid JSON / YAML shows Raw with "Can't parse".
- **Tables (B-06):** `TablePreview` gains Parquet via `hyparquet` (schema + first 1,000
  rows, reading only the needed byte ranges through an async-buffer over the URL or blob)
  and Arrow IPC via `apache-arrow` `tableFromIPC` (first 1,000 rows), paged in the table
  as above. Footer: "Showing first 1,000 of N rows" when N is known. CSV / XML unchanged.
- The same changes show in Flow's and LUML's Attachments tabs (a `.parquet` attachment
  opens as a table there too); no other change to those tabs.

### 3. `.luml` view (`LumlPackagePreview`)

- Calls `file.inspect`, then shows, top to bottom:
  - a row "For full overview" with the actions on the right (secondary small buttons with
    14 px icons):
    - **experiment:** **Open in Experiments** (`FlaskConical`, §5) and **Upload experiment
      to LUML** (`CloudUpload`);
    - **model:** **Upload model to LUML** (`CloudUpload`);
    - **dataset:** **Upload dataset to LUML** (`CloudUpload`);
  - **dataset only — Data:** `Tabs` with one tab per `subset / split`; each tab previews the
    first file of the split (Parquet / CSV / Arrow) via `/api/flow/file/entry` in the
    attachments table, 1,000 rows; total rows from `num_rows` when known;
  - **Manifest:** the whole `manifest.json` as highlighted YAML, scrolling after 320 px;
  - **Contents:** the files in the archive, `File` / `Folder` icon, path, size on the right.
  - **unknown kind:** the no-preview card.
- A file in **Contents** opens in `FilePreview` via `/api/flow/file/entry`.

### 4. Editing (B-15)

- **Edit** swaps the highlighted text for `UiCodeEditor` (language from the shared map,
  full body height) and, in the row above it, the view toggle for **Cancel** (text button)
  and **Save** (primary), both small, on the right.
- **Changed on disk:** when the file changes on disk during an edit (`files_changed` and a
  newer `mtime`) or `file.write_text` returns `FileConflict`, a warning `Message` (small)
  appears above the editor: "This file changed on disk after you started to edit it." with
  **Overwrite** (saves with `force: true`) and **Reload** (text button; takes the file from
  disk and drops the edit).

- **Agent lock** (from `file_locks` frames), drawn like a cell an agent works on: the
  card's border takes the agent's colour; under the header a strip in that colour with a
  `Lock` icon (14 px) and "{label} is working on this file" (e.g. "Claude is working on
  this file", or "An agent is working on this file" when `actor` is null), with the tooltip
  "Read-only until 3 minutes after the agent's last change to this file."; the body is
  dimmed and **Edit** is disabled. Colour: `agentColor(actor)` (`store/flow`
  `AGENT_COLORS`), neutral when `actor` is null.

- **Lock during an edit:** the editor turns read-only and the strip appears; the person's
  unsaved text stays visible and copyable. When the lock ends, the changed-on-disk warning
  offers **Overwrite** / **Reload**.

### 5. Experiment from a `.luml` (B-09, TQ-4)

- New route `workspaces/experiment?path=<abs .luml>` rendering the experiment details tabs
  (overview, metrics, traces, evals, attachments) read-only:
  - `exp.db.zip` (via `/file/entry`) → unzip → `sql.js`, as the main frontend's
    `frontend/src/hooks/useSqlLite.ts` → the snapshot provider from `@luml/experiments`;
  - `attachments.tar` + `attachments.index.json` → `TarAttachmentsProvider` with byte
    ranges from `/file/entry`.
- No rename, delete, tag or upload actions; a banner names the file.

### 6. Row menu and dialogs (B-14)

- Files and folders get the notebooks' ⋮ menu with **Rename**, **Move to…**, **Delete** (no
  Duplicate); notebooks gain **Move to…** and keep their items.
- **Rename** is inline, as in `WorkspaceFolderItemFlow.vue`, with a small secondary
  **Save** button (smaller than the notebook row's).
- **Move to…:** a `LumlflowDialog` (600 px, layout of "Create new notebook"), header
  "MOVE TO", text "Move **{name}** to:", a folder field, and a full-width rounded **Move**
  button, disabled until a folder is chosen. The folder field opens a picker that starts at
  the current directory, lists its folders, and can go up to the parent and into a folder
  (operations work anywhere the page can browse); the chosen path shows in the field.

- **New folder** / **New file:** the same dialog as "Create new notebook": header "CREATE
  NEW FOLDER" / "CREATE NEW FILE", required **Name** field (placeholder "Name your folder"
  / "Name your file, e.g. notes.md"), full-width rounded **Create folder** / **Create file**,
  disabled while the name is empty. Errors under the field in red, small: `"{name}" already
  exists` (`AlreadyExists`) and the name-rule message for an invalid name. A created file
  opens in the viewer.

- **Delete** uses `LumlflowConfirmDialog`:
  - file: header "Delete {name}?", text "This action is permanent and cannot be undone.
    Cells that read this file will fail the next time they run.", buttons **Cancel** and
    **Delete file** (warn, outlined);
  - folder: header "Delete {name}?", text "The folder and everything in it are deleted. This
    action is permanent and cannot be undone.", buttons **Cancel** and **Delete folder**.

- Rename and move of a file show an inline note under the field: "Cells that read this file
  by path are not updated."
- **`FlowOpen`:** `LumlflowConfirmDialog` "{n} open notebook(s) will be closed: {names}.
  Running cells stop and agents working in them lose their session. Close and continue?"
  (**Close and continue** / **Cancel**) → repeats the call with `close_open: true`.
- Errors from operations show as an error toast with the message (`kind` decides the
  wording for known kinds, the OS message for `OsError`).

### 7. Upload

- `UploadModal.vue` gets a `publishFile` prop beside `publish` / `publishExperiment`; the
  name defaults to the manifest's `name`.

## Dependencies

- `@luml/attachments`: `hyparquet`, `apache-arrow` (21.1.0, as the main frontend),
  `js-yaml`, `@codemirror/view`, `@codemirror/state`, `@codemirror/language`,
  `@codemirror/lang-python`, `@codemirror/lang-javascript`, `@codemirror/lang-json`,
  `@codemirror/lang-yaml`, `@codemirror/lang-markdown`, `@codemirror/lang-css`,
  `@codemirror/lang-sql`, `@codemirror/lang-xml` (as peer dependencies where Flow already
  has them).
- Flow frontend: `sql.js` and the unzip library the main frontend uses for `exp.db.zip`.
- Backend: none new (`watchdog`, `tarfile`, `fnnx` already used).

## Trade-offs

- **CodeMirror in the shared package** makes the main LUML frontend heavier, but previews
  and the editor look the same.
- **`hyparquet` instead of `parquet-wasm`:** no wasm file to serve in two apps, partial
  reads; slower on full scans, which previews don't do.
- **Operations anywhere on disk:** consistent with browsing, but a bug can touch any file
  the user can; mitigated by `Protected` paths, name checks and confirm dialogs.
- **Lock attribution** is per lease, not per write; several agents give a generic lock.
- **`flow.rename` / `flow.delete` change behaviour** (refuse while open); the CLI passes
  `close_open: true` to keep today's behaviour.
- **Listing pages of 2,000:** fast first paint for huge folders; a file past the loaded
  pages is found only after **Show more** (no search in this version).

# Scenarios

## Listing

## Scenario: Files appear in the listing
**Given** a folder with `analysis.flow/`, `data/`, `report.md`, `.env` and `.venv/`
**When** the person opens it on the Workspace page
**Then** the listing shows `analysis` (notebook), `data` (folder) and `report.md` with its
size and modified date, in that order, and does not show `.env` or `.venv`

## Scenario: Show hidden
**Given** the same folder
**When** the person turns on **Show hidden**
**Then** `.env` and `.venv` are listed, `.lumlflow` is not, and the toggle stays on after a
reload

## Scenario: Big folder is paged
**Given** a folder with 4,500 files
**When** the person opens it
**Then** 2,000 items are shown with "Showing 2,000 of 4,500 items" and **Show more**; two
clicks on **Show more** load all 4,500 and the button disappears

## Scenario: Listing refreshes on outside changes
**Given** the person is looking at a folder
**When** a file is created in it from a terminal
**Then** the file appears in the listing within about a second, without a manual refresh

## Scenario: Symlink to a folder
**Given** `data` is a symlink to `/mnt/big/data`
**When** the person opens the folder holding it
**Then** `data` is listed as a folder with a link icon and can be opened

## Scenario: Broken symlink
**Given** `latest.csv` links to a file that no longer exists
**When** the person clicks it
**Then** the viewer shows name and date only, with size unknown

## Preview

## Scenario: Preview a supported file
**Given** `plot.png`
**When** the person clicks it
**Then** the listing narrows to a column, the image opens next to it with name, size,
modified date and path, and the URL holds `file=<path>`

## Scenario: Unsupported binary file
**Given** `model.pkl` (binary)
**When** the person clicks it
**Then** the viewer shows name, size and modified date only

## Scenario: Unknown extension with text content
**Given** a `Makefile` (no extension, UTF-8)
**When** the person clicks it
**Then** it is shown as plain text with **Edit**

## Scenario: File over the preview limit
**Given** `big.csv` of 50 MB
**When** the person clicks it
**Then** the viewer shows name, size and date with "File is too large for preview"

## Scenario: Large video plays
**Given** `run.mp4` of 300 MB
**When** the person clicks it
**Then** the video plays and can seek (range requests), without loading the whole file

## Scenario: Parquet in all three places
**Given** `train.parquet` of 400 MB in the workspace, and the same file as an experiment
attachment in Flow and in LUML
**When** the person opens it in each place
**Then** a paginated table shows its columns and the first 1,000 rows with "Showing first
1,000 of N rows", without downloading the whole file

## Scenario: Markdown toggle
**Given** `README.md`
**When** the person opens it, then clicks **Raw**
**Then** it first shows rendered, then the highlighted source

## Scenario: JSON and YAML toggles
**Given** a minified `config.json` and a `params.yaml`
**When** the person opens each
**Then** each shows Pretty by default and **Raw** shows the file as it is on disk

## Scenario: Invalid JSON
**Given** `broken.json` that does not parse
**When** the person opens it
**Then** it shows Raw with "Can't parse", and no Pretty toggle

## Scenario: Code highlighting in Attachments tabs
**Given** an experiment attachment `train.py`
**When** the person opens it in Flow's or LUML's Attachments tab
**Then** the code is highlighted

## Scenario: Plain text stays plain
**Given** `run.log`
**When** the person opens it
**Then** it shows without highlighting

## `.luml` files

## Scenario: Experiment `.luml`
**Given** `run-42.luml` with `artifact_type: "experiment"`
**When** the person opens it
**Then** the viewer shows the manifest as YAML, the archive files, **Open in Experiments**
and **Upload experiment to LUML**

## Scenario: Open an experiment from the file
**Given** `run-42.luml`
**When** the person clicks **Open in Experiments**
**Then** the experiment details open read-only from the archive (overview, metrics,
traces, evals, attachments), a banner names the file, there are no edit actions, and the
local tracker has no new experiment

## Scenario: Model `.luml`
**Given** a model `.luml` (fnnx, no `artifact_type`)
**When** the person opens it
**Then** the viewer shows the manifest as YAML, the archive files and "For full overview,
upload model to LUML" with **Upload model to LUML**

## Scenario: Tabular dataset `.luml`
**Given** a tabular dataset with subset `default` and splits `train`, `test`, Parquet chunks
**When** the person opens it
**Then** tabs `default / train` and `default / test` each show the first 1,000 rows of the
split's first chunk with the split's total rows, and the manifest and archive files below

## Scenario: Hugging Face dataset `.luml`
**Given** an HF dataset with config `default` and splits `train`, `validation`
**When** the person opens it
**Then** each split tab shows the first 1,000 rows of its first `.arrow` file as a table

## Scenario: Unknown `.luml`
**Given** a `.luml` that is not an experiment or dataset and that fnnx cannot read
**When** the person opens it
**Then** the viewer shows name, size and date only

## Scenario: File inside an archive
**Given** an experiment `.luml`
**When** the person clicks `attachments.index.json` in the archive list
**Then** it opens as pretty JSON, read from the archive without unpacking it to disk

## Scenario: Upload a dataset
**Given** a dataset `.luml` and a connected LUML account
**When** the person clicks **Upload dataset to LUML** and confirms
**Then** a job uploads the file with progress and the dataset appears in the chosen
collection

## Scenario: Agent inspects a `.luml`
**Given** an agent connected over MCP
**When** it calls `file-inspect` on `run-42.luml`
**Then** it gets the kind, manifest and file list the person sees

## Operations

## Scenario: Rename a file
**Given** `raw.csv`
**When** the person renames it to `raw-2026.csv`
**Then** it is renamed on disk, the listing updates, and the inline note says cells reading
it by path are not updated

## Scenario: Rename to an existing name
**Given** `a.csv` and `b.csv`
**When** the person renames `a.csv` to `b.csv`
**Then** the rename is refused with "b.csv already exists" and nothing changes

## Scenario: Invalid name
**Given** any file
**When** the person renames it to `../x` or `a/b`
**Then** the rename is refused and nothing changes

## Scenario: Move a file
**Given** `plot.png` and folder `figures/`
**When** the person uses **Move to…** and picks `figures`
**Then** the file is moved into `figures/` and disappears from the current listing

## Scenario: Move a folder into itself
**Given** folder `a/` with subfolder `a/b/`
**When** the person moves `a` into `a/b`
**Then** the move is refused and nothing changes

## Scenario: Move across disks
**Given** a file on the internal disk and a target folder on an external disk
**When** the person moves it
**Then** it is copied, the source is removed, and a failed copy leaves the source untouched

## Scenario: Delete a file permanently
**Given** `tmp.csv`
**When** the person deletes it and confirms
**Then** it is removed from disk (not to Trash)

## Scenario: Delete a folder
**Given** folder `old/` with files and no open notebooks
**When** the person deletes it and confirms
**Then** the folder and everything in it are removed

## Scenario: Delete a folder with an open notebook
**Given** folder `old/` containing `exp.flow` with an open session
**When** the person deletes `old/`
**Then** a dialog lists `exp` as open and warns that running cells stop and agents lose
their session; **Close and continue** closes it and deletes the folder; **Cancel** changes
nothing

## Scenario: Rename an open notebook
**Given** an open notebook `exp.flow`
**When** the person renames it from the row menu
**Then** the same close-and-continue dialog appears before the rename

## Scenario: CLI delete keeps today's behaviour
**Given** an open notebook `exp.flow`
**When** `lumlflow flow delete exp` runs
**Then** the notebook is closed and deleted without a prompt

## Scenario: Protected paths
**Given** the folder `lumlflow ui` runs in, the home folder, or `/`
**When** a rename, move or delete is requested for that folder itself
**Then** it is refused with `Protected`, while files inside it can still be changed

## Scenario: Delete a symlink to a folder
**Given** `data` links to `/mnt/big/data`
**When** the person deletes `data`
**Then** only the link is removed; `/mnt/big/data` and its contents stay

## Scenario: New file and new folder
**Given** a folder that already holds `README.md`
**When** the person clicks **New file** and enters `README.md`
**Then** the dialog shows `"README.md" already exists` under the name and nothing is
created; with `notes.md` the file is created and opens in the viewer; **New folder** with
`plots` creates the folder

## Scenario: No permission
**Given** a file the OS user may not delete
**When** the person deletes it
**Then** an error toast shows the OS message ("Permission denied") and the file stays

## Scenario: Operation outside the start folder
**Given** the person browsed up to a folder above the one `lumlflow ui` runs in
**When** they rename a file there
**Then** the rename works as anywhere else

## Editing and agent locks

## Scenario: Edit and save
**Given** `config.yaml` with no agent lock
**When** the person edits and saves it
**Then** the file is written atomically and no agent lock appears for that write, even if
an agent is active

## Scenario: Not editable
**Given** a 5 MB `data.csv` or a binary file
**When** the person opens it
**Then** there is no **Edit** button

## Scenario: Changed on disk during an edit
**Given** the person is editing `notes.md` and it changes on disk, with no lock
**When** the change arrives, or the person saves
**Then** a warning above the editor says "This file changed on disk after you started to
edit it." with **Overwrite** (writes the person's text) and **Reload** (takes the file
from disk)

## Scenario: One agent changes a file
**Given** one agent session holds a lease and `notes.md` is open
**When** the agent writes `notes.md` from its shell
**Then** the card's border and a strip take the agent's colour, the strip says "{agent} is
working on this file", the body is dimmed, **Edit** is disabled, and it becomes editable
180 s after the agent's last change

## Scenario: Several agents active
**Given** two agent sessions hold leases
**When** `notes.md` changes on disk
**Then** the strip reads "An agent is working on this file" in a neutral colour

## Scenario: Lock ends with the agent's session
**Given** a file locked by an agent
**When** that agent's session ends
**Then** the lock is released immediately

## Scenario: Change without an agent
**Given** no agent holds a lease
**When** the person changes a file from their own editor
**Then** no lock appears; the listing and viewer refresh

## Scenario: Lock during an edit
**Given** the person is editing `notes.md` with unsaved text
**When** an agent writes the file
**Then** the editor turns read-only and the agent strip appears, the unsaved text stays
visible and copyable, and after the lock ends the person chooses **Overwrite** or
**Reload**

## Scenario: Save while locked
**Given** a file locked by an agent
**When** a `file.write_text` arrives (even with `force`)
**Then** it is refused with `FileLocked`

## Scenario: Open file deleted from outside
**Given** `notes.md` is open with unsaved edits
**When** it is deleted from a terminal
**Then** the viewer shows "This file was moved or deleted", keeps the unsaved text visible,
and **Close** returns to the listing

## Scenario: Unsaved edits, then rename
**Given** unsaved edits in `notes.md`
**When** the person renames `notes.md` from the row menu
**Then** a dialog asks to discard the changes; **Cancel** keeps the edits and the name

# Tasks

Backend tasks first (daemon in `lumlflow/lumlflow/flow/daemon/`, tests in
`lumlflow/tests/unit/daemon/`), then frontend. Each task ends with its checks passing:
backend `ruff` + `mypy` + `pytest lumlflow/tests/unit`; frontend `lint`, `type-check`,
`test:ci` of every package it touches. Tasks that change `@luml/attachments` also run
`type-check`, `test:ci` and `build` of `frontend/` (main LUML app) and `lumlflow/frontend/`.

- [ ] **1. Paths helper and listing with files** (Design §1, §2)
  - [ ] `Api._file_path` (parent resolved, last component kept), name validation reusing
    `Hub._new_flow_ref` checks, `NotAFile`, `Protected`, `OsError` mapping
  - [ ] `list_directory(root, hidden)`: files with `size`, `modified`, `is_link`; folders
    with `modified`, `is_link`; broken links; hidden rule; ordering and
    `offset` / `limit` (max 2000), `total`, `next_offset`
  - [ ] `workspace.list` params and response; update `test_workspace.py`
  - [ ] Tests: names (`..`, `/`, empty), protected paths, symlink kept as link, hidden on /
    off, `.lumlflow` never listed, paging of 4,500 entries

- [ ] **2. File bytes and `.luml` inspection** (Design §3)
  - [ ] `GET /api/flow/file` in `web.py` (token, regular file, `FileResponse`, Range)
  - [ ] `GET /api/flow/file/entry` (tar member streaming with Range, 404 on unknown member)
  - [ ] `file.inspect` (kind detection via `artifact_type` / fnnx `Reader`; tabular and HF
    split lists; `num_rows`); add to `_SILENT`
  - [ ] MCP tool `file-inspect` in `mcp.py`; update `test_mcp.py`
  - [ ] Tests with small fixture archives built by the SDK (`save_tabular_dataset`, HF
    dataset if `datasets` is available in tests, an experiment via the tracker, a model)
    and a non-luml tar

- [ ] **3. File and folder operations** (Design §4)
  - [ ] `file.rename`, `file.move` (same / cross filesystem, rollback), `file.delete`
    (unlink / rmtree, links never followed), `file.mkdir`, `file.create` (name required,
    `"{name}" already exists`)
  - [ ] `flow.move`; `close_open` and `FlowOpen` in all operations, including
    `flow.rename` and `flow.delete`; open sessions found under a folder
  - [ ] CLI `flow delete` passes `close_open: true` (`cli.py`)
  - [ ] Tests: each scenario under *Operations* that the daemon decides (exists, invalid
    name, into itself, protected, open notebook refused / closed, symlink delete,
    permission error)

- [ ] **4. Text read / write with conflict check** (Design §5)
  - [ ] `file.read_text` (2 MB, UTF-8, NUL check) and `file.write_text` (`FileConflict`,
    `force`, atomic write keeping the mode, returns `mtime_ns`)
  - [ ] `FileLocked` check calls an interface that task 5 implements (stub returns no lock)
  - [ ] Tests: too large, not text, conflict, force, mode kept

- [ ] **5. File watcher and agent locks** (Design §6)
  - [ ] `filewatch.py`: refcounted non-recursive watches per subscribed directory and open
    file's parent; ignore `.lumlflow` and `.flow`; 300 ms debounce
  - [ ] `files` subscription on `/api/flow/stream` (`caught_up`, `files_changed`,
    `file_locks`)
  - [ ] Lock attribution from `Daemon._client_leases` (one agent / several → "an agent"),
    `own_writes` skip, expiry with `CLAIM_IDLE_S` and on lease end, sweep in `main.py`
  - [ ] Wire `file.write_text` to refuse `FileLocked`
  - [ ] Tests (as `test_cell_claims.py` / `test_stream.py`): one agent, several agents, no
    agent, own write not locked, expiry, lease end

- [ ] **6. Upload a `.luml` file** (Design §7)
  - [ ] `file.publish` via `_spawn_upload` + `ArtifactHandler.upload_file`; `.luml` only
  - [ ] Tests with a mocked LUML client: job created, progress completes, non-`.luml`
    refused

- [ ] **7. `@luml/attachments`: exports, types, highlighting, toggles** (Frontend §2)
  - [ ] Export `FilePreview`, standalone `useFilePreview`, `getFileType`, `FILE_TYPES`,
    language map
  - [ ] New extensions; size rule (10 MB, except audio / video / PDF)
  - [ ] Read-only CodeMirror in `CodePreview` with the listed language packs and
    `--ui-code-*` colours; `txt` / `log` plain
  - [ ] Markdown Rendered / Raw, JSON and YAML Pretty / Raw, "Can't parse" fallback
  - [ ] Tests for type detection, toggles, invalid JSON / YAML; check Flow's and LUML's
    Attachments tabs still build and pass

- [ ] **8. `@luml/attachments`: Parquet and Arrow tables** (Frontend §2, B-06)
  - [ ] `hyparquet` reader over URL / blob with partial reads; `apache-arrow` IPC reader;
    first 1,000 rows, "Showing first 1,000 of N rows"
  - [ ] Tests with small Parquet and Arrow fixtures; check both apps

- [ ] **9. Workspace listing and file viewer** (Frontend §1)
  - [ ] API types and calls for the new `workspace.list` fields and paging; store items of
    `type: 'file'`; **Show more**; **Show hidden** (localStorage, try/catch)
  - [ ] `WorkspaceFolderItem.vue` file rows (click, icon, size, selected, link icon)
  - [ ] `WorkspacesPage.vue` split layout and `?file=`; `WorkspaceFileViewer.vue` (header,
    `FilePreview` over `/api/flow/file`, plain-text fallback via `file.read_text`,
    no-preview / empty / too-large states)
  - [ ] `files` stream subscription; refresh on `files_changed`; "moved or deleted" state
  - [ ] Match the look of `prototype/WorkspaceFolder/` and `prototype/WorkspacesPage/`
    (`WorkspacesPage.vue`, `WorkspaceFileViewer.vue`)
  - [ ] Tests for the store (paging, hidden, refresh) and viewer states

- [ ] **10. Row menu, dialogs and operations** (Frontend §6)
  - [ ] ⋮ menu for files, folders and notebooks; inline rename with Save; **Move to…**
    dialog with a folder picker that can go up; **Delete** confirms; **New file** / **New
    folder** dialogs with name errors
  - [ ] `FlowOpen` close-and-continue dialog; unsaved-changes dialog; error toasts by `kind`
  - [ ] Match the look of the dialogs in `prototype/WorkspacesPage/WorkspacesPage.vue`,
    the row menu and inline rename in `prototype/WorkspaceFolder/WorkspaceFolderItem.vue`
  - [ ] Tests for the store actions and dialog flows

- [ ] **11. Editing with locks and conflicts** (Frontend §4)
  - [ ] `UiCodeEditor` with the shared language map; Edit / Save / Cancel
  - [ ] Agent strip, coloured border and dimmed body with `agentColor` / neutral colour;
    read-only during a lock; keep unsaved text; changed-on-disk warning with Overwrite /
    Reload (during an edit, after a lock, on `FileConflict`)
  - [ ] Match the look of the editing, conflict and agent states in
    `prototype/WorkspacesPage/WorkspaceFileViewer.vue`
  - [ ] Tests for lock, conflict and save flows

- [ ] **12. `.luml` view and upload** (Frontend §3, §7)
  - [ ] `LumlPackagePreview` for experiment, model, dataset (split tabs via
    `/api/flow/file/entry`), unknown; archive file list opening `FilePreview`
  - [ ] `UploadModal` `publishFile`; buttons for all three kinds
  - [ ] Match the look of `prototype/WorkspacesPage/LumlPackagePreview.vue`
  - [ ] Tests per kind with mocked `file.inspect`

- [ ] **13. Experiment from a `.luml` (read-only route)** (Frontend §5)
  - [ ] Route `workspaces/experiment?path=`; `exp.db.zip` → unzip → `sql.js` provider
    (as `frontend/src/hooks/useSqlLite.ts`); `TarAttachmentsProvider` over `/file/entry`
  - [ ] Experiment tabs rendered read-only, banner with the file name, no write actions
  - [ ] Tests with a small experiment archive fixture

- [ ] **14. Remove the design references** (Frontend)
  - [ ] Delete `codie/design/LM-1113/` (the design prototype): they are spec material
    and must not reach `main`, where CI rejects `codie/**`
