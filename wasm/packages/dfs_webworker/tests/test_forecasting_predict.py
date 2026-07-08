import json

import numpy as np
import pytest
import synth

from dfs_webworker.forecasting import ForecastingPipeline


def _univariate(n=48, seed=1, freq="MS", frequency="month"):
    d = synth.dates(n, freq)
    y = synth.trend(n, seed=seed, slope=2.0)
    pipe = ForecastingPipeline.fit(
        {"date": d, "y": y}, "date", "y", frequency=frequency
    )
    return pipe, d, y


def _two_stage(n=48, seed=0):
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(seed)
    spend = 50 + 10 * np.sin(2 * np.pi * np.arange(n) / 12) + rng.normal(0, 2, n)
    visitors = 200 + 3 * np.arange(n) + rng.normal(0, 5, n)
    revenue = 100 + 1.5 * spend + 0.4 * visitors + rng.normal(0, 3, n)
    pipe = ForecastingPipeline.fit(
        {"date": d, "revenue": revenue, "marketing_spend": spend, "visitors": visitors},
        "date",
        "revenue",
        aux_cols=["marketing_spend", "visitors"],
        frequency="month",
    )
    return pipe, d, {"revenue": revenue, "marketing_spend": spend, "visitors": visitors}


def _known_future(n=48, seed=2):
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(seed)
    visitors = 200 + 2 * np.arange(n) + rng.normal(0, 5, n)
    promo = (np.arange(n) % 4 == 0).astype(float)
    sales = 100 + 0.5 * visitors + 20 * promo + rng.normal(0, 3, n)
    pipe = ForecastingPipeline.fit(
        {"date": d, "sales": sales, "visitors": visitors, "promo": promo},
        "date",
        "sales",
        aux_cols=["visitors", "promo"],
        known_future_cols=["promo"],
        frequency="month",
    )
    return pipe, d, {"sales": sales, "visitors": visitors, "promo": promo}


# --------------------------------------------------------------------------- #
# fixed-weight prediction
# --------------------------------------------------------------------------- #
def test_fixed_weight_level_shift_reflected():
    pipe, d, y = _univariate()
    assert pipe.target_model.order[1] + pipe.target_model.seasonal_order[1] >= 1

    history = synth.records(d, y=y)
    shifted = synth.records(d, y=y + 500.0)

    base = [r["predicted_y"] for r in pipe.predict(history, horizon=6)]
    lifted = [r["predicted_y"] for r in pipe.predict(shifted, horizon=6)]

    # Filtering carries the new window's level; no refit -> forecast shifts by +500.
    for a, b in zip(base, lifted):
        assert abs((b - a) - 500.0) < 1e-3


def test_prediction_is_deterministic():
    pipe, d, y = _univariate()
    history = synth.records(d, y=y)
    first = pipe.predict(history, horizon=8)
    second = pipe.predict(history, horizon=8)
    assert first == second


def test_json_spec_roundtrip_predicts_identically():
    pipe, d, y = _univariate()
    history = synth.records(d, y=y)
    reloaded = ForecastingPipeline.from_dict(json.loads(json.dumps(pipe.to_dict())))
    assert reloaded.predict(history, 5) == pipe.predict(history, 5)
    # no training observations leak into the spec
    blob = json.dumps(pipe.to_dict())
    assert "actuals" not in blob


def test_unsupported_spec_version_is_rejected():
    pipe, _, _ = _univariate()
    spec = pipe.to_dict()
    assert spec["version"] == 1
    spec["version"] = 2
    with pytest.raises(ValueError, match="version"):
        ForecastingPipeline.from_dict(spec)


def test_forecast_dates_are_consecutive_periods_after_last():
    pipe, d, y = _univariate()
    out = pipe.predict(synth.records(d, y=y), horizon=4)
    assert [r["date"] for r in out] == [
        "2024-01-01",
        "2024-02-01",
        "2024-03-01",
        "2024-04-01",
    ]


def test_horizon_must_be_positive_integer():
    pipe, d, y = _univariate()
    history = synth.records(d, y=y)
    for bad in (0, -3, 2.5, "4", True):
        with pytest.raises(ValueError, match="horizon"):
            pipe.predict(history, bad)
    assert len(pipe.predict(history, 3.0)) == 3  # integral float accepted


# --------------------------------------------------------------------------- #
# history validation
# --------------------------------------------------------------------------- #
def test_too_little_history_names_required_and_supplied():
    pipe, d, y = _univariate()
    short = synth.records(d[: pipe.min_history - 1], y=y[: pipe.min_history - 1])
    with pytest.raises(ValueError) as exc:
        pipe.predict(short, horizon=3)
    message = str(exc.value)
    assert str(pipe.min_history) in message
    assert str(pipe.min_history - 1) in message


