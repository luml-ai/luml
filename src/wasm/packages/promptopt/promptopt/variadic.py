class VariadicList(list):
    def __repr__(self):
        return f"VariadicList<{super().__repr__()}>"
