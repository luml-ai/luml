from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_STORE_PATH = "~/.luml/experiments"

if TYPE_CHECKING:
    from lumlflow.tracker import TrackerProvider

_tracker_provider: "TrackerProvider | None" = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    BACKEND_STORE_URI: str = Field(
        default=_DEFAULT_STORE_PATH,
        validation_alias=AliasChoices("LUML_BACKEND_STORE_URI", "BACKEND_STORE_URI"),
    )
    LUML_API_KEY: str | None = None
    LUML_BASE_URL: str = "https://api.luml.ai"

    @field_validator("BACKEND_STORE_URI", mode="after")
    @classmethod
    def parse_uri(cls, v: str) -> str:
        if "://" in v:
            _, path_str = v.split("://", 1)
        else:
            path_str = v
        path = Path(path_str).expanduser().resolve()
        if path.suffix == ".db":
            path = path.parent
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)


@lru_cache
def get_config() -> Settings:
    return Settings()  # type: ignore[call-arg]


def get_tracker() -> "TrackerProvider":
    global _tracker_provider

    if _tracker_provider is None:
        from lumlflow.tracker import TrackerProvider

        _tracker_provider = TrackerProvider(
            lambda: Settings().BACKEND_STORE_URI  # type: ignore[call-arg]
        )
    return _tracker_provider


config = get_config()
