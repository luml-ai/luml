"""Writes experiments with this worktree's SDK and publishes them with its API client.

Run by run.sh against the disposable stack. For each storage (MinIO through the S3
bucket secret, Azurite through the Azure one) it creates an orbit and a `mixed`
collection, uploads every scenario artifact into it, and writes the ids the browser
specs need to ``$E2E_WORK_DIR/platform.json``.
"""

from __future__ import annotations

import json
import math
import os
import random
import shutil
import subprocess
import sys
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from luml_api import LumlClient
from luml_api._types import ArtifactStatus, BucketType, CollectionType

from luml.experiments.tracker import ExperimentTracker

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "sdk/python/sdk/tests/fixtures/experiment_snapshots"
OLD_SDK_SCRIPT = Path(__file__).with_name("old_sdk_experiment.py")

LARGE_POINTS_PER_KEY = 1_000_000
LARGE_KEYS = ("train/loss", "train/grad_norm", "val/accuracy")
REGULAR_STEPS = 3_000
SHORT_STEPS = 40
# Debugging only: generated artifacts are kept and reused there (deterministic).
CACHE = os.environ.get("E2E_ARTIFACT_CACHE")
TWIN_KEY = "train/long_running_metric/with_a_fairly_long_key_name"


@dataclass
class Published:
    id: str
    name: str
    kind: str
    generation: int
    member: str
    offset: int
    size: int
    file_size: int
    bucket_location: str


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"missing environment variable {name}")
    return value


def api_key(base_url: str) -> str:
    with httpx.Client(base_url=base_url, timeout=30) as session:
        signed_in = session.post(
            "/v1/auth/signin",
            json={
                "email": env("DEV_ADMIN_EMAIL"),
                "password": env("DEV_ADMIN_PASSWORD"),
            },
        )
        signed_in.raise_for_status()
        # The auth cookie is Secure, which httpx does not send over http; browsers do on
        # loopback, so the platform works there. Sent by hand.
        token = signed_in.cookies["access_token"]
        created = session.post(
            "/v1/users/me/api-keys",
            headers={
                "Cookie": f"access_token={token}",
                "Origin": env("E2E_FRONTEND_URL"),
            },
        )
        created.raise_for_status()
        return str(created.json()["key"])


def log_series(
    tracker: ExperimentTracker, key: str, steps: int, seed: int, scale: float = 1.0
) -> None:
    rng = random.Random(seed)
    for step in range(steps):
        value = scale * math.exp(-step / max(steps, 1) * 3) + rng.random() * 0.01
        tracker.log_dynamic(key, value, step=step)


def new_experiment(
    store: Path, name: str, out: Path, series: list[tuple[str, int, int]]
) -> Path:
    if CACHE and out.exists():
        return out
    tracker = ExperimentTracker(f"sqlite://{store}")
    experiment_id = tracker.start_experiment(name=name, group="e2e")
    tracker.log_static("seed", series[0][2])
    for key, steps, seed in series:
        log_series(tracker, key, steps, seed)
    tracker.end_experiment()
    tracker.export(str(out), experiment_id)
    return out


def old_experiment(work: Path) -> tuple[Path, str]:
    """Generation 1 by released luml-sdk 0.5.0 when its venv is there, else frozen."""
    python = os.environ.get("E2E_OLD_SDK_PYTHON")
    out = work / "old_sdk_0_5_0.tar"
    if CACHE and out.exists():
        return out, "luml-sdk 0.5.0"
    if python and Path(python).exists():
        subprocess.run(
            [python, "-I", str(OLD_SDK_SCRIPT), str(work / "old-store"), str(out)],
            check=True,
        )
        return out, "luml-sdk 0.5.0"
    return (
        FIXTURES / "l_gen1_twin.tar",
        "frozen l_gen1_twin.tar (no luml-sdk 0.5.0 venv)",
    )


def fallback_experiment(work: Path) -> Path | None:
    """Legacy rows stored by luml-sdk 0.5.0, exported by this SDK (old format kept)."""
    python = os.environ.get("E2E_OLD_SDK_PYTHON")
    if not (python and Path(python).exists()):
        return None
    out = work / "fallback.tar"
    if CACHE and out.exists():
        return out
    store = work / "fallback-store"
    shutil.rmtree(store, ignore_errors=True)
    subprocess.run(
        [python, "-I", str(OLD_SDK_SCRIPT), "legacy", str(store)], check=True
    )
    ExperimentTracker(f"sqlite://{store}").export(str(out), "fallback")
    shutil.rmtree(store)
    return out


def snapshot_member(tar_path: Path) -> tuple[str, int, int]:
    with tarfile.open(tar_path) as archive:
        for member in archive.getmembers():
            name = member.name
            if name in ("exp.db", "exp.db.zip") or (
                "experiment_snapshot" in name
                and name.rsplit("/", 1)[-1] in ("exp.db", "exp.db.zip")
            ):
                return name, member.offset_data, member.size
    raise ValueError(f"{tar_path} has no snapshot member")


