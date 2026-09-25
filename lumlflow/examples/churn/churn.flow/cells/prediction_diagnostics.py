class PredictionDiagnostics:
    """Plot predicted-vs-actual values and residuals on the test split."""

    uid = "01M00M6530J9C7T1522Q61ZC9F"
    consumes = {"model": "train_model.model", "test": "split.test"}
    produces = {"plot": "asset"}

    def materialize(self, ctx, model, test):
        import matplotlib.pyplot as plt

        x_test = test.drop(columns=["target"])
        y_test = test["target"]
        preds = model.predict(x_test)
        residuals = y_test - preds

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

        ax1.scatter(y_test, preds, alpha=0.6, color="steelblue")
        lo, hi = y_test.min(), y_test.max()
        ax1.plot([lo, hi], [lo, hi], "r--", linewidth=1)
        ax1.set_xlabel("actual")
        ax1.set_ylabel("predicted")
        ax1.set_title("predicted vs actual")

        ax2.scatter(preds, residuals, alpha=0.6, color="darkorange")
        ax2.axhline(0, color="r", linestyle="--", linewidth=1)
        ax2.set_xlabel("predicted")
        ax2.set_ylabel("residual")
        ax2.set_title("residuals")

        fig.tight_layout()

        return {"plot": fig}
