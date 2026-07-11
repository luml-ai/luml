# Proposals

## Problem

Luml satellites are agents that pair with the platform, advertise capabilities, and execute queued tasks (deploy, undeploy, and a growing set of newer task types) against a specific infrastructure backend. Today there is exactly one satellite implementation (`satellite/`), and everything — platform client, poll loop, task dispatch, task lifecycle bookkeeping, capability declaration, FastAPI proxy — is a single monolithic application. Building a second satellite (Kubernetes, SageMaker, Modal, …) means copying and hand-maintaining all of it.

A key lesson shapes this spec: extracting the satellite's low-level building blocks (platform client, dispatcher, poll controller, FastAPI app factory) into a passive library is not enough. That shape resembles a small web application, and it leaves all the meaningful responsibility to each satellite implementation — hand-wired runtime, hand-managed task status transitions, untyped `dict` payloads, a hand-maintained capabilities dict that can silently drift from the registered handlers, and a hard FastAPI dependency even for satellites that never proxy traffic. The SDK must own those responsibilities, not merely provide parts.

## Proposed solution

Build a satellite SDK (`luml_satellite_kit`) **from scratch, against the current satellite implementation as the baseline**, structured around **tasks as the central concept**. The SDK owns the runtime, the task lifecycle, and the task↔capability bookkeeping; a satellite implementation supplies only infrastructure-specific logic.

This follows from what a satellite *is*: satellites are differentiated by the backend infrastructure they run on (Docker, Kubernetes, SageMaker, Modal, …), not by which capability they serve — each satellite is expected to implement most if not all capabilities for its infrastructure. Accordingly, the existing satellite is renamed to **`docker-satellite`**: it is the Docker-infrastructure satellite, not the deployment-only satellite.

Target package layout:

- `core` — common interfaces, base settings, shared schemas, errors.
- `platform` — the platform HTTP client.
- `tasks` — the task framework: a generic base handler that owns the full execution flow (claim → validate typed payload → execute → report result/failure), plus per-task-type bases (`deploy`, `undeploy`, and bases for the newer task types) that encode each task type's platform-generic lifecycle and leave only infrastructure-specific methods abstract.
- `web` — everything FastAPI-related. **Optional**: a satellite that doesn't proxy inference traffic (e.g. a Kubernetes satellite where traffic goes directly to pods) never imports it and doesn't need FastAPI installed.

Key behavioral changes:

- **Template-method task handlers**: the framework owns status transitions, payload validation into per-task-type Pydantic models, and error capture/reporting; a satellite implements a small set of abstract methods per task type.
- **Registration-driven capabilities**: handlers are registered with the controller, which derives the advertised capability map from the registrations — eliminating manual capability dicts and their drift risk.
- **SDK-owned runtime**: a single entry point runs the whole satellite — platform client session, pairing, poll loop, optional web server, graceful shutdown.
- **Complete migration**: the renamed `docker-satellite` moves onto the SDK as the reference implementation, and **every task type present in the current implementation migrates** — including task types added after this spec was written, which are discovered from the code at implementation time and migrated by the same recipe.

## Why this approach

- Keeping the satellite monolithic (or extracting only passive building blocks) leaves every new satellite re-implementing the error-prone parts: status transitions, payload parsing, capability sync. LM-220's goal — making new satellites cheap and safe to build — only happens if the SDK owns those invariants.
- Deriving capabilities from registered handlers makes the "advertises X but can't do X" class of bugs unrepresentable instead of merely discouraged.
- Building from the current implementation means the newest task types shape the abstractions, instead of being force-fitted afterward into abstractions designed around deploy/undeploy only.

# Design

## Constraints

