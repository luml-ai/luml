# Proposals

## Problem

Registry users select several artifacts in the collection table and press Delete, and SDK
users script clean-ups of many artifacts at once. The platform has no batch deletion:

- The backend exposes only per-artifact endpoints. Deleting one artifact is a three-step,
  client-driven flow: request a delete URL (the artifact moves to `pending_deletion`), delete
  the object from the bucket through that URL, then confirm the deletion. A separate force
  endpoint drops the database row (and every deployment row referencing it) without touching
  the bucket.
- The frontend emulates a batch by running that three-step flow for every selected artifact in
  parallel. Failures are reported only as a count and by artifact id, never with a reason.
- The SDK exposes only the pieces (`delete_url`, `delete`). Its `delete` calls the confirm
  step directly, so for an uploaded artifact it fails unless the caller first requested the
  delete URL and deleted the object themselves. There is no batch call at all.

An artifact cannot always be deleted. Today the platform refuses in these cases:

| Blocker | Enforced today | How the user resolves it |
|---|---|---|
| Referenced by a deployment (any status) | delete-url and confirm answer 409; the database also forbids removing the row | Delete the deployments first (the satellite undeploys them) |
| Linked to a track (has track entries) | delete-url, confirm and force answer 409; the database also forbids removing the row | Unlink the artifact from its tracks first |
| Caller lacks artifact-delete permission on the orbit (org member without the orbit admin role) | 403 on every deletion endpoint | — |
| Artifact is not in the addressed collection / orbit | 404 | — |
| The object cannot be deleted from the bucket | a `deletion_failed` status exists for this, but the web client never sets it: the artifact stays in `pending_deletion` | Retry the deletion |

The frontend's emulation handles these inconsistently:

- It blocks the whole selection when any artifact has an *active* deployment, while the
  backend blocks on a deployment in *any* status, so artifacts with failed or pending
  deployments fail silently as "Failed to delete".
- It force-deletes *every* selected artifact when any one of them is not `uploaded`: healthy
  artifacts lose their rows while their files stay in the bucket.
- Track-linked artifacts fail without any explanation.
- Force deletion removes deployment rows without undeploying; the containers keep running on
  the satellite until its next restart-time sync removes them as orphans.

## Proposal

Add a real batch deletion to the platform and make it the single deletion path for the
registry UI and the SDK, while keeping the platform out of the data plane: the platform only
signs bucket URLs today (uploads, downloads and deletes are all performed by the client
against the bucket, multipart uploads included), and batch deletion keeps that property.

1. **Two collection-scoped batch endpoints replace the per-artifact three-step loop.** The
   first takes a list of artifact ids and, for every artifact that may be deleted, moves it to
   `pending_deletion` and returns its presigned delete URL; artifacts that may not be deleted
   come back in a `failed` list with a machine-readable reason and the entities that block
   them. The client deletes the objects through the URLs (a missing object counts as deleted)
   and then calls the second endpoint, which confirms the deletion for the whole list and
   again answers with `deleted` and `failed`. Both accept up to 100 ids; clients chunk larger
   selections.
2. **Partial success, never all-or-nothing.** Every artifact in the request is evaluated on its
   own. Everything that can be deleted is deleted; the rest is reported with its reason. A
   blocked or unknown artifact never fails the whole request.
3. **What blocks a deletion.** An artifact referenced by a deployment in *any* status, or
   linked to a track, is never deleted, and batch deletion never removes or changes a
   deployment or a track entry. The response lists the blocking deployments (with their status)
   and tracks; the user removes them through their own flows first (delete the deployments on
   the deployments page, unlink the artifact on the track page) and deletes again. This is the
   rule the single deletion enforces today, now reported instead of hidden behind a generic
   error.
4. **Force stays, but only for the one thing that can still get stuck.** The client tolerates
   a missing object, so artifacts in `pending_upload`, `upload_failed`, `deletion_failed` or
   `pending_deletion` go through the normal flow; status alone no longer needs a force path.
   What can still get stuck is the bucket step: a bucket that keeps refusing the delete
   (credentials rotated outside the platform, object lock or retention, a bucket policy) or a
   URL that cannot be signed would leave the artifact in `deletion_failed` forever. For that
   case the confirmation phase accepts a `force` flag: the record is removed although the
   object was not deleted, and the file stays in the bucket for the user to remove by hand.
   Force never overrides deployments or tracks and never touches the bucket. The web client
   offers it only where the normal path has already failed: for rows already in
   `deletion_failed`, and in the result dialog for artifacts whose object could not be deleted
   in the attempt that just ran. The SDK exposes the same flag. The legacy per-artifact force
   endpoint stays as it is but is no longer used by the web client.
5. **Frontend:** the registry toolbar and the artifact editor run the batch flow for one or
   many artifacts. Deleted artifacts are announced with a toast; artifacts that stayed are
   shown in a result dialog with the reason and links to the blocking deployments and tracks.
   The existing pre-check for active deployments stays in front of the flow: while a selected
   artifact has an active deployment, the current modal lists them and nothing is deleted. The
   "any non-uploaded artifact → force everything" branch is replaced by the narrower force rule
   above.
6. **SDK:** a new `delete_batch` on the artifacts resource runs the same three phases and
   returns the typed result; the existing single `delete` is reworked to run the same flow for
   one artifact, so one call deletes an uploaded artifact. Both take an optional `force` that
   skips the bucket step, documented as a last resort. `delete_url` and the per-artifact
   endpoints stay as they are.

## Why this approach

- The client keeps performing the bucket operations, so the platform still never needs network
  access to a customer's bucket and never runs data-plane operations with the stored
  credentials — the same design as uploads and downloads.
- Two requests per batch instead of three per artifact, and the server can say *why* an
  artifact stayed (which deployments, which tracks) — the current per-artifact loop cannot.
- Partial success matches how people use a multi-select table: the deletable rows disappear
  and the rest is listed with reasons, instead of the whole request failing because one
  artifact is deployed.
