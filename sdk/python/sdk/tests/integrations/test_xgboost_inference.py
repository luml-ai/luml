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


def _assert(preds, expected, compare, atol=1e-5) -> None:
    assert len(preds) == len(expected)
    if compare == "int":
        assert [int(p) for p in preds] == expected
    elif compare == "float":
        assert all(abs(p - e) < atol for p, e in zip(preds, expected, strict=False))
    elif compare == "float_2d":
        assert all(
            abs(p - e) < atol
            for row_p, row_e in zip(preds, expected, strict=False)
            for p, e in zip(row_p, row_e, strict=False)
        )


def test_df_unified(xgb_df_unified) -> None:
    f = xgb_df_unified
    _assert(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]),
        f["expected"],
        f["compare"],
    )


def test_ndarray_unified(xgb_ndarray_unified) -> None:
    f = xgb_ndarray_unified
    _assert(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]),
        f["expected"],
        f["compare"],
    )


def test_ndarray_native(xgb_ndarray_native) -> None:
    f = xgb_ndarray_native
    _assert(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]),
        f["expected"],
        f["compare"],
    )


def test_dmatrix_unified(xgb_dmatrix_unified) -> None:
    f = xgb_dmatrix_unified
    _assert(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]),
        f["expected"],
        f["compare"],
    )


def test_dmatrix_native(xgb_dmatrix_native) -> None:
    f = xgb_dmatrix_native
    _assert(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]),
        f["expected"],
        f["compare"],
    )


def test_sparse_native(xgb_sparse_native) -> None:
    f = xgb_sparse_native
    _assert(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]),
        f["expected"],
        f["compare"],
    )
