"""The placeholder model-registry store resolves for ``luml://`` and is empty.

Its only job is to make the registry resolvable so an MLflow server started
against a luml tracking URI does not emit the "Model registry functionality is
unavailable" banner; every read returns empty.
"""

import pytest
from luml_mlflow.registry import NO_REGISTRY, LumlModelRegistryStore
from mlflow.exceptions import MlflowException


def test_searches_return_empty() -> None:
    store = LumlModelRegistryStore("luml://local")
    assert list(store.search_registered_models()) == []
    assert list(store.search_model_versions()) == []
    assert store.get_latest_versions("anything") == []


def test_resolves_via_mlflow_for_luml_uri() -> None:
    from mlflow.tracking._model_registry.utils import _get_store

    store = _get_store("luml://local")
    assert isinstance(store, LumlModelRegistryStore)
    assert list(store.search_registered_models()) == []


def test_registering_a_model_names_the_missing_registry() -> None:
    store = LumlModelRegistryStore("luml://local")

    with pytest.raises(MlflowException, match=NO_REGISTRY[:35]):
        store.create_registered_model("churn")
    with pytest.raises(MlflowException, match=NO_REGISTRY[:35]):
        store.create_model_version("churn", "file:///tmp/churn")
