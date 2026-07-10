"""Serialization roundtrip tests: train -> serialize -> load via fnnx -> predict.

Covers the "Serialization roundtrip without refitting" scenario plus the env,
tag, meta, dtype, and predict-validation contracts of the FNNX bundle. The
fnnx runtime loads bundles without pydantic, so bundle metadata is read back by
inspecting the tar directly (the pydantic-based ``fnnx.extras.reader.Reader`` is
unavailable in this env).
"""

import importlib
import json
import sys
import tarfile
from contextlib import contextmanager

import numpy as np
import pandas as pd
import pytest
import synth
from fnnx.runtime import Runtime

from dfs_webworker.constants import (
    FORECASTING_CHART_TAG,
    FORECASTING_METRICS_TAG,
    FORECASTING_PRODUCER,
    FORECASTING_TAG,
    REGISTRY_METRICS_TAG,
)
from dfs_webworker.forecasting import ForecastingPipeline
from dfs_webworker.forecasting_serialization import serialize


def _serialize(pipe: ForecastingPipeline) -> bytes:
    return serialize(pipe, pipe.test_metrics, pipe.model_config(), pipe.chart)


def _runtime(blob: bytes, tmp_path) -> Runtime:
    path = tmp_path / "model.pyfnx"
    path.write_bytes(blob)
    return Runtime(str(path))


def _member(blob: bytes, tmp_path, name: str):
    path = tmp_path / "read.pyfnx"
    path.write_bytes(blob)
    with tarfile.open(path) as tar:
        return json.loads(tar.extractfile(tar.getmember(name)).read().decode())


def _members(blob: bytes, tmp_path) -> list[str]:
    path = tmp_path / "read.pyfnx"
    path.write_bytes(blob)
    with tarfile.open(path) as tar:
        return tar.getnames()


def _future_records(history: list[dict], horizon: int, cols: list[str]) -> list[dict]:
    last = pd.Timestamp(history[-1]["date"])
    dates = pd.date_range(last, periods=horizon + 1, freq="MS")[1:]
    return [
        {"date": d.strftime("%Y-%m-%d"), **{c: float(i % 2) for c in cols}}
        for i, d in enumerate(dates)
    ]


def _assert_forecast_close(a: list[dict], b: list[dict], tol: float = 1e-6) -> None:
    assert len(a) == len(b)
    for ra, rb in zip(a, b):
        assert set(ra) == set(rb)
        for key, va in ra.items():
            if isinstance(va, str):
                assert va == rb[key]
            else:
                assert va == pytest.approx(rb[key], abs=tol, rel=tol)


# --------------------------------------------------------------------------- #
# fitted pipelines (module-scoped: fitting is the expensive part)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def univariate():
    d = synth.dates(40, "MS")
    y = synth.trend(40, seed=1, slope=2.0)
    pipe = ForecastingPipeline.fit({"date": d, "y": y}, "date", "y", frequency="month")
    return pipe, synth.records(d, y=y)


@pytest.fixture(scope="module")
def two_stage():
    n = 48
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(0)
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
    history = synth.records(d, revenue=revenue, marketing_spend=spend, visitors=visitors)
    return pipe, history


@pytest.fixture(scope="module")
def known_future():
    n = 48
    d = synth.dates(n, "MS")
    rng = np.random.default_rng(2)
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
    history = synth.records(d, sales=sales, visitors=visitors, promo=promo)
    return pipe, history


# --------------------------------------------------------------------------- #
# roundtrip: predictions match the in-memory pipeline
# --------------------------------------------------------------------------- #
def test_roundtrip_matches_in_memory_univariate(univariate, tmp_path):
    pipe, history = univariate
    runtime = _runtime(_serialize(pipe), tmp_path)
    result = runtime.compute({"in": {"history": history, "horizon": 6}}, {})
    forecast = result["out"]["forecast"]

    assert len(forecast) == 6
    assert set(forecast[0]) == {
        "date",
        "predicted_y",
        "predicted_y_lower",
        "predicted_y_upper",
    }
    _assert_forecast_close(forecast, pipe.predict(history, 6))


def test_roundtrip_matches_in_memory_two_stage(two_stage, tmp_path):
    pipe, history = two_stage
    runtime = _runtime(_serialize(pipe), tmp_path)
    result = runtime.compute({"in": {"history": history, "horizon": 5}}, {})
    forecast = result["out"]["forecast"]

    # target with bounds + a point forecast per auto-forecast auxiliary
    assert set(forecast[0]) == {
        "date",
        "predicted_revenue",
        "predicted_revenue_lower",
        "predicted_revenue_upper",
        "predicted_marketing_spend",
        "predicted_visitors",
    }
    _assert_forecast_close(forecast, pipe.predict(history, 5))


