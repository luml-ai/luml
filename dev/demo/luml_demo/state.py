"""Persisted ids and secrets of a prepared demo environment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DemoState:
    api_key: str = ""
    user_id: str = ""
    organization_id: str = ""
    orbit_id: str = ""
    bucket_secret_id: str = ""
    collections: dict[str, str] = field(default_factory=dict)
    tracks: dict[str, str] = field(default_factory=dict)
    satellites: dict[str, dict[str, Any]] = field(default_factory=dict)
    repositories: dict[str, str] = field(default_factory=dict)
    runs: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    datasets: dict[str, str] = field(default_factory=dict)
    deployments: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> DemoState:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in known})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    def winner(self, scenario: str) -> dict[str, Any] | None:
        for artifact in self.artifacts.get(scenario, []):
            if artifact.get("winner"):
                return artifact
        return None

    def runner_up(self, scenario: str) -> dict[str, Any] | None:
        ranked = sorted(
            (a for a in self.artifacts.get(scenario, []) if not a.get("winner")),
            key=lambda a: -float(a.get("metric", 0.0)),
        )
        return ranked[0] if ranked else None
