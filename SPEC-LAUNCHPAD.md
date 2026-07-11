# Proposals

## Problem

Satellites are orbit-level workers and every one of them is hand-operated: a user creates the record, copies the one-time API key, provisions a host, runs the daemon, and repeats this for every orbit and every infrastructure backend. There is no organization-level concept that can provision, update, or decommission satellites. Worse, for API-based platforms (Modal, SageMaker, and similar) a daemon is pure overhead — the platform is already an API that LUML could call directly, yet today the only way to serve tasks is to run a poll-mode process somewhere.

## Proposed solution

Introduce the **Launchpad**: an organization-level entity that manages satellites. A launchpad can create a satellite, update it, rotate its credentials, and decommission it; satellites created this way stay linked to (and owned by) their launchpad.

Launchpads come in two modes:

- **poll** — a daemon (built on a new, separate `luml-launchpad-kit` SDK) pairs with LUML and polls a launchpad task queue, mirroring the proven satellite pattern. It executes management tasks against infrastructure it can reach (e.g. provisioning docker-satellite containers on hosts it controls).
- **direct** — a plugin running inside the LUML backend. LUML calls the platform's APIs itself; no daemon anywhere. Direct plugins are pip-installable packages discovered via Python entry points, so new platforms are cheap to author without touching the backend repo.

A direct launchpad is not the same thing as a virtual satellite: a direct plugin can provision **real satellites** (poll-mode daemons running on the platform) and/or back **virtual satellites** — satellite records with no daemon whose task queue (deploy, undeploy, …) the backend executes by calling the plugin.

Every launchpad declares **satellite templates**: the kinds of satellites it can provision, each with a config form described in the same reactive form-spec DSL satellites already use for deployment parameters. The UI renders create-satellite flows entirely from these declarations.

## Why this approach

- The satellite queue/pairing/last-seen machinery is proven; poll launchpads reuse the pattern (not the code) rather than inventing a second protocol style.
- Entry-point plugins keep the backend closed for modification but open for new platforms — the same property the satellite-kit gives daemon authors.
- Virtual satellites remove the daemon-ops burden exactly where it adds nothing (API-based platforms) while leaving the satellite abstraction — capabilities, task queue, deployments — untouched, so the rest of LUML (and the existing frontend deploy flow) works unchanged.
- Templates-as-data means the frontend never needs per-platform UI code, the same bet already made with `extra_fields_form_spec`.

# Design

## Constraints

- The existing satellite↔backend worker contract (pairing payload, `/satellites/v1/*` endpoints, task statuses `pending/running/done/failed`) is not changed. Unmanaged satellites keep working exactly as before; management via launchpad is purely additive.
- The backend is FastAPI + SQLAlchemy + alembic with **no background-worker infrastructure**. The executor for direct-mode work is specified as a contract only (see "Executor contract"); the mechanism (in-process loop, separate worker process, …) is the implementer's choice.
- The reactive form-spec DSL (fields, validators, conditions — `frontend/src/lib/api/satellites/interfaces.ts`, evaluated by `frontend/src/hooks/satellites/useSatelliteFields.ts`) is reused for launchpad/template config forms. Any typed models of it must carry the same lockstep-mirror comments as in the satellite-kit spec: changes must be mirrored in the FE.
- `luml-launchpad-kit` is a **separate SDK** from `luml-satellite-kit`. It should mirror the satellite-kit's architecture (template-method task handlers, registration-driven declarations, runtime entry point) for conceptual consistency, but there is no code-sharing requirement.
- This spec is independent of SPEC.md (the satellite-kit spec); neither blocks the other. Where both touch the form-spec DSL, the same FE files are the source of truth.

## Data model