def test_roundtrip_matches_in_memory_known_future(known_future, tmp_path):
    pipe, history = known_future
    horizon = 4
    future = _future_records(history, horizon, ["promo"])
    runtime = _runtime(_serialize(pipe), tmp_path)
    result = runtime.compute(
        {"in": {"history": history, "horizon": horizon, "future": future}}, {}
    )
    forecast = result["out"]["forecast"]

    # promo is known-future: no field of any kind for it in the output
    assert set(forecast[0]) == {
        "date",
        "predicted_sales",
        "predicted_sales_lower",
        "predicted_sales_upper",
        "predicted_visitors",
    }
    _assert_forecast_close(forecast, pipe.predict(history, horizon, future))


def test_prediction_is_deterministic_across_calls(univariate, tmp_path):
    pipe, history = univariate
    runtime = _runtime(_serialize(pipe), tmp_path)
    first = runtime.compute({"in": {"history": history, "horizon": 6}}, {})
    second = runtime.compute({"in": {"history": history, "horizon": 6}}, {})
    assert first["out"]["forecast"] == second["out"]["forecast"]


@contextmanager
def _dfs_webworker_unimportable():
    """Simulate the fnnx serve environment, where dfs_webworker is absent.

    Every cached dfs_webworker module is dropped (plus any previously loaded
    bundled ``forecasting`` module, so the import inside the bundle re-runs)
    and the package is poisoned: ``sys.modules[name] = None`` makes any import
    attempt raise ImportError immediately.
    """
    saved = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "forecasting"
        or name == "dfs_webworker"
        or name.startswith("dfs_webworker.")
    }
    sys.modules["dfs_webworker"] = None  # type: ignore[assignment]
    try:
        yield
    finally:
        del sys.modules["dfs_webworker"]
        sys.modules.pop("forecasting", None)
        sys.modules.update(saved)


def test_bundle_runs_standalone_without_dfs_webworker(univariate, tmp_path):
    # The bundled forecasting module must not import dfs_webworker at module
    # level: in-process tests would never catch such a regression because the
    # package is importable here, so it is explicitly made unimportable.
    pipe, history = univariate
    blob = _serialize(pipe)
    with _dfs_webworker_unimportable():
        with pytest.raises(ImportError):
            importlib.import_module("dfs_webworker.store")
        runtime = _runtime(blob, tmp_path)
        result = runtime.compute({"in": {"history": history, "horizon": 4}}, {})
    forecast = result["out"]["forecast"]
    assert len(forecast) == 4
    _assert_forecast_close(forecast, pipe.predict(history, 4))


# --------------------------------------------------------------------------- #
# bundle shape: no pickle, JSON spec only
# --------------------------------------------------------------------------- #
def test_bundle_carries_json_spec_and_no_pickle(univariate, tmp_path):
    pipe, _ = univariate
    blob = _serialize(pipe)

    names = _members(blob, tmp_path)
    assert not [n for n in names if n.endswith((".pkl", ".pickle", ".joblib"))]

    variant = _member(blob, tmp_path, "variant_config.json")
    spec = variant["extra_values"]["pipeline"]
    assert spec["target_model"]["params"]  # fitted parameter vector, not raw data
    assert spec["target_col"] == "y" and "aux_models" in spec


# --------------------------------------------------------------------------- #
# runtime env pins
# --------------------------------------------------------------------------- #
def test_env_pins_statsmodels_stack_without_sklearn(univariate, tmp_path):
    pipe, _ = univariate
    env = _member(_serialize(pipe), tmp_path, "env.json")
    packages = [
        dep["package"].split("==")[0].split("[")[0]
        for dep in env["python3::conda_pip"]["dependencies"]
    ]

    for required in ("statsmodels", "scipy", "pandas", "numpy", "fnnx"):
        assert required in packages
    assert "scikit-learn" not in packages and "sklearn" not in packages
    assert "joblib" not in packages


# --------------------------------------------------------------------------- #
# manifest + meta tags and payloads
# --------------------------------------------------------------------------- #
def test_manifest_carries_forecasting_producer_tag(univariate, tmp_path):
    pipe, _ = univariate
    manifest = _member(_serialize(pipe), tmp_path, "manifest.json")
    assert manifest["producer_name"] == FORECASTING_PRODUCER
    assert FORECASTING_TAG in manifest["producer_tags"]