- Deployments and track entries are never touched from the artifact side: a container on a
  satellite can never be orphaned by deleting its artifact, and a track keeps every version
  until someone unlinks it on purpose.
- Force is kept for the only failure that retrying cannot resolve (an object the bucket will
  not let go of) and is offered only after that failure, so a stuck row can always be cleared
  while healthy artifacts are never forced by accident, as the current "force everything"
  branch does.
- The per-artifact endpoints stay untouched, so older SDK versions keep working.

Alternatives considered and rejected:

- *Server-side deletion (the backend deletes the objects itself).* One request instead of two
  phases, but it would make the platform reach into customers' buckets for the first time: a
  new network requirement and a new use of the stored credentials, at odds with the current
  control-plane-only design.
- *A force flag that unlinks tracked artifacts on the way (the W&B `delete_aliases` pattern).*
  Rejected for now: a tracked version is only removed from its track on the track page. It can
  be added later without changing the batch contract.
- *Keep the per-artifact loop and only add error codes.* Still three requests per artifact,
  still no place to report blockers for the whole selection at once.
- *All-or-nothing batch (409 with the blockers, nothing deleted).* Forces the user to deselect
  blocked rows by hand and re-run; the per-item report gives the same information after doing
  the useful part of the work.
- *A dry-run / preview endpoint.* Not needed while the first phase already reports per-item
  outcomes before anything is removed from the bucket.
- *No force at all.* Tempting once status is no longer a blocker, but a bucket that permanently
  refuses the delete would leave a row nobody can remove. Force is kept and narrowed instead.

# Design

## The flow in three phases

Batch deletion is orchestrated by the client (web app or SDK) against two new endpoints of a
collection. The platform keeps its control-plane role: it decides what may be deleted, signs
the bucket URLs and removes the records; the client removes the objects from the bucket.

| Phase | Who | What happens |
|---|---|---|
| 1. Request | client → platform | The client sends the artifact ids. The platform evaluates every artifact, moves the eligible ones to `pending_deletion`, and returns a presigned delete URL for each of them plus a `failed` list for the rest. |
| 2. Bucket | client → bucket | The client sends an HTTP DELETE to every returned URL, in parallel. A 2xx or a 404 from the bucket means the object is gone. Any other outcome is a storage failure for that artifact. |
| 3. Confirm | client → platform | The client sends the ids whose objects are gone. The platform re-evaluates each artifact, removes the eligible records and returns `deleted` and `failed`. |

The client merges the `failed` lists of phase 1, phase 2 and phase 3 into one result and
presents it. Nothing in this flow requires the platform to reach the bucket.

## Endpoints

Both endpoints live under the collection's artifact routes, require the same authentication as
the other artifact endpoints (JWT or API key) and the `artifact.delete` permission on the orbit
(organization owner or admin, orbit admin). Both accept a body with:

| Field | Type | Rules |
|---|---|---|
| `artifact_ids` | list of artifact ids | 1 to 100 entries; duplicates are collapsed |
| `force` | boolean, confirm deletion only | default false; true removes the records although the objects were not deleted (see the server-side rules) |

**Request deletion** — `POST /v1/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/delete-urls`

Answers 200 with:

| Field | Content |
|---|---|
| `urls` | one entry per eligible artifact: `artifact_id` and the presigned delete `url` for its object |
| `failed` | one failure entry per artifact that is not eligible |

**Confirm deletion** — `DELETE /v1/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts`

Answers 200 with:

| Field | Content |
|---|---|
| `deleted` | ids of the artifacts whose records were removed |
| `failed` | one failure entry per artifact that was not removed |

A failure entry:

| Field | Content |
|---|---|
| `artifact_id` | the requested id |
| `name` | the artifact's name, or null when the artifact does not exist |
| `reason` | one of the reason codes below |
| `deployments` | for reason `deployments`: every deployment referencing the artifact, each with `id`, `name` and `status`; otherwise empty |
| `tracks` | for reason `tracks`: every track the artifact is linked to, each with `id` and `name`; otherwise empty |

Reason codes:

| Code | Meaning | Raised in | What the user does |
|---|---|---|---|
| `not_found` | the id is not an artifact of this collection (unknown, another collection, already deleted) | phase 1, 3 | nothing |
| `deployments` | at least one deployment, in any status, references the artifact | phase 1, 3 | deletes the deployments through the deployments flow, then retries |
| `tracks` | the artifact is linked to at least one track | phase 1, 3 | unlinks it on the track page, then retries |
| `not_pending_deletion` | phase 3 without `force` was called for an artifact that never went through phase 1 | phase 3 | retries the whole flow |
| `storage_error` | the delete URL could not be signed (reported by the platform in phase 1, which moves the artifact to `deletion_failed`) or the object could not be deleted from the bucket (set by the client in phase 2, which moves the artifact to `deletion_failed` as well) | phase 1, 2 | retries, or force-deletes it (the record is removed, the file stays in the bucket) |

Request-level errors keep the platform's usual shape (`detail` message) and apply to the whole
request, with nothing changed: 403 without the permission, 404 when the orbit or the collection
is not in the addressed organization/orbit, 404 when the orbit has no bucket secret (phase 1
cannot sign anything), 422 when the body violates the rules above. Everything else is a 200
with per-artifact outcomes, including the case where every artifact failed.

## Server-side rules

- **Evaluation order per artifact** (both phases): `not_found`, then `deployments`, then
  `tracks`, then — in phase 3 without `force` only — `not_pending_deletion`. An artifact gets
  exactly one reason, the first that applies.
- **Deployments block in every status** and are never modified by artifact deletion. Only
  deleting the deployments (through their own flow) unblocks the artifact.
- **Tracks block exactly as today.** Batch deletion never removes a track entry; unlinking stays
  on the track page. Only unlinking the artifact from every track unblocks it.
- **Status is not a blocker.** Phase 1 accepts artifacts in any status (`uploaded`,
  `pending_upload`, `upload_failed`, `deletion_failed`, `pending_deletion`) and moves the
  eligible ones to `pending_deletion`. An artifact already in `pending_deletion` is simply given
  a URL again; this is how an interrupted deletion is resumed.
