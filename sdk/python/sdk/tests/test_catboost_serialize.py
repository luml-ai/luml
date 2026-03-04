import numpy as np
import pandas as pd
import scipy.sparse as sp
import catboost as ctb

from luml.integrations.catboost import save_catboost

N, N_FEATURES = 100, 5
FEATURE_NAMES = [f"feat_{i}" for i in range(N_FEATURES)]


def _train(X_df: pd.DataFrame) -> ctb.CatBoostClassifier:
    rng = np.random.default_rng(42)
    y = (X_df.iloc[:, 0] + X_df.iloc[:, 1] > 0).astype(int)
    model = ctb.CatBoostClassifier(iterations=10, depth=3, verbose=False, random_seed=42)
    model.fit(X_df, y)
    return model


def main() -> None:
    rng = np.random.default_rng(42)
    X = rng.standard_normal((N, N_FEATURES))
    X_df = pd.DataFrame(X, columns=FEATURE_NAMES)

    model = _train(X_df)
    X_sparse = sp.csr_matrix(X)

    cases = [
        ("catboost_ndarray_native.luml",  model, X,        "native"),
        ("catboost_ndarray_unified.luml", model, X,        "unified"),
        ("catboost_df_unified.luml",      model, X_df,     "unified"),
        ("catboost_sparse_native.luml",   model, X_sparse, "native"),
    ]

    for path, estimator, inputs, fmt in cases:
        ref = save_catboost(estimator=estimator, inputs=inputs, path=path, input_format=fmt)
        assert ref.validate(), f"Validation failed: {path}"
        print(f"ok  {path}")


if __name__ == "__main__":
    main()