- **Baseline is the current satellite implementation** — the up-to-date satellite code at the time implementation starts, not `main` as of this writing. The first implementation step inventories it (see "Task inventory"). Any earlier partial extraction present on the working branch is replaced by the new SDK, not built upon.
- **The satellite ↔ backend contract does not change.** Endpoints, task statuses (`pending/running/done/failed`), and the pairing payload (`base_url`, `slug`, `capabilities: dict[capability-name, spec-dict | None]`) stay exactly as the backend expects them (`backend/luml/schemas/satellite.py`). The migrated satellite must advertise the same capability map and produce the same status/result sequences the current implementation produces. One trivial backend exception: `satellite_parameters` typing is widened to admit booleans (see "Deployment parameter form spec"); no other backend changes.
- Task **types** are open strings in the SDK (the backend enum remains the platform-side source of truth for what gets scheduled). The kit ships string constants for the known types but never restricts to them, so a new task type never requires a kit release.
- The satellite implementation directory (`satellite/` on the baseline; possibly already renamed on the working branch) becomes `docker-satellite/` (directory, package references, CI workflow, Docker/compose files). Future satellites follow the same infra-named convention (`kubernetes-satellite`, `sagemaker-satellite`, …).
- The satellite's `model_server` is in scope only where its interaction with the agent forces a change; it is not being restructured for its own sake.
- **One running instance per satellite identity.** Task pickup is poll-then-mark-running, not a distributed claim; two replicas sharing a satellite token would double-execute tasks. The kit assumes and documents single-instance operation; multi-replica/HA satellites are explicitly out of scope and would require platform-side claim semantics first.

## Task inventory

Because the satellite has grown task types this spec does not enumerate, the migration is driven by an inventory taken from the baseline code, not by a fixed list:

