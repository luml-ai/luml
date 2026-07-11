from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_STORE_PATH = "~/.luml/experiments"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LUML_BACKEND_STORE_URI: str = _DEFAULT_STORE_PATH
    LUML_MLFLOW_ON_UNSUPPORTED: Literal["warn", "raise"] = "warn"
    LUML_MLFLOW_AUTOSYNC: bool = True
    LUML_MLFLOW_UPLOAD_MODE: Literal["auto", "separate"] = "auto"
    LUML_MLFLOW_COLLECTION_CONFLICT: Literal["raise", "suffix"] = "raise"
    LUML_API_KEY: str | None = None
    LUML_BASE_URL: str = "https://api.luml.ai"
    LUML_WEB_URL: str = "https://app.luml.ai"
    LUML_ARTIFACT_URL_TEMPLATE: str = (
        "{web}/{org}/{orbit}/collections/{collection}/artifacts/{artifact_id}"
    )

    @field_validator("LUML_BACKEND_STORE_URI", mode="after")
    @classmethod
    def _normalize_store_uri(cls, v: str) -> str:
        return _normalize_store_path(v)


def _normalize_store_path(value: str) -> str:
    """Strip an optional ``sqlite://`` prefix, expand ``~``, and resolve."""
    if "://" in value:
        scheme, path_str = value.split("://", 1)
        if scheme != "sqlite":
            raise ValueError(
                f"Unsupported backend store scheme {scheme!r}; "
                "only 'sqlite' is supported"
            )
    else:
        path_str = value
    path = Path(path_str).expanduser().resolve()
    if path.suffix == ".db":
        path = path.parent
    return str(path)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
