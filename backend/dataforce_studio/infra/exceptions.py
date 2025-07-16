from fastapi import status


class ServiceError(Exception):
    def __init__(
        self,
        message: str = "Service error",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthError(ServiceError):
    def __init__(
        self,
        message: str = "Authentication error",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class OrganizationLimitReachedError(ServiceError):
    def __init__(
        self,
        message: str = "Organization reached users limit",
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class OrganizationDeleteError(ServiceError):
    def __init__(
        self,
        message: str = "Organization cant be deleted",
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class CollectionDeleteError(ServiceError):
    def __init__(
        self,
        message: str = "Collection cant be deleted",
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class OrbitLimitReachedError(ServiceError):
    def __init__(
        self,
        message: str = "Orbit reached users limit",
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class GoogleCodeMissingError(ServiceError):
    def __init__(
        self,
        message: str = "Google code is missing",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class NotFoundError(ServiceError):
    def __init__(
        self,
        message: str = "Not found",
        status_code: int = status.HTTP_404_NOT_FOUND,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class InsufficientPermissionsError(ServiceError):
    def __init__(
        self,
        message: str = "Not enough rights",
        status_code: int = status.HTTP_403_FORBIDDEN,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class DatabaseConstraintError(ServiceError):
    def __init__(
        self, message: str, status_code: int = status.HTTP_409_CONFLICT
    ) -> None:
        super().__init__(message=message, status_code=status_code)


class BucketSecretInUseError(ServiceError):
    def __init__(
        self,
        message: str = "Cannot delete bucket secret that is currently used by orbits",
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class UserAPIKeyCreateError(ServiceError):
    def __init__(
        self,
        message: str = "User can have only one api key",
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class APIKeyNotFoundError(ServiceError):
    def __init__(
        self,
        message: str = "API key not found",
        status_code: int = status.HTTP_404_NOT_FOUND,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )
