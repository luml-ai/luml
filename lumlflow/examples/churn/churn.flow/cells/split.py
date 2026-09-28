class Split:
    """Train/test split of the diabetes dataset."""

    uid = "01M00KYVY7C5DTWD81S0TBZHHG"
    consumes = {"data": "load_data.data"}
    produces = {"train": "asset", "test": "asset"}
    params = {"test_size": 0.2, "seed": 42}

    def materialize(self, ctx, data):
        from sklearn.model_selection import train_test_split

        ctx.seed()
        train, test = train_test_split(
            data, test_size=self.params["test_size"], random_state=self.params["seed"]
        )
        return {"train": train, "test": test}
