"""Settings for deploy satellite."""

from functools import lru_cache

from luml_satellite_sdk import BaseSettings
from pydantic import AliasChoices, AnyHttpUrl, Field
from pydantic_settings import SettingsConfigDict


class DeploySettings(BaseSettings):
    """Settings for the deploy satellite.

    Extends the SDK's BaseSettings to add deployment-specific configuration
    for Docker containers and model servers.

    Required environment variables (from BaseSettings):
        - API_KEY or SATELLITE_TOKEN: API key for authenticating with the LUML
          platform. (SATELLITE_TOKEN supported for backwards compatibility)
        - SATELLITE_ID: Unique identifier for this satellite instance.

    Optional environment variables:
        - API_URL or PLATFORM_URL: URL of the LUML platform API
          (default: https://api.luml.ai). PLATFORM_URL supported for backwards
          compatibility.
        - POLLING_INTERVAL or POLL_INTERVAL_SEC: Interval in seconds between polling
          (default: 2.0). POLL_INTERVAL_SEC supported for backwards compatibility.
        - BASE_URL: Public URL of this satellite (reported to platform).
        - DOCKER_NETWORK: Docker network name (default: satellite_satellite-network).
        - MODEL_SERVER_PORT: Port for model servers (default: 8080).
        - MODEL_IMAGE: Docker image for deployments (default: df-random-svc:latest).
        - HEALTH_CHECK_TIMEOUT: Health check timeout in seconds (default: 1800).
        - HEALTH_CHECK_INTERVAL: Health check interval in seconds (default: 1.0).
        - AGENT_API_HOST: Agent API bind host (default: 0.0.0.0).
        - AGENT_API_PORT: Agent API port (default: 8000).
    """

    # Override BaseSettings fields with backwards-compatible aliases
    api_key: str = Field(
        validation_alias=AliasChoices("API_KEY", "SATELLITE_TOKEN", "api_key"),
        description="API key for authenticating with the LUML platform.",
    )

    api_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("https://api.luml.ai"),
        validation_alias=AliasChoices("API_URL", "PLATFORM_URL", "api_url"),
        description="URL of the LUML platform API.",
    )

    polling_interval: float = Field(
        default=2.0,
        validation_alias=AliasChoices(
            "POLLING_INTERVAL", "POLL_INTERVAL_SEC", "polling_interval"
        ),
        description="Interval in seconds between polling for new tasks.",
    )

    # Docker configuration
    docker_network: str = Field(
        default="satellite_satellite-network",
        description="Docker network name for containers.",
    )

    # Model server configuration
    model_server_port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Port for model server containers.",
    )

    model_image: str = Field(
        default="df-random-svc:latest",
        description="Docker image to use for model deployments.",
    )

    # Health check configuration
    health_check_timeout: int = Field(
        default=1800,
        ge=1,
        description="Maximum time in seconds to wait for container health check.",
    )

    health_check_interval: float = Field(
        default=1.0,
        gt=0,
        description="Interval in seconds between health check attempts.",
    )

    # Agent API configuration
    agent_api_host: str = Field(
        default="0.0.0.0",
        description="Host to bind the agent API server.",
    )

    agent_api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for the agent API server.",
    )

    # Public URL for satellite (backwards compatibility with original satellite)
    base_url: str = Field(
        default="http://localhost",
        description="Public URL of this satellite (reported to platform).",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


# Backwards compatibility alias
Settings = DeploySettings


@lru_cache
def get_settings() -> DeploySettings:
    """Get cached settings instance.

    Returns:
        The deploy satellite settings loaded from environment variables.

    Note:
        This function is cached, so subsequent calls return the same instance.
        Required environment variables (API_KEY, SATELLITE_ID) must be set.
    """
    return DeploySettings()  # type: ignore[call-arg]


settings: DeploySettings = get_settings()
