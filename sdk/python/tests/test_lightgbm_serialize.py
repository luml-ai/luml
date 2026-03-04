import numpy as np
import pandas as pd
import scipy.sparse as sp
import lightgbm as lgb

from luml.integrations.lightgbm import save_lightgbm

N, N_FEATURES = 100, 5
FEATURE_NAMES = [f"feat_{i}" for i in range(N_FEATURES)]


def _train(X_df: pd.DataFrame) -> lgb.Booster:
    rng = np.random.default_rng(42)
    y = (X_df.iloc[:, 0] + X_df.iloc[:, 1] > 0).astype(int)
    return lgb.train(
        {"objective": "binary", "num_leaves": 7, "verbose": -1},
        lgb.Dataset(X_df, label=y),
        num_boost_round=10,
    )


def main() -> None:
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N, N_FEATURES))
    X_df = pd.DataFrame(X, columns=FEATURE_NAMES)

    booster = _train(X_df)
    X_sparse = sp.csr_matrix(X)

    cases = [
        ("lightgbm_ndarray_native.luml",  booster, X,        "native"),
        ("lightgbm_ndarray_unified.luml", booster, X,        "unified"),
        ("lightgbm_df_unified.luml",      booster, X_df,     "unified"),
        ("lightgbm_sparse_native.luml",   booster, X_sparse, "native"),
    ]

    for path, estimator, inputs, fmt in cases:
        ref = save_lightgbm(estimator=estimator, inputs=inputs, path=path, input_format=fmt)
        assert ref.validate(), f"Validation failed: {path}"
        print(f"ok  {path}")


if __name__ == "__main__":
    main()