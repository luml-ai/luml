# Proposals

## Problem

The backend test suite (`backend/tests/`, 62 files, 1 054 collected cases) grew from
several hands without a shared convention. A full audit was done on 2026-09-29 and is
kept in this branch's history (commit `dc84cd40`, file `SPEC.md`). The findings that
block everyday work, in the order they hurt:

1. **The test run can write into the development database.** The database fixture
   always drops and recreates a database named `df_studio_test`, but then migrates and
   runs every test against whatever database the configured connection string names.
   The checked-in `backend/.env.test`, which the settings load under pytest, names the
   local development database `df_studio`. A plain `uv run pytest` on a developer
   machine therefore migrates `df_studio` and fills it with test data. CI is safe only
   because it sets the connection string explicitly.
2. **A new database is built for every integration test.** Drop, create and all 42
   migrations, about one second per test; 277 tests take 265 seconds while the 777
   unit tests take 11. The backend CI workflow is one sequential job of six to seven
   minutes, and the lint and unit results arrive only when the whole job ends.
3. **No pytest configuration** exists: no test paths, no asyncio mode (766 identical
   `asyncio` markers), no way to run one layer other than by path.
4. **One 698-line `conftest.py` serves two layers that share almost nothing**, holds
   dataclasses that 17 files import from it, duplicates the seeding of user,
   organization and bucket secret in two fixtures, and picks roles and inviters at
   random. Engines are created in 25 places and disposed in 4.
5. **The same builders are rewritten in every integration file**: create an artifact
   (4 copies), create a sibling orbit (3 identical), create a sibling organization (2
   identical), run an alembic command (2).
6. **Route tests copy their scaffolding into every file**: the authentication stub is
   declared 12 times under four names, the application factory 13 times under five
   names, the production error handler is re-implemented three times, routers are
   mounted under prefixes that differ from production, and two tests call route
   functions directly instead of going through HTTP. Two route tests mock the
   repository and run the route and the handler together.
7. **Files sit in the wrong layer**: three handler-with-database tests hide among
   repository tests, migration tests have no folder, infrastructure tests sit in the
   root of `unit/`.

## Solution

This spec is the **foundation** half of the clean-up: everything that touches the
fixtures, the configuration, the folder layout, the CI workflow and the route-test
layer. It leaves every handler and repository test body as it is. The second half —
converting each handler, repository and integration file to classes with per-handler
collaborator fixtures, shared identifiers, renamed fixtures, no comments — is
`SPEC-2.md` on this branch; it assumes every task of this spec is done.

At a glance:

- The database fixture refuses any connection string that does not name the test
  database, migrates one **template database** once per run and gives every test a
  clone of it (`CREATE DATABASE … TEMPLATE`, about 50 ms instead of about 1 s).
- Pytest gets a configuration with automatic asyncio mode; the CI workflow becomes
  three parallel jobs (static checks, unit, integration), with dependency caching and
  the type checker covering the tests.
- Files move into a layout where the folder says the layer and the file says the
  module: `integration/repositories/`, `integration/handlers/`,
  `integration/migrations/`, `unit/infra/`.
- Shared code moves to an importable `tests/support/` package; `conftest.py` is split
  per layer; seed fixtures chain, are deterministic and own their engines.
- Route tests get one application fixture built from the production application with
  a replaceable authentication principal, one file per router, classes, production
  URLs, and no direct calls of route functions.

## Why this approach

- Template cloning keeps the strongest isolation the suite has today — a fresh
  database per test — so no test changes, including the ones that run migrations up
  and down or open several connections on purpose. Emptying tables between tests or
  rolling back a transaction would be marginally faster but needs exceptions for
  exactly those tests.
- Splitting the CI job alone would not shorten it: the integration job would still
  take four and a half minutes. The fixture is the cause; the split only makes lint
  and unit failures visible earlier.
- Doing the foundation first and the file-by-file conversion second keeps each pull
  request reviewable and lets the conversion assume a stable layout, support package
  and fixture set.

## Decisions taken

