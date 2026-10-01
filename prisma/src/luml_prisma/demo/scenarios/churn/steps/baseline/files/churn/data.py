"""Account snapshot loading and the fixed stratified holdout split."""

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

DATA_PATH = Path("data/customers.csv")
TARGET = "churned"
ID_COLUMN = "customer_id"
CATEGORICAL = ["plan", "billing_cycle", "region"]
NUMERICAL = [
    "tenure_months",
    "seats",
    "monthly_spend",
    "events_per_day_k",
    "dashboards_created",
    "api_calls_30d",
    "support_tickets_90d",
    "nps_score",
    "integrations_count",
]
FEATURES = CATEGORICAL + NUMERICAL
SEED = 42
HOLDOUT_FRACTION = 0.2


def load_customers(path: Path = DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def split_holdout(df: pd.DataFrame):
    """Stratified 80/20 split; returns X_train, X_test, y_train, y_test, test ids."""
    X_train, X_test, y_train, y_test, _, ids_test = train_test_split(
        df[FEATURES],
        df[TARGET],
        df[ID_COLUMN],
        test_size=HOLDOUT_FRACTION,
        stratify=df[TARGET],
        random_state=SEED,
    )
    return (
        X_train.reset_index(drop=True),
        X_test.reset_index(drop=True),
        y_train.reset_index(drop=True),
        y_test.reset_index(drop=True),
        ids_test.reset_index(drop=True),
    )
