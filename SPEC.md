# Backend test suite: audit and restructuring spec

Status: draft for review. Nothing in the test suite has been changed yet.
Audited revision: `458001c4` (branch `oleh/26q3/platform-admin`), 2026-09-29.
Scope: `backend/tests/` only.

## 1. Purpose

The backend test suite grew from several hands (people and coding agents) without a
shared convention. This document records what the suite looks like today, what is wrong
with it, which conventions it should follow, and the ordered work needed to get there.

It is written so that a separate agent can execute it phase by phase. Section 9 lists
the decisions that must be made by the reviewer before the work starts.

### Non-goals

- No change to production code under `backend/luml/`.
- No change to what is tested: every existing test case keeps its behaviour and its
  assertions. The refactor moves, renames, groups and de-duplicates.
- No new coverage. Coverage gaps are listed in section 5.9 for information only.

## 2. Snapshot

| Metric | Value |
| --- | --- |
| Test files | 62 |
| Lines in `tests/` (incl. `conftest.py`, JSON) | 32 888 |
| Test functions defined | 906 |
| Test cases collected (with parametrization) | 1 054 (777 unit, 277 integration) |
| Unit suite result / time | 777 passed, 11 s |
| Integration suite result / time | 277 passed, 265 s (4 min 25 s) |
| Files that use test classes | 10 of 62 (78 of 906 test functions) |
| `@patch` decorators | 1 394 |
| `@pytest.mark.asyncio` markers | 766 |
| Hard-coded `UUID("…")` literals | 861, of which 728 are declared inside test bodies |
| Comment lines / docstrings in tests | 107 / 22 |
| `conftest.py` files | 1 (root, 698 lines) |
| Pytest configuration | none (no `[tool.pytest.ini_options]`, no `pytest.ini`) |

Layout today:

```
tests/
  conftest.py                          698 lines, all fixtures for all layers
  satellite_field_condition_cases.json
  unit/
    test_security.py
    test_security_headers.py
    api/            16 files   route tests, handlers mocked
    handlers/       20 files   handler tests, repositories mocked
    repositories/    3 files   repository helpers, no database
  integration/
    test_migrations_env.py
    test_satellite_contract_migration.py
    repository/     19 files   repositories against a real Postgres
```

## 3. History: when each layer appeared

Authors are the squash-merge authors of the pull request, i.e. the PR owner, not
necessarily the person or agent who typed the test.

