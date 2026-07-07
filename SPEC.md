# Proposals

Two user-visible bugs affect the experiments UI. Both apps that ship it — the main frontend (`frontend/`, snapshot/compare views) and the lumlflow dashboard (`lumlflow/frontend`) — render experiments through the shared workspace package `@luml/experiments` (`extras/js/packages/experiments`), so both exhibit both bugs and both are fixed by correcting the shared package.

**Bug 1 — metric line charts show invalid values.** Dynamic metric charts are drawn with Plotly cubic-spline interpolation (hardcoded `shape: 'spline', smoothing: 1.2`). Splines overshoot and undershoot between real data points, so the rendered curve passes through values that were never logged — a loss curve can appear to dip below its true minimum or oscillate where the data is monotone. The fix is to render straight lines between the actual points (no smoothing, no toggle — decided with the user). Relatedly, metric series are silently decimated when large (every Nth point kept: client-side above 50k points, lumlflow server-side above 1000 points); the package already has a "contains aggregated data" warning for this, but the API path discards the server's `subsampled` flag so the warning never appears, and the browser-side snapshot query reads points without ordering by step. Both transparency gaps are in scope; the decimation strategy itself is not (it keeps real values and does not distort them).

**Bug 2 — span durations in the trace view are sometimes wrong.** Span durations are computed and formatted in the shared package, and several defects combine to make the span view incorrect:
- The duration formatter has no microsecond tier: any span between 1µs and ~0.5ms displays as "0ms".
- Span timestamps are epoch nanoseconds (~1.8e18), which exceed JavaScript's safe-integer range; every JS ingestion point stores them as `number`, so each timestamp independently rounds by up to ~±512ns. Subtracting two rounded values can yield nonsense sub-microsecond durations, including negatives, which the formatter prints verbatim (e.g. "-256ns").
- The waterfall bar geometry divides by the trace time range, producing NaN widths when the range is zero (instantaneous or single-point traces), and its guards treat a legitimate value of 0 as "missing".

The fix: make the formatter correct and honest at the precision it displays (add a µs tier, floor display at "<1µs", never print negatives or tier-boundary artifacts), and make the waterfall math total — defined for zero-range traces, absent-vs-zero distinguished. We deliberately do **not** introduce BigInt timestamp plumbing (custom JSON parsing, sql.js BigInt mode, interface changes across two providers): the float noise is sub-microsecond, invisible once the display floor is "<1µs", so the plumbing would buy no user-visible correctness. As a small adjunct, the Python SDK's docstrings and type comments claim `execution_time` is in *seconds* while the value is nanoseconds — those annotations are corrected so the unit confusion stops propagating.

# Design

## Where the code lives

All chart and trace rendering is in `@luml/experiments` (`extras/js/packages/experiments`), consumed by both apps via npm workspaces. Fixes land there once; no lumlflow-frontend or main-frontend component changes are required. The lumlflow FastAPI server already reports `subsampled` in its metric-history response and the Python SDK already orders metric history by step (`sdk/python/sdk/luml/experiments/backends/sqlite.py:2428`), so backend behavior is unchanged; only annotations in the SDK are touched.

## Metric charts

- `DynamicMetricsItem.vue` (`src/components/dynamic-metrics/`) builds the Plotly trace config. The line rendering becomes linear — no spline, no smoothing parameter. This is the single rendering site (the enlarged "scaled" view reuses the same computed config). Nothing else about the chart (colors, hover, layout, markers-for-single-point) changes.
- `ExperimentSnapshotApiProvider.prepareMetricData` (~line 420) currently hardcodes `aggregated: false`; it must propagate the API response's `subsampled` flag into the metric's `aggregated` field so the existing warning icon in `DynamicMetricsItemContent.vue` appears whenever the server decimated the series.
- `ExperimentSnapshotDatabaseProvider.getModelDynamicMetricData` (~line 781) queries `dynamic_metrics` without an order clause; points must be returned in ascending step order. (The API path already gets ordered data from the SDK.)

## Span durations

Formatting contract for `getFormattedExecutionTime` / `getFormattedTime` (`src/helpers/helpers.ts`), input in nanoseconds, possibly fractional (the sqlite path parses `execution_time` as float), possibly negative (float64 rounding artifact):

- below 1µs (including zero and negative): display `<1µs` — sub-microsecond figures derived from epoch-ns subtraction are precision noise and must not be presented as exact.
- 1µs up to 1ms: integer microseconds, e.g. `42µs`.
- 1ms up to 1s: milliseconds as today, e.g. `500ms`.
- 1s and above: unchanged tier structure (seconds with two decimals, then `Xmin Ys`, `Xh Ymin`, `Xd Yh`).
- No tier-boundary artifacts anywhere: a value must never render as `1000µs`, `1000ms`, or `60.00s` — rounding at a tier edge promotes into the next tier.

Waterfall geometry (`TraceSpan.vue` offsets, `getSpansTimes` in `src/store/evals/index.ts`, min/max threading through `ExperimentSnapshot.vue` → `TraceDialog.vue` → `TraceSpans.vue`):

- Guards must distinguish absent min/max from a legitimate value of 0 (no falsy checks on timestamps).
- Zero time range (all spans instantaneous at the same nanosecond, e.g. MLflow in-progress spans whose end is fabricated as start): no NaN — bars render deterministically at zero offset and full width.
- Computed offset/width percentages are clamped to the valid 0–100 range.
- An empty span list must not propagate `Infinity`/`-Infinity` sentinels out of `getSpansTimes`.

