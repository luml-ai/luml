class CorrelationHeatmap:
    """Heatmap of pairwise feature correlations, including the target."""

    uid = "01M00M61EX9MZJHJD9DE9JY4MX"
    consumes = {"data": "load_data.data"}
    produces = {"plot": "asset"}

    def materialize(self, ctx, data):
        import matplotlib.pyplot as plt

        corr = data.corr(numeric_only=True)

        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(corr.columns)))
        ax.set_yticklabels(corr.columns)
        for i in range(len(corr.columns)):
            for j in range(len(corr.columns)):
                ax.text(
                    j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7
                )
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()

        return {"plot": fig}
