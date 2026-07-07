"""SARIMAX forecasting engine with automatic configuration.

The pipeline fits one SARIMAX per auto-forecast auxiliary column plus one target
model that carries every auxiliary column as an exogenous regressor. Known-future
columns get no model of their own: the caller supplies their future values at
predict time. Models are fully JSON-serializable (orders + fitted parameter
vectors, never the training data) and predict via fixed-parameter Kalman
filtering on caller-supplied history.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import kpss

from dfs_webworker.store import Store
from dfs_webworker.utils import success

Frequency = str

_PERIOD_CODE: dict[Frequency, str] = {
    "day": "D",
    "week": "W",
    "month": "M",
    "quarter": "Q",
    "year": "Y",
}
_SEASONAL_PERIOD: dict[Frequency, int] = {
    "day": 7,
    "week": 52,
    "month": 12,
    "quarter": 4,
    "year": 0,
}

FREQUENCIES: tuple[Frequency, ...] = tuple(_PERIOD_CODE.keys())

Aggregation = str
AGGREGATIONS: tuple[Aggregation, ...] = ("mean", "sum")
DEFAULT_AGGREGATION: Aggregation = "mean"

MIN_TRAIN_ROWS = 12
SEASONAL_STRENGTH_THRESHOLD = 0.64
KPSS_SIGNIF = 0.05
MAX_P = MAX_Q = 3
MAX_SEASONAL = 1
MAX_CANDIDATE_FITS = 25
FIT_MAXITER = 50
CV_FOLDS = 3
# Back-test horizon for non-seasonal series (seasonal series use one full cycle).
NONSEASONAL_CV_HORIZON = 8
CHART_MAX_POINTS = 500
CONF_ALPHA = 0.05


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def _mae(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.mean(np.abs(y - yhat)))


def _rmse(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - yhat) ** 2)))


def _mape(y: np.ndarray, yhat: np.ndarray) -> float | None:
    # Ignore periods whose magnitude is negligible relative to the series scale
    # (e.g. holiday/closed-day near-zeros) so a tiny denominator cannot blow the
    # percentage error up to hundreds of percent.
    ay = np.abs(y)
    positive = ay[ay > 0.0]
    if not positive.size:
        return None
    threshold = 1e-3 * float(np.median(positive))
    mask = ay > threshold
    if not mask.any():
        return None
    return float(np.mean(np.abs((y[mask] - yhat[mask]) / y[mask])) * 100.0)


def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot == 0.0:
        return 0.0
    ss_res = float(np.sum((y - yhat) ** 2))
    return 1.0 - ss_res / ss_tot


def _baseline_lag(seasonal_order: tuple[int, int, int, int]) -> int:
    """Naive-baseline lag for MASE.

    Seasonal-naive (lag = period) only when the fitted model actually carries
    seasonal structure; otherwise one-step naive (lag 1). Using a seasonal
    baseline on a non-seasonal series would make the denominator artificially
    large and inflate the skill score, so the baseline is tied to what the model
    chose, not merely to the frequency.
    """
    seas_p, seas_d, seas_q, period = seasonal_order
    if period > 0 and (seas_p > 0 or seas_d > 0 or seas_q > 0):
        return period
    return 1


def _mase_scale(train: np.ndarray, m: int) -> float | None:
    """In-sample mean absolute error of the (seasonal) naive forecast on ``train``.

    Used as the MASE denominator. Falls back to the one-step naive (``m = 1``)
    when the series is too short for a full seasonal lag. Returns ``None`` when a
    stable positive scale cannot be computed (flat or too-short series).
    """
    train = np.asarray(train, dtype=float)
    lag = m if (m >= 1 and len(train) > m) else 1
    if len(train) <= lag:
        return None
    diffs = np.abs(train[lag:] - train[:-lag])
    if not diffs.size:
        return None
    scale = float(np.mean(diffs))
    if not math.isfinite(scale) or scale <= 0.0:
        return None
    return scale


def _metrics(
    y: np.ndarray, yhat: np.ndarray, scale: float | None = None
) -> dict[str, float | None]:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    mae = _mae(y, yhat)
    return {
        "MAE": mae,
        "RMSE": _rmse(y, yhat),
        "MAPE": _mape(y, yhat),
        "R2": _r2(y, yhat),
        "MASE": (mae / scale) if (scale is not None and scale > 0.0) else None,
    }


_METRIC_KEYS = ("MAE", "RMSE", "MAPE", "R2", "MASE")


def _aggregate_metrics(folds: list[dict[str, float | None]]) -> dict[str, float | None]:
    if not folds:
        return {key: None for key in _METRIC_KEYS}
    out: dict[str, float | None] = {}
    for key in _METRIC_KEYS:
        values = [f[key] for f in folds if f.get(key) is not None]
        out[key] = float(np.mean(values)) if values else None
    return out


def _clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return float(min(1.0, max(0.0, value)))


def _clamp_to_history(
    forecast: np.ndarray, history: np.ndarray, margin: float = 1.0
) -> np.ndarray:
    """Bound an auxiliary forecast to the range seen in its own history.

    Auto-forecast auxiliary series feed the target model as exogenous regressors;
    a diverging AR/MA fit can otherwise send them to ±1e9 and blow the target
    forecast up (observed R² of -4e6). Clipping to ``[min, max]`` padded by
    ``margin`` × range keeps the regressors physically plausible, and any
    non-finite value falls back to the last observed level.
    """
    history = np.asarray(history, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    if not history.size:
        return forecast
    lo = float(np.min(history))
    hi = float(np.max(history))
    span = hi - lo
    pad = margin * span if span > 0.0 else max(abs(hi), 1.0)
    last = float(history[-1])
    safe = np.where(np.isfinite(forecast), forecast, last)
    return np.clip(safe, lo - pad, hi + pad)


def _as_horizon(horizon: object) -> int:
    if isinstance(horizon, bool):
        raise ValueError("horizon must be a positive integer")
    if isinstance(horizon, float):
        if not horizon.is_integer():
            raise ValueError("horizon must be a positive integer")
        horizon = int(horizon)
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    return horizon


# --------------------------------------------------------------------------- #
# frames, dates, grid
# --------------------------------------------------------------------------- #
def _to_frame(data: object) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, dict):
        return pd.DataFrame(data)
    if isinstance(data, (list, tuple)):
        return pd.DataFrame.from_records(list(data))
    raise ValueError(f"Unsupported data container: {type(data).__name__}")


def _fmt_date(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _parse_dates(values: pd.Series, label: str) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    if parsed.isna().any():
        raise ValueError(f"{label} contains values that could not be parsed as dates")
    return parsed


def _to_numeric(values: pd.Series, column: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.isna().any():
        raise ValueError(f"Column '{column}' contains non-numeric values")
    return numeric


def _period_ordinals(dates: pd.Series, frequency: Frequency) -> np.ndarray:
    periods = pd.DatetimeIndex(dates).to_period(_PERIOD_CODE[frequency])
    return np.asarray(periods.astype("int64"))


def _validate_grid(dates: pd.Series, frequency: Frequency) -> None:
    ordinals = _period_ordinals(dates, frequency)
    diffs = np.diff(ordinals)
    dup = np.where(diffs == 0)[0]
    if dup.size:
        i = int(dup[0])
        raise ValueError(
            f"Duplicate date at the {frequency} frequency: "
            f"{_fmt_date(dates.iloc[i + 1])}"
        )
    gap = np.where(diffs > 1)[0]
    if gap.size:
        i = int(gap[0])
        raise ValueError(
            f"History has a gap in the {frequency} grid between "
            f"{_fmt_date(dates.iloc[i])} and {_fmt_date(dates.iloc[i + 1])}"
        )


def _aggregate_to_grid(
    df: pd.DataFrame,
    date_col: str,
    value_cols: list[str],
    frequency: Frequency,
    aggregation: Aggregation,
) -> pd.DataFrame:
    """Collapse rows that share a period at ``frequency`` into a single row.

    Numeric columns are combined with ``aggregation`` (``mean`` or ``sum``) and
    the earliest original date in each period represents it. This is a no-op when
    every period already holds exactly one row, so well-formed grids are left
    untouched; it only merges the sub-period duplicates that would otherwise make
    ``_validate_grid`` raise. Input is assumed already sorted by ``date_col``.
    """
    periods = pd.DatetimeIndex(df[date_col]).to_period(_PERIOD_CODE[frequency])
    agg_map: dict[str, str] = {date_col: "first"}
    for col in value_cols:
        agg_map[col] = aggregation
    grouped = (
        df.assign(_period=np.asarray(periods.astype("int64")))
        .groupby("_period", sort=True, as_index=False)
        .agg(agg_map)
    )
    return grouped[[date_col, *value_cols]].reset_index(drop=True)


def _generate_future_dates(
    last_date: pd.Timestamp, horizon: int, frequency: Frequency
) -> list[pd.Timestamp]:
    last = pd.Timestamp(last_date)
    if frequency == "day":
        return [last + pd.Timedelta(days=i) for i in range(1, horizon + 1)]
    if frequency == "week":
        return [last + pd.Timedelta(weeks=i) for i in range(1, horizon + 1)]
    base = last.to_period(_PERIOD_CODE[frequency])
    return [(base + i).to_timestamp() for i in range(1, horizon + 1)]


# --------------------------------------------------------------------------- #
# model spec
# --------------------------------------------------------------------------- #
@dataclass
class SeriesModel:
    name: str
    order: tuple[int, int, int]
    seasonal_order: tuple[int, int, int, int]
    trend: str
    params: list[float]
    param_names: list[str]
    k_exog: int
    min_history: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "order": list(self.order),
            "seasonal_order": list(self.seasonal_order),
            "trend": self.trend,
            "params": list(self.params),
            "param_names": list(self.param_names),
            "k_exog": self.k_exog,
            "min_history": self.min_history,
        }

    @classmethod
    def from_dict(cls, spec: dict) -> "SeriesModel":
        return cls(
            name=spec["name"],
            order=tuple(spec["order"]),
            seasonal_order=tuple(spec["seasonal_order"]),
            trend=spec["trend"],
            params=[float(p) for p in spec["params"]],
            param_names=list(spec["param_names"]),
            k_exog=int(spec["k_exog"]),
            min_history=int(spec["min_history"]),
        )

    def config_report(self) -> dict:
        return {
            "order": list(self.order),
            "seasonal_order": list(self.seasonal_order),
            "trend": self.trend,
            "min_history": self.min_history,
        }


def _min_history(order: tuple[int, int, int], seasonal_order: tuple[int, int, int, int]) -> int:
    p, d, q = order
    seas_p, seas_d, seas_q, s = seasonal_order
    return d + seas_d * s + max(p + s * seas_p, q + s * seas_q) + 1


def _build_sarimax(
    endog: np.ndarray,
    order: tuple[int, int, int],
    seasonal_order: tuple[int, int, int, int],
    trend: str,
    exog: np.ndarray | None = None,
) -> SARIMAX:
    return SARIMAX(
        np.asarray(endog, dtype=float),
        exog=(None if exog is None else np.asarray(exog, dtype=float)),
        order=order,
        seasonal_order=seasonal_order,
        trend=trend,
        enforce_stationarity=True,
        enforce_invertibility=True,
    )


def _fit(
    endog: np.ndarray,
    order: tuple[int, int, int],
    seasonal_order: tuple[int, int, int, int],
    trend: str,
    exog: np.ndarray | None = None,
):
    model = _build_sarimax(endog, order, seasonal_order, trend, exog)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return model.fit(disp=False, maxiter=FIT_MAXITER, method="lbfgs")


# --------------------------------------------------------------------------- #
# automatic configuration
# --------------------------------------------------------------------------- #
def _trend_term(d: int, seasonal_d: int) -> str:
    return "c" if (d + seasonal_d) <= 1 else "n"


def _detect_seasonal_diff(y: np.ndarray, s: int) -> int:
    if s <= 0 or len(y) < 3 * s:
        return 0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = STL(y, period=s, robust=True).fit()
    except Exception:
        return 0
    var_resid = float(np.var(result.resid))
    var_detrended = float(np.var(result.resid + result.seasonal))
    if var_detrended <= 0.0:
        return 0
    strength = max(0.0, 1.0 - var_resid / var_detrended)
    return 1 if strength > SEASONAL_STRENGTH_THRESHOLD else 0


def _seasonal_diff(y: np.ndarray, s: int) -> np.ndarray:
    return y[s:] - y[:-s]


def _detect_trend_diff(y: np.ndarray, s: int, seasonal_d: int) -> int:
    series = _seasonal_diff(y, s) if seasonal_d else y
    d = 0
    while d < 2 and len(series) >= 8:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pvalue = kpss(series, regression="c", nlags="auto")[1]
        except Exception:
            break
        if pvalue < KPSS_SIGNIF:
            series = np.diff(series)
            d += 1
        else:
            break
    return d


def _starting_orders(d: int, seasonal_d: int, seasonal: bool) -> list[tuple]:
    seas_hi = 1 if seasonal else 0
    p2, q2 = min(2, MAX_P), min(2, MAX_Q)
    p1, q1 = min(1, MAX_P), min(1, MAX_Q)
    return [
        (p2, d, q2, seas_hi, seasonal_d, seas_hi),
        (0, d, 0, 0, seasonal_d, 0),
        (p1, d, 0, seas_hi, seasonal_d, 0),
        (0, d, q1, 0, seasonal_d, seas_hi),
    ]


def _neighbors(state: tuple, s: int, seasonal: bool) -> list[tuple]:
    p, d, q, seas_p, seasonal_d, seas_q = state
    moves: list[tuple] = []
    for dp in (-1, 1):
        moves.append((p + dp, d, q, seas_p, seasonal_d, seas_q))
        moves.append((p, d, q + dp, seas_p, seasonal_d, seas_q))
        if seasonal:
            moves.append((p, d, q, seas_p + dp, seasonal_d, seas_q))
            moves.append((p, d, q, seas_p, seasonal_d, seas_q + dp))
    valid = []
    for m in moves:
        mp, _, mq, msp, _, msq = m
        if 0 <= mp <= MAX_P and 0 <= mq <= MAX_Q and 0 <= msp <= MAX_SEASONAL and 0 <= msq <= MAX_SEASONAL:
            valid.append(m)
    return valid


def _search_orders(
    y: np.ndarray, s: int, seasonal_d: int, d: int, exog: np.ndarray | None
):
    seasonal = s > 0
    trend = _trend_term(d, seasonal_d)
    tried: set[tuple] = set()
    best_state: tuple | None = None
    best_res = None
    # BIC penalises extra parameters more heavily than AICc (log(n)·k vs 2k),
    # so the search prefers simpler models that generalise better out of sample.
    best_bic = math.inf
    fits = 0

    def evaluate(state: tuple):
        nonlocal fits, best_state, best_res, best_bic
        if state in tried or fits >= MAX_CANDIDATE_FITS:
            return
        tried.add(state)
        p, sd, q, seas_p, ssd, seas_q = state
        order = (p, sd, q)
        seasonal_order = (seas_p, ssd, seas_q, s if seasonal else 0)
        try:
            res = _fit(y, order, seasonal_order, trend, exog)
        except Exception:
            return
        finally:
            fits += 1
        bic = getattr(res, "bic", math.inf)
        if not math.isfinite(bic):
            return
        if bic < best_bic:
            best_bic = bic
            best_state = state
            best_res = res

    for state in _starting_orders(d, seasonal_d, seasonal):
        evaluate(state)

    improved = True
    while improved and fits < MAX_CANDIDATE_FITS:
        improved = False
        if best_state is None:
            break
        anchor = best_state
        for neighbor in _neighbors(anchor, s, seasonal):
            before = best_bic
            evaluate(neighbor)
            if best_bic < before:
                improved = True

    if best_res is None or best_state is None:
        return None
    p, sd, q, seas_p, ssd, seas_q = best_state
    return best_res, (p, sd, q), (seas_p, ssd, seas_q, s if seasonal else 0), trend


def _auto_fit_series(
    name: str, y: np.ndarray, frequency: Frequency, exog: np.ndarray | None = None
) -> tuple[SeriesModel, object]:
    n = len(y)
    period = _SEASONAL_PERIOD[frequency]
    seasonal = period > 0 and n >= 2 * period + 1
    s = period if seasonal else 0
    seasonal_d = _detect_seasonal_diff(y, s) if seasonal else 0
    d = _detect_trend_diff(y, s, seasonal_d)

    searched = _search_orders(y, s, seasonal_d, d, exog)
    if searched is not None:
        res, order, seasonal_order, trend = searched
    else:
        order = (0, d, 0)
        seasonal_order = (0, seasonal_d, 0, s)
        trend = _trend_term(d, seasonal_d)
        res = _fit(y, order, seasonal_order, trend, exog)

    model = SeriesModel(
        name=name,
        order=order,
        seasonal_order=seasonal_order,
        trend=trend,
        params=[float(p) for p in np.asarray(res.params, dtype=float)],
        param_names=list(res.param_names),
        k_exog=0 if exog is None else int(exog.shape[1]),
        min_history=_min_history(order, seasonal_order),
    )
    return model, res


# --------------------------------------------------------------------------- #
# cross-validation folds
# --------------------------------------------------------------------------- #
def _make_folds(
    n: int, min_train: int, horizon: int, max_folds: int = CV_FOLDS
) -> list[tuple[int, int]]:
    """Rolling-origin folds with a fixed, realistic forecast horizon.

    Each fold trains on an expanding prefix ``[0:train_end]`` and forecasts
    ``horizon`` steps over a non-overlapping window, walking back from the end so
    the most recent data is always tested. The horizon is capped so at least one
    fold fits. The previous scheme split the whole series into ``k`` equal chunks,
    which on a long series meant back-testing forecasts hundreds of steps ahead
    (e.g. 123 months) and made every metric look terrible; a horizon of one
    seasonal cycle keeps the evaluation meaningful.
    """
    horizon = max(1, min(int(horizon), n - min_train))
    folds: list[tuple[int, int]] = []
    train_end = n - horizon
    while len(folds) < max_folds and train_end >= min_train:
        folds.append((train_end, horizon))
        train_end -= horizon
    folds.reverse()
    return folds


def _downsample(points: list[dict], max_points: int = CHART_MAX_POINTS) -> list[dict]:
    if len(points) <= max_points:
        return points
    idx = np.unique(np.linspace(0, len(points) - 1, max_points).round().astype(int))
    return [points[i] for i in idx]


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #
@dataclass
class ForecastingPipeline:
    date_col: str
    target_col: str
    aux_cols: list[str]
    known_future_cols: list[str]
    frequency: Frequency
    target_model: SeriesModel
    aux_models: dict[str, SeriesModel]
    min_history: int
    aggregation: Aggregation = DEFAULT_AGGREGATION
    train_metrics: dict[str, float | None] = field(default_factory=dict)
    test_metrics: dict[str, float | None] = field(default_factory=dict)
    series_test_metrics: dict[str, dict[str, float | None]] = field(default_factory=dict)
    split_date: str | None = None
    chart: dict = field(default_factory=dict)

    # ---- construction ---------------------------------------------------- #
    @property
    def auto_forecast_cols(self) -> list[str]:
        return [c for c in self.aux_cols if c not in self.known_future_cols]

    @classmethod
    def fit(
        cls,
        data: object,
        date_col: str,
        target_col: str,
        aux_cols: list[str] | None = None,
        known_future_cols: list[str] | None = None,
        frequency: Frequency = "month",
        preview_horizon: int | None = None,
        aggregation: Aggregation = DEFAULT_AGGREGATION,
    ) -> "ForecastingPipeline":
        aux_cols = list(aux_cols or [])
        known_future_cols = list(known_future_cols or [])
        _validate_roles(date_col, target_col, aux_cols, known_future_cols, frequency)
        aggregation = _validate_aggregation(aggregation)
        if preview_horizon is not None and known_future_cols:
            raise ValueError(
                "A preview horizon cannot be used when known-future columns are "
                "marked; their future values are supplied on the Evaluate screen."
            )

        df = _clean_training_frame(
            data, date_col, target_col, aux_cols, frequency, aggregation
        )
        n = len(df)
        if n < MIN_TRAIN_ROWS:
            raise ValueError(
                f"Not enough data to train: at least {MIN_TRAIN_ROWS} usable rows "
                f"are required, got {n}"
            )

        target = df[target_col].to_numpy(dtype=float)
        exog = (
            np.column_stack([df[c].to_numpy(dtype=float) for c in aux_cols])
            if aux_cols
            else None
        )
        auto_cols = [c for c in aux_cols if c not in known_future_cols]

        aux_models: dict[str, SeriesModel] = {}
        aux_results: dict[str, object] = {}
        for col in auto_cols:
            model, res = _auto_fit_series(col, df[col].to_numpy(dtype=float), frequency)
            aux_models[col] = model
            aux_results[col] = res

        target_model, target_res = _auto_fit_series(target_col, target, frequency, exog)

        min_history = max(
            [target_model.min_history] + [m.min_history for m in aux_models.values()]
        )

        pipeline = cls(
            date_col=date_col,
            target_col=target_col,
            aux_cols=aux_cols,
            known_future_cols=known_future_cols,
            frequency=frequency,
            target_model=target_model,
            aux_models=aux_models,
            min_history=min_history,
            aggregation=aggregation,
        )
        pipeline._evaluate(df, target_res, aux_results, preview_horizon)
        return pipeline

    # ---- serialization --------------------------------------------------- #
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "date_col": self.date_col,
            "target_col": self.target_col,
            "aux_cols": list(self.aux_cols),
            "known_future_cols": list(self.known_future_cols),
            "frequency": self.frequency,
            "aggregation": self.aggregation,
            "min_history": self.min_history,
            "target_model": self.target_model.to_dict(),
            "aux_models": {k: v.to_dict() for k, v in self.aux_models.items()},
        }

    @classmethod
    def from_dict(cls, spec: dict) -> "ForecastingPipeline":
        return cls(
            date_col=spec["date_col"],
            target_col=spec["target_col"],
            aux_cols=list(spec["aux_cols"]),
            known_future_cols=list(spec["known_future_cols"]),
            frequency=spec["frequency"],
            target_model=SeriesModel.from_dict(spec["target_model"]),
            aux_models={
                k: SeriesModel.from_dict(v) for k, v in spec["aux_models"].items()
            },
            min_history=int(spec["min_history"]),
            aggregation=spec.get("aggregation", DEFAULT_AGGREGATION),
        )

    def model_config(self) -> dict:
        series = {self.target_col: self.target_model.config_report()}
        for col, model in self.aux_models.items():
            series[col] = model.config_report()
        return {
            "frequency": self.frequency,
            "seasonal_period": _SEASONAL_PERIOD[self.frequency],
            "aggregation": self.aggregation,
            "date_col": self.date_col,
            "target_col": self.target_col,
            "aux_cols": list(self.aux_cols),
            "known_future_cols": list(self.known_future_cols),
            "min_history": self.min_history,
            "series": series,
        }

    # ---- prediction ------------------------------------------------------ #
    def predict(
        self, history: object, horizon: int, future: object | None = None
    ) -> list[dict]:
        horizon = _as_horizon(horizon)

        df = self._validate_history(history)
        last_date = df[self.date_col].iloc[-1]
        forecast_dates = _generate_future_dates(last_date, horizon, self.frequency)
        future_df = self._validate_future(future, forecast_dates)

        aux_forecasts: dict[str, np.ndarray] = {}
        for col, model in self.aux_models.items():
            aux_forecasts[col] = self._filter_forecast(
                df[col].to_numpy(dtype=float), model, horizon
            )

        if self.aux_cols:
            hist_exog = np.column_stack(
                [df[c].to_numpy(dtype=float) for c in self.aux_cols]
            )
            future_cols = []
            for col in self.aux_cols:
                if col in self.known_future_cols:
                    assert future_df is not None  # guaranteed by _validate_future
                    future_cols.append(future_df[col].to_numpy(dtype=float))
                else:
                    future_cols.append(aux_forecasts[col])
            future_exog: np.ndarray | None = np.column_stack(future_cols)
        else:
            hist_exog = None
            future_exog = None

        target_res = _build_sarimax(
            df[self.target_col].to_numpy(dtype=float),
            self.target_model.order,
            self.target_model.seasonal_order,
            self.target_model.trend,
            hist_exog,
        ).filter(np.asarray(self.target_model.params, dtype=float))
        forecast = target_res.get_forecast(steps=horizon, exog=future_exog)
        mean = np.asarray(forecast.predicted_mean, dtype=float)
        conf = np.asarray(forecast.conf_int(alpha=CONF_ALPHA), dtype=float)

        records: list[dict] = []
        for i, date in enumerate(forecast_dates):
            record = {
                self.date_col: _fmt_date(date),
                f"predicted_{self.target_col}": float(mean[i]),
                f"predicted_{self.target_col}_lower": float(conf[i, 0]),
                f"predicted_{self.target_col}_upper": float(conf[i, 1]),
            }
            for col in self.auto_forecast_cols:
                record[f"predicted_{col}"] = float(aux_forecasts[col][i])
            records.append(record)
        return records

    def _filter_forecast(
        self, endog: np.ndarray, model: SeriesModel, horizon: int
    ) -> np.ndarray:
        res = _build_sarimax(
            endog, model.order, model.seasonal_order, model.trend
        ).filter(np.asarray(model.params, dtype=float))
        forecast = np.asarray(res.get_forecast(steps=horizon).predicted_mean, dtype=float)
        return _clamp_to_history(forecast, endog)

    def _validate_history(self, history: object) -> pd.DataFrame:
        df = _to_frame(history)
        required = [self.date_col, self.target_col, *self.aux_cols]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"History is missing required column(s): {', '.join(missing)}"
            )
        dates = _parse_dates(df[self.date_col], "History date column")
        df = df.assign(**{self.date_col: dates})
        for col in [self.target_col, *self.aux_cols]:
            df[col] = _to_numeric(df[col], col)
        df = df.sort_values(self.date_col).reset_index(drop=True)
        df = _aggregate_to_grid(
            df, self.date_col, [self.target_col, *self.aux_cols], self.frequency, self.aggregation
        )
        _validate_grid(df[self.date_col], self.frequency)
        if len(df) < self.min_history:
            raise ValueError(
                f"Not enough history: this model requires at least "
                f"{self.min_history} rows, got {len(df)}"
            )
        return df

    def _validate_future(
        self, future: object | None, forecast_dates: list[pd.Timestamp]
    ) -> pd.DataFrame | None:
        has_future = future is not None and len(_to_frame(future)) > 0
        if not self.known_future_cols:
            if has_future:
                raise ValueError(
                    "This model has no known-future columns; 'future' must not be "
                    "provided"
                )
            return None
        if not has_future:
            raise ValueError(
                "This model requires future values for known-future column(s): "
                f"{', '.join(self.known_future_cols)}"
            )

        fdf = _to_frame(future)
        if self.date_col not in fdf.columns:
            raise ValueError("future records must include the date column")
        extra_cols = [
            c
            for c in fdf.columns
            if c != self.date_col and c not in self.known_future_cols
        ]
        if extra_cols:
            raise ValueError(
                f"future contains unexpected column(s): {', '.join(extra_cols)}"
            )
        missing_cols = [c for c in self.known_future_cols if c not in fdf.columns]
        if missing_cols:
            raise ValueError(
                f"future is missing known-future column(s): {', '.join(missing_cols)}"
            )

        dates = _parse_dates(fdf[self.date_col], "future date column")
        fdf = fdf.assign(**{self.date_col: dates})
        for col in self.known_future_cols:
            fdf[col] = _to_numeric(fdf[col], col)
        fdf = fdf.sort_values(self.date_col).reset_index(drop=True)
        fdf = _aggregate_to_grid(
            fdf, self.date_col, list(self.known_future_cols), self.frequency, self.aggregation
        )

        expected = pd.DatetimeIndex(forecast_dates).to_period(
            _PERIOD_CODE[self.frequency]
        )
        provided = pd.DatetimeIndex(fdf[self.date_col]).to_period(
            _PERIOD_CODE[self.frequency]
        )
        if provided.has_duplicates:
            raise ValueError("future contains duplicate dates")
        expected_set = set(expected)
        provided_set = set(provided)
        missing_dates = sorted(str(p) for p in expected_set - provided_set)
        if missing_dates:
            raise ValueError(
                f"future is missing values for forecast date(s): "
                f"{', '.join(missing_dates)}"
            )
        extra_dates = sorted(str(p) for p in provided_set - expected_set)
        if extra_dates:
            raise ValueError(
                f"future has values for date(s) outside the horizon: "
                f"{', '.join(extra_dates)}"
            )

        ordered = fdf.set_index(provided).loc[expected].reset_index(drop=True)
        return ordered

    # ---- evaluation ------------------------------------------------------ #
    def _evaluate(
        self,
        df: pd.DataFrame,
        target_res: object,
        aux_results: dict[str, object],
        preview_horizon: int | None,
    ) -> None:
        target = df[self.target_col].to_numpy(dtype=float)
        exog = (
            np.column_stack([df[c].to_numpy(dtype=float) for c in self.aux_cols])
            if self.aux_cols
            else None
        )

        self.train_metrics = _in_sample_metrics(target_res, target, self.target_model)
        series_train = {self.target_col: self.train_metrics}
        for col, res in aux_results.items():
            series_train[col] = _in_sample_metrics(
                res, df[col].to_numpy(dtype=float), self.aux_models[col]
            )

        cv = self._cross_validate(df, target, exog)
        self.series_test_metrics = cv["series_metrics"]
        self.test_metrics = dict(cv["series_metrics"].get(self.target_col, {}))
        # Headline score = variance explained (R²). MASE is kept in the metrics as
        # a separate "does it beat seasonal-naive?" signal, but a genuinely
        # accurate model that merely matches naive should not read as 0%.
        target_r2 = self.test_metrics.get("R2")
        if target_r2 is None:
            target_r2 = self.train_metrics.get("R2")
        self.test_metrics["SC_SCORE"] = _clamp01(target_r2)
        self.split_date = cv["split_date"]
        self.chart = self._build_chart(df, cv, preview_horizon)

    def _cross_validate(
        self, df: pd.DataFrame, target: np.ndarray, exog: np.ndarray | None
    ) -> dict:
        n = len(target)
        min_train = max(self.min_history, MIN_TRAIN_ROWS // 2 + 2)
        period = _SEASONAL_PERIOD[self.frequency]
        horizon = period if period > 0 else NONSEASONAL_CV_HORIZON
        folds = _make_folds(n, min_train, horizon)
        series_folds: dict[str, list[dict]] = {self.target_col: []}
        for col in self.auto_forecast_cols:
            series_folds[col] = []

        last_fit: dict | None = None
        for train_end, h in folds:
            fold = self._run_fold(df, target, exog, train_end, h, series_folds)
            if fold is not None:
                last_fit = fold

        series_metrics = {
            col: _aggregate_metrics(vals) for col, vals in series_folds.items()
        }
        split_date = (
            _fmt_date(df[self.date_col].iloc[last_fit["train_end"]])
            if last_fit is not None
            else None
        )
        return {
            "series_metrics": series_metrics,
            "split_date": split_date,
            "last_fit": last_fit,
        }

    def _run_fold(
        self,
        df: pd.DataFrame,
        target: np.ndarray,
        exog: np.ndarray | None,
        train_end: int,
        h: int,
        series_folds: dict[str, list[dict]],
    ) -> dict | None:
        try:
            target_res = _fit(
                target[:train_end],
                self.target_model.order,
                self.target_model.seasonal_order,
                self.target_model.trend,
                None if exog is None else exog[:train_end],
            )
            aux_fold_forecasts: dict[str, np.ndarray] = {}
            future_cols = []
            for col in self.aux_cols:
                actual = df[col].to_numpy(dtype=float)
                if col in self.known_future_cols:
                    future_cols.append(actual[train_end : train_end + h])
                else:
                    model = self.aux_models[col]
                    res = _fit(
                        actual[:train_end], model.order, model.seasonal_order, model.trend
                    )
                    forecast = np.asarray(
                        res.get_forecast(steps=h).predicted_mean, dtype=float
                    )
                    # Keep the regressor plausible so a diverging aux fit cannot
                    # explode the target forecast it feeds.
                    forecast = _clamp_to_history(forecast, actual[:train_end])
                    aux_fold_forecasts[col] = forecast
                    future_cols.append(forecast)
                    series_folds[col].append(
                        _metrics(
                            actual[train_end : train_end + h],
                            forecast,
                            _mase_scale(actual[:train_end], _baseline_lag(model.seasonal_order)),
                        )
                    )
            future_exog = np.column_stack(future_cols) if future_cols else None
            forecast = target_res.get_forecast(steps=h, exog=future_exog)
            target_forecast = np.asarray(forecast.predicted_mean, dtype=float)
            series_folds[self.target_col].append(
                _metrics(
                    target[train_end : train_end + h],
                    target_forecast,
                    _mase_scale(
                        target[:train_end],
                        _baseline_lag(self.target_model.seasonal_order),
                    ),
                )
            )
        except Exception:
            return None
        conf = np.asarray(forecast.conf_int(alpha=CONF_ALPHA), dtype=float)
        return {
            "train_end": train_end,
            "h": h,
            "target": target_forecast,
            "target_lower": conf[:, 0],
            "target_upper": conf[:, 1],
            "aux": aux_fold_forecasts,
        }

    def _build_chart(
        self, df: pd.DataFrame, cv: dict, preview_horizon: int | None
    ) -> dict:
        dates = df[self.date_col]
        iso_dates = [_fmt_date(d) for d in dates]
        series: dict[str, dict] = {}

        def actuals(col: str) -> list[dict]:
            values = df[col].to_numpy(dtype=float)
            return _downsample(
                [{"date": iso_dates[i], "value": float(values[i])} for i in range(len(values))]
            )

        series[self.target_col] = {"actuals": actuals(self.target_col)}
        for col in self.auto_forecast_cols:
            series[col] = {"actuals": actuals(col)}
        for col in self.known_future_cols:
            series[col] = {"actuals": actuals(col)}

        last_fit = cv["last_fit"]
        if last_fit is not None:
            start = last_fit["train_end"]
            fit_dates = iso_dates[start : start + last_fit["h"]]
            target_fit = [
                {
                    "date": fit_dates[i],
                    "value": float(last_fit["target"][i]),
                    "lower": float(last_fit["target_lower"][i]),
                    "upper": float(last_fit["target_upper"][i]),
                }
                for i in range(len(fit_dates))
            ]
            series[self.target_col]["test_fit"] = target_fit
            for col in self.auto_forecast_cols:
                fit = last_fit["aux"].get(col)
                if fit is None:
                    continue
                series[col]["test_fit"] = [
                    {"date": fit_dates[i], "value": float(fit[i])}
                    for i in range(len(fit_dates))
                ]

        if preview_horizon:
            self._add_future_preview(df, series, preview_horizon)

        return {"split_date": cv["split_date"], "series": series}

    def _add_future_preview(
        self, df: pd.DataFrame, series: dict[str, dict], horizon: int
    ) -> None:
        records = self.predict(df, horizon)
        for record in records:
            date = record[self.date_col]
            target_series = series[self.target_col].setdefault("future", [])
            target_series.append(
                {
                    "date": date,
                    "value": record[f"predicted_{self.target_col}"],
                    "lower": record[f"predicted_{self.target_col}_lower"],
                    "upper": record[f"predicted_{self.target_col}_upper"],
                }
            )
            for col in self.auto_forecast_cols:
                series[col].setdefault("future", []).append(
                    {"date": date, "value": record[f"predicted_{col}"]}
                )


def _in_sample_metrics(
    res: Any, y: np.ndarray, model: SeriesModel
) -> dict[str, float | None]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        predicted = np.asarray(res.get_prediction().predicted_mean).astype(float)
    p, d, q = model.order
    seas_p, seas_d, seas_q, s = model.seasonal_order
    burn = min(d + seas_d * s, len(y) - 2)
    burn = max(burn, 0)
    actual = np.asarray(y, dtype=float)[burn:]
    predicted = predicted[burn:]
    mask = np.isfinite(predicted)
    return _metrics(
        actual[mask], predicted[mask], _mase_scale(y, _baseline_lag(model.seasonal_order))
    )


def _validate_roles(
    date_col: str,
    target_col: str,
    aux_cols: list[str],
    known_future_cols: list[str],
    frequency: Frequency,
) -> None:
    if frequency not in _PERIOD_CODE:
        raise ValueError(
            f"Unsupported frequency '{frequency}'. Choose one of "
            f"{', '.join(FREQUENCIES)}"
        )
    if date_col == target_col:
        raise ValueError("The date column and target column must be different")
    if target_col in aux_cols or date_col in aux_cols:
        raise ValueError(
            "Auxiliary columns must be distinct from the date and target columns"
        )
    if len(set(aux_cols)) != len(aux_cols):
        raise ValueError("Auxiliary columns must be unique")
    unknown = [c for c in known_future_cols if c not in aux_cols]
    if unknown:
        raise ValueError(
            f"Known-future columns must be auxiliary columns: {', '.join(unknown)}"
        )


def _validate_aggregation(aggregation: Aggregation) -> Aggregation:
    if aggregation not in AGGREGATIONS:
        raise ValueError(
            f"Unsupported aggregation '{aggregation}'. Choose one of "
            f"{', '.join(AGGREGATIONS)}"
        )
    return aggregation


def _clean_training_frame(
    data: object,
    date_col: str,
    target_col: str,
    aux_cols: list[str],
    frequency: Frequency,
    aggregation: Aggregation,
) -> pd.DataFrame:
    df = _to_frame(data)
    required = [date_col, target_col, *aux_cols]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Training data is missing required column(s): {', '.join(missing)}"
        )
    df = df[required].copy()
    df[date_col] = _parse_dates(df[date_col], "Training date column")
    for col in [target_col, *aux_cols]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=[target_col, *aux_cols]).reset_index(drop=True)
    df = df.sort_values(date_col).reset_index(drop=True)
    df = _aggregate_to_grid(df, date_col, [target_col, *aux_cols], frequency, aggregation)
    _validate_grid(df[date_col], frequency)
    return df


# --------------------------------------------------------------------------- #
# worker routes
# --------------------------------------------------------------------------- #
def forecasting_train(
    data: object,
    date_col: str,
    target_col: str,
    aux_cols: list[str] | None = None,
    known_future_cols: list[str] | None = None,
    frequency: Frequency = "month",
    preview_horizon: int | None = None,
    aggregation: Aggregation = DEFAULT_AGGREGATION,
) -> dict:
    # Local import breaks the forecasting <-> forecasting_serialization cycle.
    from dfs_webworker.forecasting_serialization import serialize

    pipeline = ForecastingPipeline.fit(
        data,
        date_col=date_col,
        target_col=target_col,
        aux_cols=aux_cols,
        known_future_cols=known_future_cols,
        frequency=frequency,
        preview_horizon=preview_horizon,
        aggregation=aggregation,
    )
    model_config = pipeline.model_config()
    model_bytes = serialize(
        pipeline, pipeline.test_metrics, model_config, pipeline.chart
    )
    model_id = Store.save(pipeline)
    return success(
        model_id=model_id,
        train_metrics=pipeline.train_metrics,
        test_metrics=pipeline.test_metrics,
        model_config=model_config,
        chart=pipeline.chart,
        model=model_bytes,
    )


def forecasting_predict(
    model_id: str,
    history: object,
    horizon: int,
    future: object | None = None,
) -> dict:
    pipeline = Store.get(model_id)
    if not isinstance(pipeline, ForecastingPipeline):
        raise ValueError(f"Model {model_id} is not a forecasting model")
    forecast = pipeline.predict(history, horizon, future)
    return success(forecast=forecast)


def forecasting_deallocate(model_id: str) -> dict:
    Store.delete(model_id)
    return success()
