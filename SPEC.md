# Proposals

## Problem

Several backend operations follow the pattern "read a row, check a rule, then write", with the
check and the write in different transactions. Two concurrent requests both pass the check
against the same stale state and both write. The batch artifact deletion (LM-587) closed this
window for its own flow by locking the artifact rows and checking inside the same transaction;
the rest of the platform still has the following gaps:

| # | Operation | Race | Consequence today |
|---|---|---|---|
| 1 | Single-artifact delete URL request | Deployments are checked, then the artifact is moved to `pending_deletion` in a separate transaction; a deployment created in between is not seen | The client deletes the object from the bucket, the confirmation is refused by the database, and a deployment points at an object that no longer exists |
| 2 | Assigning a track stage to an entry | "One entry per stage" is checked in code only; there is no database rule | Two concurrent assignments (or two forced reassignments) leave two entries in the same stage |
| 3 | Refresh-token rotation | "Is the token revoked?" and "revoke it" are separate steps; the blacklist accepts duplicates | The same refresh token used twice at the same moment yields two valid sessions |
| 4 | Deleting a collection | The artifact count is read, then the collection is deleted; artifacts cascade | An artifact created in between disappears mid-upload: its record is gone, its object stays in the bucket, the client's status update answers 404 |
| 5 | Organization quotas (artifacts, orbits, satellites, members, organizations per user) | The count is read, then the record is inserted | N concurrent requests overshoot the limit by up to N-1 |
| 6 | Sending an organization invite | "Does an invite exist?" is checked in code only | A double submit creates two invites and two emails |
| 7 | Deleting an organization | The member count is read, then the organization is deleted; members cascade | A member who joined in between is deleted together with the organization |
| 8 | Deleting a track stage | Usage is checked, then the stage is deleted; entries lose the stage silently (`SET NULL`) | An entry assigned to the stage in between ends up without a stage and nobody is told |

Changing an artifact's status through the update endpoint has the same shape but every
concurrent outcome is a valid state, so it is left alone.

## Proposal

Every check-then-write above becomes atomic. Two mechanisms, chosen per case:

- **A database rule** where the invariant is a property of the data (uniqueness, referential
  integrity). The database refuses the second writer and the platform answers 409. Used for
  2, 3, 6 and 8.
- **A row lock for the duration of the check and the write** where the rule depends on a
  count or on related rows (quotas, "no children", "not referenced"). The second writer waits
  for the first to finish and then re-evaluates the rule against the committed state. Used for
  1, 4, 5 and 7.

Behaviour per operation:

1. **Single-artifact delete URL.** The artifact row is locked; deployments and track links are
   checked and the status is moved to `pending_deletion` in that same transaction. A deployment
   creation that overlaps waits and then sees `pending_deletion`; a delete request that overlaps
   a deployment creation sees the deployment and answers 409 as today. The presigned URL is
   generated before the lock, so a refused request changes nothing. Together with LM-587 (which
   locks the artifact row on deployment creation and requires `uploaded`) the window is closed
   from both sides; on its own this change closes the deletion side.
2. **Track stages.** The database enforces "at most one entry per stage in a track". A second
   concurrent assignment answers 409 "Stage '…' is already assigned to another entry." instead of
   succeeding; a forced reassignment that loses the race answers the same 409 and the caller
   retries. Existing duplicates are resolved once, keeping the entry with the highest version.
3. **Refresh tokens.** Revoking is the single step that decides: the token is written to the
   blacklist first, and only the writer that inserted it gets a new token pair; a concurrent
   second use answers 400 "Token has been revoked". Logout stays idempotent: revoking an already
   revoked token is not an error. Existing duplicate blacklist rows are collapsed once.
4. **Collection deletion.** The collection row is locked, the artifact count is taken under the
   lock, and the row is deleted in the same transaction. An artifact creation that overlaps
   waits on the collection row (the foreign-key check does) and then fails because the
   collection is gone; the creation endpoint answers 404 "Collection not found" instead of a
   server error. A non-empty collection still answers 409 as today.
5. **Quotas.** The organization row is locked while the count is taken and the record inserted,
   for artifacts, orbits, satellites and members; the user row is locked the same way for the
   per-user organization limit. Concurrent requests serialize on that row, so the limit is
   never exceeded. The early checks in the handlers stay as a fast path with the same message;
   the check under the lock is the one that decides.
6. **Invites.** The database enforces one pending invite per organization and email. A
   concurrent duplicate answers 409 "invite already exists" as the pre-check does today.
   Existing duplicates are collapsed once, keeping the newest.
7. **Organization deletion.** The organization row is locked, the member count is taken under
   the lock, and the row is deleted in the same transaction. A membership creation that overlaps
   waits and then fails because the organization is gone; the accept-invite / add-member
   endpoints answer 404 "Organization not found" instead of reporting a duplicate member.
