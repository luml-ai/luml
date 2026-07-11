class LumlExperimentsError(Exception):
    def __init__(
        self,
        message: str = "Luml Experiments error",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class LumlFilterError(LumlExperimentsError, ValueError):
    def __init__(
        self,
        message: str = "Invalid filter string",
    ) -> None:
        super().__init__(message)