- **Force skips only the status check.** With `force`, phase 3 removes the records of the
  listed artifacts whatever their status, without any phase 1 or 2 having run for them, and
  leaves the object in the bucket as it is. Everything else is unchanged: `not_found`,
  `deployments` and `tracks` are reported exactly as without `force`, no deployment or track
  entry is touched, the same permission applies, and the platform still never reaches the
  bucket. This is where the batch differs from the legacy per-artifact force endpoint, which
  also drops the deployment rows.
- **Phase 1 changes only the eligible artifacts.** Blocked artifacts keep their status; no URL is
  issued for them. If a URL cannot be generated for one artifact, that artifact is reported with
  `storage_error` and moved to `deletion_failed`, so afterwards it is treated like any other
  failed deletion (the web client's force gate included); the others are unaffected.
- **Phase 3 removes records one artifact at a time**, each in its own transaction, so one
  failure never rolls back the others. If the database refuses the removal because a deployment
  or a track link appeared between the check and the removal, the artifact is reported with
  `deployments` or `tracks` accordingly and keeps its `pending_deletion` status.
- **Lookups are set-based**: the artifacts of the request, their deployments and their track
  links are loaded with one query each, not one query per artifact.
- **Nothing else changes**: no new tables or columns, no migration. The per-artifact endpoints
  (delete URL, confirm, force) keep their current behaviour; the web client and the SDK just stop
  calling them. The legacy force endpoint still drops deployment rows; aligning or removing it is
  a follow-up outside this work.

## Client-side rules (web app and SDK alike)

- **Chunking.** A selection larger than 100 artifacts is processed in chunks of at most 100,
  one chunk after the other (phase 1 → 2 → 3 per chunk). Results are merged across chunks. A
  request-level error (network failure, 4xx/5xx) stops the flow: what was already deleted stays
  deleted and is reported, and every artifact of the chunk that hit the error plus all later
  chunks counts as *not completed*. Not-completed artifacts are neither deleted nor failed with
  a reason; running the deletion again for them is safe (an artifact left in `pending_deletion`
  is simply finished). True all-or-nothing is not possible across the bucket and the database,
  so the flow is designed to be resumable instead.
- **Bucket deletion.** One HTTP DELETE per URL, in parallel within a chunk. 2xx and 404 mean the
  object is gone; the artifact goes into the phase 3 request. Any other response or a transport
  error means a storage failure: the artifact is *not* sent to phase 3, the client sets its
  status to `deletion_failed` through the existing artifact update endpoint (the platform allows
  that transition from `pending_deletion`), and the artifact is reported with `storage_error`.
- **Phase 3 is skipped** for a chunk when no object deletion succeeded.
- **Force.** A forced deletion skips phases 1 and 2: the ids go straight to the confirmation
  with `force` set, in chunks of at most 100, and the result is merged like any other. The
  client never sets `force` on its own; it is always an explicit choice of the user (web
  client) or the caller (SDK).
- **The merged result** has the same shape as the platform's: `deleted` (ids) and `failed`
  (failure entries, with names taken from the platform's entries or from the client's own list).

## Web client

- **Trigger points.** The registry table toolbar (multi-select) and the artifact editor's
  "Delete artifact" button both run the same store action with a list of ids, behind three
  gates in this order. First the existing active-deployments pre-check: if any selected
  artifact carries an `active` deployment in its list data, the current modal lists those
  artifacts with their deployments linked to the deployments page and nothing is sent. Then the
  force gate: when every selected artifact is in `deletion_failed` (in the editor: the artifact
  itself), the existing typed force confirmation opens ("Force delete this artifact?" / "Force
  delete these artifacts?", the word `delete` typed to enable the button, the warning that the
  files stay in the bucket) and a forced deletion runs, with no bucket retry. Otherwise the
  normal confirmation ("Delete N artifacts?" / "Delete artifact?") and the normal flow. A
  selection that mixes `deletion_failed` rows with others goes through the normal flow: the
  failed rows retry the bucket and, if it refuses again, get the force option in the result
  dialog. Deployments in other statuses are not in the list data, so they surface through the
  result dialog instead.
- **Removed behaviour.** The "any selected artifact is not `uploaded` → force-delete
  everything" branch and the store's per-artifact force action (the legacy force endpoint) are
  removed. Artifacts in `upload_failed`, `pending_upload` and `pending_deletion` are deleted
  through the normal flow; only `deletion_failed` reaches force directly, as described above.
  The typed force confirmation stays: it now serves the force gate and the result dialog's
  force action, and the component keeps its other user (deployments).
- **After the batch.** Deleted rows leave the table; when the flow completes, the selection is
  cleared. Rows that failed stay; a row that failed with `storage_error` shows the
  `deletion_failed` status, whether its URL could not be signed or the bucket refused the
  DELETE. A success toast reports what was deleted: `Artifact "<name>" deleted` for one, `N
  artifacts deleted` for several. Nothing is toasted for failures with a reason; they go to
  the dialog. A forced deletion is reported exactly the same way.
- **After a request-level error.** The selection is not cleared: it keeps exactly the
  not-completed artifacts, so the user retries with one click. The error toast shows the
  platform's message and, when something was already deleted, adds `N artifacts deleted, M not
  completed`. Not-completed rows that already passed phase 1 show the `pending_deletion`
  status. The result dialog is shown only if some artifact failed with a reason before the
  error.
- **Result dialog** ("Some artifacts were not deleted" / "Artifact was not deleted"), shown when
  `failed` is not empty, with a Close button and, while the list holds `storage_error` entries,
  a "Force delete" button; a new component in the visual pattern of the pre-check modal. One
  block per failed artifact: the artifact name and a reason line:

  | Reason | Reason line | Links |
  |---|---|---|
  | `deployments` | "Used by deployments: <name> (<status>), …. Delete the deployments first." | each deployment links to the orbit's deployments page with that deployment selected (`?deployment=<id>`), opened in a new tab |
  | `tracks` | "Linked to tracks: <name>, …. Unlink the artifact from the tracks first." | each track links to its track page, opened in a new tab |
  | `storage_error` | "The file could not be deleted from the bucket. Try again, or force delete to remove the artifact and leave the file in the bucket." | — |
  | `not_found` | "The artifact no longer exists." | — |
  | `not_pending_deletion` | "Could not be deleted. Try again." | — |

- **Force from the result dialog.** The "Force delete" button applies to every `storage_error`
  entry in the dialog and to nothing else; artifacts blocked by deployments, tracks or
  `not_found` never get a force option. It opens the typed force confirmation on top of the
  dialog; on confirm, a forced deletion runs for those ids. The artifacts it deletes leave the
  table and are toasted like any deletion; if it reports failures (for example a deployment
  created in the meantime), the dialog shows that new result, otherwise it closes.
- **Artifact editor.** On success the editor closes and the app navigates back to the collection
  (existing behaviour). On failure the editor stays open and the same result dialog is shown. A
  successful forced deletion, from the gate or from the dialog, counts as success.
- **Permissions.** The Delete button and the editor's delete action stay gated by the orbit's
  `artifact.delete` permission, as today.

## SDK

- **`artifacts.delete_batch(artifact_ids, *, collection_id=None, force=False)`** on both the
  sync and the async client. Runs the three phases with chunking and the bucket rules above,
  using the client's default collection when none is given (same validation as the other
  artifact methods), and returns an `ArtifactsDeleteResult` with `deleted` (ids) and `failed`
  (a list of `ArtifactDeleteFailure`: `artifact_id`, `name`, `reason`, `deployments`,
  `tracks`). It never raises for per-artifact outcomes; request-level HTTP errors propagate as
  the usual SDK status errors. Artifacts deleted before such an error stay deleted; calling
  again with the same ids is safe (already deleted ids come back as `not_found`, interrupted
  ones are finished). With `force=True` it skips phases 1 and 2 and confirms with `force` set,
  chunked the same way: the objects stay in the bucket, and blocked or unknown artifacts are
  reported exactly as without force. The docstring presents `force` as the last resort for an
  artifact whose object the bucket will not delete, to be used after a normal call came back
  with `storage_error`.
- **`artifacts.delete(artifact_id, *, collection_id=None, force=False)`** keeps its positional
  signature and is reworked to run the same flow for one artifact. It returns nothing on
  success and raises `ArtifactDeleteError` (a `LumlAPIError` carrying the failure entry:
  `artifact_id`, `reason`, `deployments`, `tracks`) when the artifact stayed. `force` behaves as
  in `delete_batch`. A caller that still performs the old manual steps (`delete_url`, own bucket
  delete, `delete`) keeps working: the artifact is already in `pending_deletion`, the re-issued
  URL deletes nothing, and the confirmation succeeds.
- `delete_url` stays unchanged. The new exception is exported from the package root next to the
  other errors. The generated API reference (`docs/docs/api-reference/resources/artifacts.md`)
  is regenerated from the docstrings.

## Trade-offs

- Two round trips per chunk instead of one: the price of keeping bucket access on the client,
  which is the platform's existing data-plane design.
- An interrupted client can leave artifacts in `pending_deletion` with their object already
  gone; this exists today and is recoverable by deleting the artifact again.
- Failures at phase 3 caused by a deployment or track link created between the phases leave an
  artifact whose object is gone. The window is a few seconds and the artifact stays visible in
  `pending_deletion`, so the user can finish the job once the blocker is removed.
- Tracked artifacts still need a detour through the track page before they can be deleted; the
  dialog now tells the user which tracks, which the single deletion never did.
- A forced deletion leaves the object in the bucket, and the file has to be removed by hand;
  the confirmation says so. This is the price of a force path that still never lets the
  platform touch the bucket, and the reason the web client offers it only after the normal
  path failed.

# Scenarios

## Backend — request deletion (phase 1)

## Scenario: every requested artifact is eligible
**Given** a collection with three `uploaded` artifacts that have no deployments and no track links, and a caller with `artifact.delete` on the orbit
**When** the caller requests deletion of the three ids
**Then** the response is 200 with three `urls` entries and an empty `failed` list, each URL is a presigned delete for the artifact's own object, and all three artifacts are now in `pending_deletion`

## Scenario: mixed selection is classified per artifact
**Given** artifact A is `uploaded` with no references, B has a deployment in status `failed`, C has an `active` deployment, D is linked to two tracks, E belongs to another collection of the same orbit, and F does not exist
**When** the caller requests deletion of A–F
**Then** `urls` contains only A, and `failed` contains B and C with reason `deployments` (B listing its deployment with status `failed`, C listing its deployment with status `active`), D with reason `tracks` listing both tracks by id and name, E and F with reason `not_found` and a null name; only A changed status, and the deployments and track entries are untouched

## Scenario: deployment reference wins over track reference
**Given** an artifact that has both a deployment and a track link
**When** the caller requests its deletion
**Then** it is reported once, with reason `deployments`, and its `tracks` field is empty

## Scenario: artifacts in failed or intermediate statuses are eligible
**Given** four artifacts in `pending_upload`, `upload_failed`, `deletion_failed` and `pending_deletion`, none referenced anywhere
**When** the caller requests their deletion
**Then** all four receive a URL and all four are in `pending_deletion` afterwards

## Scenario: duplicated ids are collapsed
**Given** a request whose list contains the same id three times
**When** the request is processed
**Then** the artifact appears once in the response and is evaluated once

## Scenario: body rules are enforced
**Given** a caller with the permission
**When** the caller sends an empty list, or 101 ids
**Then** the platform answers 422 and no artifact changes

## Scenario: permission is checked before anything happens
**Given** an orbit member (no `artifact.delete`) and an eligible artifact
**When** the member requests deletion
**Then** the platform answers 403 and the artifact keeps its status

## Scenario: collection outside the orbit
**Given** a collection that belongs to another orbit of the same organization
**When** the caller requests deletion of any ids through that collection path under the first orbit
**Then** the platform answers 404 with the collection-not-found message

## Scenario: orbit without a bucket secret
**Given** an orbit whose bucket secret no longer exists
**When** the caller requests deletion of an eligible artifact
**Then** the platform answers 404 with the bucket-secret-not-found message and the artifact keeps its status

## Scenario: the delete URL cannot be signed for one artifact
**Given** two eligible artifacts A and B, and a storage client that fails to sign the URL for B's object
**When** the caller requests deletion of both
**Then** the response is 200 with a URL for A, which is now in `pending_deletion`, and B in `failed` with reason `storage_error`, now in `deletion_failed`

## Scenario: an artifact whose URL could not be signed is forced like any other
**Given** the artifact B from the previous scenario, selected alone in the registry table
**When** the user clicks Delete
**Then** the typed force confirmation opens and, once confirmed, B is removed with one forced confirmation and no delete-URL request

## Backend — confirm deletion (phase 3)

## Scenario: confirmation removes the records
**Given** three artifacts in `pending_deletion` with no references
**When** the caller confirms their deletion
**Then** the response is 200 with the three ids in `deleted` and an empty `failed`, the artifact records are gone, and the collection's artifact count decreased by three

## Scenario: confirmation of an artifact that skipped phase 1
**Given** an `uploaded` artifact
**When** the caller confirms its deletion without `force` (the field omitted or false)
**Then** it is reported with reason `not_pending_deletion` and its record and status are unchanged

## Scenario: forced confirmation ignores the status
**Given** four artifacts with no references in `uploaded`, `deletion_failed`, `upload_failed` and `pending_upload`, none of which went through phase 1
**When** the caller confirms their deletion with `force`
**Then** the response is 200 with the four ids in `deleted`, the records are gone, and no delete URL was signed and nothing was sent to the bucket

## Scenario: forced confirmation still respects deployments and tracks
**Given** artifact A in `deletion_failed` referenced by a deployment in status `failed`, and artifact B in `deletion_failed` linked to a track
**When** the caller confirms both with `force`
**Then** A is reported with reason `deployments` listing that deployment and B with reason `tracks` listing that track, both records and statuses are unchanged, and the deployment and the track entry still exist

## Scenario: forced confirmation of an unknown id
**Given** an id from another collection
**When** the caller confirms it with `force`
**Then** it is reported with reason `not_found` and the response is 200

## Scenario: a deployment appeared between the phases
**Given** an artifact in `pending_deletion` that received a deployment after phase 1
**When** the caller confirms its deletion
**Then** it is reported with reason `deployments` listing that deployment, the deployment is untouched, and the artifact stays in `pending_deletion`

## Scenario: a track link appeared between the phases
**Given** an artifact in `pending_deletion` that was linked to a track after phase 1
**When** the caller confirms its deletion
**Then** it is reported with reason `tracks` listing that track, the track entry still exists, and the artifact stays in `pending_deletion`

## Scenario: partial success in one confirmation
**Given** artifact A in `pending_deletion` with no references and artifact B in `pending_deletion` with a deployment
**When** the caller confirms both
**Then** the response is 200 with A in `deleted` and B in `failed` with reason `deployments`

## Scenario: unknown ids at confirmation
**Given** an id that was deleted by another user a moment ago and an id from another collection
**When** the caller confirms them
**Then** both are reported with reason `not_found` and the response is still 200

## Web client

## Scenario: deleting a selection from the toolbar
**Given** three `uploaded` artifacts selected in the registry table and a user with the delete permission
**When** the user clicks Delete and confirms "Delete 3 artifacts?"
**Then** the app requests deletion once for the three ids, sends one bucket DELETE per returned URL, confirms once with the three ids, removes the three rows, clears the selection and shows the toast "3 artifacts deleted"; no dialog appears

## Scenario: a selected artifact has an active deployment
**Given** a selection where A is eligible and B carries the deployment "api" (`active`) in its list data
**When** the user clicks Delete
**Then** the existing modal opens listing B with "api" linked to the deployments page, no request is sent, nothing is deleted and the selection is unchanged

## Scenario: some artifacts stay
**Given** a selection where A is eligible, B is referenced by deployments "old" (`failed`) and "stuck" (`deletion_failed`), which are not in the list data, and C is linked to track "release"
**When** the user confirms the deletion
**Then** A's row disappears with the toast `Artifact "A" deleted`, and the result dialog lists B with "Used by deployments: old (failed), stuck (deletion_failed). Delete the deployments first." where each deployment name links to the deployments page with that deployment selected, and C with "Linked to tracks: release. Unlink the artifact from the tracks first." where the track name links to the track page; the dialog only offers Close

## Scenario: unlinking on the track page unblocks the artifact
**Given** the artifact C from the previous scenario
**When** the user unlinks C on the track page and deletes C again from the registry
**Then** C is deleted and the toast `Artifact "C" deleted` is shown

## Scenario: a missing object counts as deleted
**Given** an `upload_failed` artifact whose object was never written to the bucket
**When** the user deletes it
**Then** the bucket answers 404 to the DELETE, the app still confirms the deletion, and the artifact is deleted without any force dialog

## Scenario: the bucket refuses the deletion
**Given** an eligible artifact whose bucket DELETE answers 403
**When** the user deletes it
**Then** the artifact is not sent to the confirmation, its status is set to `deletion_failed` through the update endpoint, its row stays in the table with the "Deletion failed" status, and the result dialog lists it with "The file could not be deleted from the bucket. Try again, or force delete to remove the artifact and leave the file in the bucket." and offers a "Force delete" button

## Scenario: force from the result dialog
**Given** the result dialog listing B with the bucket message and C with "Used by deployments: …"
**When** the user clicks "Force delete", types `delete` and confirms
**Then** one confirmation with `force` is sent for B only, no delete URL is requested and nothing is sent to the bucket, B's row disappears with the toast `Artifact "B" deleted`, and the dialog stays open showing only C

## Scenario: force delete of rows that already failed
**Given** two artifacts in `deletion_failed` selected and nothing else
**When** the user clicks Delete
**Then** the typed force confirmation opens instead of the normal one; after the user types `delete` and confirms, the app sends one confirmation with `force` for the two ids, requests no delete URLs and sends nothing to the bucket, the two rows disappear, the selection is cleared and the toast "2 artifacts deleted" is shown

## Scenario: a mixed selection is not forced
**Given** an `uploaded` artifact A and a `deletion_failed` artifact B selected together
**When** the user clicks Delete
**Then** the normal confirmation "Delete 2 artifacts?" opens, both go through the normal flow with a delete URL requested for each, and when B's bucket DELETE fails again A is deleted while B is listed in the result dialog with the force option

## Scenario: retrying a failed deletion in a mixed selection
**Given** the selection from the previous scenario
**When** the user confirms and the bucket now answers 204 for B
**Then** both artifacts are deleted without any force dialog

## Scenario: a forced deletion that is blocked
**Given** a `deletion_failed` artifact that received a deployment after it was selected
**When** the user force-deletes it from the toolbar
**Then** the result dialog lists it with "Used by deployments: …" and no force option, its row stays with the "Deletion failed" status, and the deployment is untouched

## Scenario: more than one hundred artifacts selected
**Given** 130 eligible artifacts selected
**When** the user confirms the deletion
**Then** the app runs the flow for the first 100 and then for the remaining 30, and the toast reports "130 artifacts deleted"

## Scenario: the request itself fails
**Given** a selection of five artifacts
**When** the request for deletion answers 500
**Then** nothing is removed from the table, no dialog opens, an error toast with the platform's message is shown, and the five artifacts stay selected

## Scenario: an error in the middle of a large selection
**Given** 130 eligible artifacts selected
**When** the first chunk completes and the request for the second chunk answers 500
**Then** the first 100 rows are removed, the toast shows the platform's message with "100 artifacts deleted, 30 not completed", the remaining 30 rows stay selected, and clicking Delete again deletes them

## Scenario: an error after the objects were deleted
**Given** 3 eligible artifacts selected
**When** the bucket deletes all three objects and the confirmation request fails with a network error
**Then** the three rows stay in the table in `pending_deletion` and stay selected, the error toast is shown, and deleting them again removes them (the bucket answers 404, the confirmation succeeds)

## Scenario: deleting from the artifact editor
**Given** the editor of an eligible artifact
**When** the user clicks "Delete artifact" and confirms
**Then** the artifact is deleted, the toast `Artifact "<name>" deleted` is shown, the editor closes and the app navigates to the collection

## Scenario: the editor's artifact has an active deployment
**Given** the editor of an artifact whose details carry an `active` deployment
**When** the user clicks "Delete artifact"
**Then** the existing modal lists that deployment, no request is sent and the editor stays open

## Scenario: the editor's artifact is blocked
**Given** the editor of an artifact linked to a track
**When** the user clicks "Delete artifact" and confirms
**Then** the editor stays open and the result dialog shows the track link with the unlink hint

## Scenario: force delete from the artifact editor
**Given** the editor of a `deletion_failed` artifact with no references
**When** the user clicks "Delete artifact", types `delete` in the force confirmation and confirms
**Then** one confirmation with `force` is sent for that id, the toast `Artifact "<name>" deleted` is shown, the editor closes and the app navigates to the collection

## Scenario: no delete without the permission
**Given** a user whose orbit role is member
**When** the registry table is shown
**Then** there is no Delete button in the toolbar and no "Delete artifact" button in the editor

## SDK

## Scenario: delete_batch runs the three phases
**Given** a sync client with default organization, orbit and collection, and three eligible artifact ids
**When** `delete_batch` is called with the three ids
**Then** the SDK posts the ids to the request endpoint, sends one HTTP DELETE per returned URL, sends the confirmation with the three ids, and returns a result with the three ids in `deleted` and an empty `failed`

## Scenario: delete_batch reports failures from every phase
**Given** the request endpoint answers with a URL for A and a `deployments` failure for B, and the bucket answers 500 for A's URL
**When** `delete_batch` is called with A and B
**Then** no confirmation is sent, A's status is updated to `deletion_failed`, and the result has an empty `deleted` and two failures: A with `storage_error` and B with `deployments` including the deployment list

## Scenario: delete_batch treats a bucket 404 as success
**Given** the bucket answers 404 for the object of A
**When** `delete_batch` is called with A
**Then** A is confirmed and returned in `deleted`

## Scenario: delete_batch chunks large lists
**Given** 250 artifact ids
**When** `delete_batch` is called
**Then** the request and confirmation endpoints are each called three times (100, 100, 50 ids) and the merged result covers all 250 ids

## Scenario: delete succeeds in one call
**Given** an `uploaded` artifact with no references
**When** `delete` is called with its id
**Then** the SDK runs the three phases for that single id and returns nothing

## Scenario: delete raises when the artifact stays
**Given** an artifact linked to a track
**When** `delete` is called with its id
**Then** `ArtifactDeleteError` is raised, carrying the artifact id, reason `tracks` and the track list

## Scenario: delete_batch with force skips the bucket
**Given** 250 artifact ids with no references, in any status
**When** `delete_batch` is called with them and `force=True`
**Then** the SDK requests no delete URLs, sends nothing to the bucket, sends three confirmations with `force` (100, 100, 50 ids), and returns the 250 ids in `deleted`

## Scenario: force does not override blockers
**Given** an artifact linked to a track
**When** `delete` is called with its id and `force=True`
**Then** one forced confirmation is sent, `ArtifactDeleteError` is raised with reason `tracks` and the track list, and the track entry still exists

## Scenario: the manual legacy sequence still works
**Given** a caller that first calls `delete_url`, deletes the object itself, and then calls `delete`
**When** `delete` runs
**Then** the request phase re-issues a URL for the `pending_deletion` artifact, the bucket answers 404, the confirmation succeeds and `delete` returns nothing

## Scenario: async client parity
**Given** the async client
**When** `delete_batch` and `delete` are awaited with the same inputs as above
**Then** the same platform calls are made and the same results or exceptions are produced

# Tasks

Conventions for every task: new test files hold one test class named after the module, unit
tests mock everything external, integration tests live under the package's `integration`
directory. Backend tests run against the local test database, not the dev one:
`cd backend && POSTGRESQL_DSN="$(grep ^POSTGRESQL_DSN .env | cut -d= -f2- | sed 's#/df_studio$#/df_studio_test#')" uv run pytest`.
Each task ends with the package's CI checks listed in its last subtask.

- [ ] Task 1 — Backend: batch deletion endpoints (request + confirm)
  - [ ] Add the request body schema (`artifact_ids`, 1–100, duplicates collapsed; the confirm body also carries `force`, default false), the reason enum (`not_found`, `deployments`, `tracks`, `not_pending_deletion`, `storage_error`), the failure entry (`artifact_id`, `name`, `reason`, `deployments` with id/name/status, `tracks` with id/name), the request-deletion response (`urls`, `failed`) and the confirm response (`deleted`, `failed`) in `backend/luml/schemas/artifacts.py`.
  - [ ] Add the set-based lookups: in `backend/luml/repositories/artifacts.py` fetch the requested artifacts of a collection with their deployments in every status and a batch status move (to `pending_deletion` for the artifacts that received a URL, to `deletion_failed` for those whose URL could not be signed); in `backend/luml/repositories/tracks.py` (track-entry repository) the tracks (id, name) per artifact for a set of artifact ids.
  - [ ] Add per-artifact record removal in `backend/luml/repositories/artifacts.py` that runs in its own transaction and reports a database constraint refusal so the handler can map it to `deployments` / `tracks`.
  - [ ] Implement the two handler operations in `backend/luml/handlers/artifacts.py` following the Design rules: permission and orbit/collection access checked once, classification order `not_found` → `deployments` → `tracks` (→ `not_pending_deletion` in confirm without `force`; with `force` the status is ignored and the record removed, deployments and tracks still block, nothing is signed), URLs signed with the orbit's storage client (a signing failure reports `storage_error` for that artifact only and moves it to `deletion_failed`), no deployment or track entry ever modified.
  - [ ] Register the routes in `backend/luml/api/orbits/orbit_artifacts.py`: `POST /collections/{collection_id}/artifacts/delete-urls` and `DELETE /collections/{collection_id}/artifacts` (JSON body), both answering 200 with the response schemas; keep the existing per-artifact routes untouched.
  - [ ] Unit tests for the handler in a new `backend/tests/unit/handlers/test_artifacts_batch_deletion.py` (one class): every phase-1 and phase-3 scenario from the Scenarios section (classification per artifact, precedence of `deployments` over `tracks`, statuses accepted, duplicates, permission and access errors, missing bucket secret, signing failure for one artifact → `storage_error` and `deletion_failed` for that artifact only, race → constraint refusal mapped to a reason, partial success, unknown ids, forced confirmation in every status without touching storage, forced confirmation still blocked by deployments and tracks, `force` off by default).
  - [ ] Route tests in a new `backend/tests/unit/api/test_orbit_artifacts_batch_routes.py` (pattern of `backend/tests/unit/api/test_orbit_tags_routes.py`): body validation (empty list, 101 ids → 422), DELETE with a JSON body reaches the handler with `force` defaulting to false and passed through when set, response shapes.
  - [ ] Integration tests for the repositories in a new `backend/tests/integration/repository/test_artifacts_batch_deletion.py`: batch fetch with deployments of several statuses and tracks, batch status move, per-artifact removal, constraint refusal when a deployment or a track entry references the artifact, collection artifact count after removal.
  - [ ] Run `uv run ruff format --check luml migrations tests utils`, `uv run ruff check luml migrations tests utils`, `uv run mypy luml` and the test suite (command above) in `backend`; all green.

- [ ] Task 2 — Web client: batch deletion flow in the API client and the artifacts store (depends on Task 1)
  - [ ] Add the request/response and failure-entry types (reason union, `deployments`, `tracks`) to `frontend/src/lib/api/artifacts/interfaces.ts` and the two batch calls to `frontend/src/lib/api/artifacts/index.ts` (`POST .../artifacts/delete-urls`, `DELETE .../artifacts` with `data` body carrying `artifact_ids` and `force`, as `deleteEntries` does in `frontend/src/lib/api/orbit-tracks/index.ts`); remove the per-artifact delete-URL and confirm calls once nothing uses them.
  - [ ] Reimplement the store's batch deletion in `frontend/src/stores/artifacts/index.ts` (result type in `frontend/src/stores/artifacts/artifacts.interface.ts`): chunks of 100 processed sequentially, phase 1, parallel bucket DELETEs with 2xx/404 as success, phase 3 only for the ids whose object is gone, `deletion_failed` set through the existing update call on storage failure, merged `deleted` / `failed` result with names, deleted rows removed from the list, `storage_error` rows updated to `deletion_failed` in the list, remaining chunks skipped after a request-level error with the not-completed ids reported alongside the error. Add a forced deletion next to it (same chunking, confirmation with `force` only, no phase 1 or 2, same result shape and list updates) that replaces the store's per-artifact force action.
  - [ ] Adjust the two existing call sites (`TableToolbar.vue`, `ArtifactEditor.vue`) to the new result shape without changing their UX yet, so the app keeps working until Task 3.
  - [ ] Unit tests in a new `frontend/src/stores/__tests__/artifacts.test.ts` (pattern of `frontend/src/stores/__tests__/deployments.test.ts`, mocking `@/lib/api` and axios): happy path, failures from each phase, bucket 404 tolerated, storage failure → status update and `storage_error`, chunking at 130 ids, request-level error stops the remaining chunks and reports the not-completed ids, list updates, forced deletion sends only confirmations with `force` and no delete-URL or bucket request.
  - [ ] Run `npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:ci` in `frontend`; all green. The Playwright deletion tests in `frontend/tests/integration/artifacts.spec.ts` still mock the per-artifact endpoints and are expected to fail until Task 3 rewrites them.

- [ ] Task 3 — Web client: toolbar, editor and the result dialog (depends on Task 2)
  - [ ] Add a result dialog component next to `frontend/src/components/orbits/tabs/registry/collection/artifacts-table/ArtifactsDeploymentsModal.vue` (same folder, same visual pattern and dialog pass-through options from `models-table.data.ts`; the pre-check modal and its store state stay as they are) driven by store state holding the last deletion result: title by count, one block per failed artifact with the reason lines and links from the Design table (deployments → `orbit-deployments` route with `?deployment=<id>`, tracks → `track` route, both in a new tab), a Close button that clears the state and a "Force delete" button shown only while `storage_error` entries are present, which opens the existing `ForceDeleteConfirmDialog.vue` on top and runs the store's forced deletion for those ids, then closes the dialog or shows the new failures.
  - [ ] Rework the delete flow in `frontend/src/components/orbits/tabs/registry/collection/artifacts-table/TableToolbar.vue`: active-deployments pre-check → force gate (every selected artifact `deletion_failed` → the existing typed force confirmation → store forced deletion) or the existing confirmation → store batch deletion → success toast by name/count for `deleted` → result dialog when `failed` is not empty; replace the "not uploaded → force everything" branch with that gate and keep the typed force confirmation with its warning text; clear the selection when the flow completes, and after a request-level error keep the not-completed artifacts selected and show the error toast with the deleted / not-completed counts.
  - [ ] Rework `frontend/src/components/orbits/tabs/registry/collection/artifact/ArtifactEditor.vue` the same way, including the force gate for a `deletion_failed` artifact (typed force confirmation → forced deletion): on success, forced or not, close and emit as today; on failure keep the editor open and show the result dialog; the active-deployments pre-check stays. Render the result dialog in `frontend/src/pages/collection/artifact/index.vue` next to the deployments modal.
  - [ ] Remove the leftovers: the legacy per-artifact force API call in `frontend/src/lib/api/artifacts/index.ts` and anything still calling it; `frontend/src/components/ui/dialogs/ForceDeleteConfirmDialog.vue` stays (force gate, result dialog, deployments).
  - [ ] Component test for the result dialog (vitest, pattern of `frontend/src/components/deployments/edit/DeploymentsEditor.test.ts`): reason lines and links for `deployments`, `tracks`, `storage_error`, `not_found`; title for one vs several artifacts; the "Force delete" button present only with `storage_error` entries and applying only to them.
  - [ ] Update `frontend/tests/integration/artifacts.spec.ts` (fixtures in `frontend/tests/integration/fixtures/data.ts`): the single and multiple deletion tests mock the two batch endpoints and the bucket DELETE; replace the force-delete tests with an `upload_failed` artifact deleted through the normal flow (bucket answers 404), a `deletion_failed` artifact that opens the typed force dialog and sends one confirmation with `force` and no delete-URL request, a bucket refusal whose result dialog offers "Force delete" and then sends the forced confirmation, and a blocked artifact whose dialog shows the deployment and track links; keep (or add) the test that a selected artifact with an active deployment opens the pre-check modal and sends no deletion request.
  - [ ] Run `npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:ci` and `npx playwright test tests/integration/artifacts.spec.ts` in `frontend`; all green.

- [ ] Task 4 — SDK (`sdk/python/api`): `delete_batch` and the reworked `delete` (depends on Task 1)
  - [ ] Add the result types to `sdk/python/api/luml_api/_types.py` (`ArtifactsDeleteResult` with `deleted` and `failed`, `ArtifactDeleteFailure` with `artifact_id`, `name`, `reason`, `deployments`, `tracks`, plus the two platform response models) and `ArtifactDeleteError` to `sdk/python/api/luml_api/_exceptions.py`, exported from `sdk/python/api/luml_api/__init__.py`.
  - [ ] Add a bucket delete helper next to the download helper in `sdk/python/api/luml_api/handlers/base_file_handler.py` (sync and async): HTTP DELETE on a presigned URL, 2xx/404 as success, anything else as a storage failure.
  - [ ] Implement `delete_batch` on the abstract base, the sync and the async resource in `sdk/python/api/luml_api/resources/artifacts.py` (collection validation like the other methods, chunks of 100, three phases, `deletion_failed` set through `update` on storage failure, merged result, no exception for per-artifact outcomes, `force=False` keyword that skips phases 1 and 2 and confirms with `force`) and rework `delete` to run the same flow for one id with the same `force` keyword, raising `ArtifactDeleteError` with the failure entry when the artifact stays. Docstrings with examples, `force` documented as the last resort after a `storage_error`, as the reference docs are generated from them.
  - [ ] Tests: update the `delete` tests in `sdk/python/api/tests/unit/test_model_artifact_resource.py` and the abstract-method list in `sdk/python/api/tests/unit/test_artifact_resource_coverage.py`; add a new `sdk/python/api/tests/unit/test_artifact_delete_batch.py` (one class) covering the SDK scenarios: three phases with the exact platform calls, failures from each phase, bucket 404 tolerated, storage failure → status update and `storage_error`, chunking at 250 ids, `force=True` sending only chunked confirmations with `force` and no delete-URL or bucket request, `force=True` still raising for a tracked artifact, `delete` returning nothing vs raising, legacy manual sequence, async parity.
  - [ ] Regenerate the API reference with `python docs/generate_docs.py` (pydoc-markdown) so `docs/docs/api-reference/resources/artifacts.md` documents `delete_batch` and the reworked `delete`.
  - [ ] Run `uv run ruff format --check luml_api tests examples`, `uv run ruff check luml_api tests`, `uv run mypy luml_api`, `uv run pytest` in `sdk/python/api`; all green.
