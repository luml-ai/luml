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

## Data Models (`luml/models/tracks.py`)

All three classes follow the exact patterns in `luml/models/collection.py`: SQLAlchemy 2 mapped columns, `uuid.uuid7` primary keys, `ForeignKey` with `ondelete="CASCADE"` where appropriate, `TimestampMixin` for `created_at`/`updated_at`, and `lazy="selectin"` relationships.

### `TrackOrm`

```python
class TrackOrm(TimestampMixin, Base):
    __tablename__ = "tracks"

    id:            Mapped[uuid.UUID]       # PK, default uuid7
    orbit_id:      Mapped[uuid.UUID]       # FK → orbits.id ON DELETE CASCADE, index=True
    name:          Mapped[str]             # NOT NULL
    artifact_type: Mapped[str]             # NOT NULL; validated against ArtifactType enum at API layer
    description:   Mapped[str | None]
    tags:          Mapped[list[str]]       # JSON array, default []
    created_by:    Mapped[uuid.UUID]       # FK → users.id, NOT NULL
    next_version:  Mapped[int]             # default 1, never decremented

    orbit:   Mapped["OrbitOrm"]            # relationship back_populates="tracks"
    entries: Mapped[list["TrackArtifactOrm"]] # cascade="all, delete, delete-orphan"
    stages:  Mapped[list["TrackStageOrm"]] # cascade="all, delete, delete-orphan"

    total_entries = column_property(...)   # scalar subquery count of TrackArtifactOrm rows

# DB constraint: UNIQUE(orbit_id, name)
```

### `TrackArtifactOrm`

```python
class TrackArtifactOrm(TimestampMixin, Base):
    __tablename__ = "track_entries"

    id:            Mapped[uuid.UUID]        # PK, default uuid7
    track_id:      Mapped[uuid.UUID]        # FK → tracks.id ON DELETE CASCADE, index=True
    artifact_id:   Mapped[uuid.UUID]        # FK → artifacts.id ON DELETE RESTRICT, index=True
    version:       Mapped[int]              # NOT NULL; assigned from Track.next_version at insert
    stage_id:      Mapped[uuid.UUID | None] # FK → track_stages.id ON DELETE SET NULL, nullable
    added_by:      Mapped[uuid.UUID]        # FK → users.id, NOT NULL

    track:    Mapped["TrackOrm"]
    artifact: Mapped["ArtifactOrm"]
    stage:    Mapped["TrackStageOrm | None"]

# DB constraint: UNIQUE(track_id, artifact_id)
# DB partial unique index: UNIQUE(track_id, stage_id) WHERE stage_id IS NOT NULL
#   enforced at DB level to prevent concurrent PATCH requests from assigning the same stage twice
# Artifact deletion is BLOCKED (ON DELETE RESTRICT) while any track entry references it.
# The artifact delete handler must check for track entries first and raise 409 if any exist.
```

### `TrackStageOrm`

```python
class TrackStageOrm(TimestampMixin, Base):
    __tablename__ = "track_stages"

    id:       Mapped[uuid.UUID]      # PK, default uuid7
    track_id: Mapped[uuid.UUID]      # FK → tracks.id ON DELETE CASCADE, index=True
    name:     Mapped[str]            # NOT NULL

    track:   Mapped["TrackOrm"]
    entries: Mapped[list["TrackArtifactOrm"]]

# DB constraint: UNIQUE(track_id, name)
```

**Default stages** created automatically when a new track is created (in the same transaction): Staging, Pre-Production, Production, Archived. After creation they are indistinguishable from user-created stages — no special flag.

