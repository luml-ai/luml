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
are in `SPEC-design/` (see Design prototype). Codes in brackets (`B-#`, `TQ-#`, `S-#`) are
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
- Agents can inspect a `.luml` through a new MCP tool (B-07).
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

## Overview

The Workspace page talks only to the local daemon, over three channels that exist today.

- **RPC.** Listing, file operations, text read / write, `.luml` inspection and upload are
  methods on the daemon's `Api`, called over `POST /api/flow/rpc` and the socket.
- **HTTP.** File bytes and single members of a `.luml` archive are served by two new `GET`
  endpoints, so the browser can stream and read byte ranges.
- **Stream.** Outside changes and agent locks arrive on a new `files` channel of
  `/api/flow/stream`.

Daemon code is in `lumlflow/lumlflow/flow/daemon/`, the Flow frontend in
`lumlflow/frontend/src/`, the shared preview in `extras/js/packages/attachments/`.

## Paths

Every new method and endpoint takes absolute paths and applies the same rules.

- **No root confinement.** The boundary is what the daemon's OS user can access, the same
  as browsing today.
- **Existence.** A path must exist, except the target of a create.
- **Symlinks.** A link is never resolved away: the path's parent is resolved and the last
  component is kept as given. A link is listed as its target's kind (file or folder) and
  marked as a link. Previews and text read / write act on the target. Rename, move and
  delete act on the link only; deleting a link to a folder never removes the target's
  contents. A broken link is listed as a file with unknown size and shows the no-preview
  card.
