import numpy as np
import pytest
import xgboost as xgb
from fnnx.envs.uv import UvEnvManager
from fnnx.handlers.stdio import StdIOHandler, StdIOHandlerConfig
from fnnx.runtime import Runtime

N_TRAIN = 100
N_FEATURES = 5
BATCH = 4
NUM_TREES = 10
AUTO = [f"x{i}" for i in range(N_FEATURES)]

HANDLER_CONFIG = StdIOHandlerConfig(env_manager=UvEnvManager)


def _run(path, inputs):
    return Runtime(path, handler=StdIOHandler, handler_config=HANDLER_CONFIG).compute(
        inputs, dynamic_attributes={}
    )


@pytest.fixture(scope="module")
def model():
    """Reproduces the same booster as xgb_ndarray_native (seed=42, AUTO features)."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N_TRAIN, N_FEATURES)).astype(np.float32)
    y = (X[:, 0] + X[:, 1] > 0).astype(np.float32)
    dtrain = xgb.DMatrix(X, label=y, feature_names=AUTO)
    return xgb.train(
        {"max_depth": 3, "objective": "binary:logistic"},
        dtrain,
        num_boost_round=NUM_TREES,
    )


@pytest.fixture(scope="module")
def X_test():
    return (
        np.random.default_rng(1).standard_normal((BATCH, N_FEATURES)).astype(np.float32)
    )


def test_output_margin(xgb_ndarray_native, model, X_test) -> None:
    """output_margin=True returns raw logit scores, not probabilities."""
    expected = model.predict(
        xgb.DMatrix(X_test, feature_names=AUTO), output_margin=True
    ).tolist()

    out = _run(
        xgb_ndarray_native["ref"].path,
        {
            "payload": {
                "dmatrix": {"data": X_test.tolist()},
                "predict_config": {"output_margin": True},
            }
        },
    )

    preds = out["xgboost_output"]["predictions"]
    assert np.allclose(preds, expected, atol=1e-5)
    expected_proba = model.predict(xgb.DMatrix(X_test, feature_names=AUTO)).tolist()
    assert not np.allclose(preds, expected_proba, atol=1e-5)


def test_pred_leaf(xgb_ndarray_native, model, X_test) -> None:
    """pred_leaf=True returns leaf node indices: one integer per tree per sample."""
    expected = model.predict(
        xgb.DMatrix(X_test, feature_names=AUTO), pred_leaf=True
    ).tolist()

    out = _run(
        xgb_ndarray_native["ref"].path,
        {
            "payload": {
                "dmatrix": {"data": X_test.tolist()},
                "predict_config": {"pred_leaf": True},
            }
        },
    )

    preds = out["xgboost_output"]["predictions"]
    # shape: (BATCH, NUM_TREES)
    assert len(preds) == BATCH
    assert all(isinstance(row, list) and len(row) == NUM_TREES for row in preds)
    assert preds == expected


def test_iteration_range(xgb_ndarray_native, model, X_test) -> None:
    """iteration_range=(0, 5) uses only the first 5 trees."""
    dm = xgb.DMatrix(X_test, feature_names=AUTO)
    expected_partial = model.predict(dm, iteration_range=(0, 5)).tolist()
    expected_full = model.predict(dm).tolist()

    out = _run(
        xgb_ndarray_native["ref"].path,
        {
            "payload": {
                "dmatrix": {"data": X_test.tolist()},
                "predict_config": {"iteration_range": [0, 5]},
            }
        },
    )

    preds = out["xgboost_output"]["predictions"]
    assert np.allclose(preds, expected_partial, atol=1e-5)
    assert not np.allclose(preds, expected_full, atol=1e-3)
