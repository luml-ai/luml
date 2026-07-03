# Proposals

## Problem

LUML's **Express Tasks** module (the no-/low-code AutoML surface) ships four task types today: Tabular Classification, Tabular Regression, Prompt Optimization, and Notebooks. The frontend already advertises a fifth — **Time Series Forecasting** — but it is a dead placeholder card (`frontend/src/constants/constants.ts`, `isDisabled: true`, button label "coming soon"). Users who want to predict future values from historical time-series data (sales projections, demand planning, financial forecasting) have no way to do it on the platform.

## Solution (at a glance)

Implement Time Series Forecasting as a first-class Express Task built on **SARIMAX models with frozen weights**:

1. **Train + evaluate + download** — a 3-step flow (Upload → Configure → Evaluate) that fits SARIMAX models entirely client-side in the WASM Pyodide worker (`wasm/packages/dfs_webworker`), with **fully automatic model configuration** (trend/differencing, seasonality, and ARMA orders are auto-detected; the user picks only the column roles and the date frequency), and produces a portable `.luml` (FNNX) artifact.
2. **Fixed-weight prediction on fresh history** — the artifact stores the fitted parameter vectors as plain JSON, **never the training data**. Every prediction call supplies a window of recent history (≥ a model-derived minimum length) plus a horizon (and, for models with known-future columns, those columns' future values); the frozen model is applied to that history via Kalman filtering with **fixed parameters — no refitting, no optimization** — and forecasts beyond the window's last date. Users can therefore keep using one trained model on ever-newer historical intervals.
3. **Two-stage multivariate support with known-future covariates** — at setup the user marks which auxiliary columns will be **known in the future** (planned prices, scheduled promotions, calendar features). Each unmarked auxiliary gets its own univariate SARIMAX and is auto-forecast at prediction time; marked columns get no model of their own — the caller supplies their future values with every prediction. Both kinds feed the target model as **exogenous regressors**.
4. **Self-describing export** — the artifact is a standard FNNX pyfunc bundle carrying its producer tags, metrics, model configuration, and training-chart payload, so the deferred Runtime/Registry/Deployment integrations can be added later without retraining exported models.

## Why this approach

- **SARIMAX is the requested model family, and "fixed weights on new data" is native to it.** statsmodels state-space models separate the parameter vector from the data: a model spec can be rebuilt around any endog series and evaluated with a previously fitted parameter vector (filtering only). This is exactly "ARIMA with fixed weights over new historical intervals" — deterministic, fast, and refit-free.
- **statsmodels is the only viable library.** It ships in the Pyodide 0.26.2 distribution (statsmodels 0.14.2, with scipy/patsy deps available as wasm wheels), so training runs in the browser worker. Every alternative fails Pyodide: pmdarima (C extensions, not in the distribution), statsforecast (requires numba), prophet (requires cmdstan), sktime (wraps statsmodels anyway). The one piece pmdarima would have provided — automatic order selection — is re-implemented as a bounded stepwise AICc search (Hyndman–Khandakar style).
- **JSON parameters keep the codebase convention.** Like prompt-optimization, the model is stored as JSON in the bundle's `extra_values` and reconstructed at serve time — no pickle, no sklearn/statsmodels results-object serialization, no version coupling of binary formats.
- **Mirror the existing tabular/prompt-opt pattern.** Same worker `Router` dispatch, same `PyfuncBuilder` serialization path. No backend training infrastructure.

## Out of scope (v1)

- **Runtime upload-for-inference** — v1 delivers training, the evaluation dashboard, and model export only. The exported artifact is fully self-describing, so these integrations land later without retraining.
- Multiple competing algorithms / AutoML model selection beyond the automatic SARIMAX configuration.
- VARMAX joint multivariate modeling (statsmodels VARMAX lacks seasonal orders and is numerically fragile; the two-stage exog design covers the cross-series use case).
- Automatic frequency detection (the user explicitly picks day/week/month/quarter/year).
- Multiple seasonal periods per series (daily data gets the weekly cycle only, not day-of-year; noted as a known limitation).
- Manual override of detected orders/seasonality (fully automatic; the detected configuration is reported read-only).
- Backend (`backend/luml`) or `sdk/python` changes — all new code lives in `wasm/packages/dfs_webworker` and `frontend`.

---

# Design

## Architecture overview

The browser flow (Upload → Configure → Evaluate) drives a new forecasting module in the WASM worker (`wasm/packages/dfs_webworker`), which auto-configures and fits the SARIMAX pipeline, runs rolling-origin cross-validation, and serializes the result to a `.luml` pyfunc bundle — parameters as JSON in `extra_values`, producer tag `dataforce.studio::forecasting:v1`, env pinning statsmodels/scipy/pandas/numpy. Prediction — the worker route behind the Evaluate screen and the exported pyfunc alike — takes `{history, horizon[, future]}` (the `future` values for known-future columns) and returns `{forecast}` via fixed-parameter filtering.

The split of responsibilities matches the tabular task (`wasm/packages/dfs_webworker/dfs_webworker/tabular.py` + `frontend/src/components/express-tasks/tabular/*`) and the prompt-optimization serialization precedent.

## 1. Forecasting engine (WASM, Python)

New module `wasm/packages/dfs_webworker/dfs_webworker/forecasting.py` holding the forecasting pipeline. The user supplies only the column roles — date column, target column, optional auxiliary columns, of which any subset may be marked **known-future** (values the user will supply at prediction time) — and the frequency (`day|week|month|quarter|year`); everything else is detected.

### Model structure (two-stage)

- One univariate SARIMAX per **auto-forecast auxiliary** column (auxiliaries not marked known-future), each independently auto-configured. **Known-future** columns get no model of their own.
- One SARIMAX for the **target** with all auxiliary columns — both kinds — as exogenous regressors (aligned actual values at training time).
- At prediction, auto-forecast auxiliary models are filtered on the provided auxiliary history and forecast `horizon` steps; known-future columns take their caller-supplied future values as-is. The target model is filtered on the provided target history with the actual auxiliary history as exog, then forecasts with the auxiliary **forecasts** plus the supplied known-future values as future exog. (Training on actual exog while predicting with forecast exog is the standard ARIMAX trade-off for auto-forecast auxiliaries; known-future columns avoid it entirely.)
- With no auxiliary columns, the pipeline is a single univariate SARIMAX. With every auxiliary marked known-future, there are no auxiliary models at all — only the target model.

### Automatic configuration (per series)

Detection follows the auto.arima (Hyndman–Khandakar) recipe, implemented with statsmodels primitives:

- **Seasonal period `s`** comes from the user-picked frequency: day→7, week→52, month→12, quarter→4, year→none. If the series is shorter than two full cycles (plus a small buffer), seasonal modeling is **disabled automatically** for that series rather than erroring.
- **Seasonal differencing `D`** (0 or 1): STL-decompose the series at period `s` and compute the seasonal-strength statistic (variance-ratio form); `D = 1` when strength exceeds the conventional ~0.64 threshold.
- **Trend differencing `d`** (0–2): repeated KPSS tests on the (seasonally differenced) series — difference until stationarity is not rejected, capped at 2.
- **Deterministic term**: constant when `d + D == 0`, drift when `d + D == 1`, none when `d + D ≥ 2` (the search may additionally compare with/without the term by AICc).
- **Orders `(p,q,P,Q)`**: stepwise neighborhood search minimizing **AICc**, starting from the standard auto.arima starting points, bounded to `p,q ≤ 3` and `P,Q ≤ 1`, with a hard cap of roughly 25 candidate fits per series (browser compute budget). Fits use stationarity/invertibility enforcement (required for stable fixed-param filtering later) and a bounded optimizer iteration count; candidates that fail to converge are skipped. If every candidate fails, fall back to a plain `(0,d,0)` + deterministic-term model, which always fits.

The detected configuration per series — orders, seasonal order, seasonal period, deterministic term, and the resulting minimum history length — is returned to the frontend and embedded in the artifact as the read-only **model configuration report**.

### Fixed weights: serialization and prediction

- The pipeline serializes to a **fully JSON-serializable spec**: column roles, frequency, and per series the model orders, seasonal order, deterministic term, the fitted **parameter vector** (list of floats with parameter names), and the minimum history length. No training observations are stored.
- Deserialization rebuilds the pipeline from that spec. Prediction constructs each statsmodels model around the **caller-supplied history** and evaluates it with the stored parameter vector via **filtering only** — the optimizer never runs at predict time, so predictions are deterministic and fast.
- Training (`fit`, auto-configuration, cross-validation) is the only code path that needs the optimizer; prediction needs statsmodels/scipy/pandas/numpy but no fitting machinery beyond the Kalman filter. Both sides use statsmodels — there is no pure-numpy serving path in this design (reimplementing the Kalman filter was rejected as high-risk); the serving env consequence is covered in §2.

### Minimum history (the predict-time contract)

Every prediction must supply enough history to initialize the model's lags and innovations. Per series the hard floor is `d + D·s + max(p + s·P, q + s·Q) + 1` observations; the **pipeline-level `min_history` is the maximum across the target and all auto-forecast auxiliary models** (they share the same input rows). Known-future columns have no model of their own, but their historical values must still be present in every history row — filtering the target model over the history requires its full exog history. `min_history` is computed at train time, reported to the UI, embedded in the artifact metadata, and **validated on every predict call** with a clear error naming the required row count. A UI hint additionally recommends at least one extra full seasonal cycle when seasonal terms are present (non-blocking).

Training has its own floor: a hard minimum of 12 usable rows (clear error below that), with the existing soft UI guard of ~30 rows at upload.

### Prediction semantics

`predict(history, horizon, future)`:
- `history`: wide records `[{date, <target>, <aux>…}]` — including the known-future columns' historical values. Validated: all required columns present and numeric, dates parse, no duplicates, and the dates form a **regular grid at the model's frequency** (sorted internally; gaps are an error).
- `horizon`: positive integer — number of consecutive periods to forecast beyond the last history date. Forecast dates are generated from the last history date at the model frequency (weekly grids anchor to the history's weekday; monthly, quarterly, and yearly grids anchor to period starts).
- `future`: **required iff the model has known-future columns, rejected otherwise.** Records `[{date, <known-future col>…}]` carrying exactly the known-future columns, numeric, covering **exactly** the `horizon` forecast dates — no gaps, duplicates, extra dates, or extra columns; violations produce clear errors naming the offending dates or columns.
- Output: wide records `[{date, predicted_<target>, predicted_<target>_lower, predicted_<target>_upper, predicted_<aux>…}]`, where `<aux>` ranges over the **auto-forecast** auxiliaries only. Known-future columns are omitted from the output — the `predicted_` prefix strictly means the model forecast that value; the caller already has what it supplied. The bounds are the 95% prediction interval for the target (available from the state-space forecast at no extra cost); auxiliary series get point forecasts only.
- The engine always forecasts the full contiguous horizon (SARIMAX forecasting is recursive); the UI's "single date" mode is a display filter, not an engine mode.

### Evaluation and metrics

- **Rolling-origin cross-validation**: orders are selected once on the full series; then 3 expanding-window folds (fallback to 2 on small data) refit **parameters only** (orders fixed) on each fold's train window and forecast its holdout. Holdout forecasting mirrors predict semantics: auto-forecast auxiliaries are forecast by their fold-refit models, while known-future columns feed the target their **actual holdout values** (they would be known in reality). Per fold: `MAE`, `RMSE`, `MAPE`, `R2` for the target (and per auto-forecast auxiliary; known-future columns have no model and no metrics). Folds aggregate by mean; `MAPE` is computed over non-zero actuals, is `None` for an all-zero fold, aggregation skips `None` folds, and an all-`None` aggregate stays `None` (rendered `—`).
- `SC_SCORE = clamp(R2, 0, 1)` — the 0–1 total score for the circular widget, mirroring tabular.
- "Train" metrics are in-sample one-step-ahead predictions from the final full-data fit; "test" metrics are the mean CV metrics.
- **Chronological only, never shuffled.** The chart's train/test boundary (`split_date`) is the start of the last fold's holdout window; the `test_fit` line is that fold's genuinely out-of-sample forecast (params refit on pre-boundary data only).

### Chart payload

Identical in shape to the tabular-style structure the frontend consumes: `{split_date, series: {<col>: {actuals, test_fit, future}}}` with per-point `{date, value}`, `actuals` downsampled to ≤ ~500 points, one series per target + auxiliary column. Known-future series carry `actuals` only — no `test_fit` or `future` segments, since nothing models them. `future` is the optional training-time preview (see §6); the target's future points also carry `lower`/`upper` when intervals are rendered.

## 2. FNNX serialization

New package `wasm/packages/dfs_webworker/dfs_webworker/forecasting_serialization/` mirroring `prompt_optimization/serialization/` (JSON in `extra_values`, reconstructed in `warmup`; no pickle):

- The pyfunc's `warmup` rebuilds the pipeline from `extra_values["pipeline"]` (the JSON spec of §1); `compute` validates and runs `predict(history, horizon, future)`. The forecasting pipeline module is bundled via `add_module` so it imports inside the runtime, exactly as prompt-opt bundles `promptopt`.
- **Input dtype**: `{history: list[record], horizon: int}`, plus `future: list[record]` **iff** the model has known-future columns — the field is written into the per-model dtype only when it applies, so each artifact's schema states exactly what its predict call needs. **Output dtype**: `{forecast: list[record]}` (shapes per §1; known-future columns never appear in output records).
- **Producer info**: `dataforce.studio/forecasting` with manifest tag `dataforce.studio::forecasting:v1`.
- **Meta entries**:
  - `dataforce.studio::forecasting_metrics:v1` — `{metrics, model_config}` where `metrics` is the test-metrics dict (`MAE/RMSE/MAPE/R2/SC_SCORE`) and `model_config` is the read-only report: frequency, column roles (incl. which columns are known-future), per-series orders/seasonal order/deterministic term, seasonal period, and `min_history`.
  - `dataforce.studio::registry_metrics:v1` — so the existing generic registry-metrics path can surface metrics if an exported model is later promoted (no forecasting-specific Registry work in v1).
  - `dataforce.studio::forecasting_chart:v1` — the embedded training-results chart payload `{split_date, series: {<col>: {actuals, test_fit}}}` so a future inference surface can redraw training results without the original CSV. Not consumed by any v1 screen — embedded now so exported artifacts stay forward-compatible. Future points are not embedded.
- **Runtime env**: `fnnx` runtime deps plus `statsmodels`, `scipy`, `pandas`, `numpy` pinned to the worker's installed versions via `importlib.metadata`. **No scikit-learn, no joblib.** (Heavier than a pure-numpy env — the accepted cost of real state-space prediction, see Trade-offs.)

## 3. Worker entry + routing (WASM)

In `forecasting.py`, mirroring `tabular.py`:

- A **train** entry point: takes the dataset, the column roles, the frequency, and an optional preview horizon; auto-configures, fits, cross-validates, and serializes; stores the live pipeline in `Store`; returns the model id, train/test metrics, the model-config report, the chart (including the optional `future` preview computed from the training data when a preview horizon is given — rejected with a clear error when known-future columns are marked, since their future values don't exist at train time; see §6), and the `.luml` bytes.
- A **predict** entry point: takes a model id, `history`, `horizon`, and — for models with known-future columns — `future`; runs fixed-weight prediction against the in-`Store` pipeline (powers the Evaluate screen's interactive re-forecast; the frontend passes the uploaded training series as `history`). Returns the wide forecast records of §1 — the same shape the pyfunc returns, so the frontend needs one adapter.
- A **deallocate** entry point for `Store` cleanup by model id.

Register `/forecasting/train`, `/forecasting/predict`, `/forecasting/deallocate` in the `Router` (`dfs_webworker/__init__.py`); add the forecasting constants (task name, manifest tag, metrics tag, chart tag) to `dfs_webworker/constants.py`.

**Worker environment**: `frontend/public/webworker.js` must load statsmodels 0.14.2 and its deps (patsy, packaging) from the Pyodide 0.26.2 distribution. The file currently micropip-installs `scipy==1.14.1` while the distribution's statsmodels is built against scipy 1.12.0 — the implementer must verify statsmodels imports and fits correctly alongside the existing installs and reconcile the scipy source/version if needed.

## 4. Frontend — shared contract

`frontend/src/lib/data-processing/interfaces.ts`:
- `WEBWORKER_ROUTES_ENUM`: the three forecasting routes. `Tasks`: add `FORECASTING`.
- Types covering the forecasting contract: the frequency choices, the metrics dict (`MAE/RMSE/MAPE/R2/SC_SCORE`, MAPE nullable), the model-config report of §2 (incl. `min_history` and the known-future column subset), the train payload and training-data shapes, the predict input (history, horizon, optional future records), the chart structures of §1, and the wide predict-output record (incl. the target's optional bounds).

**Predict-result adapter.** Add a normalizer that pivots the wide `predicted_<col>` records returned by `/forecasting/predict` into per-series `{date, value}` points (carrying the target's bounds through for the band). The Evaluate re-forecast (§7) routes its raw result through it before touching the chart. (When a Runtime surface lands later, the same adapter covers the pyfunc path — its records have the identical wide shape, just nested under `predictions.forecast`.)

No `FnnxService.ts` changes in v1 — the forecasting tags are written by the serializer, but nothing reads `.luml` files in the frontend until the Runtime surface lands.

## 5. Frontend — task registration & routing

- `frontend/src/constants/constants.ts`: enable the Time Series Forecasting card — drop the disabled/"coming soon" state, give it the standard next-step button, link it to the forecasting route, keep an analytics name. **No "Upload for inference" dropdown option** — Runtime is deferred, so the card offers only training. Add the forecasting step labels (Data Upload / Forecast Setup / Model Evaluation) and resources entries alongside the existing tasks'.
- `frontend/src/router/index.ts`: add the `/forecasting` route to a new `ForecastingPage.vue` (same `meta.showInvalidMessage` pattern as the tabular pages).

## 6. Frontend — training flow

- `pages/ForecastingPage.vue` → thin page rendering `ForecastingWrapper` (mirrors `ClassificationPage.vue`).
- `components/express-tasks/forecasting/ForecastingWrapper.vue` — 3-step `Stepper` (mirrors `TabularWrapper.vue`):
  - **Step 1 Upload**: reuse `ui/UploadData.vue` + `useDataTable`; validate ≥ 2 columns and the ~30-row soft guard (the 12-row hard floor lives in the engine).
  - **Step 2 Forecast Setup**: date column select (default: first parseable-as-dates column), target select, optional auxiliary multi-select (excludes date/target), an optional **known-future multi-select** over the chosen auxiliaries (marks the features whose future values the user will supply at prediction time; subset of the auxiliaries by construction), frequency select, and an **optional preview horizon**: a future end-date picker plus a "selected date only / whole period" toggle. The preview only controls the Evaluate chart's `future` segment; it never constrains the saved model. When any column is marked known-future, the preview controls are hidden with a hint pointing to the Evaluate re-forecast (which collects the needed future values), and no preview horizon is sent. Validations: distinct date/target columns, a parseable date column must exist, end date must be after the last historical date.
  - **Step 3 Evaluate**: below.
- New hook `hooks/useForecastingTraining.ts` (parallel to `useModelTraining`) owning train, predict, model download (`forecasting_<timestamp>.luml`), metrics/chart/model-config access, and deallocation of tracked models on unmount.

## 7. Frontend — evaluation & results

`components/express-tasks/forecasting/evaluate/index.vue`:
- **Metrics panel** — circular total score from `SC_SCORE` + cards for MAE, RMSE, MAPE (`—` when null), R².
- **Model configuration card** — the read-only auto-detection report: detected orders/seasonality per series, seasonal period, which columns are known-future (with a note that predict calls must supply their future values), and the **minimum history** required for future predictions (this is the user's heads-up that predict calls need that much data).
- **Forecast chart** — one overlaid multi-series line chart (reuse the app's existing chart component; no new charting dependency) plotting target + auxiliaries, each line segmented by role with shared segment colors: train actuals (before `split_date`), test actuals plus dashed out-of-sample `test_fit`, dashed future forecast. Target emphasized (thicker), series distinguished by legend. The three segment colors come from **existing theme CSS variables** (`var(--p-…)`, the same mechanism `lib/apex-charts/apex-charts.ts` already uses), shared across series. The theme files (`assets/theme/light-theme.css`/`dark-theme.css`) are auto-generated from the Figma design tokens and **must never be hand-edited**; introducing new dedicated tokens is out of scope — that would have to go through the Figma export pipeline. A shaded 95% band around the target's future segment is a **nice-to-have** — point lines are required, the band may ship later.
- **Interactive re-forecast** — a horizon picker (future end date + single/whole-period toggle) calls `startPredict` → `/forecasting/predict` with the **in-session training series as `history`** and the computed horizon; the result is normalized via the §4 adapter and overlaid as the prediction segment, plus a predictions-CSV download (including the bound columns). For models with known-future columns, the panel additionally shows a **future-values editor**: an editable grid with one row per horizon date and one column per known-future feature, which can also be populated by uploading a small CSV (`date` + known-future columns; rows matched to the horizon dates). Forecasting stays blocked until every cell holds a numeric value; the grid contents are sent as `future` alongside history/horizon, and the provided values are drawn as those series' future segment, visually distinct from forecast lines.
- **Download `.luml`** button.

## 8. Deferred: Runtime, Registry, Deployment

Not built in v1. The artifact is designed so all three land later with no engine or serialization changes:
- **Runtime** — the `forecasting_v1` manifest tag, `forecasting_metrics:v1`/`forecasting_chart:v1` meta entries, and the generic pyfunc contract are already in the bundle; a future dashboard needs only frontend work (tag mapping, cards, a recent-history CSV upload validated against `min_history`, plus the future-values input for known-future models — the input dtype says whether it's needed).
- **Registry** — the `registry_metrics:v1` meta entry is written at export, so the existing generic metrics path works whenever promotion is enabled for this task type.
- **Deployment** — fully generic for pyfunc bundles; the manifest-derived OpenAPI schema would expose `{history, horizon[, future]}` → `{forecast}` as-is. The bundle env is pinned correctly now (statsmodels/scipy/pandas/numpy), so exported models remain deployable without retraining.

## Dependencies

- **New in the Pyodide worker**: statsmodels 0.14.2 (+ patsy, packaging) from the Pyodide 0.26.2 distribution (`webworker.js` changes, incl. the scipy-version reconciliation noted in §3).
- **Bundle runtime env**: statsmodels, scipy, pandas, numpy (+ fnnx runtime deps). No scikit-learn/joblib.
- **Frontend**: no new dependencies (PrimeVue Stepper, existing chart component).

## Trade-offs

- **statsmodels at serve time** — heavier than a pure-numpy path, but fixed-weight SARIMAX prediction *is* Kalman filtering; reimplementing it in numpy was rejected as high-risk. In v1 the bundle's predict path is exercised only by the serialization roundtrip test (serving surfaces are deferred), but the env pins are set correctly now so exported artifacts serve later without changes.
- **History always required at predict** — the artifact is stateless and never embeds user data (a privacy and staleness win), at the cost of any future inference surface needing a data upload before it can forecast. Chosen deliberately over storing the training tail.
- **Two-stage exog** — the target is trained on actual auxiliary values but predicts with forecast ones; standard ARIMAX behavior, accepted for the cross-series signal it buys. Marking a column known-future sidesteps this entirely — at the cost of the caller having to supply its values on every predict.
- **Bounded stepwise search** — `p,q ≤ 3`, `P,Q ≤ 1`, ~25 fits: worse than exhaustive search on pathological series, necessary for browser latency; the `(0,d,0)` fallback guarantees training never dead-ends.
- **Single seasonal period per frequency** — daily data models the weekly cycle only (no 365-period terms; SARIMAX state dimension makes long periods impractical); weekly data's `s = 52` is allowed but seasonal orders stay minimal. Fourier-term exog for long periods is a possible v2.

---

# Scenarios

## Scenario: Train a monthly forecast with auto-configuration (happy path)
**Given** a CSV with a monthly `date` column and a numeric `sales` column (≥ 36 rows, visible trend and yearly seasonality)
**When** the user uploads it, assigns `date`/`sales`, picks frequency `month`, and trains
**Then** the engine detects `s = 12`, a nonzero `D` or seasonal terms, selects orders by stepwise AICc, returns train/test metrics (MAE/RMSE/MAPE/R²/SC_SCORE), a `model_config` report (orders, seasonal period, deterministic term, `min_history`), a chart with `actuals`/`test_fit` for `sales`, and the `.luml` bytes; the Evaluate step renders score, metric cards, config card, and the segmented chart.

## Scenario: Two-stage training with auxiliary columns
**Given** a CSV with `date`, target `revenue`, auxiliaries `marketing_spend` and `visitors`
**When** the user assigns roles and trains
**Then** each auxiliary gets its own auto-configured SARIMAX, the target model uses both auxiliaries as exogenous regressors, `model_config` reports per-series configurations, and prediction outputs include `predicted_revenue` (with bounds) plus `predicted_marketing_spend`/`predicted_visitors`.

## Scenario: Known-future covariates supplied at predict
**Given** a model trained with target `sales`, auto-forecast auxiliary `visitors`, and `promo` marked known-future
**When** predict is called with a valid history (including `promo`'s historical values), `horizon = 4`, and `future` records carrying `promo` for the 4 forecast dates
**Then** no auxiliary model exists for `promo`, the supplied values feed the target as future exog, and the output records contain `predicted_sales` (with bounds) and `predicted_visitors` but no `promo` field of any kind.

## Scenario: Missing or malformed future values
**Given** a model with a known-future column
**When** predict is called without `future`, or with future records that miss a horizon date, add an extra date, or omit the known-future column
**Then** the call fails with a clear error naming the missing/extra dates or columns, and nothing is forecast; symmetrically, supplying `future` to a model with no known-future columns is rejected.

## Scenario: Evaluation uses actual holdout values for known-future columns
**Given** a training run with a known-future column
**When** rolling-origin CV forecasts each fold's holdout
**Then** the target's future exog for that column comes from the actual holdout values (never a forecast), auto-forecast auxiliaries are forecast by their fold-refit models, and metrics are reported for the target and auto-forecast auxiliaries only.

## Scenario: Fixed-weight prediction on fresh history
**Given** a model trained on 2020–2023 monthly data and a predict call supplying only 2024 rows (≥ `min_history`) with `horizon = 6`
**When** the pyfunc (or `/forecasting/predict`) runs
**Then** no parameter optimization occurs — the stored parameter vectors are applied to the new history by filtering — and the response contains 6 consecutive monthly records starting after the last 2024 date, reflecting the provided history's recent level (not the training data's).

## Scenario: Prediction is deterministic
**Given** the same artifact, the same history window, and the same horizon
**When** predict is called repeatedly (via the worker route or a loaded bundle)
**Then** the outputs are identical across calls and environments (within floating tolerance).

## Scenario: Too little history at predict time
**Given** a model whose `min_history` is 15 and a predict call supplying 10 rows
**When** the call validates
**Then** it fails with a clear error naming the required minimum (15) and the supplied count.

## Scenario: History with gaps or wrong columns
**Given** a predict history whose dates skip a period at the model frequency, or which lacks an auxiliary column the model was trained with
**When** validation runs
**Then** the call errors with a message naming the gap (or the missing column); nothing is forecast.

## Scenario: Short series disables seasonality instead of failing
**Given** 18 monthly rows (fewer than two full yearly cycles)
**When** the user trains with frequency `month`
**Then** seasonal modeling is disabled automatically (non-seasonal ARIMA), training succeeds, and `model_config` reports the absence of seasonal terms.

## Scenario: Trending non-seasonal series gets differenced
**Given** a strongly trending, non-seasonal series
**When** auto-configuration runs
**Then** KPSS-based detection selects `d ≥ 1`, the seasonal-strength test selects `D = 0`, and the fitted model extrapolates the trend (drift/deterministic term per the `d + D` rule).

## Scenario: Training data below the hard floor
**Given** a CSV with fewer than 12 usable rows
**When** the user trains
**Then** the engine raises a clear "not enough data" error surfaced via the training error toast, and no model is produced.

## Scenario: Every candidate fit fails to converge
**Given** a pathological series where all stepwise candidates error or fail to converge
**When** training runs
**Then** the engine falls back to the `(0,d,0)` + deterministic-term model, training completes, and metrics/artifact are still produced.

## Scenario: Chart split is strictly chronological
**Given** any trained forecast
**When** the chart is produced
**Then** `split_date` equals the start of the last rolling-origin holdout, all `actuals` before it are the train segment and from it onward the test segment, `test_fit` comes from a params-refit on pre-boundary data only (genuinely out-of-sample), and no shuffled splitter is used anywhere.

## Scenario: Evaluate-screen re-forecast without retraining
**Given** a completed training session on the Evaluate step
**When** the user picks a new future end date and runs the re-forecast
**Then** the frontend sends the uploaded training series as `history` with the computed horizon to `/forecasting/predict`, the overlay updates from the normalized result, and a predictions CSV (incl. target bounds) is downloadable — with no new training call.

## Scenario: Re-forecast with the future-values editor
**Given** the Evaluate step for a model with known-future columns and a chosen future end date
**When** the user fills the per-date grid (or uploads a CSV of `date` + known-future columns that populates it) and runs the re-forecast
**Then** forecasting stays blocked until every horizon date has a numeric value for every known-future column, the predict call carries the grid contents as `future`, and the overlay/CSV update as usual.

## Scenario: Preview deferred when known-future columns exist
**Given** Step 2 with an auxiliary marked known-future
**When** the user completes setup and trains
**Then** the preview end-date controls are hidden with a hint pointing to the Evaluate re-forecast, the train call carries no preview horizon, and the training chart has no `future` segment.

## Scenario: Single-date display mode
**Given** a horizon picker set to "selected date only" for a date 8 periods out
**When** the forecast returns
**Then** the engine forecast covers all 8 periods, and the UI displays/exports only the final date's record.

## Scenario: Serialization roundtrip without refitting
**Given** a pipeline trained in the worker and serialized
**When** the `.luml` is loaded through a fresh fnnx runtime and asked to predict with the training series as history
**Then** predictions match the in-memory pipeline's output within floating tolerance, reconstruction reads only the JSON spec (no pickle), the env pins statsmodels/scipy/pandas/numpy but not scikit-learn/joblib, and the manifest/meta carry the forecasting tags, metrics, `model_config` (incl. the known-future designation), and chart payload; for a model with known-future columns the input dtype carries the `future` field, for one without it doesn't.

## Scenario: MAPE with zero target values
**Given** a target series containing zeros
**When** metrics are computed
**Then** MAPE uses only non-zero actuals per fold, all-zero folds yield `None` and are skipped in aggregation (all-`None` → `None`, rendered `—`), while MAE/RMSE/R²/SC_SCORE aggregate normally.

## Scenario: Setup validations
**Given** the Forecast Setup step
**When** no column parses as dates, or date and target are the same column, or the preview end date is not after the last historical date
**Then** the UI blocks progression with a specific message for each case; no train call is made.

## Scenario: Worker error is reported, not swallowed
**Given** any exception inside a forecasting route
**When** the worker `invoke` wraps it
**Then** the standard `{status:'error', error_type, error_message, traceback}` payload is returned and the frontend shows the training/predict error toast, leaving the user on their current step.

## Scenario: Model cleanup on unmount
**Given** trained models held in the worker `Store`
**When** the user leaves the forecasting flow
**Then** the hook deallocates every tracked `model_id` on unmount.

---

# Tasks

- [x] Add the SARIMAX forecasting engine with auto-configuration
  - [x] Load statsmodels (+ patsy/packaging) in `frontend/public/webworker.js` from the Pyodide distribution; verify import/fit works alongside the existing scipy pin and reconcile if needed
  - [x] Create `dfs_webworker/forecasting.py`: pipeline class, two-stage fit (per auto-forecast-aux SARIMAX + target-with-exog; known-future columns get no model), auto-detection (STL seasonal strength → D, KPSS → d, deterministic-term rule, bounded stepwise AICc search with the `(0,d,0)` fallback), seasonal-period-from-frequency table incl. the short-series seasonal-disable rule
  - [x] Implement the JSON spec (to/from dict, params + orders + column roles incl. known-future + `min_history`, no training data) and fixed-weight `predict(history, horizon, future)` with full history validation (columns, regular grid, min length), future-values validation (required iff known-future columns exist, exact horizon-date coverage, exact column set), and 95% target bounds
  - [x] Implement rolling-origin CV (params-only refits, actual holdout values as future exog for known-future columns, metric definitions incl. the MAPE `None` rules and SC_SCORE), train metrics, and the chart payload (`split_date`, per-series `actuals`/`test_fit`, actuals-only known-future series, out-of-sample fit, ≤ ~500-point downsampling)
  - [x] Add forecasting constants to `dfs_webworker/constants.py`
  - [x] Unit tests: auto-detection on trending/seasonal/short synthetic series, two-stage exog flow, known-future flow (supplied values feed the target, no aux model/metrics, output omits the column), fixed-weight predict on fresh history (level shift reflected, no refit), determinism, min-history/gap/column/future-values validation errors, CV chronology, MAPE-with-zeros, convergence fallback

- [x] Serialize forecasting models to FNNX bundles
  - [x] Add `dfs_webworker/forecasting_serialization/` mirroring prompt-opt: pyfunc source (warmup rebuilds from `extra_values["pipeline"]`, compute validates + predicts) and a serializer taking the pipeline, metrics, model config, and chart that writes the `{history, horizon[, future]}`/`{forecast}` dtypes (`future` present iff the model has known-future columns), the producer tag, and the three meta entries (`forecasting_metrics:v1` with `{metrics, model_config}`, `registry_metrics:v1`, `forecasting_chart:v1`)
  - [x] Pin runtime env to statsmodels/scipy/pandas/numpy (+ fnnx deps) via `importlib.metadata`; assert no scikit-learn/joblib
  - [x] Roundtrip test: train → serialize → load via fnnx runtime → predictions match in-memory within tolerance; env/tags/meta assertions; dtype includes `future` only for known-future models; predict-time validation errors propagate through the pyfunc

- [x] Add forecasting worker routes
  - [x] Implement the train/predict/deallocate entry points in `forecasting.py` with the documented contracts (train returns metrics + `model_config` + chart incl. optional preview `future` + model bytes, rejecting a preview horizon when known-future columns are marked; predict takes `history` + `horizon` + optional `future` against the `Store` pipeline)
  - [x] Register the three routes in the `Router`
  - [x] Route-level tests: train payload shape, predict-by-`model_id` with fresh history, deallocate, error payloads on invalid input

- [x] Extend the frontend shared contract for forecasting
  - [x] Add the routes, task, and forecasting contract types to `lib/data-processing/interfaces.ts` (frequency, metrics, model config incl. the known-future subset, payload/training-data/chart/record shapes, the predict input with optional future records); verify `DataProcessingWorker.ts` dispatch covers the routes
  - [x] Add the predict-result normalizer (wide `predicted_<col>` records → per-series points, carrying target bounds); unit tests

- [ ] Enable the forecasting task card and route
  - [ ] Flip the card in `constants/constants.ts` (enable, link, analytics; no inference dropdown) and add the forecasting steps and resources constants
  - [ ] Add the `/forecasting` route and a `ForecastingPage.vue` shell rendering the (stub) wrapper
  - [ ] Smoke test: card enabled, route resolves

- [ ] Build the forecasting training flow
  - [ ] `ForecastingWrapper.vue`: 3-step Stepper; Step 1 upload with forecasting validators; Step 2 setup (role selects with defaults incl. the known-future multi-select over the auxiliaries, frequency, optional preview end-date + single/whole toggle hidden when known-future columns are marked, all §6 validations)
  - [ ] `hooks/useForecastingTraining.ts`: train/predict/download/cleanup + metrics/chart/config getters; wire Step 2 → train → Step 3
  - [ ] Component tests: each setup validation, preview hidden when known-future columns are marked, successful train→advance (worker mocked), unmount cleanup

- [ ] Build the forecasting evaluation step
  - [ ] Pick the train/test/prediction segment colors from existing `--p-*` theme variables (the theme CSS files are Figma-generated — never hand-edit them or add tokens manually)
  - [ ] Build a reusable `ForecastChart.vue` (overlaid multi-series, role-segmented colors, dashed test-fit/future, actuals-only known-future series, target emphasis, legend; optional target band as nice-to-have)
  - [ ] Build the future-values editor (per-horizon-date grid over the known-future columns + CSV upload populating it, numeric completeness gating the forecast)
  - [ ] `evaluate/index.vue`: score widget, metric cards (MAPE `—` when null), model-config card incl. `min_history` and known-future roles, chart, interactive re-forecast (training series as history + grid contents as `future` → `/forecasting/predict` → overlay + CSV), `.luml` download
  - [ ] Component tests: metric/config rendering, segment coloring around `split_date`, future-values grid gating and CSV fill, re-forecast overlay (with and without known-future columns), downloads