- Enumerate every task type the current implementation dispatches (its task-registry/dispatch wiring and the backend's `SatelliteTaskType` enum are the two sources; they must agree).
- Enumerate the capabilities the current implementation advertises at pairing, and which task types serve each capability.
- For each task type, identify the split between platform-generic logic (platform calls, status/result bookkeeping — moves into an SDK per-task-type base) and Docker-specific logic (stays in `docker-satellite` as the concrete handler).

The completeness criterion for the whole effort: after migration, every inventoried task type has a registered handler, and the derived capability map equals the currently advertised one. Deploy and undeploy are specified fully below as the worked examples; additional task types follow the same pattern ("Migration recipe").

## Package layout (`luml_satellite_kit`)

A new package under `satellite-kit/`:

- **`core`** — base satellite settings, shared schemas (task envelope, deployment models, error message), SDK exception types. No FastAPI imports anywhere in `core`.
- **`platform`** — `PlatformClient`, built from the current satellite's platform client, exposing the complete set of platform endpoints the baseline uses (including any added for newer task types).
- **`tasks`** — the task framework:
  - the generic task-handler base (lifecycle + typed payloads + capability declaration),
  - the controller (handler registration, capability derivation, poll loop, dispatch),
  - per-task-type base handlers: `tasks/deploy`, `tasks/undeploy`, plus one module per inventoried task type whose logic is meaningfully platform-generic. A task type that is entirely satellite-specific may subclass the generic base directly instead of getting an SDK base — decide per type during inventory.
- **`web`** — everything FastAPI-related: the app factory, the inference-proxy router helpers (bearer-token verification against `authorize_inference_access`), and OpenAPI schema merging support (generalized from the current agent's API module so any proxy satellite gets the same auth-decorated, deployment-merged OpenAPI behavior without rewriting it).
- **`testing`** — the satellite-author testing toolkit: a fake platform client that records every interaction (status transitions, deployment updates, pairing payload) for assertions, plus task-envelope factories. Ships in the package (importable without the `web` extra) so every satellite — current and future — writes its handler tests against the same harness instead of inventing mocks. The kit's own tests and docker-satellite's parity tests are its first consumers.
- **`mock`** — a mock satellite shipped with the kit: in-memory handlers for the known task types (deploy stores state in a dict, nothing real is provisioned), declaring realistic capabilities, runnable as a module against a real or local platform. Deliberately non-functional as infrastructure; it exists (a) as the SDK's own end-to-end exercise and second consumer, keeping the abstractions from bending Docker-shaped, (b) as a copy-paste starting point for new satellites, and (c) as a disposable satellite for testing the platform side (pairing, task queueing) without real infra.
- **Runtime entry point** — a single `Satellite` runtime object: constructed with settings, registered handlers, optional web integration, and optional startup/shutdown hooks; its run method owns the platform-client session, pairing, the poll loop, the web server (when configured), and graceful shutdown. A satellite's `main.py` reduces to: build dependencies, instantiate handlers, register, run.

This is a new pre-release package (0.1.0, single consumer); no compatibility with any earlier kit API is owed.

## Web layer optionality

FastAPI lives behind a pip extra (`luml-satellite-kit[web]`). A non-proxy satellite installs the bare kit and never imports `web`; importing `luml_satellite_kit.web` without the extra installed fails with a clear error naming the extra. When a web integration is passed to the runtime, the runtime starts and stops the HTTP server itself alongside the poll loop; when it isn't, no web components exist in the process.

## Task handler contract

A handler is defined by: a task type (string), a payload model (Pydantic), an optional capability declaration, and an execute method. The framework — not the implementer — owns the lifecycle:

1. Mark the task `running` on the platform.
2. Validate `task.payload` into the handler's payload model. On validation failure, report the task `failed` with a structured reason; the implementer's code never runs.
3. Call the handler's execute logic with the validated, typed payload.
4. On normal return, report `done` with the (optional) result the handler produced. On exception, report `failed` with an `ErrorMessage`, then invoke the handler's failure hook so task-specific side effects (e.g. marking a deployment `failed`) happen in one place.

Implementers signal rich failures by raising a dedicated SDK exception carrying reason/error detail; any other exception is wrapped. Status reporting must be best-effort resilient (a status-update failure is logged, never crashes the poll loop).

### Per-task-type base handlers

The SDK encodes what is platform-generic about each task type, leaving only infrastructure-specific steps abstract. Worked examples:

- **Deploy base handler**: owns fetching the `Deployment` and the model-artifact download URL from the platform, resolving `env_variables_secrets` into concrete values, and the final bookkeeping (update deployment with `inference_url` + `schemas` + `active`, task `done` with the inference URL; on any failure, deployment `failed` with the error). Abstract: provision the workload and wait until it is ready (given deployment, artifact URL, resolved env), and produce the inference URL and optional schemas for a ready workload. It declares the `deploy` capability; the concrete satellite supplies the capability spec values (version, supported variants, etc.) since those describe the satellite, not the SDK.
- **Undeploy base handler**: owns the final bookkeeping (platform-side deployment deletion, task `done`; on failure, deployment `deletion_failed` with the error). Abstract: tear down the workload for a deployment id. Declares no capability of its own — undeploy is part of the `deploy` capability's contract.

Bases for the newer inventoried task types follow the same shape: platform calls and status/result bookkeeping in the base, infrastructure actions abstract, capability declaration mirroring what the current implementation advertises for that type.

Abstract provisioning operations are expected to be **convergent**: re-running deploy for a deployment whose workload already exists adopts or replaces it rather than failing (the current Docker implementation's create-or-replace behavior is the model). The platform has no task redelivery today, so this is not about duplicate delivery — it keeps retry-after-crash and manual re-runs safe on any backend. Recovery of tasks left `running` by a dead process remains satellite policy, implementable via startup hooks and the platform client's status-filtered task listing.

## Migration recipe (per task type)

Each inventoried task type migrates the same way, so task types unknown to this spec need no spec change:

1. Define its payload model from the fields the current implementation reads out of `task.payload` (required vs optional determined by how the current code treats absence).
2. Split the current handler: platform-generic flow into an SDK base (or directly onto the generic base if nothing generalizes), Docker-specific actions into the concrete `docker-satellite` handler.
3. Preserve the observable platform interaction: same status transitions, same result payloads, same error-message structure as the current implementation for both success and failure paths.
4. Carry over the capability contribution (if any) as the handler's declaration, keeping the derived pairing payload identical.
5. Port or add handler-level tests covering the type's success and failure paths against a mocked platform.

## Capability derivation

Each handler may declare at most one capability: a name plus a spec. At registration time the controller assembles the advertised capability map as the union of declared capabilities; two handlers declaring the same capability name is a startup error (fail fast, before pairing). Handlers with no capability declaration contribute nothing to the map but still receive tasks. The derived map must be identical to what the current implementation sends at pairing.

Unlike task types, capability names are not open-ended in practice: the backend validates pairing capability keys against its own `SatelliteCapability` enum (only `deploy` today), so a satellite advertising a new capability requires a coordinated backend change. The kit still treats the name as a string — it must not need a release when the backend enum grows.

### Typed capability specs

The kit distributes typed models for the known capability specs (e.g. a deploy-capability spec with version, supported variants, tags combinations, extra-fields form spec — fields taken from what the current implementation sends), so all satellites share one vocabulary instead of hand-writing dicts that drift apart. These models are a satellite-side convenience only: they serialize to exactly the dict the backend expects today, and the wire contract remains the dict. Evolution must be backward-compatible — additive, optional-with-default fields only, so a satellite on an older kit still produces a valid spec; a capability whose shape isn't modeled yet can be declared as a raw dict.

### Deployment parameter form spec

The deploy capability's `extra_fields_form_spec` is not a static field list but a reactive form DSL: fields with types, dropdown values, validators (min/max/regex/in/…), and visibility conditions that reference other fields' current values and the model's tags/variant/version. The frontend interprets it in `frontend/src/hooks/satellites/useSatelliteFields.ts` against the shapes in `frontend/src/lib/api/satellites/interfaces.ts`. Satellite parameters are exactly where heterogeneous backends differ (instance types, GPU counts, replicas, regions), so the kit treats this DSL as first-class:

- **Typed DSL models (1a).** The kit ships typed models for the full form-spec DSL — fields, validators, condition objects — mirroring the frontend's shapes, so satellites author their forms in type-checked code instead of raw dicts. Serialization to the pairing payload is unchanged.
- **Satellite-side enforcement (1b).** Because the kit understands the DSL, the deploy base validates incoming `satellite_parameters` against the satellite's declared form spec before the handler runs: validators are enforced, and visibility conditions are evaluated with the deployment's model context (tags/variant/version), mirroring the frontend's evaluation. A violation fails the task with a structured reason naming the field — same path as payload validation, so a stale frontend or a direct API call cannot smuggle in values the advertised form would reject. Values for fields whose conditions make them inapplicable are ignored, not rejected (tolerant reader); a missing required-and-applicable field is a validation failure. Handlers receive parameters as validated, typed values.

**Lockstep constraint:** the DSL models and the validator/condition evaluator must carry explicit code comments stating that they are mirrored by the frontend implementation (`interfaces.ts`, `useSatelliteFields.ts`) and that any change must be made in both places in lockstep. Evolution is additive, like all wire models.

**Boolean parameters fix:** the DSL has a `boolean` field type, but the backend types `satellite_parameters` as `dict[str, int | str]` (`backend/luml/schemas/deployment.py`), so a boolean form value cannot round-trip as a `bool`. Widen the backend typing to admit `bool` (all `satellite_parameters` fields in the deployment schemas) and use the widened typing in the kit's deployment model. Purely a type widening — no endpoint, storage, or frontend behavior changes.

## Wire-model evolution

Once multiple satellites run on different kit versions, the platform will grow its wire payloads. All kit wire models — task envelope, task payloads, deployment, capability specs — are **tolerant readers**: unknown fields are ignored, never validation errors, so a satellite on an older kit keeps working when the platform adds fields. Evolution of the models themselves is additive (new fields optional with defaults). Removing or re-typing a field is a breaking change requiring a coordinated platform/kit decision, not something a kit release does unilaterally.

## Controller and runtime behavior

- Registration: handlers are registered with the controller; registering two handlers for the same task type is a startup error.
- Poll loop: same semantics as the current implementation's periodic controller — poll pending tasks at the configured interval, dispatch each, report `failed` (with reason) for tasks whose type has no registered handler or whose envelope doesn't validate, survive per-tick errors.
- Dispatch mode: the kit provides the mechanism, the satellite owns the guarantees. Sequential mode is the default and matches today's behavior (one task at a time). A satellite may opt into parallel mode with a concurrency bound, so one long-running task (e.g. a deploy waiting on health checks) doesn't block the queue. The kit makes no ordering or mutual-exclusion promises in parallel mode — enabling it is the satellite asserting its handlers tolerate concurrent execution; any resource-level serialization (e.g. never deploy and undeploy the same deployment concurrently) is the satellite's responsibility. docker-satellite stays sequential in this migration.
- Crash recovery is likewise satellite-level policy: the kit guarantees startup hooks run (with the platform client) before polling begins, which is where a satellite reconciles orphaned in-flight state; the kit itself makes no claims about tasks left `running` by a previous process.
- Runtime start sequence: open platform client → run satellite-provided startup hooks (e.g. the Docker satellite's deployment reconciliation) → start managed background workers and the web server if configured → pair (with derived capabilities) → poll forever. Shutdown stops the loop, the workers, and the web server gracefully.
- Managed background workers: satellites register long-running or periodic workers (the current satellite's monitoring worker is the model — today it is hand-supervised in `main.py` with manual `create_task`/`cancel`/`finally` plumbing) and the runtime owns their supervision: started after the platform client is available, exceptions surfaced in logs rather than silently swallowed, cancelled cleanly on shutdown. A worker crash never takes down task polling. The worker's logic is entirely satellite-specific; the kit owns only the lifecycle.
- Settings: a `BaseSatelliteSettings` in `core` (token, platform URL, base URL, poll interval); the satellite slug is explicit satellite-provided configuration, not a hardcoded constant.

## docker-satellite migration

`satellite/` is renamed to `docker-satellite/` and its agent is rewritten on the SDK as the reference implementation:

- Every inventoried task type becomes a concrete handler implementing only Docker-specific steps; all hand-rolled status/error bookkeeping moves into the SDK bases per the migration recipe.
- `main.py` shrinks to construction + registration + run; the hand-maintained capabilities dict is replaced by handler capability declarations producing the same pairing payload.
- The generic parts of the agent's API module (bearer auth, security-decorated OpenAPI merging) move into `luml_satellite_kit.web`; deploy-specific routes and the model-server/OpenAPI handlers stay in the agent, built on those helpers.
- Satellite-internal subsystems that are not task handlers keep their roles: one-shot reconciliation (deployment sync) becomes a startup hook; long-running loops (the monitoring worker) become runtime-managed workers; all use the runtime-provided platform client instead of module-level singletons and self-constructed clients.
- Observable behavior toward the backend and toward inference clients is unchanged.

## Testing

Add `satellite-kit/tests/` covering the lifecycle, capability derivation, controller dispatch (both modes), runtime sequencing, web optionality, and the mock satellite end-to-end against the `testing` fake platform. `docker-satellite` keeps its behavior verified with handler-level tests built on the `testing` toolkit plus fake Docker/model-server clients — one success + failure pair per inventoried task type. Both suites run under per-package CI workflows.

# Scenarios

## Scenario: task lifecycle happy path
**Given** a registered handler whose payload model matches a pending task's payload
**When** the controller dispatches the task
**Then** the platform sees the task `running` before handler logic executes, and `done` with the handler's result after it returns.

## Scenario: payload validation failure
**Given** a pending task whose payload is missing a field required by the handler's payload model
**When** the controller dispatches the task
**Then** the task is reported `failed` with a structured reason naming the validation problem, and the handler's execute logic is never invoked.

## Scenario: handler failure reporting
**Given** a handler whose execute logic raises an SDK task error with reason and detail
**When** the task runs
**Then** the task is reported `failed` carrying that reason/detail, and the handler's failure hook runs (for the deploy base: the deployment is marked `failed` with the same error).

## Scenario: unknown task type
**Given** a pending task whose type has no registered handler
**When** the controller polls
**Then** the task is reported `failed` with an unknown-type reason and the poll loop continues with the next task.

## Scenario: capabilities derived from registration
**Given** the migrated docker-satellite with all its handlers registered
**When** the runtime pairs with the platform
**Then** the pairing payload's capability map is identical to the one the pre-migration satellite sends.

## Scenario: conflicting registrations fail fast
**Given** two handlers declaring the same capability name, or two handlers for the same task type
**When** they are registered
**Then** startup fails with a clear error before any pairing or polling happens.

## Scenario: non-web satellite
**Given** a satellite built on the bare kit (no `web` extra installed) that registers handlers and runs
**When** the runtime starts
**Then** it pairs and processes tasks with no HTTP server in the process, and nothing in the used code paths imports FastAPI.

## Scenario: web import without extra
**Given** an environment with the bare kit installed
**When** code imports `luml_satellite_kit.web`
**Then** the import fails with an error message naming the `web` extra to install.

## Scenario: runtime-owned web server
**Given** a satellite passing a web integration to the runtime
**When** the runtime starts and later shuts down
**Then** the HTTP server starts before pairing, serves `/healthz`, and stops gracefully with the runtime.

## Scenario: parallel dispatch mode
**Given** a controller in parallel mode with a concurrency bound and one handler that blocks for a long time
**When** a slow task and a fast task are both pending
**Then** the fast task completes without waiting for the slow one; in sequential mode (the default) the same setup processes them one at a time.

## Scenario: handler tests via the testing toolkit
**Given** a satellite author writing tests for a concrete handler using the kit's fake platform client and task factories
**When** the handler runs a success case and a failure case
**Then** the fake platform's recorded interactions let the test assert the exact status transitions and payloads without any hand-written mocks.

## Scenario: mock satellite end-to-end
**Given** the kit-shipped mock satellite started against a (fake or local) platform
**When** it pairs and receives a deploy task
**Then** it advertises its declared capabilities, executes the task in memory, and reports the same status sequence a real satellite would — provisioning nothing.

## Scenario: typed capability spec compatibility
**Given** the deploy capability spec built via the kit's typed models (including a form spec with validators and conditions) with the values the current satellite advertises
**When** it is serialized into the pairing payload
**Then** the resulting dict is identical to the one the current implementation sends.

## Scenario: satellite parameters validated against the form spec
**Given** a deploy handler whose form spec declares a numeric field with a max validator, and a deployment whose `satellite_parameters` exceed it
**When** the deploy task runs
**Then** the task fails with a structured reason naming the field, and the handler's provisioning logic never runs.

## Scenario: boolean satellite parameter round-trip
**Given** a form spec declaring a boolean field and a deployment created with that field set to a boolean value
**When** the deployment reaches the deploy handler
**Then** the parameter arrives as a `bool` and validates against the boolean field type.

## Scenario: conditionally inapplicable parameters ignored
**Given** a form spec where field B is only applicable when field A has a given value, and a deployment where A has a different value
**When** the deploy task runs
**Then** any value for B is ignored rather than rejected, and a missing B is not treated as a validation failure — while a missing required-and-applicable field still fails the task.

## Scenario: tolerant payload reading
**Given** a pending task whose payload contains all required fields plus fields unknown to the handler's payload model
**When** the controller dispatches the task
**Then** validation succeeds, the unknown fields are ignored, and the handler runs normally.

## Scenario: full task-type coverage
**Given** the set of task types dispatched by the pre-migration satellite (per the inventory)
**When** the migrated docker-satellite starts
**Then** every one of those task types has a registered handler — none falls into the unknown-type path.

## Scenario: docker-satellite parity — deploy
**Given** the migrated docker-satellite agent and a pending deploy task (against fake Docker/model-server/platform)
**When** the task runs to success
**Then** the platform receives the same sequence as before the migration: task `running`; deployment updated with proxy inference URL, schemas, and `active`; task `done` with the inference URL.

## Scenario: docker-satellite parity — failed container
**Given** a deploy task whose container creation fails (e.g. missing image)
**When** the task runs
**Then** the task is `failed` and the deployment is marked `failed` with an error message identifying the image problem, as before the migration.

## Scenario: docker-satellite parity — undeploy failure
**Given** an undeploy task where container removal raises
**When** the task runs
**Then** the task is `failed` and the deployment is marked `deletion_failed`, as before the migration.

## Scenario: parity for newer task types
**Given** any inventoried task type beyond deploy/undeploy, with a representative pending task
**When** the task runs to success and, separately, is made to fail
**Then** the platform receives the same status transitions, result payloads, and error-message structure the pre-migration implementation produces for that type.

## Scenario: startup reconciliation hook
**Given** docker-satellite's deployment-sync logic registered as a runtime startup hook
**When** the runtime starts
**Then** it runs using the runtime's platform client before task polling begins.

## Scenario: managed background worker
**Given** a periodic worker registered with the runtime
**When** the runtime runs and later shuts down
**Then** the worker starts after the platform client is available, an exception inside it is logged without stopping task polling, and shutdown cancels it cleanly.

## Scenario: convergent re-deploy
**Given** a deploy task for a deployment whose workload already exists (e.g. left over from a crashed run)
**When** the task executes
**Then** provisioning adopts or replaces the existing workload and the task completes `done` — no failure due to the pre-existing workload.

# Tasks

- [ ] Inventory the satellite baseline and record the migration map
  - [ ] Enumerate all dispatched task types, their payload fields, status/result sequences, and error shapes from the current satellite code and the backend enum
  - [ ] Enumerate advertised capabilities and which task types serve each
  - [ ] Enumerate startup/background workers and their platform-client usage
  - [ ] Record the inventory as a checklist appendix in this SPEC.md (the completeness criterion for the migration tasks below)
- [ ] Create the satellite-kit package with core, platform, and web layers
  - [ ] Scaffold `satellite-kit/` (replacing any earlier extraction remnants on the branch) with `core` (settings, shared schemas, exceptions), `platform` (client covering every endpoint the baseline uses), and `web` behind a pip extra with an import guard
  - [ ] Task types as open strings with constants for the inventoried types
  - [ ] Set up `satellite-kit/tests/` and a CI workflow; cover schemas, settings, platform client, and the web-extra guard
- [ ] Add task handler framework with lifecycle and capability derivation
  - [ ] Implement the `testing` toolkit: fake platform client recording all interactions, task-envelope factories
  - [ ] Implement the generic task-handler base: typed payload validation, running/done/failed reporting, failure hook, SDK task error
  - [ ] Implement the controller: handler registration, duplicate task-type/capability startup errors, capability map derivation, poll-and-dispatch loop with sequential (default) and bounded-parallel dispatch modes
  - [ ] Tests for lifecycle happy path, validation failure, handler failure, unknown type, capability derivation, registration conflicts, and both dispatch modes
- [ ] Add satellite runtime entry point
  - [ ] Implement the `Satellite` runtime: platform client session, startup/shutdown hooks, managed background workers, optional web server ownership, pairing with derived capabilities, poll loop, graceful shutdown
  - [ ] Tests for start sequence ordering, non-web operation, web server start/stop, hook execution, and worker supervision (clean cancellation, crash isolation)
- [ ] Allow boolean satellite parameters in the backend
  - [ ] Widen `satellite_parameters` typing to include `bool` across the deployment schemas in `backend/luml/schemas/deployment.py`
  - [ ] Regression test covering a deployment created with a boolean satellite parameter
- [ ] Add per-task-type base handlers
  - [ ] Deploy base: artifact/deployment fetching, secret resolution, deployment status bookkeeping, satellite-parameters validation against the declared form spec, `deploy` capability declaration with satellite-supplied spec; abstract workload provisioning/readiness
  - [ ] Undeploy base: platform deployment deletion and `deletion_failed` bookkeeping; abstract workload teardown
  - [ ] Bases (or generic-base guidance) for each additional inventoried task type, per the migration recipe
  - [ ] Typed payload models for all inventoried task types and typed capability spec models serializing to the exact current pairing dicts
  - [ ] Form-spec DSL typed models and the validator/condition evaluator, with lockstep-mirror comments referencing `interfaces.ts` and `useSatelliteFields.ts`
  - [ ] Tests covering each base's success and failure bookkeeping, capability-spec/form-spec serialization, and parameter validation (validators, conditional applicability), built on the testing toolkit
- [ ] Add the mock satellite
  - [ ] Implement `mock`: in-memory handlers built on the per-task-type bases, realistic typed capability declarations, runnable as a module
  - [ ] Mock-satellite end-to-end test against the fake platform: pair → deploy task → status sequence → undeploy
- [ ] Rename satellite to docker-satellite
  - [ ] Rename the directory and update package/project references (`pyproject.toml`, Dockerfiles, `docker-compose.yml`)
  - [ ] Rename/adjust the satellite CI workflow and its path filters
  - [ ] Sweep remaining references — external contracts (pairing slug, API paths) unchanged
- [ ] Migrate docker-satellite onto the kit
  - [ ] Rewrite each inventoried task type as a concrete handler implementing only Docker-specific steps
  - [ ] Move generic auth/OpenAPI pieces of the agent API into `luml_satellite_kit.web`; keep satellite-specific routes in the agent
  - [ ] Replace the hand-maintained capabilities dict and hand-wired `main.py` with handler registration and the runtime; make the slug explicit configuration; remove module-level singletons
  - [ ] Wire background workers/reconciliation through runtime hooks
  - [ ] Port handler-level tests onto the testing toolkit
  - [ ] Verify against the inventory appendix: full task-type coverage, identical pairing payload, parity tests per task type passing
