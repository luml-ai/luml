class Evaluate:
    """Score the model on the held-out split and log it as an experiment."""
    uid = "01M36TK7BS5TC26E92RQWD26V1"

    consumes = {"model": "train_model.model", "x_test": "features.x_test"}
    produces = {"experiment": "experiment", "metrics": "asset"}

    def materialize(self, ctx, model, x_test):
        from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

        x = x_test.drop(columns=["target"])
        y = x_test["target"]
        preds = model.predict(x)
        proba = model.predict_proba(x)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y, preds)),
            "f1": float(f1_score(y, preds)),
            "roc_auc": float(roc_auc_score(y, proba)),
        }
        ctx.tracker.log_params({"model": type(model).__name__, **model.get_params()})
        ctx.tracker.log_metrics(metrics)
        return {"experiment": ctx.tracker.record, "metrics": metrics}
