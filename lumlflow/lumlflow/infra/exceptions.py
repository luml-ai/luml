from fastapi import status


class ApplicationError(Exception):
    def __init__(
        self,
        message: str = "Application error",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

