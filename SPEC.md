# Proposals

## Problem

`SPEC.md` (the foundation spec) fixes the database fixture, the configuration, the
layout, the shared support package and the route-test layer. It deliberately leaves
every handler, repository and integration test body as it is. What remains is the bulk
of the suite — about 28 000 lines in 43 files — and it has the problems the audit
(commit `dc84cd40`) lists under handler tests and structure:

1. **Patch stacks instead of fixtures.** Handlers keep their repositories and helper
   handlers as private class attributes, so tests patch them by dotted string:
   1 394 `@patch` decorators, up to 11 on one test, mock parameters that must mirror
   the decorators bottom-up, and 184 mock parameters that the test never reads. The
   same permission check is patched through ten different module paths.
2. **Two styles, no classes.** 52 files use module-level functions; the team wants one
   class per module. Eleven files are between 1 000 and 3 800 lines and mark their
   sections with divider comments instead of classes.
3. **Identifiers re-declared in every test.** 728 of 861 UUID literals are local
   variables repeating the same five or six values.
4. **Shared mutable state.** `unit/handlers/test_artifacts.py` keeps a fake session and
   a list of transaction errors as module globals; one test clears the list by hand.
   Seventeen files hold the handler under test as a module-level singleton. Two
   platform admin tests repeat the same patch that re-enables the audit logger the
   integration suite's migration step disables.
5. **Comments, docstrings, markers, stale names.** 107 comment lines, 22 docstrings,
   766 `@pytest.mark.asyncio` markers made redundant by the configuration, fixture
   names that start with `test_` or read as actions (`test_user`, `create_orbit`),
   test names that do not match the behaviour (`test_get_invite_where`).
6. **Integration tests repeat the same three lines** unpacking the seed fixture and
   constructing the repository, and create their own engines.

## Solution

Convert the suite file by file to one convention, without changing what any test
proves:

- **One collaborator fixture per handler** replaces the patch stacks. A helper in
  `tests/support/mocks.py` builds a handler instance whose private collaborators
  (repositories, helper handlers, clients) are replaced by mocks with the
  collaborator's own interface. A test configures the mocks it needs and asserts on
  them by attribute, never by decorator order.
- **Classes everywhere**, one class per file; files above roughly 800 lines become a
  folder named after the module with one file and one class per area.
- **Shared identifiers** in `tests/support/ids.py`; local identifiers only where a test
  needs a value distinct from the shared ones.
- **No module-level state**: the handler under test, the fake session and the recorded
  transaction errors come from fixtures.
- **Fixtures renamed** to nouns, with the old names kept as aliases until the last file
  is converted.
- **No comments, no docstrings, no asyncio markers**; reasons move into test names.
- **Integration tests** take a `repository` fixture per file and the `engine` fixture
  from the foundation instead of unpacking and constructing by hand.

## Why this approach

- Replacing the collaborators on the handler *instance* with interface-shaped mocks
  needs no change to production code, removes the dotted-path patching entirely, makes
  a misspelt method an error instead of a silent no-op, and makes every collaborator
  available without listing it — the reason the 184 "unused" patches existed
  disappears with them. The existing `lineage_mocks` fixture and the `context` fixture
  of the batch deletion tests already work this way; this spec generalises them.
- File by file, largest first, keeps every pull request reviewable against the old
  file and lets each session run the converted file alone and inside the whole suite.
- Aliases for renamed fixtures let the rename happen per file, where the local
  variables that could shadow the new name are visible.

## What changes in what is tested

Two categories of test change meaning, deliberately, and each task reports them:

