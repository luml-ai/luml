"""Publishing prisma run artifacts into collections, lineage and tracks."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from luml.artifacts.dataset import save_tabular_dataset
from luml_api import ArtifactStatus, ArtifactType, CollectionType, LumlClient
from luml_api.handlers.model_artifacts import ModelFileHandler

from luml_demo.config import TRACK_STAGES, DemoConfig, ScenarioSpec
from luml_demo.prisma_engine import PrismaClient, RunArtifact
from luml_demo.shell import say, wait_for
from luml_demo.state import DemoState

MODELS_COLLECTION = "models"
DATASETS_COLLECTION = "datasets"


def make_client(config: DemoConfig, state: DemoState) -> LumlClient:
    return LumlClient(
        base_url=config.api_url,
        api_key=state.api_key,
        organization=state.organization_id,
        orbit=state.orbit_id,
    )


def ensure_collections(client: LumlClient, state: DemoState) -> None:
    existing = {c.name: str(c.id) for c in client.collections.list_all()}
    wanted = {
        MODELS_COLLECTION: (CollectionType.MODEL, "Models promoted from Prisma research runs"),
        DATASETS_COLLECTION: (CollectionType.DATASET, "Training snapshots the models were fitted on"),
    }
    for name, (kind, description) in wanted.items():
        if name in existing:
            state.collections[name] = existing[name]
            continue
        created = client.collections.create(description=description, name=name, type=kind)
        state.collections[name] = str(created.id)
        say(f"created collection {name} ({kind})")


def ensure_tracks(client: LumlClient, state: DemoState, scenarios: tuple[ScenarioSpec, ...]) -> None:
    existing = {t.name: str(t.id) for t in client.tracks.list().items}
    for spec in scenarios:
        if spec.track_name in existing:
            state.tracks[spec.track_name] = existing[spec.track_name]
            continue
        track = client.tracks.create(
            name=spec.track_name,
            artifact_type=ArtifactType.MODEL,
            description=f"Registry track for {spec.model_name}; stages {', '.join(TRACK_STAGES)}",
            tags=[spec.name, "prisma"],
            stages=list(TRACK_STAGES),
        )
        state.tracks[spec.track_name] = str(track.id)
        say(f"created track {spec.track_name}")


def publish_dataset(client: LumlClient, state: DemoState, spec: ScenarioSpec, csv_path: Path) -> str | None:
    if spec.dataset_file is None:
        return None
    if spec.name in state.datasets:
        return state.datasets[spec.name]
    name = f"{spec.name}-training-snapshot"
    for existing in client.artifacts.list_all(collection_id=state.collections[DATASETS_COLLECTION]):
        if existing.name == name:
            state.datasets[spec.name] = str(existing.id)
            say(f"reusing dataset artifact {name} ({existing.id})")
            return str(existing.id)
    frame = pd.read_csv(csv_path)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{spec.name}-training-snapshot.luml"
        save_tabular_dataset(
            {"train": frame},
            file_format="csv",
            name=f"{spec.name}-training-snapshot",
            description=f"Account snapshot used to train {spec.model_name}",
            output_path=str(path),
        )
        artifact = client.artifacts.upload(
            str(path),
            name=f"{spec.name}-training-snapshot",
            description=f"{len(frame):,} rows, {len(frame.columns)} columns",
            tags=[spec.name, "training-data"],
            collection_id=state.collections[DATASETS_COLLECTION],
        )
    state.datasets[spec.name] = str(artifact.id)
    say(f"uploaded dataset artifact {artifact.name} ({artifact.id})")
    return str(artifact.id)


def _stage_for(rank: int, winner: bool) -> str | None:
    if winner:
        return "production"
    if rank == 0:
        return "development"
    if rank == 1:
        return "staging"
    return None


@dataclass(frozen=True)
class EngineUploads:
    """The engine's queued uploads for a run, so the engine moves the bytes and keeps the link."""

    prisma: PrismaClient
    run_id: str
    by_node: dict[str, dict[str, Any]]

    @classmethod
    def collect(cls, prisma: PrismaClient, run_id: str) -> EngineUploads:
        return cls(prisma, run_id, {str(u["node_id"]): u for u in prisma.pending_uploads(run_id)})


def upload_through_engine(
    client: LumlClient,
    uploads: EngineUploads,
    upload: dict[str, Any],
    artifact: RunArtifact,
    *,
    collection_id: str,
    name: str,
    description: str,
    tags: list[str],
    lineage_inputs: list[str] | None,
) -> str:
    """Register the artifact, hand the engine the presigned URL, wait, mark it uploaded."""
    details = ModelFileHandler(str(artifact.artifact_path)).artifact_details()
    created = client.artifacts.create(
        collection_id,
        file_name=f"{name}.luml",
        extra_values={**details.extra_values, "experiment_ids": artifact.experiment_ids},
        manifest=details.manifest,
        file_hash=details.file_hash,
        file_index=details.file_index,
        size=details.size,
        name=name,
        description=description,
        tags=tags,
        lineage_inputs=lineage_inputs,
    )
    artifact_id = str(created.artifact.id)
    url = created.upload_details.url
    if not url:
        raise RuntimeError(f"the platform returned no upload URL for {name}")
    uploads.prisma.post_upload_url(uploads.run_id, str(upload["id"]), url)

    def finished() -> bool:
        outcome = uploads.prisma.upload_outcome(uploads.run_id, str(upload["id"]))
        if outcome == "failed":
            raise RuntimeError(f"the engine failed to upload {name}")
        return outcome == "completed"

    wait_for(f"the engine to upload {name}", finished, timeout=900, interval=3)
    client.artifacts.update(artifact_id, status=ArtifactStatus.UPLOADED, collection_id=collection_id)
    return artifact_id


