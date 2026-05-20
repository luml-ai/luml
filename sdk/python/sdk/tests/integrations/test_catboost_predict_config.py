import catboost as ctb
import numpy as np
import pytest

from tests.integrations._types import PackagingFixture
from tests.integrations._utils import _run

N_TRAIN = 100
N_FEATURES = 5
BATCH = 4
NUM_TREES = 10


@pytest.fixture(scope="module")
def regressor() -> ctb.CatBoostRegressor:
    """
    Reproduces the same model as ctb_regressor_ndarray_native (seed=42).
    """
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = x[:, 0] + x[:, 1]
    model = ctb.CatBoostRegressor(
        iterations=NUM_TREES, depth=3, verbose=False, random_seed=42
    )
    model.fit(x, y)
    return model


@pytest.fixture(scope="module")
def classifier() -> ctb.CatBoostClassifier:
    """
    Reproduces the same model as ctb_classifier_ndarray_native (seed=42).
    """
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    model = ctb.CatBoostClassifier(
        iterations=NUM_TREES, depth=3, verbose=False, random_seed=42
    )
    model.fit(x, y)
    return model


@pytest.fixture(scope="module")
def x_test() -> np.ndarray:
    return np.random.default_rng(1).standard_normal((BATCH, N_FEATURES))


def test_ntree_end(
    ctb_regressor_ndarray_native: PackagingFixture,
    regressor: ctb.CatBoostRegressor,
    x_test: np.ndarray,
) -> None:
    expected_partial = regressor.predict(x_test, ntree_end=5).tolist()
    expected_full = regressor.predict(x_test).tolist()

    out = _run(
        ctb_regressor_ndarray_native["ref"].path,
        {
            "payload": {
                "pool": {"data": x_test.tolist()},
                "predict_config": {"ntree_end": 5},
            }
        },
    )

    preds = out["catboost_output"]["predictions"]
    assert np.allclose(preds, expected_partial, atol=1e-5)
    assert not np.allclose(preds, expected_full, atol=1e-3)


def test_ntree_start_end(
    ctb_regressor_ndarray_native: PackagingFixture,
    regressor: ctb.CatBoostRegressor,
    x_test: np.ndarray,
) -> None:
    expected = regressor.predict(x_test, ntree_start=5, ntree_end=10).tolist()

    out = _run(
        ctb_regressor_ndarray_native["ref"].path,
        {
            "payload": {
                "pool": {"data": x_test.tolist()},
                "predict_config": {"ntree_start": 5, "ntree_end": 10},
            }
        },
    )

    preds = out["catboost_output"]["predictions"]
    assert np.allclose(preds, expected, atol=1e-5)
    assert not np.allclose(preds, regressor.predict(x_test).tolist(), atol=1e-3)


def test_prediction_type_probability(
    ctb_classifier_ndarray_native: PackagingFixture,
    classifier: ctb.CatBoostClassifier,
    x_test: np.ndarray,
) -> None:
    """
    prediction_type="Probability" returns per-class probabilities: shape (batch, 2).
    """
    expected = classifier.predict(x_test, prediction_type="Probability").tolist()

    out = _run(
        ctb_classifier_ndarray_native["ref"].path,
        {
            "payload": {
                "pool": {"data": x_test.tolist()},
                "predict_config": {"prediction_type": "Probability"},
            }
        },
    )

    preds = out["catboost_output"]["predictions"]
    assert len(preds) == BATCH
    assert all(len(row) == 2 for row in preds)
    assert np.allclose(preds, expected, atol=1e-5)
