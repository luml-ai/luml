# Proposals

## Problem

A satellite is a program a customer runs on their own infrastructure. It pairs with the LUML platform using a token, tells the platform what it can do, and then polls the platform for work: deploy a model, undeploy it, or re-apply a changed setting. It also serves the deployed models to callers, checking their API keys and injecting secrets on each request, and it runs a monitoring stack that records inference traffic, computes drift and data-quality metrics, and serves a dashboard that the LUML frontend embeds. Today exactly one satellite exists, the Docker satellite, which runs models as containers on a single host.

The Docker satellite is one program in which all of this is mixed together. The polling loop, the task bookkeeping, the serving proxy, the container management, the crash recovery and the monitoring stack call into each other freely and share process-wide state. Nothing in it can be reused without taking all of it.

This hurts in three ways.

A second satellite cannot be built cheaply. The next one is Kubernetes, and after it come providers such as Modal or SageMaker. Each would have to copy and hand-maintain the polling, the task bookkeeping, the capability declaration, the serving proxy and the monitoring stack, and would drift from the others. A first attempt at extracting a shared library produced only low-level building blocks and left every meaningful responsibility to the satellite author, so it was abandoned.

*Note: that first attempt was PR #342, February 2026.*

The Docker satellite itself is fragile in ways that a shared foundation should fix rather than copy. Tasks are processed one at a time, so one slow deployment blocks every other task behind it. Recovery after a restart is started by the web server and races the polling loop; without the web server there is no recovery at all. A task interrupted by a crash is never picked up again, because only tasks that have not started are ever fetched. The declaration of what the satellite can deploy, with the settings it offers, is maintained by hand and can drift from what the satellite actually does.

The platform's contract with satellites has grown in ways that quietly limit future satellites. Fields that a newer satellite adds to its capability declaration are silently dropped. A satellite must have a public address to pair at all, so a satellite with no web surface cannot exist. Two deployments cannot share one serving address, which rules out servers that host many models. The frontend builds the monitoring URL itself from the satellite's address, so a satellite cannot point to an external monitoring product. A deployment record has nowhere to store a provider's own handle or a human-readable progress note, so long-running or externally managed deployments cannot report what state they are in.

## Solution

Three deliverables, in order.

A satellite development kit: one Python library that owns everything about being a satellite that does not depend on the infrastructure. Pairing, capability derivation, polling, task bookkeeping, deployment convergence and recovery, the serving unit with its authorization and secret injection, and the monitoring stack. An author of a container-style satellite writes only how to start, check, remove and list workloads and which deployment settings to offer. An author of an unusual satellite uses the lower-level parts without adopting the rest.

The Docker satellite rebuilt on the kit. It becomes the reference satellite: identical towards the platform and towards inference callers, with only the Docker-specific parts left in it, and better behaved where the kit is better (parallel convergence, recovery before polling, resumed tasks).

A Kubernetes satellite, installed with a Helm chart on vanilla Kubernetes and on OpenShift. Serving is not funnelled through one process: each model pod gets a sidecar that authorizes callers and injects secrets, so serving scales with the models. Monitoring runs per satellite with its own store, collector, metric worker and dashboard. GPU use is a deployment setting that a satellite offers only when it declares it in its capabilities: the operator of an installation with GPUs turns it on, and a CPU-only satellite declares no GPU setting, so its users are never offered one. Images run as non-root and are published.

Alongside these, small additive changes to the platform contract: keep unknown capability fields, let a deployment carry a provider handle and a progress note, allow pairing without a public address, let a deployment point to an external monitoring link, allow deployments to share a serving address, and serve a versioned description of the satellite-facing API.

Why this direction: extracting passive building blocks was tried and failed, and one monolith per satellite does not scale past two. The kit must own the error-prone invariants (status transitions, recovery, capability derivation) so that a new satellite cannot get them wrong, while leaving every infrastructure decision to the author.

*Note: five independent design reviews against unusual satellites (external monitoring products, serverless providers, multi-model servers, GitOps operators, edge devices) shaped the Design.*

## Constraints

- Satellites already deployed by customers continue to work with no change on their side.
- Kubernetes serving goes through per-pod sidecars, never through the satellite process.
- Monitoring is per satellite; one satellite's traffic must not degrade another's dashboards.
- Kubernetes and OpenShift are served by the same satellite, differing only in installation settings.
- Nothing in the kit may assume it is used internally; a third-party author must be possible without a redesign.
- The kit is usable in pieces: dropping one part must not force dropping the others.
- A later provider satellite (Modal, for example) and later platform-managed satellites reuse the same infrastructure-specific code with no rewrite.

## Non-goals

- Launchpads, virtual satellites and platform-side execution of satellite work.
- High availability of the satellite process itself.
- Monitoring hosted by the platform or shared between satellites.
- Custom task types beyond leaving room for them.
- Traffic splitting, canary rollouts and autoscaling as LUML features.
- A richer settings editor; editing a deployment's settings after creation (they are set once, so a replica count is chosen when the deployment is created). Editing is likely to be needed later, so the Design keeps it possible (see Deployment settings).
- SDK support for satellites without an address or for absolute serving addresses; the SDK already resolves an absolute monitoring link, and both in-repo satellites keep an address, so the SDK keeps working as it is.
- The user guide under `docs/`.

# Design

## Packages and layout

The satellite code today lives under `satellite/`: the agent is one uv project that ships the monitoring UI's committed build output, the UI itself is a separate npm project, and the model server is already a separate uv project beside them. After this work there are four Python packages, each a standalone uv project with its own lock, so that each image and each CI job builds from its own package directory as `sdk/python/api` does today, plus the unchanged monitoring UI:

| package | path | role |
|---|---|---|
| `luml-satellite` | `satellite/kit/` | the kit; extras `serving`, `monitoring` |
| `luml-satellite-docker` | `satellite/implementations/docker/` | the Docker satellite |
| `luml-satellite-kubernetes` | `satellite/implementations/kubernetes/` | the Kubernetes satellite and its chart |
| model server | `model_servers/default/` | unchanged behaviour, non-root image, its own test suite |

The satellite implementations sit under `satellite/implementations/`, one folder each, so the tree shows that they depend on the kit, and a later provider satellite gets a sibling folder.

The model server moves out of `satellite/` into a top-level `model_servers/` folder, with today's server as `default`. It shares no code with the satellites, which reach it only over HTTP and choose it by image name, so it can be used on its own, and further model servers become its siblings. A model server that only one satellite needs lives in that satellite's folder instead. What a model server must answer stays defined in the kit, next to the stub model server. The move changes paths only: the image name `luml-model-server` and the `satellite/model-server/v*` release tags stay, so field installs and the release history are unaffected, while the publish workflow's path filter and build context, the compose file's build context for the model image and the old satellite workflow's lint targets follow the new path.

The satellites depend on the kit as an editable path dependency. Each package mirrors today's tooling (the ruff rule set and line length of `satellite/pyproject.toml`, pytest in auto asyncio mode, respx). The kit and the two satellites add strict mypy. The model server gains tests, lint and a non-strict mypy run; type-only edits to its code are allowed and its behaviour stays unchanged. The kit and the satellites require Python 3.14, as today's agent does, and their ruff and mypy target is 3.14; the model server keeps its own bound. The kit builds with hatchling like `sdk/python/api` and bundles the monitoring UI's build output, so the UI's build target moves into the kit. The built UI bundle stays committed inside the kit, as today. The kit is publishable to PyPI later.

The kit is organised in tiers that import only downward: the wire contract (models and platform client), the declaration (settings, capabilities, pairing, configuration), the workload contract (driver, artifacts, recording, status transitions), convergence (task handling, reconciliation) and the runtime that composes them. The container vocabulary, the `serving` extra and the `monitoring` extra sit beside the tiers. `serving` and `monitoring` never import each other, and what both need lives in the core; `monitoring` implements the recording contract defined in the workload tier; a single sidecar executable composes both. Nothing reads the environment except the configuration object and the executables. The kit keeps no process-wide state, so several satellites can coexist in one process. The kit also ships test doubles (an in-memory fake platform, a scripted fake driver, a stub model server, a driver conformance suite) so satellite authors can test without infrastructure.

Several satellites may also share one host or one cluster, each as its own process with its own token, and they must never touch each other's workloads. The rule is the same for every driver: a workload carries the identity of the satellite that started it, a driver counts a workload as owned only when that identity is its own, and every other workload it can see is foreign, which orphan cleanup logs and leaves alone. The Docker satellite and Kubernetes satellite sections say how each driver applies the rule.
The kit must import and work without the extras; a test blocks `fastapi` and `opentelemetry` and imports the core.

Module layout, internal names, chart value names and template layout are left to the implementer. The kit README, the chart README and the Kubernetes release checklist are requested deliverables.

## Wire contract

The platform client is a port of today's client in `satellite/agent/clients/platform_client.py`: the same calls against the same `/satellites/v1/*` routes, without the process-wide cache, with an injectable transport for tests. Every platform-owned record tolerates unknown fields so that a newer platform's data survives a round trip. A task's type is a plain string so tasks of unknown types parse and can be failed rather than crash the pass.

New in the contract, all optional: a deployment carries `provider_ref`, called the provider handle from here on, and `progress_note`, and the deployment update body carries both; the pairing request carries a `kit` object (`name`, `version`, `kind`, `api_version`) and may omit `base_url`; the paired satellite answer carries `base_url` (possibly null) and `kit_info`; a public `GET /satellites/v1/contract` answers the satellite API version number and the OpenAPI description of the `/satellites/v1/*` routes.

Two existing deployment fields keep their wire names and get prose names here: `inference_url` is the serving address, and `monitoring_url` is the monitoring link, which may now hold an absolute link. The pairing request already carries the satellite's OpenAPI document, called the pairing document from here on.

Pairing sends the kit's version, its kind (`docker`, `kubernetes`) and the API version it was built against, then fetches the contract document and compares. The comparison normalises path parameters so the backend's parameter names do not matter and checks that every operation the client uses exists. Its verdict is logged, never raised: a warning when the platform is newer or the document is unavailable, an error when the platform lacks an operation the kit uses. Pairing also compares the declared capabilities with what the platform kept and logs every dropped or changed field as a warning.

Platform errors map to three families: refusals, authentication failures (401, 403) and everything else. The refusal family is the one today's agent distinguishes (400, 404, 409, 410) with 422 added. A pre-upgrade platform requires `base_url` and answers 422 when it is absent. When no address is configured and the 422's detail names that field, the kit turns it into a clear message ("this platform requires BASE_URL; set BASE_URL or upgrade the platform"), logs it and keeps retrying pairing with backoff. Any other pairing 422 is logged with the platform's detail.

Derived tokens replace today's artifact-token module. They are keyed by the derivation key, a secret the satellite owns and never sends to the platform. The platform can reissue the satellite token at any time, and a workload uses its derived tokens for as long as it runs, so the two must not share a lifetime: with a derivation key configured, a reissued satellite token changes no derived token, and running workloads are neither disturbed nor re-applied. When no derivation key is configured the key is the satellite token, which is today's behaviour. The artifact token keeps today's derivation unchanged, an HMAC over the deployment id alone, so with the default key containers started by the old agent keep verifying. Every other purpose is an HMAC over a purpose and a subject and is domain-separated from the artifact token, so tokens for different purposes cannot collide. The companion purpose yields the companion token. It guards the companion API, which is the interface the satellite offers its sidecars, and each sidecar's internal port; both are described in Serving. A short fingerprint of the derivation key lets a driver label its workloads so a rotated key is detectable.

## Deployment settings

Today the Docker satellite declares no user-facing settings and reads one hidden one, `health_check_timeout`, from a deployment's stored parameters. The platform stores those parameters as a flat mapping of booleans, integers and strings, and the frontend renders a form from a field list the satellite sends at pairing.

A satellite declares its settings as a pydantic model that ignores unknown keys. The model may be a fixed class or one the satellite builds at start from its configuration, as the Kubernetes satellite does so that an operator sets the limits; the kit takes the class either way and treats both alike. The kit derives the field list at pairing from the model and parses a deployment's stored parameters into an instance before any infrastructure call; a parse failure fails the deployment with reason "Invalid deployment settings" naming the field. Allowed field types are exactly what the platform stores: boolean, integer, string, a fixed list of string or integer values (rendered as a dropdown), and a string enum, each optionally nullable. Declaring any other type, including float, fails at class creation naming the field; the Kubernetes satellite expresses CPU in millicores and memory as a dropdown for this reason.

The derived field list keeps today's shape (`name`, `type`, `values`, `required`, `validators`, `conditions`): a boolean field, a dropdown with labelled values, a number with min and max validators from the model's bounds, a text field with a regex validator, in declaration order. A field may be marked unexposed (parsed but not in the form). New: a field with a default carries it as `default`, so the form can pre-fill it (see Frontend changes).

The field format's whole vocabulary stays declarable from the settings model, even though no shipped satellite uses all of it, because the settings a satellite offers depend on the model being deployed as much as on the satellite. A field carries a list of conditions, all of which must hold for the field to be offered, in today's wire shape. A `field` condition compares another setting's value with the operators `equal`, `notEqual`, `gt`, `gte`, `lt` and `lte`, or tests that the other setting is present or absent with `includes` and `notIncludes`. A `model` condition tests the manifest of the model being deployed: its producer tags against tag combinations (`includes`, `notIncludes`), its version (`eq`, `neq`) and its variant (`eq`, `neq`, `includes`, `notIncludes`). A condition whose body is a list of conditions is a nested group. Validators cover the frontend's whole set as well: `min`, `max`, `regex`, `equal`, `in` and `notEqual`, each with an optional message, which is the only help text the form shows. A condition naming a setting the model does not declare fails at class creation naming both fields.

The satellite declares conditions and never evaluates them. The frontend evaluates them to build the form, and the platform verifies them when a deployment is created (see Backend contract changes). The kit parses every stored key whatever its conditions say, because a record created by an older platform or through the API may carry a value the form would have hidden, so a driver never takes a field's presence as proof that its conditions held.

The kit's base settings model carries `health_check_timeout` as an unexposed integer with a lower bound of one and no upper bound, since today's agent accepts it unvalidated. A satellite may override it as an exposed bounded field, as the Kubernetes satellite does. The configured default applies when a deployment stores none, and an overriding field's own default replaces the configured one for that satellite.

Settings are set once, when a deployment is created. Editing them afterwards is a non-goal, but it is likely to be needed later, so nothing may rule it out. Three properties keep it open. The kit parses the stored parameters afresh before every start and keeps no parsed copy between starts. Start is idempotent and re-applies, so a repeated start with changed settings updates the deployment's workload and never duplicates it. Re-applying (see Reconciliation at start) already rolls a workload without a status change. A later edit is then a platform change plus a task that starts the deployment again, with no change to the driver contract.

## Capabilities, pairing and configuration

Capabilities are what a satellite declares at pairing so the platform knows what it can deploy and monitor. Today's agent hard-codes the deploy capability with its settings field list and derives only the monitoring feature list, from the loaded metric registry. The kit derives the deploy capability too and keeps the feature derivation as it is. From the driver's supported variants and tag combinations, the settings model and the feature list of the monitoring bundle (the object that hands the monitoring stack to the runtime, see Monitoring), the kit builds exactly today's declaration: a `deploy` capability with version, API versions, facets (`satellite` and `deployment`, or only `satellite` when nothing is served), variants, tag combinations and the settings field list; and a `monitoring` capability with its facet and feature list. Derivation takes these as plain values (the variants, the tag combinations, the settings field list and the feature list), and the declaration tier sees only the capability-facing part of the bundle contract, so it imports nothing from the tiers above it. The feature list comes from the metric registry actually loaded, so a bundle that lacks a metric declares fewer features.

