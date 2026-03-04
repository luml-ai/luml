from fnnx.envs.uv import UvEnvManager
from fnnx.handlers.stdio import StdIOHandler, StdIOHandlerConfig
from fnnx.runtime import Runtime

HANDLER_CONFIG = StdIOHandlerConfig(env_manager=UvEnvManager)


def _run(path, inputs):
    return Runtime(path, handler=StdIOHandler, handler_config=HANDLER_CONFIG).compute(
        inputs, dynamic_attributes={}
    )


def _get_preds(out, preds_key):
    result = out
    for key in preds_key:
        result = result[key]
    return result


def _assert(preds, expected, compare, atol=1e-5):
    assert len(preds) == len(expected)
    if compare == "int":
        assert [int(p) for p in preds] == expected
    elif compare == "float":
        assert all(abs(p - e) < atol for p, e in zip(preds, expected))
    elif compare == "float_2d":
        assert all(
            abs(p - e) < atol
            for row_p, row_e in zip(preds, expected)
            for p, e in zip(row_p, row_e)
        )


def test_classifier_df_unified(ctb_classifier_df_unified):
    f = ctb_classifier_df_unified
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])


def test_classifier_ndarray_unified(ctb_classifier_ndarray_unified):
    f = ctb_classifier_ndarray_unified
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])


def test_classifier_ndarray_native(ctb_classifier_ndarray_native):
    f = ctb_classifier_ndarray_native
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])


def test_classifier_sparse_native(ctb_classifier_sparse_native):
    f = ctb_classifier_sparse_native
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])


def test_regressor_df_unified(ctb_regressor_df_unified):
    f = ctb_regressor_df_unified
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])


def test_regressor_ndarray_unified(ctb_regressor_ndarray_unified):
    f = ctb_regressor_ndarray_unified
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])


def test_regressor_ndarray_native(ctb_regressor_ndarray_native):
    f = ctb_regressor_ndarray_native
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])


def test_regressor_sparse_native(ctb_regressor_sparse_native):
    f = ctb_regressor_sparse_native
    _assert(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"], f["compare"])