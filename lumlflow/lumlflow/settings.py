import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BACKEND_STORE_URI: str

    # quickfix, to be refactored later
    model_config = SettingsConfigDict(
        env_file=".env.test" if "PYTEST_VERSION" in os.environ else ".env",
        extra="ignore",
    )


@lru_cache
def get_config() -> Settings:
    return Settings()  # type: ignore[call-arg]


config = get_config()
