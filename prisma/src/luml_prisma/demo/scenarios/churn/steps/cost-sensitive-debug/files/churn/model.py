"""Model v3: cost-sensitive logistic regression with a tuned threshold."""

import numpy as np
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, precision_recall_curve, roc_auc_score

MODEL_STRATEGY = "logreg-cost-sensitive"
PARAMS = {
    "model": "LogisticRegression",
    "C": 0.5,
    "penalty": "l2",
    "max_iter": 2000,
    "class_weight": "balanced",
    "plan_cost_weights": "starter=1.0,growth=1.5,enterprise=3.0",
    "threshold_search": "f1-max on validation",
}
PLAN_COST = {"starter": 1.0, "growth": 1.5, "enterprise": 3.0}
CURVE_FRACTIONS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def build_estimator():
    return LogisticRegression(
        C=PARAMS["C"], max_iter=PARAMS["max_iter"], class_weight="balanced"
    )


def sample_weights(X) -> np.ndarray:
    return X["plan"].map(PLAN_COST).fillna(1.0).to_numpy()


def fit(pipeline, X, y):
    # Pipeline routes fit params by step name: the weights belong to the "model" step.
    return pipeline.fit(X, y, model__sample_weight=sample_weights(X))


def decision_threshold(pipeline, X_valid, y_valid) -> float:
    p = pipeline.predict_proba(X_valid)[:, 1]
    precision, recall, thresholds = precision_recall_curve(y_valid, p)
    f1 = 2 * precision[:-1] * recall[:-1] / np.clip(precision[:-1] + recall[:-1], 1e-9, None)
    return float(thresholds[int(np.argmax(f1))])


def training_curve(pipeline, X_fit, y_fit, X_valid, y_valid) -> list[dict]:
    """Learning curve: refit on growing fractions of the training split."""
    points = []
    total = len(X_fit)
    for step, fraction in enumerate(CURVE_FRACTIONS, start=1):
        rows = max(50, int(total * fraction))
        model = fit(clone(pipeline), X_fit.iloc[:rows], y_fit.iloc[:rows])
        p_train = model.predict_proba(X_fit.iloc[:rows])[:, 1]
        p_valid = model.predict_proba(X_valid)[:, 1]
        points.append(
            {
                "step": step,
                "train_logloss": log_loss(y_fit.iloc[:rows], p_train),
                "valid_logloss": log_loss(y_valid, p_valid),
                "valid_roc_auc": roc_auc_score(y_valid, p_valid),
            }
        )
    return points


def importance(pipeline, names: list[str]) -> dict[str, float]:
    coef = pipeline.named_steps["model"].coef_[0]
    pairs = zip(names, (float(c) for c in coef), strict=True)
    return dict(sorted(pairs, key=lambda kv: -abs(kv[1])))
