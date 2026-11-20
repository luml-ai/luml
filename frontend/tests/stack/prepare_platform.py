"""Writes experiments with this worktree's SDK and publishes them with its API client.

Run by run.sh against the disposable stack. For each storage (MinIO through the S3
bucket secret, Azurite through the Azure one) it creates an orbit and a `mixed`
collection, uploads every scenario artifact into it, and writes the ids the browser
specs need to ``$E2E_WORK_DIR/platform.json``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tarfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx2
import platform_expected
import trace_data
from luml_api import LumlClient
from luml_api._types import ArtifactStatus, BucketType, CollectionType
from old_sdk import old_sdk_python

from luml.experiments.tracker import ExperimentTracker

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "sdk/python/sdk/tests/fixtures/experiment_snapshots"
OLD_SDK_SCRIPT = Path(__file__).with_name("old_sdk_experiment.py")

LARGE_POINTS_PER_KEY = 1_000_000
LARGE_KEYS = ("train/loss", "train/grad_norm", "val/accuracy")
REGULAR_STEPS = 3_000
SHORT_STEPS = 40
# Debugging only: generated artifacts are kept and reused there (deterministic), in a
# folder per content of the files that define them.
CACHE = os.environ.get("E2E_ARTIFACT_CACHE")
DATA_FILES = (Path(__file__), Path(__file__).with_name("trace_data.py"), OLD_SDK_SCRIPT)
TWIN_KEY = "train/long_running_metric/with_a_fairly_long_key_name"
# Published once more to each storage through its delaying proxy (throttle_proxy.mjs).
PROXIED_LABELS = {
    "s3": ("large", "old", "new_a", "new_b", "traces_new", "traces_old"),
    "azure": ("large",),
}
NEW_SERIES = {
    "new_a": [("train/loss", REGULAR_STEPS, 21)],
    "new_b": [("train/loss", REGULAR_STEPS, 22)],
}
# Frozen stores of the oldest eras, opened in the UI against their fixture JSON:
# revision 0 (before migrations, with and without the legacy indexes), the first
# release with migrations (luml-sdk 0.1.0, revision 2) and a revision 0 store that
# luml-sdk 0.5.0 migrated (revision 2 without the annotation tables). No fixture has
# revision 1.
OLD_ERA_FIXTURES = {
    "rev0": FIXTURES / "b_premigration.tar",
    "rev0_legacy_indexes": FIXTURES / "a_premigration_legacy_indexes.tar",
    "sdk_0_1_0": FIXTURES / "c_sdk_0_1_0.tar",
    "baseline_quirk": FIXTURES / "e_baseline_quirk.tar",
}


def fixture_kind(path: Path) -> str:
    """An experiment, or a model holding one (the fixture JSON says)."""
    kind = json.loads(path.with_suffix(".json").read_text())["artifact_kind"]
    if kind not in ("experiment", "model"):
        sys.exit(f"{path.name}: unknown artifact kind {kind}")
    return str(kind)


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
    # Where the 1 MiB and the 100 KiB span attribute values lie in the object
    # (traces_new only).
    payload_region: list[int] | None
    medium_region: list[int] | None


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"missing environment variable {name}")
    return value


def cache_dir(cache: str) -> Path:
    content = b"".join(path.read_bytes() for path in DATA_FILES)
    folder = Path(cache) / hashlib.sha256(content).hexdigest()[:16]
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def api_key(base_url: str) -> str:
    with httpx2.Client(base_url=base_url, timeout=30) as session:
        signed_in = session.post(
            "/v1/auth/signin",
            json={
                "email": env("DEV_ADMIN_EMAIL"),
                "password": env("DEV_ADMIN_PASSWORD"),
            },
        )
        signed_in.raise_for_status()
        # The auth cookie is Secure, which httpx2 does not send over http; browsers do
        # on loopback, so the platform works there. Sent by hand.
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


def recorder(
    series: list[tuple[str, int, int]],
) -> Callable[[platform_expected.RecordingTracker], None]:
    """What new_experiment logs, for platform_expected.py."""

    def log(tracker: platform_expected.RecordingTracker) -> None:
        tracker.log_static("seed", series[0][2])
        for key, steps, seed in series:
            log_series(tracker, key, steps, seed)  # type: ignore[arg-type]

    return log


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


def old_experiment(work: Path, python: str | None) -> tuple[Path, str]:
    """Generation 1 by released luml-sdk 0.5.0 when its venv is there, else frozen."""
    out = work / "old_sdk_0_5_0.tar"
    if CACHE and out.exists():
        return out, "luml-sdk 0.5.0"
    if python:
        subprocess.run(
            [python, "-I", str(OLD_SDK_SCRIPT), str(work / "old-store"), str(out)],
            check=True,
        )
        return out, "luml-sdk 0.5.0"
    return (
        FIXTURES / "l_gen1_twin.tar",
        "frozen l_gen1_twin.tar (no luml-sdk 0.5.0 venv)",
    )


def fallback_experiment(work: Path, python: str | None) -> Path | None:
    """Legacy rows stored by luml-sdk 0.5.0, exported by this SDK (old format kept)."""
    if not python:
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


def trace_experiments(work: Path, python: str | None) -> dict[str, Path]:
    """The same traces and evals (trace_data.py) by this SDK and by luml-sdk 0.5.0."""
    started = time.monotonic()
    outputs = {"traces_new": work / "traces_new.tar"}
    if not (CACHE and outputs["traces_new"].exists()):
        store = work / "traces-store"
        shutil.rmtree(store, ignore_errors=True)
        tracker = ExperimentTracker(f"sqlite://{store}")
        experiment_id = tracker.start_experiment(name="traces_new", group="e2e")
        trace_data.log_all(tracker)
        tracker.end_experiment()
        tracker.export(str(outputs["traces_new"]), experiment_id)
        shutil.rmtree(store)
    if python:
        outputs["traces_old"] = work / "traces_old.tar"
        if not (CACHE and outputs["traces_old"].exists()):
            store = work / "traces-old-store"
            shutil.rmtree(store, ignore_errors=True)
            subprocess.run(
                [
                    python,
                    "-I",
                    str(OLD_SDK_SCRIPT),
                    "traces",
                    str(store),
                    str(outputs["traces_old"]),
                ],
                check=True,
            )
            shutil.rmtree(store)
    sys.stdout.write(
        f"trace experiments written in {time.monotonic() - started:.1f}s\n"
    )
    return outputs


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


def payload_region(
    tar_path: Path, offset: int, size: int, key: str, chars: int
) -> list[int]:
    """The object byte range [first, last] of a large attribute value of trace_data.py
    in a generation 2 member: the consecutive overflow pages that end with it.

    The value starts in its row's cell and goes on in a chain of overflow pages, each a
    4-byte link and then the value's next bytes. The chain of the 1 MiB value follows
    its cell; the 100 KiB value's cell is on an earlier page, so its range starts at the
    first page of the chain, the most of the value.
    """
    with tar_path.open("rb") as handle:
        handle.seek(offset)
        database = handle.read(size)
    begin = trace_data.begin_marker(key).encode()
    end = trace_data.end_marker(key).encode()
    first, last = database.find(begin), database.rfind(end) + len(end) - 1
    if first < 0 or database.rfind(begin) != first:
        sys.exit(f"{tar_path.name}: the {key} value is missing")
    # The page size is the header's 2 bytes at offset 16; 1 stands for 65536.
    page_size = int.from_bytes(database[16:18], "big")
    page_size = 65536 if page_size == 1 else page_size
    text = trace_data.payload_text(key, chars).encode()
    chain = last - last % page_size
    while chain > first and database[chain - page_size + 4 : chain] in text:
        chain -= page_size
    if first < chain - page_size:
        first = chain + 4
    length = last - first + 1
    if not chars * 0.9 <= length <= chars * 1.02:
        sys.exit(f"{tar_path.name}: the {key} value is not in one chain of pages")
    return [offset + first, offset + last]


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
            new_experiment(store, "new_a", work / "new_a.tar", NEW_SERIES["new_a"]),
            "experiment",
        ),
        "new_b": (
            new_experiment(store, "new_b", work / "new_b.tar", NEW_SERIES["new_b"]),
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
        **{
            label: (path, fixture_kind(path))
            for label, path in OLD_ERA_FIXTURES.items()
        },
    }
    python = old_sdk_python(
        "the old-format experiment is the frozen l_gen1_twin.tar, and the tests of "
        "the fallback and traces_old experiments are skipped"
    )
    fallback = fallback_experiment(work, python)
    if fallback:
        artifacts["fallback"] = (fallback, "experiment")
    old_path, old_source = old_experiment(work, python)
    artifacts["old"] = (old_path, "experiment")
    for label, path in trace_experiments(work, python).items():
        artifacts[label] = (path, "experiment")
    large_size = artifacts["large"][0].stat().st_size
    if large_size > 150 * 1024 * 1024:
        sys.exit(f"large artifact is {large_size} bytes, above the 150 MB budget")
    return artifacts, old_source


def bucket_secret(client: LumlClient, storage: str, proxied: bool) -> str:
    if storage == "s3":
        port = env("E2E_MINIO_PROXY_PORT" if proxied else "E2E_MINIO_PORT")
        secret = client.bucket_secrets.create(
            type=BucketType.S3,
            endpoint=f"127.0.0.1:{port}",
            bucket_name="e2e-snapshots",
            access_key="e2eproxied" if proxied else "e2euser",
            secret_key="e2e-proxied-key" if proxied else "e2e-secret-key-1",
            region="us-east-1",
            secure=False,
            cert_check=False,
        )
    else:
        secret = client.bucket_secrets.create(
            type=BucketType.AZURE,
            endpoint=env(
                "E2E_AZURE_PROXIED_CONNECTION_STRING"
                if proxied
                else "E2E_AZURE_CONNECTION_STRING"
            ),
            bucket_name=env(
                "E2E_AZURE_PROXIED_CONTAINER" if proxied else "E2E_AZURE_CONTAINER"
            ),
            region="",
        )
    return secret.id


def publish(
    client: LumlClient,
    storage: str,
    artifacts: dict[str, tuple[Path, str]],
    proxied: bool = False,
) -> dict[str, Any]:
    secret_id = bucket_secret(client, storage, proxied)
    name = f"{storage} proxied" if proxied else storage
    orbit = client.orbits.create(name=f"e2e {name}", bucket_secret_id=secret_id)
    client.orbit = orbit.id
    collection = client.collections.create(
        name=f"snapshots {name}", description="e2e", type=CollectionType.MIXED
    )
    published: dict[str, Published] = {}
    for label, (path, kind) in artifacts.items():
        artifact = client.artifacts.upload(
            str(path), name=label, collection_id=collection.id
        )
        if artifact.status != ArtifactStatus.UPLOADED:
            sys.exit(f"{label}: upload ended with status {artifact.status}")
        member, offset, size = snapshot_member(path)
        traces = label == "traces_new"
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
            payload_region=payload_region(
                path, offset, size, trace_data.LARGE_KEY, trace_data.LARGE_CHARS
            )
            if traces
            else None,
            medium_region=payload_region(
                path, offset, size, trace_data.MEDIUM_KEY, trace_data.MEDIUM_CHARS
            )
            if traces
            else None,
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
    artifacts, old_source = build_artifacts(cache_dir(CACHE) if CACHE else work)
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
        "traces": trace_data.expected(),
        "expected": platform_expected.expected(
            {label: recorder(series) for label, series in NEW_SERIES.items()},
            OLD_ERA_FIXTURES,
        ),
        "storages": {
            storage: publish(client, storage, artifacts) for storage in storages
        },
        "proxied": {
            storage: publish(
                client,
                storage,
                {
                    label: artifacts[label]
                    for label in PROXIED_LABELS[storage]
                    # traces_old needs the luml-sdk 0.5.0 venv.
                    if label in artifacts
                },
                proxied=True,
            )
            for storage in storages
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
