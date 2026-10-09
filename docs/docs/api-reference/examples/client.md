---
title: client.py
sidebar_position: 1
description: "Creating a client, reading and changing its default organization, orbit and collection"
---

Client setup: API key, base URL and the default organization, orbit and collection.

Most calls need an organization, an orbit and a collection. Setting them once as
the client's defaults keeps every later call short; any call can still name a
different collection explicitly.

```python
from luml_api import LumlClient

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
COLLECTION_ID = "0199c455-21ee-74c6-b747-19a82f1a1e75"


def main() -> None:
    # With no arguments the client reads LUML_API_KEY, and LUML_BASE_URL when
    # the platform is not the production one at https://api.luml.ai
    luml_from_env = LumlClient()
    print(f"Organizations visible to the key: {luml_from_env.organizations.list()}")

    # No defaults: every call has to be given its organization, orbit and collection
    luml_without_defaults = LumlClient(api_key="luml_your_api_key_here")
    print(f"Organizations: {luml_without_defaults.organizations.list()}")

    # Recommended: defaults resolved by name...
    luml_by_names = LumlClient(
        api_key="luml_your_api_key_here",
        organization="My Organization",
        orbit="Default Orbit",
        collection="Default Collection",
    )
    print(luml_by_names.organization, luml_by_names.orbit, luml_by_names.collection)

    # ...or by id
    luml = LumlClient(
        api_key="luml_your_api_key_here",
        organization=ORGANIZATION_ID,
        orbit=ORBIT_ID,
        collection=COLLECTION_ID,
    )
    print(luml.organization, luml.orbit, luml.collection)

    # Change them on the fly; every later call uses the new defaults
    luml.organization = ORGANIZATION_ID
    luml.orbit = ORBIT_ID
    luml.collection = COLLECTION_ID
    print(luml.organization, luml.orbit, luml.collection)


if __name__ == "__main__":
    main()
```
