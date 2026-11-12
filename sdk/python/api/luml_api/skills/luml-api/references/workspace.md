# Organizations, orbits, collections and satellites

## Where you are

```python
client.organizations.list()
client.orbits.list()                 # orbits of the default organization
client.collections.list().items      # collections of the default orbit
client.organization, client.orbit, client.collection   # current defaults (ids)
```

Switch with `client.orbit = "Research"` or `client.collection = "Churn"`.
Setting an orbit needs the organization, and a collection needs the orbit.

## Collections

```python
from luml_api import CollectionType

collection = client.collections.create(
    name="Churn",
    description="Churn models and their experiments",
    type=CollectionType.MODEL_EXPERIMENT,
    tags=["retention"],
)
client.collections.get("Churn")                       # exact name or id; None if missing
client.collections.list(search="churn", tags=["retention"]).items
client.collections.update(description="...", collection_id=collection.id)
```

- `type` decides what the collection holds: `model`, `dataset`, `experiment`,
  `model_dataset`, `dataset_experiment`, `model_experiment` or `mixed`. Use
  `model_experiment` for models with their experiments, and `mixed` when
  unsure.
- `collections.delete` deletes the collection with its artifacts. Ask first.

## Satellites

```python
satellite = client.satellites.get(deployment.satellite_id)
print(satellite.name, satellite.status, satellite.last_seen_at)
```

Pairing satellites, creating orbits and storage secrets are admin work. Leave
them to the user in the web app.
