from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from luml_api import LumlClient

from luml_demo import registry
from luml_demo.config import SCENARIOS
from luml_demo.prisma_engine import RunArtifact
from luml_demo.state import DemoState


class FakeArtifacts:
    def __init__(self) -> None:
        self.uploads: list[dict[str, Any]] = []

    def upload(self, file_path: str, **kwargs: Any) -> SimpleNamespace:
        self.uploads.append({"file_path": file_path, **kwargs})
        return SimpleNamespace(id=f"art-{len(self.uploads)}", name=kwargs["name"])


class FakeTracks:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str, str | None]] = []

    def add_artifact(self, track_id: str, artifact_id: str, stage: str | None = None) -> SimpleNamespace:
        self.entries.append((track_id, artifact_id, stage))
        return SimpleNamespace(version=len(self.entries))


def _artifact(tmp_path: Path, variant: str, metric: float, *, winner: bool) -> RunArtifact:
    path = tmp_path / variant / "artifact.luml"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"tar")
    return RunArtifact(
        node_id=f"node-{variant}", variant=variant, worktree=path.parent, artifact_path=path,
        metrics={"metric": metric, "roc_auc": metric, "f1": 0.5}, experiment_ids=[f"exp-{variant}"],
        winner=winner,
    )


def test_publish_artifacts_chains_lineage_and_assigns_stages(tmp_path: Path) -> None:
    client = SimpleNamespace(artifacts=FakeArtifacts(), tracks=FakeTracks())
    state = DemoState(collections={"models": "col-m"}, tracks={"churn-scorer": "track-1"})
    spec = next(s for s in SCENARIOS if s.name == "churn")
    artifacts = [
        _artifact(tmp_path, "baseline", 0.83, winner=False),
        _artifact(tmp_path, "gradient-boosting", 0.87, winner=True),
        _artifact(tmp_path, "feature-engineering", 0.84, winner=False),
        _artifact(tmp_path, "cost-sensitive", 0.83, winner=False),
    ]
    published = registry.publish_artifacts(
        cast(LumlClient, client), state, spec, artifacts, dataset_id="ds-1",
    )

    uploads = client.artifacts.uploads
    assert [u["name"] for u in uploads] == [
        "churn-scorer-baseline", "churn-scorer-gradient-boosting",
        "churn-scorer-feature-engineering", "churn-scorer-cost-sensitive",
    ]
    assert [u["lineage_inputs"] for u in uploads] == [["ds-1"], ["art-1"], ["art-2"], ["art-3"]]
    assert all(u["collection_id"] == "col-m" for u in uploads)
    assert "winner" in uploads[1]["tags"]
    assert [e[2] for e in client.tracks.entries] == ["development", "production", "staging", None]
    winner, runner_up = state.winner("churn"), state.runner_up("churn")
    assert winner is not None and winner["artifact_id"] == "art-2"
    assert runner_up is not None and runner_up["artifact_id"] == "art-3"
    assert published[1]["version"] == 2
    assert published[0]["experiment_ids"] == ["exp-baseline"]
