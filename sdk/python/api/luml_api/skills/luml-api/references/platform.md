# How the platform works

Read this to understand what you see through the client: why a call is
refused, what a status means, where data lives.

## Organizations, orbits and roles

An organization is a team. Its orbits are workspaces, each with its own
storage, members, collections, tracks, satellites and secrets.

| Role | Can |
| --- | --- |
| Organization owner | Everything, in every orbit, including billing and deleting the organization |
| Organization admin | Everything in every orbit, except deleting orbits or the organization, and billing |
| Organization member | Only what their orbit role allows |
| Orbit admin | Everything inside the orbit, including deleting and secrets |
| Orbit member | List, read, create and update artifacts, collections, tracks and deployments; read satellites and create new ones; list secrets by name and create new ones. No deleting, except live sessions |

A `PermissionDeniedError` means the user's role does not allow the call. Tell
the user; do not look for another way.

## Storage

Each orbit stores its artifacts in its own bucket (S3-compatible or Azure),
connected through a bucket secret. Uploads and downloads go between your
machine and the bucket directly, through short-lived signed URLs; the platform
keeps only the record.

## Artifacts

- Types: `model`, `dataset`, `experiment`. A model can carry its experiment
  embedded, and the web app shows that experiment with it.
- Statuses: `pending_upload` (the record exists, the file is still going up),
  `uploaded`, `upload_failed`, `deletion_failed`.
- A collection's type limits what it holds: `model`, `dataset`, `experiment`,
  their pairs (`model_dataset`, `dataset_experiment`, `model_experiment`) or
  `mixed`.
- Lineage links artifacts to the ones they were made from.

## Tracks and stages

A track numbers the versions of one model or dataset. Stages (for example
`staging`, `production`) each hold one version at a time; they say which
version serves where. Moving a version into an occupied stage takes the old
one out.

## Satellites

A satellite is a server in the user's own infrastructure (Docker or
Kubernetes) that runs deployments and their monitoring. It pairs with the
platform and reports what it can do. Status: `active`, `inactive` (not seen
lately) or `error`. Inputs, outputs and monitoring data stay on the satellite;
only the deployment records go through the platform.

## Deployments

A deployment is a model artifact running on a satellite. When it is created
(in the web app for now), the user picks:

- the satellite and its parameters;
- environment variables, and orbit secrets for the model's secret variables
  (a custom `PyFunc` declares them as runtime secrets);
- secrets for dynamic attributes, passed to the model on each call;
- `monitoring_mode`: `full` or `off`.

Statuses: `pending` (the satellite is setting it up), `active`, `failed`
(`error_message` says why), `not_responding`, `deletion_pending`,
`deletion_failed`. Undeploying asks the satellite to remove it
(`deletion_pending` until it does); a forced delete removes the record of a
deployment that is no longer running.

Call a deployment on its satellite with the user's API key:

```bash
curl -X POST "$SATELLITE_URL/deployments/$DEPLOYMENT_ID/compute" \
  -H "Authorization: Bearer $LUML_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"tenure": [12], "plan": ["pro"]}, "dynamic_attributes": {}}'
```

`$SATELLITE_URL` is `client.satellites.get(deployment.satellite_id).base_url`.
The input names and types are in `GET .../deployments/$DEPLOYMENT_ID/openapi.json`
and in the artifact's manifest.

## Monitoring

With `monitoring_mode` `full`, the satellite records every call and compares
live traffic with the reference profile stored in the model:

- **runtime**: whether the endpoint is healthy;
- **data quality**: whether live inputs still match the model's contract;
- **feature drift**: which inputs changed against the training data;
- **output drift**: whether predictions shifted against the training data;
- **alerts**: thresholds crossed in any of the above;
- **traces**: one row per call;
- **worker**: whether monitoring itself keeps up.

Without a reference profile, only runtime, traces and alerts work.

## Relays and the Flow page

A relay lets the web app open a service that runs where nobody can reach it,
such as Flow next to a job on a cluster. An orbit with a relay assigned has a
Flow page that lists such flows. Assigning relays is admin work.
