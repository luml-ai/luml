import numpy as np
import pandas as pd
import pytest
import lightgbm as lgb
from fnnx.envs.uv import UvEnvManager
from fnnx.handlers.stdio import StdIOHandler, StdIOHandlerConfig
from fnnx.runtime import Runtime

N_TRAIN = 100
N_FEATURES = 5
BATCH = 4
NUM_ITERATIONS = 10
AUTO = [f"x{i}" for i in range(N_FEATURES)]

HANDLER_CONFIG = StdIOHandlerConfig(env_manager=UvEnvManager)


def _run(path, inputs):
    return Runtime(path, handler=StdIOHandler, handler_config=HANDLER_CONFIG).compute(
        inputs, dynamic_attributes={}
    )


@pytest.fixture(scope="module")
def model():
    """Reproduces the same booster as lgb_ndarray_native (seed=42, AUTO features)."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    return lgb.train(
        {"objective": "binary", "num_leaves": 7, "verbose": -1},
        lgb.Dataset(pd.DataFrame(X, columns=AUTO), label=y),
        num_boost_round=NUM_ITERATIONS,
    )


@pytest.fixture(scope="module")
def X_test():
    return np.random.default_rng(1).standard_normal((BATCH, N_FEATURES))


def test_raw_score(lgb_ndarray_native, model, X_test):
    """raw_score=True returns log-odds scores, not probabilities."""
    expected = model.predict(X_test, raw_score=True).tolist()

    out = _run(lgb_ndarray_native["ref"].path, {"payload": {
        "dataset": {"data": X_test.tolist()},
        "predict_config": {"raw_score": True},
    }})

    preds = out["lightgbm_output"]["predictions"]
    assert np.allclose(preds, expected, atol=1e-5)
    assert not all(0.0 <= p <= 1.0 for p in preds)


def test_num_iteration(lgb_ndarray_native, model, X_test):
    expected_partial = model.predict(X_test, num_iteration=5).tolist()
    expected_full = model.predict(X_test).tolist()

    out = _run(lgb_ndarray_native["ref"].path, {"payload": {
        "dataset": {"data": X_test.tolist()},
        "predict_config": {"num_iteration": 5},
    }})

    preds = out["lightgbm_output"]["predictions"]
    assert np.allclose(preds, expected_partial, atol=1e-5)
    assert not np.allclose(preds, expected_full, atol=1e-3)


def test_pred_leaf(lgb_ndarray_native, model, X_test):
    """pred_leaf=True returns leaf node indices: one integer per tree per sample."""
    expected = model.predict(X_test, pred_leaf=True).tolist()

    out = _run(lgb_ndarray_native["ref"].path, {"payload": {
        "dataset": {"data": X_test.tolist()},
        "predict_config": {"pred_leaf": True},
    }})

    preds = out["lightgbm_output"]["predictions"]
    assert len(preds) == BATCH
    assert all(isinstance(row, list) and len(row) == NUM_ITERATIONS for row in preds)
    assert preds == expected