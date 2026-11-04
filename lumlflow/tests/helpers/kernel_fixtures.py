from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def tracker_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "experiments"
    monkeypatch.setenv("BACKEND_STORE_URI", str(store))
    monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(store))
    return store