| Date | Commit | Author | What appeared |
| --- | --- | --- | --- |
| 2025-04-21 | `239eecff` | Nikita Gonchar | The layout itself: `conftest.py`, `integration/repository/`, `unit/handlers/`. Integration and unit tests exist from the very first test commit. |
| 2025-05 … 2025-12 | #24, #29, #34, #52, #89, #109, #165, #197 | Kate Krut, Nikita | Growth of the two original layers: repository integration tests and handler unit tests. |
| 2026-06-17 | #572 | Kate Krut | Tracks: the two largest files of the suite (`unit/handlers/test_tracks.py`, `integration/repository/test_tracks.py`). |
| 2026-08-17 | `ab71e185` (#630) | Oleh Kostromin | **`unit/api/` is created** (`test_organization_bucket_secrets.py`, `test_satellites.py`, `test_stats_removed.py`) together with `unit/test_security.py`. |
| 2026-08-27 … 2026-09-18 | #633, #612, #643, #654, #670 | Kate Krut | More `unit/api/` files: tags, orbit satellites, lineage routes, artifact routes, batch deletion routes, organization invites. |
| 2026-09-10 | `be68bd86` (#643) | Kate Krut | **`unit/repositories/` is created** (`test_lineage.py`), then `test_base.py` (#655) and `test_artifacts.py` (#686, orbie-dfs). |
| 2026-09-14 | #655, #659 | Kate Krut | `test_concurrency_guards.py`, `test_migrations_env.py`. |
| 2026-09-18 … 2026-09-28 | #666, #671, #674, #676, #686, #687, #692, #701, #702 | orbie-dfs | One small `unit/api/` file per bug fix. |
| 2026-09-25 | #679 | Oleh Kostromin | `satellite_field_condition_cases.json`, `test_satellite_parameters.py`, `test_satellite_contract*.py`. |
| 2026-09-29 | #706 | Oleh Kostromin | Platform admin tests in all three layers. |

Line ownership by `git blame`:

| Directory | Kate Krut | Oleh Kostromin | Nikita | orbie-dfs | Others |
| --- | --- | --- | --- | --- | --- |
| `unit/api` | 959 | 626 | 0 | 475 | 0 |
| `unit/handlers` | 14 193 | 3 271 | 2 813 | 657 | 91 |
| `unit/repositories` | 104 | 0 | 0 | 84 | 0 |
| `integration` | 6 317 | 916 | 972 | 212 | 95 |
| `conftest.py` | 231 | 0 | 441 | 15 | 11 |

## 4. Answers to the questions that started the audit

**Are the files in `integration/` really integration tests?**
Yes. Every file in `integration/repository/` runs a repository against a real Postgres
with all migrations applied. `test_invites.py` is a plain example of that. Two groups
do not belong to the folder they sit in: tests that drive a handler (section 5.5) and
two migration tests that sit one level up.

**Are unit tests on the API needed? It looks odd.**
They are legitimate, but the name hides what they are. They start a FastAPI application
in process, replace the handler with a mock, and check the HTTP contract of a route:
request validation, authentication and scopes, that path and body values reach the
handler, the response status and shape, that a route is or is not registered. None of
that can be checked by a handler unit test, and none of it needs a database, so the
unit layer is the right place. What is wrong is how they are written (section 5.2).

**Should the API be covered by integration tests instead?**
There is currently no test that goes through HTTP, handler, repository and database in
one run. That is a real gap, but a different task. See decision D1.

**Are unit tests on repositories needed?**
The three files test pure logic that lives in the repository layer and needs no
database: translation of a database integrity error into an application error,
validation of a sort field, building a pagination cursor. That is a valid unit test.
The folder is fine; it is small and should stay small.

**What are `DELETION_SESSION` and `_deletion_transaction` in `unit/handlers/test_artifacts.py`?**
Physical deletion of an artifact runs several repository calls inside one database
transaction. The handler opens that transaction through the lineage repository. In a
unit test there is no database, so the test replaces the transaction with a fake one:
a context manager that hands out one fake session and remembers any exception that
passes through it. `DELETION_SESSION` is that fake session; the tests use it to assert
that every repository call received the same session, which proves the calls share one
transaction. `DELETION_TRANSACTION_ERRORS` is the list of remembered exceptions; one
test uses it to assert that a failure reached the transaction, which means a rollback.
The idea is sound. The implementation is two module-level mutable globals in a module
of 74 tests (finding F-14).

**What are `HandlerMocks`, `lineage_mocks` and the async context manager in `unit/handlers/test_lineage.py`?**
The same idea done properly: a fixture that patches every collaborator of the lineage
handler once (fifteen mocks and a fake transaction) and gives the test one object with
named mocks. It replaces a stack of sixteen `@patch` decorators on each of the 31
tests. This is the best pattern in the handler layer and the model for the rest
(section 6.4). Its weakness is that it is local to one file.

**Patches that the test never uses.**
Confirmed: 184 mock parameters in 163 tests are never referenced in the test body.
Most of them are needed to keep the code from reaching a real dependency (the
permission check is the typical case), but they are repeated as decorators on every
test instead of being set up once. Some are left over and patch something the tested
path never calls. Details in F-11.

**`create_test_client`, `StubAuthBackend`: should they be in `conftest.py`?**
Yes. The same authentication stub is declared 12 times in 11 files under four
different names, and the application factory 13 times under five names (F-06).

**`satellite_field_condition_cases.json`: should it be a fixture?**
No. The file is a contract shared by two languages: the backend test
`unit/handlers/test_satellite_parameters.py` and the frontend test
`frontend/src/hooks/satellites/useSatelliteFields.test.ts` both read it, so that the
backend and the frontend evaluate field conditions the same way. It has to stay a data
file. Only its location is questionable (F-19, decision D4).

## 5. Findings

Severity: **H** blocks reliable work or can damage data, **M** costs time on every
change, **L** cosmetic or local.

### 5.1 Structure and naming

**F-01 (M) Two styles in one suite.** 52 files use module-level test functions, 10 use
classes. The class files are the recent ones. The team preference is one class per
module.

**F-02 (M) Files that are too large to navigate.**

| File | Lines | Tests |
| --- | --- | --- |
| `unit/handlers/test_artifacts.py` | 3 832 | 74 |
| `unit/handlers/test_tracks.py` | 2 469 | 80 |
| `unit/handlers/test_deployments.py` | 2 352 | 53 |
| `unit/handlers/test_satellites.py` | 1 941 | 49 |
| `integration/repository/test_tracks.py` | 1 652 | 51 |
| `unit/handlers/test_lineage.py` | 1 380 | 31 |
| `unit/handlers/test_bucket_secrets.py` | 1 298 | 28 |
| `unit/handlers/test_auth.py` | 1 260 | 57 |
| `unit/handlers/test_orbits.py` | 1 200 | 28 |
| `unit/handlers/test_collections.py` | 1 072 | 24 |
| `integration/repository/test_artifacts.py` | 1 035 | 35 |

Several of them already mark their internal sections with divider comments
(`# ---- TrackStagesHandler ----`, `# --- Mint ---`), 20 dividers in total. Each
divider is a class that was not written.

**F-03 (M) No rule for what a file is named after.** Three schemes are mixed:

- after the module under test (`test_orbits.py`, `test_collections.py`);
- after a feature that cuts across modules (`test_concurrency_guards.py`,
  `test_pagination_routes.py`, `test_artifacts_batch_deletion.py`,
  `test_satellite_parameters.py`, which tests functions of the deployments handler);
- after a bug fix (`test_stats_removed.py`, `test_user_invites.py`).

In `unit/api/` some files carry the suffix `_routes` and some do not
(`test_orbit_tags_routes.py` next to `test_orbit_satellites.py`), and the file name
does not tell which router is tested (`test_satellites.py` tests the satellite worker
router, `test_orbit_satellites.py` the orbit satellites router).

**F-04 (L) One handler, three files.** The organization handler is tested in
`test_organizations.py`, `test_organization_invites.py` and
`test_organization_members.py`. The user repository is tested in `test_user.py`,
`test_organizations.py`, `test_organization_members.py` and `test_api_keys.py`. This is
a reasonable split by topic, but it is not written down anywhere, so new tests land at
random.

**F-05 (L) Test names that do not describe the behaviour.** Examples in
`integration/repository/test_invites.py`: `test_get_invite_where` tests listing the
invites of an organization, `test_delete_invite_where` tests deleting all invites of an
organization. Neither name matches the repository method it exercises.

### 5.2 Route tests (`unit/api/`)

**F-06 (M) The same scaffolding is copied into every file.**

| Duplicated item | Copies | Names in use |
| --- | --- | --- |
| Authentication stub for a signed-in user | 12 classes in 11 files | `_SignedInBackend`, `StubAuthBackend`, `_SatelliteBackend`, `_NoCredentialsBackend`, plus one `Mock` of the backend |
| Application and client factory | 13 | `_client`, `_create_test_client`, `create_test_client`, `_app`, a `client` fixture, and one inline construction |
| Handler of application errors re-implemented in the test | 3 | in `test_lineage_routes.py`, `test_pagination_routes.py`, `test_satellites.py` |
| `USER_ID`, `ORGANIZATION_ID`, `ORBIT_ID` constants | 23, 13, 11 declarations across the suite | the same three UUID values everywhere, also as `ORG_ID` |

**F-07 (M) Three different ways to reach a route, chosen at random.**

1. A bare application with one router and a stub backend (most files).
2. The full production application (`test_stats_removed.py`,
   `test_satellite_contract.py`, `test_platform_admin.py`).
3. A direct call of the route function with a mocked request, without HTTP
   (`test_artifact_routes.py`, one test in `test_orbit_satellites.py`).

Way 3 skips validation, authentication and serialization, which are the reasons a
route test exists. Way 1 mounts routers with different prefixes in different files
(some with `/v1/organizations`, some without), so the URL in the test is not the URL
of the product. Way 1 also does not install the production error handlers, which is
why three files re-implement one (F-06), and the re-implementation can drift from the
real one.

**F-08 (M) Route tests that are not route tests.** `test_pagination_routes.py` and one
test in `test_satellites.py` mock the repository instead of the handler, so they run
the route and the handler together. They need up to five patches each and break when
the handler internals change. They are valuable, but they are a different kind of test
and are not marked as such.

**F-09 (L) One file per bug fix.** Seven files contain one or two tests each
(`test_artifact_routes.py`, `test_orbit_members_routes.py`,
`test_organization_bucket_secrets.py`, `test_organization_invites.py`,
`test_organization_members.py`, `test_satellite_contract.py`,
`test_user_invites.py`). Each of them pays the full
scaffolding cost of F-06 for one test.

### 5.3 Handler tests (`unit/handlers/`)

**F-10 (H) Patch stacks instead of fixtures.** Handlers keep their repositories as
private class attributes, so a test cannot pass a fake in; it has to patch by dotted
string path. The result is 1 394 decorators, up to 11 on one test, and the order of
the mock parameters must mirror the decorators bottom-up. A mistake in the order is
silent: the test receives the wrong mock and may still pass. Two files already avoid
this (`test_lineage.py` with the `lineage_mocks` fixture,
`test_artifacts_batch_deletion.py` with the `context` fixture) and are several times
shorter per test.

**F-11 (M) Mocks that the test does not use.** 184 mock parameters in 163 tests are
never referenced in the body.

| File | Tests with an unused mock | Unused mocks |
| --- | --- | --- |
| `unit/handlers/test_tracks.py` | 68 of 80 | 68 |
| `unit/handlers/test_artifacts.py` | 29 of 74 | 48 |
| `unit/handlers/test_orbits.py` | 17 of 28 | 17 |
| `unit/handlers/test_monitoring.py` | 12 of 20 | 12 |
| `unit/handlers/test_bucket_secrets.py` | 9 of 28 | 9 |
| `unit/handlers/test_deployments.py` | 7 of 53 | 7 |
| `unit/handlers/test_satellites.py` | 6 of 49 | 6 |
| others (8 files) | 15 | 17 |

Two different cases hide behind the number. A mock that silences a dependency the
tested path does call (mostly the permission check) is needed but belongs in a shared
fixture. A mock for something the tested path never calls is dead and should go. They
can only be told apart by removing the patch and running the test.

**F-12 (M) One object, ten patch paths.** The permission check is patched through ten
different dotted paths (`luml.handlers.permissions.…` 108 times,
`luml.handlers.artifacts.…` 41 times, and eight more). All of them resolve to the same
method, so the choice is arbitrary.

**F-13 (M) Identifiers re-declared in every test.** 728 of the 861 UUID literals are
local variables inside test bodies, the same five or six values repeated
(`0199c337-09f1-…` 189 times). Files written later declare module constants instead;
both styles coexist, sometimes in one file.

**F-14 (H) Shared mutable state between tests.** `unit/handlers/test_artifacts.py`
keeps the fake session and the list of transaction errors as module globals. The list
is appended to by every test that fails inside the transaction and is cleared by
exactly one test, by hand, before it asserts. Any new test that asserts on the list
without clearing it depends on execution order. The handler objects themselves are
module-level singletons in 17 files, which is harmless only as long as handlers keep
no state.

**F-15 (M) A unit test that depends on the integration suite.**
`unit/handlers/test_platform_admin.py` re-enables the audit logger by hand, with a
comment explaining that the migration step of the integration tests disables existing
loggers. The unit test therefore behaves differently depending on whether integration
tests ran earlier in the same process.

**F-16 (M) Tests of private methods and private attributes.** About 55 calls go to
underscore-prefixed handler methods, and 10 places reach private attributes through
the mangled name (`_ArtifactHandler__repository` and similar). These tests break on
any internal rename and pin the implementation rather than the behaviour.

**F-17 (L) Comments and docstrings.** 107 comment lines in 13 files and 22 docstrings
in 11 files, against the project rule that tests carry no explanatory comments. Three
kinds: section dividers (20, see F-02), restatements of the next line (`# Sort by
version DESC.`), and genuine reasons for the test (`# An empty list would skip
resolving the source artifact…`). The third kind is information that the test name
should carry.

**F-18 (L) Small inconsistencies.** Imports inside test bodies (6 places). Fixtures
whose names start with `test_` (`test_orbit`, `test_user`, `test_bucket`,
`test_artifact`, `test_org`), which read as tests. Fixtures named as actions
(`create_orbit`, `get_created_user`, `get_tokens`) although they return data. Fixtures
declared async although they only build an object (every data fixture in
`conftest.py`). 120 naive `datetime.now()` calls next to timezone-aware ones.

### 5.4 Shared fixtures and the database

**F-20 (H) The test run can write into the development database.** The fixture that
prepares the database always drops and creates a database with a fixed name,
`df_studio_test`, but then applies migrations to, and runs every test against,
whatever database the configured connection string names. The two are equal only by
convention. The checked-in test environment file names the local development database
`df_studio`, so a plain `uv run pytest` on a developer machine creates an unused
`df_studio_test`, then migrates `df_studio` and fills it with test data. CI is safe
because it sets the connection string explicitly. The administrative connection is
derived by replacing the text `df_studio_test` inside the connection string, which
silently does nothing for any other database name.

**F-21 (H) A new database for every test.** The database is dropped, created and
migrated through all 42 migrations for each of the 277 integration tests.
The integration run takes 265 seconds, about one second per test, and nearly all of
it is fixture setup: nine of the ten slowest phases in the run are setup, each between
1.1 and 1.4 seconds. The unit suite, three times larger, runs in 11 seconds.

**F-22 (M) One `conftest.py` for two layers that share nothing.** Usage by layer:

| Fixture group | Used by unit tests | Used by integration tests |
| --- | --- | --- |
| Database and seeded entities (7 fixtures) | 0 | 259 |
| Plain data objects (15 fixtures) | 95 | 71, of which 59 are one fixture (`test_artifact`) |

The file also holds the seven result dataclasses, which 17 test files import with
`from tests.conftest import …`. Importing from `conftest.py` is fragile: the module can
be loaded twice under two names.

**F-23 (M) Seed fixtures duplicate each other and hide failures.** The fixture that
creates an organization and the fixture that creates an orbit each create the user,
the organization and the bucket secret on their own, line for line, instead of one
building on the other. They contain assertions, two of them duplicated, so a failed
seed is reported as a failed test. Two invite fixtures are identical. Two seed
fixtures pick roles and inviters with `random`, so the data differs between runs.

**F-24 (M) Database engines are never closed.** Engines are created in 25 places and
disposed in 4. The fixture compensates by forcibly terminating all connections to the
test database before dropping it.

**F-25 (M) The same builder is written again in each integration file.**

| Helper | Copies | Files |
| --- | --- | --- |
| Create an artifact from a template | 4 (`_create_artifact` ×3, `_make_artifact`, plus `_artifact`) | artifacts, batch deletion, lineage, tracks, concurrency guards |
| Create a sibling orbit | 3, identical | collections, deployments, orbit secrets |
| Create a sibling organization | 2, identical | bucket secrets, orbits |
| Run an alembic command on an engine | 2 | concurrency guards, satellite contract migration |
| Artifact manifest | 2 | `conftest.py`, tracks |

Every integration test also starts with the same three lines that unpack the fixture
and construct the repository.

### 5.5 Tests in the wrong layer

**F-26 (M) Handler tests inside `integration/repository/`.** Two tests in
`test_deployments.py` and one in `test_lineage.py` drive a handler against the real
database. The first two use the application's global engine, so they work only when
the configured connection string is the test database. The third swaps private
attributes of the handler class. They are the only handler-with-database tests in the
suite and they are hidden among repository tests.

**F-27 (L) Migration tests have no home.** `test_migrations_env.py` and
`test_satellite_contract_migration.py` sit in the root of `integration/`;
`test_concurrency_guards.py` also runs migrations up and down but sits in
`repository/`. The satellite contract test hard-codes revision `040`.

### 5.6 Configuration

**F-28 (M) No pytest configuration.** No test paths, no asyncio mode (hence 766
identical markers), no registered markers, no way to select a layer other than by
path. Deprecation warnings are printed on every run and nobody sees them: 4 in the
unit run from the bucket secrets handler, 281 in the integration run from the alembic
configuration.

**F-29 (L) Type checking skips the tests.** The project configuration lists `tests`
for mypy, CI runs mypy on `luml` only. The tests carry type annotations and 6
`type: ignore` comments that nothing verifies.

### 5.7 Data files

**F-19 (L) The shared condition cases live in the root of the backend tests.** The
frontend test imports the file through a relative path that climbs out of the frontend
into `backend/tests/`. Nothing in the file or next to it says that it has a second
consumer, so it looks like a stray backend fixture and is easy to move or delete by
mistake.

### 5.8 Tests without assertions

Four tests contain no assertion and no expected exception; they pass as long as
nothing raises:

- `integration/repository/test_lineage.py`: `test_refresh_node_copy_ignores_an_unknown_artifact`
- `unit/handlers/test_satellite_parameters.py`:
  `test_unknown_condition_and_validator_types_are_skipped`,
  `test_empty_field_list_accepts_parameters_as_before`,
  `test_required_field_hidden_by_a_condition_may_be_absent`

This is acceptable for "does not raise" tests, but the intent should be visible in the
name. No change required beyond the rename rule in 6.2.

### 5.9 Coverage gaps (information only)

Modules with no test that imports or patches them:

- Routes: `bucket_secret_urls`, `orbit_deployments`, `orbit_secrets`, `orbits`,
  `organization`, `user`, `user_api_keys`.
- Repositories: `limits`, `permissions` (may be exercised indirectly).
- Infrastructure: `encryption`, `utils/organizations`; storage clients are touched by
  two files only.
- No end-to-end test through HTTP, handler, repository and database.

## 6. Target conventions

### 6.1 Layers

| Layer | Folder | Real database | What is mocked | What it proves |
| --- | --- | --- | --- | --- |
| Route | `unit/api/` | no | the handler | HTTP contract of a route |
| Handler | `unit/handlers/` | no | repositories, clients, other handlers | business rules |
| Repository logic | `unit/repositories/` | no | the session | pure logic inside a repository |
| Infrastructure | `unit/infra/` | no | as needed | security backend, middleware |
| Repository | `integration/repositories/` | yes | nothing | queries, constraints, locking |
| Handler with database | `integration/handlers/` | yes | permission check only | a handler and its repositories together |
| Migrations | `integration/migrations/` | yes | nothing | upgrade, downgrade, CLI |

A test belongs to the layer of the outermost thing it calls.

### 6.2 Files, classes, names

- One test file per module under test, named after the module:
  `luml/handlers/tracks.py` is tested by `unit/handlers/test_tracks.py`,
  `luml/api/orbits/orbit_lineage.py` by `unit/api/test_orbit_lineage.py`. No `_routes`
  suffix; the folder already says it.
- Every test is a method of a class. A file has one class named after the module
  (`TestTracksHandler`) unless decision D7 allows grouping by the method under test.
- A cross-cutting topic (concurrency guards, pagination) is a class inside the file of
  the module it exercises, not a file of its own. If it exercises several modules, it
  is split between their files.
- A test name states the behaviour and the condition:
  `test_<action>_<expected outcome>[_when_<condition>]`. A test that only checks that
  nothing is raised says so in its name.
- No comments and no docstrings. A reason that was in a comment goes into the test
  name. Section dividers become classes.

### 6.3 Fixtures, helpers, constants

- `tests/conftest.py`: only what both layers use.
- `tests/unit/conftest.py`: data objects and the shared mocks of 6.4.
- `tests/unit/api/conftest.py`: application, client and authentication fixtures.
- `tests/integration/conftest.py`: database, engine and seeded entities.
- Importable code (result dataclasses, builder functions, constants) lives in ordinary
  modules under `tests/support/`, never in `conftest.py`.
- A fixture is a noun and does not start with `test_` (`user`, `orbit`,
  `seeded_orbit`). A builder function is a verb (`create_artifact`).
- A fixture is async only when it awaits something.
- Seed fixtures build on each other (orbit on organization, collection on orbit), do
  not assert, and do not use randomness.
- Well-known identifiers (`USER_ID`, `ORGANIZATION_ID`, `ORBIT_ID`, `COLLECTION_ID`,
  …) are declared once in `tests/support/` and imported. A test declares a local
  identifier only when it needs a value distinct from the shared ones.

### 6.4 Mocking

- A handler test receives its collaborators from one fixture per handler that patches
  them all and returns an object with named mocks, as `lineage_mocks` does today. A
  test configures only the mocks it cares about.
- The permission check is allowed by default in that fixture; a test that checks
  permissions overrides it.
- One patch path per target: the path of the module that defines the object.
- `@patch` decorators remain acceptable for a single, test-specific patch. More than
  three on one test means a fixture is missing.
- No module-level mutable state. A fake transaction and its recorded errors are
  created per test by a fixture.
- A route test mocks the handler, never the repository. A test that needs the route
  and the handler together belongs to the handler-with-database layer or is rewritten
  as two tests.

### 6.5 Route tests

- One shared application fixture built from the production application, with the
  production error handlers and the production URL prefixes, and the authentication
  backend replaced by a stub.
- Stub backends are provided for: signed-in user with a session, signed-in user with
  an API key, satellite, anonymous.
- A route is always called through HTTP. Direct calls of route functions are rewritten.

### 6.6 Database

- The test database name comes from one place. The fixture refuses to run when the
  configured connection string does not name that database.
- The database is created and migrated once per run; tests are isolated from each
  other without re-running migrations (decision D3 chooses the mechanism).
- Tests that change the schema (migration tests, the migration part of the concurrency
  guards) get a database of their own.
- Every engine created by a fixture is disposed by that fixture.

### 6.7 Configuration

- Pytest settings live in the project configuration: test paths, automatic asyncio
  mode, registered markers `unit` and `integration` applied by folder, warnings from
  project code turned into errors.
- CI runs the two layers as separate steps so that a unit failure is reported in
  seconds.

## 7. Target layout

```
tests/
  conftest.py
  support/
    ids.py                  shared identifiers
    builders.py             create_artifact, create_sibling_orbit, …
    seeds.py                result dataclasses of seed fixtures
    auth.py                 authentication stubs
    alembic.py              run a migration command on an engine
  unit/
    conftest.py
    api/
      conftest.py
      test_auth.py
      test_orbit_artifacts.py         artifact_routes + batch + pagination (artifacts)
      test_orbit_collections.py       tags (collections) + pagination (collections)
      test_orbit_tracks.py            tags (tracks)
      test_orbit_lineage.py
      test_orbit_satellites.py
      test_orbits_members.py
      test_organization_bucket_secrets.py
      test_organization_invites.py
      test_organization_members.py
      test_platform_admin.py
      test_satellites.py              worker router, contract
      test_user_invites.py
      test_service.py                 stats route removed, route registration
    handlers/
      test_<handler>.py               one per handler
    repositories/
      test_<repository>.py
    infra/
      test_security.py
      test_middleware.py
  integration/
    conftest.py
    repositories/
      test_<repository>.py
    handlers/
      test_artifacts.py
      test_deployments.py
    migrations/
      test_env.py
      test_satellite_contract.py
      test_concurrency_guards.py
```

## 8. Work plan

Rules for every phase:

- One phase is one commit series that leaves the suite green.
- The number of collected test cases stays 1 054 (777 unit, 277 integration) unless
  the phase states a different number and the reason.
- No file under `luml/` is touched.
- A test body is changed only as far as the phase requires; assertions are never
  weakened or removed.
- Formatting and lint checks pass after each phase.

### Phase 0. Baseline

- Record the list of collected test identifiers and the run time of both layers.
- Outcome: a reference to compare every later phase against.

### Phase 1. Safety of the database fixture (F-20)

- The test database name has a single source; the administrative connection is built
  from the connection string properly instead of by text replacement.
- The fixture stops with a clear message when the connection string names any other
  database.
- The checked-in test environment file names the test database.
- Outcome: a plain local `pytest` cannot touch the development database.

### Phase 2. Configuration (F-28, F-29)

- Pytest settings are added; the 766 asyncio markers are removed.
- Markers `unit` and `integration` are applied by folder.
- Outcome: `pytest -m unit` and `pytest -m integration` select the layers; the
  collected count is unchanged.

### Phase 3. Shared support code (F-13, F-22, F-25)

- `tests/support/` is created with identifiers, builders, seed dataclasses.
- `conftest.py` is split by layer; imports from `tests.conftest` are replaced.
- Duplicated builders in integration files are replaced by the shared ones.
- Local identifier declarations inside tests are replaced by the shared constants.
- Fixtures are renamed by the rule in 6.3; async is dropped where nothing is awaited.
- Outcome: no helper exists in more than one copy; no test imports from a
  `conftest.py`.

### Phase 4. Seed fixtures and engines (F-23, F-24)

- Seed fixtures are chained, lose their assertions and their randomness.
- Every engine has an owner that disposes it.
- Outcome: the forced termination of connections is no longer needed for a clean run.

### Phase 5. Route tests (F-06, F-07, F-08, F-09)

- One application fixture and the four authentication stubs replace all local copies.
- URLs in tests become the production URLs.
- Direct calls of route functions become HTTP calls.
- The tests that mock a repository are moved to the handler-with-database layer or
  split, per decision D1.
- Files are merged and renamed to one per router; tests become class methods.
- Outcome: no route test file defines an application, a client or a backend.

### Phase 6. Handler tests (F-10, F-11, F-12, F-14, F-15)

Per handler file, largest first:

- A collaborators fixture is introduced; patch stacks are removed.
- Each unused mock is checked: removed when the test passes without it and reaches no
  real dependency, otherwise covered by the fixture.
- Module-level fake session and error list become a fixture.
- The logger workaround in the platform admin test is replaced by a fixture that
  guarantees the logger state regardless of what ran before.
- Tests become class methods; divider comments become classes or files per D7.
- Outcome: no test has more than three patch decorators; the file passes when run
  alone, when run after the integration suite, and in random order.

### Phase 7. Integration tests (F-01, F-05, F-26, F-27)

- Folders `repositories/`, `handlers/`, `migrations/` are created and files moved.
- Handler-driven tests are moved to `integration/handlers/` and stop using the global
  engine and mangled private attributes as far as possible without changing production
  code; what remains is listed in the phase report.
- Tests become class methods; the repeated unpacking lines are replaced by fixtures
  that provide the repository.
- Stale names are fixed.
- Outcome: `integration/repositories/` contains only repository tests.

### Phase 8. Database lifecycle (F-21)

- Implemented per decision D3.
- Outcome: integration run time drops from 265 seconds to under one minute, with the
  same collected count and no order dependence.

### Phase 9. Comments and leftovers (F-17, F-18, F-19)

- Comments and docstrings are removed; reasons move into test names.
- Imports inside test bodies move to the top of the file.
- The shared condition cases file is handled per decision D4.
- Outcome: no comment other than lint or type suppressions remains in `tests/`.

Phases 1 and 2 are independent of everything else and can be merged first. Phases 5,
6 and 7 depend on phase 3 and are independent of each other. Phase 8 depends on 4.

## 9. Decisions for the reviewer

Each has a recommendation; the work plan assumes the recommendation unless changed.

**D1. What to do with route tests that also run the handler (F-08), and with the
missing end-to-end layer.**
Recommended: keep `unit/api/` as the route layer with the handler mocked; rewrite the
two pagination tests so that the route test mocks the handler and the cursor rule is
asserted in the handler test; do not add an end-to-end layer in this refactor and open
a separate task for a thin smoke set (sign in, create an orbit, upload an artifact).
Alternative: introduce `integration/api/` now and move these tests there against a
real database.

**D2. Classes everywhere.**
Recommended: yes, all 906 test functions become methods, done file by file inside
phases 5, 6 and 7 rather than as one mechanical change, so that grouping is decided
while the file is being read.

**D3. How tests are isolated once the database is created only once.**
Recommended: create and migrate once per run, empty all tables between tests.
Migration tests and concurrency tests keep a private database. Alternative: wrap each
test in a transaction that is rolled back, which is faster but does not work for the
tests that open several connections or commit on purpose (concurrency guards, batch
deletion, lineage), so two mechanisms would coexist.

**D4. The shared condition cases file (F-19).**
Recommended: keep it as a data file, move it to a folder that says what it is
(`backend/tests/contracts/`), and update the frontend import in the same change.
Alternative: leave it where it is.

**D5. Tests of private methods (F-16).**
Recommended: leave as they are in this refactor and list them in the phase 6 report;
rewriting them through public methods changes what is tested and needs a review of
its own.

**D6. Type checking of tests (F-29).**
Recommended: add `tests` to the CI type check after phase 6, when the number of
suppressions is known. Alternative: remove `tests` from the type checker
configuration so that configuration and CI agree.

**D7. One class per file versus several.**
The stated preference is one class per module. For the eleven files in F-02 one class
of 50 to 80 methods does not improve navigation.
Recommended: one class per file by default; a file above roughly 800 lines becomes a
folder named after the module with one file and one class per area
(`unit/handlers/tracks/test_stages.py` with `TestTrackStages`).
Alternative: keep one file per module and allow several classes in it, grouped by the
method under test, as `test_platform_admin_auth.py` does today.

**D8. Order and size of the work.**
Recommended: phases 1 and 2 immediately (small, remove a real hazard), then phase 3,
then 5, 6, 7 as separate pull requests per folder. Phase 6 is the largest, about
21 000 lines, and is best split into one pull request per handler file.

## 10. Appendix: file inventory

Columns: lines, tests in classes, tests at module level, fixtures, module-level
helpers, comment lines, `@patch` decorators, largest patch stack.

### unit/api

| File | Lines | In class | Module | Fixt. | Helpers | Cmt | Patch | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| test_artifact_routes.py | 69 | 0 | 1 | 0 | 0 | 0 | 1 | 1 |
| test_auth.py | 112 | 0 | 5 | 0 | 1 | 0 | 5 | 1 |
| test_lineage_routes.py | 405 | 0 | 11 | 0 | 3 | 2 | 11 | 2 |
| test_orbit_artifacts_batch_routes.py | 213 | 4 | 0 | 0 | 2 | 0 | 4 | 1 |
| test_orbit_members_routes.py | 61 | 0 | 1 | 0 | 0 | 0 | 1 | 1 |
| test_orbit_satellites.py | 98 | 0 | 3 | 0 | 1 | 0 | 3 | 1 |
| test_orbit_tags_routes.py | 132 | 0 | 4 | 0 | 1 | 0 | 4 | 1 |
| test_organization_bucket_secrets.py | 85 | 0 | 2 | 0 | 1 | 0 | 2 | 1 |
| test_organization_invites.py | 71 | 1 | 0 | 0 | 1 | 0 | 1 | 1 |
| test_organization_members.py | 76 | 1 | 0 | 0 | 1 | 0 | 1 | 1 |
| test_pagination_routes.py | 126 | 0 | 2 | 0 | 1 | 0 | 9 | 5 |
| test_platform_admin.py | 347 | 0 | 17 | 2 | 2 | 0 | 9 | 1 |
| test_satellite_contract.py | 20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| test_satellites.py | 136 | 0 | 4 | 0 | 1 | 0 | 6 | 3 |
| test_stats_removed.py | 43 | 0 | 3 | 0 | 0 | 0 | 1 | 1 |
| test_user_invites.py | 66 | 0 | 2 | 0 | 1 | 0 | 2 | 1 |

### unit/handlers

| File | Lines | In class | Module | Fixt. | Helpers | Cmt | Patch | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| test_api_keys.py | 99 | 0 | 5 | 0 | 0 | 0 | 5 | 1 |
| test_artifacts.py | 3832 | 0 | 74 | 0 | 6 | 15 | 287 | 11 |
| test_artifacts_batch_deletion.py | 550 | 12 | 0 | 1 | 1 | 0 | 0 | 0 |
| test_auth.py | 1260 | 0 | 57 | 3 | 0 | 0 | 107 | 6 |
| test_bucket_secrets.py | 1298 | 0 | 28 | 0 | 2 | 0 | 67 | 3 |
| test_collections.py | 1072 | 0 | 24 | 0 | 1 | 2 | 67 | 5 |
| test_deployments.py | 2352 | 0 | 53 | 0 | 3 | 0 | 124 | 7 |
| test_lineage.py | 1380 | 0 | 31 | 1 | 5 | 0 | 0 | 0 |
| test_monitoring.py | 650 | 0 | 20 | 0 | 3 | 6 | 46 | 3 |
| test_orbit_secrets.py | 552 | 0 | 15 | 0 | 1 | 0 | 28 | 3 |
| test_orbits.py | 1200 | 0 | 28 | 3 | 2 | 0 | 100 | 7 |
| test_organization_invites.py | 338 | 0 | 8 | 0 | 0 | 0 | 27 | 9 |
| test_organization_members.py | 382 | 0 | 9 | 0 | 0 | 0 | 30 | 4 |
| test_organizations.py | 441 | 0 | 14 | 0 | 0 | 0 | 29 | 3 |
| test_permissions.py | 413 | 0 | 15 | 0 | 1 | 0 | 30 | 3 |
| test_platform_admin.py | 98 | 0 | 4 | 0 | 0 | 1 | 4 | 1 |
| test_platform_admin_auth.py | 402 | 23 | 0 | 0 | 6 | 0 | 8 | 1 |
| test_satellite_parameters.py | 296 | 0 | 7 | 0 | 2 | 0 | 0 | 0 |
| test_satellites.py | 1941 | 0 | 49 | 0 | 0 | 0 | 103 | 6 |
| test_tracks.py | 2469 | 0 | 80 | 0 | 4 | 24 | 265 | 8 |

### unit/repositories and unit root

| File | Lines | In class | Module | Fixt. | Helpers | Cmt | Patch | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| repositories/test_artifacts.py | 84 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| repositories/test_base.py | 67 | 4 | 0 | 0 | 1 | 0 | 0 | 0 |
| repositories/test_lineage.py | 37 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| test_security.py | 129 | 0 | 3 | 1 | 2 | 0 | 5 | 2 |
| test_security_headers.py | 22 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

### integration

| File | Lines | In class | Module | Fixt. | Helpers | Cmt | Patch | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| repository/test_api_keys.py | 73 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| repository/test_artifacts.py | 1035 | 0 | 35 | 0 | 3 | 9 | 0 | 0 |
| repository/test_artifacts_batch_deletion.py | 463 | 8 | 0 | 0 | 2 | 0 | 0 | 0 |
| repository/test_bucket_secrets.py | 436 | 0 | 18 | 0 | 1 | 1 | 0 | 0 |
| repository/test_collections.py | 344 | 0 | 11 | 0 | 1 | 0 | 0 | 0 |
| repository/test_concurrency_guards.py | 897 | 22 | 0 | 0 | 8 | 0 | 0 | 0 |
| repository/test_deployments.py | 903 | 0 | 24 | 1 | 3 | 3 | 2 | 1 |
| repository/test_invites.py | 139 | 0 | 6 | 0 | 1 | 0 | 0 | 0 |
| repository/test_lineage.py | 766 | 0 | 14 | 0 | 3 | 9 | 0 | 0 |
| repository/test_monitoring.py | 52 | 0 | 3 | 0 | 0 | 2 | 0 | 0 |
| repository/test_orbit_secrets.py | 192 | 0 | 10 | 0 | 1 | 0 | 0 | 0 |
| repository/test_orbits.py | 412 | 0 | 17 | 0 | 1 | 0 | 0 | 0 |
| repository/test_organization_members.py | 110 | 0 | 5 | 0 | 0 | 0 | 0 | 0 |
| repository/test_organizations.py | 67 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| repository/test_platform_admin.py | 213 | 0 | 9 | 0 | 0 | 1 | 0 | 0 |
| repository/test_satellites.py | 344 | 0 | 12 | 0 | 0 | 0 | 0 | 0 |
| repository/test_token_blacklist.py | 50 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| repository/test_tracks.py | 1652 | 0 | 51 | 0 | 4 | 32 | 0 | 0 |
| repository/test_user.py | 218 | 0 | 8 | 1 | 0 | 0 | 0 | 0 |
| test_migrations_env.py | 37 | 2 | 0 | 0 | 1 | 0 | 0 | 0 |
| test_satellite_contract_migration.py | 109 | 0 | 2 | 0 | 3 | 0 | 0 | 0 |
