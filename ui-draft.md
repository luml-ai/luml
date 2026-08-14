# Proposals

Build the **lumlflow flow workbench** — the user-facing surface of the flow
runtime that `preplan.md` resolves technically. The requirement source is
`ui-draft.md`: this plan follows the draft's own order (onboarding → left panel
→ canvas → notebook → extras → during the session → after the session →
reopening → errors) and treats each line as something the user must be able to
do. `preplan.md` supplies what is actually behind each surface — the store, the
journal, the daemon API, the kernel — and therefore also supplies the
constraints that force a handful of the draft's items to change shape or wait.

**Problem.** The runtime records everything needed for this UI as facts — cell
versions, per-output content hashes, materializations with cost and provenance,
branches as selection maps, an append-only journal of intent-carrying
transactions — and exposes none of it to a user. The draft describes the surface
that makes an agent-driven, non-linear session legible: what exists right now on
this branch, what the agent just did, what is stale, what the variants produced,
and what broke.

**Solution at a glance.**

- **One screen, two views.** Left: the active branch — its identifier (click for
  all branches and their graph) and its inventory. Center: **canvas** or
  **notebook**, two tabs over the *same* branch slice and the *same* cell cards
  at two densities. That is the draft's layout, and it holds because canvas and
  notebook genuinely differ in one thing only: whether outputs or code get the
  accent.
- **The card is the product.** One card per cell; a tab strip over the assets
  that cell produced; expansion in place; source visible and editable without
  leaving; provenance, timing, and the run/stop/rename/delete ops on every card.
  Draft's "each cell can produce several assets → one card with tabs" is exactly
  the runtime's merged cell/asset model (`preplan.md` §3), so the central
  component needs no reconciling at all.
- **Renderers reuse the attachment previews.** The draft says assets render as
  "each type we have in attachments" plus the native three. `@luml/attachments`
  already ships image, svg, audio, video, text, code, table, pdf, and html
  previews with loading/unsupported/too-big/empty/error states, and it is already
  a frontend dependency — so the renderer registry is that set plus `experiment`,
  `model`, `dataset`, `plot`, `metric`, `note`, with the attachment
  `PreviewStates` machinery reused verbatim for the states.
- **Everything live comes from the journal.** Two channels on the daemon's
  loopback socket: journal transactions with cursor replay, and ephemeral
  `run_id`-scoped log chunks (§12). The draft's "live stream of all updates" is
  a subscription, not polling, and reopening is a replay from a cursor.
- **Every surface has a kernel-free tier.** Previews are always stored and
  always enough to browse (§3, §7). Expanding into a full value, paging a frame,
  or diffing starts a kernel — and the UI says so before it does.
- **Viewing a branch is not switching to it.** The draft requires switching
  branches while the agent works. The v1 runtime has one worktree bound to one
  branch (§6), so the UI splits the verb: reading any branch is a pure store
  read, always available; *checking out* rebinds files and waits on the agent's
  worktree lock.

**Why this shape.** The draft is mostly a faithful projection of the runtime,
which means most of the work is surfacing facts rather than inventing state. The
plan's real content is (a) the card contract, (b) the session lifecycle with its
degraded states enumerated, and (c) the places where the draft names something
the v1 runtime deliberately does not have — each answered in place, with the
nearest real thing, rather than left to be discovered mid-implementation.

Not in v1, argued where they come up: an embedded agent terminal, per-branch
agent orchestration, a datasources registry, a variables panel, whole-flow
upload to LUML, workspace-file browsing.

**Relationship to existing code.** The workbench is designed from the draft and
does not inherit from the prototype routes under `/flow/*` on this branch; those
stay where they are, untouched, as fixture-backed experiments. Reuse is at the
level of shipped building blocks: `@luml/attachments` previews, the tracker's
experiment/model screens as link targets, `RightFullHeightDialog`, the toast and
confirm modules, PrimeVue + Tailwind tokens.

---

# Terminology the draft and the runtime spell differently

Fixing this first, because three of these words appear on screen and the wrong
one teaches the wrong mental model.

