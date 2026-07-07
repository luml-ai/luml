from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SATELLITE_TOKEN: str
    PLATFORM_URL: AnyHttpUrl = "https://api.luml.ai"
    BASE_URL: str = "http://localhost"
    MODEL_IMAGE: str = "luml-random-svc:latest"
    POLL_INTERVAL_SEC: float = 2.0
    MODEL_SERVER_PORT: int = 8080
    MONITORING_FRAME_ANCESTORS: str = ""
    MONITORING_SESSION_TTL_SECONDS: int = 1800

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    def monitoring_frame_ancestors(self) -> list[str]:
        return self.MONITORING_FRAME_ANCESTORS.split()


@lru_cache
def get_config() -> Settings:
    return Settings()


config = get_config()
