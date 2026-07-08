import numpy as np
import synth

from dfs_webworker.forecasting import (
    ForecastingPipeline,
    _aggregate_metrics,
    _mape,
    _metrics,
)


def test_mape_ignores_zero_actuals():
    y = np.array([0.0, 10.0, 0.0, 20.0])
    yhat = np.array([1.0, 11.0, 2.0, 18.0])
    # only the two non-zero actuals contribute: (|11-10|/10 + |18-20|/20)/2 * 100
    expected = (0.1 + 0.1) / 2 * 100
    assert abs(_mape(y, yhat) - expected) < 1e-9


def test_mape_all_zero_is_none():
    y = np.zeros(5)
    yhat = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert _mape(y, yhat) is None


def test_metrics_mape_none_for_all_zero_series():
    y = np.zeros(4)
    yhat = np.array([1.0, 2.0, 3.0, 4.0])
    m = _metrics(y, yhat)
    assert m["MAPE"] is None
    assert m["MAE"] is not None and m["RMSE"] is not None and m["R2"] is not None


def test_aggregate_skips_none_mape_folds():
    folds = [
        {"MAE": 1.0, "RMSE": 1.0, "MAPE": None, "R2": 0.5},
        {"MAE": 3.0, "RMSE": 3.0, "MAPE": 20.0, "R2": 0.7},
    ]
    agg = _aggregate_metrics(folds)
    assert agg["MAPE"] == 20.0  # None fold skipped
    assert agg["MAE"] == 2.0  # MAE/RMSE/R2 aggregate normally
    assert agg["R2"] == 0.6


def test_aggregate_all_none_mape_stays_none():
    folds = [
        {"MAE": 1.0, "RMSE": 1.0, "MAPE": None, "R2": 0.5},
        {"MAE": 3.0, "RMSE": 3.0, "MAPE": None, "R2": 0.7},
    ]
    agg = _aggregate_metrics(folds)
    assert agg["MAPE"] is None
    assert agg["MAE"] == 2.0


def test_mape_with_zeros_integration_does_not_crash():
    n = 40
    d = synth.dates(n, "MS")
    base = synth.trend(n, seed=4, level=5.0, slope=0.0, noise=1.0)
    y = np.clip(base, 0, None)
    y[::5] = 0.0  # inject zeros
    pipe = ForecastingPipeline.fit(
        {"date": d, "y": y}, "date", "y", frequency="month"
    )
    assert "MAPE" in pipe.test_metrics  # None or a float, but present
    assert 0.0 <= pipe.test_metrics["SC_SCORE"] <= 1.0


def test_cv_split_is_chronological():
    n = 48
    d = synth.dates(n, "MS")
    sales = synth.seasonal(n, seed=0, slope=2.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "sales": sales}, "date", "sales", frequency="month"
    )

    assert pipe.split_date is not None
    actuals = pipe.chart["series"]["sales"]["actuals"]
    dates_seen = [p["date"] for p in actuals]
    assert dates_seen == sorted(dates_seen)  # never shuffled

    split = pipe.split_date
    test_fit = pipe.chart["series"]["sales"]["test_fit"]
    assert all(p["date"] >= split for p in test_fit)  # fit is out-of-sample


def test_cv_uses_actual_holdout_values_for_known_future():
    # promo is an impactful but unforecastable binary signal. When it is
    # known-future, CV must feed the target its ACTUAL holdout values (so the
    # target tracks the ±30 swings and scores well); when it is auto-forecast,
    # the target only sees a poor forecast of promo and scores far worse.
    n = 48
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(7)
    promo = (rng.random(n) > 0.5).astype(float)
    sales = 100 + 0.2 * np.arange(n) + 30.0 * promo + rng.normal(0, 1.0, n)

    known_future = ForecastingPipeline.fit(
        {"date": d, "sales": sales, "promo": promo},
        "date",
        "sales",
        aux_cols=["promo"],
        known_future_cols=["promo"],
        frequency="month",
    )
    auto_forecast = ForecastingPipeline.fit(
        {"date": d, "sales": sales, "promo": promo},
        "date",
        "sales",
        aux_cols=["promo"],
        known_future_cols=[],
        frequency="month",
    )

    assert known_future.test_metrics["R2"] > 0.5
    assert known_future.test_metrics["R2"] > auto_forecast.test_metrics["R2"] + 0.3
    # metrics only for the modelled (auto-forecast) series, never the known-future one
    assert "promo" not in known_future.series_test_metrics
    assert "promo" in auto_forecast.series_test_metrics


def test_sc_score_equals_clamped_test_r2():
    n = 48
    d = synth.dates(n, "MS")
    sales = synth.seasonal(n, seed=0, slope=2.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "sales": sales}, "date", "sales", frequency="month"
    )
    r2 = pipe.test_metrics["R2"]
    assert pipe.test_metrics["SC_SCORE"] == min(1.0, max(0.0, r2))


def test_chart_downsamples_actuals():
    n = 700
    d = synth.dates(n, "D")
    y = synth.trend(n, seed=7, slope=0.1, noise=1.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "y": y}, "date", "y", frequency="day"
    )
    assert len(pipe.chart["series"]["y"]["actuals"]) <= 500


def test_preview_future_segment_added_when_no_known_future():
    n = 48
    d = synth.dates(n, "MS")
    sales = synth.seasonal(n, seed=0, slope=2.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "sales": sales}, "date", "sales", frequency="month", preview_horizon=6
    )
    future = pipe.chart["series"]["sales"].get("future")
    assert future is not None and len(future) == 6
    assert all("lower" in p and "upper" in p for p in future)


def test_preview_rejected_with_known_future_columns():
    n = 48
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(0)
    visitors = 200 + 2 * np.arange(n) + rng.normal(0, 5, n)
    promo = (np.arange(n) % 4 == 0).astype(float)
    sales = 100 + 0.5 * visitors + 20 * promo + rng.normal(0, 3, n)
    import pytest

    with pytest.raises(ValueError, match="preview"):
        ForecastingPipeline.fit(
            {"date": d, "sales": sales, "visitors": visitors, "promo": promo},
            "date",
            "sales",
            aux_cols=["visitors", "promo"],
            known_future_cols=["promo"],
            frequency="month",
            preview_horizon=6,
        )
