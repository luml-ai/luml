"""Model v2: gradient-boosted shallow trees with per-stage curves."""

from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score

MODEL_STRATEGY = "gbdt"
PARAMS = {
    "model": "GradientBoostingClassifier",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 3,
    "subsample": 0.8,
    "min_samples_leaf": 20,
    "class_weight": "none",
    "threshold_search": "fixed",
}
CURVE_EVERY = 5


def build_estimator():
    return GradientBoostingClassifier(
        n_estimators=PARAMS["n_estimators"],
        learning_rate=PARAMS["learning_rate"],
        max_depth=PARAMS["max_depth"],
        subsample=PARAMS["subsample"],
        min_samples_leaf=PARAMS["min_samples_leaf"],
        random_state=42,
    )


def fit(pipeline, X, y):
    return pipeline.fit(X, y)


def decision_threshold(pipeline, X_valid, y_valid) -> float:
    return 0.5


def training_curve(pipeline, X_fit, y_fit, X_valid, y_valid) -> list[dict]:
    """Per-boosting-stage train/validation curves from staged predictions."""
    model = fit(clone(pipeline), X_fit, y_fit)
    preprocess = model.named_steps["preprocess"]
    estimator = model.named_steps["model"]
    staged = zip(
        estimator.staged_predict_proba(preprocess.transform(X_fit)),
        estimator.staged_predict_proba(preprocess.transform(X_valid)),
        strict=True,
    )
    points = []
    for stage, (p_train, p_valid) in enumerate(staged, start=1):
        if stage % CURVE_EVERY and stage != PARAMS["n_estimators"]:
            continue
        points.append(
            {
                "step": stage,
                "train_logloss": log_loss(y_fit, p_train[:, 1]),
                "valid_logloss": log_loss(y_valid, p_valid[:, 1]),
                "valid_roc_auc": roc_auc_score(y_valid, p_valid[:, 1]),
            }
        )
    return points


def importance(pipeline, names: list[str]) -> dict[str, float]:
    gains = pipeline.named_steps["model"].feature_importances_
    pairs = zip(names, (float(g) for g in gains), strict=True)
    return dict(sorted(pairs, key=lambda kv: -kv[1]))