def build_artifacts(work: Path) -> tuple[dict[str, tuple[Path, str]], str]:
    store = work / "store"
    artifacts = {
        "large": (
            new_experiment(
                store,
                "large",
                work / "large.tar",
                [
                    (key, LARGE_POINTS_PER_KEY, 11 + index)
                    for index, key in enumerate(LARGE_KEYS)
                ],
            ),
            "experiment",
        ),
        "new_a": (
            new_experiment(
                store, "new_a", work / "new_a.tar", [("train/loss", REGULAR_STEPS, 21)]
            ),
            "experiment",
        ),
        "new_b": (
            new_experiment(
                store, "new_b", work / "new_b.tar", [("train/loss", REGULAR_STEPS, 22)]
            ),
            "experiment",
        ),
        "short": (
            new_experiment(
                store, "short", work / "short.tar", [("train/loss", SHORT_STEPS, 23)]
            ),
            "experiment",
        ),
        "gen2_full": (FIXTURES / "i_gen2_sdk_0_6_0.tar", "experiment"),
        "twin_gen1": (FIXTURES / "l_gen1_twin.tar", "experiment"),
        "twin_gen2": (FIXTURES / "m_gen2_twin.tar", "experiment"),
        "model_gen2": (FIXTURES / "j_gen2_model_sdk_0_6_0.tar", "model"),
        "model_gen1": (FIXTURES / "f_model_sdk_0_5_0.tar", "model"),
    }
    fallback = fallback_experiment(work)
    if fallback:
        artifacts["fallback"] = (fallback, "experiment")
    old_path, old_source = old_experiment(work)
    artifacts["old"] = (old_path, "experiment")
    large_size = artifacts["large"][0].stat().st_size
    if large_size > 150 * 1024 * 1024:
        sys.exit(f"large artifact is {large_size} bytes, above the 150 MB budget")
    return artifacts, old_source


def bucket_secret(client: LumlClient, storage: str) -> str:
    if storage == "s3":
        secret = client.bucket_secrets.create(
            type=BucketType.S3,
            endpoint=f"127.0.0.1:{env('E2E_MINIO_PORT')}",
            bucket_name="e2e-snapshots",
            access_key="e2euser",
            secret_key="e2e-secret-key-1",
            region="us-east-1",
            secure=False,
            cert_check=False,
        )
    else:
        secret = client.bucket_secrets.create(
            type=BucketType.AZURE,
            endpoint=env("E2E_AZURE_CONNECTION_STRING"),
            bucket_name=env("E2E_AZURE_CONTAINER"),
            region="",
        )
    return secret.id


def publish(
    client: LumlClient, storage: str, artifacts: dict[str, tuple[Path, str]]
) -> dict[str, Any]:
    secret_id = bucket_secret(client, storage)
    orbit = client.orbits.create(name=f"e2e {storage}", bucket_secret_id=secret_id)
    client.orbit = orbit.id
    collection = client.collections.create(
        name=f"snapshots {storage}", description="e2e", type=CollectionType.MIXED
    )
    published: dict[str, Published] = {}
    for label, (path, kind) in artifacts.items():
        artifact = client.artifacts.upload(
            str(path), name=label, collection_id=collection.id
        )
        if artifact.status != ArtifactStatus.UPLOADED:
            sys.exit(f"{label}: upload ended with status {artifact.status}")
        member, offset, size = snapshot_member(path)
        indexed = artifact.file_index[member]
        if (int(indexed[0]), int(indexed[1])) != (offset, size):
            sys.exit(
                f"{label}: file_index {indexed} differs from the tar ({offset}, {size})"
            )
        published[label] = Published(
            id=artifact.id,
            name=label,
            kind=kind,
            generation=1 if member.endswith(".zip") else 2,
            member=member,
            offset=offset,
            size=size,
            file_size=path.stat().st_size,
            bucket_location=artifact.bucket_location,
        )
    return {
        "bucket_secret_id": secret_id,
        "orbit_id": orbit.id,
        "collection_id": collection.id,
        "artifacts": {label: asdict(item) for label, item in published.items()},
    }


def main() -> None:
    work = Path(env("E2E_WORK_DIR"))
    base_url = env("E2E_BACKEND_URL")
    storages = os.environ.get("E2E_STORAGES", "s3,azure").split(",")
    key = api_key(base_url)
    artifacts, old_source = build_artifacts(Path(CACHE) if CACHE else work)
    client = LumlClient(base_url=base_url, api_key=key)
    result = {
        # A throwaway key of the disposable stack; rotate_s3_key.py uses it.
        "api_key": key,
        "organization_id": client.organization,
        "old_source": old_source,
        "large": {"keys": list(LARGE_KEYS), "points_per_key": LARGE_POINTS_PER_KEY},
        "regular_steps": REGULAR_STEPS,
        "short_steps": SHORT_STEPS,
        "twin_key": TWIN_KEY,
        "storages": {
            storage: publish(client, storage, artifacts) for storage in storages
        },
    }
    (work / "platform.json").write_text(json.dumps(result, indent=2))
    for path, _ in artifacts.values():
        if path.is_relative_to(work):
            path.unlink()
    sys.stdout.write(
        f"published to {', '.join(storages)}; old-format source: {old_source}\n"
    )


if __name__ == "__main__":
    main()
