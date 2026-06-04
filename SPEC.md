# How to use this spec

This spec is intentionally **high-level**. It describes *what* to build and *how it must behave* — not the literal code. There are deliberately almost no code snippets to copy. For every part of the implementation, derive the concrete details from the **named reference file in the live codebase**, not from this document. If something here disagrees with the referenced file, the referenced file wins — follow it and flag the discrepancy.

**Backend** — Tracks is structurally a clone of the existing **Collections** feature with different fields. For each layer, open the named `collections` equivalent under `backend/luml/` and follow its exact structure, naming, imports, error handling, and conventions:

| Layer | Reference file |
|-------|----------------|
| Models | `backend/luml/models/collection.py` |
| Schemas | `backend/luml/schemas/collections.py` |
| Repository | `backend/luml/repositories/collections.py` |
| Handlers | `backend/luml/handlers/collections.py` |
| API routers | `backend/luml/api/orbits/` (router files) + `backend/luml/api/organization_routes.py` |
| Permissions | `backend/luml/schemas/permissions.py` (the `Resource.COLLECTION` wiring) |
| Migrations | latest file in `backend/migrations/versions/` |

**Frontend** — before writing any component, you **MUST do both** of the following. Do not skip either:

1. **Fetch the Figma node via the Figma MCP** (`get_design_context` **and** `get_screenshot`) for the node listed on that screen — for layout, spacing, copy, and states. A bare Figma link in this doc is **not** enough; you must actually fetch the node. If a link is attached, it is there to be opened.
2. **Open the named existing component** ("Model after:" on each screen) and reuse its structure, the same PrimeVue components, the same `:pt` styling, and the same CSS-variable tokens.

The existing component defines **how it must look in this app**; Figma defines **the specific screen**. When the two conflict on visual style, match the existing app component. **Never invent a new component, layout, or styling when a referenced one already exists** — the most common failure mode is generating generic components instead of mirroring the platform's. In particular: the Tracks entries table must look like the collection artifacts table; the track cards must look like collection cards; the drawers must look like the collection editor drawer.

---

# Proposals

**Problem**: The dataforce.studio platform stores artifacts (models, datasets, experiments) in orbit collections but provides no way to register named artifact lineages, assign lifecycle stages (Staging / Production / Archived), or retrieve the "current production model" programmatically. Teams working with ML workflows need a versioned registry comparable to MLflow's Model Registry.

**Solution**: Implement a **Tracks** feature — a named, type-scoped artifact registry per orbit. A Track holds versioned references (entries) to artifacts from the orbit's collections; each entry can carry a lifecycle stage. Tracks appear as a new **Tracks** tab in the orbit UI, alongside the existing Collections (Registry) tab.

**Why this approach**: Tracks intentionally mirror MLflow Model Registry semantics so the concept is already familiar to ML practitioners:

| MLflow              | Tracks             |
| ------------------- | ------------------ |
| Model Registry tab  | Tracks tab         |
| Registered Model    | Track              |
| Model Version+Stage | TrackArtifact + Stage |

Data is never duplicated: artifacts live in collections; track entries are references with a version and an optional stage. This fits cleanly into the existing orbit-scoped, layered architecture (models → repositories → handlers → routers).

---

# Design

## Data Models (`backend/luml/models/tracks.py`)

Follow `backend/luml/models/collection.py` exactly: SQLAlchemy 2 mapped columns, `uuid.uuid7` primary keys, `ForeignKey` with `ondelete=...` as noted below, `TimestampMixin` for `created_at`/`updated_at`, and `lazy="selectin"` relationships. Three tables.

### `tracks` (`TrackOrm`)

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, default `uuid7` |
| `orbit_id` | UUID | FK → `orbits.id` ON DELETE CASCADE, indexed |
| `name` | str | NOT NULL |
| `artifact_type` | str | NOT NULL; validated against the `ArtifactType` enum at the API layer |
| `description` | str | nullable |
| `tags` | list[str] | JSON array, default `[]` |
| `created_by` | UUID | FK → `users.id`, NOT NULL |
| `next_version` | int | default `1`, monotonically increasing, never decremented |

- DB constraint: **UNIQUE(`orbit_id`, `name`)**.
- Relationships: `orbit` (back-populates `tracks`), `entries` (cascade all/delete-orphan), `stages` (cascade all/delete-orphan).
- Expose a `total_entries` count (scalar-subquery `column_property`, same technique collections use for their counts).

### `track_entries` (`TrackArtifactOrm`) — a versioned reference to an artifact

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, default `uuid7` |
| `track_id` | UUID | FK → `tracks.id` ON DELETE CASCADE, indexed |
| `artifact_id` | UUID | FK → `artifacts.id` **ON DELETE RESTRICT**, indexed |
| `version` | int | NOT NULL; assigned from `Track.next_version` at insert |
| `stage_id` | UUID | FK → `track_stages.id` ON DELETE SET NULL, nullable |
| `added_by` | UUID | FK → `users.id`, NOT NULL |

- DB constraint: **UNIQUE(`track_id`, `artifact_id`)** — an artifact can appear in a track only once.
- DB constraint: **UNIQUE(`track_id`, `version`)** — versions are unique within a track; a safety net against any version-assignment race (see Repository Layer).
- DB **partial** unique index: **UNIQUE(`track_id`, `stage_id`) WHERE `stage_id` IS NOT NULL** — a stage can be held by at most one entry per track; enforced at DB level so concurrent PATCH requests can't assign the same stage twice. Postgres-only syntax (the platform is Postgres-only, so this is fine). Because of this index, force-reassigning a stage must **clear the old holder before** setting the new one within the same transaction (see Repository Layer) — otherwise the insert/update collides with the index.
- Because of ON DELETE RESTRICT, artifact deletion is **blocked** while any track entry references it. The artifact delete handler must check for entries first and return `409` (see Handler Layer).

