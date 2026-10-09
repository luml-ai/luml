<a id="luml_api.resources.tracks"></a>

# luml_api.resources.tracks

<a id="luml_api.resources.tracks.TrackResource"></a>

## TrackResource Objects

```python
class TrackResource(TrackResourceBase, ListedResource)
```

Resource for managing tracks.

<a id="luml_api.resources.tracks.TrackResource.create"></a>

#### create

```python
@validate_orbit
def create(
        name: str,
        artifact_type: ArtifactType,
        description: str | None = None,
        tags: list[str] | None = None,
        stages: list[str] | None = None
) -> Track
```

Create a new track in the default orbit.

A track groups versions of one model: every artifact added to it becomes the
next version, and stages (for example dev / staging / production) mark which
version currently serves where.

**Arguments**:

- `name` - Name of the track.
- `artifact_type` - Type of artifacts the track will hold (``ArtifactType.MODEL`` or ``ArtifactType.DATASET``).
- `description` - Optional human-readable description.
- `tags` - Optional list of tags.
- `stages` - Optional list of stage names to create with the track, for example ``["dev", "staging", "production"]``.
  

**Returns**:

  Track object with its stages and version counters.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
track = luml.tracks.create(
    name="churn-model",
    artifact_type=ArtifactType.MODEL,
    stages=["dev", "staging", "production"],
)
```
  
**Example response**:
```python
Track(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    name="churn-model",
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    artifact_type="model",
    description="Customer churn predictor",
    tags=["churn", "production"],
    stages=[
        Stage(id="...", track_id="...", name="dev", is_used=True, ...),
        Stage(id="...", track_id="...", name="production", is_used=False, ...),
    ],
    next_version=3,
    total_entries=2,
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.TrackResource.list"></a>

#### list

```python
@validate_orbit
def list(
        *,
        start_after: str | None = None,
        limit: int = 100,
        sort_by: TrackSortBy = TrackSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        types: list[ArtifactType] | None = None,
        tags: list[str] | None = None
) -> TracksList
```

List tracks in the default orbit, one page at a time.

**Arguments**:

- `start_after` - Cursor from a previous page to continue the listing.
- `limit` - Maximum tracks per page.
- `sort_by` - Field to sort by (``TrackSortBy``).
- `order` - Sort direction (``SortOrder.ASC`` or ``SortOrder.DESC``).
- `search` - Optional substring to filter track names by.
- `types` - Optional list of ``ArtifactType`` to filter by.
  

**Returns**:

  TracksList with the page's items and the cursor for the next page.
  
  Returns an empty list when the orbit has no tracks.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
page = luml.tracks.list(limit=20, search="churn")
for track in page.items:
    print(track.name, track.total_entries)
```

<a id="luml_api.resources.tracks.TrackResource.list_tags"></a>

#### list_tags

```python
@validate_orbit
def list_tags() -> builtins.list[str]
```

List unique tags across all tracks in the default orbit (sorted).

<a id="luml_api.resources.tracks.TrackResource.get"></a>

#### get

```python
@validate_orbit
def get(track_id: str) -> Track | None
```

Get a track by ID or exact name.

Search by name is case-sensitive and matches the exact track name.

**Arguments**:

- `track_id` - The ID or exact name of the track to retrieve.
  

**Returns**:

  Track object.
  
  Returns None if a track with the specified ID or name is not found.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
track_by_name = luml.tracks.get("churn-model")
track_by_id = luml.tracks.get("0199c455-21ee-74c6-b747-19a82f1a1e67")
```
  
**Example response**:
```python
Track(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    name="churn-model",
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    artifact_type="model",
    description="Customer churn predictor",
    tags=["churn", "production"],
    stages=[
        Stage(id="...", track_id="...", name="dev", is_used=True, ...),
        Stage(id="...", track_id="...", name="production", is_used=False, ...),
    ],
    next_version=3,
    total_entries=2,
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.TrackResource.update"></a>

#### update

```python
@validate_orbit
def update(
        track_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        stages: builtins.list[StageUpsertIn] | None = None
) -> Track
```

Update a track's fields; omitted fields are left as they are.

Stages are upserted: entries with an ``id`` update an existing stage,
entries without one create a new stage.

**Arguments**:

- `track_id` - ID of the track to update.
- `name` - New name for the track.
- `description` - New description.
- `tags` - New list of tags (replaces the current list).
- `stages` - List of ``StageUpsertIn`` items to create or rename stages.
  

**Returns**:

  The updated Track object.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
track = luml.tracks.update(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    description="Churn model, retrained monthly",
)
```

<a id="luml_api.resources.tracks.TrackResource.delete"></a>

#### delete

```python
@validate_orbit
def delete(track_id: str) -> None
```

Delete a track permanently.

The tracked artifacts themselves are not deleted — only the track and its
version history.

**Arguments**:

- `track_id` - ID of the track to delete.
  

**Returns**:

  None.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
luml.tracks.delete("0199c455-21ee-74c6-b747-19a82f1a1e67")
```

<a id="luml_api.resources.tracks.TrackResource.list_stages"></a>

#### list_stages

```python
@validate_orbit
def list_stages(track_id: str) -> builtins.list[Stage]
```

List the stages of a track.

**Arguments**:

- `track_id` - ID of the track.
  

**Returns**:

  List of Stage objects; ``is_used`` marks stages that currently
  hold an artifact.
  
  Returns an empty list when the track has no stages.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
stages = luml.tracks.list_stages("0199c455-21ee-74c6-b747-19a82f1a1e67")
for stage in stages:
    print(stage.name, stage.is_used)
```

<a id="luml_api.resources.tracks.TrackResource.add_artifact"></a>

#### add_artifact

```python
@validate_orbit
def add_artifact(
        track_id: str,
        artifact_id: str,
        stage: str | None = None
) -> TrackEntry
```

Register an artifact as the next version of the track.

The version number is assigned automatically. Passing ``stage`` also places
the new version into that stage.

**Arguments**:

- `track_id` - ID of the track.
- `artifact_id` - ID of the artifact to add.
- `stage` - Optional stage to place the version into, by name or by ID.
  

**Returns**:

  TrackEntry object for the newly added version.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
entry = luml.tracks.add_artifact(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    "0199c455-21ee-74c6-b747-19a82f1a1e75",
    stage="production",
)
```
  
**Example response**:
```python
TrackEntry(
    id="0199c455-21ee-74c6-b747-19a82f1a1e68",
    track_id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    artifact_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    version=3,
    stage_id="0199c455-21ee-74c6-b747-19a82f1a1e70",
    added_by="0199c50e-57a6-764f-90be-f90180e56aec",
    artifact_name="churn_model_v3",
    artifact_description=None,
    stage_name="production",
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.TrackResource.get_artifact"></a>

#### get_artifact

```python
@validate_orbit
def get_artifact(track_id: str, tracked_artifact_id: str) -> TrackEntry
```

Get one tracked version by its entry ID.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_id` - ID of the track entry (not the artifact).
  

**Returns**:

  TrackEntry object.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
entry = luml.tracks.get_artifact(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    "0199c455-21ee-74c6-b747-19a82f1a1e68",
)
```

<a id="luml_api.resources.tracks.TrackResource.get_artifact_by_stage"></a>

#### get_artifact_by_stage

```python
@validate_orbit
def get_artifact_by_stage(track_id: str, stage: str) -> TrackEntry
```

Get the version currently occupying a stage.

Answers questions like "which version is in production right now".

**Arguments**:

- `track_id` - ID of the track.
- `stage` - Stage to look in, by name or by ID.
  

**Returns**:

  TrackEntry object for the version the stage holds.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
in_production = luml.tracks.get_artifact_by_stage(
    "0199c455-21ee-74c6-b747-19a82f1a1e67", "production"
)
```
  
**Example response**:
```python
TrackEntry(
    id="0199c455-21ee-74c6-b747-19a82f1a1e68",
    track_id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    artifact_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    version=3,
    stage_id="0199c455-21ee-74c6-b747-19a82f1a1e70",
    added_by="0199c50e-57a6-764f-90be-f90180e56aec",
    artifact_name="churn_model_v3",
    artifact_description=None,
    stage_name="production",
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.TrackResource.list_artifacts"></a>

#### list_artifacts

```python
@validate_orbit
def list_artifacts(
        track_id: str,
        start_after: str | None = None,
        limit: int = 50,
        sort_by: TrackEntrySortBy = TrackEntrySortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        stage: str | None = None
) -> TrackEntriesList
```

List the tracked versions of a track, one page at a time.

**Arguments**:

- `track_id` - ID of the track.
- `start_after` - Cursor from a previous page to continue the listing.
- `limit` - Maximum entries per page.
- `sort_by` - Field to sort by (``TrackEntrySortBy``).
- `order` - Sort direction (``SortOrder.ASC`` or ``SortOrder.DESC``).
- `stage` - Optional stage (name or ID) to filter by.
  

**Returns**:

  TrackEntriesList with the page's items and the cursor for the next page.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
page = luml.tracks.list_artifacts(
    "0199c455-21ee-74c6-b747-19a82f1a1e67", limit=10
)
for entry in page.items:
    print(entry.version, entry.stage_name)
```

<a id="luml_api.resources.tracks.TrackResource.update_artifact"></a>

#### update_artifact

```python
@validate_orbit
def update_artifact(
        track_id: str,
        tracked_artifact_id: str,
        stage: str | None = None,
        force: bool = False
) -> TrackEntry
```

Move a tracked version into a stage, or take it out of one.

A stage holds at most one version. Moving into an occupied stage requires
``force=True``, which displaces the version currently there.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_id` - ID of the track entry to move.
- `stage` - Target stage, by name or by ID; None clears the stage.
- `force` - Displace the current occupant of the target stage.
  

**Returns**:

  The updated TrackEntry object.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
promoted = luml.tracks.update_artifact(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    "0199c455-21ee-74c6-b747-19a82f1a1e68",
    stage="production",
    force=True,
)
```

<a id="luml_api.resources.tracks.TrackResource.remove_artifact"></a>

#### remove_artifact

```python
@validate_orbit
def remove_artifact(track_id: str, tracked_artifact_id: str) -> None
```

Remove one version from the track.

The artifact itself is not deleted — only its entry in the track.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_id` - ID of the track entry to remove.
  

**Returns**:

  None.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
luml.tracks.remove_artifact(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    "0199c455-21ee-74c6-b747-19a82f1a1e68",
)
```

<a id="luml_api.resources.tracks.TrackResource.remove_batch_artifacts"></a>

#### remove_batch_artifacts

```python
@validate_orbit
def remove_batch_artifacts(
        track_id: str,
        tracked_artifact_ids: builtins.list[str]
) -> None
```

Remove several versions from the track in one call.

The artifacts themselves are not deleted — only their entries in the track.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_ids` - IDs of the track entries to remove.
  

**Returns**:

  None.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
luml.tracks.remove_batch_artifacts(
    "0199c455-21ee-74c6-b747-19a82f1a1e67",
    ["0199c455-...-1e68", "0199c455-...-1e69"],
)
```

<a id="luml_api.resources.tracks.AsyncTrackResource"></a>

## AsyncTrackResource Objects

```python
class AsyncTrackResource(TrackResourceBase, ListedResource)
```

Resource for managing tracks for async client.

<a id="luml_api.resources.tracks.AsyncTrackResource.create"></a>

#### create

```python
@validate_orbit
async def create(
        name: str,
        artifact_type: ArtifactType,
        description: str | None = None,
        tags: list[str] | None = None,
        stages: list[str] | None = None
) -> Track
```

Create a new track in the default orbit.

A track groups versions of one model: every artifact added to it becomes the
next version, and stages (for example dev / staging / production) mark which
version currently serves where.

**Arguments**:

- `name` - Name of the track.
- `artifact_type` - Type of artifacts the track will hold (``ArtifactType.MODEL`` or ``ArtifactType.DATASET``).
- `description` - Optional human-readable description.
- `tags` - Optional list of tags.
- `stages` - Optional list of stage names to create with the track, for example ``["dev", "staging", "production"]``.
  

**Returns**:

  Track object with its stages and version counters.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    track = luml.tracks.create(
        name="churn-model",
        artifact_type=ArtifactType.MODEL,
        stages=["dev", "staging", "production"],
    )
```
  
**Example response**:
```python
Track(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    name="churn-model",
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    artifact_type="model",
    description="Customer churn predictor",
    tags=["churn", "production"],
    stages=[
        Stage(id="...", track_id="...", name="dev", is_used=True, ...),
        Stage(id="...", track_id="...", name="production", is_used=False, ...),
    ],
    next_version=3,
    total_entries=2,
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.AsyncTrackResource.list"></a>

#### list

```python
@validate_orbit
async def list(
        *,
        start_after: str | None = None,
        limit: int = 100,
        sort_by: TrackSortBy = TrackSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        types: list[ArtifactType] | None = None,
        tags: list[str] | None = None
) -> TracksList
```

List tracks in the default orbit, one page at a time.

**Arguments**:

- `start_after` - Cursor from a previous page to continue the listing.
- `limit` - Maximum tracks per page.
- `sort_by` - Field to sort by (``TrackSortBy``).
- `order` - Sort direction (``SortOrder.ASC`` or ``SortOrder.DESC``).
- `search` - Optional substring to filter track names by.
- `types` - Optional list of ``ArtifactType`` to filter by.
  

**Returns**:

  TracksList with the page's items and the cursor for the next page.
  
  Returns an empty list when the orbit has no tracks.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    page = luml.tracks.list(limit=20, search="churn")
    for track in page.items:
        print(track.name, track.total_entries)
```

<a id="luml_api.resources.tracks.AsyncTrackResource.list_tags"></a>

#### list_tags

```python
@validate_orbit
async def list_tags() -> builtins.list[str]
```

List unique tags across all tracks in the default orbit (sorted).

<a id="luml_api.resources.tracks.AsyncTrackResource.get"></a>

#### get

```python
@validate_orbit
async def get(track_id: str) -> Track | None
```

Get a track by ID or exact name.

Search by name is case-sensitive and matches the exact track name.

**Arguments**:

- `track_id` - The ID or exact name of the track to retrieve.
  

**Returns**:

  Track object.
  
  Returns None if a track with the specified ID or name is not found.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    track_by_name = luml.tracks.get("churn-model")
    track_by_id = luml.tracks.get("0199c455-21ee-74c6-b747-19a82f1a1e67")
```
  
**Example response**:
```python
Track(
    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    name="churn-model",
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    artifact_type="model",
    description="Customer churn predictor",
    tags=["churn", "production"],
    stages=[
        Stage(id="...", track_id="...", name="dev", is_used=True, ...),
        Stage(id="...", track_id="...", name="production", is_used=False, ...),
    ],
    next_version=3,
    total_entries=2,
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.AsyncTrackResource.update"></a>

#### update

```python
@validate_orbit
async def update(
        track_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        stages: builtins.list[StageUpsertIn] | None = None
) -> Track
```

Update a track's fields; omitted fields are left as they are.

Stages are upserted: entries with an ``id`` update an existing stage,
entries without one create a new stage.

**Arguments**:

- `track_id` - ID of the track to update.
- `name` - New name for the track.
- `description` - New description.
- `tags` - New list of tags (replaces the current list).
- `stages` - List of ``StageUpsertIn`` items to create or rename stages.
  

**Returns**:

  The updated Track object.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    track = luml.tracks.update(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        description="Churn model, retrained monthly",
    )
```

<a id="luml_api.resources.tracks.AsyncTrackResource.delete"></a>

#### delete

```python
@validate_orbit
async def delete(track_id: str) -> None
```

Delete a track permanently.

The tracked artifacts themselves are not deleted — only the track and its
version history.

**Arguments**:

- `track_id` - ID of the track to delete.
  

**Returns**:

  None.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    luml.tracks.delete("0199c455-21ee-74c6-b747-19a82f1a1e67")
```

<a id="luml_api.resources.tracks.AsyncTrackResource.list_stages"></a>

#### list_stages

```python
@validate_orbit
async def list_stages(track_id: str) -> builtins.list[Stage]
```

List the stages of a track.

**Arguments**:

- `track_id` - ID of the track.
  

**Returns**:

  List of Stage objects; ``is_used`` marks stages that currently
  hold an artifact.
  
  Returns an empty list when the track has no stages.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    stages = luml.tracks.list_stages("0199c455-21ee-74c6-b747-19a82f1a1e67")
    for stage in stages:
        print(stage.name, stage.is_used)
```

<a id="luml_api.resources.tracks.AsyncTrackResource.add_artifact"></a>

#### add_artifact

```python
@validate_orbit
async def add_artifact(
        track_id: str,
        artifact_id: str,
        stage: str | None = None
) -> TrackEntry
```

Register an artifact as the next version of the track.

The version number is assigned automatically. Passing ``stage`` also places
the new version into that stage.

**Arguments**:

- `track_id` - ID of the track.
- `artifact_id` - ID of the artifact to add.
- `stage` - Optional stage to place the version into, by name or by ID.
  

**Returns**:

  TrackEntry object for the newly added version.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    entry = luml.tracks.add_artifact(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        "0199c455-21ee-74c6-b747-19a82f1a1e75",
        stage="production",
    )
```
  
**Example response**:
```python
TrackEntry(
    id="0199c455-21ee-74c6-b747-19a82f1a1e68",
    track_id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    artifact_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    version=3,
    stage_id="0199c455-21ee-74c6-b747-19a82f1a1e70",
    added_by="0199c50e-57a6-764f-90be-f90180e56aec",
    artifact_name="churn_model_v3",
    artifact_description=None,
    stage_name="production",
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.AsyncTrackResource.get_artifact"></a>

#### get_artifact

```python
@validate_orbit
async def get_artifact(track_id: str, tracked_artifact_id: str) -> TrackEntry
```

Get one tracked version by its entry ID.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_id` - ID of the track entry (not the artifact).
  

**Returns**:

  TrackEntry object.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    entry = luml.tracks.get_artifact(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        "0199c455-21ee-74c6-b747-19a82f1a1e68",
    )
```

<a id="luml_api.resources.tracks.AsyncTrackResource.get_artifact_by_stage"></a>

#### get_artifact_by_stage

```python
@validate_orbit
async def get_artifact_by_stage(track_id: str, stage: str) -> TrackEntry
```

Get the version currently occupying a stage.

Answers questions like "which version is in production right now".

**Arguments**:

- `track_id` - ID of the track.
- `stage` - Stage to look in, by name or by ID.
  

**Returns**:

  TrackEntry object for the version the stage holds.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    in_production = luml.tracks.get_artifact_by_stage(
        "0199c455-21ee-74c6-b747-19a82f1a1e67", "production"
    )
```
  
**Example response**:
```python
TrackEntry(
    id="0199c455-21ee-74c6-b747-19a82f1a1e68",
    track_id="0199c455-21ee-74c6-b747-19a82f1a1e67",
    artifact_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    version=3,
    stage_id="0199c455-21ee-74c6-b747-19a82f1a1e70",
    added_by="0199c50e-57a6-764f-90be-f90180e56aec",
    artifact_name="churn_model_v3",
    artifact_description=None,
    stage_name="production",
    created_at="2026-08-24T13:00:00Z",
    updated_at=None,
)
```

<a id="luml_api.resources.tracks.AsyncTrackResource.list_artifacts"></a>

#### list_artifacts

```python
@validate_orbit
async def list_artifacts(
        track_id: str,
        start_after: str | None = None,
        limit: int = 50,
        sort_by: TrackEntrySortBy = TrackEntrySortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        stage: str | None = None
) -> TrackEntriesList
```

List the tracked versions of a track, one page at a time.

**Arguments**:

- `track_id` - ID of the track.
- `start_after` - Cursor from a previous page to continue the listing.
- `limit` - Maximum entries per page.
- `sort_by` - Field to sort by (``TrackEntrySortBy``).
- `order` - Sort direction (``SortOrder.ASC`` or ``SortOrder.DESC``).
- `stage` - Optional stage (name or ID) to filter by.
  

**Returns**:

  TrackEntriesList with the page's items and the cursor for the next page.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    page = luml.tracks.list_artifacts(
        "0199c455-21ee-74c6-b747-19a82f1a1e67", limit=10
    )
    for entry in page.items:
        print(entry.version, entry.stage_name)
```

<a id="luml_api.resources.tracks.AsyncTrackResource.update_artifact"></a>

#### update_artifact

```python
@validate_orbit
async def update_artifact(
        track_id: str,
        tracked_artifact_id: str,
        stage: str | None = None,
        force: bool = False
) -> TrackEntry
```

Move a tracked version into a stage, or take it out of one.

A stage holds at most one version. Moving into an occupied stage requires
``force=True``, which displaces the version currently there.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_id` - ID of the track entry to move.
- `stage` - Target stage, by name or by ID; None clears the stage.
- `force` - Displace the current occupant of the target stage.
  

**Returns**:

  The updated TrackEntry object.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
- `ResourceNotFoundError` - If a stage with that name does not exist.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    promoted = luml.tracks.update_artifact(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        "0199c455-21ee-74c6-b747-19a82f1a1e68",
        stage="production",
        force=True,
    )
```

<a id="luml_api.resources.tracks.AsyncTrackResource.remove_artifact"></a>

#### remove_artifact

```python
@validate_orbit
async def remove_artifact(track_id: str, tracked_artifact_id: str) -> None
```

Remove one version from the track.

The artifact itself is not deleted — only its entry in the track.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_id` - ID of the track entry to remove.
  

**Returns**:

  None.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    luml.tracks.remove_artifact(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        "0199c455-21ee-74c6-b747-19a82f1a1e68",
    )
```

<a id="luml_api.resources.tracks.AsyncTrackResource.remove_batch_artifacts"></a>

#### remove_batch_artifacts

```python
@validate_orbit
async def remove_batch_artifacts(
        track_id: str,
        tracked_artifact_ids: builtins.list[str]
) -> None
```

Remove several versions from the track in one call.

The artifacts themselves are not deleted — only their entries in the track.

**Arguments**:

- `track_id` - ID of the track.
- `tracked_artifact_ids` - IDs of the track entries to remove.
  

**Returns**:

  None.
  

**Raises**:

- `ConfigurationError` - If no default orbit is set in the client.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    luml.tracks.remove_batch_artifacts(
        "0199c455-21ee-74c6-b747-19a82f1a1e67",
        ["0199c455-...-1e68", "0199c455-...-1e69"],
    )
```

