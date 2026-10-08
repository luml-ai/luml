class TrainModel:
    uid = "01M00KZ0JWPTG4AYBSRZD3A6EB"
    consumes = {"train": "split.train"}
    produces = {"model": "model"}
    params = {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 3, "seed": 42}

    def materialize(self, ctx, train):
        from sklearn.ensemble import RandomForestRegressor

        ctx.seed()
        x_train = train.drop(columns=["target"])
        y_train = train["target"]

        model = RandomForestRegressor(
            n_estimators=self.params["n_estimators"],
            max_depth=self.params["max_depth"],
            min_samples_leaf=self.params["min_samples_leaf"],
            random_state=self.params["seed"],
            n_jobs=-1,
        )
        model.fit(x_train, y_train)

        return {"model": model}
