# Raw REST API: shapes, required fields and lifecycles

`core-api.md` documents `LumlClient`. This file is for driving the backend
directly with curl or `httpx` — QA, repro scripts, anything the client does not
wrap. Base path is `/v1`; Swagger at `http://localhost:8000/docs` has every
route, but not the traps below. All verified against the dev stack on
2026-09-16.

## Auth

| Call | Notes |
| --- | --- |
| `POST /v1/auth/signin` `{"email","password"}` | 200; tokens arrive only as `Set-Cookie` (`access_token`, `refresh_token`). Wrong password → 400, not 401. |
| `POST /v1/auth/logout` | Reads cookies, not the bearer header. 401 without `refresh_token` cookie. |
| `GET/PATCH/DELETE /v1/auth/users/me` | Self profile. PATCH accepts `disabled` and `auth_method` (don't). Account deletion is `DELETE …/users/me`, not `/account`. |
| `GET /v1/users/me/organizations` | Plain array with `role`. |
| `GET /v1/users/me/invitations` | Plain array. Accept: `POST …/invitations/{id}/accept` → 200 with body `null`. |

Bearer works everywhere except logout: `Authorization: Bearer <access_token>`.

## List response shapes

| Endpoint | Shape |
| --- | --- |
| `GET /organizations/{org}/orbits` | array |
| `GET …/orbits/{o}/collections` | `{items, cursor}` |
| `GET …/orbits/{o}/artifacts` | `{items, cursor}` (orbit-wide; filter with `collection_ids`, `types`, `search`) |
| `GET …/orbits/{o}/tracks` | `{items, cursor}` |
| `GET …/tracks/{t}/entries` | `{items, cursor}` |
| `GET …/tracks/{t}/stages` | array |
| `GET …/orbits/{o}/satellites`, `/deployments`, `/members`, `/secrets` | array |
| `GET /organizations/{org}/members`, `/invitations` | array |

Cursor rules: a cursor encodes `sort_by`, `order` and scope; if the next request
changes any of them the cursor is silently dropped and page 1 returns again with
200. A garbage cursor also returns page 1 with 200. Sorting artifacts by a
metric (`sort_by=<metric name>`) stores `sort_by=extra_values` in the cursor, so
page 2 of a metric sort is currently unreachable — known bug, not your script.

## Bodies that need more than the path says

| Endpoint | Body must include |
| --- | --- |
| `POST /organizations/{org}/invitations` | `email`, `role`, **`organization_id`** (422 without it) |
| `POST /organizations/{org}/members` | `user_id`, **`organization_id`**, `role` — and the body value is what gets written, not the path |
| `POST …/orbits/{o}/members` | `user_id`, **`orbit_id`**, `role` ∈ `admin` \| `member` (no `viewer` here) |
| `POST …/orbits/{o}/satellites` | `{"name": …}` — the schema allows null but the column does not (500) |
| `POST …/orbits/{o}/tracks` | `name`, `artifact_type` (`model` / `experiment` / `dataset`), optional `stages: ["Staging", …]` |
| `POST …/tracks/{t}/entries` | `artifact_id`, optional `stage_id`; artifact type must match the track |
| `PATCH …/tracks/{t}/entries/{e}` | `{"stage_id": …}`; `?force=true` to steal an occupied stage |
| `POST …/collections/{c}/artifacts` | `type`, `version`, `file_name`, `extra_values`, `manifest`, `file_hash`, `file_index`, `size` |

Organization roles are lowercase in the API and DB (`owner` / `admin` /
`member`).

## Artifact lifecycle

```
POST …/collections/{c}/artifacts            → status pending_upload, returns upload URL
PATCH …/artifacts/{a} {"status":"uploaded"} → confirm (PATCH accepts only uploaded / upload_failed / deletion_failed)
GET   …/artifacts/{a}/delete-url            → 409 if a deployment or track references it; else status pending_deletion
DELETE …/artifacts/{a}                      → confirm; requires pending_deletion, else 400 "Unable to confirm deletion with status '…'"
DELETE …/artifacts/{a}/force                → drops deployment rows too (no satellite undeploy)
```

You cannot set `pending_deletion` through PATCH; the delete-url call does it.

## Limits

Organization limits (`members_limit`, `orbits_limit`, `satellites_limit`,
`artifacts_limit`) return 409 "Organization reached maximum number of …". In
dev, raise them in psql (see `dev-stack.md`).

## Flow local API (`lumlflow ui`)

| Call | Notes |
| --- | --- |
| `GET /api/groups` | array of groups (`total_experiments` may be null) |
| `GET /api/groups/experiments?group_ids=…&search=…` | Experiment list. **Without `group_ids` it returns nothing**; there is no `/api/experiments` list route (that path serves the SPA). |
| `GET /api/experiments/{id}` | `status` ∈ `active` / `completed` / `error`; `duration` is in **seconds**; `dynamic_params` is empty until the run ends. |
| `GET /api/experiments/{id}/metrics/{key}` | `{history: [{value, step, logged_at}]}` — works for running runs. |
| `POST /api/groups/experiments/validate-search` | Body is a **raw JSON string** (`"metrics.loss > 0"`), not `{"query": …}`. Entities: `attribute`, `tag`, `param(s)`, `metric(s)`. |
| `DELETE /api/groups/{id}` | 409 if the group still has experiments. |