Configuration is a pydantic settings object, instantiated explicitly and never at import, with every variable of today's `satellite/agent/settings.py` under the same name and default. `BASE_URL` becomes optional. The model image and model server port are driver-specific and belong to the satellites' own configuration.

New variables, named in today's style (upper snake case, no prefix, durations suffixed `_SEC` like `POLL_INTERVAL_SEC`, sizes suffixed `_BYTES`):

| variable | name | default |
|---|---|---|
| poll backoff cap | `POLL_BACKOFF_MAX_SEC` | 60 |
| maximum parallel convergence, per runtime instance | `MAX_PARALLEL_CONVERGENCE` | 8 |
| maximum relaunch attempts, per runtime instance | `MAX_RELAUNCH_ATTEMPTS` | 3 |
| driver call timeout | `DRIVER_CALL_TIMEOUT_SEC` | 300 |
| health pass interval | `HEALTH_PASS_INTERVAL_SEC` | 60, and 0 disables |
| default health-check timeout | `HEALTH_CHECK_TIMEOUT_SEC` | 1800 |
| internal port | `INTERNAL_PORT` | none, optional |
| recording sample rate | `RECORDING_SAMPLE_RATE` | 1.0 |
| recording body cap | `RECORDING_BODY_MAX_BYTES` | 65536 (64 KiB) |
| recording keeps inputs | `RECORDING_KEEP_INPUTS` | true |
| recording keeps outputs | `RECORDING_KEEP_OUTPUTS` | true |
| injection body cap | `INJECTION_BODY_MAX_BYTES` | 16777216 (16 MiB) |
| monitoring session secret | `MONITORING_SESSION_SECRET` | none, optional |
| derivation key | `DERIVATION_KEY` | the satellite token, optional |
| log level | `LOG_LEVEL` | `INFO` |

## Workload driver

The driver is the one thing a container-style satellite author writes. It declares its kind, its launcher protocol (a string written on workloads and compared only for equality, so a driver can recognise and relaunch workloads started under another protocol), its supported variants, its allowed tag combinations (none, as today), its settings model and its artifact delivery mode (`on_demand`, `presigned_link` or `push`). It answers seven operations:

| operation | input | answer |
|---|---|---|
| start | the deployment and a start context | ready, in progress or failed, with the upstream address, an optional provider handle and note, an error and an optional driver-supplied reason on failure, which a raised error may carry too, and optional provider-owned overrides for the serving address and the monitoring link |
| observe | a deployment id | the workload's process state: ready, starting, stopped, missing, failed or unknown, with the upstream, provider handle, note, error and recent logs when known, the launcher protocol written on the workload or none when it carries none, and a flag saying the workload needs re-applying |
| observe all | a set of deployment ids | the same, in bulk, or "unsupported" so the kit falls back to observing one by one |
| remove | a deployment id | whether the workload was removed and, separately, whether that was verified by a re-check, plus the freed artifact id |
| list workloads | — | every workload the driver can see, each with its deployment id when known, its provider handle, and whether it is owned by this satellite and whether it is shared; or "unsupported", which disables orphan cleanup |
| release artifact | an artifact id and whether other deployments still reference it | — |
| sweep | the artifact ids to keep | — |

