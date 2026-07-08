import pytest
import synth

from dfs_webworker import forecasting
from dfs_webworker.forecasting import ForecastingPipeline


def test_seasonal_monthly_detects_period_and_metrics():
    n = 48
    d = synth.dates(n, "MS")
    sales = synth.seasonal(n, seed=0, slope=2.0, amp=15.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "sales": sales}, "date", "sales", frequency="month"
    )

    P, D, Q, s = pipe.target_model.seasonal_order
    assert s == 12
    assert D == 1 or P > 0 or Q > 0  # some seasonal structure detected

    for key in ("MAE", "RMSE", "MAPE", "R2", "SC_SCORE"):
        assert key in pipe.test_metrics
    assert 0.0 <= pipe.test_metrics["SC_SCORE"] <= 1.0

    cfg = pipe.model_config()
    assert cfg["seasonal_period"] == 12
    assert cfg["frequency"] == "month"
    assert cfg["min_history"] == pipe.min_history
    assert "sales" in cfg["series"]

    series = pipe.chart["series"]["sales"]
    assert len(series["actuals"]) > 0
    assert len(series["test_fit"]) > 0


def test_short_series_disables_seasonality():
    n = 18  # fewer than two yearly cycles
    d = synth.dates(n, "MS")
    sales = synth.seasonal(n, seed=3, slope=1.0, amp=10.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "sales": sales}, "date", "sales", frequency="month"
    )

    assert pipe.target_model.seasonal_order == (0, 0, 0, 0)
    cfg_series = pipe.model_config()["series"]["sales"]
    assert cfg_series["seasonal_order"] == [0, 0, 0, 0]


def test_trending_nonseasonal_is_differenced_and_extrapolates():
    n = 60
    d = synth.dates(n, "MS")
    y = synth.trend(n, seed=1, slope=2.0, noise=1.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "y": y}, "date", "y", frequency="month"
    )

    order = pipe.target_model.order
    _, _, _, _ = pipe.target_model.seasonal_order
    D = pipe.target_model.seasonal_order[1]
    assert order[1] >= 1  # trend differencing selected by KPSS
    assert D == 0  # seasonal strength stays low for a pure trend
    assert pipe.target_model.trend in ("c", "n")

    history = synth.records(d, y=y)
    out = pipe.predict(history, horizon=6)
    forecasts = [r["predicted_y"] for r in out]
    assert forecasts[-1] > forecasts[0]  # trend continues upward


def test_convergence_fallback(monkeypatch):
    monkeypatch.setattr(forecasting, "_search_orders", lambda *a, **k: None)
    n = 36
    d = synth.dates(n, "MS")
    y = synth.trend(n, seed=5, slope=1.5)
    pipe = ForecastingPipeline.fit(
        {"date": d, "y": y}, "date", "y", frequency="month"
    )

    p, _, q = pipe.target_model.order
    assert p == 0 and q == 0  # (0, d, 0) fallback
    assert pipe.chart["series"]["y"]["actuals"]
    assert "SC_SCORE" in pipe.test_metrics


def test_year_frequency_has_no_seasonality():
    n = 30
    d = synth.dates(n, "YS")
    y = synth.trend(n, seed=2, slope=1.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "y": y}, "date", "y", frequency="year"
    )

    assert pipe.model_config()["seasonal_period"] == 0
    assert pipe.target_model.seasonal_order == (0, 0, 0, 0)


def test_training_below_hard_floor_raises():
    n = 8
    d = synth.dates(n, "MS")
    y = synth.trend(n, seed=0)
    with pytest.raises(ValueError, match="at least 12"):
        ForecastingPipeline.fit({"date": d, "y": y}, "date", "y", frequency="month")


def test_rows_with_missing_target_are_dropped_below_floor():
    n = 14
    d = synth.dates(n, "MS")
    y = synth.trend(n, seed=0).tolist()
    for i in range(4):
        y[i] = None  # only 10 usable rows remain
    with pytest.raises(ValueError, match="at least 12"):
        ForecastingPipeline.fit({"date": d, "y": y}, "date", "y", frequency="month")


def test_min_history_matches_formula():
    n = 48
    d = synth.dates(n, "MS")
    sales = synth.seasonal(n, seed=0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "sales": sales}, "date", "sales", frequency="month"
    )
    p, dd, q = pipe.target_model.order
    P, D, Q, s = pipe.target_model.seasonal_order
    expected = dd + D * s + max(p + s * P, q + s * Q) + 1
    assert pipe.target_model.min_history == expected
    assert pipe.min_history >= pipe.target_model.min_history
