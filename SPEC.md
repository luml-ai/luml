---
sidebar_label: Satellite Monitoring UI & Query API Spec
title: Satellite Monitoring UI & Frontend Integration Spec
---

# Proposals

## Problem

Part 1 makes the Satellite collect raw inference data locally. Part 2 turns that data
into monitoring metrics, drift, and alert state, materialized into `monitoring_results`
and `monitoring_alerts` in GreptimeDB. But as of those two slices nothing exposes any of
it to a human: the metrics sit in GreptimeDB with no dashboard to render them, no Query
API to read them, and no entry point from the Platform to open monitoring for a
deployment. The whole point of collecting and computing monitoring — seeing that a model
is degrading — does not yet exist for the user. This slice is what adds that read path
(the embedded dashboard below is the solution, not something that already exists).

This spec is the **third slice** of the Live Monitoring architecture: the read path.
It covers everything between the metrics that part 2 stores and a person looking at
them:

- a **Satellite Monitoring Query API** that reads part 2's results and returns
  chart-ready data (never raw rows through the Platform);
- a **Satellite-hosted Monitoring UI** (the dashboard) that renders those views;
- the **Platform integration** that lets a user open that dashboard from a deployment —
  a Monitoring tab, a short-lived launch token, and an embedded iframe.

## Solution at a glance

The dashboard is **owned and served by the Satellite** and embedded in the Platform
through an **iframe**. Raw inputs, outputs, traces, and logs never leave the Satellite;
the Platform only navigates, authorizes, and frames.

Four pieces:

- **Platform Monitoring tab.** The deployment detail area gets a Monitoring tab whose
  **entire content is the iframe** — the Platform renders no monitoring chrome of its
  own. When a user with deployment access opens it, the Platform mints a **short-lived,
  single-use, deployment-scoped `monitoring:read` launch token** and renders an iframe
  pointing at the Satellite's monitoring launch URL. Everything monitoring-specific seen
  in the design — the deployment header, the Window toggle, and the Overview / Data
  quality / Feature drift sub-tabs — is served by the Satellite inside that iframe. If
  monitoring is `off` or the Satellite lacks the
  monitoring capability, the tab shows a disabled state; if the Satellite is unreachable,
  an unavailable state.
- **Satellite launch & session.** The Satellite validates the launch token with the
  Platform, exchanges it for a **short-lived dashboard session** scoped to that one
  deployment, cleans the token out of the URL, and serves the dashboard SPA. Every
  subsequent API call is authorized by the session and enforced to that deployment.
- **Satellite Monitoring Query API.** A read-only API on the Satellite that reads
  `monitoring_results`, `monitoring_alerts`, and (locally only) `inference_events`, and
  returns **chart-ready cards, series, distributions, tables, and alerts** for the
  authorized deployment. It hides GreptimeDB and the physical schema. The views in this
  slice — runtime health, data quality, and feature drift — are **task-agnostic**, so
  they serve any classical-ML deployment as-is.
- **Satellite Monitoring UI.** The dashboard SPA the Satellite serves into the iframe.
  A single shell — header, global controls, and tabs (**Overview, Data quality, Feature
  drift**). **Read-only** in this slice.

Out of scope: the **Prediction (output) drift** and **Performance** tabs and their
task-specific views (deferred to a later slice, along with realized performance and the
targets work); LLM observability (traces/token/cost/judge/scorers); the
connect-monitoring wizard; and any write operations (target upload, alert
acknowledge/resolve).

## Why this approach

- **Iframe, Satellite-hosted, matches the source decisions.** spec_full is explicit:
  monitoring is a Satellite-owned capability, the dashboard is served by the Satellite
  and embedded through an iframe, and no raw monitoring data passes through the Platform.
  Keeping the UI and its API on the Satellite means raw IO and local traces stay local
  by construction — the Query API returns only aggregates, and the one place raw rows
  appear (the Traces panel) is served by the Satellite directly into the iframe, never
  proxied by the Platform.
- **It reuses parts 1 and 2 as its only source.** The Query API reads what part 2
  already materialized; no new collection or computation is added here.
- **A launch token, not an API key.** A browser iframe must not assume or mint a
  long-lived inference API key. A short-lived, deployment-scoped, read-only token
  exchanged immediately for a session is the right credential for a read-only dashboard
  and keeps the existing deployment-permission model as the gate.