### `track_stages` (`TrackStageOrm`)

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, default `uuid7` |
| `track_id` | UUID | FK → `tracks.id` ON DELETE CASCADE, indexed |
| `name` | str | NOT NULL |

- DB constraint: **UNIQUE(`track_id`, `name`)**.

**Default stages** are created automatically, in the same transaction as the track: **Staging, Pre-Production, Production, Archived**. After creation they are indistinguishable from user-created stages — no special flag.

**Stage color is NOT stored** — it is derived on the frontend by stage name (see the color rule in the Frontend section, used identically on track cards and entry badges):
- `Production` → green
- `Staging`, `Pre-Production` → orange
- all others (including `Archived` and custom stages) → blue

## Schemas (`backend/luml/schemas/tracks.py`)

Follow `backend/luml/schemas/collections.py`: Pydantic v2, inherit `BaseOrmConfig`, `StrEnum` for enums. Provide create/update/read schemas for Track, TrackEntry, and TrackStage, and a paginated entries-list schema (cursor + items). **No special schema for the stage-conflict 409** — see the note under API Routes.

## Permissions (`backend/luml/schemas/permissions.py`)

Add `TRACK = "track"` to the `Resource` enum, then wire it into both permission dicts exactly the way `Resource.COLLECTION` is wired:

| Role | Actions |
|------|---------|
| `OrgRole.OWNER` | LIST, READ, CREATE, UPDATE, DELETE |
| `OrgRole.ADMIN` | LIST, READ, CREATE, UPDATE, DELETE |
| `OrgRole.MEMBER` | — (no access via org role) |
| `OrbitRole.ADMIN` | LIST, READ, CREATE, UPDATE, DELETE |
| `OrbitRole.MEMBER` | LIST, READ, CREATE, UPDATE |

Handlers use `Resource.TRACK` with the appropriate per-endpoint `Action` via `PermissionsHandler.check_permissions(...)`, following the `CollectionHandler` usage of `Resource.COLLECTION`. Also update `PermissionsHandler.get_orbit_permissions_by_role(...)` to include `Resource.TRACK` so orbit details sent to the frontend include `permissions.track`.

## Repository Layer (`backend/luml/repositories/tracks.py`)

Follow `backend/luml/repositories/collections.py` (inherits `RepositoryBase`). Methods needed:

