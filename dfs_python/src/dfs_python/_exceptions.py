class DataForceAPIError(Exception):
    def __init__(
        self,
        message: str = "DataForce Studio API error.",
    ) -> None:
        self.message = message
        super().__init__(self.message)
