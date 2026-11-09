# Tracks, versions and stages

A track holds the versions of one model (or one dataset). Each artifact added
to it becomes the next version. Stages such as `staging` and `production` mark
which version serves where; a stage holds at most one version. Tracks belong to
the client's default orbit.

## Create a track

```python
from luml_api import ArtifactType

track = client.tracks.create(
    name="churn",
    artifact_type=ArtifactType.MODEL,
    description="Churn models for the retention team",
    stages=["staging", "production"],
)
```

Find one again with `client.tracks.list(search="churn").items` or
`client.tracks.get(track_id)`.

## Add a version

```python
entry = client.tracks.add_artifact(track.id, artifact.id, stage="staging")
print(entry.version, entry.stage_name)
```

The version number is assigned. `stage` is optional, by name or id.

## Promote

```python
current = client.tracks.get_artifact_by_stage(track.id, "production")
client.tracks.update_artifact(track.id, entry.id, stage="production", force=True)
```

- Moving into an occupied stage needs `force=True`, which takes the current
  version out of it. Ask the user before you promote to `production`.
- `stage=None` takes a version out of its stage.

## Read

```python
client.tracks.list_stages(track.id)
client.tracks.list_artifacts(track.id, stage="production").items
client.tracks.get_artifact(track.id, entry.id)
```

## Change and remove

```python
from luml_api._types import StageUpsertIn

client.tracks.update(track.id, stages=[StageUpsertIn(name="canary")])
client.tracks.remove_artifact(track.id, entry.id)
client.tracks.delete(track.id)
```

A `StageUpsertIn` with an `id` renames that stage; without one it adds a stage.
Ask before removing versions or deleting a track.
