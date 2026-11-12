# Artifacts

An artifact is a `.luml` file in a collection: a model, a dataset or an
experiment. Build it with the SDK, then upload it here. The calls below use the
client's default collection; pass `collection_id=` to use another one.

## Upload

```python
artifact = client.artifacts.upload(
    file_path="churn-model.luml",
    name="churn-model",
    description="Gradient boosting on 90 days of events",
    tags=["churn", "baseline"],
    lineage_inputs=[dataset_artifact.id],
)
```

- `name` defaults to the file name.
- `lineage_inputs` takes the ids of the artifacts this one was made from, such
  as its dataset or its experiment. The lineage graph shows them.
- What to upload for a tracked experiment (one model, several models, no
  model): see `python -m luml skills show luml-sdk references/upload.md`.

## Find

```python
artifact = client.artifacts.get("churn-model")      # by exact name or id; None if missing

page = client.artifacts.list(search="churn", types=["model"], limit=20)
for item in page.items:
    print(item.name, item.created_at)
next_page = client.artifacts.list(search="churn", start_after=page.cursor)

for item in client.artifacts.list_all(types=["dataset"]):
    print(item.name)
```

- `get` raises when several artifacts share the name. Use the id then.
- `types` takes `"model"`, `"dataset"` and `"experiment"`.
- `sort_by` takes `name`, `created_at`, `size`, `description`, `status`, or a
  metric key. Metric keys work only for models that carry registry metrics;
  models saved with the SDK do not carry them yet.
- An `Artifact` has `id`, `name`, `type`, `tags`, `size`, `status`,
  `manifest` (inputs, outputs and producer tags) and `extra_values` (registry
  metrics).

## Download

```python
client.artifacts.download("churn-model", file_path="churn-model.luml")
```

Load a downloaded dataset with the SDK's `load_dataset`, and run a downloaded
model with fnnx (`fnnx.runtime.Runtime(path).compute(...)`).

## Edit

```python
client.artifacts.update(artifact.id, description="Retrained on November data", tags=["churn"])
```

`tags` replaces the current list.

## Delete

Ask the user first.

```python
client.artifacts.delete(artifact.id)
result = client.artifacts.delete_batch([first.id, second.id])
print(result.deleted, result.failed)
```

`force=True` removes only the record and leaves the file in storage. Use it
only after a normal delete reports a storage error, and only when the user
agrees.

## Lineage

```python
graph = client.artifacts.get_lineage(artifact.id, depth=2)
for edge in graph.edges:
    print(edge.source, "->", edge.target)

client.artifacts.log_lineage_inputs(artifact.id, [dataset_artifact.id])
client.artifacts.log_lineage(dataset_artifact.id, [first_model.id, second_model.id])
client.artifacts.remove_lineage(artifact.id, edge.id)
```

`log_lineage_inputs` adds inputs to an artifact that is already uploaded.
`log_lineage` links one source to several artifacts made from it.
