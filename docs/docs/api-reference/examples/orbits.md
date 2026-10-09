---
title: orbits.py
sidebar_position: 4
description: "Creating, updating and deleting orbits"
---

Orbits: a workspace inside an organization, backed by one bucket.

Collections, tracks, lineage, satellites and deployments all live inside an
orbit.

```python
from luml_api import LumlClient

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
BUCKET_SECRET_ID = "0199c455-21ed-7aba-9fe5-5231611220de"

luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization=ORGANIZATION_ID,
    orbit=ORBIT_ID,
)


def main() -> None:
    # Create an orbit on a registered bucket
    orbit = luml.orbits.create(
        name="ML Production Orbit",
        bucket_secret_id=BUCKET_SECRET_ID,
    )
    print(f"Created orbit: {orbit}")

    # By name or by id
    by_name = luml.orbits.get("ML Production Orbit")
    print(f"Orbit by name: {by_name}")

    by_id = luml.orbits.get(ORBIT_ID)
    print(f"Orbit by id: {by_id}")

    # All orbits of the organization
    orbits = luml.orbits.list()
    print(f"Orbits: {orbits}")

    # Rename the client's default orbit
    updated = luml.orbits.update(name="ML Production Environment")
    print(f"Updated orbit: {updated}")

    # Delete an orbit
    luml.orbits.delete(ORBIT_ID)


if __name__ == "__main__":
    main()
```
