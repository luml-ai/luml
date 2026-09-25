class Split:
    """Stratified train/test split of the dataset."""
    uid = "01M36TK791T6KY1F3RX65QC78J"

    consumes = {"data": "load_data.data"}
    produces = {"train": "dataset", "test": "dataset"}
    params = {"test_size": 0.25, "seed": 42}

    def materialize(self, ctx, data):
        from sklearn.model_selection import train_test_split

        train, test = train_test_split(
            data,
            test_size=self.params["test_size"],
            random_state=self.params["seed"],
            stratify=data["target"],
        )
        return {"train": train.reset_index(drop=True), "test": test.reset_index(drop=True)}
