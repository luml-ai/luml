class LoadData:
    uid = "01M36TK77ZV7D7J2J952KZ55VN"

    produces = {"data": "asset"}

    def materialize(self, ctx):
        from sklearn.datasets import load_breast_cancer

        raw = load_breast_cancer(as_frame=True)
        df = raw.frame.copy()
        return {"data": df}
