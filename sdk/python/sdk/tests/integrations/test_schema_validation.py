import pytest
from fnnx.envs.uv import UvEnvManager
from fnnx.handlers.stdio import StdIOHandler, StdIOHandlerConfig
from fnnx.runtime import Runtime

HANDLER_CONFIG = StdIOHandlerConfig(env_manager=UvEnvManager)

DENSE_DATA = [[0.1, 0.2, 0.3, 0.4, 0.5], [0.5, 0.4, 0.3, 0.2, 0.1]]


def _run(path, inputs):
    return Runtime(path, handler=StdIOHandler, handler_config=HANDLER_CONFIG).compute(
        inputs, dynamic_attributes={}
    )


def test_xgboost_unknown_data_format(xgb_ndarray_native):
    """data_format='xml' is not supported — must raise ValueError."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(xgb_ndarray_native["ref"].path, {"payload": {
            "dmatrix": {"data": DENSE_DATA, "data_format": "xml"},
        }})


def test_lightgbm_unknown_data_format(lgb_ndarray_native):
    """data_format='xml' is not supported — must raise ValueError."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(lgb_ndarray_native["ref"].path, {"payload": {
            "dataset": {"data": DENSE_DATA, "data_format": "xml"},
        }})


def test_catboost_unknown_data_format(ctb_regressor_ndarray_native):
    """data_format='xml' is not supported — must raise ValueError."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(ctb_regressor_ndarray_native["ref"].path, {"payload": {
            "pool": {"data": DENSE_DATA, "data_format": "xml"},
        }})


def test_xgboost_missing_data_field(xgb_ndarray_native):
    """Omitting 'data' from the dmatrix payload must raise KeyError."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(xgb_ndarray_native["ref"].path, {"payload": {
            "dmatrix": {"data_format": "dense"},  # 'data' key missing
        }})


def test_lightgbm_missing_data_field(lgb_ndarray_native):
    """Omitting 'data' from the dataset payload must raise KeyError."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(lgb_ndarray_native["ref"].path, {"payload": {
            "dataset": {},  # 'data' key missing
        }})


def test_catboost_missing_data_field(ctb_regressor_ndarray_native):
    """Omitting 'data' from the pool payload must raise KeyError."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(ctb_regressor_ndarray_native["ref"].path, {"payload": {
            "pool": {},  # 'data' key missing
        }})


def test_xgboost_incomplete_csr(xgb_sparse_native):
    """CSR payload missing indices/indptr/shape must raise."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(xgb_sparse_native["ref"].path, {"payload": {
            "dmatrix": {
                "data": [0.1, 0.2],  # only data, no indices/indptr/shape
                "data_format": "csr",
            },
        }})


def test_lightgbm_incomplete_csr(lgb_sparse_native):
    """CSR payload missing indices/indptr/shape must raise."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(lgb_sparse_native["ref"].path, {"payload": {
            "dataset": {
                "data": [0.1, 0.2],
                "data_format": "csr",
            },
        }})


def test_catboost_incomplete_csr(ctb_regressor_sparse_native):
    """CSR payload missing indices/indptr/shape must raise."""
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        _run(ctb_regressor_sparse_native["ref"].path, {"payload": {
            "pool": {
                "data": [0.1, 0.2],
                "data_format": "csr",
            },
        }})
