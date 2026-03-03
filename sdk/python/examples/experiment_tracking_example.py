import shutil
import tempfile

from sklearn.datasets import load_iris
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

from luml.experiments.tracker import ExperimentTracker


def run_experiment() -> None:
    tracker = ExperimentTracker()

    # ── 1. Start experiment ──────────────────────────────────────

    exp_id = tracker.start_experiment(
        name="gbm_iris_baseline",
        group="iris_classification",
        tags=["baseline", "gbm"],
    )
    print(f"Started experiment: {exp_id}")

    # ── 2. Log hyperparameters ───────────────────────────────────

    n_estimators = 100
    learning_rate = 0.1
    max_depth = 3

    tracker.log_static("n_estimators", n_estimators)
    tracker.log_static("learning_rate", learning_rate)
    tracker.log_static("max_depth", max_depth)
    tracker.log_static("dataset", "iris")

    # ── 3. Train with dynamic metric logging ─────────────────────

    X, y = load_iris(return_X_y=True)

    model = GradientBoostingClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        random_state=42,
    )

    print("\nTraining (logging CV metrics every 10 trees):")
    for n_trees in range(10, n_estimators + 1, 10):
        model.set_params(n_estimators=n_trees)
        model.fit(X, y)

        scores = cross_val_score(model, X, y, cv=3, scoring="accuracy")
        mean_acc = round(scores.mean(), 4)
        std_acc = round(scores.std(), 4)

        tracker.log_dynamic("cv_accuracy_mean", mean_acc, step=n_trees)
        tracker.log_dynamic("cv_accuracy_std", std_acc, step=n_trees)
        print(f"  n_trees={n_trees:3d}  cv_acc={mean_acc:.4f} ± {std_acc:.4f}")

    # ── 4. Log the trained model ─────────────────────────────────

    model_ref = tracker.log_model(
        model,
        name="gbm_iris_final",
        tags=["final", "v1"],
        inputs=X,
    )
    print(f"\nModel logged: {model_ref.path}")

    # ── 5. Retrieve and inspect ──────────────────────────────────

    data = tracker.get_experiment(exp_id)

    print(f"\n--- Experiment summary ---")
    print(f"Name:           {data.metadata.name}")
    print(f"Status:         {data.metadata.status}")
    print(f"Static params:  {data.static_params}")
    print(f"Metric steps:   {len(data.dynamic_metrics.get('cv_accuracy_mean', []))}")

    last_acc = data.dynamic_metrics["cv_accuracy_mean"][-1]
    print(f"Final CV acc:   {last_acc['value']} (step {last_acc['step']})")

    models = tracker.get_models()
    print(f"Models logged:  {len(models)}")
    for m in models:
        print(f"  - {m.name} (tags={m.tags})")

    # ── 6. End experiment ────────────────────────────────────────

    tracker.end_experiment(exp_id)

    experiments = tracker.list_experiments()
    exp = next(e for e in experiments if e.id == exp_id)
    print(f"\nAfter end:")
    print(f"  Status:         {exp.status}")
    print(f"  Dynamic params: {exp.dynamic_params}")


if __name__ == "__main__":
    run_experiment()
