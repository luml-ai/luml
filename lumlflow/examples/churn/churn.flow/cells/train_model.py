class TrainModel:
    """Train a ridge regression model on the diabetes training split."""

    uid = "01M00KZ0JWPTG4AYBSRZD3A6EB"
    consumes = {"train": "split.train"}
    produces = {"model": "model"}
    params = {"alpha": 1.0, "seed": 42}

    def materialize(self, ctx, train):
        from sklearn.linear_model import Ridge

        ctx.seed()
        x_train = train.drop(columns=["target"])
        y_train = train["target"]

        model = Ridge(alpha=self.params["alpha"])
        model.fit(x_train, y_train)

        return {"model": model}
