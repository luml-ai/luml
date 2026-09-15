---
title: Examples
---

One file per part of the API, on the sync client; each file ends with a
`__main__` block that runs its examples. The async client mirrors the sync one
call for call, so `async_demo.py` only runs the basic flow once on it, in one
function.

The ids, names and file paths in the files are placeholders. Replace them with
your own (and set `LUML_API_KEY`, or pass `api_key=`) before running a file:

```bash
cd sdk/python/api
uv run python examples/lineage.py
```

| File | What it covers |
| --- | --- |
| [`client.py`](./client.md) | Creating a client, reading and changing its default organization, orbit and collection |
| [`organizations.py`](./organizations.md) | Listing organizations, getting one by name or id |
| [`bucket_secrets.py`](./bucket_secrets.md) | Registering the buckets that store artifacts |
| [`orbits.py`](./orbits.md) | Creating, updating and deleting orbits |
| [`collection.py`](./collection.md) | Collections of artifacts inside an orbit |
| [`artifacts.py`](./artifacts.md) | Uploading, listing, updating, downloading and deleting artifacts |
| [`lineage.py`](./lineage.md) | Recording what an artifact was produced from and reading the graph back: a training pipeline, impact analysis from a dataset, provenance of the model in production, fixing wrong links |
| [`tracks.py`](./tracks.md) | Versioning one model in a track and moving versions between stages |
| [`deployments.py`](./deployments.md) | Listing deployments and getting one by name or id |
| [`monitoring.py`](./monitoring.md) | Reading a deployment's monitoring sections from its Satellite |
| [`async_demo.py`](./async_demo.md) | The basic flow on the async client, in one function |
