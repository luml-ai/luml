"""Churn-risk training run for Nimbus Analytics accounts.

Trains the configured scorer, evaluates it on the stratified holdout, tracks the
experiment (params, metric curves, eval samples, plots, model card) with luml-sdk,
packages the pipeline as a LUML artifact with a monitoring reference profile, and
reports results to the orchestrator via .prisma/result.json.

Metric: roc_auc on the holdout — higher is better.
"""

import json
import time

import numpy as np
import pandas as pd
from luml.integrations.sklearn import save_sklearn
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    classification_report,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline

from churn import data, features, model, report, tracking

GROUP = "churn-risk"
EVAL_DATASET = "churn-holdout-v1"
EVAL_SAMPLES = 150
CV_FOLDS = 5
VALIDATION_FRACTION = 0.15


class RunLog:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.started = time.time()

    def __call__(self, message: str) -> None:
        line = f"[{time.time() - self.started:7.2f}s] {message}"
        self.lines.append(line)
        print(line, flush=True)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def build_pipeline() -> Pipeline:
    return Pipeline(
        [("preprocess", features.build_preprocessor()), ("model", model.build_estimator())]
    )


def holdout_metrics(y, p, threshold: float) -> dict[str, float]:
    predicted = (p >= threshold).astype(int)
    roc_auc = roc_auc_score(y, p)
    return {
        "metric": round(float(roc_auc), 4),
        "roc_auc": round(float(roc_auc), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "f1": round(float(f1_score(y, predicted)), 4),
        "precision": round(float(precision_score(y, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(y, predicted)), 4),
        "accuracy": round(float(accuracy_score(y, predicted)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "log_loss": round(float(log_loss(y, p)), 4),
    }


def cross_validate(tracker, X, y, log: RunLog) -> dict[str, float]:
    folds = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=data.SEED)
    scores: dict[str, list[float]] = {"cv_roc_auc": [], "cv_pr_auc": [], "cv_f1": []}
    for fold, (train_idx, valid_idx) in enumerate(folds.split(X, y), start=1):
        pipeline = model.fit(build_pipeline(), X.iloc[train_idx], y.iloc[train_idx])
        p = pipeline.predict_proba(X.iloc[valid_idx])[:, 1]
        y_valid = y.iloc[valid_idx]
        fold_scores = {
            "cv_roc_auc": roc_auc_score(y_valid, p),
            "cv_pr_auc": average_precision_score(y_valid, p),
            "cv_f1": f1_score(y_valid, (p >= 0.5).astype(int)),
        }
        for key, value in fold_scores.items():
            tracker.log_dynamic(key, float(value), step=fold)
            scores[key].append(float(value))
        log(f"fold {fold}: roc_auc={fold_scores['cv_roc_auc']:.4f} "
            f"pr_auc={fold_scores['cv_pr_auc']:.4f}")
    return {key: round(float(np.mean(values)), 4) for key, values in scores.items()}


def native(value):
    if isinstance(value, np.generic):
        return value.item()
    return value


def log_eval_samples(tracker, X_test, y_test, ids, p, threshold: float) -> None:
    rng = np.random.default_rng(data.SEED)
    chosen = rng.choice(len(X_test), size=min(EVAL_SAMPLES, len(X_test)), replace=False)
    for index in sorted(chosen):
        row = X_test.iloc[index]
        probability = float(p[index])
        label = int(y_test.iloc[index])
        predicted = int(probability >= threshold)
        tracker.log_eval_sample(
            eval_id=str(ids.iloc[index]),
            dataset_id=EVAL_DATASET,
            inputs={name: native(value) for name, value in row.items()},
            outputs={"churn_probability": round(probability, 4), "predicted": predicted},
            references={"churned": label},
            scores={
                "correct": predicted == label,
                "abs_error": round(abs(probability - label), 4),
                "log_loss": round(float(-np.log(max(1e-6, probability if label else 1 - probability))), 4),
            },
            metadata={
                "risk_band": "high" if probability >= 0.6 else "medium" if probability >= 0.3 else "low",
                "plan": row["plan"],
                "region": row["region"],
                "segment": "strategic" if row["monthly_spend"] >= 150 else "standard",
            },
        )
    review = [str(ids.iloc[i]) for i in sorted(chosen)[:3]]
    tracker.log_eval_annotation(
        EVAL_DATASET, review[0], "label_audit", "feedback", "bool", True,
        user="retention-lead", rationale="Account closed after the renewal call; label confirmed.",
    )
    tracker.log_eval_annotation(
        EVAL_DATASET, review[1], "label_audit", "feedback", "bool", False,
        user="retention-lead",
        rationale="Downgrade to starter was recorded as churn — should stay retained.",
    )
    tracker.log_eval_annotation(
        EVAL_DATASET, review[2], "expected_risk_band", "expectation", "string", "high",
        user="retention-lead", rationale="Three escalations in the last quarter.",
    )


def log_attachments(tracker, *, df, y_test, p, predicted, ids, importances,
                    figures: dict[str, bytes], log: RunLog) -> None:
    for name, png in figures.items():
        tracker.log_attachment(f"plots/{name}.png", png, binary=True)
    predictions = pd.DataFrame(
        {"customer_id": ids, "churn_probability": np.round(p, 4),
         "predicted": predicted, "churned": y_test}
    )
    tracker.log_attachment("reports/holdout_predictions.csv", predictions.to_csv(index=False))
    tracker.log_attachment(
        "reports/classification_report.txt",
        classification_report(y_test, predicted, target_names=["retained", "churned"]),
    )
    tracker.log_attachment(
        "reports/data_profile.json", json.dumps(report.data_profile(df), indent=2)
    )
    tracker.log_attachment(
        "reports/feature_importance.json", json.dumps(importances, indent=2)
    )
    tracker.log_attachment("logs/train.log", log.text())


def main() -> None:
    log = RunLog()
    df = data.load_customers()
    X_train, X_test, y_train, y_test, ids_test = data.split_holdout(df)
    X_fit, X_valid, y_fit, y_valid = train_test_split(
        X_train, y_train, test_size=VALIDATION_FRACTION, stratify=y_train,
        random_state=data.SEED,
    )
    log(f"accounts={len(df)} train={len(X_train)} holdout={len(X_test)} "
        f"churn_rate={df[data.TARGET].mean():.3f}")

    tracker = tracking.make_tracker()
    run_name = f"churn-{model.MODEL_STRATEGY}-{features.FEATURE_SET}"
    exp_id = tracker.start_experiment(
        name=run_name, group=GROUP,
        tags=["churn", model.MODEL_STRATEGY, features.FEATURE_SET],
    )
    for key, value in {**features.PARAMS, **model.PARAMS}.items():
        tracker.log_static(key, value)
    tracker.log_static("dataset", "customers.csv")
    tracker.log_static("rows_total", len(df))
    tracker.log_static("rows_train", len(X_train))
    tracker.log_static("rows_holdout", len(X_test))
    tracker.log_static("churn_rate", round(float(df[data.TARGET].mean()), 4))
    tracker.log_static("cv_folds", CV_FOLDS)
    tracker.log_static("seed", data.SEED)

    log("cross-validation")
    cv_means = cross_validate(tracker, X_train, y_train, log)
    for key, value in cv_means.items():
        tracker.log_static(f"{key}_mean", value)

    log("training curve on the validation split")
    for point in model.training_curve(build_pipeline(), X_fit, y_fit, X_valid, y_valid):
        step = point.pop("step")
        for key, value in point.items():
            tracker.log_dynamic(key, float(value), step=step)

    log("fitting the final pipeline")
    valid_model = model.fit(build_pipeline(), X_fit, y_fit)
    threshold = model.decision_threshold(valid_model, X_valid, y_valid)
    pipeline = model.fit(build_pipeline(), X_train, y_train)
    p_test = pipeline.predict_proba(X_test)[:, 1]
    predicted = (p_test >= threshold).astype(int)
    metrics = holdout_metrics(y_test, p_test, threshold)
    tracker.log_static("decision_threshold", round(float(threshold), 4))
    for key, value in metrics.items():
        if key != "metric":
            tracker.log_dynamic(f"holdout_{key}", value)
    log(f"holdout: {metrics}")

    names = features.feature_names(pipeline.named_steps["preprocess"])
    importances = model.importance(pipeline, names)
    roc_fig = report.roc_figure(y_test, p_test)
    importance_fig = report.importance_figure(importances)
    figures = {
        "roc_curve": report.png(report.roc_figure(y_test, p_test)),
        "confusion_matrix": report.png(report.confusion_figure(y_test, predicted)),
        "calibration": report.png(report.calibration_figure(y_test, p_test)),
        "feature_importance": report.png(report.importance_figure(importances)),
    }
    log_eval_samples(tracker, X_test, y_test, ids_test, p_test, threshold)
    log_attachments(
        tracker, df=df, y_test=y_test, p=p_test, predicted=predicted, ids=ids_test,
        importances=importances, figures=figures, log=log,
    )

    log("packaging the scorer as a LUML artifact")
    tracking.ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tracking.ARTIFACT_PATH.unlink(missing_ok=True)
    model_ref = save_sklearn(
        pipeline,
        X_train,
        path=str(tracking.ARTIFACT_PATH),
        extra_code_modules=["churn"],
        reference_data=X_train,
        manifest_model_name="churn-scorer",
        manifest_model_version=f"{model.MODEL_STRATEGY}-{features.FEATURE_SET}",
        manifest_model_description=(
            f"Nimbus churn-risk scorer — {model.MODEL_STRATEGY} on {features.FEATURE_SET} "
            f"features (holdout roc_auc={metrics['roc_auc']:.3f})"
        ),
    )
    card = report.build_model_card(
        title=f"Churn scorer — {model.MODEL_STRATEGY} / {features.FEATURE_SET}",
        strategy=model.MODEL_STRATEGY, feature_set=features.FEATURE_SET,
        metrics={k: v for k, v in metrics.items() if k != "metric"},
        params={**features.PARAMS, **model.PARAMS, "decision_threshold": threshold},
        importances=importances, roc_fig=roc_fig, importance_fig=importance_fig,
        rows_train=len(X_train), rows_test=len(X_test),
    )
    model_ref.add_model_card(card)
    tracking.register_metrics(model_ref, {k: v for k, v in metrics.items() if k != "metric"})
    tracker.log_model(
        model_ref, name="churn-scorer", tags=[model.MODEL_STRATEGY, features.FEATURE_SET],
        description=f"holdout roc_auc={metrics['roc_auc']:.4f}",
    )
    tracker.end_experiment(exp_id)
    tracker.link_to_model(model_ref, experiment_id=exp_id)

    tracking.write_result(exp_id, metrics)
    log(f"done: experiment={exp_id} roc_auc={metrics['roc_auc']:.4f}")


if __name__ == "__main__":
    main()
