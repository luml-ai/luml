class PlatformError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: object = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class PlatformRefusal(PlatformError):
    pass


class AuthenticationFailure(PlatformError):
    pass


class LegacyAddressRequired(PlatformRefusal):
    pass


PlatformAuthenticationError = AuthenticationFailure
PlatformRefusalError = PlatformRefusal