def publish_artifacts(
    client: LumlClient,
    state: DemoState,
    spec: ScenarioSpec,
    artifacts: list[RunArtifact],
    dataset_id: str | None,
    engine_uploads: EngineUploads | None = None,
) -> list[dict[str, Any]]:
    """Publish each run's model, chaining lineage and track versions in run order.

    With `engine_uploads` the bytes go through the engine's queue (as the browser does on
    a live run) and every node gets its registry link; otherwise the file is uploaded here.
    """
    published: list[dict[str, Any]] = []
    previous_id = dataset_id
    runner_up_rank = _runner_up_rank(artifacts, spec)
    collection_id = state.collections[MODELS_COLLECTION]
    track_id = state.tracks[spec.track_name]
    existing = {a.name: str(a.id) for a in client.artifacts.list_all(collection_id=collection_id)}
    tracked = {str(e.artifact_id): e for e in client.tracks.list_artifacts(track_id).items}
    for index, artifact in enumerate(artifacts):
        name = f"{spec.model_name}-{artifact.variant}"
        metric = artifact.metrics.get(spec.primary_metric, artifact.metrics.get("metric", 0.0))
        description = ", ".join(
            f"{key}={value:.4f}" for key, value in artifact.metrics.items() if key != "metric"
        )
        upload = engine_uploads.by_node.get(artifact.node_id) if engine_uploads else None
        tags = [spec.name, artifact.variant, "prisma", *(["winner"] if artifact.winner else [])]
        lineage_inputs = [previous_id] if previous_id else None
        if name in existing:
            artifact_id = existing[name]
            say(f"reusing uploaded {name} ({artifact_id})")
        elif upload is not None and engine_uploads is not None:
            artifact_id = upload_through_engine(
                client, engine_uploads, upload, artifact, collection_id=collection_id, name=name,
                description=f"Prisma run node {artifact.node_id[:8]} — {description}", tags=tags,
                lineage_inputs=lineage_inputs,
            )
            say(f"engine uploaded {name} ({artifact_id}) {spec.primary_metric}={metric:.4f}")
        else:
            uploaded = client.artifacts.upload(
                str(artifact.artifact_path),
                name=name,
                description=f"Prisma run node {artifact.node_id[:8]} — {description}",
                tags=tags,
                lineage_inputs=lineage_inputs,
                collection_id=collection_id,
            )
            artifact_id = str(uploaded.id)
            say(f"uploaded {name} ({artifact_id}) {spec.primary_metric}={metric:.4f}")
        if upload is not None and engine_uploads is not None:
            engine_uploads.prisma.post_artifact_link(
                engine_uploads.run_id, str(upload["id"]), artifact_id=artifact_id,
                organization_id=state.organization_id, orbit_id=state.orbit_id,
                collection_id=collection_id,
            )
            if name in existing:
                # Nothing was transferred for a reused artifact; close the queue entry so
                # an open Prisma page does not keep trying to resume it.
                engine_uploads.prisma.dismiss_upload(engine_uploads.run_id, str(upload["id"]))
        stage = "staging" if index == runner_up_rank else _stage_for(index, artifact.winner)
        entry = tracked.get(artifact_id)
        if entry is None:
            entry = client.tracks.add_artifact(track_id, artifact_id, stage=stage)
            say(f"  track {spec.track_name}: v{getattr(entry, 'version', '?')} stage={stage}")
        elif getattr(entry, "stage_name", None) != stage:
            entry = client.tracks.update_artifact(track_id, str(entry.id), stage=stage, force=True)
            say(f"  track {spec.track_name}: v{getattr(entry, 'version', '?')} moved to stage={stage}")
        published.append({
            "artifact_id": artifact_id,
            "name": name,
            "variant": artifact.variant,
            "metric": metric,
            "metrics": artifact.metrics,
            "winner": artifact.winner,
            "stage": stage,
            "version": getattr(entry, "version", None),
            "local_path": str(artifact.artifact_path),
            "experiment_ids": artifact.experiment_ids,
        })
        previous_id = artifact_id
    state.artifacts[spec.name] = published
    return published


def _runner_up_rank(artifacts: list[RunArtifact], spec: ScenarioSpec) -> int | None:
    candidates = [
        (index, a.metrics.get(spec.primary_metric, a.metrics.get("metric", 0.0)))
        for index, a in enumerate(artifacts) if not a.winner
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])[0]
