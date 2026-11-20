"""Prepares the Azurite account as a real Azure account would be for the platform.

Creates the container and sets the Blob service CORS rules a browser needs to read
artifacts by Range from another origin. Usage: ``python azurite_setup.py <connection
string> <container> <allowed origin>`` (backend venv: it has azure-storage-blob).
"""

import contextlib
import sys

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, CorsRule


def main() -> None:
    connection_string, container, origin = sys.argv[1:4]
    service = BlobServiceClient.from_connection_string(connection_string)
    service.set_service_properties(
        cors=[
            CorsRule(
                allowed_origins=[origin],
                allowed_methods=["GET", "HEAD", "PUT", "OPTIONS"],
                allowed_headers=["*"],
                exposed_headers=["*"],
                max_age_in_seconds=600,
            )
        ]
    )
    with contextlib.suppress(ResourceExistsError):
        service.create_container(container)


if __name__ == "__main__":
    main()