- **Task-agnostic views first.** The three tabs in this slice — runtime health, data
  quality, and feature drift — are the same for any classical-ML task, so the dashboard
  works across regression and classification without task-specific code. The
  task-specific views (prediction/output drift and performance) are deferred to a later
  slice, where they can be added as adapters selected by the deployment's `task_type`
  without changing this shell.

# Design

## Scope

In scope:

- Platform: a per-deployment **Monitoring tab**, the **launch-token** mint + permission
  check, the **iframe embed**, and the disabled / unavailable / loading states.
- Satellite: **launch-token validation**, **dashboard-session** exchange, URL cleaning,
  **CSP** frame embedding restricted to Platform origins, and **static hosting** of the
  Monitoring UI.
- Satellite: the **Monitoring Query API** (read-only, session-scoped, deployment-scoped)
  with chart-ready contracts for the three task-agnostic views.
- Satellite: the **Monitoring UI** SPA — header, global controls, and the three tabs
  (Overview, Data quality, Feature drift), read-only, with empty/error/placeholder states.

Out of scope: the **Prediction (output) drift** and **Performance** tabs and their
task-specific views, and their Query API endpoints (deferred to a later slice); realized
performance computation and the targets work (deferred); LLM observability and everything
under it (traces-as-LLM, token/cost, LLM-as-judge, scorers); the connect-monitoring
wizard and monitor management; all write operations (target upload/import, alert
acknowledge/resolve); producing `monitoring_results` / `monitoring_alerts` (part 2 owns
that); the reference profile generation (SDK).

## Building on parts 1 and 2

This slice reads what the earlier slices produced and does not re-add any of it:

- **Part 1** established the Satellite Agent as a **FastAPI** service, local telemetry
  through an OpenTelemetry Collector into **GreptimeDB**, the `inference_events` trace
  table (per-request `event_id`, `deployment_id`, `status`, `status_code`, `latency_ms`,
  `trace_id` / `span_id`, and `inputs` / `output` as JSON strings), the runtime metric
  tables, `otel_traces`, and the per-deployment `monitoring_enabled` flag plus the
  monitoring **capability** advertised to the Platform.
- **Part 2** added the shared Monitoring Worker and two read-ready datasets in
  GreptimeDB: **`monitoring_results`** (per deployment, metric group, window: `values`,
  `severity`, `profile_status`) and **`monitoring_alerts`** (per deployment and metric:
  `current_value`, `threshold`, `severity`, `state`, `first_seen` / `last_seen`). It
  also loads the **reference profile** on the deploy path and keeps it per deployment.
- **Platform** models deployments (`backend/luml/models/deployment.py`,
  `backend/luml/api/orbits/orbit_deployments.py`) with `satellite_id`, `inference_url`,
  `status`, `schemas`; and satellites (`backend/luml/models/satellite.py`) with
  `base_url` and a `capabilities` JSONB. The **Platform frontend** is Vue 3 + PrimeVue +
  Pinia + vue-router with ApexCharts/Plotly, API modules under `frontend/src/lib/api`,
  and stores under `frontend/src/stores`.

The Query API's inputs are therefore: `monitoring_results` and `monitoring_alerts` for
computed metrics/drift/alerts, `inference_events` for runtime rollups and the local
Traces panel, and the loaded reference profile for the Reference profile view.

## Architecture and the launch flow

```
Platform (Vue)                         Satellite (FastAPI, served locally)
──────────────                         ───────────────────────────────────
Deployment detail
  └─ Monitoring tab
       │ 1. user opens tab
       │ 2. Platform checks deployment access
       │ 3. Platform mints launch token
       │    (short-lived, single-use, deployment+satellite+user scoped, monitoring:read)
       └─ <iframe src="{satellite.base_url}/monitoring/launch?token=…">
                                        │ 4. Satellite validates token via Platform introspection
                                        │ 5. Satellite issues dashboard session (deployment-scoped)
                                        │ 6. Satellite redirects to clean /monitoring/app (no token)
                                        └─ serves Monitoring UI SPA
                                                 │ 7. SPA calls Query API same-origin (session)
                                                 └─ Query API reads GreptimeDB, returns chart-ready data
```

