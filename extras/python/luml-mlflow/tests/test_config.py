from pathlib import Path

import pytest
from luml_mlflow.config import Settings


def test_sqlite_scheme_is_stripped(tmp_path: Path) -> None:
    settings = Settings(LUML_BACKEND_STORE_URI=f"sqlite://{tmp_path}/exp")

    assert settings.LUML_BACKEND_STORE_URI == str(tmp_path / "exp")


def test_db_file_path_resolves_to_its_directory(tmp_path: Path) -> None:
    settings = Settings(LUML_BACKEND_STORE_URI=str(tmp_path / "exp" / "meta.db"))

    assert settings.LUML_BACKEND_STORE_URI == str(tmp_path / "exp")


def test_home_is_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    settings = Settings(LUML_BACKEND_STORE_URI="~/.luml/experiments")

    assert settings.LUML_BACKEND_STORE_URI == str(tmp_path / ".luml" / "experiments")


def test_non_sqlite_scheme_is_rejected() -> None:
    with pytest.raises(ValueError, match="only 'sqlite'"):
        Settings(LUML_BACKEND_STORE_URI="postgres://db/experiments")
