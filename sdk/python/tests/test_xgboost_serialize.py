import numpy as np
import pandas as pd
import scipy.sparse as sp
import xgboost as xgb

from luml.integrations.xgboost import save_xgboost

N, N_FEATURES = 100, 5


def _train(X: np.ndarray, feature_names: list[str]) -> xgb.Booster:
    rng = np.random.default_rng(42)
    y = (X[:, 0] + X[:, 1] > 0).astype(np.float32)
    dtrain = xgb.DMatrix(X, label=y, feature_names=feature_names)
    return xgb.train({"max_depth": 3, "objective": "binary:logistic"}, dtrain, num_boost_round=10)


def main() -> None:
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N, N_FEATURES)).astype(np.float32)

    named = [f"feat_{i}" for i in range(N_FEATURES)]
    auto = [f"x{i}" for i in range(N_FEATURES)]

    # booster_auto is trained with x0..x4 to match the auto-naming _add_io assigns to ndarray inputs
    booster_named = _train(X, named)
    booster_auto = _train(X, auto)

    X_df = pd.DataFrame(X, columns=named)
    X_dm = xgb.DMatrix(X, feature_names=named)
    X_sparse = sp.csr_matrix(X)

    cases = [
        ("xgboost_dmatrix_native.luml",  booster_named, X_dm,    "native"),
        ("xgboost_dmatrix_unified.luml", booster_named, X_dm,    "unified"),
        ("xgboost_ndarray_native.luml",  booster_auto,  X,       "native"),
        ("xgboost_ndarray_unified.luml", booster_auto,  X,       "unified"),
        ("xgboost_df_unified.luml",      booster_named, X_df,    "unified"),
        ("xgboost_sparse_native.luml",   booster_auto,  X_sparse, "native"),
    ]

    for path, estimator, inputs, fmt in cases:
        ref = save_xgboost(estimator=estimator, inputs=inputs, path=path, input_format=fmt)
        assert ref.validate(), f"Validation failed: {path}"
        print(f"ok  {path}")


if __name__ == "__main__":
    main()