No raw monitoring data passes through the Platform at any step. The token appears once in
the launch URL and is removed by the redirect after exchange.

## Platform: launch token and Monitoring tab

### Permission and eligibility

The Platform reuses the **existing deployment-access permission** as the gate — the same
check that authorizes viewing the deployment. A user who cannot see the deployment cannot
mint a token.

The Monitoring tab has three non-active states, decided by the Platform before any iframe
loads:

- **Disabled** — the deployment's monitoring mode is `off`, or the target Satellite does
  not advertise the monitoring capability. The tab renders a disabled explanation and no
  iframe.
- **Unavailable** — monitoring is enabled and advertised, but the Satellite's monitoring
  URL cannot be reached (or the launch/exchange fails). The tab renders a clear
  unavailable state and does not fall back to proxying data.
- **Active** — a launch token is minted and the iframe is rendered.

### Launch token

On opening the active tab, the Platform mints a launch token with these properties
(spec_full "Dashboard Authorization"):

- short-lived (minutes), **single-use**;
- scoped to one **user**, one **deployment**, one **Satellite**;
- **read-only**, limited to `monitoring:read`;
- **not** an inference credential and **not** persisted as a user API key.

Token claims carry at least: `deployment_id`, `satellite_id`, `user_id`, `scope =
monitoring:read`, `exp`, and a unique `jti` for single-use tracking.

### Token validation (introspection)

The Satellite validates the token by **calling a Platform introspection endpoint**
(`POST` the token, receive validity + claims), rather than verifying a signature locally.
Rationale: the Satellite already calls the Platform for tasks and inference-credential
checks, so this reuses an established direction; and single-use is enforced naturally —
the Platform marks the `jti` consumed on first introspection and rejects reuse. The
trade-off is one network round trip at launch, which is acceptable because it happens
once per dashboard open, not per API call.

### Platform frontend

- A **deployment detail context** with a Monitoring tab. The design's breadcrumb is
  `org / orbit / Deployments / Monitoring`; the tab lives in the deployment's detail area
  (a new detail route/view keyed by `deploymentId`, alongside the existing
  `deployment-schema` route). It reuses only the Platform outer shell (sidebar, top
  breadcrumb).
- **The whole Monitoring tab content is the iframe.** The Platform renders no
  monitoring-specific chrome — the deployment header, Window toggle, and the
  Overview / Data quality / Feature drift sub-tabs from the design are all rendered by the
  Satellite-served dashboard inside the iframe, not by the Platform. The Platform's
  monitoring view is essentially: eligibility check → token mint → full-bleed iframe
  (plus the non-active states).
- The Monitoring view: resolves eligibility, mints the token via a new Platform API
  module (`frontend/src/lib/api`) + store, and renders a full-bleed `<iframe>` at
  `{satellite.base_url}/monitoring/launch?token=…` filling the tab. It shows loading,
  disabled, and unavailable states, and surfaces a re-launch action if the session
  expires.

## Satellite: launch, session, and embedding

- **`GET /monitoring/launch?token=…`** — validates the token via Platform introspection;
  on success issues a **dashboard session** and **redirects** to a clean dashboard URL
  (e.g. `/monitoring/app`) with no token in it; on failure returns an unavailable/denied
  response the Platform can render.
- **Dashboard session** — a short-lived (e.g. 30 min) credential scoped to exactly one
  `deployment_id` and `monitoring:read`, delivered as an **httpOnly, SameSite session
  cookie** scoped to the monitoring UI path. Because the SPA and the Query API are the
  same Satellite origin, the SPA's API calls carry the cookie automatically; the browser
  never holds a bearer token. Session expiry surfaces to the SPA as `401`, which the SPA
  reports so the Platform can re-launch.
- **Deployment scope** — every Query API request derives its `deployment_id` from the
  session, never from a client-supplied parameter. A session for deployment A cannot read
  deployment B.
- **Embedding** — the monitoring responses set **`Content-Security-Policy:
  frame-ancestors`** to the allowed Platform origin(s) only, so the dashboard is
  embeddable only by the Platform. Other framing is refused.
