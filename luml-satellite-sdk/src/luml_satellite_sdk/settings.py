"""Base settings for LUML satellite workers."""

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic_settings import SettingsConfigDict


class BaseSettings(PydanticBaseSettings):
    """Base configuration for satellite workers.

    Satellites should extend this class to add their specific settings.
    All settings can be overridden via environment variables.
    """

    api_url: AnyHttpUrl = AnyHttpUrl("https://api.luml.ai")
    """URL of the LUML platform API."""

    api_key: str
    """API key for authenticating with the LUML platform."""

    satellite_id: str
    """Unique identifier for this satellite instance."""

    polling_interval: float = 2.0
    """Interval in seconds between polling for new tasks."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
