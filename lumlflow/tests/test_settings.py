from pathlib import Path

import pytest
from lumlflow.settings import Settings, get_config


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
    monkeypatch.delenv("BACKEND_STORE_URI", raising=False)
    get_config.cache_clear()


class TestSettings:
    def test_default_resolves_under_home(self) -> None:
        settings = Settings()  # type: ignore[call-arg]
        expected = str(Path("~/.luml/experiments").expanduser().resolve())
        assert settings.BACKEND_STORE_URI == expected

    def test_luml_backend_store_uri_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        custom = tmp_path / "custom-store"
        monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(custom))
        settings = Settings()  # type: ignore[call-arg]
        assert settings.BACKEND_STORE_URI == str(custom.resolve())

    def test_luml_backend_store_uri_with_sqlite_prefix(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        custom = tmp_path / "with-prefix"
        monkeypatch.setenv("LUML_BACKEND_STORE_URI", f"sqlite://{custom}")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.BACKEND_STORE_URI == str(custom.resolve())

    def test_legacy_backend_store_uri_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        legacy = tmp_path / "legacy-store"
        monkeypatch.setenv("BACKEND_STORE_URI", str(legacy))
        settings = Settings()  # type: ignore[call-arg]
        assert settings.BACKEND_STORE_URI == str(legacy.resolve())

    def test_luml_backend_store_uri_takes_priority_over_legacy(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        new_store = tmp_path / "new"
        legacy_store = tmp_path / "legacy"
        monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(new_store))
        monkeypatch.setenv("BACKEND_STORE_URI", str(legacy_store))
        settings = Settings()  # type: ignore[call-arg]
        assert settings.BACKEND_STORE_URI == str(new_store.resolve())

    def test_tilde_expansion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LUML_BACKEND_STORE_URI", "~/some/path")
        settings = Settings()  # type: ignore[call-arg]
        expected = str(Path("~/some/path").expanduser().resolve())
        assert settings.BACKEND_STORE_URI == expected

    def test_db_suffix_stripped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        db_file = tmp_path / "experiments.db"
        monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(db_file))
        settings = Settings()  # type: ignore[call-arg]
        assert settings.BACKEND_STORE_URI == str(tmp_path.resolve())
