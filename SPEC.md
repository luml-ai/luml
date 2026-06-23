# Proposals

## Problem

LUML's **Express Tasks** module (the no-/low-code AutoML surface) ships four task types today: Tabular Classification, Tabular Regression, Prompt Optimization, and Notebooks. The frontend already advertises a fifth — **Time Series Forecasting** — but it is a dead placeholder card (`frontend/src/constants/constants.ts`, `isDisabled: true`, button label "coming soon"). Users who want to predict future values from historical time-series data (sales projections, demand planning, financial forecasting — the exact use cases named in the card copy) have no way to do it on the platform.

## Solution (at a glance)

Implement Time Series Forecasting as a **first-class Express Task type with full lifecycle parity** with the existing tabular tasks:

1. **Train + evaluate + download** — a 3-step flow (Upload → Configure → Evaluate) that fits a forecasting model entirely **client-side in the WASM Pyodide worker** (`wasm/packages/dfs_webworker`), exactly like tabular classification/regression, and produces a portable `.luml` (FNNX) artifact.
2. **Runtime inference** — "Upload for inference" support so a downloaded `.luml` forecasting model can be loaded and queried in the Runtime page.
3. **Registry + Deployment** — promotion to the Registry and serving on a Satellite via the FNNX model server, with no platform-side training (the artifact is a self-describing FNNX bundle that already works with the generic registry/deployment machinery).

The forecasting engine is a **Ridge-regression-based pipeline** (provided by the product owner) that turns dates into seasonal/trend features and, optionally, models auxiliary series first and feeds their *predicted* values into the target model (reducing train/serve skew). It is generalized to support multiple date frequencies (day/week/month/quarter/year).

## Why this approach

- **Mirror the existing tabular pattern.** Tabular Express Tasks already run AutoML in-browser via `dfs_webworker`, serialize to FNNX/`.luml`, and reuse the generic Registry/Runtime/Deployment plumbing. Forecasting fits the same mold, so we reuse the upload/stepper/results UX, the worker dispatch (`Router` in `dfs_webworker/__init__.py`), the `PyfuncBuilder` serialization path, and the satellite FNNX runtime. No new backend training infrastructure is required.
- **Ridge over a heavyweight forecasting library.** The provided pipeline is small and dependency-light — scikit-learn is needed only for *training* (already available in the Pyodide worker), and *serving* reduces to pure numpy/pandas (the learned params are stored as JSON and applied as a standardize-then-linear-combination). It is deterministic and fast enough to run client-side. A dedicated library (Prophet/statsforecast/sktime) would add weight to the WASM bundle and the satellite runtime for marginal v1 benefit.
- **FNNX pyfunc bundle keeps parity for free.** Because the trained model is packaged as a standard FNNX pyfunc `.luml`, the existing Registry promotion, Runtime loader (`lib/fnnx/FnnxService.ts` + `@fnnx-ai/web`), and Satellite model server all consume it through their existing generic code paths once we add the forecasting producer tag and a results/inference UI.

## Out of scope (v1)

- Multiple competing algorithms / AutoML model selection for forecasting (only the Ridge pipeline).
- Probabilistic / confidence-interval forecasts.
- Multivariate exogenous regressors supplied at inference time (auxiliary series are *modeled from dates*, not user-supplied at predict time).
- Automatic frequency detection (the user explicitly picks the frequency).
- Backend (`backend/luml`) or `sdk/python` changes — there are none; all new code lives in `wasm/packages/dfs_webworker` and `frontend`.

---

# Design

## Architecture overview

```
Browser (Vue)                         WASM worker (Pyodide)                FNNX artifact (.luml)
─────────────                         ─────────────────────                ─────────────────────
ForecastingPage.vue                   dfs_webworker.forecasting            pyfunc bundle:
 └─ ForecastingWrapper.vue   ──train──> forecasting_train()                 - manifest.json (producer tag
     ├─ Upload (csv)                       ├─ RidgeForecastingPipeline.fit     dataforce.studio::forecasting:v1)
     ├─ Configure                          ├─ .cross_validate() -> metrics     - dtypes/inputs/outputs
     │   (roles, freq, horizon)            └─ save_forecasting() -> bytes ───> - variant_artifacts/__pyfunc__.py
     └─ Evaluate (chart+metrics)        forecasting_predict()                  - variant_artifacts/extra_modules/
                                        forecasting_deallocate()                  (forecasting pipeline module)
                                                                              - variant_config.json extra_values:
                                                                                  {"pipeline": <JSON params>}
                                                                              - env.json (pandas/numpy only)
Runtime / Registry / Deployment  ── consume .luml via generic FNNX runtime ──┘
```

The split of responsibilities matches the tabular task exactly (`wasm/packages/dfs_webworker/dfs_webworker/tabular.py` + `frontend/src/components/express-tasks/tabular/*`).

## 1. Forecasting engine (WASM, Python)

New module `wasm/packages/dfs_webworker/dfs_webworker/forecasting.py` containing a **generalized** `RidgeForecastingPipeline` based on the product-owner-provided design, plus the worker entry functions.

### `RidgeForecastingPipeline` (dataclass)

Fields (constructor args):
- `date_col: str`
- `target_col: str`
- `frequency: str` — one of `"day" | "week" | "month" | "quarter" | "year"` (user-picked; drives **both** feature engineering and the forecast date grid).
- `auxiliary_cols: list[str] | None = None`
- `alpha: float = 1.0`

Fitted state (set in `__post_init__` / `fit`):
- `training_start_date_: pd.Timestamp | None`
- `last_training_date_: pd.Timestamp | None`
- `auxiliary_models_: dict[str, Pipeline]`
- `target_model_: Pipeline | None`
- `date_feature_cols_: list[str]` — **frequency-dependent** (see below)
- `target_feature_cols_: list[str] | None`

Methods (same surface as the provided design): `fit(df)`, `predict(dates)`, `cross_validate(df, n_splits=3, test_size=None)`, plus internal helpers `_make_base_model`, `_validate_input_columns`, `_prepare_data`, `_make_date_features`, `_fit_auxiliary_models`, `_build_target_features`, static `_rmse`/`_mae`/`_mape`/`_r2`.

Each base model is `Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=alpha))])`. `fit`/`cross_validate` use scikit-learn (in the WASM training env only).

