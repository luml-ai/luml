"""Tests for SDK exceptions."""

from __future__ import annotations

import pytest

from luml_satellite_sdk.exceptions import (
    ContainerNotFoundError,
    ContainerNotRunningError,
    PairingException,
    SatelliteException,
    TaskException,
)


class TestSatelliteException:
    """Tests for SatelliteException."""

    def test_is_base_exception(self) -> None:
        """Test that SatelliteException inherits from Exception."""
        assert issubclass(SatelliteException, Exception)

    def test_can_raise_with_message(self) -> None:
        """Test raising SatelliteException with message."""
        with pytest.raises(SatelliteException, match="test error"):
            raise SatelliteException("test error")


class TestPairingException:
    """Tests for PairingException."""

    def test_inherits_from_satellite_exception(self) -> None:
        """Test that PairingException inherits from SatelliteException."""
        assert issubclass(PairingException, SatelliteException)

    def test_can_raise_with_message(self) -> None:
        """Test raising PairingException with message."""
        with pytest.raises(PairingException, match="pairing failed"):
            raise PairingException("pairing failed")

    def test_caught_by_satellite_exception(self) -> None:
        """Test that PairingException is caught by SatelliteException."""
        with pytest.raises(SatelliteException):
            raise PairingException("pairing failed")


class TestTaskException:
    """Tests for TaskException."""

    def test_inherits_from_satellite_exception(self) -> None:
        """Test that TaskException inherits from SatelliteException."""
        assert issubclass(TaskException, SatelliteException)

    def test_can_raise_with_message(self) -> None:
        """Test raising TaskException with message."""
        with pytest.raises(TaskException, match="task failed"):
            raise TaskException("task failed")


class TestContainerNotFoundError:
    """Tests for ContainerNotFoundError."""

    def test_inherits_from_satellite_exception(self) -> None:
        """Test that ContainerNotFoundError inherits from SatelliteException."""
        assert issubclass(ContainerNotFoundError, SatelliteException)

    def test_sets_container_id(self) -> None:
        """Test that container_id is set correctly."""
        error = ContainerNotFoundError("container-123")

        assert error.container_id == "container-123"

    def test_message_includes_container_id(self) -> None:
        """Test that error message includes container ID."""
        error = ContainerNotFoundError("container-123")

        assert "container-123" in str(error)

    def test_can_raise_and_catch(self) -> None:
        """Test raising and catching ContainerNotFoundError."""
        with pytest.raises(ContainerNotFoundError) as exc_info:
            raise ContainerNotFoundError("my-container")

        assert exc_info.value.container_id == "my-container"


class TestContainerNotRunningError:
    """Tests for ContainerNotRunningError."""

    def test_inherits_from_satellite_exception(self) -> None:
        """Test that ContainerNotRunningError inherits from SatelliteException."""
        assert issubclass(ContainerNotRunningError, SatelliteException)

    def test_sets_container_id(self) -> None:
        """Test that container_id is set correctly."""
        error = ContainerNotRunningError("container-123", "stopped")

        assert error.container_id == "container-123"

    def test_sets_current_status(self) -> None:
        """Test that current_status is set correctly."""
        error = ContainerNotRunningError("container-123", "stopped")

        assert error.current_status == "stopped"

    def test_message_includes_container_id_and_status(self) -> None:
        """Test that error message includes container ID and status."""
        error = ContainerNotRunningError("container-123", "exited")

        message = str(error)
        assert "container-123" in message
        assert "exited" in message

    def test_can_raise_and_catch(self) -> None:
        """Test raising and catching ContainerNotRunningError."""
        with pytest.raises(ContainerNotRunningError) as exc_info:
            raise ContainerNotRunningError("my-container", "paused")

        assert exc_info.value.container_id == "my-container"
        assert exc_info.value.current_status == "paused"
