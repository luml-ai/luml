"""Re-export TaskHandler from SDK for backward compatibility."""

from luml_satellite_sdk import TaskHandler, TaskProtocol, TaskRegistry

__all__ = [
    "TaskHandler",
    "TaskProtocol",
    "TaskRegistry",
]