- Tests that reached the real permission handler by patching its repositories
  (`get_organization_member_role`, `get_orbit_member_role`, `get_orbit_simple` on the
  permission handler's own repositories — 51 patches) now configure the permission
  mock to allow or to raise. The permission rules themselves are covered by
  `unit/handlers/test_permissions.py`, which keeps testing the real handler.
- Tests of private methods (about 55 calls) and of private attributes through mangled
  names (10 places) stay as they are and are listed in the report, per the decision
  in the foundation spec.

## Out of scope

- Anything under `backend/luml/`.
- Route tests (`unit/api/`), done in the foundation spec.
- New coverage; the gaps in the audit stay gaps.
- Timezone-naive `datetime.now()` calls in test data (120 places) — harmless, not
  touched.

# Design

## Collaborator mocks

`tests/support/mocks.py` provides one function that takes a handler instance and
returns an object with one attribute per private collaborator of the handler class.
A collaborator is a class attribute declared with two leading underscores whose value
is an instance of a class from `luml.repositories` or `luml.handlers`. Everything else
stays real: single-underscore attributes (`AuthHandler._password_hasher`), permission
tables (`PermissionsHandler`'s `__org_permissions`, `__orbit_permissions`) and
transition tables (`ArtifactHandler`'s `__artifact_transitions`). For each
collaborator the function sets on the instance a `Mock` with `spec` set to that class — so its async methods are
`AsyncMock`s, its sync methods `Mock`s, and an attribute the class does not have is an
error — and exposes it under the attribute name without the leading underscores
(`repository`, `orbit_repository`, `permissions_handler`, …). The names follow the
handler's own attribute names, so `deployments` exposes `repo`, `sat_repo`,
`orbit_repo`, …, exactly as the handler calls them.

Two collaborators need more than a spec:

- A repository with a `transaction` context manager (`LineageRepository`) gets a fake
  one: an async context manager that yields one fake session per fixture and records
  every exception that passes through it in a list. The object exposes that session
  and that list (`session`, `transaction_errors`), as `lineage_mocks` does today.
- A helper handler that is itself a mock (`permissions_handler`, `lineage_handler`,
  `email_handler`, `api_key_handler`) is left with all methods returning nothing until
  the test configures them; `check_permissions` returning nothing means "allowed".

Each handler test folder (or file) has a fixture named `mocks` that builds a fresh
handler instance for the test, applies the function, and returns the object; the
handler is reached through `mocks.handler`. Handlers with constructor arguments
(`AuthHandler`, `MonitoringHandler`, `PlatformAdminAuthHandler`) are built with the
same arguments the current module-level instance uses. Collaborators passed through
the constructor (`PlatformAdminAuthHandler`'s `auth_handler` and `google_provider`)
are passed as mocks by the fixture and exposed on the same object; the file's
`_handler` builder becomes that fixture.

What stays patched by dotted path: module-level functions and classes that are not
collaborators of the handler (`jwt.decode` in the auth tests, storage client
factories, the audit logger). Such patches use `patch` as a context manager or
`monkeypatch` inside the test, at most three per test; more means the collaborator
function is missing a case and is extended.

## Files, folders, classes

A file up to about 800 lines after conversion keeps its name and holds one class named
after the module (`TestOrbitSecretHandler`). A larger file becomes a folder named
after the module with `__init__.py`, a `conftest.py` holding the `mocks` fixture and
the module-level builders, and one file per area with one class each. Areas:

| Folder | Files (class each) |
| --- | --- |
| `unit/handlers/artifacts/` | `test_create.py` (creation, upload preparation, lineage inputs), `test_listing.py` (collection listing, sorting, cursors, filters), `test_details.py` (get, update, status transitions), `test_deletion.py` (single deletion, transaction, lineage clean-up), `test_batch_deletion.py` (from `test_artifacts_batch_deletion.py`), `test_access.py` (orbit and collection access checks, foreign tenant cases) |
| `unit/handlers/tracks/` | all four test `TracksHandler`, split by method group: `test_tracks.py` (track create, get, update, delete), `test_entries.py` (entry operations), `test_stages.py` (stage operations), `test_artifact_guards.py` (artifact deletion blocked by tracks) |
| `unit/handlers/deployments/` | `test_create.py`, `test_update.py` (details and status updates), `test_worker.py` (satellite-side operations), `test_delete.py`, `test_satellite_parameters.py` (from `test_satellite_parameters.py`) |
| `unit/handlers/satellites/` | `test_pairing.py` (pairing, authentication, last seen), `test_tasks.py`, `test_deployments.py` (deployment listing and OpenAPI), `test_management.py` (create, update, delete, capabilities) |
| `unit/handlers/auth/` | `test_passwords.py`, `test_tokens.py` (creation, verification, refresh, blacklist), `test_signin.py` (sign-in, sign-up, current user, profile update), `test_oauth.py`, `test_email_flows.py` (confirmation, password reset) |
| `unit/handlers/lineage/` | `test_links.py` (create, delete), `test_batch.py` (apply changes, positions), `test_graph.py` |
| `unit/handlers/bucket_secrets/` | `test_s3.py`, `test_azure.py`, `test_urls.py`, `test_access.py` |
| `unit/handlers/orbits/` | `test_orbits.py`, `test_members.py` |
| `unit/handlers/collections/` | `test_crud.py`, `test_listing.py` (listing, tags, cursors), `test_deletion.py` |
| `unit/handlers/organizations/` | `test_organizations.py`, `test_invites.py` (from `test_organization_invites.py`), `test_members.py` (from `test_organization_members.py`) |
| `integration/repositories/artifacts/` | `test_crud.py`, `test_listing.py`, `test_deletion.py` (single and lineage), `test_batch_deletion.py` (from `test_artifacts_batch_deletion.py`) |
| `integration/repositories/tracks/` | `test_tracks.py`, `test_stages.py`, `test_entries.py`, `test_sync_stages.py` |
| `integration/repositories/deployments/` | `test_crud.py`, `test_updates.py` (status, details, reconcile tasks), `test_listing.py` |

The implementing session may move a test between the areas of its folder when the
body clearly belongs elsewhere; it may not add or drop areas without noting it in the
report. Files not in the table stay single files with one class:
`test_api_keys.py`, `test_monitoring.py`, `test_orbit_secrets.py`,
`test_permissions.py`, `test_platform_admin.py`, `test_platform_admin_auth.py` (its
three classes merge into one, the areas become name prefixes), and every integration
file under 800 lines.

`integration/repositories/test_concurrency_guards.py` stays one file with its one
class: it is a cross-cutting topic whose tests share the race helpers, and splitting
it by repository would scatter them. Its two migration tests already left it in the
foundation spec.

## Identifiers

`tests/support/ids.py` (created by the foundation spec for route tests) holds every
identifier used by more than one file: `USER_ID`, `ORGANIZATION_ID`, `ORBIT_ID`,
`COLLECTION_ID`, `SATELLITE_ID`, `DEPLOYMENT_ID`, `ARTIFACT_ID`, `TRACK_ID`,
`ENTRY_ID`, `STAGE_ID`, `INVITE_ID`, `MEMBER_ID`, `NODE_A_ID`/`NODE_B_ID`, `EDGE_ID`,
and `OTHER_ORGANIZATION_ID`, `OTHER_ORBIT_ID` for foreign-tenant cases. The
identifiers the foundation spec already placed there keep their values, since the
route tests depend on them; a test whose local value differs from the shared one
switches to the shared one unless it needs the distinct value. The added identifiers
take the values the suite already uses most. A test
declares a local identifier only when it needs a second distinct value in the same
test; it then names it by role (`foreign_orbit_id`), never `orbit_id_2`.

## Fixture renames

New names are the primary definition; the old names are aliases (a fixture that
returns the new one) until Task 15 removes them.

| Old | New |
| --- | --- |
| `create_database_and_apply_migrations` | `database_dsn` |
| `create_organization_with_user` | `seeded_organization` |
| `create_organization_with_members` | `seeded_organization_with_members` |
| `create_orbit` | `seeded_orbit` |
| `create_orbit_with_members` | `seeded_orbit_with_members` |
| `create_collection` | `seeded_collection` |
| `create_satellite` | `seeded_satellite` |
| `get_created_user` (`test_user.py`) | `seeded_user` |
| `test_user_create` | `new_user` |
| `test_user_create_in` | `new_user_in` |
| `test_user` | `user` |
| `test_user_out` | `user_out` |
| `test_current_user_out` | `current_user_out` |
| `test_org` | `organization` |
| `test_org_details` | `organization_details` |
| `test_bucket` | `bucket_secret` |
| `test_artifact` | `new_artifact` |
| `manifest_example` | `manifest` |
| `invite_data` | `new_invite` |
| `invite_accept_data` | removed (was identical to `invite_data`) |
| `invite_get_data` | `invite` |
| `invite_user_get_data` | `user_invite` |
| `member_data` | `organization_member` |
| `test_orbit`, `test_orbit_member`, `test_orbit_details` (`test_orbits.py`) | `orbit`, `orbit_member`, `orbit_details` |
| `get_tokens` (`test_auth.py`) | `tokens` |
| `lineage_mocks`, `context` | `mocks` |

When a test body declares a local variable with the new fixture name, the local
variable is renamed by role (`created_user`, `stored_orbit`); the fixture keeps the
short name.

## Test bodies

Per test, in this order:

1. Becomes a method of the class; `self` first.
2. `@pytest.mark.asyncio` goes; `@pytest_asyncio.fixture` becomes `@pytest.fixture`.
3. Patch decorators on collaborators go; the mock parameters go; the body configures
   `mocks.<collaborator>.<method>` where it configured the parameter and asserts on
   the same path. Assertions that used `assert_awaited_once_with` keep their
   arguments verbatim. A mock parameter that the body never read is simply dropped;
   nothing replaces it, because the collaborator is mocked by the fixture anyway.
4. Patches of non-collaborators stay, as context managers inside the body.
5. Local identifier declarations that repeat a shared value become imports from
   `support/ids.py`.
6. The handler is `mocks.handler`; module-level handler instances are deleted.
7. Comments and docstrings go. A comment that stated the reason for the test becomes
   part of the test name; a comment that restated the next line is deleted; a divider
   comment has already become a file or class.
8. The name follows `test_<action>_<expected outcome>[_when_<condition>]`; a test that
   only checks that nothing is raised ends in `_does_not_raise`. Names that no longer
   match the method they exercise are fixed (`test_get_invite_where` →
   `test_get_invites_by_organization_id_returns_all_invites`).
9. Fixture parameters switch to the new names.

Module-level mutable state in `unit/handlers/test_artifacts.py` (the fake deletion
session and the error list) is replaced by the `session` and `transaction_errors`
attributes of `mocks`; the one test that cleared the list by hand asserts on the
fresh per-test list. The two platform admin tests that patch the audit logger's
`disabled` flag to false take one fixture doing that patch instead, so the test
still passes whether or not the integration suite ran before it.

Integration tests: each file (or folder `conftest.py`) defines a `repository` fixture
building the repository under test on `engine`; tests take `repository` and the seed
fixture they need, and the three unpacking lines go. Where a test needs a second
repository it builds it from `engine` in the body. Existing per-file builders that
survive the foundation spec (`_seed_entries`, `_collect_pages`, `_get_listed_artifacts`,
the race helpers) stay as module-level functions of their file or folder `conftest.py`.

## Verification per file

- The number of collected cases of the converted file equals the number before
  conversion (parametrized cases counted), unless a merge or split listed in the task
  says otherwise.
- The file passes alone (`pytest <path>`), passes as part of the whole suite, and
  passes when run directly after the integration suite (`pytest tests/integration
  <path>`).
- No `@patch` decorator on a collaborator method remains in the file; no mock
  parameter is unread; no module-level handler instance, mutable global, comment,
  docstring or asyncio marker remains.
- `ruff format --check`, `ruff check` and `mypy luml utils tests` pass.

## Trade-offs

- Spec-shaped mocks accept any argument list; a wrong argument is caught only by an
  explicit `assert_awaited_once_with`. The existing tests already assert arguments
  where it matters, and the conversion keeps every such assertion.
- Replacing collaborators on the instance relies on the handlers' private attribute
  convention (`__name` class attributes). A handler that switches to constructor
  injection later needs one change in `support/mocks.py`, not in the tests.
- Mocking the permission handler in every handler test narrows 51 tests from
  "handler plus real permission rules" to "handler given a permission verdict". The
  rules remain covered by their own file; the reports list the narrowed tests so the
  reviewer can veto individual ones.

# Scenarios

## Collaborator mocks

## Scenario: every collaborator is a mock with its interface
**Given** the artifacts handler built by the `mocks` fixture
**When** a test reads `mocks.repository.get_artifact`
**Then** it is an `AsyncMock`, `mocks.repository.no_such_method` raises `AttributeError`, and the production class attribute is untouched for other tests

## Scenario: permissions allowed by default
**Given** a test that does not configure `mocks.permissions_handler`
**When** the handler runs a permission-checked operation
**Then** the check returns nothing and the operation proceeds

## Scenario: permissions refused
**Given** `mocks.permissions_handler.check_permissions` configured to raise the insufficient-permissions error
**When** the handler runs the operation
**Then** the error propagates, and the repository mocks are not awaited

## Scenario: fake transaction
**Given** a test of physical artifact deletion
**When** the handler runs the repository calls inside the lineage transaction
**Then** every call receives `mocks.session`, and an error raised inside the transaction is recorded in `mocks.transaction_errors` of that test only

## Scenario: no order dependence
**Given** the converted `unit/handlers/test_platform_admin.py`
**When** it runs directly after `tests/integration`
**Then** the audit line test passes, as it does alone

## Conversion

## Scenario: case count preserved
**Given** `unit/handlers/test_tracks.py` collecting N cases before conversion
**When** the `unit/handlers/tracks/` folder replaces it
**Then** the folder collects N cases and every test name maps to one old test in the report

## Scenario: unused mock parameter
**Given** a test whose decorator patched `TrackRepository.get_track` and whose body never read the parameter
**When** it is converted
**Then** the decorator and the parameter are gone, the body configures nothing for `get_track`, and the test still passes

## Scenario: shared identifier
**Given** a test declaring `user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")` locally
**When** it is converted
**Then** it uses `USER_ID` from `support/ids.py` and declares no local user id

## Scenario: distinct local identifier
**Given** a test that needs an orbit of another tenant
**When** it is converted
**Then** it uses `OTHER_ORBIT_ID` from `support/ids.py` if that role exists there, otherwise a local identifier named by role

## Scenario: reason comment becomes the name
**Given** `test_create_track_other_integrity_error_propagates` in `unit/handlers/test_tracks.py` with its comment that an unrelated constraint must not be masked as a duplicate-name 409
**When** it is converted
**Then** the comment is gone and the name states the outcome (`test_create_track_propagates_integrity_error_other_than_duplicate_name`)

## Scenario: fixture alias during the transition
**Given** Task 1 done and `integration/repositories/test_invites.py` not yet converted
**When** the suite runs
**Then** `create_organization_with_user` still resolves, to the same object as `seeded_organization`

## Scenario: local variable shadowing a new fixture name
**Given** a test taking the `user` fixture whose body assigns `user = await repository.create_user(...)`
**When** it is converted
**Then** the local becomes `created_user` and the assertions that used it are updated

## Scenario: no marker, still async
**Given** `asyncio_mode = auto` from the foundation spec
**When** a converted async test method runs without a marker
**Then** it runs as a coroutine and passes

## Scenario: final sweep
**Given** all tasks done
**When** `tests/` is searched
**Then** there is no `@pytest.mark.asyncio`, no `pytest_asyncio.fixture`, no module-level `Handler()` instance, no comment other than lint or type suppressions, no docstring, no old fixture name, and every test function is a method of a `Test…` class

# Tasks

Conventions for every task: `SPEC.md` (foundation) is fully applied before Task 1; no
file under `backend/luml/` changes; assertions are never weakened or removed; the
converted file's collected case count matches the old file's unless the task says
otherwise; each task ends green on `uv run ruff format --check luml migrations tests
utils`, `uv run ruff check luml migrations tests utils`, `uv run mypy luml utils
tests` and `uv run pytest` from `backend/`, and the converted files also pass alone
and directly after `tests/integration`. Each task's report lists: the old-to-new test
name map, tests whose meaning narrowed (permission mock), tests of private methods or
mangled attributes kept, and any move between areas.

- [x] Task 1 — Support for the conversion
  - [x] Add `backend/tests/support/mocks.py`: the collaborator-replacement function, the fake transaction, and the returned object exposing collaborators, `handler`, `session`, `transaction_errors`; unit-test it in `backend/tests/unit/infra/test_support_mocks.py` (one class) against the lineage and artifacts handlers: every collaborator replaced, spec enforced, transaction recorded, production class untouched afterwards.
  - [x] Extend `backend/tests/support/ids.py` with the identifiers of the Design list that it does not hold yet, taking the values the suite uses most; the existing ones keep their values.
  - [x] In `backend/tests/conftest.py`, `backend/tests/integration/conftest.py` and `integration/repositories/test_user.py`, define every fixture under its new name and add the old names as aliases; delete `invite_accept_data`'s separate definition (alias of `new_invite`).
  - [x] Verify: 1 054-plus cases still collect (plus the new support tests), the whole suite passes with the aliases in place.

- [x] Task 2 — `unit/handlers/artifacts/`
  - [x] Create the folder, `conftest.py` with `mocks` (artifacts handler) and the shared builders of the old file (`_make_listed`, `_pagination_arg`, `_artifact_create_input`, `_pending_artifact`, `_make_artifact`), and the six files of the Design table; move `test_artifacts_batch_deletion.py` in as `test_batch_deletion.py`, replacing its `context` fixture with `mocks`.
  - [x] Convert every test per the Design; replace `DELETION_SESSION` and `DELETION_TRANSACTION_ERRORS` with `mocks.session` and `mocks.transaction_errors`.
  - [x] Verify per file and report.

- [x] Task 3 — `unit/handlers/tracks/`
  - [x] Create the folder with `conftest.py` (`mocks`, `_make_track`, `_make_entry`, `_make_stage`, `_integrity_error`) and the four files; convert; verify; report.

- [x] Task 4 — `unit/handlers/deployments/`
  - [x] Create the folder with `conftest.py` (`mocks`, `_capabilities`, `_satellite`, `_artifact`) and the five files; move `test_satellite_parameters.py` in unchanged apart from class and naming rules; convert; verify; report.

- [x] Task 5 — `unit/handlers/satellites/`
  - [x] Create the folder with `conftest.py` and the four files; convert, including the six mangled-path patches of the permission handler's repositories, which become configuration of `mocks.permissions_handler`; verify; report.

- [x] Task 6 — `unit/handlers/auth/` and `test_api_keys.py`
  - [x] Create the `auth/` folder with `conftest.py` (`mocks` building the handler with the module's secret, algorithm and provider; `passwords`, `tokens`, `tokens_by_purpose`) and the five files; `jwt.decode` patches stay as context managers; convert `test_api_keys.py` in place to one class; verify; report.

- [ ] Task 7 — `unit/handlers/lineage/` and `unit/handlers/collections/`
  - [ ] Lineage: create the folder, move `HandlerMocks`/`lineage_mocks` into `mocks` from `support/mocks.py` (dropping the hand-written patch list), three files; convert; verify.
  - [ ] Collections: create the folder with three files; convert; verify; report both.

- [ ] Task 8 — `unit/handlers/bucket_secrets/` and `test_orbit_secrets.py`
  - [ ] Bucket secrets: folder with four files (`_owner_s3_secret`, `_scoped_get_bucket_secret` in `conftest.py`); orbit secrets: one class in place; convert; verify; report.

- [ ] Task 9 — `unit/handlers/orbits/`, `unit/handlers/organizations/`, `test_permissions.py`
  - [ ] Orbits: folder with two files (`orbit`, `orbit_member`, `orbit_details` fixtures and `_scoped_bucket_secret`, `_owner_orbits` in `conftest.py`).
  - [ ] Organizations: folder with three files from `test_organizations.py`, `test_organization_invites.py`, `test_organization_members.py`.
  - [ ] Permissions: one class in place; it tests the real `PermissionsHandler` through `mocks`, which replaces only its repositories, so its repository patches go like everywhere else.
  - [ ] Convert; verify; report.

- [ ] Task 10 — `test_monitoring.py`, `test_platform_admin.py`, `test_platform_admin_auth.py`
  - [ ] One class each; `test_platform_admin_auth.py`'s three classes merge with name prefixes; one audit logger fixture replaces the two repeated `disabled` patches; `test_platform_admin_auth.py`'s `_handler` builder becomes the `mocks` fixture; convert; verify; report.

- [ ] Task 11 — `unit/repositories/` and `unit/infra/`
  - [ ] `test_artifacts.py` and `test_lineage.py` to one class each (`test_base.py` already is); `unit/infra/test_security.py` and `test_middleware.py` to one class each; identifiers and naming rules; verify; report.

- [ ] Task 12 — `integration/repositories/artifacts/` and `test_lineage.py`
  - [ ] Artifacts: folder with `conftest.py` (`repository` fixture, `_add_artifact_to_track`) and the four files, `test_artifacts_batch_deletion.py` moving in as `test_batch_deletion.py`; lineage: one class in place with `repository` and `_get_listed_artifacts`; convert; verify; report.

- [ ] Task 13 — `integration/repositories/tracks/` and `integration/repositories/deployments/`
  - [ ] Tracks: folder with `conftest.py` (`repository` fixtures for track, stage and entry repositories; `_seed_entries`, `_collect_pages`) and four files; deployments: folder with three files; convert; verify; report.

- [ ] Task 14 — remaining `integration/repositories/` files
  - [ ] `test_api_keys.py`, `test_bucket_secrets.py`, `test_collections.py`, `test_invites.py`, `test_monitoring.py`, `test_orbit_secrets.py`, `test_orbits.py`, `test_organization_members.py`, `test_organizations.py`, `test_platform_admin.py`, `test_satellites.py`, `test_token_blacklist.py`, `test_user.py`, `test_concurrency_guards.py`: one class each, `repository` fixture, seed fixtures under new names, stale names fixed (`test_get_invite_where`, `test_delete_invite_where`, `test_get_satellite_get_satellite_by_hash`); convert; verify; report.

- [ ] Task 15 — `integration/handlers/`, `integration/migrations/`, aliases, final sweep
  - [ ] Convert the three files of `integration/handlers/` and `integration/migrations/` to one class each under the new fixture names.
  - [ ] Remove every fixture alias from the `conftest.py` files and `test_user.py`.
  - [ ] Run the final-sweep scenario checks and record the results in the report: no marker, no `pytest_asyncio.fixture`, no module-level handler instance, no comment or docstring, no old fixture name, every test a method; total collected count and both layers' run times.
