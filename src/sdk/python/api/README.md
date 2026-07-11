# LUML API Client

Python client for the LUML REST API. Use this to programmatically manage your LUML cloud resources — organizations, collections, orbits, artifacts, and storage secrets.

**Main use cases:**
- Upload and retrieve artifacts (models, datasets, files)
- Manage collections and orbits within your organization
- Integrate LUML into your own pipelines or tooling

## Installation

```bash
pip install luml-api
```

## Getting your API key

1. Go to [luml.ai](https://luml.ai) and log in
2. Open **Settings** → **API Keys**
3. Click **Generate new key** and copy it

![API key settings page](https://raw.githubusercontent.com/luml-ai/luml/fix/LM-570-review-readme-across-all-projects/sdk/python/api/docs/images/api_key.webp)

Set it as an environment variable:

```bash
export LUML_API_KEY=your_api_key_here
```

Or pass it directly when initializing the client:

```python
from luml_api import LumlClient

client = LumlClient(api_key="your_api_key_here")
```

## Usage

Initialize the client with your organization and orbit, then start querying resources:

```python
from luml_api import LumlClient

luml = LumlClient(
    api_key="your_api_key_here",
    organization="your_organization_id",
    orbit="your_orbit_id",
)

# List all organizations available to your account
orgs = luml.organizations.list()
for org in orgs:
    print(org.id, org.name)

# List orbits in your organization
orbits = luml.orbits.list()
for orbit in orbits:
    print(orbit.id, orbit.name)

# List collections in the current orbit
for collection in luml.collections.list_all():
    print(collection.id, collection.name, collection.type)
```

The `organization` and `orbit` IDs can be found in the LUML platform under **Settings** → **Organization**.

## Documentation

[https://docs.luml.ai/api-reference/client/](https://docs.luml.ai/api-reference/client/)