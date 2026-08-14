class Evaluate:
    """Evaluate the trained model on the held-out test split."""
    uid = "01M00KZ617GMHXT002D3K9VG7W"
    consumes = {"model": "train_model.model", "test": "split.test"}
    produces = {"metrics": "experiment"}

    def materialize(self, ctx, model, test):
        import numpy as np
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        x_test = test.drop(columns=["target"])
        y_test = test["target"]
        preds = model.predict(x_test)

        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        mae = float(mean_absolute_error(y_test, preds))
        r2 = float(r2_score(y_test, preds))

        ctx.tracker.log_params({"alpha": model.alpha})
        ctx.tracker.log_metrics({"rmse": rmse, "mae": mae, "r2": r2})

        return {"metrics": ctx.tracker.record}