The **two-stage** design is preserved: when `auxiliary_cols` are present, auxiliary models are trained on date features, then the target model is trained on date features + **predicted** auxiliary values (not the real ones), so training-time inputs match inference-time inputs.

### JSON (de)serialization

To match the existing prompt-optimization pyfunc convention (model stored as JSON data and reconstructed at runtime, **not** pickled), the pipeline is reduced to plain numbers. 

- `to_dict() -> dict` returns a fully JSON-serializable spec: `date_col`, `target_col`, `frequency`, `auxiliary_cols`, `alpha`, `training_start_date_` (ISO string), `last_training_date_` (ISO string), `date_feature_cols_`, `target_feature_cols_`, and for the target model and **each** auxiliary model the learned params `{ "coef": list[float], "intercept": float, "scaler_mean": list[float], "scaler_scale": list[float] }` (from `Ridge.coef_/intercept_` and `StandardScaler.mean_/scale_`).
- `from_dict(spec) -> RidgeForecastingPipeline` and a **pure-numpy** prediction path `predict_from_params(dates)` that needs **only pandas + numpy** (no scikit-learn): build date features → standardize with `(x - mean) / scale` → linear combination `X @ coef + intercept`, applying the same two-stage aux→target flow. (`predict` on a fitted in-memory instance may still delegate to the sklearn pipelines; `predict_from_params` is what the deployed bundle uses.)

This keeps the trained artifact dependency-light and version-robust on the serving side.

### Frequency-aware feature engineering (generalization)

`_make_date_features(dates, training_start_date)` returns a `DataFrame` whose columns depend on `self.frequency`. The trend feature is always a continuous "elapsed periods since training start" value scaled to a stable range; seasonal features are cyclical `sin/cos` pairs appropriate to the frequency:

| frequency | trend feature | seasonal sin/cos pairs |
|-----------|---------------|------------------------|
| `year`    | `years_since_start` | none |
| `quarter` | `years_since_start` | `quarter` (period 4) |
| `month`   | `years_since_start` | `month` (12), `quarter` (4) |
| `week`    | `years_since_start` | `week_of_year` (52), `month` (12) |
| `day`     | `years_since_start` | `day_of_week` (7), `day_of_year` (365), `month` (12) |

`years_since_start` = elapsed days from `training_start_date` ÷ 365.25 (continuous, frequency-independent, replaces the month-only arithmetic in the original draft). `date_feature_cols_` is set from the selected frequency's column list at fit time and reused at predict time. Sin/cos use `2π * value / period`.

This replaces the hardcoded monthly/quarterly features in the original draft so daily/weekly/yearly data is handled correctly.

### Forecast date grid

`predict(dates)` accepts an explicit iterable of dates (used by FNNX inference). The **frontend** is responsible for generating the date grid from the user's horizon selection (see UI section) using the picked frequency. A helper `generate_forecast_dates(last_date, end_date, frequency) -> list[str]` is exposed from `forecasting.py` and used by `forecasting_train` to compute the "future forecast" preview shown on the evaluation screen. Mapping frequency → pandas offset alias: `day→"D"`, `week→"W-<DOW>"`, `month→"MS"`, `quarter→"QS"`, `year→"YS"`. For `week`, anchor to the **weekday of the last historical date** (`W-MON`…`W-SUN`) rather than the bare `"W"` (which defaults to week-ending-Sunday and would shift the generated dates off the data's weekday).

### Model reusability (no baked-in horizon)

The trained model is **horizon-agnostic and fully reusable**: it stores only the fitted trend/seasonal coefficients (and auxiliary models), never a fixed forecast range. `predict(dates)` and the FNNX bundle's input schema (`{dates: list[str]}`) accept **any** future dates, any number of times. The training-time end-date picker (Step 2) is **preview-only** — it merely chooses what the Evaluate screen's chart extrapolates (the per-series `chart.series.<col>.future` preview) and is **optional** (`forecast_end_date: str | None`; omit → empty `future`, training still succeeds). Real, repeated predictions happen afterward in **Runtime** (upload for inference, enter any horizon), **Deployment** (send `{dates}` to the Satellite), or by re-loading the downloaded `.luml`. Implementations MUST NOT persist the training-time horizon into the artifact or otherwise constrain the model to it. The only inherent limitation is that dates should fall after `last_training_date_` (extrapolation), and accuracy degrades with distance.

### Metrics

`cross_validate` uses `sklearn.model_selection.TimeSeriesSplit`. Per fold it reports target `mae`, `rmse`, `mape`, `r2` (and the same four per auxiliary column). The worker aggregates folds by **mean** into a single metrics dict. Definitions:
- `MAE = mean(|y-ŷ|)`, `RMSE = sqrt(mean((y-ŷ)²))`, `R2 = sklearn.metrics.r2_score`.
- `MAPE = mean(|y-ŷ| / |y|)` over rows where `y != 0`; if all `y == 0` in a fold, that fold's MAPE is `None`. **Fold aggregation skips `None` MAPE folds** (mean over the folds that have a value); if *every* fold is `None`, the aggregated `MAPE` is `None` (rendered `—` in the UI). The other metrics (MAE/RMSE/R2/SC_SCORE) are always aggregated over all folds regardless.
- `SC_SCORE = clamp(R2, 0.0, 1.0)` — the 0–1 "total score" used by the circular score widget (mirrors tabular `SC_SCORE`, surfaced via `toPercent`).

"Train" metrics are computed by predicting the full training set after the final `fit`; "test" metrics are the mean CV metrics. If the dataset is too small for `n_splits + 2` rows, fall back to `n_splits = max(2, len-2)` and, if still impossible (`len < 4`), raise a clear error.

**Chronological split — never random.** `TimeSeriesSplit` is inherently ordered: every split uses a contiguous past window to predict a contiguous future window, with no shuffling. The pipeline MUST sort by date in `_prepare_data` and MUST NOT use `train_test_split`, `KFold`, or any shuffled splitter anywhere. For the **chart**, a single chronological train/test boundary is defined as the start of the **last** `TimeSeriesSplit` fold's validation window: everything before it is the *train segment*, the validation window itself is the *test segment*. Expose this as `chart_split(df) -> (split_date, test_index)` and a `fit_window(df, test_index) -> dict[col -> list[{date,value}]]` helper that returns, per series (target + each auxiliary), the model's fit over the test window. **`fit_window` is genuinely out-of-sample**: it trains a fresh pipeline on the **train segment only** (rows before `test_index`) and predicts the held-out test window — it does **not** use the final full-data model, otherwise the test line would be in-sample and misleadingly accurate. These feed both the Evaluate chart and the bundle's embedded chart payload (§2) so Runtime can redraw the same train/test/fit segmentation without the original CSV.

