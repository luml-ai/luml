from functools import lru_cache

from luml_satellite_kit import BaseSatelliteSettings


class Settings(BaseSatelliteSettings):
    MODEL_IMAGE: str = "df-random-svc:latest"
    MODEL_SERVER_PORT: int = 8080


@lru_cache
def get_config() -> Settings:
    return Settings()


config = get_config()
