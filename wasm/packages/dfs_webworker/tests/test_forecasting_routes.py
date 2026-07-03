"""Route-level tests for the forecasting worker entry points.

Exercises ``forecasting_train``/``predict``/``deallocate`` both directly and
through the async ``invoke`` dispatcher, covering the train payload shape, the
fixed-weight predict-by-model-id path, ``Store`` cleanup, the known-future
future-values flow, and the ``{status:'error', ...}`` contract (Scenario:
worker error is reported, not swallowed).
"""

import asyncio

import numpy as np
import pytest
import synth

from dfs_webworker import invoke
from dfs_webworker.forecasting import (
    ForecastingPipeline,
    forecasting_predict,
    forecasting_train,
)
from dfs_webworker.store import Store
from dfs_webworker.types import FakeJsProxy


def _invoke(route: str, payload: dict) -> dict:
    return asyncio.run(invoke(route, FakeJsProxy(payload)))


def _univariate_data(n: int = 40, seed: int = 1):
    return synth.dates(n, "MS"), synth.trend(n, seed=seed, slope=2.0)


@pytest.fixture(scope="module")
def trained():
    d, y = _univariate_data()
    result = forecasting_train(
        {"date": d, "y": y}, "date", "y", frequency="month", preview_horizon=6
    )
    return result, d, y


@pytest.fixture(scope="module")
def trained_known_future():
    n = 48
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(2)
    visitors = 200 + 2 * np.arange(n) + rng.normal(0, 5, n)
    promo = (np.arange(n) % 4 == 0).astype(float)
    sales = 100 + 0.5 * visitors + 20 * promo + rng.normal(0, 3, n)
    result = forecasting_train(
        {"date": d, "sales": sales, "visitors": visitors, "promo": promo},
        "date",
        "sales",
        aux_cols=["visitors", "promo"],
        known_future_cols=["promo"],
        frequency="month",
    )
    return result, d, {"sales": sales, "visitors": visitors, "promo": promo}


# --------------------------------------------------------------------------- #
# train
# --------------------------------------------------------------------------- #
def test_train_returns_expected_payload_shape(trained):
    result, _, _ = trained
    assert result["status"] == "success"
    assert set(result) >= {
        "model_id",
        "train_metrics",
        "test_metrics",
        "model_config",
        "chart",
        "model",
    }
    assert isinstance(result["model_id"], str) and result["model_id"]
    assert isinstance(result["model"], bytes) and result["model"]

    assert set(result["train_metrics"]) >= {"MAE", "RMSE", "MAPE", "R2"}
    assert set(result["test_metrics"]) >= {"MAE", "RMSE", "MAPE", "R2", "SC_SCORE"}

    config = result["model_config"]
    assert config["frequency"] == "month"
    assert config["min_history"] >= 1
    assert config["known_future_cols"] == []
    assert "y" in config["series"]

    chart = result["chart"]
    assert "split_date" in chart
    assert chart["series"]["y"]["actuals"]


def test_train_stores_live_pipeline(trained):
    result, _, _ = trained
    assert isinstance(Store.get(result["model_id"]), ForecastingPipeline)


def test_train_chart_carries_future_preview_when_requested(trained):
    result, _, _ = trained
    # preview_horizon=6 was passed -> the training chart gets a future segment
    assert result["chart"]["series"]["y"]["future"]


def test_train_rejects_preview_horizon_with_known_future():
    n = 48
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(2)
    visitors = 200 + 2 * np.arange(n) + rng.normal(0, 5, n)
    promo = (np.arange(n) % 4 == 0).astype(float)
    sales = 100 + 0.5 * visitors + 20 * promo + rng.normal(0, 3, n)
    result = _invoke(
        "/forecasting/train",
        {
            "data": {
                "date": d,
                "sales": sales.tolist(),
                "visitors": visitors.tolist(),
                "promo": promo.tolist(),
            },
            "date_col": "date",
            "target_col": "sales",
            "aux_cols": ["visitors", "promo"],
            "known_future_cols": ["promo"],
            "frequency": "month",
            "preview_horizon": 6,
        },
    )
    assert result["status"] == "error"
    assert result["error_type"] == "ValueError"
    assert "preview horizon" in result["error_message"].lower()


