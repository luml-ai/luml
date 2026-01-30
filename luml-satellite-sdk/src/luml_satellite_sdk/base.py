"""Base abstractions for LUML Satellite implementations."""

from abc import ABC, abstractmethod
from typing import Any


class BaseSatellite(ABC):
    """Abstract base class for LUML satellite implementations.

    A satellite is a worker agent that connects to the LUML platform,
    registers its capabilities, and executes tasks assigned to it.

    Subclasses must implement the lifecycle methods (start, stop) and
    capability registration to define what tasks the satellite can handle.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the satellite and begin processing tasks.

        This method should:
        - Initialize any required resources (connections, services)
        - Register with the LUML platform
        - Begin the task polling/processing loop

        Raises:
            RuntimeError: If the satellite fails to start.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the satellite gracefully.

        This method should:
        - Stop accepting new tasks
        - Wait for in-progress tasks to complete (with timeout)
        - Clean up resources and connections
        - Deregister from the platform if applicable
        """
        ...

    @abstractmethod
    def register_capabilities(self) -> dict[str, Any]:
        """Register the capabilities this satellite supports.

        Returns a dictionary describing the satellite's capabilities,
        which is sent to the platform during pairing/registration.

        Returns:
            A dictionary mapping capability names to their specifications.
            Each capability should include version info and supported features.

        Example:
            {
                "deploy": {
                    "version": 1,
                    "supported_variants": ["pyfunc", "pipeline"],
                },
                "inference": {
                    "version": 1,
                    "supported_frameworks": ["pytorch", "tensorflow"],
                }
            }
        """
        ...