- **Tracks**: create; get by id; list orbit tracks with filter/sort/pagination (same as collections); update; delete (with the same delete-possibility checks collections use).
- **Stages**: create; list for track; update; delete (with in-use checks).
- **Entries** (all operations atomic): create — assign the version and bump the counter in a **single atomic statement** to avoid a read-then-write race: `UPDATE tracks SET next_version = next_version + 1 WHERE id = :track_id RETURNING next_version` (the row lock serializes concurrent inserts; the returned pre-increment value is the new entry's `version`), then insert the entry — all in one transaction. The `UNIQUE(track_id, version)` constraint is the backstop if this is ever violated. List with pagination (model on the collection-artifacts list); update entry stage; delete entry; list entries for a given artifact; check whether any entries reference a given artifact (`has_entries_for_artifact`); clear a stage from entries.
- **Force stage-reassign** (`update_entry` with `force=true`): in one transaction, **first** clear the stage from whichever entry currently holds it (`clear_stage_from_entries`), **then** set it on the target entry — never the reverse, or the partial unique index on `(track_id, stage_id)` rejects the write.

## Handler Layer (`backend/luml/handlers/tracks.py`)

Follow `backend/luml/handlers/collections.py`: dependency-injected repositories, custom exception types, `PermissionsHandler` injected as a class-level singleton. **Every method's first step is `check_permissions(org_id, user_id, Resource.TRACK, Action.X, orbit_id)`** — same signature as `CollectionHandler`.

- **TracksHandler**: `create_track` (check name uniqueness in orbit; create track + 4 default stages in one transaction), `list_tracks`, `get_track`, `update_track`, `delete_track` (cascades to entries + stages).
- **TrackEntriesHandler**: `create_entry`, `update_entry` (stage assignment, incl. the force/conflict logic — see Scenarios), `delete_entry`.
  - `create_entry` must load the artifact and validate it before inserting (do **not** guess field names — they are in `backend/luml/models/artifacts.py` / `backend/luml/schemas/artifacts.py`):
    - **Type match**: compare `ArtifactOrm.type` (a `str`) against `track.artifact_type`; on mismatch raise the existing `ArtifactTypeMismatchError` (`backend/luml/infra/exceptions.py`) → `422`. Do not invent a new exception.
    - **Same orbit**: the artifact has **no** direct `orbit_id` — it belongs to a collection (`ArtifactOrm.collection_id` → `CollectionOrm.orbit_id`). Resolve the artifact's orbit via its collection and require it equals the track's `orbit_id`; otherwise `422`.
  - `update_entry` force-reassign ordering is handled in the repo (see Repository Layer).
- **TrackStagesHandler**: `create_stage` (name uniqueness in track), `update_stage` (re-check uniqueness on rename), `delete_stage` (blocked if any entry uses it unless `force`).

**Artifact deletion integration** (`backend/luml/handlers/artifacts.py`): artifact deletion is a 3-phase flow — `request_delete_url` (the gate the UI hits; sets `PENDING_DELETION` and currently has its own inline deployment check), `confirm_deletion` and `force_delete_artifact` (both call the shared helper `_artifact_deletion_checks`). Because `track_entries.artifact_id` is `ON DELETE RESTRICT`, the row delete would otherwise fail with a raw DB `IntegrityError`. To return a clean `409` instead:
- Add a `has_entries_for_artifact` check to the shared **`_artifact_deletion_checks`** helper (covers `confirm_deletion` **and** `force_delete_artifact`) **and** to **`request_delete_url`** (it does not call that helper) — same `ApplicationError(..., 409)` style as the existing deployment check, with the message in the "Artifact deletion blocked" scenario.
- **`force_delete_artifact` is also blocked by tracks** — unlike its deployment behavior, it does **not** auto-unlink track entries. The only way to delete an artifact that is in a track is to first unlink it from every track. (Decision: keep tracks as a hard block on all delete paths.)

## API Routes (`backend/luml/api/orbits/orbit_tracks.py`)

Follow the router patterns in `backend/luml/api/orbits/` (FastAPI deps for JWT/API-key auth, orbit middleware). Register the router in `backend/luml/api/organization_routes.py` alongside the collections router. Endpoints (all orbit-scoped):

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/tracks` | create track (+ default stages) |
| GET | `/tracks` | list orbit tracks |
| GET | `/tracks/{track_id}` | get track |
| PATCH | `/tracks/{track_id}` | update track |
| DELETE | `/tracks/{track_id}` | delete track |
| POST | `/tracks/{track_id}/entries` | add entry (link artifact) |
| GET | `/tracks/{track_id}/entries` | list entries (cursor-paginated; optional `stage` filter) |
| PATCH | `/tracks/{track_id}/entries/{entry_id}` | update entry stage (optional `?force=true`) |
| DELETE | `/tracks/{track_id}/entries/{entry_id}` | unlink entry |
| POST | `/tracks/{track_id}/stages` | create stage |
| GET | `/tracks/{track_id}/stages` | list stages |
| PATCH | `/tracks/{track_id}/stages/{stage_id}` | update stage |
| DELETE | `/tracks/{track_id}/stages/{stage_id}` | delete stage (optional `?force=true`) |
| GET | `/artifacts/{artifact_id}/track-entries` | list the tracks/entries a given artifact belongs to |

**HTTP status codes follow the platform's existing conventions** — see the collections endpoints (`backend/luml/api/orbits/orbit_collections.py`): create/get/update return `200`, delete returns `204`. The codes named in the Scenarios section are the *expected outcome* of each operation; the source of truth is the platform convention, not the literal number.

**Stage-conflict 409** — the frontend keys off the **`409` status code itself** to show the force-confirm dialog. There is no structured body and no new exception class: `TrackEntriesHandler.update_entry` simply raises `ApplicationError(f"Stage '{stage_name}' is already assigned to v{held_by_version}. ...", 409)`. The global handler in `backend/luml/service.py` already serializes this to `{"detail": <message>}`, and the frontend displays that `detail` text directly in the confirm dialog (it does **not** parse `stage_name`/`held_by_version` out of separate fields). This matches how every other 409 on the platform is returned.

## Alembic Migration

Add the **next sequential** migration file under `backend/migrations/versions/` (use the existing files there as the template for style and revision chaining — do not hardcode a number from this doc). `upgrade()` creates tables in FK-dependency order: `tracks` → `track_stages` → `track_entries`, including all columns, FKs, indexes, and UNIQUE constraints (including `UNIQUE(track_id, version)` and the partial unique index on `(track_id, stage_id) WHERE stage_id IS NOT NULL`). `downgrade()` drops in reverse order.

## Frontend Architecture

Figma source file: `https://www.figma.com/design/tfEWciot1pORivAd7EEX0B`

**Reminder (see "How to use this spec"):** for every screen below, fetch the Figma node via the Figma MCP **and** open the "Model after:" component before writing code. Reuse the existing component's PrimeVue elements, `:pt`, and CSS tokens.

---

### Screens and navigation flows

#### Screen 1 — OrbitTracksView (Tracks tab on orbit page)

- **File**: `src/pages/orbits/OrbitTracksView.vue`
- **Route**: child of orbit (`name: orbit-tracks`, `path: tracks`)
- **Entry point**: "Tracks" tab in `OrbitTabs.vue`, next to "Registry" / "Deployments"
- **Model after**:
  - Card list: `src/components/orbits/tabs/registry/CollectionsList.vue` (VirtualScroller of cards) + `CollectionCard.vue`. The track card is **the exact same card as the collection card** — only the displayed fields differ. Copy `CollectionCard.vue` as the starting point and swap in the track fields (name, artifact-type badge, ID chip, "Last updated", ⚙ settings); do **not** build a new card from scratch. Keep the identical layout, markup, `:pt`/styling, and the same VirtualScroller setup from `CollectionsList.vue` — everything except the field set must match the collection card 1:1.
  - Empty state: `src/components/orbits/tabs/registry/CollectionsWelcome.vue`.
  - Search + type filter toolbar: `src/components/orbits/tabs/registry/CollectionsToolbar.vue` (IconField+InputText search, MultiSelect "Filter by type").
- **Figma (empty)**: node `4157-29128` (full node `4157:29127`) — "Registry / Tracks empty"
- **Figma (filled)**: node `4157-29586` — "Registry / Tracks Filled"
- **Figma (card)**: node `4157-29603` — same card as the collection card

**Empty state** (no tracks): heading "Get started with Tracks"; subtitle "Track your best artifacts across versions and stages — from Staging to Production."; "Create track" button (opens TrackCreator).

**Filled state**: search input (filter by name) + "Filter by type" dropdown; "Create track" button (top right); a list of track **cards** (same card component as collections), each showing track name, artifact-type badge, truncated ID chip, "Last updated X ago", and a settings (⚙) icon that opens `TrackSettingsPanel`. Clicking the card body navigates to `TrackPage`.

---

#### Screen 2 — TrackCreator (create-track modal)

- **File**: `src/components/orbits/tabs/tracks/TrackCreator.vue`
- **Trigger**: "Create track" button on OrbitTracksView
- **Model after**: `src/components/orbits/tabs/registry/CollectionCreator.vue` (centered create modal + form).
- **Figma**: node `4157-29186` — "Registry / Tracks > create new Track step 1"

Content: title "Create a new TRACK"; **Name\*** text input ("Name your track"); **Description** textarea ("Describe your track"); **Type\*** select (ArtifactType values); "Create track" button (disabled until Name + Type filled). The Figma "step 2" is just the same modal with fields filled — no separate step logic. On submit: `createTrack` → track + 4 default stages → card appears in the list.

---

#### Screen 3 — TrackSettingsPanel (per-track settings drawer)

- **File**: `src/components/orbits/tabs/tracks/TrackSettingsPanel.vue`
- **Trigger**: ⚙ icon on a track card
- **Model after**: `src/components/orbits/tabs/registry/CollectionEditor.vue` — same drawer shell (`Dialog position="topright"`, non-draggable, top-right side panel), same `@primevue/forms` Form, same `AutoComplete` tags input. Reuse its markup and styling. **Do not use `Drawer`** — it is not used in this project.
- **Figma**: node `4157-29631` — "Registry / Tracks Filled > Settings"
- **Figma (blocked-removal tooltip)**: node `4157-29657` — "Settings Message"

Sections: org-settings context (read-only, existing pattern) and "TRACK SETTINGS" with editable **Name**, **Description**, **Tags** (chips multiselect, same as the platform's existing tags), and **Stages** (chips multiselect):
- existing stages shown as removable chips, each with a × button;
- a "Type to add stages" input — typed stages are staged locally (not saved until "save changes");
- if the user tries to remove a stage that is assigned to an entry: show tooltip "This stage was linked to an artifact. To remove it, unlink the stage." and block the removal locally (no API call);
- removals of unassigned stages are staged locally.

Buttons: "delete track" (destructive) and "save changes". On save: `updateTrack` for name/description/tags; `createStage` for each new chip; `deleteStage` for each removed (unassigned) chip. On delete: confirm dialog → `deleteTrack`.

---

#### Screen 4 — TrackPage (track detail / entries list)

- **File**: `src/pages/track/TrackPage.vue`
- **Route**: `/organization/:organizationId/orbit/:id/track/:trackId`
- **Entry point**: clicking a track card
- **Model after** (important — this is the table that was previously built without looking at the reference): this is **the exact same table as the collection artifacts table** — only the columns differ. Copy `src/components/orbits/tabs/registry/collection/artifacts-table/ArtifactsTable.vue` and its column/body components (`NameColumnBody.vue`, `TypeColumnBody.vue`, `TagsList.vue`, `TableToolbar.vue`) as the starting point and swap in the Tracks columns (see below); do **not** build a new table from scratch. Keep the identical `DataTable` setup, props, `:pt`/`table-white` styling, row-click behavior, scroll/virtual-scroll config — everything except the column set must match the collection table 1:1. Breadcrumb: model after `src/components/orbits/tabs/registry/collection/CollectionBreadcrumb.vue`.
- **Figma (empty)**: node `4157-29863` — "Registry / Tracks Filled / Track Name"
- **Figma (filled)**: node `4157-29692` — "Registry / Tracks Filled / Track Name filled"

Layout: breadcrumb (Registry → [Track name]); header with track name and a "Link artifact" button (+ icon). Entries table columns: **Artifact name | Description | Stage (colored badge) | Version | Creation time**. Empty state: "Link an artifact first." Clicking a row opens `TrackArtifactPanel`.

**Stage badge color rule** (used here and on track cards), derived from stage name via CSS variables:
- `Production` → green (`--tag-success-background` `#DCFCE7` bg / `--tag-success-color` `#15803D` text)
- `Staging`, `Pre-Production` → orange (`--tag-warn-background` `#FFEDD5` bg / `--tag-warn-color` `#C2410C` text)
- all others incl. `Archived` and custom → blue (`--tag-primary-background` `#DBEAFE` bg / `--tag-primary-color` `#1D4ED8` text)

---

#### Screen 5 — TrackArtifactPanel (per-entry drawer)

- **File**: `src/components/orbits/tabs/tracks/TrackArtifactPanel.vue`
- **Trigger**: clicking a row in the TrackPage entries table
- **Model after**: `src/components/orbits/tabs/registry/CollectionEditor.vue` — same `Dialog position="topright"` drawer shell.
- **Figma flow**: `4157-29466` → `4157-29582` → `4157-29524` → `4157-30931` → `4157-57927` (panel open → stage selected → stage-conflict confirm → unlink confirm → toast)

Content: title "ARTIFACT settings"; **Name** (read-only artifact name); **Stage** dropdown (track stages + a "None" option); buttons "unlink artifact" (destructive) and "save changes".
- Save: `patchEntry` with the selected `stage_id` (or `null`). On a `409` response: show a confirm dialog whose body is the server's `detail` message verbatim (e.g. "Stage 'Production' is already assigned to v1. ...") → on confirm, repeat `patchEntry` with `?force=true`. The frontend keys off the `409` status code, not on parsing fields out of the body.
- Unlink: confirm dialog → `deleteEntry`.

---

#### Screen 6 — TrackAddEntryModal (link artifact to track)

- **File**: `src/components/orbits/tabs/tracks/TrackAddEntryModal.vue`
- **Trigger**: "Link artifact" button on TrackPage
- **Component type**: modal/dialog overlay
- **Model after**: collection dropdown → `src/components/model-upload/ModelUploadCollectionSelect.vue`; artifact cards → reuse the collection card / artifact display style already in the registry.
- **Figma flow**: `4157-29998` → `4157-30068` → `4157-30208` (select collection → artifact list → artifact selected & confirm)

Flow: title "Link a new ARTIFACT". **Collection\*** dropdown ("Select collection", lists this orbit's collections); artifact list empty until a collection is chosen; then show artifact cards filtered by the track's `artifact_type` (type badge, name, creation date, description excerpt, tags); selecting a card highlights it and enables Confirm; confirm calls `addEntry`, closes the modal, entry appears in the table. Artifacts already in the track are shown disabled ("Already in Track").

---

#### Screen 7 — Artifact detail page — Tracks section

- **File**: `src/components/orbits/tabs/tracks/ArtifactTracksWidget.vue`
- **Location**: a new "Tracks" section in the info panel of the artifact detail page — `src/pages/collection/artifact/DashboardView.vue` (match the styling of the existing info-panel sections there).
- **Figma**: node `4157-29366` — "Collection / Model details"

Content: section label "Tracks"; if the artifact is in tracks, a comma-separated list of track names; a "Link to track" button (always visible) opening `AddToTrackModal`. Calls `listArtifactEntries` on mount.

---

#### Screen 8 — AddToTrackModal (add artifact to a track, from the artifact page)

- **File**: `src/components/orbits/tabs/tracks/AddToTrackModal.vue`
- **Trigger**: "Link to track" button on the artifact detail page
- **Model after**: same modal + dropdown style as TrackAddEntryModal / `ModelUploadCollectionSelect.vue`.
- **Figma flow**: `4157-29466` → `4157-29582` (select track → confirm → done)

Content: a single-select dropdown listing tracks whose `artifact_type` matches the artifact, in the current orbit; tracks the artifact is already linked to are disabled; on confirm, `addEntry` once for the selected track, then close.

---

### Navigation flow summary (from the Figma prototype arrows)

```
OrbitTracksView (empty) → [Create track] → TrackCreator → [submit] → OrbitTracksView (card appears)
OrbitTracksView (filled) → [card ⚙] → TrackSettingsPanel ;  [card click] → TrackPage
TrackPage (empty) → [Link artifact] → TrackAddEntryModal → [select collection → artifact → confirm] → entry appears
TrackPage (filled) → [row click] → TrackArtifactPanel → [save] stage updated / [unlink] entry removed
Artifact detail → [Link to track] → AddToTrackModal → [select track + confirm] → Tracks section updates
```

---

### Frontend Framework (PrimeVue)

PrimeVue is the UI library. LLM reference: https://primevue.org/llms/llms-full.txt

Use the same PrimeVue components the reference files use; copy their props and `:pt` from those files rather than from here. Mapping of component → where used → which file to follow:

| Component | Where used | Follow |
|-----------|-----------|--------|
| `Dialog` (side panel) | TrackSettingsPanel, TrackArtifactPanel | `CollectionEditor.vue`. **Do not use `Drawer`.** |
| `Dialog` (centered) | TrackCreator, TrackAddEntryModal, AddToTrackModal | `CollectionCreator.vue` |
| `DataTable` + `Column` | TrackPage entries table | `ArtifactsTable.vue` (+ its column-body components) |
| `VirtualScroller` | OrbitTracksView card list | `CollectionsList.vue` |
| `AutoComplete` | Tags in TrackSettingsPanel | `CollectionEditor.vue` |
| `Select` | Stage dropdown; Type selects | existing single-selects |
| `MultiSelect` | "Filter by type" | `CollectionsToolbar.vue` |
| `Tag` | type badge / stage badge | colors via the stage CSS-var rule above |
| `Button` / `InputText` / `Textarea` / `Skeleton` | actions, fields, loading | `CollectionEditor.vue` and existing usage |

- **Forms**: `@primevue/forms` `Form` + `resolver` + `@submit` — follow `CollectionEditor.vue` / `CollectionCreator.vue`.
- **Confirm dialogs**: add factory functions to `src/lib/primevue/data/confirm.ts`; trigger via `useConfirm` → `confirm.require(...)`.
- **Toasts**: use `simpleSuccessToast` / `simpleErrorToast` from `src/lib/primevue/data/toasts.ts`; add helpers there as needed.

---

### API client (`frontend/src/lib/api/orbit-tracks/`)

Follow `frontend/src/lib/api/orbit-collections/` (`index.ts` class + `interfaces.ts`). Create `OrbitTracksApi` taking the shared Axios instance from `ApiClass`, and wire it in as `api.orbitTracks` in `frontend/src/lib/api/api.ts`. Mirror backend schemas in `interfaces.ts`. No special stage-conflict type is needed — the 409 body is the standard `{ detail: string }` the app already handles for every other 409.

Methods (name — purpose):
- **Tracks**: `createTrack`, `listTracks`, `updateTrack`, `deleteTrack`.
- **Entries**: `addEntry`; `listEntries` (optional `stage` filter + cursor pagination params); `patchEntry` (optional `force`); `deleteEntry`.
- **Artifact membership**: `listArtifactEntries(orgId, orbitId, artifactId)`.
- **Stages**: `createStage`, `listStages`, `updateStage`, `deleteStage` (optional `force`).

### Permissions (`frontend/src/lib/api/api.interfaces.ts`)

Add a `track` permission to the `OrbitPermissions` interface, mirroring `collection` (same `Omit<…, deploy>` shape the orbit-scoped resources use). Components read `orbitsStore.getCurrentOrbitPermissions?.track` and guard write/destructive actions with `.includes(PermissionEnum.X)` — same pattern as the `collection` checks in `CollectionEditor.vue` and `CollectionsList.vue`. Guard: `create` (Create track buttons), `update` (Save changes in TrackSettingsPanel), `delete` (Delete track; Unlink artifact).

### Pinia store (`frontend/src/stores/tracks.ts`)

Follow `frontend/src/stores/collections.ts`. State: `currentTrack`, `tracksList`, and `artifactEntries` (for ArtifactTracksWidget). Actions: CRUD for tracks, entries, and stages.

### Composables (`frontend/src/hooks/`)

Follow `frontend/src/hooks/useCollectionsList.ts`:
- `useTracksList.ts` — load + reset for the OrbitTracksView cards.
- `useTrackEntriesList.ts` — load + lazy/cursor-paginated load for the TrackPage entries table.

### Pages & components summary

| File | Purpose |
|------|---------|
| `src/pages/orbits/OrbitTracksView.vue` | track cards grid + empty state + toolbar |
| `src/pages/track/TrackPage.vue` | entries table |
| `src/components/orbits/tabs/tracks/TrackCreator.vue` | create-track modal |
| `src/components/orbits/tabs/tracks/TrackSettingsPanel.vue` | settings drawer |
| `src/components/orbits/tabs/tracks/TrackAddEntryModal.vue` | link-artifact modal |
| `src/components/orbits/tabs/tracks/TrackArtifactPanel.vue` | per-entry drawer |
| `src/components/orbits/tabs/tracks/ArtifactTracksWidget.vue` | Tracks section on artifact detail |
| `src/components/orbits/tabs/tracks/AddToTrackModal.vue` | add-to-track modal from artifact page |

### Routing & tab

In `frontend/src/router/index.ts`, follow the existing collection routes as the template and add: an orbit **child** route `path: 'tracks'`, `name: 'orbit-tracks'` (lazy-importing `OrbitTracksView.vue`); and a **top-level** track-detail route `/organization/:organizationId/orbit/:id/track/:trackId` (lazy-importing `TrackPage.vue`, with the same auth/orbit middleware meta the collection detail route uses).

In `frontend/src/components/orbits/tabs/OrbitTabs.vue`, add a "Tracks" entry to the `items` array following the existing entries (same `{ label, routeName, icon }` shape, a Lucide icon such as `GitBranch` or `Library`), placed alongside Registry/Deployments/Satellites/Secrets.

---

# Scenarios

> The scenarios below describe **operations** (create a track, add an entry, …), not HTTP routes — the canonical paths live in the API Routes table above. Status codes are the *expected outcome*; they follow platform conventions (see the note under API Routes).

## Scenario: Create track — happy path
**Given** an orbit exists with no track named "churn-model"
**When** a track is created with `{ name: "churn-model", artifact_type: "model" }`
**Then** it succeeds with a track object; `next_version=1`; 4 default stages (Staging, Pre-Production, Production, Archived) exist for the track

## Scenario: Create track — duplicate name
**Given** a track named "churn-model" already exists in the orbit
**When** a track is created with the same name
**Then** the request is rejected as a conflict (`409`); no track is created

## Scenario: Create track — invalid artifact_type
**Given** any orbit
**When** a track is created with `artifact_type: "foobar"`
**Then** the request fails validation (`422`, enum validation failure)

## Scenario: Add entry — happy path
**Given** a "model" track with `next_version=3`; a model artifact in the same orbit
**When** an entry is added for that artifact
**Then** it succeeds with `version=3`; track `next_version` becomes `4`; `stage_id=null`

## Scenario: Add entry — wrong artifact type
**Given** a track with `artifact_type="model"`
**When** an entry is added for an artifact that is a `dataset`
**Then** the request fails validation (`422`) with a message indicating the type mismatch

## Scenario: Add entry — artifact from different orbit
**Given** artifact belongs to orbit B; track belongs to orbit A
**When** an entry is added for that artifact
**Then** the request fails validation (`422`) indicating the artifact must belong to the same orbit

## Scenario: Add entry — artifact already in track
**Given** artifact is already an entry in the track
**When** an entry is added for the same artifact
**Then** the request is rejected as a conflict (`409`)

## Scenario: Version monotonicity after deletion
**Given** track has entries v1, v2, v3; entry v2 is deleted
**When** a new artifact is added to the track
**Then** new entry receives `version=4` (version 2 is never recycled)

## Scenario: Assign stage — free stage
**Given** entry v2 has no stage; stage "Staging" exists and is unassigned
**When** entry v2's stage is set to "Staging"
**Then** it succeeds; entry v2 has stage "Staging"

## Scenario: Assign stage — stage already taken, no force
**Given** entry v1 holds stage "Production"; entry v2 has no stage
**When** entry v2's stage is set to "Production" without force
**Then** the request is rejected as a conflict (`409`) whose `detail` message names the stage and the holding version (e.g. "Stage 'Production' is already assigned to v1. ..."); no entries modified

## Scenario: Assign stage — stage already taken, with force
**Given** entry v1 holds stage "Production"; entry v2 has no stage
**When** entry v2's stage is set to "Production" with force
**Then** it succeeds; entry v2 stage = "Production"; entry v1 stage = null

## Scenario: Remove stage from entry
**Given** entry v3 holds stage "Staging"
**When** entry v3's stage is set to null
**Then** it succeeds; entry v3 stage = null; stage "Staging" is free

## Scenario: Delete entry with active stage
**Given** entry v3 holds stage "Production"
**When** entry v3 is deleted
**Then** the entry is removed; stage "Production" record still exists but is unassigned

## Scenario: Delete entry does not affect artifact
**Given** entry v1 references artifact A; artifact A is in its collection
**When** entry v1 is deleted
**Then** artifact A remains in its collection; only the track entry is removed

## Scenario: Delete stage in use — without force
**Given** stage "Staging" is assigned to entry v1
**When** the stage is deleted without force
**Then** the request is rejected as a conflict (`409`)

## Scenario: Delete stage in use — with force
**Given** stage "Staging" is assigned to entry v1
**When** the stage is deleted with force
**Then** it succeeds; stage deleted; entry v1 `stage_id = null`

## Scenario: Delete stage not in use
**Given** stage "Archived" is not assigned to any entry
**When** the stage is deleted
**Then** it succeeds; stage deleted; no entries affected

## Scenario: SDK — filter entries by stage
**Given** track "churn-model" has entry v2 with stage "Production" and entry v1 with no stage
**When** entries are listed filtered by stage "Production"
**Then** the response contains only v2

## Scenario: Artifact deletion blocked when referenced by track
**Given** artifact A is referenced by at least one track entry
**When** the artifact is deleted
**Then** the request is rejected as a conflict (`409`) with message "Artifact is referenced by one or more tracks. Remove it from all tracks before deleting."; artifact is not deleted

## Scenario: Artifact force-delete also blocked when referenced by track
**Given** artifact A is referenced by at least one track entry
**When** the artifact is force-deleted (`force_delete_artifact`)
**Then** the request is rejected as a conflict (`409`) — force-delete does **not** auto-unlink track entries; the artifact must be unlinked from all tracks first

## Scenario: Artifact deletion succeeds when not in any track
**Given** artifact B has no track entries
**When** the artifact is deleted
**Then** it succeeds; artifact deleted normally

## Scenario: Delete track cascades
**Given** track has 5 entries and 4 stages (including custom)
**When** the track is deleted
**Then** the track, all 5 entries, and all 4 stages are deleted; referenced artifacts are unaffected

## Scenario: Stage belongs to different track
**Given** entry belongs to track A; a `stage_id` that belongs to track B
**When** the entry's stage is set to that `stage_id`
**Then** the request fails validation (`422`) indicating the stage does not belong to this track

## Scenario: Entries list pagination
**Given** a track with 50 entries; the first page was returned with a cursor token
**When** the next page is requested with that cursor and `page_size=20`
**Then** the next 20 entries are returned; the list cursor is non-null if more exist, null on the last page

## Scenario: Artifact track membership endpoint
**Given** artifact A is in tracks "churn-model" (v2, Production) and "risk-model" (v1, no stage) within orbit O
**When** the artifact's track memberships are listed
**Then** a list of 2 entries is returned, each including track_id, version, and stage

## Scenario: Orbit Tracks tab visible
**Given** user is on the orbit page
**When** page loads
**Then** "Tracks" tab appears in `OrbitTabs.vue` alongside Registry, Deployments, Satellites, Secrets

## Scenario: OrbitTracksView — empty state
**Given** orbit has no tracks
**When** user opens the Tracks tab
**Then** heading "Get started with Tracks" and subtitle are shown; "Create track" button is visible; no cards

## Scenario: TrackCreator — submit disabled until required fields filled
**Given** TrackCreator modal is open
**When** Name is empty or Type is not selected
**Then** "Create track" button is disabled

## Scenario: TrackPage — entries table with stage badges
**Given** track has entries: Model A (Pre-Production), TEST MODEL (Production), 19/09-21V6 (Staging), 19/09-21V5 (Archived)
**When** TrackPage loads
**Then** table shows all 4 entries; Production badge is green, Pre-Production and Staging badges are orange, Archived badge is blue

## Scenario: TrackArtifactPanel — stage conflict confirmation
**Given** entry v1 holds stage "Production"; user opens TrackArtifactPanel for entry v2 and assigns "Production"
**When** "save changes" is clicked
**Then** `patchEntry` is called without force → `409` returned; PrimeVue ConfirmDialog shown: "Stage 'Production' is already assigned to v1. Move it here?"; user confirms → `patchEntry` called again with `?force=true` → `200`; panel closes

## Scenario: TrackSettingsPanel — stage removal blocked when in use
**Given** stage "Production" is assigned to entry v2; user tries to remove "Production" chip
**When** user clicks × on the Production chip in TrackSettingsPanel
**Then** tooltip appears: "This stage was linked to an artifact. To remove it, unlink the stage."; chip is not removed; no API call is made

## Scenario: TrackSettingsPanel — save stages batch
**Given** user adds "QA" chip and removes "Archived" chip (unassigned); clicks "save changes"
**When** "save changes" is clicked
**Then** `createStage` called for "QA"; `deleteStage` called for "Archived"; `updateTrack` called for name/description/tags

## Scenario: Artifact page Tracks widget — not in any track
**Given** artifact has no track entries
**When** artifact detail page is viewed
**Then** "Tracks" section shows "Link to track" button; no track names listed

## Scenario: Artifact page Tracks widget — already in tracks
**Given** artifact is in tracks "churn-model" and "risk-model"
**When** artifact detail page is viewed
**Then** "Tracks" section lists "churn-model, risk-model"; "Link to track" button is visible

## Scenario: Add to Track from artifact page — type mismatch
**Given** artifact is of type "dataset"; only "model" tracks exist in the orbit
**When** user opens AddToTrackModal from the artifact page
**Then** dropdown is empty (all tracks filtered out by mismatched type)

## Scenario: TrackAddEntryModal — artifact already in track shown disabled
**Given** artifact "Model A" is already an entry in track T; user opens TrackAddEntryModal for track T
**When** artifact list is shown
**Then** "Model A" card is visually disabled; cannot be selected

---

# Tasks

- [x] **Task 1: Backend models + Alembic migration**
  - [x] Create `backend/luml/models/tracks.py` with `TrackOrm` (incl. `tags` JSON column), `TrackArtifactOrm`, `TrackStageOrm`, following `backend/luml/models/collection.py`
  - [x] Add the `tracks` relationship to `OrbitOrm` in `backend/luml/models/orbit.py`
  - [x] Add the next sequential migration under `backend/migrations/versions/` creating `tracks` → `track_stages` → `track_entries` (all columns, FKs, indexes, UNIQUE constraints incl. `UNIQUE(track_id, version)` and the partial unique index on `(track_id, stage_id)`); `downgrade()` drops in reverse

- [x] **Task 2: Backend schemas + repository layer**
  - [x] Create `backend/luml/schemas/tracks.py` following `backend/luml/schemas/collections.py` (incl. `tags`, paginated entries list; no stage-conflict schema — the 409 is a plain `{detail}` message)
  - [x] Create `backend/luml/repositories/tracks.py` with all methods incl. `list_entries_for_artifact`, `has_entries_for_artifact`, `clear_stage_from_entries`, and paginated `list_entries`. Entry create must assign `version` atomically (`UPDATE tracks SET next_version = next_version + 1 ... RETURNING` + insert in one transaction); force stage-reassign must clear the old holder **before** setting the target, in one transaction
  - [x] Integration tests in `tests/integration/repository/test_tracks.py`: create/list/get/update/delete track; create/list stages; add/list/patch/delete entries; `list_entries_for_artifact`; `has_entries_for_artifact`; `clear_stage_from_entries`; pagination; version monotonicity after deletion (versions never recycled); force stage-reassign (old holder cleared, target set)

- [x] **Task 3: Backend handlers + API routers**
  - [x] Add `TRACK = "track"` to `Resource` in `backend/luml/schemas/permissions.py`; wire `Resource.TRACK` into both permission dicts per the Permissions table
  - [x] Create `backend/luml/handlers/tracks.py` (`TracksHandler`, `TrackEntriesHandler`, `TrackStagesHandler`) following `backend/luml/handlers/collections.py`; permission check first in every method; correct HTTP errors incl. stage-from-wrong-track 422 and stage conflict 409. `create_entry` must validate the artifact: type match (`ArtifactOrm.type` vs `track.artifact_type` → reuse `ArtifactTypeMismatchError`, 422) and same-orbit (artifact's orbit via `collection_id → CollectionOrm.orbit_id` vs `track.orbit_id` → 422)
  - [x] Create `backend/luml/api/orbits/orbit_tracks.py` with all endpoints (incl. `GET /tracks/{track_id}`, cursor-paginated entries, `GET /artifacts/{artifact_id}/track-entries`); proper auth deps
  - [x] Register the tracks router in `backend/luml/api/organization_routes.py`
  - [x] Add the `has_entries_for_artifact` `409` check to `backend/luml/handlers/artifacts.py` in **both** the shared `_artifact_deletion_checks` helper (covers `confirm_deletion` + `force_delete_artifact`) and `request_delete_url`; force-delete stays blocked (no auto-unlink)
  - [x] Unit tests in `tests/unit/handlers/test_tracks.py` covering all happy paths and error cases from Scenarios

- [x] **Task 4: Frontend API client + Pinia store + composables**
  - [x] Add `track` to `OrbitPermissions` in `frontend/src/lib/api/api.interfaces.ts` (mirror `collection`)
  - [x] Create `frontend/src/lib/api/orbit-tracks/interfaces.ts` (standard `{detail}` for the 409 — no stage-conflict shape) and `index.ts` (`OrbitTracksApi` with all methods), following `frontend/src/lib/api/orbit-collections/`
  - [x] Wire `orbitTracks` into `ApiClass` in `frontend/src/lib/api/api.ts`
  - [x] Create `frontend/src/stores/tracks.ts` (tracks/entries/stages CRUD; `artifactEntries`) following `stores/collections.ts`
  - [x] Create `frontend/src/hooks/useTracksList.ts` and `useTrackEntriesList.ts` following `hooks/useCollectionsList.ts`

- [x] **Task 5: Frontend routing + OrbitTracksView + TrackCreator**
  - [x] Add the `orbit-tracks` child route and the top-level track-detail route in `frontend/src/router/index.ts` (follow the collection routes)
  - [x] Add the "Tracks" tab to `items` in `frontend/src/components/orbits/tabs/OrbitTabs.vue` (Lucide icon)
  - [x] Create `frontend/src/pages/orbits/OrbitTracksView.vue` — model after `CollectionsList.vue`/`CollectionCard.vue` (cards), `CollectionsWelcome.vue` (empty), `CollectionsToolbar.vue` (search + filter)
  - [x] Create `frontend/src/components/orbits/tabs/tracks/TrackCreator.vue` — model after `CollectionCreator.vue`

- [x] **Task 6: TrackPage + TrackSettingsPanel + TrackArtifactPanel**
  - [x] Create `frontend/src/pages/track/TrackPage.vue` — entries table modeled after `artifacts-table/ArtifactsTable.vue` (and its column-body components); breadcrumb after `CollectionBreadcrumb.vue`; stage badge colors per the rule; row click opens `TrackArtifactPanel`
  - [x] Create `frontend/src/components/orbits/tabs/tracks/TrackSettingsPanel.vue` — model after `CollectionEditor.vue` (Dialog topright + Form + AutoComplete tags); Stages chips with in-use removal blocked + tooltip; delete/save (batch stage create/delete + `updateTrack`)
  - [x] Create `frontend/src/components/orbits/tabs/tracks/TrackArtifactPanel.vue` — model after `CollectionEditor.vue` drawer; read-only name, Stage select (+ "None"), unlink/save (with 409 force-confirm flow)

- [ ] **Task 7: TrackAddEntryModal + artifact page Tracks section + AddToTrackModal**
  - [ ] Create `frontend/src/components/orbits/tabs/tracks/TrackAddEntryModal.vue` — collection dropdown after `ModelUploadCollectionSelect.vue`; artifact cards filtered by `artifact_type` (already-in-track disabled); confirm → `addEntry`
  - [ ] Create `frontend/src/components/orbits/tabs/tracks/ArtifactTracksWidget.vue` — "Tracks" section in `pages/collection/artifact/DashboardView.vue` (match existing info-panel section styling); `listArtifactEntries` on mount; comma-separated names; "Link to track" button
  - [ ] Create `frontend/src/components/orbits/tabs/tracks/AddToTrackModal.vue` — single-select dropdown of matching-type tracks (already-linked disabled); confirm → `addEntry`
