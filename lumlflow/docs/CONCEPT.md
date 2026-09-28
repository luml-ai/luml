# Concept 1 — Canvas + drawn rail

Former route: `/flow/railroad`

## The mental model

Two surfaces. Left: **the rail** — the session's history *drawn*, a trunk with stops and
forks diverging from the point they split at. Right: **the canvas** — one slice at a time,
output-first cards, laid out once and never again.

The rail is the only navigator. There is no fork dropdown and no step slider: a fork is not
a name you pick from a list, it is a line you can see leaving the trunk, and time is not a
scrubber under the canvas, it is the axis the rail is drawn along. Selecting any stop does
both things at once — shows that fork's slice and seeks playback to that moment. The header
above the rail names the fork you are on; the emphasized lane shows it spatially.

## How the rail is drawn (`railLayout.ts`)

- **Lanes are branches.** Trunk leftmost, forks to the right in fork order, each in its
  `Branch.color`. A fork's curve leaves the parent lane at the step it actually split.
- **Stops are settled states** — `checkpoints()` from the engine, plus fork points and lane
  heads. Not every transaction deserves a stop: consecutive routine transactions fold into a
  single small hollow marker carrying who and what (`3 edits · codex-1`, assets in the
  tooltip), because a bare hidden count is not scent. A failed materialization tints its
  marker red without earning a full stop.
- **A fork with no transactions of its own** (the generated fixtures put every transaction
  on the trunk) still gets a head stop, placed at the step where the newest version it
  *selected differently from its parent* was authored — the lane spans the work it contains.
- **Every position is a pure function of the full session.** Selection and playback change
  stroke, opacity and label visibility — never geometry. Stops beyond the current playback
  step render pale and hollow, which is what lets the same drawing double as the scrubber:
  click behind the head and the future literally fades until you return to it.
- The live head carries a slow pulse; the current position a ring in the lane's colour.

Transport is three icon buttons above the rail (previous stop, play/pause, next stop).
`PlaybackBar` — with its slider — is untouched and still used by concepts 2 and 3.

## Output-first cards

The materialization is the body of every card; code stays behind the Source accordion.
A materialization with several outputs shows its most readable one (`artifact.ts`:
experiment > eval > plot > frame > note > metric > model) — "first output wins" used to
show a parameter dump where the training run was.

**Experiment and eval assets** render as findings: headline metrics as large figures, metric
curves as real charts (`MetricCurve.vue` — gridlines, min/max, hover readout; palette order
validated for colour-vision-deficiency separation). Because the card cannot hold everything,
it carries **a link out to the tracker** (`/experiments/:groupId/:experimentId`): an
experiment materialized in a flow *is* a tracked experiment, so the natural reference is the
surface that already exists for it — traces, attachments, comparisons and all. A maximized
dialog was rejected because it would re-embed a whole product inside a card; the link is
honest about the boundary. In this prototype the group is the flow's project and the run id
is the run name (for evals, the materialized version id); a real integration would store the
tracker's run id on the materialization.

## What breaks at scale, and how it degrades

Tried on the `large` fixture (~150 assets, 20 branches):

- **Lanes compress** from 24px to 12px apart past 8 forks so the label column stays inside
  the card; per-lane branch-name labels turn off past 8 lanes (tooltips remain) because
  twenty names over twenty lines is noise, not scent.
- **The rail becomes a vertical scroll surface** (~60 rows). That is deliberate: the time
  axis scrolls, the marker auto-scrolls into view, and folding keeps the row count at
  checkpoints + folded runs rather than one row per transaction.
- Archived branches are dropped from the rail entirely.
- The canvas findings from the previous round stand: it needs semantic zoom past ~100 nodes,
  and the fan-out from `Split` to twenty models is still a hairball.

## What is real vs. what is faked

All numbers come from `engine.ts` (`checkpoints`, `resolveSlice`, `unsyncedCause`,
`cacheSkipSet`, `preflightCost` via the cache banner). Faked: the tracker link does not
resolve to real tracker data, and export renders a preview without writing anything.

## What I would still cut or fix

- The Canvas/Notebook toggle could arguably fold into one adaptive view.
- Fork stubs whose head step collides with a trunk row suppress their name label; a smarter
  label layout (nudge within the row, never across rows) would keep more names visible.
- `buildRailLayout` runs on every session change; fine here, but a large live session would
  want it memoised alongside the slice cache the engine already needs.
