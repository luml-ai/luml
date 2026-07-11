class FakeJsProxy:
    def __init__(self, obj):
        self.obj = obj

    def to_py(self):
        return self.obj
