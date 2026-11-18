from pathlib import Path

import pytest

from luml_prisma.config import (
    DATA_DIR_ENV_VAR,
    get_config_path,
    get_data_dir,
    load_config,
)
from luml_prisma.services.agents import _custom_agents_path


def test_data_dir_defaults_under_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert get_data_dir() == tmp_path / ".luml" / "prisma"
    assert get_config_path() == tmp_path / ".luml" / "prisma" / "config.toml"


def test_data_dir_env_override_moves_every_state_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    custom = tmp_path / "demo-engine"
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(custom))

    assert get_data_dir() == custom
    assert custom.is_dir()
    assert get_config_path() == custom / "config.toml"
    assert _custom_agents_path() == custom / "coding-clis.json"
    config = load_config()
    assert config.data_dir == custom
    assert config.db_path == custom / "luml-prisma.db"


@pytest.mark.parametrize("source", ["default", "toml", "environment"])
def test_upload_bucket_host_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: str,
) -> None:
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.delenv("LUML_PRISMA_UPLOAD_BUCKET_HOST", raising=False)
    if source != "default":
        get_config_path().write_text('upload_bucket_host = "bucket.example.com"\n')
    if source == "environment":
        monkeypatch.setenv("LUML_PRISMA_UPLOAD_BUCKET_HOST", "other.example.com")
    expected = {
        "default": "",
        "toml": "bucket.example.com",
        "environment": "other.example.com",
    }
    assert load_config().upload_bucket_host == expected[source]