- **`launchpads`** (new table, org-scoped): id, `organization_id` FK, name, description, `mode` (`poll` | `direct`), `slug` (reported at pairing, like satellites), `templates` (JSONB — declared satellite templates, empty until paired/registered), timestamps.
  - poll-only: `api_key_hash` (unique), `paired`, `last_seen_at`. Status computed from `last_seen_at` exactly like satellite status.
  - direct-only: `plugin_name` (must match an installed plugin at creation time), `config` (JSONB validated against the plugin's declared config form; fields the plugin marks as secret are encrypted at rest via `luml.infra.encryption` and never returned by read APIs). Status reflects plugin health (a plugin-provided health check; default: active while the plugin is installed).
- **`launchpad_queue`** (new table): mirrors `satellite_queue` — id, `launchpad_id` FK, `organization_id`, `type` (open string set; initial vocabulary: `pairing`, `create_satellite`, `update_satellite`, `delete_satellite`), payload, status (`pending/running/done/failed`), scheduled/started/finished timestamps, result.
- **`satellites`** gains: `launchpad_id` (nullable FK; null = unmanaged), `kind` (`daemon` | `virtual`; existing rows are `daemon`), and `api_key_hash` becomes nullable (virtual satellites never authenticate). The pairing/capabilities check constraint must admit virtual satellites, whose `paired` + `capabilities` are set by the plugin at creation.
- **`organizations`** gains `launchpads_limit`, following the existing `satellites_limit` pattern.

## Ownership semantics (managed = owned)

- A satellite with a `launchpad_id` is **managed**. Direct user mutations (update, delete, key regeneration) through the existing orbit-satellite endpoints are rejected with a clear error directing the user to the launchpad; reads are unaffected.
- All lifecycle operations on a managed satellite go through its launchpad (which enqueues launchpad tasks in poll mode or invokes the plugin in direct mode).
- A **daemon** satellite can be explicitly **released** (org-admin action): the link is cleared, it becomes an ordinary unmanaged satellite and keeps working.
- A **virtual** satellite cannot be released — without its launchpad nothing executes its queue. It can only be deleted (via the launchpad).
- Deleting a launchpad is rejected while it still has managed satellites; the user must first delete (or, for daemon satellites, release) them. No forced teardown.

## Satellite templates

A template declares one kind of satellite a launchpad can provision: name, human description, satellite `kind` (`daemon` | `virtual`), a config form in the form-spec DSL, and — for virtual templates — the capabilities the resulting satellite will carry (same shape as a pairing payload's capabilities). Poll launchpads report their templates at pairing; direct plugins declare them in code and the backend snapshots them onto the launchpad record at creation (refreshed on backend restart / plugin upgrade).

Creating a satellite through a launchpad means: pick a target orbit (launchpads are org-level; satellites remain orbit-scoped), pick a template, fill the template's config form. The backend validates the config against the form spec, creates the managed satellite record, and:

- **daemon template**: the record starts unpaired; a `create_satellite` launchpad task is enqueued (payload: satellite id, orbit, template name, config). The satellite pairs itself once provisioned, as any satellite does.
- **virtual template**: the plugin's provisioning hook runs; on success the record is immediately `paired` with the template's declared capabilities.

The user-facing create response contains the satellite and, for daemon templates, the launchpad task — never an API key (keys are issued to the launchpad, not the user; virtual satellites have none).

## Poll mode

- **Pairing**: creating a poll launchpad returns a one-time launchpad API key and enqueues a `pairing` task, mirroring satellite creation. The daemon calls a pair endpoint reporting slug and templates.
- **Worker API** (`/launchpads/v1/*`, authenticated by launchpad API key, each call touching `last_seen_at`): pair, list tasks (filterable by status), update task status, plus satellite-management endpoints scoped to the launchpad's managed satellites:
  - register/issue-key: returns a fresh satellite API key for a specific managed satellite so the daemon can inject it into the runtime it provisions — **keys never transit task payloads**;
  - update and delete the managed satellite record (e.g. after decommissioning the runtime).
- **Task flow example (create)**: daemon polls the `create_satellite` task → marks running → provisions the runtime for the template → requests the satellite key via the worker API → injects it → reports done. The satellite subsequently pairs itself over the ordinary satellite contract.
- **`luml-launchpad-kit`**: a separate SDK for authoring poll daemons. Contract mirrors the satellite-kit: per-task-type base handlers owning the lifecycle (mark running → validate typed payload → execute abstract infra-specific methods → report done/failed with a failure hook), handler registration deriving the template declarations, a launchpad platform client covering the worker API, a runtime entry point (client session → pair → poll loop → graceful shutdown), and a shipped **mock launchpad** (in-memory handlers, runnable as a module) for testing and demos.

## Direct mode (plugin framework)

- **Discovery**: plugins are pip-installable packages registering under the entry-point group **`luml.launchpads`**. The backend discovers installed plugins at startup; an org-facing endpoint lists installed plugins with their config form specs and templates so the frontend can render creation flows. Creating a direct launchpad with an unknown `plugin_name` fails; a launchpad whose plugin disappears (uninstalled) surfaces as errored, and its tasks fail rather than hang.
- **Plugin interface** (contract, not signatures): a plugin declares its name and version, a launchpad-level config form (form-spec DSL; fields markable as secret), its satellite templates, and async hooks the backend invokes:
  - launchpad task hooks: create/update/delete satellite (provision, reconfigure, tear down platform resources);
  - virtual-satellite task hooks: handlers for satellite task types (`deploy`, `undeploy`, and future types) executed against the platform's APIs — the plugin receives the decrypted launchpad config, the satellite record, and the task, and is responsible for the same status/deployment bookkeeping contract a real satellite honors (task status transitions, deployment status updates, error messages);
  - an optional health check.
- Hooks receive a client/context giving access to the same platform operations a satellite has (deployment reads/updates, artifact download URLs, orbit secrets) without going over HTTP.
- **Credential handling**: secret config fields are encrypted at rest, excluded from all read responses, and passed decrypted only to plugin hooks at execution time.

## Executor contract

Direct-mode work (launchpad tasks of direct launchpads, and the task queues of virtual satellites) executes asynchronously backend-side. The mechanism is left to the implementer, but the contract is fixed:

- Tasks transition `pending → running → done/failed` with the same semantics as satellite-executed tasks; enqueueing never blocks the API request on execution.
- Tasks may run for tens of minutes (deploys with health checks); execution must survive being decoupled from the request lifecycle.
- At-least-once delivery is acceptable; plugin hooks must therefore be convergent (re-running a create/deploy adopts or replaces existing platform resources), matching the convergent-provisioning stance of the satellite-kit spec.
- A task found `running` past a generous staleness bound (e.g. after a backend restart) may be retried or failed, but never silently dropped.
- Virtual satellites' `last_seen_at` is touched by the executor when it processes their work; their displayed status derives from their launchpad's status, not from polling recency.

## API surface

- **Org-level user API** (follows the existing org-resource auth/permission patterns, e.g. bucket secrets): launchpad CRUD under the organization prefix (create enforcing `launchpads_limit`; delete enforcing the no-managed-satellites rule), launchpad task listing, poll-launchpad API-key regeneration, list installed direct plugins, list a launchpad's managed satellites, create-satellite-via-launchpad, release a daemon satellite.
- **Worker API**: `/launchpads/v1/*` as described under Poll mode, guarded by a new `launchpad` authentication scheme parallel to the existing `satellite` scheme.
- **Existing satellite endpoints**: gain the managed-satellite mutation guard; response schemas gain `launchpad_id` and `kind` (additive, tolerant-reader safe).

## Frontend

An organization-level Launchpads section:

- list + create (mode choice; for direct: plugin picker fed by the installed-plugins endpoint, config form rendered from the plugin's form spec with secret fields write-only; for poll: one-time API key display, mirroring satellite creation);
- launchpad detail: status, templates, task history, managed satellites;
- create-satellite-through-launchpad flow: orbit picker → template picker → template config form rendered with the existing form-spec machinery (`useSatelliteFields.ts` generalized or reused);
- managed satellites are badged in orbit satellite lists, their edit/delete/key actions disabled with a pointer to the launchpad; release action for daemon satellites;
- delete flows honoring the ownership rules.

## Reference implementation & testing

- **Mock direct plugin**: ships in-repo but registers through the same `luml.launchpads` entry-point group as any third-party plugin. It targets an in-memory "platform" and declares one daemon template and one virtual template whose deploy/undeploy hooks succeed trivially (with switches to force failures). It proves plugin discovery, config validation, secret handling, virtual-satellite execution, and the executor contract end-to-end, and serves as the plugin-author example.
- **Mock launchpad** (poll): ships inside `luml-launchpad-kit` (see Poll mode).
- Backend tests cover the data model rules (ownership, constraints, limits), API guards, plugin discovery, and executor contract; kit tests cover handler lifecycle and the mock launchpad; a full end-to-end test drives create-launchpad → create-virtual-satellite → deploy → undeploy → delete through the mock plugin.

# Scenarios

## Scenario: poll launchpad creation
**Given** an org admin within `launchpads_limit`
**When** they create a poll-mode launchpad
**Then** the response contains the launchpad, a one-time API key, and a `pairing` task; the key hash is stored and the launchpad is unpaired with no templates.

## Scenario: launchpad pairing reports templates
**Given** an unpaired poll launchpad and a daemon holding its key
**When** the daemon calls the pair endpoint with slug and templates
**Then** the launchpad becomes paired, its templates are stored, and subsequent worker calls refresh `last_seen_at`.

## Scenario: create daemon satellite via poll launchpad
**Given** a paired poll launchpad with a daemon template
**When** a user creates a satellite from that template into an orbit
**Then** a managed, unpaired `daemon` satellite record exists in that orbit, a `create_satellite` task is enqueued with the validated template config, and the response contains no API key.

## Scenario: satellite key issued to the launchpad, not the payload
**Given** a `create_satellite` task being processed by a launchpad daemon
**When** the daemon requests credentials for the new satellite via the worker API
**Then** it receives a fresh satellite API key for that managed satellite only, and no launchpad task payload or result ever contains a key.

## Scenario: provisioned satellite pairs normally
**Given** a launchpad daemon that provisioned a satellite runtime with an issued key
**When** the satellite runtime starts
**Then** it pairs over the unchanged `/satellites/v1` contract and serves tasks exactly like an unmanaged satellite.

## Scenario: direct launchpad creation with plugin config
**Given** an installed plugin declaring a config form with a secret field
**When** a user creates a direct launchpad naming that plugin with valid config
**Then** the launchpad is created with the plugin's templates snapshotted, the secret value is encrypted at rest, and no read endpoint ever returns it.

## Scenario: unknown plugin rejected
**Given** no installed plugin named `nope`
**When** a user creates a direct launchpad with `plugin_name: nope`
**Then** creation fails with a clear error listing nothing sensitive, and nothing is persisted.

## Scenario: invalid template config rejected
**Given** a template whose form spec requires a field under given conditions
**When** a create-satellite request omits that field while the conditions apply
**Then** the backend rejects the request with a validation error and no satellite record or task is created.

## Scenario: virtual satellite creation
**Given** a direct launchpad with a virtual template declaring capabilities
**When** a user creates a satellite from that template
**Then** after the plugin's provisioning hook succeeds the satellite record is `virtual`, managed, immediately paired with the template's capabilities, and has no API key hash.

## Scenario: virtual satellite deploy executed by plugin
**Given** a virtual satellite and a deployment targeting it
**When** the deploy task is enqueued on its queue
**Then** the executor invokes the plugin's deploy hook asynchronously, the task transitions pending → running → done, and the deployment reaches the same status/fields a real satellite would produce.

## Scenario: virtual satellite task failure
**Given** the mock plugin's deploy hook forced to fail
**When** a deploy task executes
**Then** the task ends `failed` with an error message and the deployment is marked failed — mirroring the satellite failure contract.

## Scenario: executor restart tolerance
**Given** a virtual-satellite task stuck in `running` beyond the staleness bound after an executor restart
**When** the executor resumes
**Then** the task is retried or failed — observable, never silently dropped — and a retried convergent deploy succeeds.

## Scenario: managed satellite direct edits blocked
**Given** a launchpad-managed satellite
**When** a user calls the orbit satellite update, delete, or key-regeneration endpoints directly
**Then** the request is rejected with an error naming the owning launchpad; reads still succeed and include `launchpad_id` and `kind`.

## Scenario: releasing a daemon satellite
**Given** a managed `daemon` satellite
**When** an org admin releases it
**Then** its `launchpad_id` is cleared, it keeps serving tasks unchanged, and direct user edits are allowed again.

## Scenario: virtual satellite cannot be released
**Given** a managed `virtual` satellite
**When** a release is attempted
**Then** the request is rejected, explaining that virtual satellites can only be deleted through their launchpad.

## Scenario: launchpad deletion blocked by managed satellites
**Given** a launchpad with at least one managed satellite
**When** deletion is requested
**Then** it is rejected until all managed satellites are deleted or (daemon only) released; afterwards deletion succeeds.

## Scenario: launchpads limit enforced
**Given** an organization at its `launchpads_limit`
**When** another launchpad is created
**Then** creation is rejected, mirroring the `satellites_limit` behavior.

## Scenario: poll launchpad status from last seen
**Given** a paired poll launchpad whose daemon stopped polling
**When** the status threshold elapses
**Then** the launchpad shows inactive, using the same last-seen computation pattern as satellites.

## Scenario: virtual satellite status follows launchpad
**Given** a healthy virtual satellite whose direct launchpad's plugin is uninstalled
**When** satellite status is read
**Then** the virtual satellite's status reflects the errored launchpad, not polling recency; its pending tasks fail rather than hang.

## Scenario: unknown launchpad task type
**Given** a launchpad-kit daemon with registered handlers
**When** it polls a task of an unregistered type
**Then** the task is reported failed with an unknown-type error — same semantics as the satellite-kit.

## Scenario: unmanaged satellites unaffected
**Given** the launchpad feature fully deployed
**When** an existing unmanaged satellite pairs, polls, and executes tasks
**Then** every wire interaction is byte-compatible with the pre-launchpad contract.

## Scenario: mock plugin end-to-end
**Given** a clean backend with the mock plugin installed
**When** a test drives create direct launchpad → create virtual satellite → deploy → undeploy → delete satellite → delete launchpad
**Then** every step succeeds with the documented status transitions, exercising discovery, templates, secrets, executor, and ownership rules.

## Scenario: mock launchpad end-to-end
**Given** the `luml-launchpad-kit` mock launchpad pointed at a backend with a poll launchpad key
**When** it runs as a module and a create-satellite task is enqueued
**Then** it pairs, reports templates, processes the task through the handler lifecycle, and reports done.

# Tasks

- [ ] Add launchpad data model and migrations
  - [ ] `launchpads` and `launchpad_queue` tables per the Design entities (`backend/luml/models/`)
  - [ ] `satellites.launchpad_id`, `satellites.kind`, nullable `api_key_hash`, adjusted pairing constraint
  - [ ] `organizations.launchpads_limit` following `satellites_limit`
  - [ ] Pydantic schemas in `backend/luml/schemas/` and repository layer
  - [ ] Model/constraint tests
- [ ] Add launchpad management API and ownership rules
  - [ ] Org-level launchpad CRUD, task listing, key regeneration, managed-satellite listing, release endpoint (`backend/luml/api/organization/`, handler in `backend/luml/handlers/`)
  - [ ] Limits and delete-blocked-by-managed-satellites enforcement
  - [ ] Managed-mutation guard on existing orbit satellite endpoints; `launchpad_id`/`kind` in satellite responses
  - [ ] Permission checks following existing org-resource patterns; tests for guards, limits, release rules
- [ ] Add poll-mode launchpad worker API
  - [ ] `launchpad` authentication scheme parallel to the `satellite` scheme in `backend/luml/infra/dependencies.py`
  - [ ] `/launchpads/v1` router: pair, list tasks, update task status, satellite register/issue-key/update/delete, last-seen touching
  - [ ] Template validation at pairing; create-satellite-via-launchpad endpoint enqueueing daemon-template tasks
  - [ ] Tests covering pairing, task flow, key issuance scoping
- [ ] Add direct plugin framework
  - [ ] Plugin interface (config form, secret marking, templates, task hooks, virtual-satellite hooks, health check) and `luml.launchpads` entry-point discovery at startup
  - [ ] Installed-plugins listing endpoint; direct launchpad creation validating plugin name and config; secret encryption via `luml.infra.encryption`
  - [ ] Plugin context exposing platform operations (deployments, artifacts, secrets) in-process
  - [ ] Tests with a throwaway test plugin: discovery, validation, secret round-trip
- [ ] Add direct-mode task executor and virtual satellites
  - [ ] Executor honoring the contract (async execution, status transitions, staleness handling, last-seen touching); mechanism implementer's choice
  - [ ] Virtual-satellite creation flow (plugin provisioning hook, immediate pairing with template capabilities)
  - [ ] Virtual-satellite status derivation from launchpad status; missing-plugin failure path
  - [ ] Tests for transitions, failure bookkeeping, restart staleness
- [ ] Add mock direct plugin with end-to-end tests
  - [ ] In-repo mock plugin registered via the entry-point group; in-memory platform; one daemon + one virtual template; failure switches
  - [ ] End-to-end test: launchpad → virtual satellite → deploy → undeploy → deletions
- [ ] Build luml-launchpad-kit
  - [ ] New package mirroring satellite-kit architecture: task-handler base with owned lifecycle, registration-driven template declaration, launchpad platform client, runtime entry point
  - [ ] Mock launchpad shipped in the kit, runnable as a module
  - [ ] Kit unit tests (handler lifecycle, unknown task type, pairing payload) against a fake platform client
- [ ] Add frontend launchpad UI
  - [ ] Org-level Launchpads section: list/create (plugin picker + form-spec-rendered config with write-only secrets; poll key display), detail with templates/tasks/managed satellites
  - [ ] Create-satellite-through-launchpad flow reusing the form-spec renderer; managed badges and disabled direct actions in orbit satellite views; release/delete flows
  - [ ] API client interfaces in `frontend/src/lib/api/` with lockstep comments where DSL types are shared
