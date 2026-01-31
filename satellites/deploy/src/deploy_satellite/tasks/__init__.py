"""Task implementations for the deploy satellite."""

from deploy_satellite.tasks.deploy import DeployTask
from deploy_satellite.tasks.undeploy import UndeployTask

__all__ = [
    "DeployTask",
    "UndeployTask",
]
