---
name: luml-api
description: Work with the LUML platform from code with the luml_api client. Use when uploading or downloading models, datasets or experiments, organizing them in collections and tracks, promoting a model to a stage, reading deployments and their monitoring, or doing from code anything a user does in the LUML web app.
---

# LUML API client

`luml_api` (PyPI: `luml_api`) is the client for the LUML platform. It works
together with the SDK: the SDK (`luml`, PyPI `luml_sdk`) tracks experiments and
builds artifacts on your machine, and the client moves those artifacts to and
from the platform and manages the platform itself. Do not use the client to
build artifacts; use the SDK (`python -m luml skills show luml-sdk`).

The rule behind both: everything a data scientist does in the web app can also
be done from code. When the client has no method for something the web app
does, tell the user. Do not write raw HTTP calls to the platform.

## Setup

```bash
pip install luml_api
export LUML_API_KEY="luml_..."   # created in the web app, under account settings
```

```python
from luml_api import LumlClient

client = LumlClient(organization="My org", orbit="Research", collection="Churn")
```

- The key comes from `LUML_API_KEY`. Never put it in code, and never print it.
- The client connects to `https://api.luml.ai`. Set `LUML_BASE_URL` only for a
  self-hosted platform.
- `organization`, `orbit` and `collection` take a name or an id. They are the
  defaults for later calls. When the user has exactly one organization, orbit
  or collection, it is chosen without being named. An orbit needs its
  organization, and a collection needs its orbit.
- Change a default later with `client.collection = "Other collection"`.
- Names are matched exactly and are case-sensitive.

The async client has the same resources; set its defaults with
`setup_config`:

```python
from luml_api import AsyncLumlClient

client = AsyncLumlClient()
await client.setup_config(organization="My org", orbit="Research")
```

## Platform terms

- **Organization**: a team. **Orbit**: a workspace inside it, with its own
  storage, members and satellites.
- **Collection**: a folder of artifacts in an orbit.
- **Artifact**: a `.luml` file: a model, a dataset or an experiment.
- **Track**: the versions of one model, with stages such as `staging` and
  `production`. A stage holds at most one version.
- **Satellite**: a server the orbit deploys models to. **Deployment**: a model
  running on a satellite, with monitoring.

Roles, statuses and what each part does: [references/platform.md](references/platform.md).

## Web app to code

| In the web app | From code |
| --- | --- |
| Upload a model, dataset or experiment | SDK builds the file; `client.artifacts.upload` ([artifacts.md](references/artifacts.md)) |
| Browse, search, download, edit, delete artifacts | `client.artifacts` ([artifacts.md](references/artifacts.md)) |
| Lineage graph | `client.artifacts.get_lineage`, `log_lineage_inputs` |
| Collections | `client.collections` ([workspace.md](references/workspace.md)) |
| Tracks, versions and stages | `client.tracks` ([registry.md](references/registry.md)) |
| Deployments and their monitoring | `client.deployments` ([deployments.md](references/deployments.md)) |
| Flow page, live flows | `RelayedFlow` from the SDK; `client.flows` ([flows.md](references/flows.md)) |
| Local experiments, metrics, evals | The SDK's `ExperimentTracker`, or Flow |
| Deploy a model, change or delete a deployment | Not in the client yet |
| Open or compare an uploaded experiment | Not from code yet. Compare experiments in the local store before uploading, or ask the user to compare them in the web app |
| Sort or compare models by metric in the registry | Works only for models that carry registry metrics; models saved with the SDK do not yet |
| Secrets, members, invites, billing, API keys | Leave to the user in the web app |

## Rules

1. Address everything by name, as the user does. Resolve ids only when a method
   needs one (`client.artifacts.get(name).id`).
2. Never create, change, read or delete secrets. Deployments that need an API
   key get it from an orbit secret the user creates in the web app.
3. Ask before anything that deletes or replaces: deleting artifacts,
   collections or tracks, and moving a version into an occupied stage
   (`force=True`).
4. Handle errors by type: `NotFoundError`, `PermissionDeniedError`,
   `AuthenticationError`, `ConflictError` (all importable from `luml_api`). A
   `PermissionDeniedError` means the user's role does not allow it; tell them
   instead of trying another way.
5. Use only methods you have seen in these references or in the installed
   source. Do not guess names or keyword arguments.

## References

- [references/artifacts.md](references/artifacts.md): upload, find, download,
  edit and delete artifacts; lineage.
- [references/registry.md](references/registry.md): tracks, versions and stages.
- [references/deployments.md](references/deployments.md): deployments and
  monitoring.
- [references/workspace.md](references/workspace.md): organizations, orbits,
  collections and satellites.
- [references/flows.md](references/flows.md): flows and live sessions.
- [references/platform.md](references/platform.md): how the platform works:
  roles, storage, statuses, satellites, deployments and calling them,
  monitoring.
