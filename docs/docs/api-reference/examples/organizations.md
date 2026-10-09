---
title: organizations.py
sidebar_position: 2
description: "Listing organizations, getting one by name or id"
---

Organizations: the account level that owns orbits, buckets and members.

```python
from luml_api import LumlClient

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"

luml = LumlClient(api_key="luml_your_api_key_here", organization=ORGANIZATION_ID)


def main() -> None:
    # Every organization the API key has access to
    organizations = luml.organizations.list()
    print(f"Organizations: {organizations}")

    # The client's default organization, with its details
    default_organization = luml.organizations.get()
    print(f"Default organization: {default_organization}")

    # By name or by id
    by_name = luml.organizations.get("My Organization")
    print(f"Organization by name: {by_name}")

    by_id = luml.organizations.get(ORGANIZATION_ID)
    print(f"Organization by id: {by_id}")


if __name__ == "__main__":
    main()
```