def test_history_gap_is_rejected():
    pipe, d, y = _univariate()
    rows = synth.records(d, y=y)
    del rows[len(rows) // 2]  # skip a month -> grid gap
    with pytest.raises(ValueError, match="gap"):
        pipe.predict(rows, horizon=3)


def test_history_duplicate_dates_are_aggregated_not_rejected():
    # Sub-period duplicates are merged onto the grid by the model's aggregation
    # (mean by default), so a duplicated row must not change the forecast.
    pipe, d, y = _univariate()
    rows = synth.records(d, y=y)
    with_dup = rows + [dict(rows[-1])]
    assert pipe.predict(with_dup, horizon=3) == pipe.predict(rows, horizon=3)


def test_missing_aux_column_is_rejected():
    pipe, d, cols = _two_stage()
    rows = synth.records(d, revenue=cols["revenue"], visitors=cols["visitors"])
    with pytest.raises(ValueError, match="marketing_spend"):
        pipe.predict(rows, horizon=3)


def test_non_numeric_history_is_rejected():
    pipe, d, y = _univariate()
    rows = synth.records(d, y=y)
    rows[0]["y"] = "not-a-number"
    with pytest.raises(ValueError, match="non-numeric"):
        pipe.predict(rows, horizon=3)


# --------------------------------------------------------------------------- #
# two-stage exogenous flow
# --------------------------------------------------------------------------- #
def test_two_stage_builds_aux_models_and_exog_target():
    pipe, d, cols = _two_stage()
    assert set(pipe.aux_models) == {"marketing_spend", "visitors"}
    assert pipe.target_model.k_exog == 2

    history = synth.records(
        d,
        revenue=cols["revenue"],
        marketing_spend=cols["marketing_spend"],
        visitors=cols["visitors"],
    )
    out = pipe.predict(history, horizon=4)
    rec = out[0]
    assert "predicted_revenue" in rec
    assert "predicted_revenue_lower" in rec
    assert "predicted_revenue_upper" in rec
    assert "predicted_marketing_spend" in rec
    assert "predicted_visitors" in rec


# --------------------------------------------------------------------------- #
# known-future covariates
# --------------------------------------------------------------------------- #
def test_known_future_has_no_model_or_metrics():
    pipe, d, cols = _known_future()
    assert "promo" not in pipe.aux_models
    assert "visitors" in pipe.aux_models
    assert "promo" not in pipe.series_test_metrics
    assert "visitors" in pipe.series_test_metrics
    assert pipe.known_future_cols == ["promo"]


def test_known_future_output_omits_the_column():
    pipe, d, cols = _known_future()
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    horizon = 4
    fdates = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
    future = [{"date": fdates[i], "promo": float(i % 2)} for i in range(horizon)]

    out = pipe.predict(history, horizon, future)
    rec = out[0]
    assert "predicted_sales" in rec and "predicted_sales_lower" in rec
    assert "predicted_visitors" in rec
    assert "promo" not in rec
    assert "predicted_promo" not in rec


def test_known_future_values_feed_the_target():
    pipe, d, cols = _known_future()
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    horizon = 4
    fdates = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
    low = [{"date": fdates[i], "promo": 0.0} for i in range(horizon)]
    high = [{"date": fdates[i], "promo": 1.0} for i in range(horizon)]

    low_sales = [r["predicted_sales"] for r in pipe.predict(history, horizon, low)]
    high_sales = [r["predicted_sales"] for r in pipe.predict(history, horizon, high)]
    assert any(abs(a - b) > 1e-6 for a, b in zip(low_sales, high_sales))


def test_future_required_when_known_future_present():
    pipe, d, cols = _known_future()
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    with pytest.raises(ValueError, match="promo"):
        pipe.predict(history, horizon=4)


def test_future_missing_date_is_rejected():
    pipe, d, cols = _known_future()
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    future = [
        {"date": "2024-01-01", "promo": 1.0},
        {"date": "2024-02-01", "promo": 0.0},
        {"date": "2024-04-01", "promo": 1.0},  # 2024-03 missing
    ]
    with pytest.raises(ValueError, match="missing"):
        pipe.predict(history, horizon=4, future=future)


def test_future_extra_date_is_rejected():
    pipe, d, cols = _known_future()
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    future = [
        {"date": f"2024-0{i}-01", "promo": 1.0} for i in range(1, 6)
    ]  # 5 dates for horizon 4
    with pytest.raises(ValueError, match="outside the horizon"):
        pipe.predict(history, horizon=4, future=future)


def test_future_missing_known_future_column_is_rejected():
    pipe, d, cols = _known_future()
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    future = [{"date": f"2024-0{i}-01"} for i in range(1, 5)]
    with pytest.raises(ValueError, match="promo"):
        pipe.predict(history, horizon=4, future=future)


def test_future_extra_column_is_rejected():
    pipe, d, cols = _known_future()
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    future = [
        {"date": f"2024-0{i}-01", "promo": 1.0, "unexpected": 2.0}
        for i in range(1, 5)
    ]
    with pytest.raises(ValueError, match="unexpected"):
        pipe.predict(history, horizon=4, future=future)


def test_future_rejected_when_no_known_future_columns():
    pipe, d, y = _univariate()
    history = synth.records(d, y=y)
    future = [{"date": "2024-01-01", "whatever": 1.0}]
    with pytest.raises(ValueError, match="no known-future"):
        pipe.predict(history, horizon=1, future=future)