The start context carries the parsed settings, the resolved secrets (environment variable name to value, resolved by the kit from the deployment's secret-backed variables before start), the artifact handle, the telemetry endpoint, the health-check timeout and the recording policy. Start is idempotent: calling it again for the same deployment re-applies rather than duplicates. The kit bounds every driver call with the configured driver call timeout, so a hung call cannot hold its deployment's lock and a concurrency slot forever: a call that times out is handled like one that raised, and an observe that times out counts as unknown. Remove answers unverified when the removal could not be confirmed in time, which is a legitimate answer; the conformance suite checks only that verified is never claimed without a re-check. An opt-in helper polls observe until the workload leaves the starting state, for infrastructures that prefer a blocking start.

Observe reports process state only. Whether a workload answers its health route is the job of the serving placement, the contract between convergence and wherever serving lives: register and unregister a deployment, answer its address, describe its model (manifest, schema, reference profile), check its health, take note of the platform record, and offer a router for the satellite's application. A no-serving placement, needing no extra, answers the driver's serving address, an empty description and "healthy", for providers that serve by themselves.

The container vocabulary is optional, because the core describes a deployment and the infrastructure decides how many workloads that is. It offers what container-style drivers share: a resources record (millicores, memory, GPU count and resource name), the two label sets (the three labels today's agent writes on containers plus a satellite-id label, and the Kubernetes label set: deployment id, artifact id, satellite id, launcher protocol, derivation key fingerprint), an environment builder keeping today's precedence and reserved names (deployment variables win over secret-backed ones, and the reserved artifact id, deployment id, model name and telemetry endpoint, plus the artifact token and the satellite address when the driver passes them, win over both, with a warning on an override), and the artifact fetch program described next.

## Artifacts

Today a model container downloads its artifact from the agent with a one-time token, and the agent obtains presigned download links from the platform. Both stay, and a third mode is left open.

The artifact resolver answers a handle for whichever mode the driver declares: on demand (the artifact route on the satellite plus the artifact token), presigned link (the platform's download URL with its expiry), or push (a protocol the satellite author implements, with an in-memory double for tests). It also verifies artifact tokens and resolves a deployment's artifact for the satellite's own artifact route, as today's agent does.

The fetch program runs in an init container. Driven by environment variables (link, artifact id, cache directory defaulting to `/app/models`, and optionally the satellite's internal address, the deployment id and the artifact token), it exits immediately when the artifact's directory already exists in the cache, the same test the model server uses; otherwise it streams the archive to a uniquely named partial file, unpacks, and renames into place, the same staging protocol the model server uses, so a shared volume is safe under concurrency. On a 403 or a link already past its expiry it asks the satellite once for a fresh link. A sweep mode deletes every cached artifact not in a keep list and stale partial files. The model server then finds the artifact by its id and never calls anyone; no model-server code changes.

## Convergence

Convergence is the kit's core: it turns platform tasks into driver calls and platform status updates, and it owns every status transition. Today's agent does this in three task classes and one large handler; here it is one component with a per-deployment lock (so one deployment converges one step at a time) and a bound on concurrent driver calls per runtime instance (so deployments converge in parallel). It tracks in-progress deployments in memory with the originating task, a deadline, the last note and whether the entry is a deploy entry or a relaunch entry.

A deploy task runs as follows. Mark the task running (skipped when resuming). Fetch the deployment; failure fails the task and the deployment with reason "failed to get deployment details". Parse the settings; failure fails with "Invalid deployment settings" and never calls the driver. Resolve the secrets; failure fails with "Secret unavailable" naming the variables and never calls the driver. Obtain the artifact handle; failure fails with "Artifact unavailable" and never calls the driver. Call start; an exception fails with "Failed to create container" unless the driver supplies its own reason. Ready finalizes. In progress sends the provider handle and note to the platform and records a deadline of now plus the health-check timeout (the deployment's own or the default). A start that answers failed fails the task and the deployment with the same reason as a start that raises, and cleans up.

The reason sent to the platform is one of the kit's fixed strings. The only exception is a reason the driver supplies with a failed or raising start, which replaces the kit's default. The driver's error text and logs go into the error: a deploy failure carries the last 1000 characters of the driver's recent logs and a not-responding write the last 3000, as today.

Finalizing reads the model's description through the serving placement (manifest, schema, reference profile), registers the deployment for serving, strips secret-backed attributes from the schema as today, and patches the deployment active with the serving address (the driver's override or `/deployments/{id}`), the monitoring link (the driver's override or the bundle's), the schemas, the provider handle and a cleared note and error. The task ends done with the serving address, as today. A description part that is absent or unreadable is recorded as none and never fails finalize, as today, and the same holds for adoption and for the sidecar's start-up read. Before the active patch, only an error while registering the deployment or patching the record is a failure: it fails the task and the deployment with "failed to finalize deployment" and cleans up. Once the record is active, a later failure is logged and leaves the record and the workload as they are; the task is then closed by the rule for an already active record in Reconciliation at start. Finalizing a relaunch entry and adopting a workload have no task: a failure there is logged, leaves the record and the workload as they are, and is retried on the next pass.

Cleaning up after a terminal deploy failure removes the workload and unregisters the deployment from the serving placement. It runs only once start has been called for the task or a workload was observed on resume; the failures before start call nothing on the driver. Removing the workload is a deliberate change from today's agent, which left failed containers behind, and the logs are captured before removal.

An undeploy task marks itself running and drops any in-progress entry, failing that entry's originating deploy task with reason "superseded by undeploy". It then removes the workload, and on an unverified removal or a driver error fails the task and marks the deployment `deletion_failed` with "Failed to remove container." without deleting the record. Otherwise it deletes the record on the platform (404 and 410 count as success; another failure marks `deletion_failed` with "Failed to delete deployment."), unregisters serving, releases the artifact telling the driver whether another deployment still references it (a failure here is logged, the undeploy still succeeds), and ends done with the container-removed flag, as today.

A reconcile task (today's re-apply of a changed monitoring setting) answers "not reconciled" with the current status for an inactive deployment; for an active one it re-registers serving, re-sends the monitoring link and reports whether monitoring is enabled. It keeps today's two failure reasons: "Failed to fetch deployment." when the record cannot be fetched and "Failed to reconcile deployment." when re-applying fails.

Every poll pass revisits in-progress deployments through observe, in bulk when the driver supports it, and sends a changed note to the platform. An entry waits under one deadline: starting, ready but unhealthy and unknown all keep waiting, and all fail at the deadline in the same way. How patient a single health probe is, in timeout and retries, is left to the implementer, provided a revisit never blocks a pass.

Relaunching recovers a workload that stopped serving after activation. It first writes the recovering marker, which is the not-responding status with reason "Recovering", to the platform before touching the workload. It then prepares the start context, calls start and tracks the deployment as a relaunch entry with its own deadline. Two failures end a relaunch early:

- when the marker write fails, the workload is not touched and nothing is relaunched this pass;
- when preparing the relaunch (settings, secrets, artifact) or start fails, the record stays not responding with the marker kept and the cause in the error, nothing is tracked, and the attempt counts against the budget.

Relaunches are bounded per deployment per runtime instance by the configured attempt budget. The budget counts consecutive failed relaunch attempts and resets whenever the record returns to active, by a relaunch finalize or by adoption. A failed marker write does not count as an attempt. When the budget is spent the kit writes one last not-responding update, which leaves the reason unchanged and says in its error, ahead of the logs, that relaunching has stopped; it also logs an error naming the deployment. A restart resets the budget as well.

A health pass runs every health interval. It lists the platform's deployments each time and covers the active and not-responding ones that are not in progress, observing in bulk when possible. This closes the gap where a workload dying after activation was only noticed at the next restart.

The revisit, the health pass and Reconciliation at start act on the observed state by one table:

| observed state | deploy entry | relaunch entry | health pass | reconciliation at start |
|---|---|---|---|---|
| ready and healthy | finalize | finalize back to active, with no task write | adopt | adopt |
| ready but unhealthy | wait | wait | unhealthy | with the marker, track as a relaunch entry with its deadline; without it, unhealthy |
| starting | wait | wait | relaunch | relaunch |
| stopped or failed | died | died | relaunch | relaunch |
| missing | died | died | with the marker, relaunch; without it, not found | as in the health pass |
| unknown | wait | wait | leave for the next pass | look again after fifteen seconds, then leave it to the health pass |

Wait keeps the entry until its deadline. A deploy entry that reaches the deadline fails the task and the deployment with "healthcheck timeout" and the logs, then cleans up. A relaunch entry that reaches it is treated as died.

Died means, for a deploy entry, that the task and the deployment fail with "Container stopped or not found" and the logs, followed by cleanup. For a relaunch entry it means the record becomes not responding with "Relaunched container did not become healthy" and the logs, the workload is kept and the entry is dropped. The marker is thereby cleared, so the workload is judged by its state again on the next pass. Every failed or died outcome also clears the note on the record.

Unhealthy marks the record not responding with "Health check failed" and the logs, once. Not found marks it not responding with "Not Found". The serving registration is kept while a record is not responding or being relaunched, so compute answers the upstream error meanwhile. Adopt is described in Reconciliation at start. In a health pass it does nothing for a deployment that is already registered and active; it registers an active deployment that was never registered, for example after an unknown state at reconciliation.

Status transitions are enforced in one place. The kit re-reads the record before a status-changing write and judges the transition against the status it read. The allowed transitions:

| from | to |
|---|---|
| pending | active, failed, not responding |
| active | active, not responding |
| not responding | active, not responding |
| failed | active, failed, not responding |
| deletion pending | deletion failed |
| deletion failed | deletion failed |

A refused transition is logged as a warning and skipped, never sent, and a status write the platform refuses is handled the same way. When a deploy's final transition is refused because the record is in a deletion status, its task fails like one superseded by an undeploy task. A 404 or 410 on the re-read means the record is gone: the workload is removed, serving is unregistered, the entry is dropped and an originating deploy task fails as one whose record is gone does in Reconciliation at start. Any other failure of the re-read attempts the write and relies on the platform's own refusal. The reason strings on the not-responding paths are today's exact ones.

Informational updates (provider handle, progress note) never fail a deployment: a refused or failed update is logged and convergence continues, and notes are truncated to a thousand characters before sending.

## Reconciliation at start

Reconciliation is what the satellite does once at start: it adopts what is already running, resumes interrupted tasks and removes orphans. Today's agent launches the equivalent recovery from the web server, where it races the polling loop. Here it runs to completion before the first poll and does not need the web server.

First it lists the platform's deployments, retrying with backoff until the platform answers. Then, for every active or not-responding deployment in parallel under the locks, it observes the workload and acts by the reconciliation column of the table in Convergence. Adopting a ready and healthy workload registers it, and if the platform status differs, patches it active (a refusal does not promote, and on 404 or 410 the orphaned workload is removed; an authentication failure is logged and serving continues; any other error keeps serving locally); otherwise it only re-sends the monitoring link. A workload whose launcher protocol is absent or differs from the driver's is relaunched whatever its state. A driver that cannot write the protocol on its workloads answers its own declared protocol from observe, so the rule never fires for it. A workload that observe reports as needing re-applying is started again under its deployment's lock and skipped by the state table in that pass. It is then tracked like a relaunch entry with its own deadline, but with no marker write and no status change, so the health pass leaves it alone while its pods roll. When it becomes ready and healthy it is adopted. The health pass honours the flag in the same way. A re-apply start that fails is logged, leaves the record unchanged, does not count against the relaunch budget and is retried on the next health pass.

Then it lists running tasks. One that does not parse or has an unknown type is failed as in a polling pass, and one of a custom type is handed to its handler again. A deploy task whose record is pending is resumed from the workload's state: ready and healthy finalizes; ready but unhealthy, starting or unknown is tracked with the deadline counted from the task's start time; and stopped, missing or failed calls start again with a fresh deadline of now plus the timeout. A deploy task whose record is already active or not responding ends done with the record's serving address. One whose record is failed ends failed with the record's error. One whose record is deletion pending or deletion failed fails like a deploy task superseded by an undeploy task. An undeploy task runs again, and a record that is already gone counts as success. A reconcile task runs again. A deploy or reconcile task whose record is gone fails with "deployment record gone".

Then orphans: every listed workload that is owned, not shared and whose deployment id is unknown to the platform is removed; shared and foreign workloads are logged and left alone, and a listed workload without a deployment id is never removed. Finally the driver sweeps its artifact cache with the set of artifacts still referenced.

## Polling and the runtime

A polling pass is one round of fetching and scheduling the platform's pending tasks; today's agent runs the tasks of a pass one after another. A pass runs these steps in order:

1. List the pending tasks.
2. Fail those that do not parse ("invalid task payload") and those of unknown type ("unknown type: <type>"), without stopping the pass.
3. Skip tasks already in flight.
4. Schedule each remaining task under the concurrency bound and its deployment's lock, without waiting for it. A handler exception fails the task with "handler error: <message>".
5. Revisit the in-progress deployments.

Custom task types are added as handlers; the kit does not touch their status. The deployment-id requirement and the per-deployment lock apply to the three built-in task types: a built-in task without a deployment id fails as one that does not parse, and a custom task without one runs under the concurrency bound only. A drain operation waits for in-flight work, for shutdown and tests.

The runtime composes a configuration, a driver, an optional serving placement, an optional monitoring bundle and optional custom handlers, and offers capabilities, the HTTP applications (public and internal, either may be absent), pair, reconcile, one poll pass, and run forever. The loop is short and copyable: pair with backoff, reconcile, then poll and run the health pass when due, sleeping the poll interval, with exponential full-jitter backoff up to the configured cap on consecutive failures, an error after five, and for an authentication failure the message "platform rejected the satellite token; re-pair this satellite". On stop it drains, stops the worker and closes stores. One running copy per satellite identity is the documented rule.

## Serving

The serving unit is what today's agent does in its compute route: check the caller's API key, inject secret-backed attributes, forward to the model server, record the call, and serve the deployment's schema. It becomes a FastAPI application built from four replaceable parts and runnable in-process or as a sidecar.

- An authorizer answers allowed, denied or unavailable for an API key. Unavailable answers 502 "Authorization failed" with the platform-backed authorizer, as today, and the 503 described below with the companion one. Its contract and the platform-backed implementation live in the core, because the monitoring extra's machine router, the read-only monitoring routes under a deployment's path that programs call with an API key, uses them too. The platform-backed one asks the platform and caches per instance for a minute; the companion one asks the satellite's companion API and caches with a one-minute TTL, a refresh fifteen seconds before expiry, a ten-minute stale allowance while the satellite is unreachable, and a ten-second negative cache.
- A secret source resolves a deployment's secret-backed attributes by name, platform-backed or companion-backed alike, and reports an unavailable secret by name. The platform-backed one keeps a per-instance cache with today's 60 s TTL.
- A transform hooks the pass-through: it may rewrite the request stream and headers, rewrite the response, and expose the safe inputs to record. The JSON default reproduces today's behaviour: it buffers a JSON body only as far as needed, injects missing secret-backed attributes, and exposes the inputs minus the secret keys. For an upstream error answer it keeps today's `detail` envelope and the upstream status. A request body that is not JSON answers 422 as today when the transform parses it, for injection or for recording; a body forwarded unparsed gets the upstream's own answer in that envelope. A pass-through transform inspects nothing and exposes no bodies to record.
- A recorder wraps the forwarded call: it may contribute upstream request headers, which is how the trace context reaches the model server, and it produces the call's inference event and its event id. The monitoring extra provides the real one and the core provides a no-op.

The public routes keep today's paths, tags, summaries and shapes so the pairing document stays comparable:

| route | change |
|---|---|
| `GET /healthz` | unchanged, bearer-protected |
| `GET /deployments` | read-only listing; never probes or evicts |
| `POST /deployments/{id}/compute` | streaming pass-through with `X-Event-Id` when the call is recorded; its OpenAPI entry reproduces today's JSON body and response so the snapshot keeps the old entry |
| `GET /deployments/{id}/openapi.json` | new: that deployment's schema with secret-backed attributes stripped, for SDK and curl users |
| `GET /openapi.json`, `/docs`, `/redoc` | unchanged |
| `POST /satellites/deployments/inference-access` | now bearer-protected; the exemption in the schema builder is removed |
| `GET /livez` | new, unauthenticated, hidden from the document; answers once the app is up, for probes |

A path that matches no route answers 404 with today's body, the detail plus the code `unknown_route`, while the dashboard's own paths under `/monitoring` keep the plain 404. The API client turns that code into its out-of-sync error, which tells a user that their satellite is older than their client, so the body is part of the contract. The kit installs this handler on every application it builds that serves the machine router.

The kit's own bearer check answers 403 for a missing bearer on every bearer-protected route, whatever the FastAPI version. Today's pinned FastAPI answers 403 and newer releases answer 401.

Two body caps apply. Bodies over the recording cap are forwarded and left out of the event. When secrets must be injected the JSON transform buffers up to the injection cap and answers 413 above it. The upstream timeout stays today's 45 s. Upstream timeouts answer 504 and connection failures 502, each naming the error type (today both are blank 500s); an unavailable secret answers 424 naming the attribute. API keys are cached by hash and never logged.

An event with status and latency is emitted for every call of a monitored deployment. For a deployment whose monitoring is off the serving unit skips the recorder, and the no-op recorder produces nothing; in both cases no event is emitted and the response carries no event id header, as today. Bodies are left out above the recording cap, on a sample miss, when the keep flags exclude them and with the pass-through transform, and every event carries whether bodies were sampled.

The application can be restricted to a single deployment (any other id answers 404 with code `deployment_not_hosted`). It can also run in the not-hosted mode, where compute itself answers that 404, for a satellite whose sidecars serve compute.

The starting gate answers 503 "Satellite starting" on the deployment listing, compute and the per-deployment schema route until reconciliation has finished. The artifact route, the companion API, the liveness route and the monitoring routes are never gated.

The serving unit is placeable: in the satellite process, next to each workload, in a shared pool, inside the workload, or absent when the provider serves. Three placements ship. In-process (Docker) reads health and metadata directly from the model server, including the reference-profile gating that today lives in the deployment schemas. Companion (Kubernetes) keeps a companion record per deployment (secret attribute names, monitoring flag, metadata, artifact id, recording policy), answers the companion API, and reads health and metadata through the sidecar's internal port with the companion token. The no-serving placement is described in Workload driver.

An internal application carries the artifact route (`/satellites/deployments/{id}/artifact` with the artifact token header, hidden from the document) and the companion API. Docker includes it in its public application on the same port, as today, because containers reach the agent there. Kubernetes serves it on the internal port, exposed by the satellite's Service and never by an Ingress.

The companion API is bound to one deployment by the companion token: a wrong token answers 403, an unknown, foreign or not-yet-registered deployment answers 404 with code `deployment_not_hosted`, and the sidecar keeps retrying. It offers authorization of an API key with a TTL, the deployment's secret-backed attributes and the deployment's metadata, which is the companion record. Neither the satellite token nor the derivation key ever enters a model pod.

*Note: a platform-issued per-deployment credential is the recorded end state and would replace only how the companion token is minted.*

The sidecar is one executable configured by environment: the deployment id, the satellite's internal address, the companion token, the upstream model address, the serving and internal ports, the cache TTL and stale allowance, recording defaults, the log level and the telemetry endpoint. It uses the monitoring extra's recorder when the extra is present and a telemetry endpoint is set, else the no-op recorder with one warning. 

At start the sidecar waits for the upstream health route and reads the model's description. The start-up order is an invariant: the liveness route and the internal port come up as soon as the upstream is healthy, independent of the satellite. The metadata fetch retries with backoff in the background. A 404 from the companion API is expected during boot, because a deployment is registered only when it finalizes, and finalizing needs the pod ready and the description read through the internal port. Compute answers 503 until the metadata has been fetched once. The recording policy the satellite returns wins over the environment defaults.

On the internal port the sidecar exposes the model's health, manifest, schema and reference profile behind the companion token, so the satellite, worker and dashboard read metadata without exposing the model port. Its liveness route is unauthenticated on the serving port.

The sidecar refreshes the deployment metadata and the secret values on the same cache TTL and stale allowance as authorization, so a change made by a reconcile task reaches running sidecars within one TTL without restarting pods. While the satellite is unreachable it serves cached answers up to the stale allowance (one warning), then answers 503 "authorization unavailable". Once the sidecar has fetched its metadata, a 403 or a 404 from the companion API is treated like an unreachable satellite: the sidecar serves from cache up to the stale allowance and never caches that answer as a denial. This covers a rotated derivation key and a satellite that restarted and has not reconciled yet.

The sidecar works behind a service mesh: plain HTTP on a named port, no assumptions about the client address, TLS terminated upstream.

## Monitoring

Today's monitoring code under `satellite/agent/monitoring/` is ported into the kit's `monitoring` extra, split into ingest, storage, compute and dashboard, with behaviour unchanged: algorithms, table names, the `/monitoring/*` and `/deployments/{id}/monitoring/*` routes, the launch flow and the static assets are as they are. The service names stay so the collector's filters keep working.

Ingest implements the recording contract and applies the recording policy. Storage defines two protocols, the worker-side store and the dashboard-side query store, with the GreptimeDB and in-memory implementations; new heartbeat read and write operations (a `monitoring_worker_heartbeat` table) let a dashboard in another process answer the worker section. A heartbeat is written per worker shard on each tick and carries what today's worker section shows, including the per-deployment progress and current failures, so the dashboard answers the same section in split mode by merging the shards' heartbeats. A vendor store implements the two protocols and its bundle answers an absolute monitoring link. Compute keeps the metrics and registry; the worker's health is per instance rather than global, it persists heartbeats, touches a heartbeat file each tick, and takes a shard (index, count) selecting deployments by a hash of their id, the later per-deployment split hook. A deployment source abstracts where the worker learns about deployments: the served registry in-process, or the platform (active deployments with full monitoring, refreshed every minute, with metadata read through the sidecars' internal ports using the companion token) in split processes.

Dashboard sessions become stateless: the cookie is a signed, base64 payload (deployment, scope, issued-at, expiry, hard deadline) verified by signature, expiry and hard deadline, so any dashboard replica accepts any other's cookie. Every session-authenticated dashboard response re-issues the cookie with a slid expiry capped by the hard deadline, because today the expiry slides on every authenticated request and the monitoring UI calls the session route only once. The cookie name and the two session dependencies keep their names. The secret comes from configuration and defaults, in-process, to a token derived for that purpose from the derivation key, so with a derivation key configured a reissued satellite token does not end dashboard sessions. The machine router stays bearer-protected by the platform-backed authorizer, so the dashboard process holds the satellite token.

A bundle ties these together for the runtime: it declares the monitoring capability, answers the monitoring link for a deployment (`/deployments/{id}/monitoring` when the deployment's monitoring mode is full, else none), provides the recorder and the worker, mounts the routes, and closes stores. It takes a role: everything in one process (Docker), or one of three split roles (Kubernetes). The satellite role declares the capability, answers monitoring links and mounts the monitoring routers so the pairing document matches Docker's; it needs no store, because the Ingress sends those paths to the dashboard. The worker role runs the metric worker against the store. The dashboard role serves the monitoring routes against the query store, and because the Ingress sends the machine router's paths to it, its application answers an unknown route with the same `unknown_route` body as the serving application. The worker and dashboard executables read the same configuration plus an upstream address template for the sidecars' internal ports; the worker has a probe mode that succeeds while the heartbeat file is younger than three ticks, for an exec liveness probe; the dashboard exposes an unauthenticated liveness route.

Store scaling is configuration: the kit reads the store host and port and optional basic-auth credentials, and the chart carries its own templated copy of the collector configuration, because Helm reads only files inside the chart directory. The copy follows `satellite/otel-collector-config.yaml` with the resolved host, port, database name and credentials instead of the hard-coded address and database name.

## Backend contract changes

The platform backend keeps deployments and satellites in its database and validates what satellites send; every change here is additive. The next migration (040 on top of 039 today) adds `provider_ref` (512 characters, nullable) and `progress_note` (1000 characters, nullable) to deployments, drops the unique constraint on `inference_url` (from migration 011), and adds a nullable JSON `kit_info` to satellites. The downgrade re-creates the constraint and fails naming the duplicates if any exist. The stored parameter type stays booleans, integers and strings.

Capability schemas keep unknown fields instead of ignoring them; the reserved-field and facet validation is unchanged. The pairing input's `base_url` becomes optional, a `kit` object (bounded strings and an API version of at least one) is accepted and stored as `kit_info`, and the satellite read model exposes `kit_info`. The deployment read model exposes the two new fields; the satellite-side update accepts them with the same length limits.

Creating a deployment verifies its satellite parameters against the deploy capability's settings field list, next to today's variant and tag-combination checks and with the same artifact manifest. Conditions are evaluated with the frontend's semantics, over the submitted parameters and the manifest's producer tags, version and variant. A parameter naming a declared field whose conditions do not hold is refused, as is a value that does not match the field's type, its dropdown values or its validators, and a required field whose conditions hold and which is absent. A parameter naming no declared field is stored untouched, because unexposed settings such as `health_check_timeout` are not in the list. A refusal answers 422 naming the field and the failed rule, a condition or validator type the backend does not know is skipped rather than refused so that a newer kit keeps working, and a satellite with an empty field list behaves exactly as today. The frontend already drops the value of a field it stops showing, so the form never submits what this check refuses.

Condition evaluation therefore exists twice, in the frontend's field hook and in this check, and one shared file of condition cases keeps them from drifting. Each case gives a field's conditions, the current values, a manifest's producer tags, version and variant, and whether the field is offered. The file lives under `backend/tests/`, the backend's tests and the frontend's tests both run every case, and a change to either evaluator that the other does not follow fails CI. The platform is the authority on what is stored, so a drift that slips through costs a field shown and then refused by name, or a field hidden though allowed, and never a stored value the declaration forbids.

Monitoring launch resolves its base in one place: the deployment's monitoring link when it is absolute, else the satellite's address when set, else none. Eligibility answers a new reason `no_dashboard_address` when everything else is eligible but no base exists. Minting the launch token without a base answers 409 naming the missing dashboard address, replacing today's 409 "Satellite base URL is not configured". The launch token answer gains a ready-made `launch_url` (`<base>/monitoring/launch?token=…`) and its `satellite_base_url` becomes nullable. An external product still receives the single-use launch token and introspects it through the platform, so no unauthenticated dashboard is ever linked.

A router without authentication serves `GET /satellites/v1/contract`: the API version number and the OpenAPI document generated once from the satellite worker router's routes. The backend is the only home of this description; no contract file is added under `docs/`.

## Frontend changes

Today the monitoring store builds the iframe URL from the satellite address and the launch token, the schema page joins the satellite address with the deployment's relative serving address to form the "try it" server URL (the schema itself comes from the platform record), and the satellite settings form initialises every field empty.

The monitoring store uses `launch_url` when present and falls back to today's construction when the answer only carries a satellite address, as an older backend's answer does; the new backend sends the launch URL whenever a base exists, so the fallback exists only for that deploy-order case. The iframe origin check derives from whichever it used. The monitoring page explains the new reason ("This satellite has no dashboard address.").

The schema page uses an absolute serving address as is, joins a relative one with the satellite address as today, and passes no server URL when the address is relative and the satellite has none; the schema component renders without the server block in that case (today it would target the frontend's own origin).

The settings form seeds a field's value from `default` when present and otherwise leaves it empty as today, and the validators treat an empty non-required field as absent, so a form of numeric fields with defaults submits untouched. Old satellites send no defaults, so nothing changes for them.

The deployments table shows the progress note in a muted line under the pending and not-responding tags when present. The deployment editor shows a read-only provider handle row when present. The satellites card shows the kit kind before the slug when present. Interfaces gain the corresponding optional fields, and the satellite's address becomes nullable.

## Docker satellite

The Docker satellite becomes the driver, its configuration, and a main module that composes the kit, in `satellite/implementations/docker/`. Everything it sends to the platform and answers to callers is unchanged except for the differences listed below.

Its settings model exposes nothing, so the settings field list stays empty and the capabilities and the slug are identical to today's (today's agent applies no resource settings; exposing them would be a change beyond the rebuild). The pairing request gains the kit object, and the pairing document differs only in the two entries named with the snapshot below. Its configuration restores the default `BASE_URL`, and carries the model image, the model server port and the compose network name (hard-coded today). It leaves the derivation key unset by default, so the artifact tokens it mints equal today's. A reissued satellite token does not disturb its running containers either way, because a container presents its artifact token only for its first download and finds the artifact in its own cache afterwards; an operator who sets a derivation key makes that independent of the satellite token by construction.

The driver is kind `docker`, launcher protocol `3`, on-demand artifact delivery. It keeps today's container launcher: the `sat-<id>` container name, the per-artifact cache volume at `/app/models` and the same environment with the satellite address `http://satellite-agent:<port>`. To today's three labels it adds a satellite-id label holding the id the platform answers at pairing. A container is owned only when it has the `sat-` name prefix, the deployment-id label and this satellite's id in the satellite-id label.

Today's agent writes no such label, so two agents on one host remove each other's containers as orphans. Docker cannot add a label to an existing container, so the launcher protocol moves from `2` to `3`, and the launcher protocol rule relaunches every container started by the old agent once, at the first start after the upgrade, which gives it the label. The way to several satellites on one host is therefore to upgrade the existing satellite first and to add the others afterwards. A `sat-` container without this satellite's id whose deployment this satellite does not know is foreign, whether it carries another satellite's id or none.

Each satellite on a host runs in its own compose project with its own network, named by the network name setting, so the `satellite-agent` alias resolves to its own agent. The per-artifact cache volumes are shared by the host's satellites. Docker refuses to delete a volume that a container still uses, which release artifact and the sweep treat as still referenced, as today; deleting a warm volume that only another satellite would have reused costs that satellite one download.

Start answers in progress with the container's address as upstream, and a missing image fails with the driver-supplied reason "Docker image not found", as today. Observe maps the container state: running is ready, created or restarting is starting, exited is stopped with a hundred log lines, every other state that is not running, such as paused, dead or removing, is stopped as well, as today, not found is missing, a daemon error after three attempts is unknown, and the launcher protocol label is reported, or none for a container without it. Bulk observe is unsupported. Remove deletes the container with force and re-reads to verify. Release artifact deletes the per-artifact cache volume unless another deployment still references the artifact. Listing answers every `sat-` container as not shared, and as owned only when it also carries the deployment-id label and this satellite's id. Sweep is today's stale-staging cleanup.

The main module builds the platform client, the driver, the monitoring bundle in the all-in-one role when monitoring is enabled, the in-process serving placement with the platform-backed authorizer and secret source and the bundle's recorder, includes the internal routes on the same application, starts uvicorn on the agent port before reconciling, so the starting gate described in Serving applies until reconciliation ends, and runs the runtime forever with kind `docker` and today's slug. Nothing runs from the web server's lifespan.

Deliberate differences from today's agent, none visible in the declared capabilities:

- containers carry a satellite-id label, and a container started by the old agent is relaunched once, at the first start after the upgrade, to receive it;
- a `sat-` container that does not carry this satellite's id and belongs to no deployment of this satellite is left alone, where today it is removed as an orphan;
- failed deploys remove their container after capturing logs;
- an unreadable secret fails the deployment instead of launching without it;
- the inference-access route requires a bearer, since leaving it unauthenticated is a known defect of today's agent;
- a per-deployment schema route and a hidden liveness route exist;
- upstream failures answer 502 and 504 instead of blank 500s;
- the deployment listing no longer health-probes or evicts;
- compute answers 424 for an unavailable secret instead of forwarding without it;
- compute answers 413 above the injection cap;
- recorded bodies are capped, where today nothing caps them;
- deployment routes answer 503 until reconciliation has finished;
- a workload that dies after activation is relaunched by the health pass instead of only at the next restart;
- relaunch attempts are bounded per runtime instance;
- undeploy counts a 404 or 410 on the record deletion as success, where today any delete error marks the deletion failed;
- an undeploy whose container removal cannot be verified ends in deletion failed and keeps the record, where today removal errors are suppressed and the record is deleted;
- a built-in task without a deployment id fails as a task that does not parse, where today each of the three task classes answers its own reason;
- a stored health-check timeout that does not parse fails the deployment as invalid settings.

The image is built from the `satellite/` context on Python 3.14, copying the kit and the Docker package; the compose file changes only the agent's Dockerfile path and, with the model server's move, the model image's build context. The old `satellite/agent/` stays until the new package passes the same behavioural tests; it is then deleted, and the existing image name, entrypoint and environment names point at the new package. The behavioural suite in `satellite/implementations/docker/tests/` ports today's task, reconcile, undeploy, relaunch, inspection, capability, OpenAPI, artifact, instrumentation, metadata and smoke tests, asserting the same platform calls and HTTP answers except where this Design states a different behaviour, with a regenerated static OpenAPI snapshot that differs from the old one only in the inference-access security entry and the added schema route. The SDK's monitoring contract test is repointed to the new snapshot. Today's three model-server tests move next to the model server.

## Kubernetes satellite

The Kubernetes satellite is the driver, its manifests, a thin API wrapper, its configuration and a main module, in `satellite/implementations/kubernetes/`, plus the chart. Its workloads:

| workload | image | replicas |
|---|---|---|
| satellite | Kubernetes satellite | 1, recreate strategy |
| dashboard | monitoring | configurable, default 1 |
| worker | monitoring | 1 |
| collector | upstream OpenTelemetry collector | 1 |
| store | upstream GreptimeDB standalone | stateful set of 1, absent in external mode |
| one per deployment | model server plus sidecar | the deployment's replica setting |

The settings offered to users describe what this installation can run, so none of their ranges is fixed in code. The operator sets deployment limits in the chart's values, the satellite reads them from its configuration and builds its settings model from them at start, and the field list sent at pairing, the form and the platform's verification of parameters all follow, so a user is never offered a value the cluster cannot honour. The limits are operator configuration and not discovered from the cluster, because reading node capacity needs cluster-wide permissions and the satellite installs with a namespaced Role.

| setting | offered as | limits the operator configures | default limits |
|---|---|---|---|
| replicas | number | maximum, default value | 1–64, default 1 |
| CPU in millicores | number | minimum, maximum, default value | 100–64000, default 1000 |
| memory limit | dropdown | the list of values, default value | eight values from 512Mi to 64Gi, default 2Gi |
| use GPU | boolean, default off | whether GPUs are offered at all | not offered |
| GPU count | number, visible when GPU is on | maximum | 1–8, default 1 |
| GPU resource name | dropdown, visible when GPU is on | the list of resource names | `nvidia.com/gpu`, `amd.com/gpu`, default the first |
| artifact cache | dropdown, ephemeral or shared | offered only when a shared cache claim is configured | not offered |
| health-check timeout | number | minimum, maximum, default value | 60–7200, default 1800 |
| log level | dropdown: debug, info, warning, error | none | default info |

The log level sets the sidecar's log level because the model server reads none. A setting that is not offered is absent from the field list and takes its off value: an installation without GPUs declares none of the three GPU fields, and one without a shared cache claim declares no artifact cache field and always uses the ephemeral cache. A dropdown left with a single value is likewise not offered and takes that value. GPU limits, node selector, tolerations and runtime class are emitted only when GPU is on.

The configuration is validated at start and a contradiction stops the satellite with a message naming the value: a minimum above its maximum, a default outside its limits or its list, an empty list, a memory value that is not a Kubernetes quantity, or a maximum beyond the platform's integer range. Limits take effect at the next pairing, which the restart following a chart upgrade performs. Tightening them never touches a running workload: stored parameters are parsed only when a workload is started, so a deployment whose stored value now falls outside the limits keeps running. A later start treats it as any other invalid value, through the path that started it: a deploy task fails with "Invalid deployment settings" naming the field, and a relaunch or a re-apply leaves the record not responding with that cause in the error. A stored value for a setting that is no longer offered is handled the same way rather than silently ignored: a stored use-GPU that is true on an installation that offers no GPUs is invalid, naming the field. So that the operator learns this before a relaunch does, reconciliation at start logs one warning per active deployment whose stored parameters no longer fit the limits, naming the deployment and the field.

The pod security preset is an installation setting with two values, `vanilla` and `openshift`. Configuration adds the namespace, the satellite name (the release name, written as the satellite-id label), the public base URL (the chart derives `https://` when a TLS secret is configured or the OpenShift preset is chosen, whose edge termination needs no secret, and `http://` otherwise, overridable), the satellite's internal address, the internal port, the model and serving images, ingress class, annotations and TLS secret, the deployment limits, whether GPUs are offered with their maximum count and resource names, GPU node selector, tolerations and runtime class, the shared cache claim name, the pod and container security contexts from the preset, image pull secrets, sidecar resources, and whether monitoring paths are routed.

Per deployment the driver renders four objects, all named `luml-dep-<id>`, labelled managed-by `luml-satellite`, the Kubernetes label set (including the derivation key fingerprint) and `luml.ai/shared=false`:

- A Secret holding the model's environment, the companion token, the artifact link and the artifact token. The model's environment is the environment builder's output, built without a satellite address and without the artifact token: the secret-backed and plain variables plus the reserved model name, deployment id, artifact id and telemetry endpoint. The Secret's key layout is left to the implementer.
- A Deployment with the replica count, rolling updates, the preset's security contexts and GPU placement when on. Its parts:
  - a pod annotation with a hash of the Secret's stable material, which is the model's environment and the derived tokens and not the artifact link, so a repeated start with a fresh link leaves the pods alone while a rotated derivation key rolls them and a reissued satellite token does not;
  - an init container from the serving image, running the fetch program with the link and token from the Secret;
  - the model container, which receives the model's environment, and never the satellite's address, the artifact token, the artifact link or the companion token, with port 8080, resources and a readiness probe on its health route;
  - the sidecar, with the companion token from the Secret, the deployment's log level, named ports `http` and `internal`, and a readiness probe on its liveness route;
  - the cache volume, ephemeral or the shared claim.
- A ClusterIP Service exposing `http` and `internal` only; the model port is never exposed.
- A standard Ingress object on the satellite host, which keeps one host with a path per deployment and the same URL shape as Docker, with prefix rules `/deployments/<id>/monitoring` to the dashboard (only when monitoring paths are routed) and `/deployments/<id>` to the deployment's `http` port, with the chart's TLS. One Ingress per deployment so parallel convergence never edits a shared object.

The driver is kind `kubernetes`, launcher protocol `1`, presigned-link delivery. Start applies the four objects server-side with a fixed field manager and answers in progress with `deployment/luml-dep-<id>` as provider handle, "0/<replicas> pods ready" as note and the Service's internal port as upstream. When the shared cache is chosen and no shared cache claim is configured, start answers failed at once, naming the missing shared cache. Observe answers ready while any replica is available, and ready wins even when another pod is failing. It does not read the Deployment's progress condition: the kit's deadline is the only timeout, so a slow start always fails with the deadline's reason. With no replica available it answers failed when a pod is in an image-pull or crash-loop state, an init container counting only once it is in crash-loop back-off because Kubernetes restarts it by itself, reporting the pod state and message as the error with a hundred lines of the failing container's logs; missing when the Deployment is gone; else starting with "<ready>/<replicas> pods ready" and the first pending condition's message (for example an insufficient-GPU message). 

Bulk observe issues one label-selected list of Deployments and one of Pods. Remove deletes the four objects with foreground propagation and polls up to a minute to verify; when the objects outlive the poll it answers unverified. Listing uses the managed-by label, owned when the satellite-id label matches, shared when the shared label says so. Release artifact does nothing, because the sweep reclaims shared-cache space. Sweep runs a short-lived Job with the fetch program's sweep mode, only for the shared cache. The satellite itself keeps no persistent volume.

Several Kubernetes satellites may share a cluster, in separate namespaces or as differently named releases in one namespace. The satellite-id label is the release name, which is unique within a namespace, and the Role is namespaced, so a satellite sees nothing outside its namespace. Bulk observe selects on the satellite-id label as well as the managed-by label, and listing answers another release's workloads as not owned. The chart names every object it renders after the release, the shared cache claim and the sweep Job included, and the network policy selects on the satellite-id label, so one release's policy neither covers nor admits another release's pods. Each release has its own host, so their Ingress paths never collide.

The satellite's own application serves the public routes on `http` with compute in the not-hosted mode, so the listing, the inference-access check, the merged OpenAPI document, the docs and the liveness route exist and the pairing document is generated from this application with the same routers as Docker. The internal application (companion API, artifact route) is on the `internal` port, exposed by the satellite's Service only. RBAC is a namespaced Role over deployments, services, ingresses, secrets and jobs, plus read on pods and pod logs.

The chart's values are grouped by concern:

- satellite: token or existing secret, derivation key (generated when unset), platform URL, host, base URL override, slug, poll interval, image, resources;
- sidecar: image, cache TTL and stale allowance, recording defaults, resources; the model image;
- deployment limits: maximum and default replicas, CPU minimum, maximum and default, the memory values and their default, health-check timeout minimum, maximum and default;
- GPU: enabled (off by default), maximum count, resource names, node selector, tolerations, runtime class;
- shared cache: enabled, size, storage class, access modes defaulting to ReadWriteMany;
- ingress: class, annotations, TLS;
- pod security preset with overridable pod and container contexts;
- monitoring: enabled, frame ancestors, session secret, dashboard replicas, worker, collector, store mode (standalone or external) with image, persistence, optional object storage, external host, port and credentials, and retention;
- network policy, RBAC and service account.

The templates render:

- the service account and RBAC;
- the secrets, with generated values kept across upgrades by lookup;
- the collector configuration templated with the resolved store address, database name and credentials;
- the satellite Deployment (liveness and readiness on its liveness route) and Service (`http` and `internal`);
- the shared Ingress: `/monitoring` to the dashboard, `/` to the satellite's `http` port, never to `internal`;
- the dashboard and the worker, the latter with an exec probe in its probe mode;
- the collector, and in standalone mode the store stateful set with its Service, its data volume and object-storage configuration when enabled;
- the shared cache claim;
- the network policy: default deny scoped by label to this release's pods and its model pods, so foreign workloads in the namespace are untouched, allowing exactly the flows this design uses. Model pods need external egress, because the init container downloads from the artifact storage host and the real model server builds its environment from package indexes at start. The rest of the enumeration is left to the implementer. The end-to-end job runs with the policy enabled so a missing in-cluster flow fails it, but it cannot verify the external flows, so the release checklist deploys a real model with the policy enabled. The kind cluster must use a network plugin that enforces NetworkPolicy, which one negative assertion in the end-to-end job proves;
- the notes.

Every pod, third-party images included, runs non-root with the runtime default seccomp profile, no privilege escalation and all capabilities dropped, with writable data on volumes. The vanilla preset pins user 10001, group 0 and file-system group 10001. The OpenShift preset pins no user or group (the security context constraint assigns them), uses the `openshift-default` ingress class with the edge-termination annotation, and renders no Route objects. The chart's README documents the values, the presets, the store's path from standalone to object storage to an external cluster, and mesh notes.

The derivation key lives in its own chart-generated Secret, kept across upgrades and mounted into the satellite, dashboard and worker pods, so the chart never runs on the satellite token as the key.

Satellite token rotation: when the satellite token is regenerated and the chart secret upgraded, the chart restarts the satellite, dashboard and worker pods, whose pod templates carry a checksum annotation of the chart-managed token and derivation key secrets. With an existing secret the operator restarts them by hand, which the chart README documents. Nothing else happens: the derivation key is unchanged, so no fingerprint is stale, no Deployment is re-applied, no model pod rolls, and the sidecars' companion tokens keep verifying.

Derivation key rotation is a separate, deliberate operation for a leaked key, documented in the chart README: the operator replaces the key and the same pods restart. After the restart, observe reports every owned Deployment whose fingerprint label is stale as needing re-applying. Reconciliation starts them again, which re-renders their Secrets and rolls their pods; sidecars keep serving from cache meanwhile.

Images: the serving image with both extras, the monitoring image and the Kubernetes satellite image, all on Python 3.14 and all running as user 10001 in group 0 with a group-writable application directory. The model server image sets its home, micromamba root and uv cache under `/app`, makes `/app` group-writable and runs as 10001; micromamba reads its root from the environment, so no code changes. The image also pre-creates `/app/models` owned by user 10001 and group 0 and group-writable. Docker creates a mount point missing from the image as root-owned, so without this a fresh named volume mounted there would not be writable; with it the volume inherits the image's ownership. Compose keeps running the model server with its named volume.

CI adds per-package lint-and-test workflows for the kit, the Docker satellite, the model server (lint, non-strict mypy and its own tests) and the Kubernetes satellite (plus chart lint and unit tests), and an end-to-end workflow with a `vanilla` and an `openshift` leg on kind. The end-to-end job builds and loads the Kubernetes satellite, serving and monitoring images and a stub model image built from the kit's stub model server, installs an ingress controller, runs the kit's fake platform (seeded with a token, an API key, a fixture artifact served through its download-link route, and deploy tasks), and installs the chart with the stub as the model image. The real model server image is covered only by its own image tests, because it needs a loadable model and builds its environment from the network. The OpenShift leg labels the namespace with the restricted pod security standard and passes a random user and file-system group from the OpenShift range with the group left unset, which is what the restricted constraint does. It asserts:

- pairing with kind `kubernetes`;
- a deployment reaching active with `/deployments/<id>` as address;
- a GPU deployment's note naming the insufficient GPU (kind has no GPU; allocation is on the manual checklist);
- compute on a monitored deployment answering 200 with an event id for a valid key and 401 for a bad one;
- the per-deployment schema route;
- the internal path answering 404 from the public host;
- the model port being unreachable from another pod, which proves that the network plugin enforces the policy;
- the monitoring launch redirect and session;
- a deployment created with three replicas having three pods answering;
- compute surviving deletion of the satellite pod;
- a repeated chart upgrade keeping the generated session secret;
- undeploy removing the four objects;
- the orphan rules: an owned hand-made Deployment removed after restart, a foreign one untouched;
- on the OpenShift leg, every pod running as the random user.

Publishing: image workflows for the Kubernetes satellite, the serving image and the monitoring image, modelled on the existing satellite image workflow and pushing to `ghcr.io`, tagged from `satellite/<name>/v*` tags and with the branch tags used today, and a chart workflow packaging with the tag's version and pushing the chart as an OCI artifact to the registry on release tags. A release checklist covers a real OpenShift install with the preset, a Route synthesised from the Ingress, a GPU deployment on a GPU node, a real model deployed with the network policy enabled, inference, the dashboard, the sidecar surviving a satellite restart, a reissued satellite token leaving the model pods untouched, derivation key rotation, undeploy, an upgrade with the recreate strategy, the assigned-user audit and the tag list.

## Dependencies

The kit's core needs httpx, pydantic and pydantic-settings; the `serving` extra adds FastAPI and uvicorn; the `monitoring` extra adds the OpenTelemetry API, SDK and OTLP gRPC exporter and brings its own FastAPI and uvicorn, because its dashboard and executables are web applications that must install without `serving`. The kit declares compatible version ranges whose lower bounds are today's agent's pins. Development tooling matches today's pins plus mypy. The Docker satellite keeps aiodocker; the Kubernetes satellite adds the asynchronous Kubernetes client. CI needs helm, kind and helm-unittest. The process-wide cache library is dropped. The backend, frontend and SDK need nothing new.

## Trade-offs

A Python sidecar rather than Envoy. Envoy is what operators reach for when they already run a mesh, and it solves transport problems (pooling, retries, mutual TLS, uniform telemetry) that are not the serving unit's job. The serving unit does four application-level things: authorize, inject secret values into a JSON body, record the call under a policy, and serve the schema. Envoy's external authorization covers only the first; body rewriting and recording would need a second implementation of the same logic in another language plus Envoy configuration, image and upgrade cadence to own. 

The sidecar is the code the Docker satellite runs in-process, tested by the same suites, small next to a model server, and transparent to a mesh. It scales with the model pods and keeps the satellite off the request path. *Note: an external-authorization placement, exposing the authorizer, secret source and transform behind a small gRPC adapter, is recorded as a future option for operators whose mesh mandates Envoy filters; the trigger is measured, sidecar CPU above roughly a third of the model container's at a customer's peak.*

The trust boundary. Model pods hold only per-deployment tokens derived from the derivation key, so a compromised pod is bounded to its deployment, and a leaked satellite token does not yield them. The dashboard and worker pods hold the satellite token itself, because launch-token introspection, API-key checks and deployment listing are satellite-authenticated, and the derivation key, because they read metadata through the sidecars' internal ports; a compromised dashboard replica is therefore a compromised satellite, and they run under the same security context and network policy as the satellite.

Deliberate Docker differences. The differences listed in Docker satellite leave the declared capabilities, successful compute calls and the monitoring paths as they are. Relaunching the old agent's containers once at the upgrade trades one restart of every model for strict ownership: Docker cannot label a running container, and without the label two satellites on one host cannot tell their containers apart. Removing failed containers after capturing logs trades post-mortem container logs for a host that does not accumulate dead containers. Failing on an unreadable secret trades a silently misconfigured model for a visible error. Capping recorded bodies means that calls whose bodies exceed the recording cap no longer feed the data-quality and drift metrics; the cap is configurable.

Non-blocking convergence keeps tasks running on the platform while workloads boot. That journal is what makes crash resume and parallelism work, at the cost of readiness being noticed up to one poll interval late.

Bounded relaunches. A workload that keeps dying is relaunched a fixed number of times per runtime instance and then left not responding with its last logs; a satellite restart resets the budget, which is the operator's escape hatch.

Stateless signed sessions cannot be revoked before the hard deadline, which the in-memory store could not do either; launch tokens stay single-use on the platform.

Plain objects with labels instead of a custom resource and operator keep the satellite installable with a namespaced Role; an operator-managed satellite is a later driver, not a redesign. An init container with a link and one refresh keeps the satellite off the artifact path; the refresh covers pods recreated after the link's lifetime; a shared cache hit skips both. Removing the uniqueness of the serving address is safe because nothing looks deployments up by it. Settings stay booleans, integers and strings because widening the platform type would touch the ORM, the schema, the SDK and the form, and millicores and dropdowns express every setting the two satellites need.

# Scenarios

## Scenario: The Kubernetes package holds only infrastructure-specific code
**Given** the Kubernetes satellite package built on the kit
**When** an import-boundary test scans the package's modules
**Then** no module imports an HTTP client, and the package reaches the platform only through the kit's client

## Scenario: Fresh Helm install on vanilla Kubernetes and on OpenShift
**Given** a fresh cluster (vanilla, and separately OpenShift) and a satellite token
**When** the operator installs the chart with the matching preset
**Then** the satellite pairs, deploys a model, serves it, and shows its dashboard in LUML; the vanilla case is verified by the kind end-to-end job, and the OpenShift case and GPU allocation by the release checklist

## Scenario: Field Docker satellites survive the upgrade
**Given** a Docker satellite built before this work, which pairs with an address, sends no kit object and never sends the new deployment fields
**When** the platform has applied the new migration
**Then** pairing answers 200 with the same capabilities, updates without the new fields leave them null, and the frontend shows the deployment exactly as before

## Scenario: Both drivers produce the same status sequence
**Given** the kit's scripted deploy case: a start that becomes ready and healthy, and separately a workload that dies before becoming healthy
**When** the Docker satellite's suite and the Kubernetes satellite's suite each run it with their driver against their infrastructure double
**Then** both record the sequence of task and deployment statuses and the reasons the case expects, and only the provider handle and the note differ

## Scenario: Serving scales with the cluster
**Given** a Kubernetes satellite
**When** a deployment is created with three replicas
**Then** three pods with sidecars answer compute behind one Service and the satellite receives no compute request

## Scenario: The monitoring store moves to external mode by configuration
**Given** the chart rendered with a standalone store, and separately in external mode with a host, port and credentials
**When** a chart unit test compares the two renderings
**Then** only these differ: the store workload with its Service and volume, the store credentials, the network-policy egress rule, the store settings in the kit's environment and the collector configuration

## Scenario: A one-shot satellite uses only the lower tiers
**Given** a script composing the platform client, pairing and the convergence deploy step with the no-serving placement and no monitoring bundle
**When** it runs once against the fake platform started as a separate process, with one pending deploy task
**Then** the task ends done, the deployment is active with the serving address from the driver's answer, and neither FastAPI nor OpenTelemetry is imported in the script's process

## Scenario: A vendor store replaces the default without a fork
**Given** a store implementing the worker-side and dashboard-side storage protocols whose bundle answers an absolute monitoring link
**When** it is wired into the worker and the dashboard
**Then** metrics are computed and served against it and the deployment's monitoring link is the absolute one

## Scenario: Kit and platform upgrade independently
**Given** a satellite declaring an unknown capability field
**When** it pairs with the upgraded platform
**Then** the field is stored intact and nothing is logged at warning level

## Scenario: An older platform drops a capability field
**Given** a satellite declaring an unknown capability field
**When** it pairs with the fake platform in legacy mode
**Then** the dropped field is logged at warning level with its dotted path and pairing succeeds

## Scenario: Frontend falls back to today's URLs for old satellites
**Given** a launch-token answer without a launch URL, as an older backend sends, and a record with a relative serving address on a satellite with an address
**When** the monitoring and schema pages open
**Then** the iframe URL is built from the satellite address and the launch token, and the Swagger server URL is the satellite address joined with the relative serving address, exactly as today

## Scenario: Sidecar keeps serving while the satellite restarts
**Given** a sidecar with cached authorization and secrets
**When** the satellite pod is deleted
**Then** valid-key calls keep succeeding within the stale allowance, and the cache refreshes once the satellite is back

## Scenario: Chart installs under OpenShift-equivalent restrictions
**Given** a kind namespace enforcing the restricted pod security standard, a random non-root user and file-system group, and the group left unset
**When** the chart is installed with the OpenShift preset and a model deployed
**Then** every pod starts (store and collector included), inference works, the dashboard is reachable, and every pod runs as the given user

## Scenario: A provider-style driver converges with no kit change
**Given** a fake driver in the provider style, whose start answers in progress with a provider handle and which does not support listing, composed with the no-serving placement
**When** a deploy task converges against the fake platform
**Then** the record becomes active with the driver's serving address and the provider handle, orphan cleanup is skipped, and the test uses only the kit's public contracts

## Scenario: Core imports without the extras
**Given** the kit installed without extras
**When** the wire contract, recording, convergence, runtime and container modules are imported with FastAPI and OpenTelemetry blocked
**Then** the import succeeds

## Scenario: Two satellites share one process
**Given** two runtimes with different tokens and fake drivers
**When** both poll concurrently against two fake platforms
**Then** each registry and cache holds only its own entries

## Scenario: Form fields are derived from the settings model
**Given** the Kubernetes settings model built from the default limits with GPUs offered
**When** the field list is derived
**Then** use-GPU is a boolean with default false, GPU count is a number with min 1, max 8, default 1 and one condition on use-GPU being true, CPU is a number with default 1000, memory is a dropdown of eight values with default 2Gi, and the health-check timeout is present as a number

## Scenario: Every condition and validator of the field format is declarable
**Given** a settings model with a field conditional on the producer tags including a combination, one conditional on the variant, one conditional on the version, one with a nested group mixing a `field` and a `model` condition, one conditional on another setting being present, and fields using the `in`, `equal` and `notEqual` validators and a regex with a message
**When** the field list is derived
**Then** each condition and validator appears in today's wire shape with the frontend's operator names, the frontend's field hook shows and hides each field for matching and non-matching models without any frontend change, and a condition naming an undeclared setting fails at class creation naming both fields

## Scenario: Stored parameters are parsed whatever their conditions say
**Given** a settings model whose GPU count is conditional on use-GPU, and stored parameters with use-GPU false and a GPU count
**When** the parameters are parsed
**Then** parsing succeeds and the instance carries both values, and no condition is evaluated

## Scenario: Stored parameters are parsed leniently for unknown keys and strictly for known ones
**Given** the Kubernetes settings model built from the default limits
**When** parameters with replicas set to zero, and separately with an unknown key, are parsed
**Then** the first raises a settings error naming replicas and the second ignores the key

## Scenario: Non-scalar and float settings fields are rejected at declaration
**Given** a settings subclass with a list field, and separately one with a float field
**When** each class is created
**Then** a declaration error names the field

## Scenario: Deploy form submits with the declared defaults
**Given** the Kubernetes settings field list as the satellite's declaration
**When** the deployment form renders and the user touches no satellite field
**Then** every number and dropdown shows its default, validation passes, and the submitted parameters are the defaults as flat scalars

## Scenario: Deploy form is unchanged for a declaration without defaults
**Given** a field list without default keys, as an old satellite sends
**When** the deployment form renders
**Then** the fields are empty and behave exactly as today

## Scenario: Capabilities are derived, not listed
**Given** a monitoring bundle whose registry lacks the multivariate drift metric
**When** capabilities are derived
**Then** the monitoring features are runtime, traces, alerts, data quality, feature drift and output drift, and the deploy capability's field list equals the settings model's derived list

## Scenario: Deployments converge in parallel, one at a time per deployment
**Given** deploy tasks for A, B and C where A's start blocks on an event, and a reconcile task for A
**When** one poll pass runs
**Then** B and C reach active while A is starting, A's reconcile task runs only after A's start call has returned, and in-flight driver calls never exceed the configured bound

## Scenario: An in-progress start is revisited without blocking
**Given** start answers in progress with a note and a provider handle, and observe answers starting with a new note, then ready and healthy
**When** three passes run
**Then** the platform receives the handle and note, then the new note with no status change, each pass returns after one driver call, and after the third the record is active with a cleared note and the task is done with the serving address

## Scenario: Progress notes are truncated and their failures tolerated
**Given** an in-progress deployment whose driver reports a 1200-character note, and a platform answering 422 to the note update
**When** a pass runs
**Then** the note is sent truncated to 1000 characters, the 422 is logged, and the deployment keeps converging

## Scenario: A start that never becomes ready fails at the deadline
**Given** a health-check timeout of 60 seconds and a driver always answering starting with logs, and separately one always answering ready while the health check keeps failing
**When** the clock passes the deadline
**Then** in both cases task and deployment are failed with reason "healthcheck timeout", the logs in the error and a cleared note, remove was called once, and the deployment is no longer in progress

## Scenario: Invalid settings fail before the driver
**Given** stored parameters with a non-numeric GPU count
**When** the deploy task runs
**Then** start is never called and the deployment is failed with reason "Invalid deployment settings" naming the field

## Scenario: An unreadable secret fails before the driver
**Given** a deployment whose secret the platform answers 404 for
**When** the deploy task runs
**Then** start is never called and the deployment is failed with reason "Secret unavailable" naming the variable

## Scenario: An unavailable artifact fails before the driver
**Given** a deployment for whose artifact the platform answers no download link
**When** the deploy task runs
**Then** start is never called and the deployment is failed with reason "Artifact unavailable"

## Scenario: A failure after activation leaves the deployment alone
**Given** a deploy whose active patch succeeded and whose task write then fails, and separately one whose serving registration fails before the active patch, and separately one whose schema and reference profile cannot be read
**When** the pass ends, and the satellite later restarts
**Then** the first record stays active with its workload kept, the failure is logged, and reconciliation ends its task done with the record's serving address; the second is failed with "failed to finalize deployment" and its workload removed; the third becomes active with those parts recorded as none

## Scenario: A crash mid-deploy is resumed before polling
**Given** a running deploy task started two minutes ago, a pending record and a starting workload, and separately the same task and record with a missing workload
**When** the satellite starts
**Then** the deployment is tracked with the deadline counted from the task's start, no second running write happens, pending tasks are only listed after reconciliation returned, and it finalizes when ready; in the second case start is called again and the deadline is counted from now

## Scenario: A running task whose record already settled is closed
**Given** running deploy tasks whose records are active, not responding, failed and deletion pending
**When** reconciliation runs
**Then** the first two end done with the record's serving address, the third ends failed with the record's error, and the fourth ends failed with reason "superseded by undeploy"

## Scenario: Recovery marker protects a missing workload
**Given** a not-responding record with the recovering marker and a missing workload, and separately the same without the marker
**When** reconciliation runs, and separately a health pass runs
**Then** the marked one is started, and the unmarked one becomes not responding with "Not Found" and nothing starts, in both passes

## Scenario: An exited workload is relaunched with the marker written first
**Given** an active record whose workload has exited
**When** reconciliation runs
**Then** the record receives the recovering marker before the driver is asked to start

## Scenario: A relaunch that never becomes healthy stops relaunching
**Given** an active record whose driver answers stopped, then starting forever after each start
**When** health passes run and the relaunch deadline passes, three times
**Then** the first round starts from the stopped workload and the next two from the starting workload that is no longer tracked; each round writes the recovering marker and then "Relaunched container did not become healthy" with the logs, no failed status is ever attempted, remove is never called, and a fourth pass starts nothing, writes one last not-responding update whose error says relaunching has stopped, and logs an error naming the deployment

## Scenario: A failed marker write leaves the workload untouched
**Given** an active record whose workload has exited, and a platform answering 500 to the marker write
**When** a health pass runs
**Then** start and remove are never called, nothing is tracked, and the attempt budget is untouched

## Scenario: A start failure during a relaunch keeps the marker
**Given** an active record whose workload has exited, and a driver whose start raises
**When** health passes run
**Then** the record stays not responding with the recovering marker and the cause in the error, nothing is tracked, and once the attempt budget is spent no further start is called and one last update, with the marker kept, says in its error that relaunching has stopped

## Scenario: A successful relaunch restores the full budget
**Given** an attempt budget of three, and an active record whose workload exits, fails two relaunches, becomes ready and healthy after the third, and exits again later, and separately one that fails two relaunches, recovers by itself and is adopted
**When** health passes run
**Then** the third relaunch finalizes back to active, and the later exit is relaunched again with all three attempts available; the adopted one also has all three attempts available at its next exit

## Scenario: Reconciliation waits for the platform and needs no web server
**Given** a platform answering 503 twice then 200 to the deployment listing, and a runtime without any HTTP application
**When** the satellite starts
**Then** it retries with backoff, registers the running deployments after the third answer, and lists pending tasks only afterwards

## Scenario: Deployment routes are gated until reconciliation ends
**Given** a runtime whose reconciliation has not finished, with a serving application that includes the internal routes and the monitoring routes
**When** the deployment listing, compute and the per-deployment schema route are called, then the artifact route, the companion API, the liveness route and a monitoring route, and all of them again after reconciliation
**Then** the first three answer 503 "Satellite starting" before reconciliation ends and are served after it, and the others are never gated

## Scenario: A workload observed unknown at reconciliation is left to the health pass
**Given** an active record whose driver answers unknown twice
**When** reconciliation runs
**Then** observe is called again after fifteen seconds, no status is written, nothing is started or removed, and the next health pass observes the deployment and, finding it ready and healthy, registers it

## Scenario: Orphan cleanup never removes shared or foreign workloads
**Given** listed workloads x (owned, shared), y (owned), z (not owned) and w (owned, without a deployment id), none known to the platform
**When** reconciliation runs
**Then** only y is removed

## Scenario: Orphan cleanup is skipped without listing
**Given** a driver that does not support listing
**When** reconciliation runs
**Then** nothing is removed

## Scenario: Illegal transitions are refused by the kit
**Given** a deploy entry in progress whose record was set to deletion pending meanwhile, with a ready and healthy workload
**When** the next pass finalizes it
**Then** no active status is sent, a warning names the refused transition, and the deploy task ends failed with reason "superseded by undeploy"

## Scenario: A record deleted on the platform ends convergence
**Given** a deploy entry in progress with a ready and healthy workload whose record the platform deleted without an undeploy task, so the re-read answers 404, and separately one whose re-read answers 500
**When** the next pass finalizes each
**Then** for the first no status is sent, the workload is removed, serving is unregistered, the entry is dropped and the deploy task ends failed with "deployment record gone"; for the second the active patch is attempted

## Scenario: An undeploy arriving during a start supersedes the deploy
**Given** a deploy entry in progress and a pending undeploy task for the same deployment
**When** a poll pass runs
**Then** the entry is dropped, the deploy task ends failed with reason "superseded by undeploy", the workload is removed, the record is deleted and the undeploy task ends done

## Scenario: Undeploy refuses to delete the record after an unverified removal
**Given** a driver whose remove answers unverified
**When** the undeploy task runs
**Then** the deployment is deletion failed with "Failed to remove container." and the record is never deleted

## Scenario: Undeploy reports a verified no-op removal
**Given** a driver whose remove answers not removed but verified
**When** the undeploy task runs
**Then** the record is deleted and the task ends done with the container-removed flag false

## Scenario: Undeploy is idempotent and truthful about the platform
**Given** an undeploy task where the record delete answers 404, and separately one where it answers 500, and separately one where releasing the artifact raises
**When** each runs
**Then** the first ends done, the second marks the deployment deletion failed with "Failed to delete deployment.", the third ends done, and no in-progress entry remains for any of them

## Scenario: Reconcile task outcomes
**Given** reconcile tasks for a failed deployment, for an active one, for one whose record cannot be fetched, and for an active one whose re-registration raises
**When** each runs
**Then** the first ends done with "not reconciled" and the record's status, the second re-registers serving, re-sends the monitoring link and ends done reporting whether monitoring is enabled, the third fails with "Failed to fetch deployment." and the fourth with "Failed to reconcile deployment."

## Scenario: A crashed workload is noticed after activation
**Given** an active record whose driver starts answering stopped
**When** a health pass runs
**Then** the platform record becomes not responding with the recovering marker before start is called, and the deployment is tracked as a relaunch entry

## Scenario: Health passes observe in bulk when the driver allows
**Given** a driver supporting bulk observe and five active records
**When** a health pass runs
**Then** the driver is asked once for all five

## Scenario: Unknown and custom task types
**Given** a task of an unknown type with no handler, and separately a runtime with a handler for that type and a task of it that carries no deployment id
**When** a poll pass runs
**Then** the first is failed with "unknown type: <type>" without stopping the pass, and the second awaits the handler, under the concurrency bound only, without the kit touching its status

## Scenario: A hung driver call is bounded
**Given** a driver call timeout of 5 seconds, a driver whose start never returns for deployment A, and a pending deploy task for B
**When** a poll pass runs and the clock passes the timeout
**Then** A's deploy fails like a start that raised and releases its lock and its concurrency slot, B converges meanwhile, and an observe that hangs counts as unknown

## Scenario: The poll loop backs off and names a rejected token
**Given** a platform answering 500, then 401, to the task listing
**When** ten passes run with an injected clock
**Then** sleeps grow toward the backoff cap, one error appears after five failures, and the 401 logs "re-pair this satellite"

## Scenario: The contract check logs and never blocks
**Given** a contract route answering 404, then a document lacking the task listing, then a newer API version, then a document naming path parameters differently from the kit
**When** the kit pairs each time
**Then** the verdicts are unavailable (warning), older platform (error), newer platform (warning) and ok, and pairing proceeds every time with the kit object in the body

## Scenario: Pairing without a public address
**Given** no base URL configured
**When** the satellite pairs
**Then** the body has no address key, the platform stores a null address and the kit info, and the satellites page renders it as active

## Scenario: An older platform demands an address
**Given** no base URL configured and the fake platform in legacy mode, and separately a platform answering 422 to pairing for a rejected capability
**When** the satellite pairs
**Then** the 422 is logged as "this platform requires BASE_URL; set BASE_URL or upgrade the platform" and pairing is retried with backoff; the second 422 is logged with the platform's detail and without that message

## Scenario: Inference-access check requires a bearer
**Given** a serving application
**When** the inference-access route is called without authorization, and then with a valid bearer
**Then** the first answers 403, the second answers the verdict for the key in the body, and the static document marks the operation as bearer-protected

## Scenario: Liveness is public and hidden
**Given** a serving application
**When** its liveness route is called without a bearer
**Then** it answers 200 and is absent from the OpenAPI document

## Scenario: Serving injects secrets and records under the policy
**Given** a served deployment with monitoring on and one secret-backed attribute, a policy sampling half the calls with a 1 KiB recording cap, and a sample draw that misses then hits
**When** two compute calls succeed
**Then** the upstream receives the attribute both times, both events carry latency and status, the first has no bodies, the second carries bodies without the secret, and both responses carry an event id

## Scenario: A deployment with monitoring off is served without recording
**Given** a served deployment whose monitoring is off, and separately a monitored one served with the no-op recorder
**When** a compute call succeeds on each
**Then** the upstream's answer is returned, no event is emitted and neither response carries an event id

## Scenario: Bodies above the recording cap are forwarded and left out of the event
**Given** a monitored deployment, a 1 KiB recording cap and a 2 KiB injection cap
**When** a 1.5 KiB body needing injection is posted, and then a 3 KiB one
**Then** the first reaches the upstream with the secret injected and its event carries status and latency without bodies, and the second answers 413

## Scenario: Recording propagates the trace context upstream
**Given** a monitored deployment served in-process with the monitoring extra's recorder, and separately a sidecar recording through the monitoring extra
**When** a compute call is forwarded in each
**Then** the upstream request carries a trace-context header in both

## Scenario: Serving names its failures
**Given** a served deployment
**When** its secret is unavailable, then the upstream times out, then the upstream refuses connections
**Then** the answers are 424 naming the attribute, 504 naming the timeout error type, and 502 naming the connection error type

## Scenario: Pass-through streams without buffering beyond the cap
**Given** a monitored deployment, the pass-through transform and a 4 KiB recording cap
**When** a 50 MiB binary body is proxied
**Then** the upstream receives all 50 MiB, peak buffered data stays under 8 MiB, and the event carries status and latency without bodies

## Scenario: Companion cache timeline
**Given** a companion authorizer with a 60 s TTL, refresh 15 s ahead and a 600 s stale allowance, and a counting fake companion API
**When** one key is checked at 0, 50 and 70 seconds, then the API fails and the key is checked at 500 and 1000 seconds, and a new key at 500
**Then** the API was called once by 50 s, a background refresh happened between 45 and 70 s, 500 s succeeds from the stale entry, the new key answers 503 "authorization unavailable", and 1000 s answers 503

## Scenario: A refusing companion API is treated like an unreachable satellite
**Given** a sidecar that has fetched its metadata and cached one key, and a companion API that then answers 404 because the satellite restarted and has not reconciled yet, and separately 403 because the derivation key was rotated
**When** the cached key and a new key are checked within the stale allowance
**Then** in both cases the cached key succeeds from the stale entry, the new key answers 503 "authorization unavailable", and neither refusal is cached as a denial, so both keys are checked afresh once the companion API answers again

## Scenario: Companion API refuses wrong tokens and foreign deployments
**Given** the companion API
**When** it is called with a wrong token, with a foreign deployment id, and with a deployment not yet registered
**Then** the answers are 403, 404 with code `deployment_not_hosted`, and the same 404

## Scenario: Sidecar starts while the satellite is down
**Given** a sidecar whose satellite is unreachable at boot, and separately one whose companion API answers 404 because the deployment is not registered yet
**When** each starts
**Then** the liveness route and the internal port answer once the upstream is healthy, compute answers 503 while the metadata fetch retries with backoff, and compute is served once the metadata has been fetched

## Scenario: Sidecar records through the monitoring extra
**Given** a sidecar with the monitoring extra installed and a telemetry endpoint set, and separately one without an endpoint
**When** each starts and receives the deployment metadata
**Then** the first records through the instrumentation and applies the policy the satellite returned over its environment defaults, and the second uses the no-op recorder and logs one warning

## Scenario: Sidecar internal port is token-guarded
**Given** a running sidecar
**When** the model manifest is requested on the internal port without the companion token, and then with it
**Then** the answers are 403 and 200

## Scenario: A monitoring mode change reaches a running sidecar
**Given** a Kubernetes deployment whose sidecar records calls, and a reconcile task that turns its monitoring off
**When** the reconcile task has run and one cache TTL has passed
**Then** the sidecar has stopped recording without a pod restart, and turning monitoring on again starts recording within one TTL

## Scenario: Dashboard sessions survive a replica switch and honour the cap
**Given** two dashboard applications sharing a session secret, a 60 s sliding TTL and a 120 s hard deadline
**When** a cookie from a launch on the first is presented to the second, each time as last re-issued, on query routes at 40 and 90 seconds and on the session route at 140 seconds
**Then** the answers are 200 with a slid cookie at 40 and at 90 seconds, so query requests alone keep the session alive past one TTL, and 401 at the hard deadline

## Scenario: Tampered sessions are refused
**Given** a valid session cookie
**When** its signature is altered
**Then** the session route answers 401

## Scenario: Split worker and dashboard
**Given** the worker process with the fake platform listing one active deployment with full monitoring, a fake sidecar internal port serving a profile behind the companion token, an in-memory store with events, and the dashboard process on the same store
**When** one tick runs
**Then** runtime health and data quality results are written for the latest window, the dashboard's worker section reports running with the tick's heartbeat and the deployment's windows processed, last window end, last lag and current metric failures, the machine router's worker answer built from the heartbeat carries every field the API client requires of that operation, an unknown path under the deployment's monitoring prefix answers 404 with the code `unknown_route` from the dashboard process, and the worker's probe mode exits 0 and then 1 once the heartbeat file is older than three ticks

## Scenario: Sharded workers split the deployments
**Given** two workers with shards (0, 2) and (1, 2)
**When** both tick over the same deployments
**Then** every deployment is processed by exactly one worker, and the dashboard's worker section merges both shards' heartbeats

## Scenario: The platform verifies satellite parameters against the declared fields
**Given** a satellite whose field list has a GPU count conditional on use-GPU being true, a field conditional on a producer tag, a required field, a bounded number and a dropdown, and an artifact without that tag
**When** deployments are created with a GPU count while use-GPU is false, with the tag-conditional field, without the required field, with a number out of bounds, with a value outside the dropdown, then with valid parameters plus `health_check_timeout` and another undeclared key, and with a field whose condition type the backend does not know
**Then** the first five answer 422 naming the field and the failed rule, the sixth is created with every parameter stored, the seventh is created, and a satellite with an empty field list accepts any parameters as today

## Scenario: The two condition evaluators cannot drift
**Given** the shared condition case file, covering every condition type, operator and nested group with matching and non-matching values and manifests
**When** the backend's tests and the frontend's tests each run every case through their own evaluator
**Then** both agree with every case's expected answer, and a change to one evaluator's answer for any case fails that side's CI run

## Scenario: Backend keeps unknown capability fields and validates known ones
**Given** a capability declaration with an unknown field in the deploy capability and a custom capability
**When** it is normalised
**Then** the unknown field is kept, a string version is still rejected with 422, and the custom capability is stored as before

## Scenario: Contract document is public and versioned
**Given** no authorization header
**When** the contract route is requested
**Then** it answers 200 with API version 1, every path starting with `/satellites/v1/`, the pair and task routes present, and no user-facing route

## Scenario: Provider handle and progress note round trip
**Given** a pending deployment
**When** the satellite sends a provider handle and a note, then active with a null note
**Then** the user-facing read shows both, then the handle with a null note

## Scenario: A progress note is bounded
**Given** a deployment
**When** the satellite sends a 1001-character note
**Then** the platform answers 422

## Scenario: Two deployments share a serving address
**Given** the backend with the new migration applied
**When** two deployments are updated with the same absolute serving address
**Then** both succeed

## Scenario: Monitoring launch with an external link
**Given** a deployment with an absolute monitoring link on a satellite without an address
**When** the launch token is minted
**Then** the launch URL is the link followed by the launch path and token, and the satellite address in the answer is null

## Scenario: Monitoring launch with a relative link
**Given** a deployment with a relative monitoring link on a satellite with an address
**When** the launch token is minted
**Then** the launch URL is the satellite address followed by the launch path and token

## Scenario: Monitoring launch without any address
**Given** a deployment with a relative monitoring link on a satellite without an address
**When** eligibility is checked, and separately the launch token is minted
**Then** eligibility answers ineligible with reason `no_dashboard_address`, minting answers 409 naming the missing dashboard address, and the page shows "This satellite has no dashboard address."

## Scenario: The new migration upgrades and downgrades
**Given** a database at the revision before the new migration
**When** the upgrade and then the downgrade run
**Then** both succeed and the new columns exist only after the upgrade

## Scenario: Downgrade refuses duplicate serving addresses
**Given** a database with the new migration applied and two deployments sharing a serving address
**When** the downgrade runs
**Then** it fails naming the duplicate values

## Scenario: Frontend shows new fields only when present
**Given** one record with a provider handle, a note and an absolute serving address on a satellite without an address, and one old record
**When** the table, editor, schema page and satellites card render
**Then** the first shows the note under the tag, the provider row, the absolute server URL and the kit kind, and the second matches today's snapshots

## Scenario: Schema page without any server URL
**Given** a record with a relative serving address on a satellite without an address
**When** the schema page renders
**Then** the schema is shown and the server block is hidden

## Scenario: GPU settings render from the declared fields
**Given** the Kubernetes settings field list, derived from the default limits with GPUs offered, as a fixture
**When** the form renders and use-GPU is toggled
**Then** GPU count and GPU resource appear only when it is on, and the submitted parameters are flat scalars

## Scenario: Docker capabilities are wire-identical
**Given** the rebuilt Docker satellite with monitoring
**When** it pairs
**Then** the capabilities equal today's declaration exactly, including the empty settings list, the slug is today's, the pairing request additionally carries the kit object, and the OpenAPI document equals the new snapshot, which differs from the old only in the inference-access security entry and the added schema route, with the compute operation's body and response unchanged

## Scenario: Old-agent containers are relaunched once to receive the satellite label
**Given** a running `sat-<id>` container carrying only today's three labels with launcher protocol 2, healthy, and an active record
**When** the rebuilt satellite starts, and later starts again
**Then** the first start writes the recovering marker, replaces the container with one carrying the satellite-id label and launcher protocol 3, and the record returns to active; the second start registers it, re-sends only the monitoring link, and creates or removes no container

## Scenario: Two Docker satellites share a host
**Given** two rebuilt satellites with different ids on one Docker daemon, each with an active record and its container, and a `sat-` container without a satellite-id label whose deployment neither satellite knows
**When** both reconcile
**Then** each adopts only its own container, neither removes the other's, and the unlabelled container is logged and left alone

## Scenario: Containers without the driver's launcher protocol are relaunched
**Given** a running container without the launcher protocol label and an active record
**When** the rebuilt satellite starts
**Then** the recovering marker is written and the container is relaunched

## Scenario: Docker deploy failure removes the container after capturing logs
**Given** a container dying before its health route answers
**When** the rebuilt satellite runs the deploy task
**Then** the platform receives task running, deployment failed with "Container stopped or not found" and the last 1000 characters of the container's recent logs, task failed with the same message, and the container is removed afterwards

## Scenario: Docker driver maps container states
**Given** containers the daemon reports as running, created, restarting, exited, paused and dead, a deployment with no container, and a daemon that errors three times
**When** observe runs for each
**Then** the answers are ready, starting, starting, stopped with a hundred log lines, stopped, stopped, missing and unknown

## Scenario: Docker image and compose keep field-install names
**Given** the updated compose file and publish workflow
**When** the compose configuration is resolved with today's environment file, and separately the driver starts a container with the network name overridden
**Then** the configuration resolves, the service name, image name, port mapping and network alias are unchanged, and the container joins the network named by the override

## Scenario: Kubernetes manifests carry GPU and cache settings
**Given** GPU on with two AMD GPUs, a shared cache, three replicas, 1500 millicores and chart GPU tolerations
**When** the manifests render
**Then** the Deployment has three replicas, the model container alone has the CPU and GPU limits, the shared claim is mounted at `/app/models` in the init and model containers, the tolerations are copied, the model container's environment carries the model name, deployment id, artifact id and telemetry endpoint and neither a satellite address nor the artifact token, the sidecar environment has neither the satellite token nor the derivation key, the companion token is only on the sidecar and the artifact link only on the init container, every container drops all capabilities, the Service exposes only the two named ports, the Ingress lists the monitoring path before the deployment path, the fingerprint label and secret-hash annotation are present, and a second render with a fresh artifact link leaves the annotation unchanged

## Scenario: Kubernetes manifests with defaults request no GPU
**Given** the default settings and monitoring paths not routed
**When** the manifests render
**Then** no GPU limit, node selector, toleration or runtime class appears and the Ingress has no monitoring rule

## Scenario: A small cluster without GPUs offers only what it can run
**Given** a Kubernetes satellite configured with a CPU maximum of 4000 and default of 500, memory values 512Mi, 1Gi and 2Gi with default 1Gi, a replicas maximum of 2, GPUs not offered and no shared cache claim
**When** the field list is derived and sent at pairing, and deployments are then created on the platform with 8000 millicores, with use-GPU true, and with 2000 millicores
**Then** the field list carries CPU with max 4000 and default 500, memory as a dropdown of the three values with default 1Gi, replicas with max 2, and no GPU and no artifact cache field, the first two creations answer 422 naming the field, and the third renders a Deployment with a 2000 millicore limit, no GPU limits, node selector, tolerations or runtime class, and the ephemeral cache

## Scenario: Contradictory deployment limits stop the satellite at start
**Given** configurations with a CPU minimum above its maximum, a default memory value missing from the memory values, an empty list of GPU resource names with GPUs offered, and a memory value that is not a Kubernetes quantity
**When** the satellite starts with each
**Then** it exits before pairing with a message naming the offending value

## Scenario: Tightened limits leave running deployments alone
**Given** an active deployment stored with 8000 millicores and one stored with use-GPU true, and a satellite restarted with a CPU maximum of 4000 and GPUs no longer offered
**When** reconciliation and the health pass run, and each workload later stops and is relaunched
**Then** reconciliation logs one warning per deployment naming CPU and use-GPU respectively, both keep running and stay active with their workloads untouched, and each relaunch leaves its record not responding with "Invalid deployment settings" naming the field in the error, without calling the driver

## Scenario: Shared cache without a claim fails at once
**Given** a deployment choosing the shared artifact cache on a satellite with no shared cache claim configured
**When** the deploy task runs
**Then** start answers failed naming the missing shared cache, no object is applied, and the deployment fails without waiting for the deadline

## Scenario: Two Kubernetes satellites share a namespace
**Given** two releases with different names in one namespace of the in-memory API, each with one deployment's objects, and the chart rendered for both releases
**When** each driver lists workloads, observes in bulk and reconciles, and the two renderings are compared
**Then** each driver answers the other's workload as not owned, bulk observe answers only its own, neither removes the other's, no rendered object name is shared, and each network policy selects only its own release's pods

## Scenario: A repeated start with changed settings re-applies them
**Given** a Kubernetes deployment started with one replica
**When** start is called again for it with three replicas
**Then** the same four objects are updated in place, the Deployment has three replicas, and no object is duplicated

## Scenario: OpenShift preset pins no user
**Given** the OpenShift preset
**When** the manifests and the chart render
**Then** no pod sets a user or file-system group

## Scenario: Kubernetes driver maps pod states
**Given** an in-memory API answering, in turn: one available replica; one available replica next to a crash-looping pod; a pod in image-pull back-off; a pending pod with an insufficient-GPU message; an init container that exited with 1 and is being restarted; an init container in crash-loop back-off; no Deployment
**When** observe runs for each
**Then** the answers are ready; ready again; failed with the back-off state and message as the error, plus logs; starting with the GPU message in the note; starting; failed with the init container's logs; missing

## Scenario: Kubernetes driver observes in bulk and verifies removal
**Given** five deployments in the in-memory API
**When** bulk observe runs, and then remove runs for one
**Then** exactly two list calls are made, remove answers verified only after the Deployment is gone, and it answers unverified when the objects outlive its poll

## Scenario: A reissued satellite token leaves the model pods untouched
**Given** two owned, active Deployments rendered under a derivation key, and a satellite restarted with a new satellite token and the same derivation key
**When** reconciliation runs and a sidecar calls the companion API with the companion token it already holds
**Then** observe reports neither as needing re-applying, start is not called, the Secrets and the secret-hash annotations are unchanged, no pod rolls, the companion API accepts the token, and the records stay active throughout

## Scenario: Derivation key rotation rolls the model pods
**Given** two owned Deployments whose fingerprint label differs from the current derivation key's
**When** reconciliation runs
**Then** observe reports both as needing re-applying, start is called for both with no recovering marker written, the re-rendered Secrets carry tokens derived from the new derivation key, the secret-hash annotation changes, both deployments are tracked while their pods roll so the health pass leaves them alone, they are adopted once ready and healthy, and the records stay active throughout

## Scenario: Artifact init container uses the cache and refreshes an expired link
**Given** an empty cache, a link answering 403, and a satellite artifact route answering a working link
**When** the fetch program runs twice
**Then** the first run asks the satellite once, unpacks into the artifact's directory and leaves no partial file; the second exits 0 with no HTTP call; and the model server started afterwards logs that it uses the cached model

## Scenario: Artifact sweep keeps only listed artifacts
**Given** a cache with three artifacts and a stale partial file
**When** the fetch program runs in sweep mode keeping one
**Then** the other two and the partial file are removed

## Scenario: Only one satellite copy polls
**Given** the chart rendered with its defaults, and separately a satellite pod starting against the fake platform
**When** the satellite Deployment is parsed, and the pod's platform calls are recorded
**Then** the Deployment has one replica with the recreate strategy, and the new pod reconciles before its first poll

## Scenario: Ingress is standard and routes by path
**Given** the chart rendered for a host plus a rendered deployment Ingress
**When** the objects are parsed
**Then** every Ingress is the standard networking API, no Route objects exist, `/monitoring` and `/deployments/<id>/monitoring` go to the dashboard, `/deployments/<id>` goes to the deployment's `http` port, `/` goes to the satellite's `http` port, and no rule targets the internal port

## Scenario: Base URL scheme follows TLS
**Given** the chart rendered without TLS, and separately with a TLS secret, and separately with the OpenShift preset and no TLS secret
**When** the satellite's environment is read
**Then** the base URL starts with `http://` in the first case and with `https://` in the other two

## Scenario: Images run as an arbitrary user
**Given** the four images
**When** each runs as a random high user in group 0
**Then** the satellite and sidecar answer their liveness route, the monitoring image imports the monitoring extra, and the model server unpacks a synthetic archive under `/app/models` and, when a loadable model artifact and network access are available, creates its micromamba environment under `/app`

## Scenario: A fresh named volume is writable by the model server
**Given** the model server image and one empty named volume mounted at `/app/models`
**When** the image runs twice as a random user in group 0 with the same synthetic archive
**Then** the first run unpacks the artifact into the volume without permission errors and the second run reuses it

## Scenario: kind end-to-end passes on both presets
**Given** the CI kind cluster with the fake platform, the stub model server and the chart
**When** the end-to-end suite runs
**Then** every assertion listed in the Kubernetes satellite section passes on the vanilla and the OpenShift leg

## Scenario: Chart and images are published
**Given** release tags for the Kubernetes satellite and the chart
**When** the workflows run
**Then** the versioned image and the versioned chart exist in the registry, and a push to main publishes only the branch-tagged images

# Tasks

- [x] Add the satellite kit skeleton and wire contract tier
  - [x] Create `satellite/kit/` as a uv project (hatchling, extras, dev group, ruff and strict mypy targeting 3.14, pytest, dependency ranges with today's pins as lower bounds) with a short README
  - [x] Port the deployment, task and monitoring-introspection schemas from `satellite/agent/schemas/` (the dashboard query schemas in `monitoring_query.py` are ported with the monitoring code) and `satellite/agent/clients/platform_client.py` into the wire contract tier, with the new fields, the pairing and contract calls, the error families and the legacy-address message
  - [x] Add the token derivation and the contract comparison
  - [x] Add the fake platform (every satellite route with the backend's status codes, a legacy mode, transition recording, artifact bytes, a runner for out-of-process use) and copy the model-server mock fixture from `satellite/tests/conftest.py`
  - [x] Tests: every client call, update bodies, error mapping, the legacy 422 and another pairing 422 logged with its detail, isolation between two clients, contract verdicts including parameter normalisation, token compatibility with today's artifact tokens when no derivation key is configured, derived tokens and the fingerprint unchanged by a new satellite token under a configured derivation key, separation between token purposes, the no-extras import test over the modules that exist so far
  - [x] Add a kit lint-and-test workflow

- [x] Add the kit declaration tier
  - [x] Implement the settings model with field derivation (including defaults, `field` and `model` conditions, nested groups and the whole validator set with messages), parsing that ignores conditions, and rejection of non-scalar and float fields and of conditions naming an undeclared setting
  - [x] Implement capability derivation and the capability diff, pairing, and the configuration object with today's variables and the new ones; introduce the capability-facing part of the monitoring bundle contract that capability derivation reads, with a fake bundle among the test doubles
  - [x] Tests: each field type against today's field shape, defaults, unexposed fields, every condition type and operator including model conditions and nested groups, every validator type with its message, a condition naming an undeclared setting, parsing that ignores conditions, parsing errors, unknown keys, derivation reproducing today's Docker declaration against the fake bundle (port only the declaration cases of `satellite/tests/unit/test_capabilities.py`; its registry-driven cases move to the monitoring bundle task and its pairing-document case to the Docker satellite task), diff lines, pairing sending the kit object and tolerating a missing contract, two configurations coexisting

- [ ] Add the kit workload tier
  - [ ] Implement the driver contract and its value types, the blocking-wait helper, the artifact resolver for the three modes, the recording contract and policy, and the status transition table with today's marker strings
  - [ ] Implement the container vocabulary: resources, label sets, the environment builder, and the fetch program with caching, staging, one link refresh and sweep mode
  - [ ] Implement the fake driver and the driver conformance suite
  - [ ] Tests: port `test_deployment_metadata.py` from `satellite/tests/unit/`; the artifact resolver and artifact token verification; environment precedence, reserved names and the absent satellite address; the wait helper with a fake clock; every allowed and forbidden transition; fetch cache hit on an existing artifact directory, miss, 403 refresh, sweep and no leftover partial files; conformance against the fake driver, including that verified is never claimed without a re-check; extend the no-extras import test

- [ ] Add kit task convergence and the polling pass
  - [ ] Implement the serving placement contract with the no-serving placement, and convergence of tasks: deploy with its failure reasons, finalize, the revisit of in-progress entries under the deadline, cleanup on failure, undeploy superseding an in-progress deploy, the reconcile task, note truncation and tolerated informational updates
  - [ ] Implement the polling pass: task parsing, unknown and custom types, in-flight tracking, the concurrency bound per runtime instance, per-deployment locks and drain
  - [ ] Add a scripted deploy case with its expected status sequence to the test doubles, for satellite suites to run with their own driver
  - [ ] Tests with the fake platform, fake driver and a fake clock: parallel and serial convergence, revisit with notes, the deadline for starting, ready but unhealthy and unknown, cleanup with unregistering and only once start was called, the log sizes in errors, the note cleared on a failed outcome, invalid settings, unreadable secret, unavailable artifact, a start answering failed or raising with and without a driver-supplied reason, finalize failure before and after the active patch, an unreadable description part recorded as none, every undeploy outcome, an undeploy arriving during a start, transitions refused by the kit after re-reading the record and by the platform, a record found gone on the re-read and a re-read failing otherwise, the reconcile task (port `test_reconcile_task.py`), unknown and custom types, a custom task without a deployment id, a hung driver call bounded by the driver call timeout, a provider-style fake driver with the no-serving placement, driving convergence without the runtime; extend the no-extras import test

- [ ] Add kit reconciliation, health pass and runtime loop
  - [ ] Implement relaunching (marker first, its failure paths, the attempt budget per runtime instance), the health pass, reconciliation at start (the state table's reconciliation column, the launcher protocol rule, re-applying with its tracking, task resumption, orphans, sweep) and the runtime with its loop
  - [ ] Tests with the same doubles: every reconciliation branch (port the expectations of `test_deploy_task.py` and `test_container_relaunch.py` except where this Design states a different behaviour), every cell of the state table, a failed marker write, a start failure during a relaunch, the relaunch budget, its reset after a successful relaunch and after adoption, a failed marker write not counting as an attempt, the last update once the budget is spent, the serving registration kept while not responding, the marker rule in health passes, a health pass adopting and registering an unregistered deployment, a finalize failure outside a deploy task retried on the next pass, bulk observe preferred, the unknown state at reconciliation, re-applying without a status change and tracked until adopted, in the health pass too, a failed re-apply start retried without touching the budget, a workload with an absent or different launcher protocol relaunched, a driver answering its own declared protocol never relaunched for it, resumption per task type and record state, a resumed deploy that starts again with a fresh deadline, running tasks that do not parse or are of an unknown or custom type, a workload without a deployment id never removed, reconcile-before-poll order with no HTTP application, backoff and the 401 message, pairing retry, two runtimes in one process; extend the no-extras import test

- [ ] Copy monitoring into the kit as an extra
  - [ ] Copy `satellite/agent/monitoring/` and the dashboard query schemas in `satellite/agent/schemas/monitoring_query.py` into ingest, storage, compute and dashboard with behaviour unchanged and passing strict mypy, with the feature list next to the registry; leave `satellite/agent/monitoring/`, its tests and its checked-in static assets in place until the cut-over
  - [ ] Copy the checked-in static assets into the kit so the copied embedding test finds the dashboard bundle; the next task replaces them with the rebuilt bundle
  - [ ] Tests: copy the monitoring tests into the kit with the same assertions, from both places they live in: the directory `satellite/tests/unit/monitoring/` and the top-level files `test_monitoring_worker.py`, `test_monitoring_data_quality.py`, `test_monitoring_feature_drift.py`, `test_monitoring_output_drift.py`, `test_monitoring_multivariate_drift.py`, `test_greptime_store.py`, `test_runtime_health.py` and `test_telemetry_setup.py` in `satellite/tests/unit/`

- [ ] Add the monitoring bundle, authorizer and recording policy
  - [ ] Add the authorizer contract and the platform-backed authorizer to the core
  - [ ] Add per-instance worker health, the recording contract implemented by the instrumentation, the recording policy in ingest, the store credentials and the bundle in its all-in-one role, which implements the bundle contract from the declaration task
  - [ ] Repoint the monitoring UI build output into the kit, rebuild and commit the built bundle in place of the copied assets, without touching the old agent's checked-in static assets
  - [ ] Tests: the platform-backed authorizer with its cache and its unavailable answer, per-instance worker health, the recording policy, the vendor store, bundle wiring, and the registry-driven cases of `satellite/tests/unit/test_capabilities.py` against the real bundle

- [ ] Add stateless sessions and split monitoring processes
  - [ ] Add signed sessions, heartbeat storage and file, the deployment sources, worker shards, the bundle's split roles, and the worker and dashboard executables with their probes
  - [ ] Add the monitoring Dockerfile and its publish workflow
  - [ ] Tests: the dashboard application's `unknown_route` body on an unknown path under a deployment's monitoring prefix and the plain 404 under `/monitoring`, the split-mode worker answer carrying the fields the API client requires, session replica, tamper and cap tests, query requests alone sliding the session, split worker and dashboard with the heartbeat's per-deployment fields and the probe, shards with their heartbeats merged, platform source caching and token

- [ ] Add the kit serving extra with the in-process placement
  - [ ] Implement the serving application (the route table, bearer on inference-access, the 403 for a missing bearer, the two caps, an event for every call of a monitored deployment and none otherwise, the 45 s upstream timeout, error mapping with the upstream error envelope, per-deployment schema, the starting gate, single-deployment and not-hosted modes), the internal application with the artifact route, and the in-process placement
  - [ ] Tests: the `unknown_route` body on an unmatched path; port `test_artifact_endpoint.py` and `test_reference_profile.py` from `satellite/tests/unit/`, the compute cases of `test_inference_instrumentation.py` and the inference parts of `test_monitoring_flag.py` using the copied mock fixture; the application's own OpenAPI entries, leaving the full snapshot test to the Docker satellite task; secret injection, sampling and both caps with an event for every call of a monitored deployment, no event and no event id header with monitoring off or the no-op recorder, the trace-context header sent upstream, streaming without buffering, error mapping including the upstream error envelope and the 422 for a parsed request body that is not JSON and the upstream's answer for one forwarded unparsed, the 403 for a missing bearer, the platform-backed secret source's cache, the starting gate with its gated routes and the ungated ones that exist so far, the liveness route

- [ ] Add the companion placement, sidecar and serving image
  - [ ] Implement the companion placement, the companion API, the companion-backed authorizer and secret source, and the sidecar executable with its start-up order and its refresh of metadata and secrets
  - [ ] Add the serving Dockerfile (3.14, both extras, non-root) and its publish workflow
  - [ ] Tests: the companion cache timeline, a 403 or 404 from the companion API served from the stale cache and never cached as a denial, companion API refusals, sidecar boot with the satellite down and with the deployment not yet registered, a monitoring mode change reaching the sidecar within one TTL, recorder selection and policy precedence, the trace-context header reaching the upstream through the sidecar, the internal port guard, the companion API left ungated by the starting gate

- [ ] Extend the satellite contract in the backend
  - [ ] The next migration with the guarded downgrade and the ORM changes in `backend/luml/models/deployment.py` and `backend/luml/models/satellite.py`
  - [ ] Capability schemas keeping unknown fields, the optional pairing address, the kit object and its storage, the new deployment fields with limits, in `backend/luml/schemas/` and `backend/luml/handlers/satellites.py`
  - [ ] The launch base resolution, the launch URL, the new ineligibility reason and the 409 for minting without a base in `backend/luml/schemas/monitoring.py` and `backend/luml/handlers/monitoring.py`
  - [ ] Verification of satellite parameters against the declared field list at deployment creation, in `backend/luml/handlers/deployments.py`, with condition evaluation matching `frontend/src/hooks/satellites/useSatelliteFields.ts`, and the shared condition case file under `backend/tests/` covering every condition type, operator and nested group with matching and non-matching values and manifests
  - [ ] The public contract route in `backend/luml/api/satellites.py`, included in the service
  - [ ] Tests under `backend/tests/` for every backend scenario and the migration, with the parameter verification run over every shared condition case; mypy, ruff and pytest pass

- [ ] Show the new satellite contract fields in the frontend
  - [ ] Update the satellite, deployment and monitoring interfaces, the monitoring store, the monitoring page copy, the schema page and its OpenAPI component, the settings form default seeding and validator, the deployments table, the deployment editor and the satellites card under `frontend/src/`
  - [ ] Tests: the monitoring store (launch URL, fallback, null), the monitoring page reason, the schema page's three cases, the editor and table with old fixtures unchanged, the settings form with the GPU fixture, the field hook run over every shared condition case read from `backend/tests/`, defaults submitting untouched and an old declaration unchanged; type-check, lint and the CI test run pass

- [ ] Rebuild the Docker satellite on the kit
  - [ ] Create `satellite/implementations/docker/` as a uv project with the kit as path dependency and aiodocker, the driver, the settings, the configuration, the main module and a Dockerfile with the `satellite/` context
  - [ ] Port the behavioural suite from `satellite/tests/`, including the pairing-document case of `test_capabilities.py`, with the regenerated snapshot and every difference this Design states asserted; add the driver conformance suite against the Docker driver, the observe mapping with its catch-all state, the kit's scripted deploy case, the one relaunch that gives an old-agent container the satellite-id label and its plain adoption at the next start, two satellites on one daemon leaving each other's containers and an unlabelled one of an unknown deployment alone, protocol relaunch, parallel deploys, a resumed deploy, verified removal, failed-container removal, the network name override, and a main smoke test against the fake platform
  - [ ] Add a Docker satellite lint-and-test workflow

- [ ] Run the model server as non-root with its own test suite
  - [ ] Move `satellite/model_server/` to `model_servers/default/` and repoint the model server publish workflow's path filter and build context, the model image's build context in `satellite/docker-compose.yml` and the old satellite project's and workflow's lint targets, keeping the image name and the release tag pattern
  - [ ] Update `model_servers/default/Dockerfile` (home, micromamba root and uv cache under `/app`, group-writable, `/app/models` pre-created for user 10001 and group 0 and group-writable, user 10001) and add a dev dependency group with pytest and mypy, the pytest configuration and a non-strict mypy configuration to its project, fixing the type errors it reports with type-only edits
  - [ ] Move `test_model_env_setup.py`, `test_model_artifact_resolution.py` and `test_model_server_telemetry.py` from `satellite/tests/unit/` into `model_servers/default/tests/` with a local span exporter helper; add a model-server workflow running lint, mypy and the tests
  - [ ] Tests: the moved suite passes; an integration test (skipped without Docker) runs the image as a random user against a synthetic archive built by the test and checks unpacking and ownership under `/app/models`, needing no network; the health-route and micromamba-location checks need a loadable model artifact supplied by the environment and network access, and are skipped and reported as not run otherwise; a second Docker-only test, skipped without Docker, runs the image twice as a random user against one empty named volume mounted at `/app/models` and checks that the first run writes it and the second reuses it without permission errors

- [ ] Cut the Docker satellite over to the kit build
  - [ ] Repoint `satellite/docker-compose.yml`, the satellite image publish workflow and the SDK's monitoring contract test, which keeps passing without any change to the client's operations; replace the satellite workflow with the per-package ones
  - [ ] Before deleting, check that every file under `satellite/tests/` has a ported counterpart or a stated reason for removal, including `test_container_inspection.py` and `test_undeploy_cache_cleanup.py`, which no other task names
  - [ ] Delete `satellite/agent/` with its monitoring code and checked-in static assets, `satellite/tests/`, `satellite/pyproject.toml`, `satellite/uv.lock`, `satellite/Dockerfile` and `satellite/__init__.py`; `satellite/.env.example`, `satellite/otel-collector-config.yaml`, `satellite/docker-compose.yml` and `satellite/README.md` stay
  - [ ] Verify with the automated smoke test and the SDK contract test; run the compose walk-through against `dev/docker-compose.yml` (pair, deploy, compute with an event id, dashboard launch, undeploy) only when Docker and a platform are available, and report it as not run otherwise

- [ ] Add the Kubernetes satellite package
  - [ ] Create `satellite/implementations/kubernetes/` as a uv project with the kit and the asynchronous Kubernetes client, the settings, the configuration, the manifests, the API wrapper with an in-memory double, the driver, the main module and a non-root Dockerfile
  - [ ] Tests: the settings model built from configuration (default limits, a small cluster without GPUs or a shared cache, a single-value dropdown not offered, every contradiction stopping the start, the warning for stored parameters outside tightened limits); golden manifests (defaults without GPU, GPU, shared cache, replicas, monitoring paths on and off, both presets, secret placement per container, the model container's reserved variables including the telemetry endpoint, fingerprint label, a secret hash that ignores a fresh artifact link and a reissued satellite token and changes with a rotated derivation key), the driver against the in-memory API (every observe state including ready winning over a failing pod and an init container failing only in crash-loop back-off, bulk observe call count, idempotent apply, a repeated start with changed settings updating the objects in place, two releases in one namespace kept apart in listing and bulk observe, the re-applying signal on a stale fingerprint, verified and unverified removal, start failing at once for the shared cache without a claim, owned, shared and foreign listing), the conformance suite, the kit's scripted deploy case, the import-boundary test, the settings field snapshot, a main composition smoke test
  - [ ] Replace the frontend's GPU settings fixture with the package's settings field snapshot, taken from the default limits with GPUs offered, so the two cannot diverge
  - [ ] Add a Kubernetes satellite lint-and-test workflow and its image publish workflow

- [ ] Add the Kubernetes satellite Helm chart
  - [ ] Write the chart under `satellite/implementations/kubernetes/chart/`: values, the OpenShift values file, CI values for both presets, every template listed in the Kubernetes satellite section, the notes and the README
  - [ ] Chart unit tests: the deployment limits and the GPU values reaching the satellite's configuration, GPUs not offered by default, both presets, restricted security fields on every pod, no Route, Ingress host and paths and no internal target, one replica with recreate, the standalone, standalone with object storage, and external store modes and the collector configuration with its database name, the existing-secret path, the generated derivation key kept across upgrades and mounted into the satellite, dashboard and worker pods, the checksum annotation over the token and derivation key secrets on those pods, the cache claim with access modes, the base URL scheme including the OpenShift preset, the label-scoped default-deny network policy with the model pods' external egress, two releases in one namespace sharing no object name and each policy selecting only its own release's pods, external store mode changing only the store workload with its Service and volume, the store credentials, the network-policy egress rule, the kit's store settings and the collector configuration; chart lint and unit tests run in the Kubernetes workflow
  - [ ] Add the chart publish workflow

- [ ] Add the Kubernetes e2e on kind and the release checklist
  - [ ] Add the stub model server to the kit's test doubles with a Dockerfile for the stub model image, the fixture artifact, and the end-to-end scripts and test covering the assertions listed in the Kubernetes satellite section, run with the network policy enabled on a kind cluster whose network plugin enforces it
  - [ ] Add the end-to-end workflow with the vanilla and OpenShift legs, triggered on kit, Kubernetes satellite and model server changes and on demand; its OpenShift leg owns the arbitrary-user check for the serving, monitoring and Kubernetes satellite images
  - [ ] Write `satellite/implementations/kubernetes/RELEASE_CHECKLIST.md`
