from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from luml_api import ArtifactStatus, LumlClient

from luml_demo import registry
from luml_demo.config import SCENARIOS
from luml_demo.prisma_engine import RunArtifact
from luml_demo.state import DemoState


class FakeArtifacts:
    def __init__(self, existing: dict[str, str] | None = None) -> None:
        self.uploads: list[dict[str, Any]] = []
        self.existing = existing or {}

    def upload(self, file_path: str, **kwargs: Any) -> SimpleNamespace:
        self.uploads.append({"file_path": file_path, **kwargs})
        return SimpleNamespace(id=f"art-{len(self.uploads)}", name=kwargs["name"])

    def list_all(self, *, collection_id: str) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=aid, name=name) for name, aid in self.existing.items()]


class FakeTracks:
    def __init__(self, tracked: dict[str, tuple[int, str]] | None = None) -> None:
        self.entries: list[tuple[str, str, str | None]] = []
        self.tracked = tracked or {}

    def add_artifact(self, track_id: str, artifact_id: str, stage: str | None = None) -> SimpleNamespace:
        self.entries.append((track_id, artifact_id, stage))
        return SimpleNamespace(version=len(self.entries))

    def list_artifacts(self, track_id: str) -> SimpleNamespace:
        items = [
            SimpleNamespace(id=f"entry-{aid}", artifact_id=aid, version=v, stage_name=stage)
            for aid, (v, stage) in self.tracked.items()
        ]
        return SimpleNamespace(items=items)

    def update_artifact(self, track_id: str, entry_id: str, stage: str | None = None,
                        force: bool = False) -> SimpleNamespace:
        self.entries.append((track_id, f"update:{entry_id}", stage))
        return SimpleNamespace(version=99)


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


def test_publish_artifacts_reuses_uploaded_versions(tmp_path: Path) -> None:
    client = SimpleNamespace(
        artifacts=FakeArtifacts(existing={"churn-scorer-baseline": "art-old"}),
        tracks=FakeTracks(tracked={"art-old": (1, "development")}),
    )
    state = DemoState(collections={"models": "col-m"}, tracks={"churn-scorer": "track-1"})
    spec = next(s for s in SCENARIOS if s.name == "churn")
    artifacts = [
        _artifact(tmp_path, "baseline", 0.83, winner=False),
        _artifact(tmp_path, "gradient-boosting", 0.87, winner=True),
    ]
    published = registry.publish_artifacts(cast(LumlClient, client), state, spec, artifacts, dataset_id=None)
    assert [u["name"] for u in client.artifacts.uploads] == ["churn-scorer-gradient-boosting"]
    assert client.artifacts.uploads[0]["lineage_inputs"] == ["art-old"]
    assert client.tracks.entries == [
        ("track-1", "update:entry-art-old", "staging"),
        ("track-1", "art-1", "production"),
    ]
    assert published[0]["artifact_id"] == "art-old" and published[0]["version"] == 99


class FakePrisma:
    def __init__(self) -> None:
        self.urls: list[tuple[str, str]] = []
        self.links: list[dict[str, str]] = []

    def post_upload_url(self, run_id: str, upload_id: str, presigned_url: str) -> None:
        self.urls.append((upload_id, presigned_url))

    def upload_outcome(self, run_id: str, upload_id: str) -> str | None:
        return "completed" if any(u == upload_id for u, _ in self.urls) else None

    def post_artifact_link(self, run_id: str, upload_id: str, **link: str) -> None:
        self.links.append({"upload_id": upload_id, **link})


class FakeArtifactsWithCreate(FakeArtifacts):
    def __init__(self) -> None:
        super().__init__()
        self.created: list[dict[str, Any]] = []
        self.updates: list[tuple[str, Any]] = []

    def create(self, collection_id: str, **kwargs: Any) -> SimpleNamespace:
        self.created.append({"collection_id": collection_id, **kwargs})
        return SimpleNamespace(
            artifact=SimpleNamespace(id=f"art-{len(self.created)}"),
            upload_details=SimpleNamespace(url=f"https://bucket/{kwargs['name']}"),
        )

    def update(self, artifact_id: str, *, status: Any, collection_id: str) -> None:
        self.updates.append((artifact_id, status))


def test_publish_artifacts_through_the_engine_links_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    details = SimpleNamespace(
        manifest={"producer_tags": ["luml.ai::sklearn:v1"]}, file_hash="h", size=3,
        file_index={"manifest.json": (0, 2)}, extra_values={"roc_auc": 0.87},
    )
    monkeypatch.setattr(
        registry, "ModelFileHandler", lambda path: SimpleNamespace(artifact_details=lambda: details),
    )
    client = SimpleNamespace(artifacts=FakeArtifactsWithCreate(), tracks=FakeTracks())
    prisma = FakePrisma()
    state = DemoState(organization_id="org", orbit_id="orb", collections={"models": "col-m"},
                      tracks={"churn-scorer": "track-1"})
    spec = next(s for s in SCENARIOS if s.name == "churn")
    artifacts = [
        _artifact(tmp_path, "baseline", 0.83, winner=False),
        _artifact(tmp_path, "gradient-boosting", 0.87, winner=True),
    ]
    by_node = {"node-baseline": {"id": "up-1"}, "node-gradient-boosting": {"id": "up-2"}}
    uploads = registry.EngineUploads(cast(Any, prisma), "run-1", by_node)

    published = registry.publish_artifacts(
        cast(LumlClient, client), state, spec, artifacts, dataset_id="ds-1", engine_uploads=uploads,
    )

    assert client.artifacts.uploads == []
    assert [c["name"] for c in client.artifacts.created] == [
        "churn-scorer-baseline", "churn-scorer-gradient-boosting",
    ]
    expected_values = {"roc_auc": 0.87, "experiment_ids": ["exp-baseline"]}
    assert client.artifacts.created[0]["extra_values"] == expected_values
    assert client.artifacts.created[1]["lineage_inputs"] == ["art-1"]
    assert prisma.urls == [("up-1", "https://bucket/churn-scorer-baseline"),
                           ("up-2", "https://bucket/churn-scorer-gradient-boosting")]
    assert [u[1] for u in client.artifacts.updates] == [ArtifactStatus.UPLOADED] * 2
    assert prisma.links[1] == {"upload_id": "up-2", "artifact_id": "art-2", "organization_id": "org",
                               "orbit_id": "orb", "collection_id": "col-m"}
    assert published[1]["artifact_id"] == "art-2" and published[1]["stage"] == "production"


def test_publish_dataset_reuses_existing(tmp_path: Path) -> None:
    client = SimpleNamespace(artifacts=FakeArtifacts(existing={"churn-training-snapshot": "ds-old"}))
    state = DemoState(collections={"datasets": "col-d"})
    spec = next(s for s in SCENARIOS if s.name == "churn")
    assert registry.publish_dataset(cast(LumlClient, client), state, spec, tmp_path / "x.csv") == "ds-old"
    assert client.artifacts.uploads == []
    assert state.datasets == {"churn": "ds-old"}