Out of scope, unchanged: the trace-level `execution_time` semantics (wall-clock envelope `max(end) − min(start)` computed exactly in int64 SQL), span tree building, and the MLflow bridge's fabricated end times.

## SDK unit annotations

The nanosecond value is misdocumented as seconds in `sdk/python/sdk/luml/experiments/backends/data_types.py` (`execution_time: float  # seconds`) and in the `get_traces`-area docstrings of `backends/sqlite.py` (prose and example values that read as seconds); `tracker.py`'s docstring example references a nonexistent `execution_time_ms` field. All are corrected to state nanoseconds and use plausible ns example values. Comment/docstring-only — no behavior change, no schema change.

## Testing

`@luml/experiments` currently has no test infrastructure. It gets its own vitest setup (config + `test` script in the package, jsdom environment), following the main frontend's conventions (vitest 3, `@vue/test-utils`, tests colocated under `__tests__/`). New behavior is covered there: formatter unit tests, chart-trace-config tests, provider mapping/ordering tests, and waterfall geometry tests (component-level where needed). lumlflow's Python suite is untouched (no Python behavior changes).

# Scenarios

## Scenario: Metric line renders only real values
**Given** a metric series with points (1, 0), (2, 10), (3, 0)
**When** the chart trace config is built by `DynamicMetricsItem`
**Then** the line is linear with no smoothing, so the rendered path cannot exceed the range of the logged values

## Scenario: Server-side downsampling shows the warning
**Given** the lumlflow API returns a metric history with `subsampled: true`
**When** the metric is prepared by the API provider and rendered
**Then** the metric's `aggregated` flag is true and the "contains aggregated data" warning icon is shown on the chart card

## Scenario: Full-resolution data shows no warning
**Given** the lumlflow API returns a metric history with `subsampled: false`
**When** the metric is rendered
**Then** no aggregated-data warning is shown

## Scenario: Snapshot metric points come back in step order
**Given** a snapshot database whose `dynamic_metrics` rows for a key are stored out of step order
**When** the database provider fetches the metric data
**Then** the returned x values are in ascending step order

## Scenario: Microsecond-range span no longer shows 0ms
**Given** a span whose duration is 40,000ns (40µs)
**When** its duration is formatted
**Then** it displays "40µs", not "0ms"

## Scenario: Sub-microsecond and negative durations display as a floor
**Given** durations of 500ns, 0ns, and −256ns (float rounding artifact)
**When** each is formatted
**Then** each displays "<1µs" — never a negative value

## Scenario: No tier-boundary artifacts
**Given** durations of 999,999ns, 999,600,000ns, and 59,999,000,000ns
**When** each is formatted
**Then** the outputs are "1ms", "1.00s", and "1min 0s" respectively — never "1000µs", "1000ms", or "60.00s"

## Scenario: Fractional nanosecond input is handled
**Given** a trace `execution_time` of 1234.56 (float from the sqlite path)
**When** it is formatted
**Then** a clean value is displayed with no fractional nanoseconds leaking into the output

## Scenario: Normal tiers are preserved
**Given** durations of 500ms, 5.4s, and 90s
**When** each is formatted
**Then** the outputs are "500ms", "5.40s", and "1min 30s"

## Scenario: Instantaneous trace renders without NaN
**Given** a trace whose spans all share the same start and end timestamp (zero time range)
**When** the waterfall renders
**Then** no NaN reaches the DOM; each bar renders at zero offset and full width

## Scenario: Zero is a valid timeline boundary
**Given** span timestamps where the trace minimum time is 0 (test-constructed) and the maximum is positive
**When** bar offsets are computed
**Then** offsets are computed from the actual values rather than short-circuiting to 0 via a falsy check

## Scenario: Trace with no spans
**Given** a trace whose span list is empty
**When** min/max span times are derived
**Then** no Infinity/−Infinity sentinel reaches the waterfall components

# Tasks

- [ ] Add vitest tooling to the experiments package
  - [ ] Add vitest config, jsdom environment, and a `test` script to `extras/js/packages/experiments`, following `frontend/vitest.config.ts` conventions
  - [ ] Add a smoke test for an existing pure helper to prove the setup runs
- [ ] Render metric lines without spline smoothing
  - [ ] Change the Plotly line config in `DynamicMetricsItem.vue` to linear with no smoothing
  - [ ] Add a test asserting the computed trace config uses a linear line shape and carries the exact input x/y values
- [ ] Surface metric downsampling and order snapshot points
  - [ ] Propagate the API `subsampled` flag into `aggregated` in `ExperimentSnapshotApiProvider.prepareMetricData`
  - [ ] Add ascending step ordering to the metric query in `ExperimentSnapshotDatabaseProvider.getModelDynamicMetricData`
  - [ ] Add tests for the flag mapping and the ordering
- [ ] Fix span duration formatting
  - [ ] Rework `getFormattedExecutionTime`/`getFormattedTime` in `helpers.ts` per the formatting contract (µs tier, "<1µs" floor, negative/fractional input, no boundary artifacts)
  - [ ] Add exhaustive formatter unit tests covering every tier and boundary from the scenarios
- [ ] Harden span waterfall geometry
  - [ ] Replace falsy timestamp guards with absent-vs-zero checks and clamp offsets in `TraceSpan.vue`
  - [ ] Make zero-range traces render deterministically and keep Infinity sentinels from escaping `getSpansTimes`/`ExperimentSnapshot.vue`
  - [ ] Add geometry tests (zero range, zero minimum, empty span list, normal trace)
- [ ] Correct execution_time unit annotations in the SDK
  - [ ] Fix the seconds-vs-nanoseconds comments and docstring examples in `data_types.py`, `sqlite.py`, and `tracker.py`
