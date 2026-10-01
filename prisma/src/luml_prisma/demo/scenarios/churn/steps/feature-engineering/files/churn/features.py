"""Feature set v2: raw columns plus per-seat intensity and lifecycle signals."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from churn.data import CATEGORICAL, NUMERICAL

FEATURE_SET = "engineered"
DERIVED = [
    "spend_per_seat",
    "events_per_seat",
    "api_calls_per_seat",
    "dashboards_per_seat",
    "tickets_per_month",
    "log_api_calls",
    "is_new_account",
]
PARAMS = {
    "feature_set": FEATURE_SET,
    "categorical_encoding": "one-hot",
    "numerical_scaling": "standard",
    "derived_features": len(DERIVED),
}


def add_derived(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    seats = out["seats"].clip(lower=1)
    out["spend_per_seat"] = out["monthly_spend"] / seats
    out["events_per_seat"] = out["events_per_day_k"] / seats
    out["api_calls_per_seat"] = out["api_calls_30d"] / seats
    out["dashboards_per_seat"] = out["dashboards_created"] / seats
    out["tickets_per_month"] = out["support_tickets_90d"] / 3.0
    out["log_api_calls"] = np.log1p(out["api_calls_30d"])
    out["is_new_account"] = (out["tenure_months"] <= 3).astype(int)
    return out


def build_preprocessor():
    encode = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", StandardScaler(), NUMERICAL + DERIVED),
        ]
    )
    return Pipeline([("derive", FunctionTransformer(add_derived)), ("encode", encode)])


def feature_names(preprocessor) -> list[str]:
    encode = preprocessor.named_steps["encode"]
    return [name.split("__", 1)[1] for name in encode.get_feature_names_out()]
