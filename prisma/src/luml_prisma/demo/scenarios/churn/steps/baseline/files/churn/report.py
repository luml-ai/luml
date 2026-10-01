"""Plots, data profile and the model card for a training run."""

import io
import json

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from luml.card import CardBuilder
from sklearn.calibration import calibration_curve
from sklearn.metrics import auc, confusion_matrix, roc_curve

from churn.data import CATEGORICAL, NUMERICAL, TARGET


def _png(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def roc_figure(y, p):
    fpr, tpr, _ = roc_curve(y, p)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(fpr, tpr, label=f"ROC (AUC = {auc(fpr, tpr):.3f})", color="#2563eb")
    ax.plot([0, 1], [0, 1], "--", color="#9ca3af", linewidth=1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Holdout ROC curve")
    ax.legend(loc="lower right")
    return fig


def confusion_figure(y, predicted):
    matrix = confusion_matrix(y, predicted)
    fig, ax = plt.subplots(figsize=(4, 3.6))
    image = ax.imshow(matrix, cmap="Blues")
    for (i, j), value in zip(((0, 0), (0, 1), (1, 0), (1, 1)), matrix.ravel(), strict=True):
        ax.text(j, i, str(value), ha="center", va="center",
                color="white" if value > matrix.max() / 2 else "black")
    ax.set_xticks([0, 1], ["retained", "churned"])
    ax.set_yticks([0, 1], ["retained", "churned"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion matrix")
    fig.colorbar(image, ax=ax, fraction=0.046)
    return fig


def calibration_figure(y, p):
    fraction, mean_predicted = calibration_curve(y, p, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(mean_predicted, fraction, marker="o", color="#059669", label="model")
    ax.plot([0, 1], [0, 1], "--", color="#9ca3af", linewidth=1, label="perfect")
    ax.set_xlabel("Mean predicted churn probability")
    ax.set_ylabel("Observed churn rate")
    ax.set_title("Calibration (10 quantile bins)")
    ax.legend()
    return fig


def importance_figure(importances: dict[str, float], top: int = 15):
    items = list(importances.items())[:top][::-1]
    names = [name for name, _ in items]
    values = [value for _, value in items]
    fig, ax = plt.subplots(figsize=(6, 0.32 * len(items) + 1))
    ax.barh(names, values, color=["#dc2626" if v < 0 else "#2563eb" for v in values])
    ax.set_title("Feature importance")
    ax.axvline(0, color="#374151", linewidth=0.8)
    return fig


def png(fig) -> bytes:
    return _png(fig)


def data_profile(df: pd.DataFrame) -> dict:
    profile = {
        "rows": int(len(df)),
        "churn_rate": round(float(df[TARGET].mean()), 4),
        "numerical": {},
        "categorical": {},
    }
    for column in NUMERICAL:
        series = df[column]
        profile["numerical"][column] = {
            "mean": round(float(series.mean()), 3),
            "std": round(float(series.std()), 3),
            "min": float(series.min()),
            "p50": float(series.median()),
            "max": float(series.max()),
            "missing": int(series.isna().sum()),
        }
    for column in CATEGORICAL:
        counts = df[column].value_counts(normalize=True)
        profile["categorical"][column] = {
            str(k): round(float(v), 4) for k, v in counts.items()
        }
    return profile


def build_model_card(
    *,
    title: str,
    strategy: str,
    feature_set: str,
    metrics: dict[str, float],
    params: dict,
    importances: dict[str, float],
    roc_fig,
    importance_fig,
    rows_train: int,
    rows_test: int,
) -> CardBuilder:
    card = CardBuilder(title=title)
    card.write_heading(title, level=1)
    card.write_markdown(
        f"Binary churn-risk scorer for Nimbus Analytics accounts "
        f"(**{strategy}** on the **{feature_set}** feature set). "
        f"Trained on {rows_train:,} accounts, evaluated on a stratified holdout of "
        f"{rows_test:,}. Positive class = account churned within the next 90 days."
    )
    card.write_heading("Holdout metrics", level=2)
    card.write(
        pd.DataFrame(
            {"metric": list(metrics), "value": [round(v, 4) for v in metrics.values()]}
        )
    )
    card.write(roc_fig)
    card.write_heading("What drives the score", level=2)
    card.write(importance_fig)
    top = list(importances.items())[:5]
    card.write_markdown(
        "Top signals: " + ", ".join(f"`{name}` ({value:+.3f})" for name, value in top)
    )
    card.write_heading("Training configuration", level=2)
    card.write_markdown("```json\n" + json.dumps(params, indent=2) + "\n```")
    card.write_heading("Intended use and limits", level=2)
    card.write_markdown(
        "- Scores accounts for the retention team's weekly outreach list.\n"
        "- Inputs must be the 12 account-snapshot fields; unseen plan or region "
        "values are encoded as all-zero one-hot rows.\n"
        "- Not calibrated for accounts younger than one billing cycle."
    )
    return card