| Draft says | Runtime calls it | Consequence for the UI |
|---|---|---|
| notebook (the thing you create and open) | **flow** — a directory with `cells/`, a venv, and a `.lumlflow/` store | "Notebook" is a *view* of a flow, never the unit. You create and open flows; you switch to the notebook view. |
| pairing the agent with the notebook | **agent session registration** (`lumlflow agent exec -- claude`, which sets `LUMLFLOW_ACTOR`) | The UI cannot pair anything itself — the agent runs in the user's terminal. It can hand over the command and then *detect* the registration. |
| cell number | **slug** (the filename sans `.py`), with an internal `uid` | No positional numbers: the graph is non-linear and agents rename constantly. `uid`s never reach the screen (§10's error-vocabulary rule). |
| variables | **params** (declared data) and the **scratch REPL** | Cells run in throwaway namespaces; there are no globals to list (§1). |
| session | **branch** for scope, **journal** for history | "Rerun the whole session" means run this branch's slice to its leaves. |

---

# Design

## 1. Onboarding and getting a session (draft 1–8)

The draft's first eight steps are one flow, and only three of them touch the UI.

**Outside the UI:** open a folder, install lumlflow (tool install — uvx/pipx),
download the flow skill (`extras/skills/`, distributed per §10), start the coding
agent. Documented, linked from the workbench, not wrapped.

**`lumlflow ui`** starts the daemon if needed and opens the browser at the flow
picker. There is no separate UI process to reason about: the daemon serves the
frontend on the loopback port it records in `.lumlflow/daemon.port`, and any CLI
verb auto-starts it.

**Flow picker** (`/flows`) — flows the daemon knows, plus *open a folder* and
*init a flow here* (`lumlflow init` scaffolds `cells/`, `flow.yaml`,
`pyproject.toml`, `AGENTS.md`, and the store). Opening one lands on the
workbench. The draft's "create new notebook / open new notebook" is these two
gestures, renamed per the terminology table.

**Pairing** is a panel, not a wizard, and it works in one direction only:

- it shows the exact command to copy (`lumlflow agent exec -- claude`, or
  `agent begin --label` for an already-running agent);
- it flips to "claude-1 · working on `main`" the moment the `agent_begin`
  transaction arrives on the journal — no confirmation step, nothing for the
  user to tell the UI;
- unpaired is a first-class state, not an error: everything in the workbench
  works unpaired, because a human editing cells is a supported actor (§13).

**The empty state** is the canvas with three doors — *pair an agent*, *create the
first cell* (`cells new`, which scaffolds a real file, §2), *read the DSL
cheatsheet* (the generated `AGENTS.md`) — plus the draft's own line about adding
assets from the notebook view, and the honest fourth option: just tell the agent
what to build.

## 2. Left panel: the active branch (draft 9)

The draft is explicit that this panel is scoped to one branch. Switching the
viewed branch re-scopes all of it.

**Branch identifier** at the top: name, state, and its position in the family
(`forked from main · 12 steps ago`). Clicking it opens the **branch graph** — all
branches and their relationships, as the draft asks: a fork tree where each
branch is a node placed at the step it split from its parent, carrying its head
state, last intent, and whether an agent is on it. From there: view a branch,
check it out (see §7's two verbs), archive it, or select 2–5 for comparison
(§8). Archived branches are collapsed behind a toggle.

The graph is an overlay rather than a permanent panel because the draft treats
it as a disclosure from the identifier — and because branch topology is something
you consult at decision points, not something you watch.

**Current agent task**: the latest transaction's `intent` on the branch plus the
registered actor's label. Intents are mandatory on every transaction (§15) —
that requirement exists precisely so this line can be rendered from facts rather
than guessed. Unpaired reads "not paired"; a paired but quiet agent reads idle
with the time since its last transaction. Never a fabricated status.

**The inventory sections**, with the draft's labels on the left and what each
one honestly is on the right:

| Draft label | What it lists | Notes |
|---|---|---|
| files | **Cells** on this branch: slug, primary output kind, staleness chip | Not filesystem files. Workspace files (`data/raw.csv`, exports, scratch) never appear: the store never versions them and the flow directory is monolithic to the UI (§4). Shared code (`lib/`) gets no browser either — a lib edit surfaces *as a staleness cause naming the file* ("stale: `lib/metrics.py` changed"), which is §8d's entire v1 exposure. |
| experiments | Cells' `experiment` outputs | A lens over declared outputs, not a second store. Each links to the producing cell, and once the daemon has uploaded it, out to the tracker's experiment screen. |
| models | `model` outputs | Same, with the model's headline metric on the row. |
| data (input datasets) | `dataset` outputs, plus cells marked `volatility: external` | The second group is what "input" actually means at runtime: a cell reading `ctx.flow_dir` is unmemoizable and the store cannot know when its bytes changed (§1 hazard 2). Grouping them as inputs is honest; calling them datasets would not be. |
| docs (concise summary of the branch) | **Note cells** on the branch, plus the intent timeline beneath them | No store field holds a branch summary, and one would need an author. Note cells are real versioned assets (markdown in a docstring, §2), so the summary lives in the flow and travels with it. A *Summarize this branch* button hands the payload to the agent (§15) and the agent writes the note cell. Flagged in Open Questions if a first-class field is wanted instead. |
| datasources | — | **Cut from v1.** The runtime has no datasource concept; external reads are just `external`-volatility cells, and secrets are daemon-held and never returned to the frontend (§8). A connection/credential/schema browser is a product of its own. The inputs group covers the visible need. |
| variables | — | **Cut as named.** Cells execute in throwaway namespaces and communicate only through declared outputs (§1) — there are no globals to list, and listing them would advertise the exact mental model this product removes. Replaced by two real things: `params` on the card that declares them (§4), and the **scratch REPL** panel for probing live values (`lumlflow eval`, defensive copies, never writes assets, §1). |
| dependencies/packages (?) | Resolved packages from `uv.lock`, with add/remove | The draft's own question mark is fair; it earns its place because §14 produces two states the user must see: "restart kernel to apply" after an install, and "env mismatch — restart under this branch's lock" when the branch's lockfile differs from the live venv. Read-mostly; the CLI stays primary. |

**Settings**, both as the draft frames them, both corrected by what the runtime
can actually do:

- **Reactivity** is three-state, not two. §8a's default is lazy (changes mark,
  materialization happens on demand); eager is opt-in per asset or automatic
  below a cost threshold learned from recorded `cost_seconds`. So:
  `lazy` · `auto below <threshold>` (editable) · plus a per-asset eager toggle on
  the card. A flat lazy/auto switch would either never auto-run cheap plots or
  auto-run training.
- **Package reload** splits into two mechanisms that must not share a control.
  Flow-local code (`lib/`) *always* reloads — the daemon evicts `lib.*` from
  `sys.modules` when the lib hash changes, because not doing so poisons the
  cache with a stale module against a fresh hash (§8d). That is a correctness
  rule and gets no toggle. Third-party packages cannot be hot-reloaded honestly
  within a kernel lifetime (§14's active-imports trap), so the real setting is
  **on env change: ask to restart · restart automatically · never**, with the
  banner as the always-on floor.

## 3. Canvas and notebook: two tabs, one slice

Both render the resolved slice of the viewed branch. The difference is density,
and it is exactly the draft's:

- **Canvas** — cards laid out on the graph, **outputs first**, source behind an
  accordion. Edges are the declared `consumes` wiring, so the graph on screen is
  the graph the scheduler runs (§"cell vs asset").
- **Notebook** — one column, **code accented**, outputs below each cell. Order is
  topological over the slice; a DAG has no author-given order, so ties break on
  creation step (see Open Questions) and manual reordering is out of scope.

Cross-navigation both ways, as the draft asks: *open in notebook* and *see in
canvas*, each scrolling to the cell, highlighting it, and preserving it in the
URL (`?asset=train_model`) so the two views cannot disagree and links are
shareable. One `<CellCard>` component with a `density` prop serves both, which
is what keeps the draft's "same settings/options as in canvas" true by
construction rather than by discipline.

## 4. The card contract (draft 10)

One card per cell. Anatomy, assembled from the draft's per-cell list:

**Header** — slug (the address the user and the agent both use), primary output
kind, status chip, and the timing facts:

- status: `materialized` · `running` · `stale (cause)` · `unmaterialized` ·
  `failed`. `unmaterialized` is its own state, never shown as stale: the asset
  has no baseline on any branch, and asserting a change since a baseline that
  does not exist is a claim the runtime refuses to make (§8a).
- **running time** (draft): `cost_seconds`, plus a **cached** badge when the
  result came from a memo hit — a hit is not a 0-second run, and saying so is
  what makes the cache legible — plus the "computed under older env" badge when
  the recorded lock hash differs from the live one (§14).

**Tab strip over the assets this cell produced** — the draft's central ask, and
the runtime's own render surface (§3): the keys of `produces` are the tabs, the
primary output default-selected. Then two implicit tabs, **code** and **logs**;
while the cell runs, a live **console** tab streams stdout/stderr and demotes to
`logs` on completion, with the freshest output tab taking focus. Every past
materialization keeps its own logs, so rewinding shows *that* run's output, not
the latest.

Which output is primary matters more than it looks: a training cell that returns
`{model, run, checkpoint, curves}` must open on the experiment, not on whichever
key came first. Ranking: `experiment` > `eval` > `plot` > `frame`/`table` >
`note` > `metric` > `model`.

**Per-type rendering**, per the draft:

| Asset | Card body |
|---|---|
| any attachment type | The `@luml/attachments` preview for that type — image, svg, audio, video, text, code, table, pdf, html — with its existing loading/unsupported/too-big/empty/error states. |
| `model` | Headline metric + configs. Plus *see the full experiment* when the cell also produced an `experiment`, or references one. |
| `experiment` (embedded in a model) | Mini plot of the main metric. |
| `experiment` | Main metric + configs + mini plot of the main metric. |
| `dataset` | Schema + head, paged on expand. |
| `metric` / `note` / `plot` | Scalar with direction, rendered markdown, series plot. |
| unknown kind | Key-value grid over the stored preview. The kind registry is open at runtime (§3), so the renderer registry needs a documented fallback rather than an exhaustive switch. |

Everything above draws from the **stored preview**, which is why browsing works
with no kernel.

**Expanded version** (draft): the card expands into a full-height right drawer
(`RightFullHeightDialog`) carrying configs, full results, the paged value (`asset
page`, proxied to the kernel — the browser receives pages of a frame, never the
frame), and the draft's exit door: *see the full experiment* → the tracker's
experiment screen, *see the model* → the model screen. Expand is the first
gesture that may start a kernel; the UI says so before it spins one.

**Source code, visible and editable here and now** (draft): Monaco in the `code`
tab. Edits go **daemon API → store**, never by writing the worktree file (§13):
attribution is correct at the source, the edit is valid whether or not the branch
is checked out, and files are not rewritten under a working agent. Optimistic
locking on the base `definition_hash`; on conflict the menu is *overwrite* or
*fork my edit*, with fork as the default suggestion. `params` are editable
without touching source at all (§13) — they are declared data, so a param change
is a version with a params-only diff.

**Provenance** (draft's created-by / last-edit-by): both come from version
authorship, with one caveat rendered rather than hidden. In v1 there is a single
shared worktree, so every file edit during an agent session attributes to that
agent — including a human's concurrent vim edits (§11 states this cost
plainly). Windows of plausible mixed editing are flagged in the journal, and the
card renders the flag ("attribution uncertain — mixed editing window") instead of
a confident wrong name.

**The op row**, mapping the draft's list to daemon verbs:

| Draft | Verb | What the UI must say |
|---|---|---|
| run the cell | `run <slug[.output]>` | It runs the minimal stale upstream closure, so "run this cell" may run three. The button carries the **preflight**: what is cached, what recomputes, total seconds — before the click (§5). |
| rerun the whole branch/session | run to every leaf of the slice | One preflight for the batch. Force-rerun (ignore memo) is a labeled modifier, never the default. |
| stop the cell | `cancel` (interrupt injection) | An in-flight run may have several awaiting branches; preemption fires only when no awaiter still wants the result (§8c). When another branch still awaits, the button reads "leave the run, requeue this branch". |
| delete the cell | per-branch delete | It drops from **this** branch's selection; other branches are untouched, and consumers left dangling on this branch show as flagged references with did-you-mean, never silent breakage (§5). The confirm says exactly that — "delete" here does not mean what it means in a notebook. |
| rename the cell | `rename --rewire` | Free, because identity rides on the `uid`: filename and every reference string are rewritten atomically and no cache, lineage, or history is touched (§2). The reverse direction matters too — an agent's `mv` arrives as an *implicit rename* transaction, so the card must animate a rename, not a delete-and-create. |
| open in notebook / see in canvas | — | §3's cross-navigation. |
| — | duplicate cell | Present but buried and labeled. In-branch duplication mints a fresh identity with no consumers; it is how you get copy-pasted sibling variants, which forking exists to replace (§5). Fork is the promoted gesture. |

**Addressing, for talking to the agent** (draft: "each cell should have a
number/name, and each branch should have name/number"). The address is the
**slug and the branch name** — never a number. Positional numbering is wrong
twice here: the graph is non-linear, so there is no cell 3; and agents rename
constantly, so a number would be a second identity to disagree with the slug.
`uid`s never appear on screen at all. What ships instead is stronger than a
number the user retypes: a **send-to-agent** action on every card, error, and
diff, emitting §15's context payload (slug, branch, version, error, current
focus) as an MCP prompt or CLI argument — the mechanism the runtime already
defines for "fix this" / "explain this".

## 5. Extra options

| Draft | Verdict |
|---|---|
| Upload an artifact to LUML | **Ships.** `promote` (§3): the bytes are already staged in the CAS, so promotion is a daemon op with journal-visible states (`queued/uploading/done/failed`). Cells that declared `model`/`dataset`/`experiment` upload automatically on success, so this button is for inline `asset` outputs — matching AGENTS.md's "declare `asset` unless you mean to publish; promote later". |
| Upload the entire Flow to LUML (in the chosen branch state) | **Deferred.** Flow-as-LUML-artifact export is explicitly out of v1 (`preplan.md` deferred list) — there is no platform-side flow object to upload to. The v1 substitute sits in the same menu, honestly labeled: **export flow file** (`lumlflow export flow.py`, a deterministic single-file projection of the active slice) plus per-artifact promote. |
| Download the artifact | **Ships.** Streamed from the CAS through the daemon. Values that were never persisted (over the size threshold, or `persist: False`) have no bytes: the button becomes *materialize and download* carrying the preflight cost, rather than failing on click. |

## 6. During the session

**Live stream of all updates** (draft). Journal channel, monotonic steps, cursor
tracked client-side; a dropped socket reconnects and replays from the cursor
(§12), so it is a latency event and never a data event. Cell output arrives on
the separate `run_id`-scoped channel and goes straight into the running card's
console tab; a late joiner gets the tail from the daemon's ring buffer.

**Task giving for the agent via terminal** (draft) — the one item with a real
scope decision attached. The product has no embedded agent by design, so the
agent lives in the user's terminal. v1 ships the **handoff**: send-to-agent
payloads from any card, error, or comparison, plus a read-only activity feed of
what the agent did. An **embedded terminal** (xterm.js against a daemon PTY
endpoint running `lumlflow agent exec -- claude`) would satisfy the draft
literally and does not violate BYO-agent — but it is a terminal emulator, an
auth surface, and a support burden, so it is scoped as a **v1.1 candidate behind
a flag**. Flagged for decision: if the in-app terminal is required for the demo,
it belongs in Milestone 5 and adds roughly a milestone of work.

**Manual editing after the agent stops, and "some block for a cell in process"**
(draft). There is nothing to block: the worktree is always versioned, so an edit
during a run cannot destroy anything (§6). What the card shows is honest state
instead of a lock — "run in flight against v3"; editing creates v4 with a queued
rerun under §8c's awaiter-aware preemption. The one real lock is the **worktree
lock**: while an agent session holds it, a UI edit lands in the store but its
projection to files is deferred, and the card says "saved · not yet written to
files" (§13). The alternative — rewriting files under a working agent — is
precisely what the runtime forbids.

**Switching branches while the agent works** (draft: the user must not have to
sit and wait). This is why the UI has two verbs:

- **View branch** — a pure store read: previews, no kernel, no lock. Available
  for every branch, including the one an agent is driving. This satisfies the
  draft's requirement.
- **Check out branch** — rebinds the single v1 worktree, takes the lock, and
  waits (or `--force`) while an agent session holds it (§6, §11). The UI says so
  plainly: "the agent is working in the files — you can look anywhere, but
  checking out waits."

**STOP for the whole session** (draft: screen button + ctrl+c in the terminal).
The screen button cancels the in-flight run and drains the queue — that is the
part the daemon owns. Stopping the *agent* is only ours if we own its process,
which in v1 we do not (see the terminal decision above), so the button's
secondary line says so and offers the payload. Ctrl+C in the user's terminal is
the agent's own mechanism: documented, not intercepted. No button that claims to
stop something it cannot reach.

**STOP for one branch → the agent moves to the next** (draft). Split: cancelling
that branch's queued and in-flight runs **ships** (awaiter-aware). "The agent
moves on" is multi-branch orchestration, and the v1 concurrency model is one user
plus one agent on one branch (§15) — the agent's task queue is not ours to
advance. So the action cancels the work and optionally sends the agent a "branch
X is cancelled, move on" payload. Honest about who decides.

## 7. After the session: comparing branches (draft)

Entered by selecting 2–5 branches in the branch graph. Three surfaces, matching
the draft's three asks:

**Final results side by side.** One column per branch, aligned on asset, showing
each branch's version of the headline outputs — metrics as figures, curves
overlaid where the metric is shared. Comparability is not assumed: pin-at-fork
is the only v1 fork mode precisely so that sweeps stay comparable (§5), and
where it does not hold — divergent pins, mismatched datasets, mismatched scoring,
nondeterministic inputs — the comparison carries the warning inline. A
side-by-side of two numbers that were not computed comparably is worse than no
comparison.

**Where the paths go differently.** The daemon's `diff` reports two distinct
kinds of divergence (§15), and the difference between them is what makes a
20-branch comparison readable at all:

- **definition divergence** — someone edited the cell (source or params). Rare,
  structural, and *the* thing the user wants to see. Rendered as the branching
  point, with the two versions side by side.
- **materialization divergence** — same code, different inputs. Transitively
  closed, so it covers nearly everything below any edit. Rendered collapsed:
  one row per asset carrying a result chip per branch, never a fan of
  identical-code nodes.

Below that, an exhaustive table for differences with no shape — renames,
absences, param-only changes — so nothing is unreachable just because it did not
fit the visual.

**The list of created artifacts, each with a link** — the draft's mapping,
implemented as the fallback chain: `experiment` → the tracker's experiment
screen; `model` → the model card, or its embedded experiment when there is one;
`dataset` → the dataset view; nothing else → the main metric.

From here the two closing verbs: **adopt** the winner's version of an asset back
onto another branch (per-asset cherry-pick, with three-way conflict detection on
`definition_hash` and pick-a-side resolution — the whole v1 merge story, §5), and
**export** the chosen slice.

## 8. Closing and reopening (draft)

**Flow state indicator** (draft asks for one). Five states, because
running/stopped is not enough to be honest:

`running` (a run in flight) · `idle` (paired, nothing running) · `unpaired` ·
`kernel not started` (browsing works; expand will start it) · `daemon down`
(nothing live; last-known state shown and marked stale).

**Toasts on state change** (draft), coalesced. An agent burst must not produce
forty toasts, so run-level notifications are throttled and grouped by transaction
intent; state transitions and failures always get one. The existing `toasts/`
module.

**Reopening → the active branch** (draft, both for a still-running flow and a
stopped one). "Active" is the worktree's bound branch, which is durable store
state (§6) and survives daemon restarts, so the same rule serves both of the
draft's cases. The UI's last-viewed branch is a local preference layered on top,
used only when that branch still exists.

Two things the reopen path must handle that follow from the runtime rather than
from the draft: edits made while the daemon was down land as one coarse
`offline` transaction attributed to `user` (§11), and the UI must render it as
such — "the fine-grained edit sequence while the daemon was down is not
recorded" — rather than presenting it as a normal burst. And because the journal
is cursor-based, reopening after an overnight run knows exactly how far behind it
was: the indicator carries "N changes since you were here", opening the
transaction list at the cursor. That is a marker, not an inbox — the draft's
reopen rule is to land on the active branch, and this preserves it.

## 9. Errors (draft)

| Draft | What ships |
|---|---|
| Agent stopped by itself without finishing → permanent toast under the last produced cell | A **persistent inline banner** anchored under the last cell the agent touched — a banner rather than a toast, because this is a state and toasts are for transitions. Fires when the agent session ends with a failed run or unsynced assets outstanding. Detection is honest: a clean `agent end` is journaled, a killed agent is inferred from lost registration plus silence, and the banner says "the agent session ended" rather than diagnosing why. |
| Out of memory → stop the work, permanent toast about lack of memory | Kernel death is observable (exit status / OOM kill). The banner names the cell that was materializing when it died, offers **restart kernel**, drains the queue rather than silently retrying, and states what is true: the kernel is stateless relative to `.lumlflow/`, so nothing recorded is lost (§8). |
| Code error, agent-authored, on canvas → show nothing; the agent sees it and fixes it | **Demotion, not suppression.** Showing nothing collides with the runtime's never-silently-stale guarantee, and the failure is a journaled fact that appears in history anyway — so hiding it live only makes two views disagree. So: the status chip goes to failed and the traceback fills the `logs` tab, with no toast, no modal, and no red wash across the canvas. When a later version by the same author repairs the same asset, the pair collapses into one "v0→v1 · 1 failed attempt" entry in history. The user is never interrupted by a failure the agent is already fixing, and never told it did not happen. |
| Code error, agent-authored, in notebook → show the error; the agent fixes it | Same demotion rule at notebook density: the error renders inline under the cell, because code is the notebook's subject. |
| Code error, user-authored, canvas or notebook → show the error to the user | Full traceback in `logs`, inline summary on the card, and a **fix this** handoff carrying the §15 payload (asset, version, traceback). That is the difference between showing an error and doing something about it. |

Two error classes the draft does not list but the runtime produces, both needing
a surface: **flagged versions** (broken declaration, unknown reference — accepted
but flagged, never rejected, because agents iterate through broken intermediate
states, §11) render as a warning chip on the card with the did-you-mean
suggestion; and **conflicts** (an edit landing on a moved head) render as §4's
overwrite / fork-my-edit menu.

## 10. Cross-cutting: data flow and degraded states

```
daemon (loopback WS, port in .lumlflow/daemon.port)
  ├─ channel 1: journal transactions + kernel lifecycle  →  useFlowSession()
  └─ channel 2: run_id-scoped log chunks (ring buffer)   →  useRunLogs()

useFlowSession()   authoritative session state; cursor-tracked; replay on reconnect
useSlice(branchId) resolved slice + daemon-served staleness verdicts, cached per branch
useSelection()     viewedBranchId / selectedAssetId / comparedBranchIds, URL-synced
useFlowOps()       mutating daemon calls; every one carries an intent string
```

Three rules:

1. **No derived truth in the frontend.** Staleness verdicts, preflight costs,
   divergence kinds, and `settled` are computed by the daemon from stored facts
   and served. The frontend renders them; it does not recompute them.
2. **Optimistic only where the store is.** Edits carry a base `definition_hash`
   and can be rejected into a conflict menu, so an edit renders pending until its
   transaction lands. Runs are never optimistic.
3. **Unknown is a state.** `unmaterialized`, `attribution uncertain`, `flagged`,
   `irrecoverable` are all rendered as themselves rather than smoothed away.

**Staleness display** — a question `preplan.md` leaves to the UI, decided here.
Lead with the **direct-cause** view (this asset's own definition changed, its
deps were rewired, or a direct parent rematerialized), because the transitive
view lights up an entire large canvas after one upstream edit and then carries no
information. The transitive view stays discoverable, as the never-silently-stale
boundary requires: a count in the header ("14 more downstream"), a filter that
switches the canvas to transitive tinting, and a subdued tint so nothing is
*silently* fresh-looking. Causes are always named in words ("parent `features`
rematerialized", "`lib/metrics.py` changed").

**Degraded states, enumerated** — the same discipline `preplan.md` applies to
kernel isolation applies here: a failure mode without a surface is a spinner
that never resolves.

| Condition | Surface |
|---|---|
| Daemon down | Last-known session, read-only, marked stale, with the command to start it. |
| Kernel not started | Full browsing from previews. Expand/page/diff announce "this starts the kernel". |
| Socket dropped | Banner, auto-reconnect, cursor replay. No refresh, no loss. |
| Worktree lock held by an agent | Checkout, rewind, and adopt disabled with the reason and a force escape; UI edits still land, projection deferred. |
| Env mismatch on the viewed branch | Header flag "env mismatch — restart under this branch's lock"; background work for that branch is deferred, and the UI says so rather than looking idle. |
| Value never persisted | *Materialize and download* with preflight, not a broken download. |
| Irrecoverable rewind | Preflight declares it **before** the click (§5's `irrecoverable` category), never after. |
| Unknown preview/kind version | Key-value fallback with an explicit "newer preview format" note. |

---

# Scenarios

Acceptance scenarios; each is a test target.

**Pairing is detected, not declared.** The user runs
`lumlflow agent exec -- claude` in their terminal; the pair panel flips to
"claude-1 · main" on the next journal event, with no UI action taken.

**A cell with four outputs is one card.** A training cell producing
`{model, run, checkpoint, curves}` renders one card with four output tabs plus
`code` and `logs`, opening on the experiment with its curves drawn — not on a
config dump.

**Browsing needs no kernel.** With the kernel stopped, every card renders, the
inventory is complete, the branch graph draws; only *expand* prompts a start.

**Viewing another branch never waits on the agent.** An agent holds the worktree
on `main`; the user opens `exp/lr-sweep`, reads its cards, and compares the two.
No lock contention, no kernel. Attempting *checkout* shows the lock and the force
escape.

**Run reports its closure before running.** `features` is stale; the user clicks
run on `holdout_eval`; the preflight names three recomputes and the total seconds
before the click, and all three are marked when it runs.

**An agent's failure does not interrupt.** The agent authors a broken cell, runs
it, fails, fixes it, reruns: no toast, no modal; the chip goes failed then
materialized, `logs` holds both tracebacks, and history shows one folded
"v0→v1 · 1 failed attempt".

**A user's failure surfaces with a handoff.** The user edits in Monaco, runs,
fails: inline error, traceback in `logs`, *fix this* emits the payload with
asset, version, and traceback.

**Rename animates as a rename.** An agent `mv`s a cell file; the
implicit-rename transaction arrives and the card keeps its identity, position,
and history — no delete-and-create flicker.

**Per-branch delete is described accurately.** Deleting a cell on a fork names
the branch in the confirm, leaves other branches untouched, and leaves the fork's
consumer showing a flagged reference with did-you-mean.

**Param edit needs no code.** Changing `lr` in the card's config lands a
params-only version and marks the cell stale with cause `definition-changed`.

**Reconnect replays.** The socket is killed mid-burst; on reconnect the UI
replays from its cursor and the resulting state equals a fresh load.

**Reopening lands on the active branch.** After a daemon restart the workbench
opens on the worktree's bound branch, with "N changes since you were here" and
offline edits rendered as one coarse `user` transaction.

**Comparison collapses same-code divergence.** Five sweep branches: the
definition edit is the branching point rendered side by side, everything
downstream is one row per asset with a chip per branch, and a divergent pin
raises its warning inline.

**Mixed editing is not claimed.** A human edits in vim during an agent session;
affected versions render "attribution uncertain" rather than a confident agent
name.

**No internals leak.** A rendering test asserts no `uid`, content hash, or memo
key appears in any user-facing string (§10's error-vocabulary rule).

---

# Tasks

Milestones follow the draft's order so each is demoable on its own. Paths under
`lumlflow/frontend/src/flow/`; the tracker pages are untouched.

- [ ] **M1. Live session client and shell** (`api/`, `composables/`)
  - [ ] Typed op vocabulary from the daemon journal; WS client with reconnect + cursor replay; `runLogs` channel with ring-buffer tail for late joiners
  - [ ] `useFlowSession`, `useSlice`, `useSelection` (URL-synced), `useFlowOps` (intent-carrying)
  - [ ] Degraded-state machine: daemon down · kernel not started · socket dropped · behind cursor
  - [ ] Workbench shell: routes (`/flows`, `/flows/:id`, `/flows/:id/notebook`, `/flows/:id/compare`), left panel frame, flow-state indicator, coalesced toasts
  - [ ] Tests: reconnect-replay equality, cursor handling, each degraded state
- [ ] **M2. Onboarding** (`pages/FlowsPage.vue`, `components/PairPanel.vue`)
  - [ ] Flow picker with daemon discovery, open-a-folder, `init`
  - [ ] Pair panel: copyable command, live actor detection, unpaired as a working state
  - [ ] Empty-state canvas with the four doors
  - [ ] Tests: unpaired → paired driven by a journal event
- [ ] **M3. The card contract** (`components/CellCard.vue`, `renderers/`)
  - [ ] Tab strip over produced assets + `code`/`logs`, live `console` during runs with focus handoff; per-materialization logs on rewind
  - [ ] Renderer registry: `@luml/attachments` previews for attachment types (reusing `PreviewStates`), plus experiment/model/dataset/plot/metric/note, plus kv-grid fallback; primary-output ranking
  - [ ] Header/footer: status chip with named cause, cached badge, cost, env badge, created/last-edit-by with mixed-editing flag
  - [ ] Expand drawer (`RightFullHeightDialog`): configs, results, paged value via `asset page`, links out to the experiment/model screens
  - [ ] Two densities behind one `density` prop
  - [ ] Tests: multi-output primary selection, rewind logs, no-internals-leak assertion
- [ ] **M4. Canvas, notebook, and the left panel**
  - [ ] Canvas: graph layout from declared wiring, outputs-first cards; notebook: topological column, code-accented; cross-jump with highlight and URL sync
  - [ ] Left panel: branch identifier + branch-graph overlay (view / checkout / archive / select-to-compare), current agent task, cells, experiments, models, inputs, docs (note cells + intent timeline), env panel, settings (reactivity three-state, env-change policy)
  - [ ] Staleness rendering: direct-cause default, transitive count + filter + subdued tint, `unmaterialized` distinct
  - [ ] Tests: direct-vs-transitive rendering, canvas↔notebook parity, branch re-scoping of the panel
- [ ] **M5. Editing and run controls**
  - [ ] Monaco `code` tab → `cells_edit` with base `definition_hash`; conflict menu (overwrite / fork-my-edit); pending-edit and deferred-projection states; flagged-version chips with did-you-mean
  - [ ] Param editing (params-only version); `cells new`, including "add cell downstream of X"
  - [ ] Run cell (preflight tooltip), rerun branch, force-rerun modifier, cancel with awaiter-aware wording, stop-session with honest scope, per-asset eager toggle
  - [ ] Rename (`--rewire`) and implicit-rename animation; per-branch delete with an accurate confirm; duplicate, buried and labeled
  - [ ] Error surfaces: demoted agent failures, loud user failures, kernel-death and agent-ended banners, restart-kernel banner
  - [ ] Tests: conflict menu, deferred projection, cancel-with-awaiters, param-only diff, both failure paths
- [ ] **M6. Comparing branches** (`compare/`)
  - [ ] 2–5 branch selection from the graph; side-by-side result columns with inline integrity warnings
  - [ ] Divergence rendering: definition divergence as the branching point, materialization divergence collapsed to chip rows, exhaustive table for shapeless differences
  - [ ] Artifact list with the draft's link mapping; adopt-the-winner (per-asset, conflict menu) and export the chosen slice
  - [ ] Tests: collapse behavior on a wide sweep, adopt conflict, warning surfacing
- [ ] **M7. Extras, handoff, REPL**
  - [ ] Send-to-agent payload builder (§15) and its gestures: fix this, explain this diff, summarize this branch
  - [ ] Promote an inline artifact with journal-visible upload states; download / materialize-and-download; export flow file (labeled a file export, not a platform upload)
  - [ ] Scratch REPL panel scoped to the viewed branch (defensive copies, never writes assets); provenance panel (consumed input versions, recorded env, collection ref)
  - [ ] Env ops (`env add/remove`) and the on-env-change policy
  - [ ] Tests: payload shape per gesture, upload state transitions, eval against a non-checked-out branch
- [ ] **Recorded as out of scope**, so nobody rebuilds them by accident: embedded
  agent terminal (v1.1 candidate, flagged), per-branch agent orchestration,
  datasources registry, variables panel, whole-flow upload to LUML,
  workspace-file browsing, multi-agent presence rendering, custom JS renderers,
  manual notebook ordering.

---

# Open questions

- **The embedded terminal.** The draft's "task giving for agent via terminal" is
  the one item with a genuine scope decision attached. Recommendation: handoff in
  v1, PTY behind a flag in v1.1. Needs a call before M5, since it changes that
  milestone's size.
- **Branch docs authorship.** Note cells are the only honest v1 source for the
  draft's "docs" section. If a hand-written branch summary should be a
  first-class field, that is a store change (a `description` on the branch
  record) and should be requested of the runtime spec now rather than faked in
  the frontend.
- **Notebook ordering stability.** Topological order is not unique. Creation
  step is the obvious tiebreak, but it must be pinned, or cards will reorder
  under the user when an unrelated cell lands.
- **Preview schema versioning.** The preview payload is both the sync format and
  the UI contract. The renderer registry should pin a version and degrade
  visibly; decide the degradation wording with the first live session.
- **Canvas at scale.** The wedge's flows are small, but a wide sweep fans one
  cell out to twenty models, and past roughly a hundred nodes the canvas needs
  semantic zoom (collapse by group, expand on focus). Not a v1 blocker; the
  first thing that breaks.
- **How loudly to render attribution uncertainty.** Per-actor worktrees, which
  would make attribution certain, are deferred. Until then the flag's prominence
  is a taste call best made against real sessions.
