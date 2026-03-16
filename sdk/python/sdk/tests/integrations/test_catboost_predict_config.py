import catboost as ctb
import numpy as np
import pytest
from fnnx.envs.uv import UvEnvManager
from fnnx.handlers.stdio import StdIOHandler, StdIOHandlerConfig
from fnnx.runtime import Runtime

N_TRAIN = 100
N_FEATURES = 5
BATCH = 4
NUM_TREES = 10

HANDLER_CONFIG = StdIOHandlerConfig(env_manager=UvEnvManager)


def _run(path, inputs):
    return Runtime(path, handler=StdIOHandler, handler_config=HANDLER_CONFIG).compute(
        inputs, dynamic_attributes={}
    )


@pytest.fixture(scope="module")
def regressor():
    """Reproduces the same model as ctb_regressor_ndarray_native (seed=42)."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = X[:, 0] + X[:, 1]
    model = ctb.CatBoostRegressor(iterations=NUM_TREES, depth=3, verbose=False, random_seed=42)
    model.fit(X, y)
    return model


@pytest.fixture(scope="module")
def classifier():
    """Reproduces the same model as ctb_classifier_ndarray_native (seed=42)."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    model = ctb.CatBoostClassifier(iterations=NUM_TREES, depth=3, verbose=False, random_seed=42)
    model.fit(X, y)
    return model


@pytest.fixture(scope="module")
def X_test():
    return np.random.default_rng(1).standard_normal((BATCH, N_FEATURES))


def test_ntree_end(ctb_regressor_ndarray_native, regressor, X_test):
    expected_partial = regressor.predict(X_test, ntree_end=5).tolist()
    expected_full = regressor.predict(X_test).tolist()

    out = _run(ctb_regressor_ndarray_native["ref"].path, {"payload": {
        "pool": {"data": X_test.tolist()},
        "predict_config": {"ntree_end": 5},
    }})

    preds = out["catboost_output"]["predictions"]
    assert np.allclose(preds, expected_partial, atol=1e-5)
    assert not np.allclose(preds, expected_full, atol=1e-3)


def test_ntree_start_end(ctb_regressor_ndarray_native, regressor, X_test):
    expected = regressor.predict(X_test, ntree_start=5, ntree_end=10).tolist()

    out = _run(ctb_regressor_ndarray_native["ref"].path, {"payload": {
        "pool": {"data": X_test.tolist()},
        "predict_config": {"ntree_start": 5, "ntree_end": 10},
    }})

    preds = out["catboost_output"]["predictions"]
    assert np.allclose(preds, expected, atol=1e-5)
    assert not np.allclose(preds, regressor.predict(X_test).tolist(), atol=1e-3)


def test_prediction_type_probability(ctb_classifier_ndarray_native, classifier, X_test):
    """prediction_type="Probability" returns per-class probabilities: shape (batch, 2)."""
    expected = classifier.predict(X_test, prediction_type="Probability").tolist()

    out = _run(ctb_classifier_ndarray_native["ref"].path, {"payload": {
        "pool": {"data": X_test.tolist()},
        "predict_config": {"prediction_type": "Probability"},
    }})

    preds = out["catboost_output"]["predictions"]
    assert len(preds) == BATCH
    assert all(len(row) == 2 for row in preds)
    assert np.allclose(preds, expected, atol=1e-5)
