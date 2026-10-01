"""Model v1: L2-regularized logistic regression with a fixed 0.5 threshold."""

from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

MODEL_STRATEGY = "logreg"
PARAMS = {
    "model": "LogisticRegression",
    "C": 1.0,
    "penalty": "l2",
    "max_iter": 2000,
    "class_weight": "none",
    "threshold_search": "fixed",
}
CURVE_FRACTIONS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def build_estimator():
    return LogisticRegression(C=PARAMS["C"], max_iter=PARAMS["max_iter"])


def fit(pipeline, X, y):
    return pipeline.fit(X, y)


def decision_threshold(pipeline, X_valid, y_valid) -> float:
    return 0.5


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