| Question | Decision |
| --- | --- |
| Isolation of integration tests | Template database, clone per test |
| Large test files (1 000–3 800 lines) | A folder per module, one file and one class per area — applied in the second spec |
| Route tests that run the handler | Split: the route test mocks the handler, the rule moves to the handler test; an end-to-end layer is a later task |
| CI | Three jobs in one workflow |
| Scope of this spec | Foundation only; file-by-file conversion in a second spec |
| `satellite_field_condition_cases.json` | Stays where it is (shared with the frontend test) |
| Tests of private methods and mangled attributes | Stay; listed in the task report |
| Type checking of tests | Added to CI (it already passes) |
| `@pytest.mark.asyncio` markers | Left in place; removed file by file in the second spec |
| Fixture renames (`test_user`, `create_orbit`, …) | Second spec, file by file |
| `unit/api/` | Fully reworked in this spec: fixture, merge per router, classes, production URLs |

## Out of scope

- Any file under `backend/luml/`, `backend/migrations/`, `backend/alembic.ini`.
- Handler, repository and integration test bodies, apart from moving files and
  replacing the duplicated builders and engine creation with the shared ones.
- Deprecation warnings printed by the run (one from `luml/handlers/bucket_secrets.py`,
  one from alembic's configuration); both need changes outside the tests.
- Branch protection settings on GitHub (which checks are required) — done by hand
  after the workflow is merged.

# Design

## Database fixture

Names: the test database is `df_studio_test`; the template is `df_studio_test_template`;
both names are constants next to the fixture and nowhere else.

**Connection string guard.** The integration session reads the configured
`POSTGRESQL_DSN`, parses it as a SQLAlchemy URL and stops with an error naming the
expected database when the URL's database is not `df_studio_test`. The check runs at the
start of the integration session, not at import, so `pytest tests/unit` never touches
it and needs no database. The administrative connection is the same URL with the
database replaced by `postgres` and the driver marker removed, built through URL
manipulation, not text replacement.

**Session preparation** (once per run, before the first integration test):

1. Terminate every other session connected to `df_studio_test` or
   `df_studio_test_template`, drop both if they exist.
2. Create `df_studio_test_template` and run the existing migration helper
   (`utils/db.py`) against it up to head. The helper disposes its engine; nothing
   else may stay connected to the template, or the clone step fails.
3. At the end of the session drop the template.

The preparation runs to completion inside a synchronous session-scoped fixture (its
async work is driven to completion there) so that no connection or engine bound to the
session's event loop outlives it; per-test fixtures keep pytest-asyncio's default
function loop scope.

**Per test** (the existing `create_database_and_apply_migrations` fixture keeps its
name and still yields the test database's connection string):

1. Terminate other sessions on `df_studio_test`, drop it if a previous test or an
   interrupted run left it behind.
2. `CREATE DATABASE df_studio_test TEMPLATE df_studio_test_template`.
3. Yield the connection string.
4. Terminate other sessions on `df_studio_test` and drop it.

Consequences that need no special handling: migration tests that downgrade the
schema work on their private clone; tests that open several connections and commit
work as before; `alembic current` from the CLI test sees the template's
`alembic_version`; the application's global engine (`luml/infra/db.py`), used by the
handler-with-database tests, is bound to the same connection string and therefore to
the test database.

`backend/.env.test` names `df_studio_test`. The CI workflow keeps passing the connection
string explicitly.

## Pytest configuration

`[tool.pytest.ini_options]` in `backend/pyproject.toml`:

| Option | Value | Effect |
| --- | --- | --- |
| `testpaths` | `tests` | `uv run pytest` from `backend/` collects the suite |
| `asyncio_mode` | `auto` | async tests and fixtures need no marker; existing markers stay valid |

Layers are selected by path (`tests/unit`, `tests/integration`); no markers are
registered.

## CI workflow

`.github/workflows/[backend] tests-and-linters.yml` keeps its triggers and path filters
and gets three jobs that run in parallel:

| Job | Steps | Database |
| --- | --- | --- |
| `checks` | `ruff format --check`, `ruff check`, `mypy luml utils tests` | no |
| `unit-tests` | `pytest tests/unit` | no |
| `integration-tests` | Postgres 15 as a service container with a readiness check, `pytest tests/integration` | yes |

All three install dependencies with uv through the official setup action with its
cache enabled. The environment variables of the current test step (`PYTEST_VERSION`,
`POSTGRESQL_DSN`, `AUTH_SECRET_KEY`, `BUCKET_SECRET_KEY`) move to the two test jobs.
The type check now covers everything the mypy configuration lists (`luml`, `utils`,
`tests`); it passes today with no changes.

## Layout

```
backend/tests/
  conftest.py                         data fixtures used by both layers
  satellite_field_condition_cases.json
  support/
    __init__.py
    seeds.py                          result dataclasses of the seed fixtures
    builders.py                       create_artifact, create_sibling_orbit, create_sibling_organization
    alembic.py                        run an alembic command on an engine
    ids.py                            identifiers shared by more than one file
    auth.py                           authentication principals for route tests
  unit/
    api/
      conftest.py                     application, client, principal
      test_auth.py
      test_orbit_artifacts.py
      test_orbit_collections.py
      test_orbit_lineage.py
      test_orbit_satellites.py
      test_orbit_tracks.py
      test_orbits_members.py
      test_organization_bucket_secrets.py
      test_organization_invites.py
      test_organization_members.py
      test_platform_admin.py
      test_satellites.py
      test_service.py
      test_user_invites.py
    handlers/                         unchanged
    repositories/                     unchanged
    infra/
      test_security.py                from unit/test_security.py
      test_middleware.py              from unit/test_security_headers.py
  integration/
    conftest.py                       database, engine, seed fixtures
    repositories/                     from integration/repository/
    handlers/
      test_artifacts.py               one test from repository/test_lineage.py
      test_deployments.py             two tests from repository/test_deployments.py
    migrations/
      test_env.py                     from integration/test_migrations_env.py
      test_041_satellite_contract.py  from integration/test_satellite_contract_migration.py
      test_039_concurrency_guards.py  two tests from repository/test_concurrency_guards.py
```

Every folder is a package (`__init__.py`), as today, because file basenames repeat
across folders. Moves are done with `git mv` so history follows the file.

Which tests move out of `repositories/`:

| From | Tests | To |
| --- | --- | --- |
| `test_deployments.py` | `test_partial_details_update_preserves_untouched_columns`, `test_details_update_treats_explicit_null_secrets_as_cleared`, with the `deployment_handler` fixture | `handlers/test_deployments.py` |
| `test_lineage.py` | `test_concurrent_deletion_of_the_last_live_artifacts_removes_the_component` | `handlers/test_artifacts.py` |
| `test_concurrency_guards.py` | `test_migration_keeps_the_longest_blacklist_expiry`, `test_migration_extends_legacy_rows_to_the_token_expiry` | `migrations/test_039_concurrency_guards.py` |

The moved tests keep their bodies, including private attribute access; helpers they
need travel with them or come from `support/`.

## Support package and conftest split

`tests/conftest.py` keeps only the plain data fixtures (`invite_data`,
`invite_get_data`, `invite_user_get_data`, `invite_accept_data`, `member_data`,
`test_user_create`, `test_user_create_in`, `test_user`, `test_user_out`,
`test_current_user_out`, `test_org`, `test_org_details`, `manifest_example`,
`test_bucket`, `test_artifact`) under their current names. Fixtures that await nothing
become plain synchronous fixtures returning the object; the explicit
`scope="function"` goes.

`tests/integration/conftest.py` holds the database fixture, an `engine` fixture and
the seed fixtures:

- `engine`: a function-scoped async engine on the test database, disposed at teardown.
  Every seed fixture uses it instead of creating its own; every test that today calls
  the engine factory on the connection string uses the fixture instead (24 tests plus
  the `get_created_user` fixture in `test_user.py`). The `engine` field of the seed
  dataclasses stays, so test bodies do not change.
- Seed fixtures chain: `create_orbit` builds on `create_organization_with_user`
  instead of repeating the user, organization, limits and bucket secret steps;
  `create_collection` on `create_orbit`; `create_satellite` on `create_collection`, as
  today. Duplicated assertions go; assertions that narrow an optional result stay.
- Determinism: `create_organization_with_members` invites on behalf of the
  organization's owner; `create_orbit_with_members` gives the ten members alternating
  roles, admin first. `random` is not imported in `conftest.py`.
- The two identical invite fixtures (`invite_data`, `invite_accept_data`) stay both,
  because renames are out of scope; the second is declared as an alias of the first.

`tests/support/seeds.py` holds the seven result dataclasses moved out of `conftest.py`;
the 17 files that import them from `tests.conftest` import them from there.

`tests/support/builders.py`:

| Builder | Replaces | Behaviour |
| --- | --- | --- |
| `create_artifact(engine, template, collection_id, *, name, status=uploaded, artifact_type=model, extra_values=None, description=None, unique_identifier=None)` | `_create_artifact` in batch deletion, lineage, tracks; `_make_artifact` in artifacts; `_artifact` in concurrency guards | Copies the template, sets the given fields, a fresh unique identifier and bucket location, creates the row |
| `create_sibling_orbit(engine, organization_id, bucket_secret_id)` | three identical copies | Creates an orbit named `sibling orbit` in the same organization |
| `create_sibling_organization(engine, user_id)` | two identical copies | Creates an organization named `sibling org` owned by the user |
| `create_collection(engine, orbit_id, name, type=model)` | `_make_collection` in artifacts, `_create_other_orbit_collection` in lineage (partly) | Creates a collection and returns it |

The tracks integration file builds artifacts from its own manifest today; it keeps
passing its own template to `create_artifact` so that nothing it asserts changes.
Helpers that exist in one file only (`_seed_entries`, `_collect_pages`, `_race`,
`_split`, `_wait_for_lock_waiters`, …) stay where they are.

`tests/support/alembic.py` holds one function that runs an alembic command
(`upgrade` or `downgrade` to a revision) on an engine, replacing `_alembic` in the
concurrency guards and `_migrate` in the satellite contract migration test.

## Route tests

`tests/support/auth.py` defines the principals a route test can act as, each a pair
of credentials and identity exactly as the production backend would return them:

| Principal | Scopes | Identity |
| --- | --- | --- |
| signed-in user (default) | `authenticated`, `jwt` | user `USER_ID`, `caller@example.com` |
| API-key user | `authenticated`, `api_key` | same user |
| satellite | `authenticated`, `satellite` | satellite and orbit ids given by the test |
| anonymous | none | none |

`tests/unit/api/conftest.py`:

- `app`: session-scoped, the production application (`AppService`) as is — routers
  under their production prefixes, production error handlers, CORS, security headers.
- `principal`: function-scoped, defaults to the signed-in user. A class overrides it
  to act as another principal, or a test parametrizes it indirectly.
- `client`: function-scoped test client on `app`; while it is alive, the
  authentication backend's `authenticate` is patched to return `principal` (or
  nothing for anonymous). The satellite path of the real backend also records the
  satellite's last-seen time; the stub does not, so the `touch_last_seen` patches in
  the satellite worker tests go.

Rules for every route test:

- Handlers are mocked at the handler class method, never repositories. The two
  pagination tests become: a route test per router asserting that `cursor=` reaches
  the handler unchanged and that an "Invalid cursor" application error from the
  handler is answered with 400 and the standard detail body; and one handler test per
  handler (`unit/handlers/test_artifacts.py`, `unit/handlers/test_collections.py`)
  asserting that an empty cursor string reaches the repository as no cursor. The
  satellite test that mocks the repository becomes a route test asserting that a
  not-found error from the handler is answered with 404.
- URLs are the production URLs (`/v1/organizations/…`, `/v1/auth/…`,
  `/satellites/v1/…`, `/v1/invitations/…`).
- Every route is called through the client. The two direct calls
  (`create_artifact` in `test_artifact_routes.py`, `get_satellite_openapi` in
  `test_orbit_satellites.py`) become HTTP calls; the artifact one keeps its two
  principals (signed-in user, API-key user) and its assertion on the scopes forwarded.
- One file per router, one class named after the router module, tests as methods:

| File | Class | Takes tests from |
| --- | --- | --- |
| `test_auth.py` | `TestAuth` | `test_auth.py` |
| `test_orbit_artifacts.py` | `TestOrbitArtifacts` | `test_artifact_routes.py`, `test_orbit_artifacts_batch_routes.py`, artifacts half of `test_pagination_routes.py` |
| `test_orbit_collections.py` | `TestOrbitCollections` | collections tests of `test_orbit_tags_routes.py`, collections half of `test_pagination_routes.py` |
| `test_orbit_tracks.py` | `TestOrbitTracks` | tracks tests of `test_orbit_tags_routes.py` |
| `test_orbit_lineage.py` | `TestOrbitLineage` | `test_lineage_routes.py` |
| `test_orbit_satellites.py` | `TestOrbitSatellites` | `test_orbit_satellites.py` |
| `test_orbits_members.py` | `TestOrbitsMembers` | `test_orbit_members_routes.py` |
| `test_organization_bucket_secrets.py` | `TestOrganizationBucketSecrets` | same file |
| `test_organization_invites.py` | `TestOrganizationInvites` | same file |
| `test_organization_members.py` | `TestOrganizationMembers` | same file |
| `test_platform_admin.py` | `TestPlatformAdmin` | same file |
| `test_satellites.py` | `TestSatellites` | `test_satellites.py`, `test_satellite_contract.py` |
| `test_service.py` | `TestService` | `test_stats_removed.py` |
| `test_user_invites.py` | `TestUserInvites` | same file |

- Well-known identifiers used by more than one file (`USER_ID`, `ORGANIZATION_ID`,
  `ORBIT_ID`, `COLLECTION_ID`, and the satellite, deployment and artifact ids that
  repeat) are declared once in `tests/support/ids.py` and imported; file-local ids
  stay local. The second spec extends the same module to the handler tests.
- `test_platform_admin.py` keeps its own application fixture: the admin routes are
  mounted only when the admin configuration is set at construction, and the file
  patches that configuration around the construction. It follows the other rules.
- Tests that only inspect router registration or the OpenAPI document
  (`test_lineage_router_is_registered_for_organizations`,
  `test_get_deployment_route_is_registered_once`, the contract test, the stats tests)
  stay in the file of the router they inspect and use `app` where they need one.

## Trade-offs

- A session-scoped application means a test cannot swap the application's
  configuration; the one file that needs to (platform admin) builds its own. Building
  the production application per test would cost about 0.4 s each.
- Keeping fixture names such as `test_user` and `create_orbit` for now leaves the
  naming rule of the second spec unapplied in the new `conftest.py` files; the rename
  touches about 300 signatures and can shadow local variables, so it is done file by
  file where the bodies are read anyway.
- `create_artifact` in `support/builders.py` accepts a template because the artifacts
  and tracks files rely on different manifests; a single built-in template would
  change what those files assert on.

# Scenarios

## Database fixture

## Scenario: the connection string names another database
**Given** `POSTGRESQL_DSN` names `df_studio`
**When** any integration test is collected and run
**Then** the run stops before any database is dropped or migrated, with an error that names `df_studio_test` as the required database, and `df_studio` is untouched

## Scenario: unit tests need no database
**Given** no Postgres is reachable
**When** `pytest tests/unit` runs
**Then** all unit tests pass and no connection is attempted

## Scenario: the template is migrated once
**Given** a run with 277 integration tests
**When** the run completes
**Then** the migration helper ran exactly once, on `df_studio_test_template`, and every test received `df_studio_test` cloned from it

## Scenario: every test starts from a fresh database
**Given** a test that inserts an organization and a test that counts organizations, in either order
**When** both run in one session
**Then** the counting test sees only what it inserted itself

## Scenario: a schema-changing test does not leak
**Given** `test_041_satellite_contract` ends with the schema downgraded to `040`
**When** the next integration test runs
**Then** it receives a database at head

## Scenario: leftovers of an interrupted run
**Given** a previous run was killed while `df_studio_test` and `df_studio_test_template` existed, with an idle connection still open on one of them
**When** a new run starts
**Then** both are dropped and recreated and the run proceeds

## Scenario: the CLI test still sees the head revision
**Given** the per-test clone
**When** `alembic current` runs against its connection string
**Then** it reports the head revision

## Scenario: handler-with-database tests use the test database
**Given** the application's global engine is bound to the configured connection string
**When** a test in `integration/handlers/` runs
**Then** the handler writes to `df_studio_test` and the test's engine reads it back

## Scenario: run time
**Given** the local Postgres in Docker
**When** `pytest tests/integration` runs
**Then** it finishes in under 90 seconds with 277 passed (265 seconds before)

## Configuration and CI

## Scenario: async tests without markers
**Given** `asyncio_mode = auto`
**When** the suite is collected
**Then** 1 054 cases are collected, the same identifiers as before, and the existing markers cause no warning

## Scenario: a unit failure is reported without waiting for the database
**Given** a pull request that breaks a handler test
**When** the workflow runs
**Then** `unit-tests` fails within about a minute while `integration-tests` is still running, and `checks` reports independently

## Scenario: only the integration job starts Postgres
**Given** the three jobs
**When** they run
**Then** `checks` and `unit-tests` have no service container and no `POSTGRESQL_DSN` dependency on a database being up

## Scenario: the type check covers the tests
**Given** a test file with a type error
**When** `checks` runs
**Then** `mypy luml utils tests` fails the job

## Layout

## Scenario: history follows moved files
**Given** `integration/repository/test_orbits.py` moved to `integration/repositories/test_orbits.py`
**When** `git log --follow` is run on the new path
**Then** the file's previous commits are listed

## Scenario: no test is lost in the move
**Given** the moves in the Design table
**When** the suite is collected
**Then** 1 054 cases are collected; the three handler-driven tests are under `integration/handlers/`, the two migration guards under `integration/migrations/`, and `integration/repositories/` imports no handler

## Scenario: repeated basenames resolve
**Given** `unit/handlers/test_artifacts.py`, `unit/repositories/test_artifacts.py`, `integration/repositories/test_artifacts.py`, `integration/handlers/test_artifacts.py`
**When** the suite is collected
**Then** all four are collected under distinct module paths

## Support package

## Scenario: no builder exists twice
**Given** the suite after the change
**When** the tests folder is searched for functions creating an artifact, a sibling orbit, a sibling organization or running alembic
**Then** each exists once, in `tests/support/`

## Scenario: nothing imports from a conftest
**Given** the suite after the change
**When** the tests folder is searched for `from tests.conftest import`
**Then** there is no match

## Scenario: seed data is deterministic
**Given** `create_orbit_with_members` and `create_organization_with_members`
**When** they run twice
**Then** the roles of the members and the inviter of each invite are the same both times

## Scenario: every engine is disposed
**Given** a run of the integration suite with the forced termination of connections temporarily removed from the per-test teardown
**When** the run completes
**Then** every drop succeeds, because no fixture or test left an engine open

## Scenario: chained seeds see one organization
**Given** `create_satellite`
**When** the fixture resolves
**Then** its organization, orbit, collection and satellite belong to one user and one organization created once, with limits lifted once

## Route tests

## Scenario: default principal
**Given** a route test that does not override `principal`
**When** it calls a user route
**Then** the route sees a signed-in user with the `jwt` scope and `USER_ID`

## Scenario: anonymous principal
**Given** a class overriding `principal` with the anonymous principal
**When** it calls a protected route
**Then** the response is 401 and the handler mock is not awaited

## Scenario: satellite principal
**Given** a class overriding `principal` with a satellite
**When** it deletes a worker deployment
**Then** the handler receives that satellite's id, and no last-seen update is attempted

## Scenario: production URL
**Given** the artifacts router
**When** the test posts to `/v1/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/delete-urls`
**Then** the route answers, and a post to the same path without the `/v1/organizations` prefix answers 404

## Scenario: production error handler
**Given** a handler mock raising an application error with status 409 and a message
**When** the route is called
**Then** the response is 409 with `{"detail": <message>}`, produced by the application's own handler

## Scenario: production validation handler
**Given** a body with a non-finite number
**When** the lineage batch route is called
**Then** the response is 422 with the message the production validation handler produces

## Scenario: forwarded scopes without a direct call
**Given** the API-key principal
**When** the artifact creation route is called over HTTP
**Then** the handler mock is awaited with scopes `["authenticated", "api_key"]`

## Scenario: pagination split
**Given** the artifacts list route and a handler mock raising "Invalid cursor" with 400
**When** the route is called with `cursor=garbage`
**Then** the response is 400 with `{"detail": "Invalid cursor"}` and no repository is patched
**And** a handler test calling the handler with an empty cursor string asserts that the repository receives no cursor

## Scenario: platform admin keeps its application
**Given** `test_platform_admin.py`
**When** its tests run
**Then** they build their own application under the admin configuration and pass, and every other route file uses the shared `app`

## Scenario: route-test scaffolding exists once
**Given** the suite after the change
**When** `unit/api/` is searched for authentication backend subclasses, application factories or exception handlers
**Then** none is found outside `conftest.py` and `test_platform_admin.py`

# Tasks

Conventions for every task: no file under `backend/luml/` or `backend/migrations/`
changes; test assertions are never weakened or removed; the collected count stays
1 054 (777 unit, 277 integration) unless the task says otherwise; each task ends green
on `uv run ruff format --check luml migrations tests utils`,
`uv run ruff check luml migrations tests utils`, `uv run mypy luml utils tests` and
`uv run pytest`, all from `backend/`. Until Task 1 is merged, run pytest with
`POSTGRESQL_DSN` exported as the value from `backend/.env.test` with the database part
replaced by `df_studio_test`; from Task 1 on, `.env.test` names the test database and
plain `uv run pytest` is correct. Tests carry no explanatory comments or docstrings;
new tests are class methods.

- [x] Task 1 — Database fixture: connection string guard and template database
  - [x] In `backend/tests/conftest.py`, replace the text-replacement derivation of the administrative connection string with URL parsing; add the session start check that stops with an error naming `df_studio_test` when the configured database differs; keep `create_database_and_apply_migrations` as the per-test fixture name and return type.
  - [x] Add the session-scoped preparation: terminate sessions, drop and create `df_studio_test_template`, migrate it with `utils/db.py`, drop it at session end; make sure no connection outlives it.
  - [x] Rewrite the per-test fixture as terminate-drop-clone-yield-terminate-drop using `CREATE DATABASE … TEMPLATE`.
  - [x] Point `POSTGRESQL_DSN` in `backend/.env.test` at `df_studio_test`.
  - [x] Verify: `pytest tests/unit` passes with Postgres stopped; `pytest tests/integration` with the DSN naming `df_studio` stops before touching it; two consecutive integration runs pass with 277 cases each; a run interrupted mid-way followed by a full run passes; the integration run takes under 90 seconds locally (record the number in the task report).

- [x] Task 2 — Pytest configuration and CI workflow
  - [x] Add `[tool.pytest.ini_options]` with `testpaths` and `asyncio_mode = "auto"` to `backend/pyproject.toml`; confirm 1 054 cases still collect with unchanged identifiers and no marker warnings.
  - [x] Rewrite `.github/workflows/[backend] tests-and-linters.yml` into the jobs `checks`, `unit-tests`, `integration-tests` per the Design table: uv installed through the official setup action with caching, Postgres 15 as a service container with a readiness check in `integration-tests` only, the existing environment variables on the two test jobs, `mypy luml utils tests` in `checks`.
  - [x] Verify locally: `uv run mypy luml utils tests` passes; `uv run pytest tests/unit` and `uv run pytest tests/integration` pass separately. Note in the task report that `unit-tests` and `integration-tests` must be added by hand to the repository's required checks next to `checks`.

- [ ] Task 3 — Layout
  - [ ] `git mv backend/tests/integration/repository` to `integration/repositories`; create `integration/handlers/`, `integration/migrations/`, `unit/infra/` as packages.
  - [ ] Move `unit/test_security.py` to `unit/infra/test_security.py` and `unit/test_security_headers.py` to `unit/infra/test_middleware.py`.
  - [ ] Move `integration/test_migrations_env.py` to `integration/migrations/test_env.py` and `integration/test_satellite_contract_migration.py` to `integration/migrations/test_041_satellite_contract.py`.
  - [ ] Move the two handler-driven deployment tests with their `deployment_handler` fixture into `integration/handlers/test_deployments.py`, the lineage concurrent-deletion test into `integration/handlers/test_artifacts.py`, and the two blacklist migration guards into `integration/migrations/test_039_concurrency_guards.py`; helpers they need travel with them (duplicated for now if the source file still needs them; Task 4 unifies).
  - [ ] Update every import path that referenced a moved module; verify 1 054 cases collect and pass, `git log --follow` works on a moved file, and `integration/repositories/` imports no handler.

- [ ] Task 4 — Support package, conftest split, seeds and engines
  - [ ] Create `backend/tests/support/` with `seeds.py` (the seven dataclasses from `conftest.py`), `builders.py` (`create_artifact`, `create_sibling_orbit`, `create_sibling_organization`, `create_collection`), `alembic.py` (one command runner); replace `from tests.conftest import …` in all 17 files.
  - [ ] Create `backend/tests/integration/conftest.py` with the database fixture from Task 1, the `engine` fixture and the seed fixtures; leave the data fixtures in `backend/tests/conftest.py` as synchronous fixtures without explicit scope.
  - [ ] Chain the seed fixtures (`create_orbit` on `create_organization_with_user`), remove duplicated assertions, replace `random` with the deterministic choices of the Design, declare `invite_accept_data` as an alias of `invite_data`.
  - [ ] Replace every engine creation in tests and fixtures (24 tests, `get_created_user`, the migration tests) with the `engine` fixture; keep the `engine` field on the seed dataclasses.
  - [ ] Replace the duplicated builders in `integration/repositories/test_artifacts.py`, `test_artifacts_batch_deletion.py`, `test_lineage.py`, `test_tracks.py`, `test_concurrency_guards.py`, `test_collections.py`, `test_deployments.py`, `test_orbit_secrets.py`, `test_bucket_secrets.py`, `test_orbits.py` and in `integration/migrations/` with the `support` ones; tracks keeps passing its own template.
  - [ ] Verify: 1 054 cases pass; no `from tests.conftest import` remains; each builder exists once; the integration run with the forced connection termination temporarily disabled in teardown still drops every database (then restore the termination as a safety net).

- [ ] Task 5 — Route tests
  - [ ] Create `backend/tests/support/ids.py` with the shared identifiers, `backend/tests/support/auth.py` with the four principals, and `backend/tests/unit/api/conftest.py` with the session-scoped `app`, the `principal` and `client` fixtures patching the backend's `authenticate` per test.
  - [ ] Merge and rename the sixteen files into the fourteen of the Design table, one class per file, tests as methods, production URLs, handler-level mocks only; delete the local backends, factories and error handlers; drop the `touch_last_seen` patches.
  - [ ] Rewrite the two direct route-function calls as HTTP calls, keeping the artifact test's two principals and its scopes assertion.
  - [ ] Split the pagination tests: route tests asserting cursor forwarding and the 400 mapping in `test_orbit_artifacts.py` and `test_orbit_collections.py`; handler tests for the empty cursor in `unit/handlers/test_artifacts.py` and `unit/handlers/test_collections.py`. Rewrite the satellite foreign-deployment test as a route test on the handler's not-found error. Record the resulting unit count in the task report (it changes by the tests added and merged here) and confirm no other test is added or removed.
  - [ ] Verify: no authentication backend subclass, application factory or exception handler is defined in `unit/api/` outside `conftest.py` and `test_platform_admin.py`; `pytest tests/unit/api` passes in under 15 seconds; the whole suite is green.
