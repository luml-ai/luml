from collections.abc import Iterator
from pathlib import Path

import pytest
from luml_mlflow import _tracker as tracker_mod
from luml_mlflow import config as config_mod


@pytest.fixture
def temp_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Point the plugin at a brand-new sqlite store under ``tmp_path``."""
    store = tmp_path / "experiments"
    monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(store))
    monkeypatch.setenv("LUML_MLFLOW_ON_UNSUPPORTED", "warn")
    config_mod.reset_settings_cache()
    tracker_mod.reset_tracker_cache()
    yield store
    config_mod.reset_settings_cache()
    tracker_mod.reset_tracker_cache()
