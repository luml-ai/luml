from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseSatelliteSettings(BaseSettings):
    SATELLITE_TOKEN: str
    PLATFORM_URL: AnyHttpUrl = "https://api.luml.ai"
    BASE_URL: str = "http://localhost"
    POLL_INTERVAL_SEC: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