def test_meta_entries_tags_and_payloads(two_stage, tmp_path):
    pipe, _ = two_stage
    meta = _member(_serialize(pipe), tmp_path, "meta.json")
    by_tag = {entry["producer_tags"][0]: entry["payload"] for entry in meta}
    assert set(by_tag) == {
        FORECASTING_METRICS_TAG,
        REGISTRY_METRICS_TAG,
        FORECASTING_CHART_TAG,
    }

    fm = by_tag[FORECASTING_METRICS_TAG]
    assert set(fm["metrics"]) >= {"MAE", "RMSE", "MAPE", "R2", "SC_SCORE"}
    assert fm["model_config"]["frequency"] == "month"

    # registry path expects a flat {"metrics": {...}} payload
    assert by_tag[REGISTRY_METRICS_TAG]["metrics"] == fm["metrics"]

    chart = by_tag[FORECASTING_CHART_TAG]
    assert "split_date" in chart and "revenue" in chart["series"]
    # future points are never embedded in the exported chart
    for series in chart["series"].values():
        assert "future" not in series


def test_chart_future_segment_is_stripped(univariate, tmp_path):
    pipe, _ = univariate
    chart = {
        "split_date": "2021-01-01",
        "series": {
            "y": {
                "actuals": [{"date": "2020-01-01", "value": 1.0}],
                "test_fit": [{"date": "2021-01-01", "value": 2.0}],
                "future": [{"date": "2021-02-01", "value": 3.0}],
            }
        },
    }
    blob = serialize(pipe, pipe.test_metrics, pipe.model_config(), chart)
    meta = _member(blob, tmp_path, "meta.json")
    payload = next(
        e["payload"] for e in meta if e["producer_tags"][0] == FORECASTING_CHART_TAG
    )
    assert payload["split_date"] == "2021-01-01"
    assert set(payload["series"]["y"]) == {"actuals", "test_fit"}


def test_model_config_records_known_future_designation(known_future, tmp_path):
    pipe, _ = known_future
    meta = _member(_serialize(pipe), tmp_path, "meta.json")
    model_config = next(
        e["payload"]["model_config"]
        for e in meta
        if e["producer_tags"][0] == FORECASTING_METRICS_TAG
    )
    assert model_config["known_future_cols"] == ["promo"]
    assert model_config["min_history"] >= 1
    # promo is known-future -> it has no model of its own
    assert "promo" not in model_config["series"]
    assert "visitors" in model_config["series"]


# --------------------------------------------------------------------------- #
# input dtype carries `future` only for known-future models
# --------------------------------------------------------------------------- #
def test_input_dtype_omits_future_without_known_future(univariate, tmp_path):
    pipe, _ = univariate
    dtypes = _member(_serialize(pipe), tmp_path, "dtypes.json")
    props = dtypes["ext::in"]["properties"]
    assert set(props) == {"history", "horizon"}


def test_input_dtype_includes_future_for_known_future(known_future, tmp_path):
    pipe, _ = known_future
    dtypes = _member(_serialize(pipe), tmp_path, "dtypes.json")
    props = dtypes["ext::in"]["properties"]
    assert "future" in props


# --------------------------------------------------------------------------- #
# predict-time validation errors propagate through the pyfunc
# --------------------------------------------------------------------------- #
def test_too_little_history_error_propagates(known_future, tmp_path):
    pipe, history = known_future
    runtime = _runtime(_serialize(pipe), tmp_path)
    future = _future_records(history, 4, ["promo"])
    with pytest.raises(ValueError, match="at least"):
        runtime.compute(
            {"in": {"history": history[:5], "horizon": 4, "future": future}}, {}
        )


def test_missing_future_error_propagates(known_future, tmp_path):
    pipe, history = known_future
    runtime = _runtime(_serialize(pipe), tmp_path)
    with pytest.raises(ValueError, match="requires future values"):
        runtime.compute({"in": {"history": history, "horizon": 4}}, {})


def test_unexpected_future_error_propagates(univariate, tmp_path):
    pipe, history = univariate
    runtime = _runtime(_serialize(pipe), tmp_path)
    stray = [{"date": history[-1]["date"], "promo": 1.0}]
    with pytest.raises(ValueError, match="no known-future columns"):
        runtime.compute(
            {"in": {"history": history, "horizon": 3, "future": stray}}, {}
        )


def test_history_gap_error_propagates(univariate, tmp_path):
    pipe, history = univariate
    runtime = _runtime(_serialize(pipe), tmp_path)
    gapped = history[:20] + history[22:]  # drop two consecutive months
    with pytest.raises(ValueError, match="gap"):
        runtime.compute({"in": {"history": gapped, "horizon": 3}}, {})
