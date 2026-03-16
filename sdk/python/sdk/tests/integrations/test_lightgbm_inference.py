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


def _assert_close(preds, expected, atol=1e-5):
    assert len(preds) == len(expected)
    assert all(abs(p - e) < atol for p, e in zip(preds, expected))


def test_df_unified(lgb_df_unified):
    f = lgb_df_unified
    _assert_close(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"])


def test_ndarray_unified(lgb_ndarray_unified):
    f = lgb_ndarray_unified
    _assert_close(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"])


def test_ndarray_native(lgb_ndarray_native):
    f = lgb_ndarray_native
    _assert_close(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"])


def test_sparse_native(lgb_sparse_native):
    f = lgb_sparse_native
    _assert_close(_get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"])
