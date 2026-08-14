# Preplan — Flow runtime and session model

Answers to the open technical questions for the agent-driven, non-linear notebook
environment. *Lattice* was the internal working title (the product proposal
lives in `lattice-dfaft.md`) and does not ship: no lattice-derived name appears
in any shipped identifier — CLI, store directory, imports, and env vars all
belong to **lumlflow**, the standalone package that ships the flow runtime and
platform (`luml` proper is the SDK it bundles — artifact/experiment logging,
collections), and the system is otherwise referred to neutrally (the flow
runtime, the daemon). The product proposal covers the *what/why*; this document
resolves the *how* far enough to start detailed planning.

Two inputs inform everything below:

1. **`lattice-dfaft.md`** — artifact-first, non-linear, BYO-agent, lazy-reactive,
   experiments as first-class artifacts, no embedded agent. This one is binding.
2. **The flow concept UIs on `oleh/26q3-lattice-ui-concepts`**
   (`lumlflow/frontend/src/flow/types.ts`, `engine.ts`) — mockups, not final
   decisions; this document is free to contradict them. They still matter as a
   first pass at semantics that surfaced real problems (branch explosion,
   staleness noise, incomparable sweeps), so each idea below is either **kept on
   merits** or **explicitly reopened**:
   - A **branch is a selection map** (`assetId → versionId`) plus **pins**
     (pin-at-fork is the default), *not* a copy of anything.
   - **Definition vs. materialization divergence** are distinct: an edit is rare
     and structural; "same code, different inputs" is transitively closed and
     covers most of the graph.
   - **Staleness ("unsynced") is non-transitive** and derived per `(branch, asset)`,
     never stored. Causes: `definition-changed`, `deps-rewired`,
     `parent-rematerialized`. (The mockups' `engine.ts` only approximates
     this — it measures against the *parent branch's* slice and returns null
     for unmaterialized assets; §8a defines the real baseline.)
   - **Early cutoff** compares per-output *content hashes*, not version ids: an
     edit that changes `run` but not `checkpoint` must not invalidate consumers
     of `checkpoint` only.
   - **Transactions**: atomic batches of ops carrying an agent-supplied `intent`
     string. One explicit reversal here: the mockups treated `settled`
     transactions as the only states worth time-travelling to (`checkpoints()`
     filters to settled); this doc keeps intent-carrying transactions but
     reverses that gate — any transaction is a valid rewind target, and
     `settled` (branch fully materialized and consistent) is demoted to a
     quality badge marking natural checkpoints — a highlight, not a gate (§5).
   - **Identity is `assetId`; names are display properties.** Agents rename
     things constantly.
   - Multi-actor **presence** (`activeBranchId` / `activeAssetId` per agent) is
     part of the model — kept in the model, deferred past v1 as a surface (§15):
     the v1 concurrency model is one user + one agent on one branch.

Verdicts on the mockup-era ideas, argued in the body where they come up:

