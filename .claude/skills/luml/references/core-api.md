# Core — `luml_api` platform client

`from luml_api import LumlClient, AsyncLumlClient`

## Client and defaults

```python
luml = LumlClient()                       # reads LUML_API_KEY, and LUML_BASE_URL
                                          # when the platform is not https://api.luml.ai
luml = LumlClient(
    api_key="luml_...",
    organization="My Organization",       # name or id
    orbit="Default Orbit",
    collection="Default Collection",
)
luml.collection = "0199c455-..."          # defaults are settable afterwards
```

Prefer the no-argument form and the environment variables — do not write keys
into source.

The hierarchy is organization → orbit → collection, and it is enforced: an orbit
default needs an organization default, a collection default needs an orbit
default, and each must belong to its parent. When the key can see exactly one of
a level, that one is picked automatically. Any call can still override with
`collection_id=`.

Resolution by name costs a list call per level at construction time. In a hot
path or a loop, pass ids.

**Async**: `AsyncLumlClient` mirrors every method, awaited. It takes no defaults
in the constructor — set them with one call:

```python
luml = AsyncLumlClient()
await luml.setup_config(organization=..., orbit=..., collection=...)
```

## Errors

All inherit `LumlAPIError`: `AuthenticationError`, `PermissionDeniedError`,
`NotFoundError`, `ConflictError`, `BadRequestError`, `UnprocessableEntityError`,
`InternalServerError`, `APIResponseValidationError`, plus the platform-specific
`CapabilityNotSupportedError`, `UnsupportedCapabilityVersionError`,
`NotAvailableInVersionError`, `ContractViolationError`, `SatelliteOutOfSyncError`.
Catch the specific one; `ConflictError` in particular is the normal signal for
"a stage already holds a version" and "this lineage edge exists".

## Artifacts

```python
luml.artifacts.upload(
    file_path="model.fnnx",
    name="Customer Churn Predictor",
    description=None, tags=None,
    lineage_inputs=[DATASET_ID],       # records provenance as part of the upload
    collection_id=None,                # default collection when omitted
    on_progress=None,
) -> Artifact

luml.artifacts.download(artifact_id, file_path=None, *, collection_id=None)
luml.artifacts.get(model_value, *, collection_id=None)   # by id or by name
luml.artifacts.list(*, collection_id=None, start_after=None, limit=100,
                    sort_by=None, order=SortOrder.DESC,
                    types=[ArtifactType.MODEL], search=None) -> ArtifactsList
luml.artifacts.list_all(...)                          # auto-paginates
luml.artifacts.update(artifact_id, file_name=None, name=None, description=None,
                      tags=None, status=None, *, collection_id=None)
luml.artifacts.delete(artifact_id, *, collection_id=None)
```

`upload` is the everyday call — it registers the artifact, sends the file, and
confirms. `create(...)` is only the registration step, for clients that move the
file themselves; the artifact stays `pending_upload` until `update(...)` confirms
it. `download_url` / `delete_url` return signed URLs for the same reason.

`sort_by` accepts `name`, `created_at`, `size`, `description`, `status`, **or any
metric key** recorded on the artifact — that is how you ask for "the best model
by F1":

```python
best = luml.artifacts.list(types=[ArtifactType.MODEL], sort_by="F1",
                           order=SortOrder.DESC, limit=1)
```

Artifacts produced by the Flow SDK (`save_tabular_dataset`, `tracker.export`,
`log_model`) upload directly: hand `upload` the reference's `.path`.

## Lineage

A graph per orbit; edges point from an input to what it produced
(`dataset -> experiment`, `experiment -> model`, `dataset -> model`).

```python
luml.artifacts.log_lineage(source_artifact_id, target_artifact_ids)  # source -> targets
luml.artifacts.log_lineage_inputs(artifact_id, input_artifact_ids)   # inputs -> artifact
luml.artifacts.get_lineage(artifact_id, depth=None) -> LineageGraph
luml.artifacts.remove_lineage(artifact_id, edge_id) -> LineageEdge
```

