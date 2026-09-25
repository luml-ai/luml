class FeatureDistributions:
    """Histograms of each feature and the target."""

    uid = "01M00M5X7PCEF070G7QV7VNEXA"
    consumes = {"data": "load_data.data"}
    produces = {"plot": "asset"}

    def materialize(self, ctx, data):
        import matplotlib.pyplot as plt

        cols = list(data.columns)
        n = len(cols)
        ncols = 4
        nrows = -(-n // ncols)

        fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows))
        axes = axes.flatten()
        for ax, col in zip(axes, cols, strict=False):
            ax.hist(data[col], bins=30, color="steelblue", edgecolor="white")
            ax.set_title(col)
        for ax in axes[n:]:
            ax.axis("off")
        fig.tight_layout()

        return {"plot": fig}
