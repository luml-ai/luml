class TrainModel:
    """Train a logistic regression baseline on the scaled training split."""
    uid = "01M36TK7ATD6Z1RER02GED8YP0"

    consumes = {"x_train": "features.x_train"}
    produces = {"model": "model"}
    params = {"C": 1.0, "seed": 42}

    def materialize(self, ctx, x_train):
        from sklearn.linear_model import LogisticRegression

        ctx.seed()
        x = x_train.drop(columns=["target"])
        y = x_train["target"]
        model = LogisticRegression(C=self.params["C"], max_iter=2000)
        model.fit(x, y)
        return {"model": model}
