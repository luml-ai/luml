from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_config() -> Settings:
    return Settings()  # type: ignore[call-arg]


config = get_config()
