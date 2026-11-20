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


class NotFound(ApplicationError):
    def __init__(self, message: str = "Not Found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class CodedError(ApplicationError):
    """Answered as `{"detail": {"code", "message"}}` so clients can map `code` to a
    typed error."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        super().__init__(message, status_code)