Color is **not stored in the DB** — it is derived on the frontend by stage name:
- `Production` → green ( var(--tag-success-background, #DCFCE7); bg / color: var(--tag-success-color, #15803D); text)
- `Staging`, `Pre-Production` → orange (var(--tag-warn-background, #FFEDD5); bg / var(--tag-warn-color, #C2410C); text)
- all others (including `Archived` and custom stages) → blue ( var(--tag-primary-background, #DBEAFE); bg /  var(--tag-primary-color, #1D4ED8); text)

## Schemas (`luml/schemas/tracks.py`)

All schemas follow `luml/schemas/collections.py` patterns: Pydantic v2, inherit from `BaseOrmConfig`, use `StrEnum` for enums.

### Track schemas

```python
class TrackCreate(BaseOrmConfig):
    name: str
    artifact_type: ArtifactType   # from luml.schemas.artifacts
    description: str | None = None
    tags: list[str] = []

class Track(BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    name: str
    artifact_type: ArtifactType
    description: str | None
    tags: list[str]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    total_entries: int

class TrackUpdate(BaseOrmConfig):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None

class TracksList(BaseModel):
    items: list[Track]
    cursor: str | None
```

### TrackArtifact schemas

```python
class TrackArtifactCreate(BaseOrmConfig):
    artifact_id: UUID

class TrackArtifactStage(BaseOrmConfig):
    id: UUID
    name: str

class TrackArtifact(BaseOrmConfig):
    id: UUID
    track_id: UUID
    artifact_id: UUID
    version: int
    stage: TrackArtifactStage | None
    created_at: datetime        # = added_at; from TimestampMixin
    added_by: UUID

class TrackArtifactUpdate(BaseOrmConfig):
    stage_id: UUID | None       # None = remove stage

class TrackStageConflict(BaseOrmConfig):
    stage_name: str
    held_by_version: int         # version number of the entry currently holding the stage

class TrackArtifactUpdateResponse(BaseOrmConfig):
    entry: TrackArtifact

class TrackEntriesList(BaseModel):
    items: list[TrackArtifact]
    cursor: str | None
```

### TrackStage schemas

```python
class TrackStageCreate(BaseOrmConfig):
    name: str

class TrackStage(BaseOrmConfig):
    id: UUID
    track_id: UUID
    name: str
    created_at: datetime

class TrackStageUpdate(BaseOrmConfig):
    name: str | None = None

class TrackStagesList(BaseModel):
    items: list[TrackStage]
    cursor: str | None
```

## Permissions (`luml/schemas/permissions.py`)

Add `TRACK = "track"` to the `Resource` enum. Then add `Resource.TRACK` to every role in both permission dicts, following the same pattern as `Resource.COLLECTION`:

| Role | Actions |
|------|---------|
| `OrgRole.OWNER` | LIST, READ, CREATE, UPDATE, DELETE |
| `OrgRole.ADMIN` | LIST, READ, CREATE, UPDATE, DELETE |
| `OrgRole.MEMBER` | — (no access via org role) |
| `OrbitRole.ADMIN` | LIST, READ, CREATE, UPDATE, DELETE |
| `OrbitRole.MEMBER` | LIST, READ, CREATE, UPDATE |

Handlers use `Resource.TRACK` with the appropriate per-endpoint `Action` via `PermissionsHandler.check_permissions(...)`, following the existing `CollectionHandler` pattern for `Resource.COLLECTION` (for example, list endpoints use `Action.LIST`).

Also update `PermissionsHandler.get_orbit_permissions_by_role(...)` to include `Resource.TRACK` in the fixed set of resources it returns for orbit permissions (alongside `orbit`, `orbit_user`, `artifact`, `collection`, `satellite`, `orbit_secret`, and `deployment`), so orbit details sent to the frontend include `permissions.track`.

## Repository Layer (`luml/repositories/tracks.py`)

Follows the pattern in `luml/repositories/collections.py` (inherits `RepositoryBase`).

Methods:

```python
# Tracks
async def create_track(session, data: TrackCreate, orbit_id, user_id) -> TrackOrm
async def get_track(session, track_id) -> TrackOrm | None
async def list_tracks(session, orbit_id) -> list[TrackOrm]
async def update_track(session, track: TrackOrm, data: TrackUpdate) -> TrackOrm
async def delete_track(session, track: TrackOrm) -> None

# Stages
async def create_stage(session, track_id, data: TrackStageCreate) -> TrackStageOrm
async def get_stage(session, stage_id) -> TrackStageOrm | None
async def list_stages(session, track_id) -> list[TrackStageOrm]
async def update_stage(session, stage: TrackStageOrm, data: TrackStageUpdate) -> TrackStageOrm
async def delete_stage(session, stage: TrackStageOrm) -> None
async def clear_stage_from_entries(session, stage_id) -> None   # nulls stage_id on all entries

# Entries — all operations are atomic
async def add_entry(session, track: TrackOrm, artifact_id, user_id) -> TrackArtifactOrm
    # assigns version=track.next_version; increments track.next_version atomically
async def get_entry(session, entry_id) -> TrackArtifactOrm | None
async def list_entries(session, track_id, stage_name: str | None = None, cursor: Cursor | None = None, page_size: int = 20) -> list[TrackArtifactOrm]
async def get_entry_holding_stage(session, track_id, stage_id) -> TrackArtifactOrm | None
async def update_entry_stage(session, entry: TrackArtifactOrm, stage_id: UUID | None) -> TrackArtifactOrm
async def delete_entry(session, entry: TrackArtifactOrm) -> None
async def list_entries_for_artifact(session, orbit_id, artifact_id) -> list[TrackArtifactOrm]
    # returns all entries across all tracks in this orbit that reference artifact_id
async def has_entries_for_artifact(session, artifact_id) -> bool
    # used by artifact delete handler to check if deletion is blocked
```

## Handler Layer (`luml/handlers/tracks.py`)

Follows `luml/handlers/collections.py` pattern: dependency-injected repositories, custom exception types, `PermissionsHandler` injected as class-level singleton.

**Every method calls `check_permissions(org_id, user_id, Resource.TRACK, Action.X, orbit_id)` as its first step** — same signature as in `CollectionHandler`. The action mapping:

| Method | Action |
|--------|--------|
| `create_track`, `add_entry`, `create_stage` | `Action.CREATE` |
| `list_tracks`, `list_entries`, `list_stages` | `Action.LIST` |
| `get_track` | `Action.READ` |
| `update_track`, `patch_entry`, `update_stage` | `Action.UPDATE` |
| `delete_track`, `delete_entry`, `delete_stage` | `Action.DELETE` |

**`TracksHandler`**
- `create_track(user_id, org_id, orbit_id, data)`: check permissions; validate orbit exists and belongs to org; validate `data.artifact_type` ∈ `ArtifactType`; check name uniqueness in orbit; create track + 4 default stages in single transaction
- `list_tracks(user_id, org_id, orbit_id)`: check permissions; validate orbit; return list
- `get_track(user_id, org_id, orbit_id, track_id)`: check permissions; validate track belongs to orbit
- `update_track(user_id, org_id, orbit_id, track_id, data)`: check permissions; validate; if name changes check uniqueness
- `delete_track(user_id, org_id, orbit_id, track_id)`: check permissions; validate; delete (cascades to entries + stages)

**`TrackEntriesHandler`**
- `add_entry(user_id, org_id, orbit_id, track_id, artifact_id)`:
  1. `check_permissions(..., Action.CREATE)`
  2. Validate track belongs to orbit
  3. Validate artifact exists and `artifact.orbit_id == orbit_id`
  4. Validate `artifact.type == track.artifact_type` → raise `422` if mismatch
  5. Check no existing entry for `(track_id, artifact_id)` → raise `409` if duplicate
  6. Atomically: set `entry.version = track.next_version`, `track.next_version += 1`, insert entry
- `patch_entry(user_id, org_id, orbit_id, track_id, entry_id, stage_id, force: bool = False)`:
  1. `check_permissions(..., Action.UPDATE)`
  2. Validate entry belongs to track
  3. If `stage_id` is not None: validate stage belongs to track
  4. Check for existing entry holding `stage_id` in this track
  5. If found and `force=False` → raise `409 Conflict` with `TrackStageConflict` body (stage_name, held_by_version)
  6. If found and `force=True` → set that entry's `stage_id = None`
  7. Update entry's `stage_id`; return `TrackArtifactUpdateResponse`
- `delete_entry(user_id, org_id, orbit_id, track_id, entry_id)`: check permissions (`Action.DELETE`); validate; delete

**`TrackStagesHandler`**
- `create_stage(user_id, org_id, orbit_id, track_id, data)`: check permissions (`Action.CREATE`); check name uniqueness in track
- `update_stage(user_id, org_id, orbit_id, track_id, stage_id, data)`: check permissions (`Action.UPDATE`); if name changes, check uniqueness
- `delete_stage(user_id, org_id, orbit_id, track_id, stage_id, force)`: check permissions (`Action.DELETE`); count entries using this stage; if count > 0 and not force → raise `409`; otherwise delete (DB `ON DELETE SET NULL` clears entries automatically)

**Artifact deletion integration** (`luml/handlers/artifacts.py`):
- In the existing artifact delete handler, **before** deleting, call `repo.has_entries_for_artifact(session, artifact_id)`. If `True` → raise `409 Conflict` with message "Artifact is referenced by one or more tracks. Remove it from all tracks before deleting."

## API Routes (`luml/api/orbits/orbit_tracks.py`)

Router prefix: `/{organization_id}/orbits/{orbit_id}` (registered under `/v1/organizations` in `organization_routes.py`).

```
# Tracks
POST   /tracks                                      → 200 Track
GET    /tracks                                      → 200 TracksList
GET    /tracks/{track_id}                           → 200 Track
PATCH  /tracks/{track_id}                           → 200 Track
DELETE /tracks/{track_id}                           → 204

# Entries
POST   /tracks/{track_id}/entries                   → 200 TrackArtifact
GET    /tracks/{track_id}/entries                   → 200 TrackEntriesList
       query param: ?stage=<stage_name>             (filter by stage name)
       query param: ?cursor=<str>&page_size=<int>   (cursor pagination, default page_size=20)
PATCH  /tracks/{track_id}/entries/{entry_id}        → 200 TrackArtifactUpdateResponse
       query param: ?force=true                     (evict stage from current holder; without it → 409 if taken)
DELETE /tracks/{track_id}/entries/{entry_id}        → 204

# Artifact track membership (for artifact detail page widget)
GET    /artifacts/{artifact_id}/track-entries       → 200 TrackEntriesList
       returns all entries referencing this artifact across all tracks in this orbit

# Stages
POST   /tracks/{track_id}/stages                    → 200 TrackStage
GET    /tracks/{track_id}/stages                    → 200 TrackStagesList
PATCH  /tracks/{track_id}/stages/{stage_id}         → 200 TrackStage
DELETE /tracks/{track_id}/stages/{stage_id}         → 204 (or 409 without ?force=true)
       query param: ?force=true
```

Register in `luml/api/organization_routes.py`:

```python
from luml.api.orbits.orbit_tracks import tracks_router
organization_all_routers.include_router(tracks_router)
```

## Alembic Migration

File: `backend/migrations/versions/033_add_tracks_tables.py`

`upgrade()` creates tables in order: `tracks` → `track_stages` → `track_entries` (respects FK dependencies).
`downgrade()` drops in reverse order.

Include all columns, FKs, indexes, and UNIQUE constraints defined in the data model.

## Frontend Architecture

Figma source: `https://www.figma.com/design/tfEWciot1pORivAd7EEX0B`

---

### Screens and navigation flows

All screens, their locations, triggers, and content are derived directly from Figma.

#### Screen 1 — OrbitTracksView (Tracks tab on orbit page)

**File**: `src/pages/orbits/OrbitTracksView.vue`
**Route**: child of orbit (`name: orbit-tracks`, `path: tracks`)
**Entry point**: "Tracks" tab in `OrbitTabs.vue`, next to "Collections"
**Figma (empty)**: link only to section updated!: https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29128&m=dev (full node:  node `4157:29127` )  — "Registry / Tracks empty"  
**Figma (filled)**:  Registry / Tracks Filled"  https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29586&m=dev

**Empty state** (no tracks yet):
- Heading: "Get started with Tracks"
- Subtitle: "Track your best artifacts across versions and stages — from Staging to Production."
- Button: "Create track" (opens TrackCreator modal)

**Filled state** (tracks exist):
- Search input (filter by name) + "Filter by type" dropdown
- "Create track" button (top right)
- Track **cards** (not a table) figma ard url: @https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29603&m=dev (the same card as collection card) — each card shows:
  - Track name (e.g. "DataTeam Track")
  - Artifact type badge (e.g. "Model")
  - ID chip (truncated UUID)
  - "Last updated X hours ago"
  - Settings (⚙) icon → opens `TrackSettingsPanel` (sidebar drawer)
- Click track card body → navigates to `TrackPage`

---

#### Screen 2 — TrackCreator (modal, 2 visual steps)

**File**: `src/components/orbits/tabs/tracks/TrackCreator.vue`
**Trigger**: "Create track" button on OrbitTracksView
**Figma**: @https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29186&m=dev — "Registry / Tracks > create new Track step 1"

**Content**:
- Title: "CREATE A NEW TRACK"
- Field: **Name*** — text input, placeholder "Name your track"
- Field: **Description** — textarea, placeholder "Describe your track"
- Field: **Type*** — select dropdown (ArtifactType enum values)
- Button: "Create track" (primary, disabled until Name + Type filled)

Step 2 in Figma = same modal with fields filled — no separate step logic needed, just form state.

On submit: calls `createTrack` → creates track + 4 default stages → track card appears in list.

---

#### Screen 3 — TrackSettingsPanel (sidebar/drawer per track)

**File**: `src/components/orbits/tabs/tracks/TrackSettingsPanel.vue`
**Trigger**: Settings (⚙) icon on a track card in OrbitTracksView
**Component type**: `Dialog` with `position="topright"` (same pattern as `CollectionEditor.vue`)
**Figma**: @https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29631&m=dev — "Registry / Tracks Filled > Settings"
**Figma (tooltip/blocked removal)**: node @https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29657&m=dev — "Registry / Tracks Filled > Settings Message"

**Content** (two sections):
- Section "Organization settings" — (read-only org context, existing pattern)
- Section "TRACK SETTINGS":
  - **Name** — editable text input (pre-filled with track name)
  - **Description** — textarea (pre-filled)
  - **Tags** — chips multiselect; follows the same pattern as the existing tags implementation in the platform
  - **Stages** — chips multiselect:
    - Shows existing stages as removable chips (e.g. Production, Pre-Production)
    - Each chip has a × remove button
    - Text input: "Type to add stages" — stages typed here are staged locally (not saved yet)
    - If user tries to remove a stage that is assigned to an entry: show tooltip "This stage was linked to an artifact. To remove it, unlink the stage." Block the removal locally without calling the API
    - Removals of unassigned stages are staged locally
- Buttons: "delete track" (destructive, red), "save changes"

On "save changes": calls `updateTrack` (name/description/tags); for stages — calls `createStage` for each newly added chip, calls `deleteStage` for each removed chip (only unassigned ones can be removed, see tooltip above).
On "delete track": PrimeVue ConfirmDialog → `deleteTrack`.

---

#### Screen 4 — TrackPage (track detail / entries list)

**File**: `src/pages/track/TrackPage.vue`
**Route**: `/organization/:organizationId/orbit/:id/track/:trackId`
**Entry point**: clicking a track card on OrbitTracksView
**Figma (empty)**: @https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29863&m=dev — "Registry / Tracks Filled / Track Name"
**Figma (filled)**: @https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29692&m=dev — "Registry / Tracks Filled / Track Name filled"

**Layout**:
- Breadcrumb: Registry → [Track name]
- Header: track name, "Link artifact" button (+ icon), optional secondary action buttons

**Entries table** columns: Artifact name | Description | Stage (colored badge) | Version | Creation time

**Empty state**: "Link an artifact first."

**Filled state** — example entries:

| Artifact name | Stage | Version |
|---|---|---|
| Model A | Pre-Production | v1 |
| TEST MODEL | Production | v2 |
| 19/09-21V6 | Staging | v6 |
| 19/09-21V5 | Archived | v5 |

- Clicking any row → opens `TrackArtifactPanel` (sidebar)
- Stage badge colors:
  - `Production` → green ( var(--tag-success-background, #DCFCE7); bg / color: var(--tag-success-color, #15803D); text)
  - `Staging`, `Pre-Production` → orange (var(--tag-warn-background, #FFEDD5); bg / var(--tag-warn-color, #C2410C); text)
  - all others (including `Archived` and custom stages) → blue ( var(--tag-primary-background, #DBEAFE); bg /  var(--tag-primary-color, #1D4ED8); text)

---

#### Screen 5 — TrackArtifactPanel (sidebar per entry)

**File**: `src/components/orbits/tabs/tracks/TrackArtifactPanel.vue`
**Trigger**: clicking a row in the TrackPage entries table
**Component type**: `Dialog` with `position="topright"` (same pattern as `CollectionEditor.vue`)

**Figma**: `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29466&m=dev` 
→ `https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29582&m=dev` 
→ `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29524&m=dev` 
→ `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-30931&m=dev` 
→ `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-57927&m=dev`
  (step 1: panel open → step 2: stage selected → step 3: stage conflict confirm → step 4: unlink confirm → step 5: toast)

**Content**:
- Title: "ARTIFACT settings"
- **Name** — read-only text showing artifact name (e.g. "llm_train-v54567")
- **Stage** — dropdown: list of track stages + "None" option (no stage)
- Buttons: "unlink artifact" (destructive), "save changes"

On "save changes": calls `patchEntry` with selected `stage_id` (or `null`).  
If response is `409` with `TrackStageConflict`: show PrimeVue ConfirmDialog "Stage '{name}' is already assigned to v{held_by_version}. Move it here?" → on confirm, repeat `patchEntry` with `?force=true`.  
On "unlink artifact": PrimeVue ConfirmDialog → `deleteEntry`.

---

#### Screen 6 — TrackAddEntryModal (link artifact to track)

**File**: `src/components/orbits/tabs/tracks/TrackAddEntryModal.vue`
**Trigger**: "Link artifact" button on TrackPage
**Component type**: modal/dialog (overlay over TrackPage)
**Figma**: nodes `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29998&m=dev` 
→ `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-30068&m=dev` 
→ `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-30208&m=dev`
  (step 1: collection select → step 2: artifact list → step 3 +step 4: artifact selected and confirm)

**Flow (4 steps in Figma)**:

1. **Step 1** — Collection selector:
   - Title: "Link a new ARTIFACT"
   - Field: **Collection*** — dropdown, placeholder "Select collection" (lists collections in this orbit)
   - Artifact list is empty until collection is selected

2. **Step 2** — Artifact list (after collection selected):
   - Shows artifact cards filtered by track's `artifact_type`
   - Each card: artifact type badge, name, creation date, description excerpt, tags

3. **Step 3** — Artifact selected:
   - Selected card is highlighted
   - Confirm button becomes active

4. **Step 4** — Confirm:
   - Calls `addEntry`; modal closes; entry appears in table

Note: artifacts already in the track are shown disabled ("Already in Track").

---

#### Screen 7 — Artifact detail page — Tracks section (addition to existing page)

**File**: `src/components/orbits/tabs/tracks/ArtifactTracksWidget.vue`
**Location**: existing artifact detail page (DashboardView or shared artifact layout), added as a new "Tracks" section in the info panel
**Figma**: @https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29366&m=dev — "Collection / Model details"

**Content**:
- Section label: "Tracks"
- If artifact is in tracks: comma-separated list of track names (e.g. "My TEST Track, Data Team Track")
- Button: "Link to track" — opens `AddToTrackModal`
- If artifact is in no tracks: same button, no list

---

#### Screen 8 — AddToTrackModal (add artifact to track, from artifact page)

**File**: `src/components/orbits/tabs/tracks/AddToTrackModal.vue`
**Trigger**: "Link to track" button on artifact detail page
**Figma**: nodes `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29466&m=dev` 
→ `@https://www.figma.com/design/tfEWciot1pORivAd7EEX0B/Luml-%7C-ToDev?node-id=4157-29582&m=dev`
  (step 1: track select → step 2: confirm → step 3: done)

**Content**:
- Single-select dropdown: lists tracks of matching `artifact_type` in the current orbit
- Already-linked tracks are shown disabled
- On confirm: calls `addEntry` once for the selected track; closes modal

---

### Navigation flow summary (from Figma prototype arrows)

```
OrbitTracksView (empty)
  → [Create track btn] → TrackCreator modal
      → [submit] → OrbitTracksView (filled, track card appears)

OrbitTracksView (filled)
  → [track card ⚙] → TrackSettingsPanel (drawer)
  → [track card click] → TrackPage

TrackPage (empty)
  → [Link artifact btn] → TrackAddEntryModal
      → [select collection] → artifact list
      → [select artifact] → artifact highlighted
      → [confirm] → TrackPage (entry appears in table)

TrackPage (filled)
  → [row click] → TrackArtifactPanel (drawer)
      → [save changes] → entry stage updated
      → [unlink artifact] → entry removed

Artifact detail page
  → [Link to track btn] → AddToTrackModal
      → [select track + confirm] → artifact linked, Tracks section updated
```

---

### Frontend Framework (PrimeVue)

PrimeVue is the UI component library. LLM-optimized API reference:  
https://primevue.org/llms/llms-full.txt

| Component | Where used | Key props / notes |
|-----------|-----------|-------------------|
| `Dialog` | TrackSettingsPanel, TrackArtifactPanel, TrackCreator, TrackAddEntryModal, AddToTrackModal | Side-panel style: `position="topright"` `:draggable="false"` `style="margin-top:80px;height:86%;width:420px"` — follow `CollectionEditor.vue`. Centered modals: default position. **Do not use `Drawer`** — it is not used in this project. |
| `DataTable` + `Column` | TrackPage entries table | `scrollable` `scrollHeight` `@row-click` `data-key="id"` — follow `ArtifactsTable.vue` |
| `VirtualScroller` | OrbitTracksView track cards list | `lazy` `@lazy-load` wrapping custom card components — follow `CollectionsList.vue` |
| `AutoComplete` | Tags field in TrackSettingsPanel | `multiple` `:suggestions` `@complete` — follow `CollectionEditor.vue` |
| `Select` | Stage dropdown in TrackArtifactPanel; Type select in TrackCreator and OrbitTracksView filter | standard single-select |
| `Tag` | Artifact type badge on track cards; stage badge in entries table | custom colors via CSS vars per stage name |
| `Button` | All actions | `variant="outlined" severity="warn"` for destructive; `variant="text"` for icon toolbar buttons |
| `InputText` | Name fields | standard |
| `Textarea` | Description fields | `style="height:72px;resize:none"` — follow `CollectionEditor.vue` |
| `Skeleton` | Loading states | follow existing usage |

**Form pattern**: `@primevue/forms` `Form` with `resolver` + `@submit` — follow `CollectionEditor.vue`.

**Confirm pattern**: add factory functions to `src/lib/primevue/data/confirm.ts`; trigger via `useConfirm` → `confirm.require(options)`.

**Toast pattern**: use `simpleSuccessToast` / `simpleErrorToast` from `src/lib/primevue/data/toasts.ts`; add new helpers there as needed.

---

### API client (`frontend/src/lib/api/orbit-tracks/`)

Files: `index.ts` (class `OrbitTracksApi`) and `interfaces.ts` (TypeScript interfaces mirroring backend schemas).

`OrbitTracksApi` receives the shared Axios instance from `ApiClass`. Methods:

```typescript
// Tracks
createTrack(orgId, orbitId, body): Promise<ITrack>
listTracks(orgId, orbitId): Promise<ITracksList>
updateTrack(orgId, orbitId, trackId, body): Promise<ITrack>
deleteTrack(orgId, orbitId, trackId): Promise<void>

// Entries
addEntry(orgId, orbitId, trackId, body): Promise<ITrackArtifact>
listEntries(orgId, orbitId, trackId, params?: { stage?: string; cursor?: string; page_size?: number }): Promise<ITrackEntriesList>
patchEntry(orgId, orbitId, trackId, entryId, body): Promise<ITrackArtifactUpdateResponse>
deleteEntry(orgId, orbitId, trackId, entryId): Promise<void>

// Artifact track membership
listArtifactEntries(orgId, orbitId, artifactId): Promise<ITrackEntriesList>

// Stages
createStage(orgId, orbitId, trackId, body): Promise<ITrackStage>
listStages(orgId, orbitId, trackId): Promise<ITrackStagesList>
updateStage(orgId, orbitId, trackId, stageId, body): Promise<ITrackStage>
deleteStage(orgId, orbitId, trackId, stageId, force?: boolean): Promise<void>
```

Wire into `ApiClass` as `api.orbitTracks`.

### Permissions (`frontend/src/lib/api/api.interfaces.ts`)

Add `track` to `OrbitPermissions`:

```typescript
export interface OrbitPermissions {
  orbit: Omit<PermissionEnum, PermissionEnum.deploy>
  orbit_user: Omit<PermissionEnum, PermissionEnum.deploy>
  artifact: PermissionEnum
  collection: PermissionEnum
  track: Omit<PermissionEnum, PermissionEnum.deploy>  // ← add this
}
```

Components read `orbitsStore.getCurrentOrbitPermissions?.track` and use `.includes(PermissionEnum.X)` to guard destructive or write actions — same pattern as `collection` checks in `CollectionEditor.vue` and `CollectionsList.vue`.

Guarded actions:
- `create` — "Create track" button in `OrbitTracksView` and `TrackCreator`
- `update` — "Save changes" in `TrackSettingsPanel`
- `delete` — "Delete track" button in `TrackSettingsPanel`; "Unlink artifact" in `TrackArtifactPanel`

### Pinia store (`frontend/src/stores/tracks.ts`)

Follows `stores/collections.ts` pattern. Refs: `currentTrack`, `tracksList`. Methods for CRUD of tracks, entries, and stages.

### Composables (`frontend/src/hooks/`)

- `useTracksList.ts` — load + reset for track cards on OrbitTracksView
- `useTrackEntriesList.ts` — load + lazy-load for entries table on TrackPage

### Pages

| File | Route | Purpose |
|------|-------|---------|
| `src/pages/orbits/OrbitTracksView.vue` | child of orbit (`name: orbit-tracks`) | Track cards grid: Name, Type, ID, Last updated, ⚙ settings |
| `src/pages/track/TrackPage.vue` | `/organization/:organizationId/orbit/:id/track/:trackId` | Entries table: Artifact name, Description, Stage badge, Version, Creation time |

### Components

```
src/components/orbits/tabs/tracks/
  TrackCreator.vue          modal: Name*, Description, Type* — creates track + 4 default stages
  TrackSettingsPanel.vue    drawer: track Name, Description, Tags, Stages chips (add/remove); delete/save
  TrackAddEntryModal.vue    modal: Collection* dropdown → artifact card list → confirm link
  TrackArtifactPanel.vue    drawer: artifact name (read-only), Stage dropdown, unlink/save
  ArtifactTracksWidget.vue  "Tracks" section on artifact detail: track name list, "Link to track" button
  AddToTrackModal.vue       modal from artifact page: multiselect track → confirm link
```

### Routing changes

`frontend/src/router/index.ts`:
1. Add child route to the orbit block:
   ```ts
   { path: 'tracks', name: 'orbit-tracks', component: () => import('../pages/orbits/OrbitTracksView.vue') }
   ```
2. Add top-level route (same level as collection):
   ```ts
   {
     path: '/organization/:organizationId/orbit/:id/track/:trackId',
     component: () => import('../pages/track/TrackPage.vue'),
     meta: { requireAuth: true, orbitMiddleware: true }
   }
   ```

`frontend/src/components/orbits/tabs/OrbitTabs.vue`:
- Add entry to the `items` array:
  ```ts
  { label: 'Tracks', routeName: 'orbit-tracks', icon: <icon> }
  ```
  (Icon: use an appropriate Lucide icon, e.g. `GitBranch` or `Library`)

---

# Scenarios

## Scenario: Create track — happy path
**Given** an orbit exists with no track named "churn-model"
**When** `POST /tracks` with `{ name: "churn-model", artifact_type: "model" }`
**Then** `200` response with track object; `next_version=1`; 4 default stages (Staging, Pre-Production, Production, Archived) exist for the track

## Scenario: Create track — duplicate name
**Given** a track named "churn-model" already exists in the orbit
**When** `POST /tracks` with `{ name: "churn-model", artifact_type: "model" }`
**Then** `409 Conflict`

## Scenario: Create track — invalid artifact_type
**Given** any orbit
**When** `POST /tracks` with `{ artifact_type: "foobar" }`
**Then** `422 Unprocessable Entity` (enum validation failure)

## Scenario: Add entry — happy path
**Given** a "model" track with `next_version=3`; a model artifact in the same orbit
**When** `POST /tracks/{track_id}/entries` with `{ artifact_id: <model uuid> }`
**Then** `200` entry with `version=3`; track `next_version` becomes `4`; `stage_id=null`

## Scenario: Add entry — wrong artifact type
**Given** a track with `artifact_type="model"`
**When** `POST` entry with an `artifact_id` that points to a `dataset` artifact
**Then** `422` with message indicating type mismatch

## Scenario: Add entry — artifact from different orbit
**Given** artifact belongs to orbit B; track belongs to orbit A
**When** `POST` entry with that artifact's id
**Then** `422` indicating artifact must belong to the same orbit

## Scenario: Add entry — artifact already in track
**Given** artifact is already an entry in the track
**When** `POST` same `artifact_id`
**Then** `409 Conflict`

## Scenario: Version monotonicity after deletion
**Given** track has entries v1, v2, v3; entry v2 is deleted
**When** a new artifact is added to the track
**Then** new entry receives `version=4` (version 2 is never recycled)

## Scenario: Assign stage — free stage
**Given** entry v2 has no stage; stage "Staging" exists and is unassigned
**When** `PATCH /entries/{entry_id}` with `{ stage_id: <staging_id> }`
**Then** `200`; entry has stage "Staging"

## Scenario: Assign stage — stage already taken, no force
**Given** entry v1 holds stage "Production"; entry v2 has no stage
**When** `PATCH` entry v2 with `{ stage_id: <production_id> }` (no `?force`)
**Then** `409 Conflict` with body `{ stage_name: "Production", held_by_version: 1 }`; no entries modified

## Scenario: Assign stage — stage already taken, with force
**Given** entry v1 holds stage "Production"; entry v2 has no stage
**When** `PATCH` entry v2 with `{ stage_id: <production_id> }?force=true`
**Then** `200`; entry v2 stage = "Production"; entry v1 stage = null

## Scenario: Remove stage from entry
**Given** entry v3 holds stage "Staging"
**When** `PATCH` entry v3 with `{ stage_id: null }`
**Then** `200`; entry v3 stage = null; stage "Staging" is free

## Scenario: Delete entry with active stage
**Given** entry v3 holds stage "Production"
**When** `DELETE /entries/{entry_id}`
**Then** `204`; entry is removed; stage "Production" record still exists but is unassigned

## Scenario: Delete entry does not affect artifact
**Given** entry v1 references artifact A; artifact A is in its collection
**When** `DELETE /entries/{entry_id}`
**Then** artifact A remains in its collection; only the track entry is removed

## Scenario: Delete stage in use — without force
**Given** stage "Staging" is assigned to entry v1
**When** `DELETE /stages/{stage_id}` (no `?force`)
**Then** `409 Conflict`

## Scenario: Delete stage in use — with force
**Given** stage "Staging" is assigned to entry v1
**When** `DELETE /stages/{stage_id}?force=true`
**Then** `204`; stage deleted; entry v1 `stage_id = null`

## Scenario: Delete stage not in use
**Given** stage "Archived" is not assigned to any entry
**When** `DELETE /stages/{stage_id}`
**Then** `204`; stage deleted; no entries affected

## Scenario: SDK — filter entries by stage
**Given** track "churn-model" has entry v2 with stage "Production" and entry v1 with no stage
**When** `GET /tracks/{track_id}/entries?stage=Production`
**Then** `200`; response contains only v2

## Scenario: Artifact deletion blocked when referenced by track
**Given** artifact A is referenced by at least one track entry
**When** `DELETE /artifacts/{artifact_id}`
**Then** `409 Conflict` with message "Artifact is referenced by one or more tracks. Remove it from all tracks before deleting."; artifact is not deleted

## Scenario: Artifact deletion succeeds when not in any track
**Given** artifact B has no track entries
**When** `DELETE /artifacts/{artifact_id}`
**Then** `204`; artifact deleted normally

## Scenario: Delete track cascades
**Given** track has 5 entries and 4 stages (including custom)
**When** `DELETE /tracks/{track_id}`
**Then** `204`; track, all 5 entries, and all 4 stages are deleted; referenced artifacts are unaffected

## Scenario: Stage belongs to different track
**Given** entry belongs to track A; `stage_id` belongs to track B
**When** `PATCH /entries/{entry_id}` with that `stage_id`
**Then** `422` indicating stage does not belong to this track

## Scenario: Entries list pagination
**Given** a track with 50 entries; first page returned with `cursor=<token>`
**When** `GET /tracks/{track_id}/entries?cursor=<token>&page_size=20`
**Then** `200` response with the next 20 entries; `TrackEntriesList.cursor` is non-null if more exist, null on last page

## Scenario: Artifact track membership endpoint
**Given** artifact A is in tracks "churn-model" (v2, Production) and "risk-model" (v1, no stage) within orbit O
**When** `GET /orbits/{orbit_id}/artifacts/{artifact_id}/track-entries`
**Then** `200` list with 2 entries, each including track_id, version, and stage

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
  - [x] Create `luml/models/tracks.py` with `TrackOrm` (including `tags` JSON column), `TrackArtifactOrm`, `TrackStageOrm` following `luml/models/collection.py` patterns
  - [x] Add `tracks` relationship to `OrbitOrm` in `luml/models/orbit.py`
  - [x] Create `backend/migrations/versions/033_add_tracks_tables.py` — `upgrade()` creates `tracks`, `track_stages`, `track_entries` tables with all columns, FKs, indexes, and unique constraints; `downgrade()` drops in reverse order

- [x] **Task 2: Backend schemas + repository layer**
  - [x] Create `luml/schemas/tracks.py` with all Pydantic v2 schemas defined in the Design section (including `tags` in Track/TrackCreate/TrackUpdate)
  - [x] Create `luml/repositories/tracks.py` with all repository methods including `list_entries_for_artifact`, `has_entries_for_artifact`, and `list_entries` with pagination support
  - [x] Write integration tests in `tests/integration/repository/test_tracks.py` covering: create/list/get/update/delete track; create/list stages; add/list/patch/delete entries; `list_entries_for_artifact`; `has_entries_for_artifact`; `clear_stage_from_entries`; pagination

- [x] **Task 3: Backend handlers + API routers**
  - [x] Add `TRACK = "track"` to `Resource` enum in `luml/schemas/permissions.py`; add `Resource.TRACK` to all roles in `organization_permissions` and `orbit_permissions` per the Permissions table in the Design section
  - [x] Create `luml/handlers/tracks.py` with `TracksHandler`, `TrackEntriesHandler`, `TrackStagesHandler` following `luml/handlers/collections.py` patterns; use `Resource.TRACK` with appropriate `Action` via `PermissionsHandler.check_permissions`; raise correct HTTP exceptions for all error cases including stage-from-wrong-track 422
  - [x] Create `luml/api/orbits/orbit_tracks.py` with all endpoints listed in the Design section (including `GET /tracks/{track_id}`, cursor-paginated entries, and `GET /artifacts/{artifact_id}/track-entries`); include proper FastAPI dependencies (JWT auth / API key)
  - [x] Register `tracks_router` in `luml/api/organization_routes.py`
  - [x] Update `luml/handlers/artifacts.py` artifact delete handler to call `repo.has_entries_for_artifact` and raise `409` if true
  - [x] Write unit tests in `tests/unit/handlers/test_tracks.py` covering all happy paths and error cases from the Scenarios section

- [x] **Task 4: Frontend API client + Pinia store + composables**
  - [x] Add `track: Omit<PermissionEnum, PermissionEnum.deploy>` to `OrbitPermissions` interface in `frontend/src/lib/api/api.interfaces.ts`
  - [x] Create `frontend/src/lib/api/orbit-tracks/interfaces.ts` — TypeScript interfaces for all response/request shapes (including `ITrackStageConflict` for 409 body)
  - [x] Create `frontend/src/lib/api/orbit-tracks/index.ts` — `OrbitTracksApi` class with all methods including `listArtifactEntries(orgId, orbitId, artifactId)` and `patchEntry` accepting optional `force` param
  - [x] Wire `orbitTracks: new OrbitTracksApi(...)` into `ApiClass` in `frontend/src/lib/api/api.ts`
  - [x] Create `frontend/src/stores/tracks.ts` — Pinia store covering tracks/entries/stages CRUD; `artifactEntries` ref for ArtifactTracksWidget
  - [x] Create `frontend/src/hooks/useTracksList.ts` — composable for track cards (load, reset)
  - [x] Create `frontend/src/hooks/useTrackEntriesList.ts` — composable for entries table with cursor pagination (load, next page)

- [x] **Task 5: Frontend routing + OrbitTracksView + TrackCreator**
  - [x] Add `orbit-tracks` child route to the orbit block in `frontend/src/router/index.ts`
  - [x] Add top-level `/organization/:organizationId/orbit/:id/track/:trackId` route in `frontend/src/router/index.ts`
  - [x] Add "Tracks" tab entry to `items` array in `frontend/src/components/orbits/tabs/OrbitTabs.vue` (Lucide `GitBranch` or `Library` icon)
  - [x] Create `frontend/src/pages/orbits/OrbitTracksView.vue` — track cards grid (Name, Type badge, ID chip, Last updated, ⚙ settings icon); empty state ("Get started with Tracks", subtitle, "Create track" button); search input + "Filter by type" dropdown
  - [x] Create `frontend/src/components/orbits/tabs/tracks/TrackCreator.vue` — modal title "Create a new TRACK"; Name* input (placeholder "Name your track"), Description textarea (placeholder "Describe your track"), Type* select; submit disabled until Name + Type filled; on submit calls `createTrack`

- [x] **Task 6: TrackPage + TrackSettingsPanel + TrackArtifactPanel**
  - [x] Create `frontend/src/pages/track/TrackPage.vue` — breadcrumb (Registry → Track name), "Link artifact" button, entries table (Artifact name, Description, Stage badge, Version, Creation time) with pagination; empty state "Link an artifact first."; row click → opens `TrackArtifactPanel`; stage badge colors: Production = green (`#DCFCE7`/`#15803D`), Staging+Pre-Production = orange (`#FFEDD5`/`#C2410C`), Archived+others = blue (`#DBEAFE`/`#1D4ED8`)
  - [x] Create `frontend/src/components/orbits/tabs/tracks/TrackSettingsPanel.vue` — `Dialog position="topright"` from ⚙ on track card; Name input, Description textarea, Tags (`AutoComplete` multiple), Stages chips (existing shown as removable chips; × blocked with tooltip "This stage was linked to an artifact. To remove it, unlink the stage." if in use; type-to-add for new stages); "delete track" button (`confirm.require`) + "save changes" (calls `updateTrack`, then batch `createStage`/`deleteStage`)
  - [x] Create `frontend/src/components/orbits/tabs/tracks/TrackArtifactPanel.vue` — `Dialog position="topright"` from row click; artifact name read-only, Stage `Select` (track stages + "None"), "unlink artifact" (`confirm.require` → `deleteEntry`) + "save changes" (`patchEntry`)

- [ ] **Task 7: TrackAddEntryModal + artifact page Tracks section**
  - [ ] Create `frontend/src/components/orbits/tabs/tracks/TrackAddEntryModal.vue` — modal "Link a new ARTIFACT"; step 1: Collection* dropdown (placeholder "Select collection"); step 2: artifact cards filtered by `artifact_type` (disabled if already in track); step 3: selected card highlighted, confirm active; on confirm calls `addEntry`
  - [ ] Create `frontend/src/components/orbits/tabs/tracks/ArtifactTracksWidget.vue` — "Tracks" section on artifact detail; calls `listArtifactEntries` on mount; shows comma-separated track names; "Link to track" button always visible; wire into the correct artifact detail view (`DashboardView.vue` or shared layout)
  - [ ] Create `frontend/src/components/orbits/tabs/tracks/AddToTrackModal.vue` — opened from "Link to track" on artifact detail; single-select dropdown listing tracks of matching `artifact_type` in orbit (disabled if artifact already in that track); on confirm calls `addEntry`
