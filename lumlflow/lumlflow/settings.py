from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    BACKEND_STORE_URI: str
    LUML_API_KEY: str | None = None
    LUML_BASE_URL: str = "https://api.luml.ai"

    @field_validator("BACKEND_STORE_URI", mode="after")
    @classmethod
    def parse_uri(cls, v: str) -> str:
        if "://" in v:
            _, path_str = v.split("://", 1)
        else:
            path_str = v
        path = Path(path_str).resolve()
        if path.suffix == ".db":
            path = path.parent
        return str(path)


@lru_cache
def get_config() -> Settings:
    return Settings()  # type: ignore[call-arg]


@lru_cache
def get_tracker() -> "ExperimentTracker":  # type: ignore[name-defined]  # noqa: F821
    from luml.experiments.tracker import ExperimentTracker

    return ExperimentTracker(f"sqlite://{get_config().BACKEND_STORE_URI}")


config = get_config()