- **Hosting** — the Monitoring UI is a static SPA bundle served by the Agent
  (FastAPI static files) under the monitoring path. It ships with the Satellite install
  and is available whenever the monitoring services run (part 1/2 reconciliation).

## Satellite Monitoring Query API

A read-only API on the Satellite Agent. It **hides GreptimeDB** and returns chart-ready
values. It reads `monitoring_results` / `monitoring_alerts` (part 2), `inference_events`
(part 1) for runtime rollups and the local Traces panel, and the loaded reference
profile. It **never** returns raw rows to anything but the same-origin iframe, and the
Platform never proxies it.

### Common query dimensions

All endpoints accept a shared set of controls (mapped to the dashboard's global
controls):

- **window** — `24h` | `7d` | `30d` (design's Window toggle) or a custom range;
- **granularity** — automatic by default;
- **compare** — against `reference` (default) or `previous` period;
- **severity** filter — all / warning / critical;
- **feature** filter — for feature-scoped views.

`deployment_id` is **not** a parameter — it comes from the session.

### Endpoints (behavioral contracts)

Each returns already-aggregated, render-ready data; the UI does no metric math.

- **Header / context** — deployment name, status, task type, model/artifact name, orbit
  or environment, bound Satellite, last-monitored window, last prediction time, and the
  reference **profile status** (`ready` | `placeholder`).
- **Overview** — the summary **cards** (Requests, Error rate, Latency p95, Active alerts
  with critical count, Drifted features with names), each with its compare-delta; the
  **alert banners** (top open critical alerts with a one-line explanation); the runtime
  **series** (requests over time, error rate over time, latency p95 over time); and **top
  drifted features** (ranked PSI).
- **Runtime** (folded into Overview in the design, but a distinct contract) — request /
  success / error counts, error rate, latency p50 / p95 / max, timeout and failed-inference
  counts, and the runtime alert list, derived from `inference_events` + runtime metric
  tables.
- **Data quality** — the per-feature **table**: missing rate, type-error rate, range /
  unseen-category rate, and per-feature status, from the data-quality result group.
- **Feature drift** — the ranked PSI **list** with per-feature status; per selected
  feature, the **reference-vs-current distribution** and the **PSI-over-time** series;
  the **multivariate (PCA)** panel (reconstruction-error / Mahalanobis-style shift value,
  per-feature-PSI summary, explained variance, and the PC1×PC2 reference-vs-logged
  projection); and the **Reference profile** panel for the selected feature (summary
  statistics, histogram bin edges or category probabilities, computed-at-training
  baseline label).
- **Alerts** — open alerts grouped by metric group (runtime, data quality, feature
  drift), each with current value, threshold, severity, first/last seen, and the related
  metric/feature — **read-only** (no acknowledge/resolve).
- **Traces** (local only) — a paginated **table** of recent inference calls in the window
  from `inference_events` (time, request id, features summary, prediction, latency,
  status). Served only into the same-origin iframe; never proxied by the Platform.

### Missing / partial data

- If the worker has **not yet materialized** a metric group for the window, the endpoint
  returns an explicit "not computed yet" empty shape rather than an error.
- If the reference **profile is placeholder or absent**, responses carry
  `profile_status` so the UI can show a placeholder warning and the profile-dependent
  views degrade rather than error (consistent with part 2's selection).
- If GreptimeDB is unavailable, endpoints return an unavailable status the UI renders as
  a section-level error; inference is unaffected (part 1/2 rule).

## Satellite Monitoring UI (the dashboard SPA)

### Tech and hosting

A small **Vue 3 SPA reusing the Luml design system** (the `_ds/luml-design-system` bundle
referenced by the design export) and **ApexCharts** for charts — the same stack as the
Platform frontend, so components, tokens, and chart idioms are shared rather than
reinvented. It is built to **static assets served by the Agent** and calls the Query API
**same-origin** with the session cookie. Read-only.

### Structure (from the design)

- **Header** — deployment name + status pill; a metadata line (task type · dataset ·
  bound satellite · model version · last prediction); and an Inference URL affordance.
- **Global controls** — the **Window** toggle (24h / 7d / 30d), compare mode, severity
  and feature filters, and manual/auto refresh. Defaults: window 24h, granularity auto,
  compare against reference, severity all.
- **Tabs** (this slice's set): **Overview**, **Data quality**, **Feature drift**. Runtime
  health is surfaced within Overview; alerts appear as Overview banners and inline per
  tab; the reference profile appears as a panel inside Feature drift. Each tab renders
  exactly the corresponding Query API contract above. These three views are task-agnostic;
  the design's Prediction drift and Performance tabs are deferred to a later slice, and
  the tab bar is built so they can slot in without reworking the shell.

### States

- **Loading** — per-section skeletons.
- **Disabled / wrong context** — handled by the Platform (the SPA assumes an active
  session); on `401` the SPA shows a "session expired — reopen from the Platform" state.
- **Placeholder profile** — a persistent warning banner when `profile_status` is
  `placeholder`.
- **No data in window** — per-section empty states when the worker hasn't produced
  results yet.
- **Section error** — per-section error when a contract returns unavailable, without
  taking down the whole dashboard.

## Failure behavior

Consistent with spec_full — inference availability outranks monitoring availability:

| Failure | Dashboard behavior |
| --- | --- |
| Satellite monitoring URL unreachable | Platform tab shows **unavailable**; no data proxied |
| Launch token invalid / expired / reused | Satellite refuses exchange; Platform shows unavailable/denied |
| Dashboard session expired | SPA gets `401`, shows re-launch state |
| GreptimeDB unavailable | Query API returns unavailable; SPA shows section errors |
| Worker hasn't materialized a window | endpoint returns "not computed yet" empty shape |
| Disallowed origin tries to embed | CSP `frame-ancestors` refuses framing |

## Trade-offs and decisions

- **Introspection over local signature verification** for the launch token — reuses the
  existing Satellite→Platform direction and makes single-use trivial, at the cost of one
  round trip per launch.
- **httpOnly session cookie over a bearer token in the SPA** — the SPA and API are
  same-origin on the Satellite, so a path-scoped httpOnly cookie is simpler and keeps no
  credential in JS.
- **A separate Satellite SPA that reuses the design system** rather than rendering the
  dashboard as a Platform page — required by the iframe/Satellite-hosted decision;
  reusing the design system keeps it visually and behaviorally consistent without
  importing the whole Platform app.
- **Task-agnostic views first, task-specific views deferred** — shipping runtime, data
  quality, and feature drift (identical across classical-ML tasks) keeps this slice small
  and immediately useful for any deployment; prediction/output drift and performance,
  which need task-specific layouts and (for performance) the deferred targets, are left to
  a later slice that slots into the same shell.
- **Read-only** — no target upload or alert lifecycle in this slice, matching part 2's
  deferral of targets and keeping the MVP surface small.

# Scenarios

## Scenario: user opens monitoring for a full deployment
**Given** a deployment in `full` mode on a Satellite that advertises the monitoring
capability, and a user with deployment access
**When** the user opens the Monitoring tab
**Then** the Platform mints a single-use `monitoring:read` launch token, the iframe loads
the Satellite launch URL, the Satellite validates the token via introspection, issues a
deployment-scoped session, redirects to a clean dashboard URL without the token, and the
dashboard renders Overview for that deployment.

## Scenario: monitoring is off
**Given** a deployment in `off` mode
**When** the user opens the Monitoring tab
**Then** the tab shows the disabled state, no token is minted, and no iframe loads.

## Scenario: Satellite lacks the monitoring capability
**Given** a deployment whose target Satellite does not advertise the monitoring capability
**When** the user opens the Monitoring tab
**Then** the tab shows the disabled state.

## Scenario: Satellite unreachable
**Given** monitoring is enabled and advertised but the Satellite monitoring URL cannot be
reached
**When** the user opens the Monitoring tab
**Then** the tab shows the unavailable state and no raw data is proxied through the
Platform.

## Scenario: launch token is single-use
**Given** a launch token that has already been exchanged once
**When** the same token is presented to the Satellite launch URL again
**Then** the Platform introspection reports it consumed and the Satellite refuses to issue
a new session.

## Scenario: expired launch token
**Given** a launch token past its expiry
**When** it is presented to the Satellite launch URL
**Then** the exchange is refused and the Platform shows an unavailable/denied state.

## Scenario: deployment scope is enforced
**Given** an active dashboard session scoped to deployment A
**When** a Query API request is made
**Then** the returned data is for deployment A only, derived from the session, regardless
of any client-supplied identifier, and there is no way to read deployment B.

## Scenario: disallowed origin cannot embed
**Given** a page on an origin that is not an allowed Platform origin
**When** it tries to embed the Satellite monitoring URL in an iframe
**Then** the browser refuses framing because of the `frame-ancestors` CSP.

## Scenario: dashboard works for any classical-ML task
**Given** a monitored deployment of any classical-ML task type (e.g. regression or
classification)
**When** the dashboard loads
**Then** the Overview, Data quality, and Feature drift tabs render from the same
task-agnostic contracts without task-specific branching, and no Prediction drift or
Performance tab is present.

## Scenario: placeholder reference profile
**Given** a deployment whose reference profile is `placeholder`
**When** the dashboard loads
**Then** a placeholder warning is shown and profile-dependent views degrade gracefully
rather than erroring.

## Scenario: window control changes the query
**Given** the dashboard is open on the 24h window
**When** the user switches to 7d
**Then** every tab re-queries the Query API for the 7d window and re-renders, without a
full re-launch.

## Scenario: worker has not computed a window yet
**Given** a monitored deployment whose worker has not yet materialized feature drift for
the selected window
**When** the user opens the Feature drift tab
**Then** the tab shows a "not computed yet" empty state rather than an error.

## Scenario: feature drift is critical
**Given** a feature whose materialized PSI for the window is above 0.25 with a critical
alert open
**When** the user opens Overview and Feature drift
**Then** the feature appears in top-drifted features, an Overview alert banner explains it,
and the Feature drift tab shows the critical status with the reference-vs-current
distribution.

## Scenario: local Traces panel stays local
**Given** the dashboard's Traces panel
**When** it loads recent inference calls
**Then** the raw request log is fetched by the SPA directly from the Satellite same-origin
and is never routed through or stored by the Platform.

## Scenario: session expires mid-session
**Given** an open dashboard whose session has expired
**When** the user triggers another query (e.g. changes the window)
**Then** the Query API returns `401` and the SPA shows a "reopen from the Platform" state.

# Tasks

The reference profile, `monitoring_results`, `monitoring_alerts`, `inference_events`, the
`monitoring_enabled` flag, and the monitoring capability are produced by parts 1 and 2 and
are treated here as existing inputs.

- [x] **Task 1 — Platform: launch token mint + introspection**
  - [x] Add a Platform endpoint that, for a deployment the caller may access, mints a
        short-lived, single-use `monitoring:read` launch token scoped to
        `deployment_id` + `satellite_id` + `user_id` (reusing the existing
        deployment-access permission as the gate), near
        `backend/luml/api/orbits/orbit_deployments.py`.
  - [x] Add a Platform introspection endpoint the Satellite calls to validate a token and
        receive its claims, marking the `jti` consumed on first use so reuse is rejected.
  - [x] Expose, for the deployment, whether monitoring is eligible (mode `full` +
        Satellite advertises the monitoring capability) and the Satellite `base_url` for
        the iframe.
  - [x] Tests: token minted only with deployment access; token carries the right scope and
        claims and expires; single-use enforced (second introspection rejected); eligibility
        reflects mode + capability.

- [x] **Task 2 — Platform frontend: deployment detail + Monitoring tab + iframe**
  - [x] Add a deployment detail context/route keyed by `deploymentId` with a Monitoring
        tab (breadcrumb `org / orbit / Deployments / Monitoring`), reusing the Platform
        shell.
  - [x] Add the API module + store to mint the launch token and read eligibility, and
        render a **full-bleed iframe** at `{satellite.base_url}/monitoring/launch?token=…`
        as the tab's entire content — no Platform-rendered monitoring header, window
        toggle, or sub-tabs (all of that is Satellite-served inside the iframe).
  - [x] Implement the disabled (off / no capability), unavailable (Satellite unreachable /
        launch failed), and loading states, plus a re-launch action on session expiry.
  - [x] Tests: disabled state for `off` / missing capability; unavailable state when the
        launch URL fails; active state renders the iframe with a freshly minted token.

- [x] **Task 3 — Satellite: launch validation, dashboard session, embedding, hosting**
  - [x] Add `GET /monitoring/launch` that validates the token via Platform introspection,
        issues a deployment-scoped `monitoring:read` dashboard session as an httpOnly
        path-scoped cookie, and redirects to a clean dashboard URL without the token.
  - [x] Enforce that every monitoring request derives `deployment_id` from the session and
        rejects cross-deployment access; expire the session and return `401` when invalid.
  - [x] Set `Content-Security-Policy: frame-ancestors` to the allowed Platform origin(s)
        on monitoring responses; serve the Monitoring UI static bundle from the Agent.
  - [x] Tests: valid token → session + redirect with no token in URL; invalid/expired/
        reused token refused; session scoped to one deployment (A cannot read B); `401`
        on expired session; framing refused for a disallowed origin.

- [x] **Task 4 — Satellite Query API: header, Overview, Runtime, Data quality**
  - [x] Add read-only, session-scoped endpoints returning chart-ready **header/context**,
        **Overview** (cards, alert banners, runtime series, top drifted features),
        **Runtime** rollups from `inference_events` + runtime metric tables, and the
        **Data quality** per-feature table from `monitoring_results`.
  - [x] Honor the common query dimensions (window, granularity, compare, severity, feature)
        and carry `profile_status`; return "not computed yet" empty shapes when the worker
        has no result for the window.
  - [x] Tests: contracts return aggregated (never raw) values scoped to the session's
        deployment; window/compare/severity change the result; missing results yield the
        empty shape; GreptimeDB unavailable yields an unavailable status, not a crash.

- [ ] **Task 5 — Satellite Query API: Feature drift + Reference profile**
  - [ ] Add the **Feature drift** endpoints (ranked PSI list; per-feature reference-vs-
        current distribution and PSI-over-time; multivariate PCA panel) and the **Reference
        profile** panel contract, from `monitoring_results` and the loaded profile.
  - [ ] Honor the common query dimensions and carry `profile_status`; degrade gracefully
        for a placeholder/absent profile and return the "not computed yet" empty shape when
        the worker has no result for the window.
  - [ ] Tests: feature drift reflects materialized PSI and severity; the PCA panel returns
        its shift/variance/projection values; placeholder profile degrades gracefully;
        missing results yield the empty shape.

- [ ] **Task 6 — Satellite Query API: Alerts + Traces**
  - [ ] Add the read-only **Alerts** endpoint grouped by metric group (runtime, data
        quality, feature drift) from `monitoring_alerts`, and the local **Traces** endpoint
        (paginated recent `inference_events`).
  - [ ] Ensure the Traces endpoint is reachable only via the same-origin session and is
        never exposed for Platform proxying.
  - [ ] Tests: Alerts are read-only and correctly grouped/filtered by severity; Traces
        paginate and are session-scoped.

- [ ] **Task 7 — Satellite Monitoring UI: shell, header, controls, Overview**
  - [ ] Scaffold the Vue 3 SPA reusing the Luml design system and ApexCharts, built to
        static assets served by the Agent, calling the Query API same-origin with the
        session cookie.
  - [ ] Implement the header, global controls (Window 24h/7d/30d, compare, severity/feature
        filters, refresh) with the specified defaults, and the **Overview** tab (cards,
        alert banners, runtime series, top drifted features).
  - [ ] Implement loading skeletons, the placeholder-profile warning, section errors, and
        the `401`/re-launch state.
  - [ ] Tests: Overview renders from the contracts; changing the window re-queries and
        re-renders without re-launch; `401` shows the re-launch state; placeholder warning
        appears when `profile_status` is placeholder.

- [ ] **Task 8 — Satellite Monitoring UI: Data quality + Feature drift**
  - [ ] Implement the **Data quality** table and the **Feature drift** tab (ranked PSI,
        feature detail with reference-vs-current distribution and PSI-over-time,
        multivariate PCA panel, reference profile panel), each rendering its Query API
        contract.
  - [ ] Render per-section empty states when the worker has no results, the placeholder
        warning for a placeholder profile, and the local Traces panel loaded same-origin.
  - [ ] Tests: Data quality and Feature drift render from the contracts across classical-ML
        task types without task-specific branching; empty states render when the worker has
        no results; the PCA panel and reference profile panel render; the Traces panel loads
        same-origin.
