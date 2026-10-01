"""Feature set v1: raw columns, one-hot categoricals, standardized numericals."""

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from churn.data import CATEGORICAL, NUMERICAL

FEATURE_SET = "raw"
PARAMS = {
    "feature_set": FEATURE_SET,
    "categorical_encoding": "one-hot",
    "numerical_scaling": "standard",
    "derived_features": 0,
}


def build_preprocessor():
    return ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", StandardScaler(), NUMERICAL),
        ]
    )


def feature_names(preprocessor) -> list[str]:
    return [name.split("__", 1)[1] for name in preprocessor.get_feature_names_out()]
