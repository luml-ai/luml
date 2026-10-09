---
title: collection.py
sidebar_position: 5
description: "Collections of artifacts inside an orbit"
---

Collections: groups of artifacts inside an orbit.

A collection has a type (models, datasets, experiments, or a mix) that decides
which artifacts it accepts.

```python
from luml_api import CollectionType, LumlClient

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
COLLECTION_ID = "0199c455-21ee-74c6-b747-19a82f1a1e75"

luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization=ORGANIZATION_ID,
    orbit=ORBIT_ID,
    collection=COLLECTION_ID,
)


def main() -> None:
    # Create a collection for models only
    collection = luml.collections.create(
        name="Production artifacts",
        description="Trained artifacts ready for production deployment",
        type=CollectionType.MODEL,
        tags=["production", "ml", "artifacts"],
    )
    print(f"Created collection: {collection}")

    # The client's default collection, with its details
    default_collection = luml.collections.get()
    print(f"Default collection: {default_collection}")

    # By name or by id
    by_name = luml.collections.get("Production artifacts")
    print(f"Collection by name: {by_name}")

    by_id = luml.collections.get(COLLECTION_ID)
    print(f"Collection by id: {by_id}")

    # All collections of the orbit
    collections = luml.collections.list()
    print(f"Collections: {collections}")

    # Change the description or tags
    updated = luml.collections.update(
        collection_id=COLLECTION_ID,
        description="Updated: Production-ready ML artifacts",
    )
    print(f"Updated collection: {updated}")

    # Delete a collection
    luml.collections.delete(COLLECTION_ID)


if __name__ == "__main__":
    main()
```
