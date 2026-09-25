class LoadData:
    """Load the sklearn diabetes regression dataset as a dataframe."""

    uid = "01M00KYAT4KFHEJHYE82WM9T3G"
    produces = {"data": "asset"}

    def materialize(self, ctx):
        from sklearn.datasets import load_diabetes

        raw = load_diabetes(as_frame=True)
        df = raw.frame.copy()
        df.attrs["target_name"] = "target"
        return {"data": df}