# --------------------------------------------------------------------------- #
# predict by model id
# --------------------------------------------------------------------------- #
def test_predict_fresh_history_reflects_level_without_refit(trained):
    result, d, y = trained
    model_id = result["model_id"]
    order = result["model_config"]["series"]["y"]["order"]
    seasonal = result["model_config"]["series"]["y"]["seasonal_order"]
    assert order[1] + seasonal[1] >= 1  # differenced -> filtering carries the level

    base = forecasting_predict(model_id, synth.records(d, y=y), 6)["forecast"]
    lifted = forecasting_predict(model_id, synth.records(d, y=y + 500.0), 6)["forecast"]

    assert len(base) == 6
    assert set(base[0]) == {
        "date",
        "predicted_y",
        "predicted_y_lower",
        "predicted_y_upper",
    }
    for a, b in zip(base, lifted):
        assert abs((b["predicted_y"] - a["predicted_y"]) - 500.0) < 1e-3


def test_predict_dates_follow_last_history_date(trained):
    result, d, y = trained
    out = forecasting_predict(result["model_id"], synth.records(d, y=y), 4)["forecast"]
    dates = [r["date"] for r in out]
    assert len(dates) == 4
    assert dates[0] > d[-1]  # ISO strings sort chronologically
    assert dates == sorted(dates) and len(set(dates)) == 4


def test_predict_known_future_via_route(trained_known_future):
    result, d, cols = trained_known_future
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    fdates = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
    future = [{"date": fdates[i], "promo": float(i % 2)} for i in range(4)]

    out = forecasting_predict(result["model_id"], history, 4, future)["forecast"]
    assert set(out[0]) == {
        "date",
        "predicted_sales",
        "predicted_sales_lower",
        "predicted_sales_upper",
        "predicted_visitors",
    }
    assert "promo" not in out[0] and "predicted_promo" not in out[0]


def test_predict_rejects_wrong_model_type():
    model_id = Store.save({"not": "a pipeline"})
    try:
        with pytest.raises(ValueError, match="not a forecasting model"):
            forecasting_predict(model_id, [], 3)
    finally:
        Store.delete(model_id)


# --------------------------------------------------------------------------- #
# deallocate + invoke dispatch
# --------------------------------------------------------------------------- #
def test_deallocate_removes_model_via_invoke():
    d, y = _univariate_data(n=36, seed=3)
    model_id = forecasting_train({"date": d, "y": y}, "date", "y", frequency="month")[
        "model_id"
    ]
    assert model_id in Store._store
    assert _invoke("/forecasting/deallocate", {"model_id": model_id}) == {
        "status": "success"
    }
    assert model_id not in Store._store


def test_invoke_dispatches_predict(trained):
    result, d, y = trained
    res = _invoke(
        "/forecasting/predict",
        {"model_id": result["model_id"], "history": synth.records(d, y=y), "horizon": 3},
    )
    assert res["status"] == "success"
    assert len(res["forecast"]) == 3


# --------------------------------------------------------------------------- #
# error payloads (Scenario: worker error is reported, not swallowed)
# --------------------------------------------------------------------------- #
def test_invoke_wraps_training_error_payload():
    d, y = _univariate_data()
    res = _invoke(
        "/forecasting/train",
        {
            "data": {"date": d, "y": y.tolist()},
            "date_col": "date",
            "target_col": "does_not_exist",
            "frequency": "month",
        },
    )
    assert res["status"] == "error"
    assert res["error_type"] == "ValueError"
    assert "does_not_exist" in res["error_message"]
    assert res["traceback"]


def test_invoke_wraps_predict_validation_error_payload(trained_known_future):
    result, d, cols = trained_known_future
    history = synth.records(
        d, sales=cols["sales"], visitors=cols["visitors"], promo=cols["promo"]
    )
    # known-future model called without `future` -> validation error, wrapped
    res = _invoke(
        "/forecasting/predict",
        {"model_id": result["model_id"], "history": history, "horizon": 4},
    )
    assert res["status"] == "error"
    assert res["error_type"] == "ValueError"
    assert "promo" in res["error_message"]