- **Kept on merits**: branch-as-selection-map (it's what makes forking O(1)),
  early cutoff on content hashes (standard incremental-build technique, and the
  only thing that makes 20-branch comparison tractable), intent-carrying
  transactions (intent-grouping is not computable from raw events), stable ids
  vs. display names (agents rename constantly).
- **Reopened**: non-transitive staleness as *the* display semantics (§8 — the
  runtime stores facts and derives both views; which the UI leads with is a
  product call, though the proposal's "never silently stale" caps how far the
  transitive view can be hidden), and the closed `AssetKind` enum (§3 — an
  open registry per the proposal's plugin pillar, and now an open *runtime*
  registry: kinds are inferred from returned values and recorded as facts,
  never declared or enumerated). The fork-default
  question was reopened, then resolved by cut: track-parent forking is out of
  v1 entirely, so pin-at-fork is not a default but the only mode (§5).

Where the questions below say "commit", the runtime term is **transaction** —
any of them can be a rewind target; `settled` is a highlight, not a gate. The
mapping is explained in §5/§6.

---

## Terminology reconciliation: cell vs. asset

The question list treats cells and assets as separate ("cell consumes and
produces assets"); the concept mockups merge them (an `AssetDefinition` carries
`source`, `deps`, `params`, `outputs`). **Recommend the merged model**
(Dagster's software-defined-assets shape) — not because the mockups use it, but
because a fully separated model buys nothing here: an asset with no producing
cell is just a source cell, and an asset with two producers is a conflict, not
a feature. Concretely:

- A **cell** is the authoring unit: one file, one class, one `materialize()`.
- A cell declares 1..n named **outputs**; each output is an addressable asset
  (`cell_id.output_name`), with its own content hash (needed for early cutoff).
- The node in the graph *is* the cell, rendered by its primary output.

This preserves the message-passing contract (cells communicate only via declared
inputs/outputs) without a second node type in the graph, and it means the DAG the
user sees is byte-for-byte the DAG the scheduler runs.

---

## 1. Forking sessions without forking the kernel

**Recommendation: one kernel process; branch state is a value, not a process.**

The mechanism is easy to state — once cells communicate *only* through declared
assets, no *heap* state is branch-specific — but the heap is not the whole
process. Same-kernel forking is the hardest, least standard part of this
design, so this section states the mechanism and then enumerates every shared
channel a real Python process has, each with an explicit policy. Isolation
that isn't enumerated is fiction.

Why not process-per-run, given that it would eliminate hazards 1, 3, and 4
outright and make cancellation trivial (kill the process)? Because it costs
per-run deserialization of inputs (seconds-scale for multi-GB frames vs.
microseconds for a hot-cache hit) plus re-import/JIT warmup — and that tax
lands on *every* interactive iteration, which is the wrong default for an
exploratory tool. The subprocess-pool executor (§8c) remains the reserved
escape hatch for workloads that want the isolation; paranoid mode is the
detector for the hazards in-process execution keeps.

- Each cell executes in a **fresh, throwaway namespace**. The runtime injects the
  resolved input values, calls `materialize()`, captures the returned outputs,
  and discards the namespace. No user-level globals survive between cells — so
  there is nothing branch-specific in the interpreter at all.
- A branch's "global scope" **is its resolved slice**: the branch's
  `selection` map resolved through the asset store. Forking = copying a dict of
  `assetId → versionId` pointers. O(#assets), microseconds, zero memory beyond
  the map.
- `sys.modules` (imports) is deliberately shared across branches — that is a
  feature (memory, import time), and safe because module state is not part of
  the asset contract. Cells that depend on module-level mutable state are
  declared `volatility: 'external'` and excluded from memoization.

**Hazard 1 — in-place mutation of shared cached values.** Two branches whose
selections point at the same cached dataframe would both observe a mutation.
Layered mitigations, cheapest first:

1. **Contract**: assets are immutable. Documented in the DSL, taught to agents
   via the generated `AGENTS.md`, linted where detectable.
2. **Runtime defaults**: kernel enables pandas copy-on-write mode; numpy arrays
   handed to consumers get `writeable=False` views where cheap.
3. **Paranoid mode (debug/CI)**: re-hash inputs after a cell runs; a changed
   hash means the cell mutated an input → hard error naming the cell, value
   restored from the store.
4. **Strict mode (opt-in)**: consumers receive a defensive copy (or a
   deserialize-from-store copy) whenever a value is live in >1 branch.

**Hazard 2 — the filesystem.** A cell that writes `./checkpoints/epoch3.pt`
has silently coupled every branch through a path. Policy: each materialization
runs with its cwd in a **per-run scratch directory**, destroyed afterwards;
durable files must be *declared outputs* — an `asset` output whose returned
`Path` infers the file kind (§3); the
runtime moves them from scratch into the CAS, so they version, fork, and GC
like any other value. Reading genuinely external paths is legitimate but
makes the run an `external` read — no memoization, no recompute claims (the
one volatility rule v1 keeps live, §2). Workspace files (§4) are exactly
that case: because cwd is per-run scratch, **`ctx.workspace_dir`** is the
sanctioned way to reach them (`ctx.workspace_dir / "data/raw.csv"`), and
the flow's optional internal `data/` folder rides `ctx.flow_dir / "data"`
(the exact access surface is an open question, §4). Both are observed as
`external` at ctx-path access — recorded like identity access (§2), no
declaration needed — because the store cannot know when `data/raw.csv`
changed. The natural upgrade — declared file inputs with hash-on-read,
restoring memoization — is a recorded future direction, not v1.

**Hazard 3 — process-global interpreter state.** Random seeds, `os.environ`,
logging config, matplotlib's implicit current figure, torch's default
device/dtype. Policy: `ctx` provides sanctioned versions of the common ones
(`ctx.seed()`, `ctx.tempdir()`, scoped env overlays); the executor runs
**reset hooks** between materializations (close figures, restore env/logging
deltas); the remainder falls under the Hazard-1 contract with `external`
volatility as the escape hatch. Honest limit, stated in the docs rather than
papered over: in-process Python cannot be fully sandboxed — paranoid mode
*detects* contamination, kernel restart *recovers* from it, and perfect
isolation is not promised.

**Hazard 4 — device (GPU) memory.** The hot cache must never pin
device-resident tensors across runs: two branches each holding a model OOMs
the GPU long before host RAM is a concern. Policy: values persist host-side
(safetensors/CPU), the hot cache holds host representations only, and device
placement happens inside `materialize()` on demand.

**Hazard 5 — concurrency at the store.** Two branches queueing the same memo
key must coalesce into **one in-flight run** that both await. A fork created
while a cell is running copies the parent's *current selection* — which cannot
yet include the in-flight, not-yet-journaled result; that result lands on the
origin branch, and the fork picks it up automatically iff its memo key
matches — no special case needed, but it must be tested, not assumed.

Interactive "it feels like a global scope" affordance: a **scratch REPL per
branch** that lazily hydrates names from the branch slice (`train_df` resolves to
the branch's version of that asset on first touch, via proxy objects). The REPL
is a mutation hole none of Hazard 1's layers cover — `train_df.dropna(inplace=True)`
typed at the prompt is not a cell run, so the post-run re-hash never fires.
Policy: REPL hydration hands out **defensive copies** by default (scratch
convenience is not worth cross-branch corruption, and copy cost is acceptable
for an interactive probe); in paranoid mode, hot-cache values touched by REPL
statements are re-hashed afterwards as a backstop. Scratch
evaluation never writes assets; promoting scratch code to a cell is an explicit
op.

## 2. Cell/asset DSL

**Recommendation: class-per-cell, declaration-as-data, statically
extractable — and structural: cell files import nothing.** Verbosity is fine
(agents write it); what matters is that the spec is *data* the tooling can
read without executing user code.

```python
# cells/train_model.py

class TrainXGB:
    """Train the churn model on engineered features."""
    uid = "01J9W3ZK7Q"
    consumes = {"train": "features.train_split", "config": "sweep.config"}
    produces = {"model": "model", "run": "experiment", "checkpoint": "asset", "curves": "asset"}
    params = {"lr": 3e-4, "epochs": 10, "seed": 1337}

    def materialize(self, ctx, train, config):
        ctx.seed()
        ...
        return {"model": m, "run": run, "checkpoint": ckpt, "curves": curves}
```

There is no base class and no import. Classification is **directory-scoped,
never shape-scoped**: only files under `cells/` are cells; any other watched
`.py` — workspace shared code (§8d), or a stray `.py` inside the flow dir —
is shared code regardless of what its classes look
like — a helper that happens to define `materialize` is never recognized
as a cell and never gets a `uid` write-back. Within a `cells/` file, shape
picks *which* top-level class is the cell: the unique class defining
`materialize` or carrying compute declarations (`uid`, `consumes`,
`produces`, `params`, `volatility`); two candidates → flagged ambiguous
(§11's flag-don't-reject rule). A `cells/` file with *no* qualifying class
is flagged invalid — never silently reclassified as lib, which would fold it
into `behaviorHash` and mark the whole flow unsynced over a typo. A **note
cell** is a class with a docstring and no `materialize` *and* no
`consumes`/`produces`; a class with compute declarations but no
`materialize` is flagged incomplete (work in progress) —
accepted-but-flagged, never treated as a valid note. References in
`consumes` are plain strings; the values of `produces` are §3's four-word
type vocabulary.

Typing is optional and stays out of the runtime: `CellProtocol`, the `ctx`
protocol type, and the `AssetType` interface ship as **typing stubs**,
imported only under `TYPE_CHECKING` — zero runtime dependency; adding the
stubs as a dev dependency buys IDE checking, with two honest catches rather
than a free lunch. A Protocol never checks a class that has no use site, so
the stubs story includes the one-line conformance idiom, scaffolded as an
optional footer comment: `if TYPE_CHECKING: _check: CellProtocol =
TrainXGB()`. And because the kernel execs cell files on the venv's Python, a
`TYPE_CHECKING`-only name in a live annotation raises `NameError` before
3.14 — so cell files that use annotations must carry
`from __future__ import annotations` (or string annotations); the scaffold
emits the future-import by default. The precedent is dbt: models never
import dbt — `ref("...")` is a convention the parser understands.

An earlier draft rejected the importless DSL and specced an imports-based
one, with a packaging split to keep it light; that is **reversed** here, and
not for dependency slimming. The decisive win is that **the flow venv needs
no lumlflow code at all**: the kernel executor doesn't need to be importable
by user code, only runnable, so the daemon launches it in the venv's
interpreter with the kernel's code path-injected from the tool install
(§14). The engineering discipline this buys into, stated honestly: a
path-injected kernel must run on whatever Python version the venv has, so
the kernel stays conservative, pure-Python, and CI-tested across the
supported version range — this replaces the earlier draft's import-boundary
CI test. Serde libraries (pyarrow, cloudpickle, safetensors) are ordinary
ecosystem dependencies scaffolded into the workspace's `pyproject.toml`
(§14) as the flow's kinds need them — not our package. The earlier rejection's counterarguments
dissolve on inspection: IDE/type support comes from the stubs (not for
free — it costs the scaffolded conformance line and the future-import rule
above, a fair price), typo
validation was always the daemon's job at acceptance (did-you-mean, below),
and future cell methods hang off the structural contract exactly as they
would off a base class.

Rules that make this work:

- **Class attributes must be literals** (enforced by the loader): `consumes`,
  `produces`, `params`, `volatility` are extracted by AST parse — no import, no
  execution. This is the "no static analysis beyond the DSL" line: we parse the
  declaration block only, never the body.
- **Identity is two-layered: the filename is the slug, and the `uid` is the
  truth.** There is no `id` attribute — the slug *is* the filename sans
  `.py` (`train_model.py` → `train_model`), the one spelling references use
  and already load-bearing for the file↔asset mapping; a second authored
  spelling could only ever agree with it or conflict. The slug is a *name*,
  unique only within a branch. True identity is the `uid`: an
  opaque ULID the daemon mints on first sight of a new cell and writes back
  into the file (formatter-style normalization; agents never type it). The
  store, journal, lineage, selection maps, divergence, and cross-branch "same
  asset" are all keyed on `uid`; the slug is how humans and agents spell it;
  the class name is free-floating display. Every collision case then has a
  boring answer:
  - *Same branch, same slug*: filesystem-impossible in a worktree — two
    files cannot share a name. The auto-suffix path (`eval_report_2`,
    flagged) survives for daemon-side ops that bypass the filesystem:
    API-created cells (§10), or an adopt that would materialize a colliding
    filename — surfaced as a conflict, never silent.
  - *Different branches, same slug*: harmless and **expected** — parallel
    agents converge on obvious names, but the two cells carry different
    `uid`s, so comparisons, divergence, and adopt never conflate them. The
    clash surfaces only when a version crosses branches (adopt, in v1 — §5),
    as a namespace conflict resolved like a file rename — never as silent
    identity confusion.
  - *Copied cell file*: the copy arrives bearing the original's `uid`; the
    daemon detects the duplicate, mints a fresh one, and records copied-from
    provenance — "copy cell" becomes robust instead of accidental.
  Renames have two equivalent spellings. `lumlflow rename train_model
  train_xgb --rewire` is the explicit one; the organic one is `mv` — any
  same-`uid`-under-a-new-filename observation is an **implicit rename**: the
  watcher records a rename transaction and triggers the same rewire flow,
  under the same worktree lock as `lumlflow switch` (§11, §13), so files are
  never rewritten under a working agent; until the rewire lands, stale
  spellings surface as dangling references with did-you-mean pointing at the
  rename. Rewire rewrites references (the filename plus every reference
  string mentioning it, atomically) — and rename is *cheap* precisely
  because identity rides on `uid`: no
  cache, lineage, or history is touched by any rename. That claim only holds
  if hashing cooperates: AST normalization
  **resolves reference strings to `uid`s** (through the branch namespace,
  at version-acceptance time) *before* hashing, so the textual rewrite leaves
  every consumer's `definitionHash` — and therefore memo keys — genuinely
  untouched. The binding is not a hashing preprocessing step but part of the
  stored definition: an `AssetVersion` *is* the source with its references
  bound to `uid`s at acceptance, and `definitionHash` hashes that bound
  form — the hash can never drift from what the immutable version means.
  Namespaces do mutate after acceptance (delete-and-recreate of a slug mints
  a new `uid`; adopt can introduce bindings, §5), so the rule: when a branch's
  namespace changes such that a cell's slug references would now bind to
  different `uid`s, the daemon **re-accepts** the affected consumer files on
  that branch — a new version with a new binding, surfacing as
  `definition-changed` staleness. Correct semantics, not an artifact: the
  cell now genuinely points at a different asset. An unresolvable slug hashes
  literally and flags the version (§11's flag-don't-reject rule). Honest
  consequence: hashing now depends on
  namespace resolution, so byte-identical cell files on branches with
  different namespaces can hash differently — which is correct, since they
  reference different assets.
- **Two hashes, deliberately split.** `definitionHash = hash(uid-bound
  AST-normalized source + params)` (the bound form the identity bullet above
  defines — slug references already resolved to `uid`s at acceptance) is
  *identity*: it drives merge conflict detection (§5) and
  divergence display (§15), and a whitespace/comment edit does not dirty
  anything. `behaviorHash = hash(definitionHash + workspace tree hash)` is
  *does it need to rerun*: staleness marking and memo keys use it
  (§8b/§8d). Folding the shared-code hash into `definitionHash` instead
  would make a three-way merge report every cell conflicted once both
  branches touch shared code, and make `lumlflow diff` report definition
  divergence everywhere. The future per-cell
  `uses = [...]` narrowing (§8d) applies to `behaviorHash`.
- **`params` and `volatility` are reserved slots — dormant in v1.** Params
  stay data, not code: the slot exists so param inspectors, params-only
  diffs, and sweeps ("N branches × param overrides" with no code diff) can
  land later without a schema change — but v1 exposes **no param or
  volatility handles in the UI** (§13); editing a param is editing the cell
  file. `volatility` is likewise parsed, recorded as provenance, and
  reserved: the only rule v1 scheduling honors is `external`'s
  no-memoization guarantee (§8b) — observed automatically from ctx-path
  access (§1 hazard 2) or declared for the undetectable cases (module-state
  dependence, hardcoded paths) — because dropping it would be silent
  staleness. The richer pure/seeded/nondeterministic semantics are a future
  feature the slots already fit.
- `ctx` carries resources (a tracker client — a thin wrapper over the luml
  SDK that records locally, the daemon syncing to the collection (§3) — seed
  control, temp dirs, secrets) so
  `materialize()` stays a pure-ish function of (inputs, params, ctx) — which is
  precisely what makes the same cell later runnable by a pipeline executor
  (Dagster/Airflow adapter compiles the same spec; no notebook-only constructs
  in the body). Seeded cells draw their seed from `params` (explicit and
  sweepable — a seed sweep is just a param sweep); `ctx.seed()` takes no
  argument and applies the runtime-resolved seed, which is why §8b's memo
  key needs no separate seed component.
- **`ctx.workspace_dir`, `ctx.flow_dir`, `ctx.branch`, `ctx.step` — paths
  and identity.** `ctx.workspace_dir` resolves the workspace — the flow's
  parent directory (§4) — the sanctioned route to workspace files (§1
  hazard 2). `ctx.flow_dir` resolves the flow directory itself, whose only
  sanctioned content beyond cells is the optional internal `data/` folder
  (§4; the access surface is an open question — `ctx.flow_dir / "data"` is
  the provisional spelling). `ctx.branch` (branch name) and
  `ctx.step` (current journal step) let a cell branch-prefix external
  writes (`ctx.workspace_dir / f"exports/{ctx.branch}/report.html"`) so
  branches don't clobber each other in the shared substrate. Two caveats travel with them, stated
  here because this is where the temptation starts. First, branch-prefixed
  workspace writes are side effects outside the store — unversioned,
  un-rewound, un-GC'd; an interop escape hatch, not the durable-output path
  (that remains a declared `asset`, §3). Second, **identity access is
  observable and recorded**: reading `ctx.branch`/`ctx.step` marks the
  materialization identity-dependent, and identity-dependent
  materializations never claim *cross-branch* memo hits (§8b) — otherwise
  branch B would be served branch A's content and B's side-effect write
  would silently never fire. This is cheap to enforce: property access is a
  runtime-observable fact, recorded exactly like kind inference (§3).
- Classes are the canonical form because they hold the declaration block
  naturally and leave room for future methods (`preview()`, `check()`,
  resource hints). Decorator sugar (`@cell(...) def train(...)`) is off the
  table now, not merely deferred — it would reintroduce the import and
  surrender the structural contract's main win.
- A **note cell** is the degenerate case: markdown in the docstring, no
  `materialize` and no compute declarations (the structural rule above —
  declarations without `materialize` read as incomplete, not as a note).

**Wiring ergonomics — three layers, one line held.** Declaration-as-data reads
as ceremony until the tooling meets it halfway; three layers do that:

1. **Scaffolding.** `lumlflow cells new <slug> [--after <producer>]` generates
   the cell file with the `consumes` block prefilled from the named producer's
   outputs and a matching `materialize` signature; the platform UI's "add cell
   downstream of X" gesture is the same daemon path (§10, §13). This is v1,
   not a later nicety — it is the same code path the UI needs anyway.
2. **Did-you-mean.** Dangling references are already flagged, not rejected
   (§11); the flag carries a fuzzy-match suggestion in `lumlflow status` and
   the UI ("unknown reference `features.train_spilt` — did you mean
   `features.train_split`?"), surfaced immediately on save.
3. **Partial references.** `"train_split"` with no producer prefix
   resolves at version acceptance iff exactly one cell on the branch produces
   an output with that name; the daemon writes back the canonical
   `"features.train_split"` formatter-style (the same write-back precedent
   as `uid` minting, §11). Ambiguous → flagged, with the candidate list.

The line being held: no marimo-style inference of wiring from cell bodies. The
wiring stays declared data — static extraction, language-neutral manifests
(§9), and branch-time resolution (§5) all hang off that — and these three
layers buy the smoothness without crossing the line.

## 3. Asset types: inline vs. LUML-native

**The declared type of an output is one of four words:
`model` | `dataset` | `experiment` | `asset`.** The rationale for exactly
four: the only thing the runtime must know *before* execution is what leaves
the flow — native reference vs. inline value — and everything kind-shaped is
knowable at runtime from the value itself. This also shrinks the Tier-0
authoring vocabulary (§10) to four words.

- **LUML-native** (`model`, `dataset`, `experiment`): the value is *also*
  serialized kernel-side into the local CAS, exactly like an `asset` output,
  and that staged entry is what consumers deserialize. Staging is
  independently necessary: cold reruns, forks, and offline consumers need a
  local byte source, and a reference-only native would have none. Collection
  logging is then the **daemon's** job: it uploads asynchronously from the
  staged bytes plus recorded metadata, writes the reference
  `{collection, artifact_id, version, digest}` back onto the materialization
  when the upload lands, and queues uploads while offline or under the
  no-network sandbox profile (§8) — journal-visible status, never blocking a
  run. The staged+daemon default is argued on merits, not on a dependency
  bar: the luml SDK is an ordinary venv dependency (scaffolded like a serde
  lib when native outputs are declared), the kernel *could* upload directly,
  and nothing forbids user code from calling luml itself — but async daemon
  upload keeps `materialize()` from blocking on a multi-GB synchronous
  upload, works under the no-network sandbox (the daemon sits outside it),
  and makes offline uniform with §12's local-first rule: staged and queued,
  a cell never fails because the network dropped. The flow stores the
  reference plus a
  cached **preview** (downsampled curves, config, final metrics) so the session
  UI renders offline. On rewind/fork the reference travels with the version —
  nothing to re-materialize, and deleting a branch never deletes a collection
  artifact. (`model`/`dataset` replace an earlier open `artifact:<type>`
  spelling; the native vocabulary tracks the luml SDK's artifact taxonomy,
  and growing it is the platform's business, not the flow schema's.)
- **Inline** (`asset`): the value is serialized into the flow's
  content-addressed store (§7) by its kind's `AssetType` plugin (see "Custom
  kinds" below) — arrow/parquet for frames, safetensors for checkpoints,
  vega/png for plots, cloudpickle as the fallback of last resort. The store
  record: `{content_hash, kind, size, preview}`.
- **Every output additionally stores a bounded preview** (table head + schema,
  plot spec, metric scalars) regardless of type — this is what the bird's-eye
  UI renders without a kernel and without touching multi-GB values.

**The kind of an inline asset is inferred, not declared.** At
materialization the returned value is matched against the registered
`python_types` matchers (DataFrame → frame, Path → file, tensors →
checkpoint, ... → cloudpickle fallback) and the winning kind is **recorded
as a fact on the materialization**. Serde, content hashing, preview, paging,
diff, and the UI renderer registry all read the recorded kind — the whole
`AssetType` plugin machinery is unchanged runtime-side; it just leaves the
authoring surface (the old declared-kind design already ran this exact
fallback chain for undeclared outputs, which was the proof it could).
Inference ambiguity — two matchers claiming a type — resolves by
deterministic registry priority and is recorded; the escape hatch for the
rare ambiguous value is an explicit override, riding a dict literal in place
of the string: `"big_frame": {"type": "asset", "kind": "frame",
"persist": True}` — string for the common case, dict for the exceptional
one. Flags (`persist`, `ephemeral`, §7) ride the same dict.

Experiments stay "the richest artifact type": a training cell declares an
`experiment` output and the tracker view is a lens over those references —
consistent with the proposal's pillar 4.

**Native lifecycle under agent churn.** Three rules keep 20 branches × N
retries from flooding collections with junk versions. Collection logging
fires on *successful* materializations only — never on failures, never on
memo hits (a hit reuses the already-logged reference). The authoring default
is `asset`: AGENTS.md and the Tier-0 guidance say **"declare `asset` unless
you mean to publish; promote later"** — promoting an existing inline value
to a collection artifact is a daemon op, cheap because the bytes are already
staged. And flow-emitted artifacts land in a **draft tier** on the
platform (a scratch tier — not §4's workspace), auto-expiring unless
promoted or referenced — recorded explicitly
as a requirement this document levies on the luml platform, not machinery it
builds.

**Custom kinds: one plugin contract for serde, hashing, preview, and diff.**
Built-in and user-defined kinds implement the same shape — `AssetType` is a
Protocol in §2's typing stubs, so a kind plugin implements the shape without
importing anything at runtime — registered via Python
entry points (installable packages) or the workspace's shared code (§8d) —
watched and hashed like any other shared code, though its history belongs
to the user's own VCS, not the flow store:

```python
class EmbeddingMatrix:                    # implements the AssetType protocol — structural, like cells
    kind = "myco.embeddings"              # namespaced; the registry is open
    python_types = (EmbTable,)            # matcher for kind inference
    def serialize(self, value, sink): ... # owns the CAS byte format
    def deserialize(self, source): ...
    def content_hash(self, value): ...    # optional; default hashes the serialized bytes
    def preview(self, value): ...         # bounded, versioned payload — always stored
    def page(self, source, query): ...    # deep inspection without loading the full value
    def diff(self, a, b): ...             # optional; powers cross-branch compare
```

Kind resolution per output value: explicit dict override (`"kind": ...`) →
registered `python_types` matcher, in deterministic registry priority →
cloudpickle fallback with a generic preview. Matchers can match by **shape
as well as type**: built-in `eval` and `metric` kinds accept documented
plain-dict/list shapes (stated in AGENTS.md's cheatsheet), so the LLM-evals
wedge's flagship values get rich preview and diff without the dict override
becoming the routine path — the override stays the escape hatch, not the
norm.

Kind plugins **execute in the kernel**. The daemon — a tool install — has
neither the serde libraries nor the flow's own plugins, so its
`asset page/query` and diff APIs proxy to the kernel, auto-starting it on
demand; at handshake the kernel reports the flow's kind registry (names,
priorities, matcher provenance — §9) so the daemon can record inference
facts. The honest consequence: previews are the kernel-free tier — browsing
a session works without a kernel, but expand, page, and diff spin one up.

Rendering deliberately requires **no custom frontend code in v1**: `preview()`
and `diff()` return compositions of **primitive renderables** (table,
series/plot spec, image, markdown, key-value grid, file link) that the
frontend already knows how to draw — so a custom kind gets a real renderer and
a real diff view by composing primitives. Shipping third-party JS renderer
bundles is a v2 extension point, kept out of v1 because loading foreign code
into the platform UI is a sandboxing/packaging problem that shouldn't gate the
kind system.

**Rich display: a tab per output, plus live console.** The cell's render
surface falls directly out of the merged cell/asset model:

- A cell renders as a **tab strip over its declared outputs** — the keys of
  `produces` are the tabs, the primary output is default-selected. Each tab
  renders via a **renderer registry keyed by asset kind** (`frame`, `plot`,
  `model`, `experiment`, `eval`, `metric`, `note`, ...). The mockups' payload
  shapes (`ArtifactValue` in `types.ts`) are a fine starting draft, but the
  kind set must be an **open registry with plugin renderers**, not a closed
  enum — an open *runtime* registry now, since kinds are inferred and
  recorded, never declared — the proposal's typed-artifact pillar explicitly
  requires the vocabulary to grow without core changes.
- Renderers draw from the stored **preview** by default (instant, works
  without a kernel); "expand" pages into the full value through a daemon API
  (`asset page/query` against the CAS entry, proxied to the kernel — see
  above) — the browser never receives a
  multi-GB frame, it receives pages of it.
- Two implicit tabs complete the strip: **code** (the cell source, collapsed
  by default per the artifact-first pillar) and **logs** — see below.
- While a cell is **running**, the strip shows a live **console tab**
  (stdout/stderr streaming in real time, §8/§12) plus per-output placeholders;
  on completion the freshest output tab takes focus and the console demotes to
  the persistent **logs** tab, which replays the capped log artifact recorded
  with that materialization. Every past materialization keeps its own logs —
  rewinding shows the logs of *that* run, not the last one.

## 4. On-disk format of a Flow

**Recommendation: directory per flow, file per cell, manifest for wiring —
and the flow directory is monolithic: cells, flow metadata, an optional
internal `data/` folder, and nothing else. Everything external — shared
code, data files, the env — lives in the flow's parent directory, the
*workspace* (§16). Single-file `.py` stays an export/import format, not the
storage format.** The analogy that sets the shape: a `.flow` directory is
to its workspace what an `.ipynb` file is to a project folder — one
self-contained document sitting among the project's code and data, treated
by the UI as a single file-like entry (§16), never browsed as a folder.

```
project/               # the workspace — where lumlflow is launched (§16)
  churn.flow/
    flow.yaml          # flow id, name, cell index (file ↔ assetId), env ref, settings
    cells/             # the only place cells live — classification is by directory (§2)
      load_data.py     # one class per file; the filename (sans .py) IS the slug (§2)
      features.py
      train_model.py
    data/              # optional internal data folder — unversioned; access surface open (below)
    .lumlflow/         # session store — the actual source of truth (see §5)
  helpers.py           # workspace shared code — watched and hashed (§8d), never inside the flow
  data/raw.csv         # workspace file — unversioned shared substrate (below)
  pyproject.toml       # workspace env definition (uv), see §14
  uv.lock
  AGENTS.md            # generated at the workspace root: DSL cheatsheet + entrypoints (§10/§15)
```

**No `lib/` inside the flow — an explicit reversal.** An earlier draft gave
the flow a conventional `lib/` home for helpers. That is reversed: the flow
is monolithic, and shared code lives in the workspace beside the `.flow`
directory, exactly where a notebook's helper modules live. §8d's
containment argument survives intact — it just relocates: the daemon
watches the workspace's `.py` files and folds their tree hash into
`behaviorHash`, so helper edits are never silently stale. A stray `.py`
inside the flow dir (outside `cells/`) is still treated as shared code —
containment, never silence — but flagged as hygiene: the flow is supposed
to be monolithic.

Why file-per-cell wins here:

- **The store's native grain is the cell version** (branch = per-asset version
  selection). A single `.py` file would force whole-file snapshots and then
  diff/split them back into cells — fighting the model.
- **Concurrent actors**: two agents editing different cells touch different
  files; no whole-file write races, watcher events map 1:1 to cells,
  attribution is trivial.
- **Agent ergonomics**: coding CLIs are optimized for "edit this file"; a
  400-line cell is a better editing target embedded in a 40-line file than at
  offset 3200 of a 4000-line notebook file.
- **The filename is the slug** (§2 — there is no separate `id` attribute to
  disagree with it), so the file ↔ asset mapping
  is identical on every branch. The `uid` inside the file (§2) is what lets
  the watcher treat a move or new filename as an **implicit rename** of the
  same asset — never a guess, never a delete-and-recreate — and backs
  identity up against copies.
- Marimo's single-file portability is real but is satisfied by
  `lumlflow export flow.py` / `lumlflow import` (deterministic round-trip).

The working directory is a **projection** of the active branch (a checkout), not
the truth — see §6. Deleting or mangling files in the worktree is always
recoverable from `.lumlflow/`.

**Workspace files.** The workspace is the flow's parent directory — the
substrate the flow sits on, browsed directly by §16's workspace view.
Everything in it that is neither a `.flow` directory, watched shared code
(`.py`, §8d), nor the env definition (§14) is a *workspace file* — data
files, exports, notebooks, scratch. Three rules: the store never versions
them; the UI treats each `.flow` directory as monolithic — workspace files
never appear on a flow's canvas or in its graph model (the flow dir as a
whole is the unit); and they are **branch-invariant** —
`switch`, `rewind`, and fork never touch them, so every branch sees the
same bytes. They are a shared, mutable substrate deliberately outside the
time plane: in the plane split below, workspace files sit on neither
plane — they are the floor both stand on. The honest consequences: never
rewound, never GC'd, never traveling with a branch — the user owns their
lifecycle, and the sanctioned durable output remains a declared `asset`
(§3). Cells reach them via `ctx.workspace_dir` (§1, §2), which marks the
read `external` — the store cannot know when `data/raw.csv`
changed. Under later per-actor worktrees this is automatic: checkouts
project the flow's cells, and the workspace sits outside them entirely.

**The internal data folder.** A flow may carry a `data/` folder of its
own — inputs that should travel when the `.flow` directory is copied. It
follows workspace-file rules (unversioned, branch-invariant, outside the
time plane); the open question is the access surface: `ctx.flow_dir /
"data"` is the provisional spelling, but whether cells get a dedicated
handle (`ctx.data`), and whether reads should later upgrade to hashed,
declared file inputs, is deliberately left open (Open questions).

**What survives version control.** First: using a VCS at all is optional —
the store, not git, owns branches and history (§5); this subsection covers
the flow that *is* in one. The workspace — its `.flow` directories
included — is what users commit; `.lumlflow/`
is never committed (the daemon writes it into `.gitignore` — scaffolded only
when a git repo is detected at flow init). Workspace code and data are
git's in the ordinary way; the store never versions them (§8d), so git is
their *only* history. Everything identity-critical
deliberately lives in the committed files:
each cell file carries its own `uid` (the write-back exists precisely so
identity travels through any channel that carries files — §2, §11),
`flow.yaml` carries the file↔uid index as a committed cross-check, and
filenames are slugs. On clone, the first daemon start rebuilds: init an empty
`.lumlflow/`, walk the files, reconstruct the namespace from filenames + in-file
`uid`s (cross-checked against `flow.yaml`; §11's reattach rule covers dropped
`uid` lines), and re-accept every cell. Bindings are compilation output (§2),
so re-acceptance is deterministic and reproduces identical
`definitionHash`es — memo keys therefore line up across machines, and caches
are merely cold, which is normal under lazy evaluation. What is honestly
lost: the time plane — journal, branch tree, old versions, values; the
committed snapshot is the active branch's slice (the only thing git ever
sees) and roots a fresh history. That is the plane split, stated plainly: git
carries the code plane (definitions — portable, text-mergeable); `.lumlflow/`
carries the time plane (branches, history, values), whose transport is the
§5 server mirror, not git. A git merge that duplicates a `uid` (a copied
cell file) is handled by the existing detect-and-remint path at next
acceptance (§2).

## 5. Fork mechanics and where session data lives

**Recommendation: a domain-aware, git-like store in `.lumlflow/` — content-
addressed objects + SQLite index + append-only journal. Git itself is not used**
(its unit is the file tree; ours is the asset version, and we need
selection/pin semantics git doesn't have). Stronger, because the borrowed
vocabulary invites the wrong assumption: **git — any VCS — is entirely
optional.** A flow directory plus `.lumlflow/` is self-sufficient; every branch,
fork, rewind, and history feature below comes from the flow's own store,
never from git, and "branch", "worktree", "checkout" name daemon-owned
mechanisms — borrowed vocabulary only, not a dependency. Where a VCS does
appear it is optional transport for the code plane (§4's plane split), and a
flow that never sees git loses nothing.

```
.lumlflow/
  store.sqlite         # index: asset versions, materializations, branches,
                       #        transactions, refs — all queryable
  objects/             # content-addressed cell sources & manifests (small blobs)
  values/              # content-addressed materialized asset values (CAS, §7)
  journal.jsonl        # append-only event log of transactions (FlowOp batches)
  worktrees/           # per-actor checkouts (see §6)
  kernel/              # socket, pid, kernel scratch
```

- **Version objects** (`AssetVersion`): definition blob hash, `definitionHash`,
  author, intent, parent version — immutable, content-addressed.
- **Materialization records**: `versionId`, consumed input version ids, output
  content hashes, state, cost, pointers into `values/`, or LUML references.
- **Branch records**: name, parent branch, fork step, `selection`,
  `pins`, `sweepGroup`, archived. **Fork = insert one branch row** with the
  parent's selection copied (staleness-baseline pointers travel with it,
  §8a). No file copies, no value copies — the CAS is shared, so unchanged
  assets cost nothing per branch. **Pin-at-fork is the only v1 fork mode**:
  inputs freeze at fork time, sweeps stay comparable, updates are explicit
  `accept-upstream` ops. Track-parent forking ("follow the parent's
  changes" — right for quick variation of live trunk) is cut from v1 — not
  because the design failed, but to shrink the surface; the sparse-overlay
  design for it (the child stores only its divergent entries and falls
  through to the parent's *current* selection, resolved recursively at
  schedule time) is recorded as the future direction, to be added when users
  actually ask for the behavior.
- **Forking never rewires anything — by construction.** A reference
  `"features.train_split"` names `(slug, output)`, never a version;
  resolution happens per branch at schedule time, in two steps: slug → `uid`
  through the branch's namespace, then `uid` → version through the selection
  map.
  Fork, then edit `features` on the fork: every downstream cell on the fork
  resolves to the fork's version while the parent keeps resolving to its own —
  zero reference rewriting, which is precisely why references must never embed
  version ids. Version-bearing edges exist only in materialization records
  (what a run actually consumed): that is provenance, not wiring.
- Two gestures that look alike but aren't: **cross-branch variation** (fork,
  then edit the cell in place — same id on every branch, so branches stay
  comparable; the intended path) versus **in-branch duplication** ("copy
  cell" — mints a fresh id with *no* consumers; splicing it into the graph is
  an explicit rewire op). The UI should steer hard toward the former: per the
  product thesis, variants are branches, not copy-pasted siblings.
- **Deletion is per-branch**: dropping a cell from one branch's selection
  leaves every other branch untouched; consumers left dangling *on that
  branch* surface as definition divergence, never as silent breakage.
- **Merge = adopt, per asset — and that is the entire v1 merge story.**
  `accept-upstream` generalizes to adopting any branch's version of an asset
  (same id, choose version) — a per-asset cherry-pick, which covers the
  sweep wedge ("take the winner's change back to trunk"). A genuine conflict
  exists only when both sides edited the same cell since the fork point
  (three-way on `definitionHash`), resolved in v1 by pick-a-side or a manual
  edit. Whole-branch merge — a batch of adopts plus slug-namespace
  unification (two `uid`s competing for one slug as a rename prompt, §2) —
  is deferred past v1; nothing in the store resists adding it later. The
  adopt-time conflict rule stays, because it guards single adopts too: an
  adopted version travels with its own `uid` binding (§2 — the binding is
  part of the immutable definition); if the target branch's namespace
  resolves one of its slugs to a different `uid`, adopt surfaces the
  mismatch as a conflict *at adopt time*, never a silent rebind — and
  namespace changes the adopt itself causes trigger §2's re-acceptance of
  affected consumers. Textual three-way merge of cell source is a later
  nicety, not a foundation.
- **The journal is the API surface for history**: every mutation (edit, run,
  fork, accept-upstream, env change) lands as a `Transaction` with `intent`,
  `author`, `ops`, `settled`. The UI's timeline, replay, and catch-up views are
  reads of this journal; the SQLite index is a materialized view of it.
- **One write ordering, for crash atomicity**: CAS objects/values first, then
  an fsync'd journal append — the commit point — then the SQLite index update.
  The index is a pure materialized view, rebuilt from journal + objects on
  startup and never trusted over them; recovery truncates a torn trailing
  journal line; CAS blobs not yet referenced by any journaled transaction are
  orphans for a later sweep (§7).
- **"Commits"** = transactions, *any* of them. An earlier draft gated rewind
  targets on `settled`, but under lazy evaluation (§8a) a branch with one
  perpetually-unmaterialized expensive leaf never settles — a realistic
  session would offer few or zero targets, breaking the time-travel promise.
  And switching — between branches or to any transaction — is **instant and
  prompt-free**: clicking a branch or a rewind target just swaps the
  selection map (a dict of pointers), lazy evaluation guarantees nothing
  recomputes on the click, and there is no "should we rewind?"
  confirmation, no preflight dialog. §7's persist-everything policy is what
  makes the promise honest: every value any journaled transaction
  references is still in the CAS, so every jump lands warm and faithful.
  The case an earlier draft guarded with a `preflightCost` gate and an
  **irrecoverable** category (values evicted or past a retention window)
  cannot arise in v1 — nothing referenced is ever evicted, and the journal
  is never pruned, so the target always exists *with* its values.
  `preflightCost` survives as background metadata on *run* decisions
  (§15's pending-dirty-set cost), never as a switch gate. `settled` (branch fully
  materialized and consistent) is demoted to a quality badge: the timeline
  highlights settled transactions as the natural checkpoints, but never gates
  on them.
- **Sync**: local-first. The lumlflow server mirrors the journal + previews
  (and optionally values, by policy) per session; that's what the platform UI
  and any remote collaborators consume. v1 can ship local-only with the server
  reading the same store on localhost.

## 6. Is "active commit = working file" the right model?

**Yes — checkout semantics is what makes external CLIs work with zero
integration. Two upgrades on the naive version:**

1. **The working copy is itself always versioned (jujutsu-style).** There is no
   dirty state: the file watcher snapshots every observed edit into a new asset
   version on the active branch (grouped into transactions, §11). Switching
   branch/checkpoint can therefore never lose work — there is nothing
   uncommitted to lose, and no stash. This also guarantees the session tree
   records *everything an agent did*, including abandoned attempts — which is
   the whole "bird's-eye view over agent executions" point. Failed/abandoned
   versions stay in history but collapse out of default views. The guarantee
   does not depend on the watcher being awake: edits made while the daemon
   is down are versioned by §11's cold-start reconciliation at next start.
2. **Per-actor worktrees, not one global checkout.** `worktrees/main` is the
   user's; an agent driving a different branch gets `worktrees/<branch>` so two
   actors never fight over the same files. A worktree is bound to exactly one
   branch at a time — that binding is what lets the watcher attribute a file
   edit to a branch without heuristics. The certainty is **per-worktree**, so
   it is only as strong as the worktree-per-actor discipline: v1 ships a
   single worktree with a hard rule that concurrent actors work on the same
   branch or wait, which weakens attribution (§11 states the honest cost);
   the layout above is reserved precisely because it is what delivers
   certainty.

Also: the checkout writes a small generated sidecar (`.lumlflow/CHECKOUT.md`,
linked from `AGENTS.md`) stating branch, checkpoint, staleness summary — so an
agent that only reads files still knows where it is.

One inversion falls out of "the worktree is a projection": the worktree is an
**opt-in adapter for file-native agents, not a requirement**. A session whose
actors all speak the daemon API (§10's `cells new`/`cells edit`, §13's UI
edits) never materializes a worktree at all — no checkout, no watcher, no
attribution machinery — so MCP-only and headless/remote sessions fall out for
free. This deletes the entire watcher-hazard cluster (§11, §13) for exactly
the sessions that never needed files.

## 7. Should assets always be serialized to disk?

**Persist everything, dedupe hard — previews always, values always,
recompute demoted from safety net to optimization:**

| Tier | What | Policy |
|---|---|---|
| Previews | table head+schema, plot spec, metrics, experiment summary | **Always**, unconditionally — small, and they power the entire session UI without a kernel |
| Values | full serialized outputs in the CAS | **Always** — persist-everything is what makes branch switching and rewind instant and prompt-free (§5); `"persist": False` (§3's dict override) stays as a dormant escape hatch for the truly outsized |
| Hot cache | deserialized objects in kernel memory | LRU over the active branch's slice — the only tier that evicts |

Rules that make persist-everything viable:

- **Content addressing is the "smart dedupe"** that makes the policy
  affordable: 20 sweep branches sharing an unchanged 5 GB features frame
  store it once; a rewind target shares every unchanged value with the
  present. Identical bytes are never stored twice — across branches,
  transactions, and time.
- **CAS values referenced by any journaled transaction are never deleted.**
  Every transaction is a rewind target (§5), and instant prompt-free
  switching is only honest if the target's values still exist. GC is
  therefore mark-and-sweep over *journal-referenced* objects: it collects
  only true orphans (§5's crash-recovery leftovers) and values whose every
  referencing transaction belongs to an explicitly deleted flow. In-flight
  runs pin their inputs and outputs for the duration — never bare refcount
  deletes racing an adopt or a rewind.
- **The honest cost is disk, and it is owned rather than hidden**: an
  append-only value store grows monotonically; dedupe bounds the growth to
  the volume of *distinct* results, which at exploration scale is the right
  trade for instant time travel. Eviction-to-cold (recompute pure values on
  demand) and a value-retention window for nondeterministic decay are
  recorded as future controls for when a flow outgrows the trade — not v1
  machinery, and neither may ever gate a switch with a prompt (§5).
  Per-flow disk usage is surfaced in `lumlflow status` so growth is visible
  before it hurts. (LUML-native outputs additionally get a collection-side
  copy once uploaded, §3.)
- With values always present, the earlier volatility-tiered retention rules
  dissolve: nondeterministic/external outputs need no special pinning —
  everything is pinned by policy — and faithful rewind holds universally,
  which matters most in the LLM-evals wedge where nondeterministic values
  are the norm, not the edge case.
- **Ephemeral outputs** (`"ephemeral": True` in §3's dict override) for the
  unserializable (connections, GPU handles):
  never persisted, always recomputed, excluded from memoization — these are
  closer to resources than assets and `ctx` is usually the better home.

## 8. Kernel architecture

One long-lived daemon per session (kernel + supervisor), four components.
One invariant before the components: **kernel plumbing is invisible.** The
user interacts with the flow, never with a kernel — opening a flow (§16)
attaches the session, the daemon spawns and supervises the kernel on
demand, and no connect/select/configure surface exists anywhere in the UI
or CLI. Everything is wired through the daemon: browsers and agents speak
to the daemon (§10–§12), the daemon alone speaks to the kernel (§9's
JSON-RPC boundary), and no client ever holds a kernel connection. The one
kernel control that surfaces at all is §14's prompted restart banner — a
one-click action, not connection management.

**a) Scheduler (DAG-level reactivity).** The graph comes from the manifests —
no static analysis of cell bodies, per the design constraint. Crucially, the
store records only **facts**: which input versions each materialization
consumed, and per-output content hashes. Staleness is never stored — it's a
derivation, and *both* candidate display semantics are cheap derivations of the
same facts: the **direct-cause view** (unsynced only if the asset's own
definition changed or a direct parent actually rematerialized — a
Dagster-style direct-cause rule, adapted from the mockups' draft rather than
taken from it: their `engine.ts` actually measures definition-changed /
deps-rewired against the *parent branch's* slice and returns null for
unmaterialized or failed assets, which is a different and less useful rule —
this one keeps a large canvas from lighting up wholesale) and the
**transitive view** (everything downstream of any change — the marimo-style
intuition users may expect). Both derivations need a defined baseline:
staleness for `(branch, asset)` compares the branch's current selected
version and its inputs' current content hashes against the **last
materialization observed on that branch** — a recorded per-`(branch, asset)`
pointer, updated on both runs and memo hits. The pointer is a recorded fact,
one cheap row, and does not violate "staleness is never stored": the
*verdict* stays derived; the *baseline* is a fact. The pointers are **branch
state, carried exactly like the selection map** — dense-copied at fork in v1
(pin-at-fork is the only mode, §5); if the deferred track-parent overlay
ever ships, the pointers ride the same sparse fallthrough to the parent's
*current* pointers. A
fork thus inherits verdicts instead of zero observations and no verdict — the
hole this section faults the mockups' engine for — and a rewind restores them
to their as-of-transaction values just as it restores the selection — the journal has the facts for
both; leaving them untouched would compare the rewound slice against
post-rewind materializations and mark it wholesale unsynced, defeating
"rewind is instant". Memo hits are journaled to make the baseline survive
§5's rebuild: a "run to X" transaction's ops record both executed
materializations and the cache hits observed during resolution (compact
entries: asset, version, memo key) — no separate event class, near-free
because hits are recorded only when a schedule pass actually resolves them.
One more verdict is defined rather than implied: an input with no content
hash anywhere — the asset never materialized on any branch — reads
**unmaterialized**, a distinct display state, not "unsynced", which would
assert a change since a baseline that does not exist. Which view the UI leads
with is reopened as a product question, with one constraint that is not open:
the binding proposal's "artifacts are never silently stale" rules out hiding
transitive staleness entirely — whichever view leads, the other must remain
discoverable (a count, a filter, a subdued tint); only the emphasis is free.
The runtime is deliberately agnostic, and execution correctness never depends
on the choice — "run to asset X" always computes the true minimal stale
upstream closure, with early cutoff on content hashes pruning both views. Default mode is **lazy**: changes only mark;
materialization happens on demand. **Eager** is opt-in per asset or automatic
below a cost threshold (learned from recorded `costSeconds`), so cheap plots
refresh live while training never auto-runs.

**b) Memoization.** Memo key = `(behaviorHash (§2), canonically-serialized
map of input name → consumed output content-hash)` — no separate `params`
or seed component: params already
ride inside `definitionHash` and therefore `behaviorHash` (§2), and a
seeded cell's seed is a param (§2), so it rides the same path. The inputs
must be a *named map*, not a sorted bag of hashes: an
upstream fix that swaps the contents of two same-schema outputs (train/test
splits, say) leaves the multiset identical — a false hit serving silently
wrong results as fresh. Env hash is recorded as provenance but **not** in the
key by default (§14). Cross-branch reuse falls
out for free: two branches that resolve identical keys hit the same CAS entry —
this is the "reuse of unchanged assets between branches" answer, and it's the
same mechanism as the single-branch cache, not a special case. One carve-out
(§2): identity-dependent materializations — the cell read
`ctx.branch`/`ctx.step` — never claim *cross-branch* hits.
`external` never memoizes — observed from ctx-path access or declared (§2),
the one volatility rule live in v1; the richer rules (e.g.
`nondeterministic` records materializations but never claims a cache hit)
are specified but dormant with the rest of the volatility feature (§2).
In-flight runs are part of the cache: a
second branch requesting a key that is currently executing awaits that run
rather than starting a duplicate (§1, hazard 5).

**c) Executor.** Runs one cell at a time (v1) from a priority queue (active
branch first, then background branch work). Per run: create the scratch cwd
(§1, hazard 2) → build fresh namespace → inject deserialized inputs (from hot
cache or CAS) → call `materialize()` → hash + persist outputs (hashing happens
while serializing, so it's ~free) → run reset hooks (§1, hazard 3) →
emit events. The run is **non-interactive by construction**: stdin is at
EOF (`/dev/null`, inherited by subprocesses), so `input()`, `getpass`, and
`breakpoint()` fail immediately with `EOFError` instead of hanging the
serial queue on an invisible prompt — the fd-captured prompt text sits in
the console right above the error, and the failure record carries a
targeted hint ("cell requested interactive input; cells are
non-interactive — take values via `params`, secrets via `ctx`"). This is
principled, not merely defensive: a human-typed answer is neither recorded
nor replayable, so interactive input is fundamentally incompatible with
memoization and recompute claims — the sanctioned homes are `params`
(recorded, sweepable) and daemon-held secrets via `ctx`, and the scratch
REPL (§1) is the interactive surface, where stdin works normally. (A
Jupyter-style `input_request` channel over the event stream is a possible
later extension *only if* the reply is recorded as provenance on the
materialization — explicitly not v1.)
stdout/stderr are captured at the **file-descriptor level**
(pipe redirection, not `sys.stdout` monkey-patching) so output from C
extensions, tqdm and subprocesses is caught too — tqdm and `logging`
default to stderr, which is why capturing both matters. One capture loop
drains both pipes and stamps a single monotonic `seq` across the two
streams; the incrementally emitted `{run_id, stream, seq, bytes}` events
(§12) thus give best-effort interleaving, faithful at chunk granularity —
with the honest caveat that exact cross-stream ordering is unknowable once
the OS buffers the pipes independently, the same accepted limit as any CI
log capture. The `stream` tag preserves stderr's identity end to end: the
live console can tint or filter it, the persistent logs tab replays it, and
on failure the traceback arrives on stderr into the same capped log
artifact that every run records — ANSI preserved throughout. Cancellation via interrupt injection (`PyThreadState_SetAsyncExc`-style /
signals), with the queue preempting stale work when its inputs change mid-run —
a per-branch judgment applied carefully to shared work: an in-flight run
tracks its awaiting branches (§8b coalescing), and preemption fires only when
*no* awaiter still wants the result under its own inputs; otherwise the run
continues and only the changed branch re-queues.
Parallelism later: same-process threads for GIL-releasing workloads, or N
executor subprocesses sharing the CAS — the store design already permits it.

**d) Shared code — a containment rule, not a feature, relocated to the
workspace.** Cutting shared-code
support would not remove shared code: users and agents factor out helpers
regardless, and with no sanctioned home those helpers become
`sys.path` hacks or local installs — where edits are invisible to hashing,
which is silent staleness, violating the never-silently-stale guarantee.
The sanctioned home is the **workspace** (§4): the flow is monolithic, so
helpers live beside the `.flow` directory, exactly where a notebook's
helper modules live, and the kernel runs with the workspace root on
`sys.path` so `import helpers` works Jupyter-style. The rule: **any
watched `.py` outside `cells/`** — workspace code, or a stray `.py` inside
a flow dir (§4's hygiene flag) — is shared code; classification is
directory-scoped (§2), so a helper that happens to define `materialize` is
still shared code. The daemon watches these files and folds the
**workspace tree hash**
into every cell's `behaviorHash` (§2 — never into `definitionHash`, which
stays identity), so a shared-code edit marks everything unsynced — blunt,
but *lazy* reactivity makes blunt cheap (nothing recomputes until asked).
Watch scope is bounded by standard exclusions (`.venv`, `.git`,
`node_modules`, other flows' internals); a large monorepo above the
workspace makes the blunt tree hash noisy, which is exactly what the
future per-cell `uses = ["helpers"]` narrowing fixes, without new
machinery. Two honest consequences of the relocation. First, **the store
does not version workspace code** — its history belongs to the user's own
VCS (§4's plane split): rewinding a flow never rewinds `helpers.py`, so a
rewound branch whose helpers have since changed reads as stale ("stale:
`helpers.py` changed") — surfaced, never silent — rather than
time-traveling files the flow does not own. Second, shared-code edits
still land in the journal as observed facts (tree-hash transitions naming
the changed paths), so the timeline shows *that* and *when* helpers
changed even though the store keeps no copy of their content — that is the
entire v1 UI exposure; there is no dedicated shared-code surface (a
workspace code drawer is a later nicety). Marking
alone is not enough, though: §1 shares `sys.modules`, so a rerun would
`import helpers` and get the cached *old* module while recording the new
hash — a permanently poisoned cache entry. So when the workspace tree hash
changes, the daemon **evicts the workspace's modules from `sys.modules`**
before the next
materialization; the fresh namespace re-imports current code. Workspace
code thus gets reload semantics while third-party packages keep §14's
restart-banner semantics. Known reload hazard, stated rather than hidden:
values deserialized against a changed class definition can misbehave —
paranoid mode detects, kernel restart recovers.

Crash/restart story: the kernel is stateless relative to `.lumlflow/` — restart
reloads the index, hot cache warms lazily, and worktree edits made during the
outage are versioned by §11's cold-start reconciliation. This is also the
reproducibility answer: a session survives reboots with all checkpoints intact.

Security note (proposal calls it a v1 concern): the kernel executes arbitrary
code by design, so isolation lives at the process boundary — the daemon runs
the kernel as a child under a basic sandbox profile (no-network mode,
FS allowlist — in the v1 cutline; only seccomp/container-grade profiles are
deferred), and everything agents touch goes through files + daemon API, never
raw kernel access. No-network mode does not strand native outputs: collection
uploads are daemon-side and queue until the network is allowed (§3). Secrets posture: `ctx` resolves secret references at run
time from a daemon-held store — secret values never enter the CAS, previews,
or journal, and the daemon API never returns them to agents.

**Portability (macOS / Linux / Windows) — a v1 requirement, not a port.**
The platform-sensitive mechanisms, each with a policy:

- **Watcher backends** differ per OS (FSEvents / inotify /
  ReadDirectoryChangesW; use a mature cross-platform library) — and
  correctness never depends on event delivery fidelity, because §11's
  quiesce contract makes every version-resolving daemon op do a synchronous
  rescan: events are a latency optimization, the rescan is the truth. That
  design choice is what makes per-OS watcher quirks tolerable.
- **Daemon↔kernel transport**: unix domain socket where available, loopback
  TCP with a daemon-minted auth-token file on Windows — a transport detail
  hidden behind §9's JSON-RPC boundary, changing nothing above it.
- **Slugs are case-normalized (lowercase)**: filenames are slugs (§4), and
  macOS/Windows filesystems are case-insensitive by default — two slugs
  differing only in case would collide on disk, so the normalizer forbids
  it (the same auto-suffix path as other collisions, §2).
- **Atomic writes**: temp-file + `os.replace` everywhere; on Windows, daemon
  file writes (`uid` write-back, projections) retry on sharing violations
  from editors holding files open — converging, the same shape as §11's
  write-back race story.
- **Capture and cancellation**: fd-level stdout/stderr capture (`dup2`) and
  `PyThreadState_SetAsyncExc`-style interrupt injection are
  CPython-portable; POSIX signal delivery is a fallback path, never the
  primary mechanism.
- **The sandbox profile degrades honestly per OS**: no-network/FS-allowlist
  ships where the OS makes it cheap (macOS seatbelt, Linux namespaces);
  Windows v1 gets plain process isolation, surfaced in `lumlflow status`
  rather than silently claimed — richer Windows isolation is deferred.
- The store assumes a **local filesystem**: a flow inside a cloud-synced
  folder (OneDrive/Dropbox/iCloud) gets a detection warning at init, since
  SQLite-WAL and file watchers both misbehave there.

## 9. Swappable kernels (future)

Don't build a second kernel now; **do freeze the boundary** so one is possible:

- Daemon ↔ kernel speaks **JSON-RPC over a local socket**: `load_slice`,
  `run(version_ids)`, `cancel`, `introspect`, plus an event stream
  (`started/progress/log/preview/materialized/failed`).
- **No Python objects cross the boundary**: values are exchanged as CAS entries
  with declared serializers; frames standardize on Arrow, which is already the
  lingua franca for R/Julia/JS kernels.
- Manifests are language-neutral (the class DSL is the *Python frontend* to a
  JSON cell spec; `flow.yaml` records `language` per flow or per cell).
- Kernels advertise capabilities (serializers, cancellation, REPL) and the
  protocol version at handshake, and report the flow's kind registry —
  names, priorities, matcher provenance — so the daemon can record §3's
  inference facts. Kernel and daemon always ship together in
  the tool install (the kernel is path-injected into the venv, §14), so
  there is no sibling version skew to negotiate away — the handshake guards
  protocol compatibility for future third-party kernels.

Cost of this discipline is near zero in v1 (the daemon/kernel split is wanted
anyway for crash isolation), and it prevents the classic mistake of pickling
Python objects into the protocol.

## 10. Connecting agents to sessions

**The Tier-0 surface — a hard constraint.** The entire system must be
drivable with exactly three gestures — edit a cell file, `lumlflow run
<slug>`, `lumlflow status` — using names only: no branch, worktree, version,
or id vocabulary is required for the minimum loop. Everything else (fork,
rewind, adopt, pins) is progressive disclosure. Two enforcement rules keep
this honest: (1) **acceptance test** — the generated `AGENTS.md` quickstart
must fit in ~20 lines, and a small-model (Haiku-class) agent given only that
quickstart must complete the edit → run → inspect → fix-a-failure loop; this
is a v1 release gate, not an aspiration. (2) **error vocabulary** — errors
and status output speak the surface language (slugs, output names, costs,
plain causes); `uid`s, content hashes, and memo keys never appear in
human/agent-facing errors — they live behind `--json`. The rationale in one
sentence: the internals are deliberately heavy so the surface can be thin —
the machinery (watcher auto-versioning, content addressing, the lazy
default) exists to *delete* user-facing ceremony, and this contract is what
keeps that claim from quietly eroding.

**Both CLI and MCP, as thin frontends over one daemon API — CLI is primary.**
The CLI is `lumlflow <verb>` — a top-level command, not a subcommand of the
SDK, because the packages are split: `luml` is the SDK dependency the runtime
bundles (artifact/experiment logging, collections), `lumlflow` is the
standalone product.

- **CLI** (`lumlflow ...`), everything with `--json`: `status`, `tree`,
  `cells list/show/new/edit`, `run <asset>`, `fork`, `switch`, `rewind`,
  `diff`, `asset preview`, `eval` (scratch REPL evaluation against the active
  branch's slice, under §1's scratch rules — defensive copies, never writes
  assets; how an agent debugging a failing cell probes live values beyond
  what `asset preview/page` serves), `context` (§15), `root` (resolves
  upward from cwd to the flow directory, `git rev-parse
  --show-toplevel`-style — for scripts and agents). Coding CLIs are
  strongest at shell + file editing, so this is the workhorse interface. Ops
  execute via the daemon socket, so they're transactional and journaled.
- **The edit surface is API-first-class, not worktree-only.** `cells new`
  (§2's scaffolding verb) and `cells edit` — exposed over MCP as `new-cell` /
  `edit-cell` tools — write `AssetVersion`s directly to the store via §13's
  daemon-originated-edit path, under the same optimistic locking (base
  `definitionHash`). MCP-only clients — hosted agents, claude.ai-style
  clients, thin custom integrations — are thereby fully supported first-class
  actors in v1, not a v2 hope; per §6, their sessions never materialize a
  worktree at all.
- **MCP server** exposed by the daemon: the same verbs as tools, plus resources
  (manifest, cell sources, previews, focus context) for agents that integrate
  MCP-natively. Strictly a wrapper over the same API — no second code path.
- **Discoverability**: a generated `AGENTS.md` at the workspace root (§4 —
  agents launch in the workspace, and one file covers every flow in it; DSL
  cheatsheet documenting the literal, import-free spelling — plain classes,
  string references, the four output types plus the accepted `eval`/`metric`
  dict shapes (§2/§3), workspace files and `ctx.workspace_dir` (§4) —
  immutability
  contract,
  CLI verbs, "run `lumlflow context`
  first", "always name cells" — §13, and "declare `asset` unless you mean to
  publish; promote later" — §3), kept current by the daemon. Plus a
  distributable skill, following the existing `extras/skills/` pattern in
  this repo (the prisma onboarding skill is the precedent).

## 11. Routing agent actions: webserver or direct files?

**Hybrid, split by the nature of the action — and both paths converge on the
journal:**

- **Code edits: direct file edits** in the worktree. This is non-negotiable for
  BYO-agent — a coding CLI's entire toolchain (search, multi-file edit, lint
  loops) assumes real files; routing edits through an API would neuter exactly
  the agents we're betting on. The daemon's **file watcher** turns observed
  edits into asset versions: parse declaration → normalize (mint and
  write back `uid` for new cells, re-uid detected copies, record a
  same-`uid`-new-filename observation as an implicit rename — §2) →
  validate → new `AssetVersion`
  on the actor's branch, grouped into a transaction. Every watcher-created
  version records the **parent version it was derived from** — the branch
  head the file content reflected when the actor last saw it; if the head has
  meanwhile moved past that parent (a store-originated edit landed while
  projection was deferred, §13), the version is flagged as divergent instead
  of silently advancing the head, with fork-my-edit as the suggested
  resolution — §13's optimistic-locking menu, now covering both directions.
  Invalid states (broken
  declaration, unknown input id) are *flagged* on the version, not rejected —
  agents iterate through broken intermediate states, and rejecting writes would
  fight their loop. The `uid` write-back is the **one sanctioned exception**
  to the never-rewrite-under-an-agent rule (§13), under a deliberately narrow
  protocol: a single-line atomic insert, performed immediately on first
  observation of a new cell, idempotent, never touching any other line; if it
  loses a race with a subsequent agent write, the watcher re-runs
  normalization on the next event and the file converges. Agents that track
  mtimes may see one spurious changed-since-read per brand-new cell —
  bounded, and the `flow.yaml`-only mapping (Open questions) remains the
  escape hatch if real agents choke on it. The companion repair rule prevents
  the worse failure: a file arriving at an existing slug *without* a `uid`
  (an agent rewrote the whole file and dropped the line) **reattaches to the
  existing `uid`** via `flow.yaml`'s file↔asset index — never mints a fresh
  one, which would read as delete-and-recreate and cascade re-acceptance and
  downstream invalidation (§2).
- **Structural & execution ops: daemon API only** (via CLI/MCP): run, fork,
  switch, rewind, accept-upstream, env ops. These need transactional semantics
  and journal ordering that file edits can't express. One ordering contract
  binds the two paths: every daemon op that resolves versions begins by
  **quiescing the watcher** for the op's worktree — a synchronous rescan that
  flushes pending events and versions any observed-but-unprocessed edits —
  before resolution. A coding CLI that writes a file and calls `lumlflow run`
  milliseconds later therefore always runs the edit it just wrote, never the
  pre-edit version with a materialization recorded against it. (The open
  question on watcher transaction grouping is about *grouping*; ordering is
  fixed here and stands either way.)
- **The watcher is never load-bearing for correctness.** The store must
  reconcile correctly from any worktree state with zero watcher events ever
  having fired. There is one reconciliation primitive — compare the worktree
  against the branch head and accept whatever diverged — run in three tiers:
  live watcher events (the low-latency path), the pre-op quiesce rescan
  (above), and **cold-start reconciliation** — daemon start after a stop,
  crash, or offline period does a full rescan and accepts divergence as new
  versions. One clause makes the primitive projection-aware: if a diverged
  file's content hash equals a *known version* of that asset on the branch,
  it is a **pending projection** (§13 — a store-originated edit whose
  write-out was deferred), and reconciliation completes the projection
  instead of accepting a new version; only content matching no known
  version is accepted as an edit. The guardrails all live in *version
  acceptance*, which is
  observation-path-agnostic: `uid` minting, copy detect-and-remint,
  collision auto-suffixing, and dangling-reference flagging run identically
  whether a file was seen live or discovered at startup — a cell file copied
  while the daemon was down is handled exactly like one copied while it was
  watching. Offline specifics: structural ops are impossible while the
  daemon is down (they are daemon API calls, and CLI verbs auto-start the
  daemon on first use, so a stopped daemon is transient anyway) — offline
  mutation is file edits only, which the rescan fully recovers, and the
  journal has no op gaps. The worktree→branch binding is durable store state
  (§6), so offline edits land on the bound branch unambiguously. What
  honestly degrades offline is granularity and attribution: the offline
  delta lands as one coarse transaction attributed `user`, marked `offline`,
  with an auto-intent ("offline edits: 3 cells changed") — the fine-grained
  edit sequence of the offline window is unrecorded, the same way git sees a
  delta rather than the process, and agent attribution cannot be claimed for
  offline windows (no registered session). Distinct concern, already
  covered: this is the *daemon* being down; the lumlflow server (the mirror)
  being down is §12's offline tolerance — local journal durable, mirror
  catches up, no data loss.
- **Attribution**: an agent session registers itself
  (`lumlflow agent begin --label "claude-1"` or wrapper `lumlflow agent exec -- claude`,
  which sets `LUMLFLOW_ACTOR` in the child env). The watcher attributes worktree
  edits to the registered actor of that worktree; unregistered edits attribute
  to `user`. v1 honesty: with one shared worktree (§6), "registered actor of
  that worktree" attributes *all* edits during an agent session to the
  agent — including a human's concurrent vim edits, which are misattributed.
  v1 mitigates rather than pretends: (a) every projection-changing op —
  `switch`, `rewind`, `adopt`/`accept-upstream`, `rename --rewire`, and the
  deferred projection of store-originated edits (§13) — takes the worktree
  lock and waits (or `--force`) while an agent session holds it, so files
  cannot be rewritten under a working agent; (b) periods with plausible mixed
  editing are flagged in the journal instead of claimed with certainty.
  Per-actor worktrees (§6) are what actually deliver attribution certainty —
  which is why that layout is reserved. Agents supply `intent` per
  transaction (`-m` on CLI ops; for
  watcher-captured edit bursts, the enclosing `agent begin/end` block's label
  and message apply).

The lumlflow webserver is **not** in the local hot path — it subscribes to the
journal (§12). Remote/cloud sessions later invert the transport, not the model.

## 12. Streaming agent changes to the platform

The append-only **journal is the stream**; everything else is subscription
plumbing:

- Daemon broadcasts journal transactions + kernel execution events over
  WebSocket/SSE; the lumlflow frontend subscribes per session. The event
  vocabulary (asset ops, materialization lifecycle, forks, presence) has a
  usable draft in the mockup types (`FlowOp`), but should be treated as a
  **versioned wire format designed now**, free to diverge from the mockups.
- Every event carries a monotonic step; **catch-up = replay from cursor**, so a
  browser that reconnects (or a user who opens a session an agent worked on
  overnight) requests `journal since N`. Concept 3 ("catch-up first") is
  literally a rendering of this replay, grouped by transaction `intent`.
- Cell output streaming (stdout/stderr, training logs, progress bars) flows on
  a separate **ephemeral `run_id`-scoped channel** multiplexed over the same
  WebSocket: the executor's fd-level capture (§8) emits ordered chunks that the
  UI pipes straight into the running cell's live console tab (§3). The journal
  records the final materialization (plus the compact memo-hit entries of
  §8a) and the capped log artifact — never the chunk stream; the log artifact
  is what the cell's persistent "logs" tab replays afterwards — keeping the
  journal small and replayable. A late-joining viewer gets the log tail from
  the daemon's ring buffer rather than the full journal.
- Offline tolerance: the journal is durable locally; the server mirror ingests
  in batches whenever reachable. No live server, no data loss.

## 13. Manual user changes

The user is just **another actor** on the same paths — no special machinery:

- Edits in the platform UI (Monaco) → daemon API → the daemon writes the new
  `AssetVersion` **directly to the store**, correctly attributed at the
  source and valid for any branch, checked out or not; it is projected into
  the worktree only when that branch is checked out and no agent session
  holds the worktree (§11's lock). The watcher is bypassed on purpose — it
  exists for edits the daemon *didn't* make. Routing daemon-originated edits
  (UI edits, future param edits, `rename --rewire`) through the worktree would
  rewrite files under a working agent and launder known authorship through
  §11's attribution heuristic. Deferral opens a lost-update window the model
  must own: while projection waits, the worktree file is stale, and an agent
  edit derived from that stale content would silently advance the head over
  the UI edit. §11's watcher parent-check closes exactly this — the
  divergence surfaces as a flagged conflict with fork-my-edit suggested, the
  same menu as the optimistic locking below, covering the store→worktree
  direction. Deferred projections also survive daemon stops: §11's
  reconciliation recognizes a worktree file equal to a known version as a
  pending projection and completes it rather than re-accepting it as an
  edit.
- **Creation never blocks on a name.** "Add cell" in the UI mints the `uid`
  immediately — identity settled at birth — plus a placeholder slug
  (`untitled_1`; auto-suffixing handles collisions) and writes the scaffold
  file (§2's scaffolding path). A brand-new cell has no consumers, so
  renaming is trivially safe at first; once the user writes the class, the
  daemon suggests a derived slug (snake-case of the class name, or from the
  docstring) as a one-click formatter-style rename, and `rename --rewire`
  covers the late case. Placeholder-named cells are flagged softly as
  hygiene — the Jupyter "Untitled" plague is the failure mode this guards
  against, and agents are instructed via `AGENTS.md` to always name cells.
- Edits in any external editor → watcher path directly. Vim users and agents
  are indistinguishable to the store.
- **No param or volatility handles in the v1 UI** (§2's dormancy). Params
  are data in the schema, so an inspector edit — tweak `lr` without opening
  code, landing as an `edit-asset` version with a params-only diff — is a
  natural later feature the slots already fit; v1 ships without it, and
  editing a param is editing the cell file (Monaco or watcher path above).
- Concurrency: per-cell optimistic locking — UI edit carries the base
  `definitionHash`; on conflict (agent got there first) the user chooses
  overwrite / fork-my-edit; default suggestion is fork, which is on-brand.
- User actions get auto-`intent` ("edited train_model params") unless provided.

## 14. Venv management

**Env is recorded provenance, not a memo-key ingredient:**

- **Per-workspace env managed by uv**: `pyproject.toml` + `uv.lock` live at
  the workspace root (§4) — the flow is monolithic and carries no env, the
  same way a notebook shares its project's env; every flow in the workspace
  shares the one venv. The store does not version the env files (workspace
  files belong to the user's VCS, §4/§8d), but env changes are still
  observed and journaled as transactions ("added lightgbm 4.3"), visible in
  the session tree like any other change.
- **The workspace venv contains no lumlflow code at all.** Cell files import
  nothing (§2), and the kernel executor doesn't need to be importable by
  user code, only runnable: the daemon launches it in the venv's interpreter
  with the kernel's code path-injected from the tool install. The product
  (daemon, store, CLI, server) stays a tool install (uvx/pipx-style), and
  the workspace's `pyproject.toml` lists only the user's own libraries plus
  the serde libraries its flows' kinds need (pyarrow, safetensors, ... —
  ordinary
  ecosystem deps, scaffolded as needed, §3, and executed kernel-side: the
  daemon never imports kind plugins or serde, §3). The **luml SDK is not
  under the no-venv rule** — that rule is about lumlflow, the product; luml
  is an ordinary package, scaffolded into the venv like a serde lib when
  native outputs are declared (§3), importable by the kernel and by user
  code alike. The typing stubs are an
  optional dev dependency for IDE checking (§2). This works precisely
  because of the daemon/kernel process split (§8) plus AST-only extraction
  (§2): the daemon touches the workspace venv only to spawn the kernel —
  watching, hashing, acceptance, and the store all run without it.
- **One venv, one kernel — the live env is workspace-global per kernel
  lifetime.** With the env at the workspace root there are no per-branch
  lockfiles and no branch/env matrix to pretend about: each materialization
  records the **actual live venv's** lock hash as provenance, and that is
  the whole story. (The earlier draft's branch-versioned lockfiles and its
  "env mismatch — restart under this branch's lock" scheduling flag die
  with the per-flow env; the provenance badge below covers what remains.)
- **Mid-run installs do not invalidate executed cells.** Their materializations
  are facts about the env they ran under; each materialization records the env
  (lock hash) it ran under as provenance. Including env hash in the memo key
  would nuke every cache on any `pip install` — wrong default for exploration.
  Cells that genuinely bind to env details can opt in: `env_sensitive = True`
  adds the lock hash to that cell's memo key.
- **The active-imports trap is a detection problem, not an invalidation
  problem**: installing a new version of an already-imported package silently
  keeps the old module live. The daemon compares `importlib.metadata` versions
  against loaded `sys.modules` after env transactions and raises a
  **"restart kernel to apply"** banner (UI + `lumlflow status`) instead of
  pretending. On restart, the env is rebuilt from `uv.lock` — that is the
  reproducibility boundary, and it's honest: within a kernel lifetime, env is
  whatever imports say; across restarts, the lockfile is law.
- Provenance mismatch surfacing: a materialization whose recorded env differs
  from the current lock renders a subtle badge ("computed under older env") via
  the integrity-warning channel — informative, not invalidating.

## 15. Communicating scope/focus to the agent

Three mechanisms, smallest first:

1. **`lumlflow context` (CLI) / `session://focus` (MCP resource)** — a
   token-budgeted brief the agent is instructed (via `AGENTS.md`) to read at
   turn start: active branch + checkpoint, the user's current focus (selected
   asset, open comparison, viewport), unsynced assets *with causes*, last
   failures with tracebacks, preflight cost of the pending dirty set, and the
   few most recent transactions with intents. Stable ids everywhere so the
   agent can address anything it sees.
2. **Sliced queries instead of dumps** — the graph and history are unbounded,
   so the CLI serves neighborhoods: `lumlflow graph --around train_model --depth 2`,
   `lumlflow cells --unsynced`, `lumlflow tree --branch exp/lr-sweep --since <step>`,
   `lumlflow diff branchA branchB` (which reports *definition* divergence —
   someone edited code — distinctly from *materialization* divergence — same
   code, different inputs; the latter is transitively closed and covers most
   of the graph below any edit, so collapsing it is what keeps a 20-branch
   diff readable).
3. **User focus → agent ships in v1; agent presence is deferred past v1.**
   The direction that is core UX: UI gestures ("fix this", "explain this
   diff") inject an explicit context payload (asset id, version, error) into
   the agent invocation rather than hoping the agent guesses — these become
   MCP prompts / CLI arguments, and `lumlflow context` carries the user's
   current focus (item 1). The other direction — per-actor presence records
   (`activeBranchId`/`activeAssetId`) rendering agents in the UI, and
   multi-agent choreography generally — is deferred past v1: the v1
   concurrency model is one user + one agent on one branch, so there is no
   fleet to render yet.

The `intent` strings on transactions close the loop in the other direction:
they're what makes the session tree navigable by the *user*, so requiring them
from agents (CLI `-m`, MCP argument) is a hard rule, not politeness.

## 16. Launch surfaces: experiments + workspace

Launching lumlflow serves two top-level surfaces, side by side:

- **Experiments** — the traditional tracker view, unchanged: runs, metrics,
  comparisons over collections. Flows feed it through their `experiment`
  outputs (§3), so it needs nothing new from the flow runtime.
- **Workspace** — a file browser rooted at the directory lumlflow was
  launched from (the default; navigating up to parents and across the tree
  is free). It renders real files — data, notebooks, code — and each
  `.flow` directory appears as a **single file-like entry**, exactly as an
  `.ipynb` renders in Jupyter's tree: monolithic (§4), never expanded into
  its internals. Opening one enters the flow session view (canvas,
  branches, timeline); other files are listed as context, with viewers a
  later nicety, not v1 scope.

Opening a flow is the entire ceremony: the daemon for that flow starts if
not running, the kernel spawns on first demand, and the session attaches —
§8's invisibility invariant. There is no kernel picker, no connect dialog,
no runtime status to manage; everything the browser sees is wired through
the daemon (§10–§12), which is also what lets the platform later serve the
same session remotely (§5's sync) without a different wiring story.

The workspace view is where §4's model becomes visible: the workspace is
the substrate (shared code, data, env) and flows are documents sitting on
it. Multiple flows in one workspace share the substrate and the env (§14)
but keep fully independent stores, branches, and histories.

---

## Suggested build order (v1 cutlines)

1. **Store + journal** (`.lumlflow/`: versions, branches, transactions, CAS,
   previews) with `fork/switch/rewind` as pure store ops — testable without a
   kernel.
2. **Kernel + scheduler** (lazy reactivity, memoization, early cutoff,
   serial executor) against the store; scratch REPL.
3. **DSL loader + watcher** (AST extraction, validation, versioning of direct
   file edits, single worktree).
4. **CLI** (`status/tree/run/fork/switch/diff/context`, `cells new/edit`,
   `--json` everywhere) + generated `AGENTS.md` → first end-to-end
   agent-driven session; the Tier-0 quickstart gate (§10) is measured here,
   not at the end.
5. **Daemon streaming → lumlflow UI** (journal over WebSocket, replace concept
   fixtures with live sessions; the workspace browser beside the existing
   experiments view — §16), LUML-native outputs (kernel-staged,
   daemon-uploaded — §3).
6. **MCP wrapper (including `new-cell`/`edit-cell`, which makes worktree-less
   sessions real — §6/§10), strict/paranoid modes, basic
   sandbox profile (no-network mode, FS allowlist — §8's security note makes
   this v1, not deferred), sweeps (agent-driven — param slots exist in the
   schema; no sweep or param UI in v1, §2/§13).**

Deferred past v1: track-parent forking (sparse-overlay design recorded, §5),
whole-branch merge (per-asset adopt is the v1 story, §5), multi-actor
presence rendering and choreography (v1 is one user + one agent on one
branch, §15), per-actor worktrees (design reserved), parallel executors,
non-Python kernels (protocol reserved), flow-as-LUML-artifact export, remote
sync/collaboration, richer sandbox profiles (seccomp/container-grade
isolation) beyond the v1 no-network/FS-allowlist profile, param/volatility
surfaces (UI handles, inspectors, sweep UIs — schema slots ship dormant,
§2/§13), volatility-driven scheduling beyond the `external` rule (§8b),
value eviction and retention-window controls (persist-everything is the v1
policy, §7).

## Open questions (not blocking, worth deciding early)

- **Hash cost on huge values**: blake3-while-serializing covers persisted
  values; for unpersisted giants (`"persist": False`, §3) we need version
  tokens instead of content
  hashes — which weakens early cutoff for their consumers. Acceptable?
- **Internal data folder access surface** (§4): the folder itself is
  decided — allowed, unversioned, travels with the flow — but the
  cell-facing spelling is open: `ctx.flow_dir / "data"` vs a dedicated
  `ctx.data` handle, and whether/when reads upgrade to hashed, declared
  file inputs.
- **Workspace watch scope** (§8d): the exclusion list and depth for the
  workspace tree hash need tuning against real project layouts (monorepos
  especially) before the blunt hash gets noisy; per-cell `uses` narrowing
  is the recorded fix.
- **Disk growth under persist-everything** (§7): at what scale the
  append-only CAS first hurts in practice, and which future control
  (eviction-to-cold vs a retention window) to reach for then — measure with
  real flows before building either; neither may gate a switch with a
  prompt (§5).
- **Transaction grouping heuristic for watcher edits**: time-window vs.
  explicit `agent begin/end` bracketing vs. both (proposed: both, window as
  fallback).
- **Worktree layout vs. agent CWD conventions**: some CLIs dislike working in
  dot-directories; `worktrees/` naming and the default single-worktree path
  need a usability pass with Claude Code/Codex/Gemini CLI early.
- **Windows in CI from the first store/watcher milestone**: the watcher,
  write-back, and capture assumptions (§8's portability policies) need
  validation there early — not a port at the end.
- **Preview spec per asset kind**: needs a versioned schema (it's the sync
  payload and the UI contract); seed from the mockups' `ArtifactValue` shapes,
  then let the open kind registry own it.
- **Naming**: resolved — `.lumlflow/` store dir, `lumlflow <verb>` CLI,
  `LUMLFLOW_ACTOR`; cell files import nothing (§2), so no import-namespace
  question exists. The package split is the
  rationale: `luml` is the SDK dependency the runtime bundles, `lumlflow` is
  the standalone product — so the CLI is its own top-level command and no
  alias question remains.
- **The minimal distribution's name** — retired: the structural DSL (§2)
  resolved it by dissolution. There is nothing to split — cell files import
  nothing and the flow venv carries no lumlflow code (§14); the only name
  left is the typing-stubs dev package, a dev-tool detail rather than a
  design question.
- **The reopened mockup decisions** (staleness display default §8 — bounded
  by "never silently stale": transitive staleness must stay discoverable,
  only the emphasis is open; open runtime kind registry §3) — cheap to keep
  open at
  the runtime level, but the UI needs a default for each before the first
  live session. The fork-pin default is no longer among them — resolved by
  cut, track-parent being out of v1 (§5).
- **Executor reset-hook scope**: which process-global resets (figures, env,
  logging deltas, device caches) pay for themselves — they run between every
  pair of materializations, so measure rather than guess.
- **Custom JS renderers (v2)**: the sandboxing/packaging model for third-party
  frontend code, for kinds whose primitive composition isn't expressive
  enough.
- **Merge UX**: whole-branch merge is cut from v1 — per-asset adopt is the
  whole story (§5), with pick-a-side for definition conflicts. The live
  question is narrower: whether textual three-way merge of cell source is
  ever worth building at all, given that an agent can simply be asked to
  reconcile two versions of a cell.
- **`uid` write-back ergonomics**: the daemon editing files the agent is also
  editing is formatter-shaped territory — §11's protocol (atomic single-line
  insert, idempotent, converges after races) needs testing against the actual
  write patterns of Claude Code/Codex/Gemini CLI before v1 (fallback if it
  fights them: record the `uid` mapping in `flow.yaml` only, at the cost of
  weaker copy/move detection).
