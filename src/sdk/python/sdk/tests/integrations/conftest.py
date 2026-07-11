import catboost as ctb
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp
import xgboost as xgb

from luml.integrations.catboost import save_catboost
from luml.integrations.lightgbm import save_lightgbm
from luml.integrations.xgboost import save_xgboost
from tests.integrations._types import PackagingFixture

N_TRAIN = 100
N_FEATURES = 5
BATCH = 4

NAMED = [f"feat_{i}" for i in range(N_FEATURES)]
AUTO = [f"x{i}" for i in range(N_FEATURES)]


def _xgb_train(x: np.ndarray, feature_names: list, y: np.ndarray) -> xgb.Booster:
    dtrain = xgb.DMatrix(x, label=y, feature_names=feature_names)
    return xgb.train(
        {"max_depth": 3, "objective": "binary:logistic"},
        dtrain,
        num_boost_round=10,
    )


@pytest.fixture(scope="session")
def xgb_df_unified(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)
    model = _xgb_train(x, NAMED, y)

    path = str(tmp_path_factory.mktemp("xgb") / "df_unified.luml")
    ref = save_xgboost(
        estimator=model,
        inputs=pd.DataFrame(x, columns=NAMED),
        path=path,
        input_format="unified",
    )

    x_test = rng.standard_normal((BATCH, N_FEATURES)).astype(np.float32)
    return {
        "ref": ref,
        "inputs": {f"feat_{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(xgb.DMatrix(x_test, feature_names=NAMED)).tolist(),
        "preds_key": ["y"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def xgb_ndarray_unified(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)
    model = _xgb_train(x, AUTO, y)

    path = str(tmp_path_factory.mktemp("xgb") / "ndarray_unified.luml")
    ref = save_xgboost(estimator=model, inputs=x, path=path, input_format="unified")

    x_test = rng.standard_normal((BATCH, N_FEATURES)).astype(np.float32)
    return {
        "ref": ref,
        "inputs": {f"x{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(xgb.DMatrix(x_test, feature_names=AUTO)).tolist(),
        "preds_key": ["y"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def xgb_ndarray_native(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)
    model = _xgb_train(x, AUTO, y)

    path = str(tmp_path_factory.mktemp("xgb") / "ndarray_native.luml")
    ref = save_xgboost(estimator=model, inputs=x, path=path, input_format="native")

    x_test = rng.standard_normal((BATCH, N_FEATURES)).astype(np.float32)
    return {
        "ref": ref,
        "inputs": {"payload": {"dmatrix": {"data": x_test.tolist()}}},
        "expected": model.predict(xgb.DMatrix(x_test, feature_names=AUTO)).tolist(),
        "preds_key": ["xgboost_output", "predictions"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def xgb_dmatrix_unified(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)
    model = _xgb_train(x, NAMED, y)

    path = str(tmp_path_factory.mktemp("xgb") / "dmatrix_unified.luml")
    ref = save_xgboost(
        estimator=model,
        inputs=xgb.DMatrix(x, feature_names=NAMED),
        path=path,
        input_format="unified",
    )

    x_test = rng.standard_normal((BATCH, N_FEATURES)).astype(np.float32)
    return {
        "ref": ref,
        "inputs": {f"feat_{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(xgb.DMatrix(x_test, feature_names=NAMED)).tolist(),
        "preds_key": ["y"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def xgb_dmatrix_native(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)
    model = _xgb_train(x, NAMED, y)

    path = str(tmp_path_factory.mktemp("xgb") / "dmatrix_native.luml")
    ref = save_xgboost(
        estimator=model,
        inputs=xgb.DMatrix(x, feature_names=NAMED),
        path=path,
        input_format="native",
    )

    x_test = rng.standard_normal((BATCH, N_FEATURES)).astype(np.float32)
    return {
        "ref": ref,
        "inputs": {
            "payload": {
                "dmatrix": {
                    "data": x_test.tolist(),
                    "feature_names": NAMED,
                }
            }
        },
        "expected": model.predict(xgb.DMatrix(x_test, feature_names=NAMED)).tolist(),
        "preds_key": ["xgboost_output", "predictions"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def xgb_sparse_native(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)
    model = _xgb_train(x, AUTO, y)

    path = str(tmp_path_factory.mktemp("xgb") / "sparse_native.luml")
    ref = save_xgboost(
        estimator=model, inputs=sp.csr_matrix(x), path=path, input_format="native"
    )

    x_test = sp.csr_matrix(rng.standard_normal((BATCH, N_FEATURES)).astype(np.float32))
    return {
        "ref": ref,
        "inputs": {
            "payload": {
                "dmatrix": {
                    "data": x_test.data.tolist(),
                    "indices": x_test.indices.tolist(),
                    "indptr": x_test.indptr.tolist(),
                    "shape": list(x_test.shape),
                    "data_format": "csr",
                }
            }
        },
        "expected": model.predict(xgb.DMatrix(x_test, feature_names=AUTO)).tolist(),
        "preds_key": ["xgboost_output", "predictions"],
        "compare": "float",
    }


def _lgb_train(feature_names: list) -> tuple[lgb.Booster, np.ndarray]:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    model = lgb.train(
        {"objective": "binary", "num_leaves": 7, "verbose": -1},
        lgb.Dataset(pd.DataFrame(x, columns=feature_names), label=y),
        num_boost_round=10,
    )
    return model, x


@pytest.fixture(scope="session")
def lgb_df_unified(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    model, x = _lgb_train(NAMED)

    path = str(tmp_path_factory.mktemp("lgb") / "df_unified.luml")
    ref = save_lightgbm(
        estimator=model,
        inputs=pd.DataFrame(x, columns=NAMED),
        path=path,
        input_format="unified",
    )

    x_test = np.random.default_rng(0).standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {f"feat_{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["y"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def lgb_ndarray_unified(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    model, x = _lgb_train(AUTO)

    path = str(tmp_path_factory.mktemp("lgb") / "ndarray_unified.luml")
    ref = save_lightgbm(estimator=model, inputs=x, path=path, input_format="unified")

    x_test = np.random.default_rng(0).standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {f"x{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["y"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def lgb_ndarray_native(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    model, x = _lgb_train(AUTO)

    path = str(tmp_path_factory.mktemp("lgb") / "ndarray_native.luml")
    ref = save_lightgbm(estimator=model, inputs=x, path=path, input_format="native")

    x_test = np.random.default_rng(0).standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {"payload": {"dataset": {"data": x_test.tolist()}}},
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["lightgbm_output", "predictions"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def lgb_sparse_native(tmp_path_factory: pytest.TempPathFactory) -> PackagingFixture:
    model, x = _lgb_train(AUTO)
    x_sparse = sp.csr_matrix(x)

    path = str(tmp_path_factory.mktemp("lgb") / "sparse_native.luml")
    ref = save_lightgbm(
        estimator=model, inputs=x_sparse, path=path, input_format="native"
    )

    x_test = sp.csr_matrix(
        np.random.default_rng(0).standard_normal((BATCH, N_FEATURES))
    )
    return {
        "ref": ref,
        "inputs": {
            "payload": {
                "dataset": {
                    "data": x_test.data.tolist(),
                    "indices": x_test.indices.tolist(),
                    "indptr": x_test.indptr.tolist(),
                    "shape": list(x_test.shape),
                    "data_format": "csr",
                }
            }
        },
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["lightgbm_output", "predictions"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def ctb_classifier_df_unified(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    x_df = pd.DataFrame(x, columns=NAMED)
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    model = ctb.CatBoostClassifier(
        iterations=10, depth=3, verbose=False, random_seed=42
    )
    model.fit(x_df, y)

    path = str(tmp_path_factory.mktemp("ctb") / "clf_df_unified.luml")
    ref = save_catboost(estimator=model, inputs=x_df, path=path, input_format="unified")

    x_test = rng.standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {f"feat_{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(x_test, prediction_type="Class").astype(int).tolist(),
        "preds_key": ["y"],
        "compare": "int",
    }


@pytest.fixture(scope="session")
def ctb_classifier_ndarray_unified(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    model = ctb.CatBoostClassifier(
        iterations=10, depth=3, verbose=False, random_seed=42
    )
    model.fit(x, y)

    path = str(tmp_path_factory.mktemp("ctb") / "clf_ndarray_unified.luml")
    ref = save_catboost(estimator=model, inputs=x, path=path, input_format="unified")

    x_test = rng.standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {f"x{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(x_test, prediction_type="Class").astype(int).tolist(),
        "preds_key": ["y"],
        "compare": "int",
    }


@pytest.fixture(scope="session")
def ctb_classifier_ndarray_native(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    model = ctb.CatBoostClassifier(
        iterations=10, depth=3, verbose=False, random_seed=42
    )
    model.fit(x, y)

    path = str(tmp_path_factory.mktemp("ctb") / "clf_ndarray_native.luml")
    ref = save_catboost(estimator=model, inputs=x, path=path, input_format="native")

    x_test = rng.standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {
            "payload": {
                "pool": {"data": x_test.tolist()},
                "predict_config": {"prediction_type": "Class"},
            }
        },
        "expected": model.predict(x_test, prediction_type="Class").astype(int).tolist(),
        "preds_key": ["catboost_output", "predictions"],
        "compare": "int",
    }


@pytest.fixture(scope="session")
def ctb_classifier_sparse_native(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    model = ctb.CatBoostClassifier(
        iterations=10, depth=3, verbose=False, random_seed=42
    )
    model.fit(x, y)

    path = str(tmp_path_factory.mktemp("ctb") / "clf_sparse_native.luml")
    ref = save_catboost(
        estimator=model, inputs=sp.csr_matrix(x), path=path, input_format="native"
    )

    x_test = sp.csr_matrix(rng.standard_normal((BATCH, N_FEATURES)))
    # prediction_type="Probability" → [[p_class0, p_class1], ...] per sample
    return {
        "ref": ref,
        "inputs": {
            "payload": {
                "pool": {
                    "data": x_test.data.tolist(),
                    "indices": x_test.indices.tolist(),
                    "indptr": x_test.indptr.tolist(),
                    "shape": list(x_test.shape),
                    "data_format": "csr",
                },
                "predict_config": {"prediction_type": "Probability"},
            }
        },
        "expected": model.predict(x_test, prediction_type="Probability").tolist(),
        "preds_key": ["catboost_output", "predictions"],
        "compare": "float_2d",
    }


@pytest.fixture(scope="session")
def ctb_regressor_df_unified(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    x_df = pd.DataFrame(x, columns=NAMED)
    y = x[:, 0] + x[:, 1]
    model = ctb.CatBoostRegressor(iterations=10, depth=3, verbose=False, random_seed=42)
    model.fit(x_df, y)

    path = str(tmp_path_factory.mktemp("ctb") / "reg_df_unified.luml")
    ref = save_catboost(estimator=model, inputs=x_df, path=path, input_format="unified")

    x_test = rng.standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {f"feat_{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["y"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def ctb_regressor_ndarray_unified(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = x[:, 0] + x[:, 1]
    model = ctb.CatBoostRegressor(iterations=10, depth=3, verbose=False, random_seed=42)
    model.fit(x, y)

    path = str(tmp_path_factory.mktemp("ctb") / "reg_ndarray_unified.luml")
    ref = save_catboost(estimator=model, inputs=x, path=path, input_format="unified")

    x_test = rng.standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {f"x{i}": x_test[:, i].tolist() for i in range(N_FEATURES)},
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["y"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def ctb_regressor_ndarray_native(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = x[:, 0] + x[:, 1]
    model = ctb.CatBoostRegressor(iterations=10, depth=3, verbose=False, random_seed=42)
    model.fit(x, y)

    path = str(tmp_path_factory.mktemp("ctb") / "reg_ndarray_native.luml")
    ref = save_catboost(estimator=model, inputs=x, path=path, input_format="native")

    x_test = rng.standard_normal((BATCH, N_FEATURES))
    return {
        "ref": ref,
        "inputs": {"payload": {"pool": {"data": x_test.tolist()}}},
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["catboost_output", "predictions"],
        "compare": "float",
    }


@pytest.fixture(scope="session")
def ctb_regressor_sparse_native(
    tmp_path_factory: pytest.TempPathFactory,
) -> PackagingFixture:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((N_TRAIN, N_FEATURES))
    y = x[:, 0] + x[:, 1]
    model = ctb.CatBoostRegressor(iterations=10, depth=3, verbose=False, random_seed=42)
    model.fit(x, y)

    path = str(tmp_path_factory.mktemp("ctb") / "reg_sparse_native.luml")
    ref = save_catboost(
        estimator=model, inputs=sp.csr_matrix(x), path=path, input_format="native"
    )

    x_test = sp.csr_matrix(rng.standard_normal((BATCH, N_FEATURES)))
    return {
        "ref": ref,
        "inputs": {
            "payload": {
                "pool": {
                    "data": x_test.data.tolist(),
                    "indices": x_test.indices.tolist(),
                    "indptr": x_test.indptr.tolist(),
                    "shape": list(x_test.shape),
                    "data_format": "csr",
                }
            }
        },
        "expected": model.predict(x_test).tolist(),
        "preds_key": ["catboost_output", "predictions"],
        "compare": "float",
    }