## 2. FNNX serialization (`save_forecasting`)

New package `wasm/packages/dfs_webworker/dfs_webworker/forecasting_serialization/` mirroring `prompt_optimization/serialization/`:

Following the prompt-optimization precedent (model stored as JSON in `extra_values`, reconstructed in `warmup`; **no pickle, no `extra_file`**):

- `__fnnx_pyfunc.py` — commented-out source of `ForecastingPyFunc(PyFunc)` (the build copies this file verbatim into the bundle as `__pyfunc__.py`, per the `PyFuncSpec` mechanism). It:
  - `warmup()`: `spec = self.fnnx_context.get_value("pipeline"); self.pipeline = RidgeForecastingPipeline.from_dict(spec)` (the pipeline class is bundled as an `extra_module` so it imports inside the runtime; reconstruction sets the learned params, no scikit-learn needed).
  - `compute(inputs, dynamic_attributes)`: read `inputs["dates"]` (list of ISO date strings), call `self.pipeline.predict_from_params(dates)` (pure numpy/pandas), return `{"forecast": <records>}` where records include the date, `predicted_<target>`, and `predicted_<aux>` columns as JSON-able lists.
  - `compute_async` raises/delegates to sync (`pyfunc.py` already handles the `NotImplementedError` → sync fallback).
