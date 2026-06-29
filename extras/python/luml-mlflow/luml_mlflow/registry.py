"""Placeholder MLflow model-registry store for the ``luml`` scheme.

The luml backend does not implement a model registry. Without a registry store
registered for ``luml://``, an MLflow server started against a luml tracking URI
shows a "Model registry functionality is unavailable; got unsupported URI" banner
and the registry pages fail to load.

This store exists only to make the registry *resolvable*: it constructs cleanly
and returns empty results for the read/search calls the UI issues on load, so the
registry pages render empty instead of erroring. Mutating operations are not
supported and inherit the base store's ``NotImplementedError``.
"""

from typing import Any

from mlflow.entities.model_registry import ModelVersion, RegisteredModel
from mlflow.store.entities import PagedList
from mlflow.store.model_registry.abstract_store import AbstractStore


class LumlModelRegistryStore(AbstractStore):
    """Empty, read-only registry placeholder so the registry resolves for luml."""

    def search_registered_models(
        self,
        filter_string: str | None = None,
        max_results: int | None = None,
        order_by: list[str] | None = None,
        page_token: str | None = None,
    ) -> PagedList[RegisteredModel]:
        return PagedList([], token=None)

    def search_model_versions(
        self,
        filter_string: str | None = None,
        max_results: int | None = None,
        order_by: list[str] | None = None,
        page_token: str | None = None,
    ) -> PagedList[ModelVersion]:
        return PagedList([], token=None)

    def get_latest_versions(
        self, name: str, stages: list[str] | None = None
    ) -> list[ModelVersion]:
        return []

    def set_registered_model_tag(self, name: str, tag: Any) -> None:
        return None

    def set_model_version_tag(self, name: str, version: str, tag: Any) -> None:
        return None


__all__ = ["LumlModelRegistryStore"]
