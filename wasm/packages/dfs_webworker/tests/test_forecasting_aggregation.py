"""Aggregation contract: sub-period rows collapse onto the frequency grid via
the pipeline's ``mean``/``sum`` setting, at train and predict time, and the
setting survives the JSON spec roundtrip."""

import pandas as pd
import pytest
import synth

from dfs_webworker.forecasting import (
    ForecastingPipeline,
    _aggregate_to_grid,
    _clean_training_frame,
    _validate_aggregation,
)


def _frame(dates: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "y": values})


def _manual_pipeline(aggregation: str = "mean") -> ForecastingPipeline:
    """Fit-free constant-mean pipeline (order (0,0,0), trend c): cheap and
    deterministic for exercising predict-time validation paths."""
    return ForecastingPipeline.from_dict(
        {
            "version": 1,
            "date_col": "date",
            "target_col": "y",
            "aux_cols": [],
            "known_future_cols": [],
            "frequency": "month",
            "aggregation": aggregation,
            "min_history": 1,
            "target_model": {
                "name": "y",
                "order": [0, 0, 0],
                "seasonal_order": [0, 0, 0, 0],
                "trend": "c",
                "params": [5.0, 1.0],
                "param_names": ["intercept", "sigma2"],
                "k_exog": 0,
                "min_history": 1,
            },
            "aux_models": {},
        }
    )


# --------------------------------------------------------------------------- #
# _aggregate_to_grid
# --------------------------------------------------------------------------- #
def test_aggregate_to_grid_mean_and_sum():
    df = _frame(
        ["2020-01-05", "2020-01-20", "2020-02-10"],
        [10.0, 30.0, 7.0],
    )
    mean = _aggregate_to_grid(df, "date", ["y"], "month", "mean")
    assert mean["y"].tolist() == [20.0, 7.0]

    total = _aggregate_to_grid(df, "date", ["y"], "month", "sum")
    assert total["y"].tolist() == [40.0, 7.0]


def test_aggregate_to_grid_keeps_earliest_date_per_period():
    df = _frame(["2020-01-05", "2020-01-20"], [1.0, 2.0])
    out = _aggregate_to_grid(df, "date", ["y"], "month", "sum")
    assert out["date"].tolist() == [pd.Timestamp("2020-01-05")]


def test_aggregate_to_grid_is_noop_on_clean_grid():
    df = _frame(["2020-01-01", "2020-02-01", "2020-03-01"], [1.0, 2.0, 3.0])
    out = _aggregate_to_grid(df, "date", ["y"], "month", "sum")
    pd.testing.assert_frame_equal(out, df)


def test_unsupported_aggregation_is_rejected():
    with pytest.raises(ValueError, match="median"):
        _validate_aggregation("median")


# --------------------------------------------------------------------------- #
# training-frame and predict-time aggregation
# --------------------------------------------------------------------------- #
def test_clean_training_frame_applies_sum_aggregation():
    df = _clean_training_frame(
        {
            "date": ["2020-01-05", "2020-01-20", "2020-02-10"],
            "y": [10.0, 30.0, 7.0],
        },
        "date",
        "y",
        [],
        "month",
        "sum",
    )
    assert df["y"].tolist() == [40.0, 7.0]


def test_validate_history_honors_pipeline_aggregation():
    rows = [
        {"date": "2020-01-05", "y": 10.0},
        {"date": "2020-01-20", "y": 30.0},
        {"date": "2020-02-10", "y": 7.0},
    ]
    assert _manual_pipeline("mean")._validate_history(rows)["y"].tolist() == [20.0, 7.0]
    assert _manual_pipeline("sum")._validate_history(rows)["y"].tolist() == [40.0, 7.0]


def test_fit_with_sum_aggregation_trains_on_summed_series():
    n = 24
    months = synth.dates(n, "MS")
    y = synth.trend(n, seed=0, slope=2.0)
    # two half-value rows per month -> summed grid equals the original series
    dates = [d for d in months for _ in range(2)]
    halves = [float(v) / 2.0 for v in y for _ in range(2)]
    pipe = ForecastingPipeline.fit(
        {"date": dates, "y": halves},
        "date",
        "y",
        frequency="month",
        aggregation="sum",
    )
    assert pipe.model_config()["aggregation"] == "sum"
    actuals = pipe.chart["series"]["y"]["actuals"]
    assert [p["value"] for p in actuals] == pytest.approx(list(y))


# --------------------------------------------------------------------------- #
# spec roundtrip
# --------------------------------------------------------------------------- #
def test_aggregation_survives_spec_roundtrip():
    spec = _manual_pipeline("sum").to_dict()
    assert spec["aggregation"] == "sum"
    assert ForecastingPipeline.from_dict(spec).aggregation == "sum"


def test_missing_aggregation_defaults_to_mean():
    spec = _manual_pipeline("sum").to_dict()
    del spec["aggregation"]
    assert ForecastingPipeline.from_dict(spec).aggregation == "mean"
