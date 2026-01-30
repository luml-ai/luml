"""Exception classes for LUML Satellite SDK."""


class SatelliteException(Exception):
    """Base exception for all satellite-related errors."""


class PairingException(SatelliteException):
    """Exception raised when satellite pairing fails."""


class TaskException(SatelliteException):
    """Exception raised when a task operation fails."""


class ContainerNotFoundError(SatelliteException):
    """Exception raised when a container is not found."""

    def __init__(self, container_id: str) -> None:
        self.container_id = container_id
        super().__init__(f"Container '{container_id}' not found")


class ContainerNotRunningError(SatelliteException):
    """Exception raised when a container is not running."""

    def __init__(self, container_id: str, current_status: str) -> None:
        self.container_id = container_id
        self.current_status = current_status
        super().__init__(
            f"Container '{container_id}' is not running (status: {current_status})"
        )
