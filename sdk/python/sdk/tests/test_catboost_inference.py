import numpy as np
from fnnx.envs.uv import UvEnvManager
from fnnx.handlers.stdio import StdIOHandler, StdIOHandlerConfig
from fnnx.runtime import Runtime

HANDLER_CONFIG = StdIOHandlerConfig(env_manager=UvEnvManager)
BATCH = 4
N_FEATURES = 5


def _rt(path: str) -> Runtime:
    return Runtime(path, handler=StdIOHandler, handler_config=HANDLER_CONFIG)


def test_ndarray_native() -> None:
    rng = np.random.default_rng(0)
    X = rng.standard_normal((BATCH, N_FEATURES))

    out = _rt("catboost_ndarray_native.luml").compute(
        {"payload": {"pool": {"data": X.tolist()}}},
        dynamic_attributes={},
    )
    preds = out["catboost_output"]["predictions"]
    assert len(preds) == BATCH
    print(f"ndarray/native:  {preds}")


def test_ndarray_unified() -> None:
    rng = np.random.default_rng(0)
    X = rng.standard_normal((BATCH, N_FEATURES))

    out = _rt("catboost_ndarray_unified.luml").compute(
        {f"x{i}": X[:, i].tolist() for i in range(N_FEATURES)},
        dynamic_attributes={},
    )
    preds = out["y"]
    assert len(preds) == BATCH
    assert all(p in (0, 1) for p in preds)
    print(f"ndarray/unified: {preds}")


def test_df_unified() -> None:
    rng = np.random.default_rng(0)
    X = rng.standard_normal((BATCH, N_FEATURES))

    out = _rt("catboost_df_unified.luml").compute(
        {f"feat_{i}": X[:, i].tolist() for i in range(N_FEATURES)},
        dynamic_attributes={},
    )
    preds = out["y"]
    assert len(preds) == BATCH
    assert all(p in (0, 1) for p in preds)
    print(f"df/unified:      {preds}")


def test_sparse_native() -> None:
    rng = np.random.default_rng(0)
    X = rng.standard_normal((BATCH, N_FEATURES))
    import scipy.sparse as sp
    X_csr = sp.csr_matrix(X)

    out = _rt("catboost_sparse_native.luml").compute(
        {"payload": {"pool": {
            "data": X_csr.data.tolist(),
            "indices": X_csr.indices.tolist(),
            "indptr": X_csr.indptr.tolist(),
            "shape": list(X_csr.shape),
            "data_format": "csr",
        }}},
        dynamic_attributes={},
    )
    preds = out["catboost_output"]["predictions"]
    assert len(preds) == BATCH
    print(f"sparse/native:   {preds}")


def main() -> None:
    test_ndarray_native()
    test_ndarray_unified()
    test_df_unified()
    test_sparse_native()


if __name__ == "__main__":
    main()