Prefer `lineage_inputs=` on `upload` over a separate call — one round trip and no
window where the artifact exists unlinked. A deleted artifact leaves its node in
the graph with `is_deleted=True` and a copy of its name.

## Collections

```python
luml.collections.create(name=..., description=..., type=CollectionType.DATASET, tags=None)
luml.collections.get(collection_value=None)      # by id or name; default collection when None
luml.collections.list(*, start_after=None, limit=100, sort_by=None, order=SortOrder.DESC,
                      search=None, types=None, tags=None, orbit_id=None)
luml.collections.list_all(...) / list_tags(*, orbit_id=None)
luml.collections.update(...) / delete(collection_id=None)
```

Collection types: `model`, `dataset`, `experiment`, `model_dataset`,
`dataset_experiment`, `model_experiment`, `mixed`.

`luml.organizations` and `luml.orbits` expose the same `get` / `list` shape.
Each resource names its `get` parameter after itself — `organization_value`,
`orbit_value`, `collection_value`, `model_value` (artifacts), `deployment_value`,
`secret_value` — and each accepts an id or a name.
`luml.bucket_secrets` manages the storage credentials a collection writes
through (`create`, `update`, `list`, `delete`).

## Tracks — model versions and stages

A track groups the versions of one model. Each artifact added becomes the next
version; a stage holds at most one version, so "what is in production" is one
lookup.

```python
track = luml.tracks.create(name="churn-model", artifact_type=ArtifactType.MODEL,
                           description=None, tags=None,
                           stages=["dev", "staging", "production"])
luml.tracks.add_artifact(track_id, artifact_id, stage=None)
luml.tracks.get_artifact_by_stage(track_id, "production") -> TrackEntry
luml.tracks.update_artifact(track_id, tracked_artifact_id, stage="production", force=False)
# TrackSortBy / TrackEntrySortBy / StageUpsertIn live in luml_api._types,
# not in the package root
luml.tracks.list_artifacts(track_id, start_after=None, limit=50,
                           sort_by=TrackEntrySortBy.CREATED_AT,
                           order=SortOrder.DESC, stage=None)
luml.tracks.list(...) / list_stages(track_id) / list_tags() / get / update / delete
luml.tracks.remove_artifact(...) / remove_batch_artifacts(track_id, ids)
```

Promoting into an occupied stage needs `force=True` — that is the guard against
silently replacing what is serving.

## Deployments and monitoring

```python
luml.deployments.list() -> list[Deployment]
luml.deployments.get(deployment_value) -> Deployment | None   # by id or name
monitoring = luml.deployments.monitoring("My Deployment") # Satellite address resolved
                                                          # from the deployment record
```

Dashboard sections, each taking query kwargs such as `window="7d"`:

```python
monitoring.header()
monitoring.overview(window="7d")          # status cards, alerts, top drifted features
monitoring.runtime(window="24h")          # request counts, error rate, latency percentiles
monitoring.data_quality(feature="age")    # per-feature validity checks
monitoring.feature_drift(severity="critical")
monitoring.output_drift(window="7d")
monitoring.reference_profile()
monitoring.alerts()
monitoring.traces() / monitoring.trace(trace_id)
monitoring.worker()
```

Monitoring reads the deployment's Satellite directly, so results depend on the
Satellite being reachable and in sync; a mismatch raises `SatelliteOutOfSyncError`,
and a section the Satellite's version does not serve raises
`CapabilityNotSupportedError` / `NotAvailableInVersionError`.

Drift and quality panels are empty unless the model carries a reference profile
(`model_ref.add_reference_profile(...)`, see `artifacts.md`).

Source of truth: `sdk/python/api/luml_api/`, runnable examples per resource in
`sdk/python/api/examples/`.
