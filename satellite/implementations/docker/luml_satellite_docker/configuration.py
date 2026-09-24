from luml_satellite import SatelliteConfiguration
from pydantic import Field


class DockerConfiguration(SatelliteConfiguration):
    BASE_URL: str = "http://localhost"
    MODEL_IMAGE: str = "luml-random-svc:latest"
    MODEL_SERVER_PORT: int = Field(default=8080, ge=1, le=65535)
    DOCKER_NETWORK_NAME: str = ""
