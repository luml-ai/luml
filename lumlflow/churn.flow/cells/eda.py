class Eda:
    """Exploratory summary of the diabetes dataset: shape, describe, correlations with target."""
    uid = "01M00KYGX6Q0FK2N50KVP3G58J"
    consumes = {"data": "load_data.data"}
    produces = {"summary": "asset", "correlations": "asset"}

    def materialize(self, ctx, data):
        describe = data.describe()

        corr_with_target = (
            data.corr(numeric_only=True)["target"]
            .drop("target")
            .sort_values(key=abs, ascending=False)
        )

        summary = {
            "shape": data.shape,
            "columns": list(data.columns),
            "missing_values": int(data.isna().sum().sum()),
            "describe": describe,
        }

        correlations = corr_with_target.to_dict()

        return {"summary": summary, "correlations": correlations}