8. **Track stage deletion.** Entries can no longer lose their stage silently: the database
   refuses to delete a stage that is assigned (`RESTRICT` instead of `SET NULL`). A forced
   deletion unassigns the entries and deletes the stage in one transaction; an assignment that
   overlaps either waits and fails with 409 "Stage does not belong to this track"-style
   refusal (the stage is gone) or wins, in which case the deletion answers 409 "Stage is
   currently assigned to an entry". Stage synchronization through track update behaves the
   same way.

## Server-side rules

- **One transaction per decision.** Wherever a rule is evaluated under a lock, the lock, the
  evaluation and the write happen in one repository method and one transaction. Handlers keep
  their early checks only as fast paths; they never decide.
- **Lock order.** When a member is created, the organization row is locked before the user row.
  No operation locks more than these two rows, so lock ordering cannot deadlock.
- **Database errors are translated by constraint.** Where several rules share a table (stage
  uniqueness vs. artifact uniqueness on track entries, uniqueness vs. foreign keys on members
  and invites), the violated constraint's name selects the response; an unknown constraint is
  reported as a generic constraint error, never as a wrong 409.
- **One-off data cleanup lives in the migration** that adds each rule: duplicate blacklist rows,
  duplicate invites and duplicate stage holders are resolved there, so the rules can be created
  on existing databases.
- **No behaviour change for single users.** Every endpoint answers exactly as before when there
  is no concurrent writer; only the losing side of a race changes from silent success or a
  server error to the documented 409 / 404.

## Out of scope

- The artifact status update endpoint (every racing outcome is valid).
- The satellite task queue: each satellite consumes its own queue; `SKIP LOCKED` becomes relevant
  only if satellites scale out.
- Aligning the legacy single-artifact confirm / force endpoints with the batch ones (LM-587 spec).

## Scenarios

### Scenario: delete URL request overlaps deployment creation
**Given** an uploaded artifact with no deployments
**When** a delete URL request and a deployment creation for it run at the same time
**Then** exactly one wins: either the artifact is in `pending_deletion` and no deployment exists, or the deployment exists and the delete URL request answers 409 "used in deployments"; the artifact is never both

### Scenario: two entries assigned to one stage at once
**Given** a track with a free stage and two entries without a stage
**When** both entries are assigned to that stage at the same time
**Then** one assignment succeeds and the other answers 409 "already assigned"; the stage has exactly one entry

### Scenario: forced reassignment races
**Given** a stage held by entry A and two requests that force-assign it to B and to C
**When** they run at the same time
**Then** the stage ends with exactly one holder (B or C), the other request answers 409, and A is unassigned

### Scenario: refresh token used twice at once
**Given** a valid refresh token
**When** two refresh requests with it run at the same time
**Then** one gets a new token pair and the other answers 400 "Token has been revoked"; a later refresh with the old token answers the same

### Scenario: logout twice
**Given** a refresh token that was already revoked by a logout
**When** logout runs again with it
**Then** it succeeds and nothing changes

### Scenario: collection deleted while an artifact is being created
**Given** an empty collection
**When** a deletion and an artifact creation for it run at the same time
**Then** either the creation finishes first and the deletion answers 409 "has artifacts", or the deletion finishes first and the creation answers 404 "Collection not found"; no artifact record is ever removed by the cascade

### Scenario: quota under concurrency
**Given** an organization with one artifact slot left
**When** two artifact creations run at the same time
**Then** exactly one succeeds and the other answers "reached maximum number of artifacts"; the same holds for orbits, satellites, members, and for the per-user organization limit

### Scenario: duplicate invite
**Given** an organization with no invite for an email
**When** two invites for that email are sent at the same time
**Then** one invite exists and the other request answers 409 "invite already exists"

### Scenario: organization deleted while a member joins
**Given** an organization with one member and a pending invite
**When** the owner deletes the organization while the invitee accepts
**Then** either the join finishes first and the deletion answers 409 "has members", or the deletion finishes first and the join answers 404 "Organization not found"

### Scenario: stage deleted while being assigned
**Given** a free stage
**When** the stage is deleted (without force) while an entry is assigned to it
**Then** either the assignment finishes first and the deletion answers 409 "currently assigned", or the deletion finishes first and the assignment answers 422 "Stage does not belong to this track"; an entry never ends up with a silently cleared stage

### Scenario: forced stage deletion
**Given** a stage held by an entry
**When** the stage is deleted with force
**Then** the entry is unassigned and the stage is removed in one step; an assignment that overlaps is refused, not silently cleared

### Scenario: no concurrency
**Given** any of the operations above with no concurrent writer
**When** it runs
**Then** the response is exactly what it was before this change