- **Names.** A new name is one path component: not empty, no `/` or `\`, not `.` or `..`.
  Reuse the checks for new notebook names in `Hub._new_flow_ref`.
- **Writes** are atomic. A failed move across filesystems removes the partial copy and
  leaves the source in place.

Refusals use the existing error shape of `/api/flow/rpc` (message and kind). The frontend
maps the kind to its wording.

| Kind | Refused when |
|---|---|
| `NotAFile` | A `file.*` method gets a `.flow` directory, a path inside one, or anything inside `.lumlflow`. Notebooks go through `flow.*`. |
| `Protected` | Rename, move or delete of the filesystem root, the user's home directory, or the folder `lumlflow ui` runs in. Their contents are not protected. |
| `AlreadyExists` | The target name exists. The message reads `"{name}" already exists`. |
| `FlowOpen` | Rename, move or delete touches an open notebook and the caller did not ask to close it. Carries the open notebooks' names and paths. |
| `OsError` | The OS refuses (no permission, read-only filesystem, disk full). Carries the OS message, e.g. "Permission denied". |
| `TooLarge`, `NotText` | A text read of a file over 2 MB, or one that is not UTF-8 or contains NUL bytes. |
| `FileConflict` | A text write to a file that changed on disk since it was read. Carries the file's current modification time. |
| `FileLocked` | A text write to a file an agent holds a lock on. Carries the lock's label. |

## Listing

`workspace.list` gains plain files, each with size, modified time (UTC) and a link flag.
Folders gain the modified time and the link flag (TQ-10).

- **Hidden entries.** By default the listing skips names that start with `.` and names in
  `EXCLUDED_DIRS` (`flow/dsl/tree.py`), for files and folders alike. With the hidden option
  on, it lists everything except `.lumlflow`. `.gitignore` is not applied.
- **Paging.** Entries are ordered as the UI shows them: notebooks, then folders, then
  files, each by name, case-insensitive. The caller asks for an offset and a limit; the
  limit defaults to 2,000 and cannot be higher. The response gives the total number of
  entries and where the next page starts, or nothing on the last page.

## Reading files

- **File bytes: `GET /api/flow/file`.** Serves a regular file by absolute path, inline,
  with a guessed media type and the same token check as `/api/flow/download`. It must
  answer `Range` requests, so audio, video, PDF and Parquet are read partially.
- **Archive member: `GET /api/flow/file/entry`.** Serves one member of a `.luml` tar by
  name, with `Range` support, without extracting the archive to disk. An unknown member
  is a 404.
- **`file.inspect`** describes a `.luml`: its kind (experiment, model, dataset or unknown),
  the parsed manifest, and the archive's files with sizes. For a dataset it also gives the
  variant (tabular or Hugging Face) and the splits; each split has its subset, name, format
  (Parquet, CSV or Arrow), member files and row count when known. It reads only the
  manifest, `dataset_info.json` and the tar index, and does not count as agent activity
  (`_SILENT`).
  - **Kind (TQ-2).** The manifest's `artifact_type` when it is experiment or dataset;
    otherwise model if `fnnx.extras.reader.Reader` opens the file (the check
    `ModelReference.validate` uses); otherwise unknown.
  - **Tabular splits** come from the manifest payload (subsets, splits, chunk files, row
    counts; a count of `-1` means unknown).
  - **Hugging Face splits** come from the payload's subsets and the `.arrow` members under
    `data/<config>/<split>/`, sorted. The row count comes from that split's
    `dataset_info.json` if present.
- **MCP.** A new read-only tool `file-inspect` in scope `workspace` calls `file.inspect`.
  For plain files agents use their shell.

## File and folder operations

Six new RPC methods. Each returns the resulting path and counts as agent activity (B-14,
TQ-5).

| Method | Behaviour |
|---|---|
| `file.rename` | Renames a file or folder in place. |
| `file.move` | Moves a file or folder into an existing folder. The folder cannot be the item itself or inside it. |
| `file.delete` | Deletes permanently; a folder goes with everything in it. |
| `file.mkdir` | Creates an empty folder in a directory. |
| `file.create` | Creates an empty file in a directory. Never overwrites. |
| `flow.move` | Moves a notebook into a folder, as `Hub.rename_flow` renames one. |

**Open notebooks.** A notebook is open while `Hub.opened()` has its session; sessions close
only after 60 minutes idle (`SESSION_IDLE_S`). Rename, move and delete look for open
notebooks at the target or inside it. If there are any, the call is refused with `FlowOpen`
unless it carries the `close_open` flag; with the flag, those sessions are closed first.

This changes `flow.rename` and `flow.delete`: today they close an open notebook silently,
now they follow the same rule. `flow.duplicate` is unchanged. The CLI command
`flow delete` (`lumlflow/lumlflow/flow/cli.py`) always sets the flag, so its behaviour
does not change.

Cells that read a renamed, moved or deleted file are not tracked (TQ-6). The dialogs only
warn.

## Editing text files

A file is editable when it is a regular file of at most 2 MB that decodes as UTF-8, has no
NUL bytes, and is not a `.luml` (B-15, TQ-7).

- **`file.read_text`** applies that check and returns the text with the file's
  modification time at full precision. It does not count as agent activity.
- **`file.write_text`** takes the text and the modification time the edit started from.
  The checks run in this order:
  - an agent lock on the file refuses the write, even when forced;
  - a different modification time on disk refuses the write, unless forced;
  - otherwise the file is written atomically (`flow/atomic.py`), keeping its mode, and the
    new modification time is returned.
- The daemon remembers its own writes so that the file watcher does not take them for an
  agent's.

## File watcher and agent locks

Agents write files through their own shell, so the daemon learns about a change only by
watching the disk. One watcher per daemon serves the `files` channel of `/api/flow/stream`.

**What is watched.** A subscriber names the directory it lists and, optionally, the file it
has open. The watcher watches each subscribed directory and the parent of each open file,
not recursively, and drops a watch when its last subscriber leaves. It uses the tolerant
inotify observer on Linux, as `watcher.py` does, and ignores `.lumlflow` and `.flow`
directories, because cells have their own watcher and claims. Events are debounced by
about 300 ms per path.

**What is sent.** Any change in a watched directory tells that directory's subscribers
that it changed. A change to the lock list sends the current locks, with the idle time, to
the subscribers watching the locked file's directory. A new subscriber gets the current
locks on catch-up, as on the other channels. The page subscribes again when the directory
or the open file changes.

**Lock rule.** A file gets a lock when it is created or modified while at least one agent
holds a lease (`Daemon._client_leases`), unless the change is the daemon's own write.

- One leased agent: the lock belongs to that agent and carries its label.
- Several leased agents: the lock has no owner and the label "an agent".
- Later changes to the file extend the lock.

**Expiry.** A lock ends `CLAIM_IDLE_S` (180 s) after the file's last change, or when its
owner's lease ends. A lock without an owner ends when no agent holds a lease. The existing
claim sweep in `main.py` also sweeps file locks and announces the result.

**Known limits (accepted).** Writes by the person's own tools outside Flow while an agent
is leased are attributed to the agent. An agent write between open and save is caught by
the modification-time check, not by the lock.

## Uploading a `.luml` to LUML

`file.publish` uploads a `.luml` file, and nothing else, to a chosen organization, orbit
and collection with an artifact name, description and tags. It starts an upload job
through `_spawn_upload` with `ArtifactHandler.upload_file` (`handlers/luml/artifacts.py`)
and returns the job id; progress is followed as for `asset.publish` (B-09, B-10, B-11).

No new upload code is needed for datasets: `upload_file` goes through `luml_api`
`artifacts.upload`, which reads the manifest generically and supports the dataset type
(TQ-3).

## Design prototype

The approved UI is built as a prototype in `SPEC-design/`: Vue files for the Workspace
page, the file viewer, the `.luml` view, the listing rows and the attachments view, with
stories that list every drawn state. The prototype is the reference for **how the UI
looks**: layout, spacing, colours, icons, texts and states. Copy the look, not the code
structure.

The prototype is not the reference for behaviour.

- It is not working code. It takes static props and sample data and has no API calls,
  store, routing, stream or events. Its sample names, sizes and the agent "Claude" are
  illustrative.
- Its imports point to copies of PrimeVue and of Flow's own components. Use the real ones:
  the Workspace page frame, the breadcrumb, **+ New notebook**, the "Create new notebook"
  dialog, the confirm dialog, the card, the code editor and the attachments table.
- Its syntax highlighting and its image, PDF, audio and video samples are stand-ins.
- Its **Move to…** folder field lists only sample folders.

Behaviour, data and edge cases come from this spec, and where the prototype and this text
disagree, the text wins. These are not in the prototype and are built from existing Flow
components in the same style: **Show hidden**, **Show more**, the "moved or deleted"
state, the open-notebook and unsaved-changes dialogs, the symlink mark, the note under
rename and move, and the read-only experiment route.

## Workspace page

With nothing open, the page is as today, with file rows in the listing.

- **Rows.** A file row shows an icon by preview type, the name and the size. A symlink
  gets a small link icon. A click opens the file, and the open file's row stays selected.
- **Create.** **New folder** and **New file** sit next to **+ New notebook** below the
  listing.
- **Show hidden** is a toggle in the listing header. The choice is remembered in the
  browser across reloads.
- **Show more.** When more entries exist, the listing ends with "Showing {n} of {total}
  items" and **Show more**, which appends the next page. A refresh reloads the pages
  already shown.
- **Empty directory:** "This directory is empty".

With a file open, the listing becomes a narrow column on the left and the viewer fills the
rest. Clicking another file swaps the viewer; closing the viewer gives the listing the
full width again. The directory and the open file are in the route query, so reload and
back keep the selection.

The viewer header shows the name, size, modified time and the full path with a copy
button. File actions are in the row menu, not in the header. The body depends on the file:

- a `.luml` gets the `.luml` view;
- a type the shared preview supports is shown by it, reading the file bytes endpoint;
- any other file is tried with `file.read_text` and shown as plain text if that succeeds;
- everything else gets the no-preview card: the header stays and the body says "No preview
  for this file type". The same card says "File is empty" or, over the preview size limit,
  "File is too large for preview".

Text and code previews and the plain-text fallback get **Edit**, shown only after
`file.read_text` succeeds.

The listing and the viewer refresh when the watcher reports a change.

- **File gone.** If the open file no longer exists after a refresh, the viewer keeps its
  header and the body says "This file was moved or deleted". Unsaved edits stay visible
  and copyable.
- **Unsaved edits and an operation.** Rename, move or delete of the file being edited, or
  of a folder that contains it, first asks "You have unsaved changes in {name}. Discard
  them and continue?" with **Discard and continue** and **Cancel**.

## Shared preview package

`@luml/attachments` previews files only inside its attachments tree today. It gains a
standalone preview that needs no tree, and everything below shows in the Workspace and in
Flow's and LUML's Attachments tabs alike. Those tabs get no other change.

- **Exports.** The standalone preview component, the file-type detection, and the
  extension-to-language map that the Flow editor reuses.
- **Types.** All current types stay. New: images `gif`, `webp`; text `log`; code `toml`,
  `ini`, `cfg`, `sh`, `sql`, `jsx`, `tsx`, `css`; tables `parquet`, `arrow`. Detection
  stays by extension.
- **Size.** The 10 MB preview limit stays, except for audio, video and PDF, which are
  streamed by URL, and Parquet, which is read partially.
- **Highlighting (B-12, TQ-8).** Code is shown in a read-only CodeMirror 6 view with the
  colours of Flow's editor (the `--ui-code-*` variables in
  `components/ui/code-editor/code-editor.const.ts`). Highlighted: Python, JavaScript and
  TypeScript with their JSX forms, JSON, YAML, Markdown, CSS, SQL, XML and HTML. `txt` and
  `log` stay plain monospaced text.
- **Toggles (B-13).** Markdown has Rendered (as today) and Raw (highlighted source). JSON
  and YAML have Pretty (re-formatted) and Raw (the file as on disk). The default is
  Rendered or Pretty. JSON or YAML that does not parse shows Raw with "Can't parse" and no
  toggle.
- **Tables (B-06).** Parquet is read with `hyparquet`: the schema and the first 1,000
  rows, fetching only the byte ranges it needs from the URL or blob. Arrow IPC is read
  with `apache-arrow`, first 1,000 rows. Both use the existing paginated table, with the
  footer "Showing first 1,000 of N rows" when N is known. CSV and XML are unchanged.

## `.luml` view

The view calls `file.inspect` and shows, top to bottom:

- **Actions**, in a row labelled "For full overview": for an experiment **Open in
  Experiments** and **Upload experiment to LUML**; for a model **Upload model to LUML**;
  for a dataset **Upload dataset to LUML**.
- **Data**, for a dataset only: one tab per subset / split. Each tab shows the first file
  of the split as a table, read through the archive member endpoint, with the first 1,000
  rows and the split's total rows when known.
- **Manifest:** the whole manifest as highlighted YAML.
- **Contents:** the archive's files with sizes. A click opens the file in the shared
  preview, read through the archive member endpoint.

An unknown kind shows the no-preview card.

The upload buttons open the existing `UploadModal.vue`, extended to publish a file through
`file.publish`. The artifact name defaults to the manifest's name.

## Editing

**Edit** replaces the preview with Flow's code editor, with **Cancel** and **Save** in
place of the view toggle (B-15).

- **Changed on disk.** When the file changes on disk during an edit, or a save is refused
  with `FileConflict`, a warning above the editor says "This file changed on disk after you
  started to edit it." **Overwrite** saves the person's text with force. **Reload** takes
  the file from disk and drops the edit.
- **Agent lock.** A locked file is drawn like a cell an agent works on: the card's border
  and a strip under the header take the agent's colour (the same colour the agent has on
  cells, `AGENT_COLORS` in `store/flow`), the body is dimmed and **Edit** is disabled. The
  strip says "{label} is working on this file", with the tooltip "Read-only until 3 minutes
  after the agent's last change to this file." A lock without an owner uses a neutral
  colour and "An agent is working on this file".
- **Lock during an edit.** The editor turns read-only and the strip appears. The person's
  unsaved text stays visible and copyable. When the lock ends, the changed-on-disk warning
  offers **Overwrite** and **Reload**.

## Experiment from a `.luml`

**Open in Experiments** goes to a new route under the Workspace page that takes the file's
path and renders the experiment details tabs (overview, metrics, traces, evals,
attachments) read-only (B-09, TQ-4).

- The experiment database is `exp.db.zip` in the archive: fetched through the archive
  member endpoint, unzipped, and opened in the browser with `sql.js`, as the main frontend
  does in `frontend/src/hooks/useSqlLite.ts`. It feeds the snapshot provider of
  `@luml/experiments`.
- Attachments come from `attachments.tar` and `attachments.index.json` through
  `TarAttachmentsProvider`, with byte ranges from the archive member endpoint.
- There are no rename, delete, tag or upload actions. A banner names the file.

## Row menu and dialogs

Files and folders get the notebooks' row menu with **Rename**, **Move to…** and **Delete**.
Notebooks gain **Move to…** and keep their items (B-14).

- **Rename** is inline, as in `WorkspaceFolderItemFlow.vue`.
- **Move to…** opens a dialog with a folder field and a **Move** button, disabled until a
  folder is chosen. The folder picker starts at the current directory, lists its folders,
  and can go up to the parent and into a folder, because operations work anywhere the page
  can browse.
- **New folder** and **New file** use the layout of "Create new notebook" with a required
  name. `AlreadyExists` and an invalid name show as an error under the field. A created
  file opens in the viewer.
- **Delete** asks for confirmation. The texts are in the prototype: both say the action is
  permanent, and the file text adds that cells that read the file will fail the next time
  they run.
- **Note under rename and move of a file:** "Cells that read this file by path are not
  updated."
- **Open notebooks.** On `FlowOpen` a confirm dialog says "{n} open notebook(s) will be
  closed: {names}. Running cells stop and agents working in them lose their session. Close
  and continue?" **Close and continue** repeats the call with `close_open`; **Cancel**
  changes nothing.
- **Other errors** show as an error toast: worded by kind for known kinds, the OS message
  for `OsError`.

## Dependencies

- `@luml/attachments`: `hyparquet`, `apache-arrow` (21.1.0, as the main frontend),
  `js-yaml`, and CodeMirror 6 with the language packs for the highlighted languages, as
  peer dependencies where Flow already has them.
- Flow frontend: `sql.js` and the unzip library the main frontend uses for `exp.db.zip`.
- Backend: none new (`watchdog`, `tarfile`, `fnnx` are already used).

## Trade-offs

- **CodeMirror in the shared package** makes the main LUML frontend heavier, but previews
  and the editor look the same.
- **`hyparquet` instead of `parquet-wasm`:** no wasm file to serve in two apps, partial
  reads; slower on full scans, which previews don't do.
- **Operations anywhere on disk:** consistent with browsing, but a bug can touch any file
  the user can; mitigated by `Protected` paths, name checks and confirm dialogs.
- **Lock attribution** is per lease, not per write; several agents give a generic lock.
- **`flow.rename` / `flow.delete` change behaviour** (refuse while open); the CLI sets
  `close_open` to keep today's behaviour.
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
**Then** the rename is refused with `"b.csv" already exists` and nothing changes

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

Backend tasks come first (daemon in `lumlflow/lumlflow/flow/daemon/`, tests in
`lumlflow/tests/unit/daemon/`), then frontend. Each task covers the scenarios of its area
with tests and ends with its checks passing: backend `ruff`, `mypy` and
`pytest lumlflow/tests/unit`; frontend `lint`, `type-check` and `test:ci` of every package
it touches. A task that changes `@luml/attachments` also runs `type-check`, `test:ci` and
`build` of `frontend/` (the main LUML app) and `lumlflow/frontend/`.

- [ ] List plain files in the workspace listing
  - [ ] Shared path rules (Paths): symlinks kept as links, name checks, `NotAFile`,
    `Protected` and `OsError`
  - [ ] `workspace.list` with files, hidden entries and paging (Listing); update
    `test_workspace.py`
  - [ ] Tests: invalid names, protected paths, links and broken links, hidden on and off,
    `.lumlflow` never listed, paging of 4,500 entries

- [ ] Serve file bytes and inspect and upload luml files
  - [ ] The two `GET` endpoints in `web.py`, both with `Range` (Reading files)
  - [ ] `file.inspect` and the MCP tool `file-inspect` (`mcp.py`, `test_mcp.py`)
  - [ ] `file.publish` (Uploading a `.luml` to LUML), tested with a mocked LUML client
  - [ ] Tests with small archives built by the SDK: tabular dataset, Hugging Face dataset
    if `datasets` is available in tests, experiment, model, and a tar that is not a `.luml`

- [ ] Add file and folder operations to the daemon
  - [ ] The six methods of File and folder operations, including the move across
    filesystems
  - [ ] The open-notebook rule in all of them and in `flow.rename` and `flow.delete`; the
    CLI `flow delete` keeps its behaviour
  - [ ] Tests for every *Operations* scenario the daemon decides

- [ ] Add text editing with a file watcher and agent locks to the daemon
  - [ ] `file.read_text` and `file.write_text` (Editing text files)
  - [ ] The watcher and the `files` channel of `/api/flow/stream`, with the lock rule and
    expiry (File watcher and agent locks)
  - [ ] Tests in the style of `test_cell_claims.py` and `test_stream.py`: size, text and
    conflict checks, forced write, mode kept; one agent, several agents, no agent, own
    write not locked, expiry, lease end, write refused while locked

- [ ] Extend the shared attachments preview
  - [ ] Standalone preview and the exports, new types and the size rule (Shared preview
    package)
  - [ ] Highlighting and the Rendered / Raw and Pretty / Raw toggles
  - [ ] Parquet and Arrow tables, tested with small fixtures
  - [ ] Flow's and LUML's Attachments tabs still build and pass

- [ ] Show files in the Workspace listing and open them in a viewer
  - [ ] File rows, **Show hidden**, **Show more** and the store behind them (Workspace
    page)
  - [ ] The split layout with the route query, and the viewer with all its body states
  - [ ] The `files` channel subscription: refresh on change and the "moved or deleted"
    state
  - [ ] Look as in `SPEC-design/WorkspaceFolder/` and `SPEC-design/WorkspacesPage/`

- [ ] Add the row menu and dialogs for file operations
  - [ ] Row menu, inline rename, **Move to…** with the folder picker, **Delete**, **New
    file** and **New folder** (Row menu and dialogs)
  - [ ] The open-notebook and unsaved-changes dialogs, and error toasts by kind
  - [ ] Look as in `SPEC-design/WorkspacesPage/WorkspacesPage.vue` and
    `SPEC-design/WorkspaceFolder/WorkspaceFolderItem.vue`

- [ ] Add text editing with conflict and agent lock states
  - [ ] Edit, Save and Cancel with Flow's code editor (Editing)
  - [ ] The changed-on-disk warning and the agent lock, also during an edit
  - [ ] Look as in `SPEC-design/WorkspacesPage/WorkspaceFileViewer.vue`

- [ ] Add the luml file view and upload
  - [ ] The view for experiment, model, dataset and unknown kinds (`.luml` view), tested
    per kind with a mocked `file.inspect`
  - [ ] Upload through `UploadModal.vue` for all three kinds
  - [ ] Look as in `SPEC-design/WorkspacesPage/LumlPackagePreview.vue`

- [ ] Open an experiment from a luml file read-only
  - [ ] The route, the database and attachments providers over the archive member
    endpoint, and the read-only tabs with the banner (Experiment from a `.luml`)
  - [ ] Tests with a small experiment archive fixture
