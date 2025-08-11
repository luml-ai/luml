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


class AuthError(ApplicationError):
    def __init__(
        self,
        message: str = "Authentication error",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )


class NotFoundError(ApplicationError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class OrganizationLimitReachedError(ApplicationError):
    def __init__(self, message: str = "Organization reached users limit") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class OrganizationDeleteError(ApplicationError):
    def __init__(self, message: str = "Organization cant be deleted") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class OrganizationMemberAlreadyExistsError(ApplicationError):
    def __init__(self, message: str = "Organization member already exists") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class OrganizationMemberNotFoundError(ApplicationError):
    def __init__(self, message: str = "Organization member not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class OrganizationInviteNotFoundError(ApplicationError):
    def __init__(self, message: str = "Organization invite not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class OrganizationInviteAlreadyExistsError(ApplicationError):
    def __init__(self, message: str = "Organization invite already exists") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class EmailDeliveryError(ApplicationError):
    def __init__(
        self,
        message: str = "Error sending email",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(message, status_code)


class CollectionDeleteError(ApplicationError):
    def __init__(self, message: str = "Collection cant be deleted") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class OrbitLimitReachedError(ApplicationError):
    def __init__(self, message: str = "Orbit reached users limit") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class GoogleCodeMissingError(ApplicationError):
    def __init__(self, message: str = "Google code is missing") -> None:
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class InsufficientPermissionsError(ApplicationError):
    def __init__(self, message: str = "Not enough rights") -> None:
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class BucketSecretInUseError(ApplicationError):
    def __init__(
        self,
        message: str = "Cannot delete bucket secret that is currently used by orbits",
    ) -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class UserAPIKeyCreateError(ApplicationError):
    def __init__(self, message: str = "Error creating api key for user") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class APIKeyNotFoundError(ApplicationError):
    def __init__(self, message: str = "API key not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class OrbitError(ApplicationError):
    def __init__(
        self, message: str = "Orbit Error", status_code: int = status.HTTP_409_CONFLICT
    ) -> None:
        super().__init__(message, status_code)


class OrbitMemberNotAllowedError(ApplicationError):
    def __init__(self, message: str = "User cannot be added to orbit") -> None:
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class OrbitMemberAlreadyExistsError(ApplicationError):
    def __init__(
        self, message: str = "Member for this this user already exist."
    ) -> None:
        super().__init__(message, status.HTTP_409_CONFLICT)


class OrbitAccessDeniedError(ApplicationError):
    def __init__(self, message: str = "Access to orbit denied") -> None:
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class OrbitMemberNotFoundError(ApplicationError):
    def __init__(self, message: str = "Orbit member not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class OrbitNotFoundError(ApplicationError):
    def __init__(self, message: str = "Orbit not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class InvalidStatusTransitionError(ApplicationError):
    def __init__(self, message: str = "Invalid status transition") -> None:
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class RepositoryError(Exception):
    def __init__(
        self,
        message: str = "Repository error",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseConstraintError(RepositoryError):
    def __init__(
        self,
        message: str = "Database Constraint Error.",
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        super().__init__(message, status_code)


class BucketSecretNotFoundError(ApplicationError):
    def __init__(self, message: str = "Bucket secret not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class CollectionNotFoundError(ApplicationError):
    def __init__(self, message: str = "Collection not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ModelArtifactNotFoundError(ApplicationError):
    def __init__(self, message: str = "Model Artifact model not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class BucketConnectionError(ApplicationError):
    def __init__(
        self,
        message: str = "Failed to connect to bucket.",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
        )
