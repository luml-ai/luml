"""The `luml` plugin's meta-skill must route only to package skills that exist."""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
META_SKILL = REPO / "skills/luml/SKILL.md"
SKILL_HOMES = {
    "luml-sdk": REPO / "sdk/python/sdk/luml/skills",
    "luml-api": REPO / "sdk/python/api/luml_api/skills",
    "lumlflow": REPO / "lumlflow/lumlflow/skills",
    "luml-mlflow": REPO / "extras/python/luml-mlflow/luml_mlflow/skills",
}


def _routed_skills() -> list[str]:
    return re.findall(r"skills show ([a-z-]+)`", META_SKILL.read_text())


def test_meta_skill_routes_to_every_package_skill() -> None:
    assert sorted(_routed_skills()) == sorted(SKILL_HOMES)


@pytest.mark.parametrize("name", list(SKILL_HOMES))
def test_routed_skill_exists(name: str) -> None:
    assert (SKILL_HOMES[name] / name / "SKILL.md").is_file()


def test_marketplace_points_at_the_plugin() -> None:
    marketplace = json.loads((REPO / ".claude-plugin/marketplace.json").read_text())
    (plugin,) = marketplace["plugins"]
    plugin_dir = REPO / plugin["source"]
    manifest = json.loads((plugin_dir / ".claude-plugin/plugin.json").read_text())
    assert manifest["name"] == plugin["name"] == "luml"
    assert plugin_dir / "SKILL.md" == META_SKILL
    assert not (plugin_dir / "skills").exists()
