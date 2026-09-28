class Features:
    """Standardize features; the scaler is fitted on train and applied to test."""
    uid = "01M36TK79XXJY52X4Q95GAZ55H"

    consumes = {"train": "split.train", "test": "split.test"}
    produces = {"x_train": "dataset", "x_test": "dataset", "scaler": "asset"}

    def materialize(self, ctx, train, test):
        import pandas as pd
        from sklearn.preprocessing import StandardScaler

        columns = [c for c in train.columns if c != "target"]
        scaler = StandardScaler().fit(train[columns])
        x_train = pd.DataFrame(scaler.transform(train[columns]), columns=columns)
        x_test = pd.DataFrame(scaler.transform(test[columns]), columns=columns)
        x_train["target"] = train["target"].to_numpy()
        x_test["target"] = test["target"].to_numpy()
        return {"x_train": x_train, "x_test": x_test, "scaler": scaler}