- `__init__.py` — `serialize(pipeline, metrics, fe_config) -> bytes`:
  - `builder.add_module(<path to forecasting pipeline module>)` so `RidgeForecastingPipeline.from_dict`/`predict_from_params` are importable in the bundle (mirrors how prompt-opt bundles `promptopt`). The module must import only `numpy`/`pandas` at runtime (guard the scikit-learn imports used by `fit` so they are not required for `from_dict`/`predict_from_params`).
  - Define input dtype `ext::in` = pydantic model `{ dates: list[str] }`; output dtype `ext::out` = `{ forecast: list[dict] }`. `builder.add_input(JSON(name="dates", dtype="ext::in"))`, `builder.add_output(JSON(name="forecast", dtype="ext::out"))`.
  - `builder.set_extra_values({"pipeline": pipeline.to_dict()})` — the JSON model spec (params, feature config, dates, frequency, column names) carried inline, exactly like prompt-opt stores `{"graph": graph.to_dict(), ...}`.
  - `builder.set_producer_info(name="app.dataforce.studio/forecasting", version=..., tags=["dataforce.studio::forecasting:v1"])`.
  - `create_meta_callback` writes `meta.json` entries:
    - `dataforce.studio::forecasting_metrics:v1` carrying `{metrics, fe_config}`, where `metrics` is the **test/eval** metrics dict (`MAE/RMSE/MAPE/R2/SC_SCORE`, with `SC_SCORE` so `getForecastingTotalScore` can render the score widget) and `fe_config` is `{frequency, date_col, target_col, auxiliary_cols}` (so Registry/Runtime read metrics without re-running),
    - `dataforce.studio::registry_metrics:v1` so the existing `FnnxService.getRegistryMetrics` generic path surfaces metrics in the Registry,
    - `dataforce.studio::forecasting_chart:v1` carrying the **embedded chart payload** so the Runtime screen can redraw the training results (train/test/fit) without the original CSV. Shape: `{ split_date, series: { <col>: { actuals: [{date,value}], test_fit: [{date,value}] } } }`, one entry per target + auxiliary column, `actuals` downsampled to ≤ ~500 points. (Future-forecast points are NOT embedded — they are recomputed live in Runtime from the user's chosen horizon.)
  - Runtime deps: `add_fnnx_runtime_dependency()`, `fnnx[core]`, `pyfnx_utils`, plus **only `pandas` and `numpy`** pinned to the worker's installed versions via `importlib.metadata.version(...)`. **No `scikit-learn` and no `joblib`** in the runtime env — prediction is pure numpy, so the served bundle stays light and free of sklearn-version pickle coupling.

This is the only "new save function" the product owner referenced; it lives in the WASM package, not the backend or `sdk/python`.

## 3. Worker entry + routing (WASM)

In `forecasting.py`, add (mirroring `tabular.py`):
- `forecasting_train(data: dict, date_col: str, target: str, auxiliary_cols: list[str], frequency: str, forecast_end_date: str | None) -> dict` → fits, cross-validates, serializes, stores the live pipeline in `Store`, and returns `success(model_id, train_metrics, test_metrics, chart, model)` where:
  - `chart`: the structured, **multi-series** chart object (also embedded into the bundle, see §2):
    ```
    {
      "split_date": "<chronological train/test boundary>",
      "series": {                      # one entry per target + each auxiliary column
        "<col>": {
          "actuals":  [{"date","value"}, ...],   # full history, downsampled ≤ ~500 pts, sorted
          "test_fit": [{"date","value"}, ...],    # model fit over the holdout window
          "future":   [{"date","value"}, ...]     # future preview up to forecast_end_date; [] if none
        }, ...
      }
    }
    ```
    The split is the chronological boundary from `chart_split` (§1). Each series carries train/test actuals via `actuals` + `split_date`, the held-out `test_fit`, and the optional `future` preview.
  - `model`: the serialized `.luml` bytes (consumed by the frontend `saveModel`).
- `forecasting_predict(model_id: str, data: dict) -> dict` → predicts against the **in-`Store` trained pipeline** (the `model_id` returned by `forecasting_train`); powers interactive horizon re-prediction on the **Evaluate dashboard** without retraining (mirrors `/tabular/predict`). `data` carries `{"dates": [...]}`; returns `success(predictions=<records>)` where `<records>` are **wide** rows `[{date, predicted_<target>, predicted_<aux>…}]` — the **same wide record shape** the `ForecastingPyFunc.compute` path returns (so the frontend uses one adapter for both, see below). **Not used by Runtime/Deployment** — those load the model from a `.luml` file and use the generic `/pyfunc/*` path (see §8/§9).
- `forecasting_deallocate(model_id: str) -> dict` → `Store.delete` (cleanup of the Evaluate-session Store model).

Register in `dfs_webworker/__init__.py` `Router`:
```
Router.add_route("/forecasting/train", forecasting_train, sync=True)
Router.add_route("/forecasting/predict", forecasting_predict, sync=True)
Router.add_route("/forecasting/deallocate", forecasting_deallocate, sync=True)
```
Add constants to `dfs_webworker/constants.py`: `FORECASTING = "forecasting"`, `FORECASTING_TAG = f"{PRODUCER}::forecasting:v1"`, `FORECASTING_METRICS_TAG = f"{PRODUCER}::forecasting_metrics:v1"`, `FORECASTING_CHART_TAG = f"{PRODUCER}::forecasting_chart:v1"`.

## 4. Frontend — shared contract

`frontend/src/lib/data-processing/interfaces.ts`:
- `WEBWORKER_ROUTES_ENUM`: add `FORECASTING_TRAIN = '/forecasting/train'`, `FORECASTING_PREDICT = '/forecasting/predict'`, `FORECASTING_DEALLOCATE = '/forecasting/deallocate'`.
- `Tasks`: add `FORECASTING = 'forecasting'`.
- New types:
  - `Frequency = 'day'|'week'|'month'|'quarter'|'year'`.
  - `ForecastingMetrics { MAE; RMSE; MAPE: number | null; R2; SC_SCORE }`.
  - `ForecastingTaskPayload { data; date_col; target; auxiliary_cols: string[]; frequency: Frequency; forecast_end_date: string | null; task: Tasks.FORECASTING }`.
  - `ForecastPoint { date: string; value: number }`, `ForecastingSeries { actuals: ForecastPoint[]; test_fit: ForecastPoint[]; future: ForecastPoint[] }`, `ForecastingChart { split_date: string; series: Record<string, ForecastingSeries> }`.
  - `ForecastingTrainingData { model; model_id; train_metrics: ForecastingMetrics; test_metrics: ForecastingMetrics; chart: ForecastingChart; status; error_message? }`.

`frontend/src/lib/data-processing/DataProcessingWorker.ts`: ensure the generic `INVOKE_ROUTE` dispatch covers the new routes (it is route-string based, so usually no change beyond enum usage — verify).

**Predict-result adapter (single source of truth for shapes).** Both live-predict paths return **wide** rows (`[{date, predicted_<col>…}]`): `/forecasting/predict` under `result.predictions`, and `/pyfunc/compute` under `result.predictions.forecast` (the pyfunc output is named `forecast`). The chart, however, consumes **per-series** `{date, value}` (`ForecastingChart.series`). Add a normalizer `toForecastSeries(records, columns): Record<string, ForecastPoint[]>` (in `lib/data-processing` or a `lib/forecasting` util) that pivots wide `predicted_<col>` rows into the per-series long shape. **Both** the Evaluate (§7) and Runtime (§8) predict paths MUST route their raw result through `toForecastSeries` (after first unwrapping `predictions` vs `predictions.forecast`) before overlaying on `ForecastChart`, so the chart only ever sees one shape.

`frontend/src/lib/fnnx/FnnxService.ts`:
- `FNNX_PRODUCER_TAGS_MANIFEST_ENUM`: add `forecasting_v1 = 'dataforce.studio::forecasting:v1'`.
- `FNNX_PRODUCER_TAGS_METADATA_ENUM`: add `contains_forecasting_metrics_v1 = 'dataforce.studio::forecasting_metrics:v1'`.
- Add `getForecastingData(metadata)`, `getForecastingTotalScore`, `prepareForecastingMetrics` (formats MAE/RMSE/MAPE/R2), and include the new tag in `getTypeTag` (already enumerates all manifest tags, so it works once added).

## 5. Frontend — task registration & routing

`frontend/src/constants/constants.ts`:
- Flip the Time Series Forecasting card: remove `isDisabled`, set `btnText: 'next'`, `linkName: 'forecasting'`, `analyticsTaskName: 'forecasting'`, and `dropdownOptions: [{ label: 'Train new model' }, { label: 'Upload for inference', route: 'runtime' }]`.
- Add `forecastingSteps = [{id:1,text:'Data Upload'},{id:2,text:'Forecast Setup'},{id:3,text:'Model Evaluation'}]` and `forecastingResources` (links analogous to `regressionResources`).

`frontend/src/router/index.ts`: add route `{ path: '/forecasting', name: 'forecasting', component: () => import('../pages/ForecastingPage.vue'), meta: { showInvalidMessage: 992 } }`.

## 6. Frontend — training flow components

- `frontend/src/pages/ForecastingPage.vue` — thin page rendering `<ForecastingWrapper :steps="forecastingSteps" />` (mirrors `ClassificationPage.vue`).
- `frontend/src/components/express-tasks/forecasting/ForecastingWrapper.vue` — 3-step `Stepper` (mirrors `TabularWrapper.vue`):
  - **Step 1 Upload**: reuse `ui/UploadData.vue` + `useDataTable`. Validation: min 3 columns, min ~30 rows. Note: 30 is a **soft UI guard** (forecasting needs fewer rows than tabular's 100, but too-short series fit poorly); the **hard floor** enforced by the engine is `<4` rows (the `cross_validate` `n_splits+2` requirement, §1). The UI guard prevents most low-quality runs before they reach the worker.
  - **Step 2 Forecast Setup**: reuse `table-view` for column-role assignment plus a config panel:
    - **Date column** select (default: first column whose values parse as dates).
    - **Target column** select.
    - **Auxiliary columns** multi-select (optional; excludes date + target).
    - **Frequency** select (day/week/month/quarter/year).
    - **Horizon (preview-only, optional)**: a future **end date** picker + a toggle **"Forecast for the selected date only" vs "Forecast the whole period up to it"** (the frontend builds the date grid; "single date" sends just that one date, "whole period" sends the full grid from `last_training_date` to the end date at the chosen frequency). This only controls the per-series `chart.series.<col>.future` preview drawn on the Evaluate screen — it does **not** constrain the saved model, which remains reusable for arbitrary dates via Runtime/Deployment. If left empty, training proceeds and the Evaluate chart simply omits the future line.
  - **Step 3 Evaluate**: results (see next).
- New hook `frontend/src/hooks/useForecastingTraining.ts` (parallel to `useModelTraining`) exposing `startTraining(payload)`, `startPredict`, `downloadModel`, `modelBlob`, training metrics getters, chart-series getters, and `deleteModels` cleanup on unmount. `downloadModel` filename: `forecasting_<timestamp>.luml`.

## 7. Frontend — evaluation & results

`frontend/src/components/express-tasks/forecasting/evaluate/index.vue`:
- **Metrics panel** — circular total score from `SC_SCORE` (`toPercent`) + cards for MAE, RMSE, MAPE (`—` when null), R² (reuse the `ServiceEvaluate` styling pattern; no feature-importances panel — date features are not user-meaningful).
- **Forecast chart** — a single **overlaid multi-series** line chart (reuse the app's existing chart component — confirm which wrapper is used by other dashboards and reuse it; do NOT add a charting dependency) that plots the **target series and every auxiliary series together** on one set of axes. Each series line is **segmented by data role**, with a **shared semantic color per segment** (identical across all series so the train/test/prediction split is instantly legible):
  - **Train segment** (token `--chart-train`): actual values over the training portion — every point **before** the chronological split boundary.
  - **Test segment** (token `--chart-test`): actual values over the holdout window (from the boundary through the last historical date), **plus** the model's fit on that same window drawn as a **dashed** line in the test color, so predicted-vs-actual on held-out data is visible.
  - **Prediction segment** (token `--chart-prediction`): the future forecast beyond the last historical date, **dashed** (only present if a horizon was chosen — see §6).
  - The split is **strictly chronological** — the holdout is the final contiguous window (the last `TimeSeriesSplit` fold); there is **never** a random/shuffled split. The train window always precedes the test window in time.
  - Series are distinguished from each other by **legend label** (and a subtle per-series channel such as marker shape / line weight, with the **target emphasized** via a thicker line); **segment color is shared** across series, per the requirement that each line is divided into train/test/prediction colors.
- **Predict control (interactive re-forecast).** A horizon picker (future end date + frequency-aware single/whole-period toggle, the same component as §6/§8) lets the user forecast a different horizon **without retraining**. It calls `useForecastingTraining.startPredict` → `/forecasting/predict` against the training `model_id` still live in the worker `Store`, normalizes the wide result via `toForecastSeries` (§4), and overlays the returned per-series future onto the chart in `--chart-prediction` (dashed), plus a predictions-CSV download. (This is the in-session Store path; Runtime uses the generic `/pyfunc/*` path instead — see §8.)
- **Color tokens** — define `--chart-train`, `--chart-test`, `--chart-prediction` in the design tokens (`frontend/tokens` / style-dictionary) so the Evaluate screen and the Runtime screen (§8) render the exact same colors.
- **Download** `.luml` button.

## 8. Frontend — Runtime inference

`frontend/src/components/runtime/dashboard/RuntimeDashboard.vue`: map `FNNX_PRODUCER_TAGS_MANIFEST_ENUM.forecasting_v1` → a new `runtime/dashboard/forecasting/index.vue`.
- **Model performance** card from the bundle's `forecasting_metrics` metadata (total score + MAE/RMSE/MAPE/R²).
- **Training-results chart (always shown).** Read the bundle's `forecasting_chart:v1` metadata and redraw the **same overlaid multi-series, segment-colored chart** as the Evaluate screen — train segment (`--chart-train`), test actuals + dashed test fit (`--chart-test`) — reusing the identical chart component and tokens. This satisfies the requirement that Runtime users still see the model's training results, without needing the original CSV.
- **Predict card.** A **frequency-aware horizon picker** (future end date + single/whole-period toggle, reusing the §6 component) builds the date grid and predicts via the **generic FNNX pyfunc path** — `useFnnxModel` already detects `variant === 'pyfunc'` on upload and runs `/pyfunc/init`, so prediction is `DataProcessingWorker.computePythonModel` → `/pyfunc/compute` (exactly as prompt-opt's `RuntimeDashboardPromptOptimizationPredict.vue` does), unwrapping `result.predictions.forecast` and normalizing via `toForecastSeries` (§4). **Runtime does NOT use `/forecasting/predict`** — that route is only for the in-session Store model on the Evaluate screen (§7); here the model comes from an uploaded `.luml`, not a training session. The returned future forecast is **overlaid onto the same training-results chart** in the **prediction color** (`--chart-prediction`, dashed), so fit and fresh forecast appear together, and is also offered as a downloadable predictions CSV (date + predicted target/auxiliary columns).

## 9. Deployment / Satellite parity

**Deployment works identically to every other Express Task — it is fully generic and requires no forecasting-specific code.** The exact same path used by tabular and prompt-optimization deployments applies:
- **Create/deploy** — `DeploymentsCreateModal` binds a Registry artifact to a Satellite; the satellite `DeployTask` (`satellite/agent/tasks/deploy.py`) downloads the `.luml` and runs it in the `model_server` container, with no model-type-specific logic.
- **Schema/inference UI** — the `model_server`'s `OpenAPIGenerator` (`satellite/model_server/openapi_generator.py`) builds the inference OpenAPI schema **automatically from the FNNX manifest** (its `inputs`/`outputs` + `dtypes.json`). `DeploymentSchemaPage.vue` renders that schema generically via the `OpenApi` component against the satellite inference URL. Because forecasting's manifest already declares `ext::in {dates: list[str]}` / `ext::out {forecast: list[dict]}` (§2), the deployment playground exposes the `{dates}` → `{forecast}` contract with **no new frontend work**. (Note: the task-branched `components/predict/index.vue` is *not* a deployment component — it is the local-worker predict used by `ServiceEvaluate.vue`/prompt-fusion; deployment uses the generic OpenAPI path only.)

**Prompt-optimization is the direct precedent**: it is also a `pyfunc` bundle, so if it deploys and serves, forecasting does too. The only thing to confirm is the serving env:
- Verify the Satellite `model_server` reconstructs the bundle env from `env.json` (only `pandas`, `numpy`, `fnnx`, `pyfnx_utils` → conda/pip install on the satellite) and runs `ForecastingPyFunc` via `from_dict` + pure-numpy `predict_from_params` (no scikit-learn, no pickle → no version coupling). The roundtrip test (Scenario: Serialization roundtrip) guards the artifact correctness; this step confirms it end-to-end on a real satellite.
- Confirm Deployment creation does not whitelist model/task types (it is artifact-generic) — no `backend/luml` change expected.

## Dependencies

No new app dependencies. The WASM worker already has scikit-learn, pandas, numpy, fnnx, pyfnx_utils available (scikit-learn is used for **training only**); the served bundle declares only `pandas`, `numpy`, `fnnx`, `pyfnx_utils` as runtime deps (prediction is pure numpy — no scikit-learn/joblib). Frontend reuses PrimeVue Stepper, `@fnnx-ai/web`, and the existing chart component.

## Trade-offs

- **Single Ridge model, no AutoML search** — predictable, fast, light; weaker on strongly non-linear/seasonal data. Acceptable for v1; the pipeline interface leaves room for swapping the base estimator later.
- **User picks frequency (no auto-detect)** — simpler and more predictable; a wrong choice yields poor seasonal features but never a crash. Auto-detect can be added later.
- **Auxiliary series modeled from dates only** — no need for users to supply future exogenous values at inference, at the cost of not using genuinely independent signals. Matches the provided pipeline's "reduce train/serve skew" intent.
- **JSON params + numpy predict** — the trained model is stored as a JSON spec in `extra_values` and reconstructed at serve time (matching the prompt-optimization pyfunc convention), with prediction reimplemented in pure numpy. Costs a `to_dict()/from_dict()` + numpy predict path, but avoids sklearn/joblib pickle version-coupling, keeps the served bundle light, and is consistent with the existing codebase. (Pickling the sklearn pipeline via joblib was the alternative — rejected for the version-coupling risk and because no other Express Task pickles its model.)

---

# Scenarios

## Scenario: Train a single-series monthly forecast (happy path)
**Given** a CSV with a monthly `date` column and a numeric `sales` column (≥ 40 rows) and no auxiliary columns
**When** the user uploads it, selects `date` as the date column, `sales` as the target, frequency `month`, picks a future end date 12 months out with "whole period", and clicks train
**Then** `forecasting_train` fits the pipeline, returns mean-CV `train_metrics`/`test_metrics` (MAE/RMSE/MAPE/R²/SC_SCORE) and a `chart` object with one `series` entry for `sales` (`actuals`, `test_fit`, 12-point `future`) plus `split_date`, and the Evaluate step shows the score widget, metric cards, and the overlaid segment-colored chart (train/test/fit/future).

## Scenario: Train with auxiliary columns
**Given** a CSV with `date`, target `revenue`, and auxiliary `marketing_spend`, `visitors`
**When** the user assigns `date`/`revenue`/auxiliary `[marketing_spend, visitors]`, frequency `month`, and trains
**Then** the pipeline trains one auxiliary model per auxiliary column on date features, trains the target model on date features + **predicted** auxiliary values, and `test_metrics` includes per-target metrics; the bundle predicts target and `predicted_marketing_spend`/`predicted_visitors` for future dates.

## Scenario: Chart split is strictly chronological (never random)
**Given** any trained forecast
**When** the `chart` is produced and rendered
**Then** the `split_date` boundary equals the start of the last `TimeSeriesSplit` validation window, every `actuals` point before it is colored as *train* and every point from it through the last historical date is colored as *test*, the train window strictly precedes the test window in time, and no shuffled/random splitter is used anywhere in fitting or evaluation.

## Scenario: Multi-series overlay (target + auxiliaries)
**Given** a model trained with target `revenue` and auxiliaries `marketing_spend`, `visitors`
**When** the Evaluate chart renders
**Then** all three series are drawn overlaid on one chart, each line segmented into train/test/prediction using the shared `--chart-train`/`--chart-test`/`--chart-prediction` colors, the target is emphasized (thicker), and series are told apart by legend label; the `chart.series` object contains keys `revenue`, `marketing_spend`, `visitors`.

## Scenario: Runtime shows training results plus the new prediction
**Given** a downloaded forecasting `.luml` opened in Runtime
**When** the dashboard loads and the user runs a horizon prediction
**Then** the training-results chart is reconstructed from the bundle's `forecasting_chart:v1` metadata (train + test actuals + dashed test fit, same colors as Evaluate) **without** the original CSV, and the freshly predicted future is overlaid on the same chart in the `--chart-prediction` color (dashed) and offered as a CSV download.

## Scenario: Frequency-aware features for daily data
**Given** a CSV with a daily `date` column and target `load`
**When** the user picks frequency `day` and trains
**Then** `_make_date_features` produces `years_since_start` plus `day_of_week`, `day_of_year`, and `month` sin/cos features (not the monthly-only set), and the forecast date grid is generated at daily (`"D"`) frequency.

## Scenario: Forecast a single future date only
**Given** a trained-ready dataset
**When** the user picks a future end date and selects "Forecast for the selected date only"
**Then** the frontend sends exactly one date, and the `future` series / predictions contain a single record for that date.

## Scenario: Forecast the whole period up to a date
**Given** the same setup with "Forecast the whole period up to it"
**When** the user trains/predicts
**Then** the frontend generates every period from `last_training_date` to the end date at the chosen frequency, and the response contains one record per period.

## Scenario: Serialization roundtrip (artifact correctness)
**Given** a pipeline trained in the WASM worker and serialized via `save_forecasting`
**When** the resulting `.luml` is loaded through a fresh `fnnx` `Runtime` (the path used by Runtime/Satellite, with scikit-learn **absent** from the environment) and asked to predict the same future dates
**Then** the predictions equal (within floating tolerance) the in-memory `pipeline.predict(dates)` output, reconstruction uses `from_dict` + `predict_from_params` (no scikit-learn import), and the bundle's `env.json` lists `pandas`, `numpy`, `fnnx` but **not** `scikit-learn` or `joblib`.

## Scenario: Runtime upload-for-inference
**Given** a downloaded forecasting `.luml`
**When** the user opens Runtime, uploads the file, and enters a future end date + frequency horizon
**Then** `RuntimeDashboard` resolves the `forecasting_v1` tag to the forecasting dashboard, shows the stored metrics, and rendering the horizon predict returns a forecast chart + downloadable CSV.

## Scenario: Registry promotion surfaces metrics
**Given** a forecasting model promoted to a Collection
**When** the Registry reads the artifact
**Then** `FnnxService.getRegistryMetrics` returns the forecasting metrics (via the `registry_metrics:v1` meta entry written by `save_forecasting`) and they render on the model card.

## Scenario: Deployment serves forecasts on a Satellite (generic path)
**Given** a forecasting model deployed to a paired Satellite via the **same generic flow** as any other Express Task (`DeploymentsCreateModal` → `DeployTask` → `model_server`)
**When** the deployment comes up and an inference request with `{dates: [...]}` hits the Satellite endpoint
**Then** the `model_server` `OpenAPIGenerator` has auto-derived the `{dates}`→`{forecast}` schema from the manifest (rendered by `DeploymentSchemaPage.vue` with no forecasting-specific code), the server reconstructs the pipeline from the bundle's JSON `extra_values` (`from_dict`, no scikit-learn), runs `ForecastingPyFunc.compute` (pure numpy), and returns the forecast records.

## Scenario: No parseable date column (error)
**Given** a CSV where no column parses as dates
**When** the user reaches Forecast Setup
**Then** the date-column select shows a validation error / disables training, with a message that a valid date column is required (no train call is made).

## Scenario: Too few rows for cross-validation
**Given** a CSV with fewer than 4 usable rows
**When** the user trains
**Then** `cross_validate` raises a clear, surfaced error ("Not enough data points for forecasting evaluation") shown via the training error toast, and no model is produced.

## Scenario: Future end date not after the last training date (error)
**Given** the user picks an end date ≤ the dataset's last date
**When** they try to set the horizon
**Then** the UI blocks it with a message that the forecast end date must be after the last historical date.

## Scenario: Target equals date column (validation)
**Given** the user selects the same column for date and target
**When** they attempt to continue
**Then** the UI prevents it and prompts to pick distinct columns.

## Scenario: Non-numeric or missing target values
**Given** a target column with non-numeric or NaN entries
**When** training runs
**Then** `_prepare_data`/`_validate_input_columns` coerces/raises a clear error for non-numeric targets and drops/forward-handles NaN rows deterministically (documented behavior), surfaced via toast rather than an uncaught traceback.

## Scenario: MAPE with zero target values
**Given** a target series containing zeros
**When** metrics are computed
**Then** MAPE is computed only over non-zero rows (or returned `null`/omitted when all-zero), R²/MAE/RMSE/SC_SCORE are still computed, and the UI renders `—` for an absent MAPE.

## Scenario: Worker error is reported, not swallowed
**Given** any exception inside `forecasting_train`
**When** the worker `invoke` wraps it
**Then** it returns `{status:'error', error_type, error_message, traceback}` (existing `Router.invoke` behavior) and the frontend shows `trainingErrorToast` with the message, leaving the user on the setup step.

## Scenario: Model cleanup on unmount
**Given** trained models held in the worker `Store`
**When** the user navigates away from the forecasting flow or Runtime
**Then** `useForecastingTraining` calls `/forecasting/deallocate` (or `/store/deallocate`) for every tracked `model_id` on `onBeforeUnmount`.

---

# Tasks

- [ ] **Task 1 — WASM: forecasting engine + frequency-aware features**
  - [ ] Add `wasm/packages/dfs_webworker/dfs_webworker/forecasting.py` with the generalized `RidgeForecastingPipeline` (fields, `fit`, `predict`, `cross_validate`, `to_dict`/`from_dict`, pure-numpy `predict_from_params`, internal helpers). Guard scikit-learn imports so `from_dict`/`predict_from_params` need only numpy/pandas.
  - [ ] Implement `_make_date_features` with the per-frequency feature table (day/week/month/quarter/year) and `years_since_start` trend.
  - [ ] Implement metrics helpers `_mae`/`_rmse`/`_mape`/`_r2` and CV aggregation (mean over folds, small-data fallback/error). Use only `TimeSeriesSplit`; never a shuffled splitter.
  - [ ] Implement `chart_split(df) -> (split_date, test_index)` (last `TimeSeriesSplit` fold boundary) and `fit_window(df, test_index) -> dict[col -> list[{date,value}]]` (per-series held-out fit) for the train/test/fit chart.
  - [ ] Implement `generate_forecast_dates(last_date, end_date, frequency)` with the pandas offset-alias mapping.
  - [ ] Add constants to `dfs_webworker/constants.py` (`FORECASTING`, `FORECASTING_TAG`, `FORECASTING_METRICS_TAG`, `FORECASTING_CHART_TAG`).
  - [ ] Unit tests (mirror `wasm` test conventions): fit/predict shapes, each frequency's feature columns, auxiliary two-stage training, CV metrics, small-data error, MAPE-with-zeros (incl. fold aggregation skipping `None` folds and all-`None` → `None`), `chart_split` chronological (train indices all precede test indices), and `predict_from_params` matches the fitted `predict` within tolerance (numpy path correctness).

- [ ] **Task 2 — WASM: FNNX serialization (`save_forecasting`)**
  - [ ] Add `dfs_webworker/forecasting_serialization/__fnnx_pyfunc.py` (commented `ForecastingPyFunc`: `warmup` reconstructs `RidgeForecastingPipeline.from_dict(self.fnnx_context.get_value("pipeline"))`; `compute` runs `predict_from_params`).
  - [ ] Add `dfs_webworker/forecasting_serialization/__init__.py` `serialize(pipeline, metrics, fe_config)` using `PyfuncBuilder`: `add_module` the forecasting pipeline module, `set_extra_values({"pipeline": pipeline.to_dict()})` (JSON params — no pickle/`add_file`), define in/out dtypes, producer info + `forecasting:v1` tag, `meta.json` entries (`forecasting_metrics:v1` + `registry_metrics:v1` + `forecasting_chart:v1` with the embedded `{split_date, series}` chart payload), runtime deps **only** `fnnx`, `pyfnx_utils`, `pandas`, `numpy` pinned via `importlib.metadata` (no scikit-learn/joblib).
  - [ ] Roundtrip test (with scikit-learn import made to fail, to prove it's unused at serve time): train → `serialize` → load via `fnnx.Runtime` → predictions match in-memory `predict`; assert `env.json` has `pandas`/`numpy`/`fnnx` and **not** `scikit-learn`/`joblib`, manifest tag, and that the `forecasting_chart:v1` meta entry round-trips with per-series `actuals`/`test_fit` + `split_date`.

- [ ] **Task 3 — WASM: worker entry functions + routing**
  - [ ] In `forecasting.py`, add `forecasting_train`, `forecasting_predict`, `forecasting_deallocate` returning the documented `success(...)` payloads (train returns `train_metrics`, `test_metrics`, the structured multi-series `chart` object `{split_date, series:{<col>:{actuals,test_fit,future}}}` with `actuals` downsampled ≤ ~500 pts, and `model` bytes; predict returns per-series future records).
  - [ ] Register the three routes in `dfs_webworker/__init__.py` `Router` and export the functions.
  - [ ] Tests for the route handlers (train returns metrics + model bytes; predict by `model_id`; deallocate removes from `Store`; error payload on bad input).

- [ ] **Task 4 — Frontend: shared contract (interfaces, worker routes, FnnxService tags)**
  - [ ] Extend `lib/data-processing/interfaces.ts`: `Tasks.FORECASTING`, `WEBWORKER_ROUTES_ENUM` forecasting routes, `Frequency`, `ForecastingTaskPayload`, `ForecastingMetrics`, `ForecastPoint`/`ForecastingSeries`/`ForecastingChart`, `ForecastingTrainingData`.
  - [ ] Verify/extend `lib/data-processing/DataProcessingWorker.ts` dispatch for the new routes.
  - [ ] Add `toForecastSeries(records, columns)` normalizer (pivots wide `predicted_<col>` rows → per-series `ForecastPoint[]`) used by both predict paths (§7/§8), with a unit test covering the `/forecasting/predict` (`predictions`) and `/pyfunc/compute` (`predictions.forecast`) unwrapping.
  - [ ] Extend `lib/fnnx/FnnxService.ts`: add manifest tag `forecasting_v1`, metadata tag `contains_forecasting_metrics_v1`, `getForecastingData`, `getForecastingTotalScore`, `prepareForecastingMetrics`.
  - [ ] Unit tests for `FnnxService` forecasting tag/metrics extraction (extend `lib/fnnx/__tests__/FnnxService.test.ts`).

- [ ] **Task 5 — Frontend: task registration, routing, page shell**
  - [ ] `constants/constants.ts`: enable the Forecasting card (`linkName: 'forecasting'`, `btnText: 'next'`, dropdown options, analytics), add `forecastingSteps` and `forecastingResources`.
  - [ ] `router/index.ts`: add `/forecasting` route.
  - [ ] Add `pages/ForecastingPage.vue` rendering `ForecastingWrapper` (stub wrapper acceptable here, completed in Task 6).
  - [ ] Smoke test/route test that the card is enabled and `/forecasting` resolves.

- [ ] **Task 6 — Frontend: training flow (upload + setup + hook)**
  - [ ] `components/express-tasks/forecasting/ForecastingWrapper.vue`: 3-step Stepper; Step 1 upload (reuse `UploadData` + `useDataTable`, forecasting validators); Step 2 Forecast Setup (date/target/auxiliary role selects, frequency select, horizon end-date picker + single/whole-period toggle, with all validations from Scenarios).
  - [ ] `hooks/useForecastingTraining.ts`: `startTraining`/`startPredict`/`downloadModel`/`deleteModels`, metrics + chart-series getters, unmount cleanup.
  - [ ] Wire Step 2 → `startTraining` → advance to Step 3 on success.
  - [ ] Component tests for setup validations (no date column, target==date, end-date ≤ last date) and a successful train→advance flow (worker mocked).

- [ ] **Task 7 — Frontend: evaluation/results step**
  - [ ] Add `--chart-train`, `--chart-test`, `--chart-prediction` design tokens (`frontend/tokens` / style-dictionary) shared by Evaluate and Runtime.
  - [ ] `components/express-tasks/forecasting/evaluate/index.vue`: total-score widget + MAE/RMSE/MAPE/R² cards (MAPE `—` when null), and a single **overlaid multi-series** chart (reuse the existing chart component) rendering every `chart.series` entry with per-segment colors (train actuals / test actuals + dashed test fit / dashed future), `split_date` boundary, target emphasized, legend per series, and a `.luml` download.
  - [ ] Build a reusable `ForecastChart.vue` consuming `ForecastingChart` (+ optional live prediction series) so Runtime (Task 8) reuses it.
  - [ ] Add the interactive **predict control** (horizon picker) wired to `useForecastingTraining.startPredict` → `/forecasting/predict` (in-session `model_id`), overlaying the result in `--chart-prediction` + CSV download.
  - [ ] Component tests: metric rendering incl. null MAPE; chart maps each series to correct segment colors; train segment precedes test segment at `split_date`; re-predict overlays a new future series; download triggers blob.

- [ ] **Task 8 — Frontend: Runtime inference + Deployment verification**
  *(The Runtime dashboard is the bulk of this task; deployment is verification-only since it's fully generic — see §9. If an `/apply` session runs low on context, split into **8a Runtime dashboard** and **8b Deployment verification**.)*
  - [ ] `runtime/dashboard/RuntimeDashboard.vue`: map `forecasting_v1` → `runtime/dashboard/forecasting/index.vue`.
  - [ ] `runtime/dashboard/forecasting/index.vue`: performance card from bundle metrics; reconstruct the training-results chart from the `forecasting_chart:v1` metadata (reusing `ForecastChart.vue`, same tokens); horizon predict (end date + frequency + single/whole-period) via the generic pyfunc path (`useFnnxModel` auto-`/pyfunc/init` + `computePythonModel` → `/pyfunc/compute`, **not** `/forecasting/predict`), normalizing via `toForecastSeries`, with the new future overlaid in `--chart-prediction` + CSV export.
  - [ ] **Deployment is generic — no forecasting-specific UI.** Verify end-to-end on a real satellite that the forecasting `.luml` deploys via the existing flow (`DeploymentsCreateModal` → `DeployTask` → `model_server`), that `OpenAPIGenerator` auto-derives the `{dates}`→`{forecast}` schema from the manifest, that `DeploymentSchemaPage.vue` renders it, and that an inference call returns forecasts. Same path as a prompt-optimization deployment.
  - [ ] Confirm the satellite `model_server` builds the bundle env from `env.json` (only `pandas`/`numpy`/`fnnx`/`pyfnx_utils`), reconstructs the pipeline via `from_dict`, and computes forecasts with pure numpy (no scikit-learn/joblib). Confirm no `backend/luml` change is needed (deployment is artifact-generic, not task-whitelisted).
  - [ ] Tests: RuntimeDashboard resolves the forecasting tag; horizon predict builds the correct date grid and renders results.
