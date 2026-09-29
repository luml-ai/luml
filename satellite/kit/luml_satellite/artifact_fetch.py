import argparse
import os
import shutil
import tarfile
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

from luml_satellite.workload import presigned_expiry

_DEFAULT_CACHE_DIR = Path("/app/models")
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_STALE_PARTIAL_AGE = timedelta(hours=3)


class ArtifactFetchError(RuntimeError):
    pass


class ArtifactLinkRefused(ArtifactFetchError):
    pass


@dataclass(frozen=True)
class FetchConfiguration:
    artifact_id: str
    download_url: str
    cache_dir: Path = _DEFAULT_CACHE_DIR
    satellite_address: str | None = None
    deployment_id: str | None = None
    artifact_token: str | None = None

    def __post_init__(self) -> None:
        _validate_cache_name(self.artifact_id, "artifact_id")
        if not self.download_url:
            raise ValueError("download_url must not be empty")
        refresh_values = (
            self.satellite_address,
            self.deployment_id,
            self.artifact_token,
        )
        if any(refresh_values) and not all(refresh_values):
            raise ValueError(
                "satellite_address, deployment_id and artifact_token must be set together"
            )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> FetchConfiguration:
        values = environment if environment is not None else os.environ
        return cls(
            artifact_id=_required_environment(values, "MODEL_ARTIFACT_ID"),
            download_url=_required_environment(values, "MODEL_ARTIFACT_URL"),
            cache_dir=Path(values.get("MODEL_CACHE_DIR", str(_DEFAULT_CACHE_DIR))),
            satellite_address=values.get("SATELLITE_AGENT_URL"),
            deployment_id=values.get("DEPLOYMENT_ID"),
            artifact_token=values.get("MODEL_ARTIFACT_TOKEN"),
        )


def fetch_artifact(
    configuration: FetchConfiguration,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> Path:
    target = configuration.cache_dir / configuration.artifact_id
    if _artifact_directory_ready(target):
        return target
    if target.exists() and not target.is_dir():
        raise ArtifactFetchError(f"artifact cache target is not a directory: {target}")

    configuration.cache_dir.mkdir(parents=True, exist_ok=True)
    owned_client = client is None
    active_client = client or httpx.Client(follow_redirects=True, trust_env=False)
    download_partial = _partial_path(configuration.cache_dir, configuration.artifact_id, "archive")
    staging = _partial_path(configuration.cache_dir, configuration.artifact_id, "staging")
    try:
        current_url = configuration.download_url
        expires_at = presigned_expiry(current_url)
        current_time = now or datetime.now(UTC)
        refreshed = False
        if expires_at is not None and expires_at <= current_time:
            current_url = _refresh_link(active_client, configuration)
            refreshed = True

        try:
            _download(active_client, current_url, download_partial)
        except ArtifactLinkRefused:
            if refreshed:
                raise
            current_url = _refresh_link(active_client, configuration)
            _download(active_client, current_url, download_partial)

        staging.mkdir()
        _extract_archive(download_partial, staging)
        try:
            staging.replace(target)
        except OSError:
            if not _artifact_directory_ready(target):
                raise
            shutil.rmtree(staging)
        return target
    except Exception:
        _remove_path(staging)
        raise
    finally:
        download_partial.unlink(missing_ok=True)
        if owned_client:
            active_client.close()


def sweep_cache(
    cache_dir: Path,
    keep_artifact_ids: Collection[str],
    *,
    now: datetime | None = None,
) -> list[Path]:
    keep = {_validate_cache_name(item, "keep artifact id") for item in keep_artifact_ids}
    if not cache_dir.exists():
        return []
    if not cache_dir.is_dir():
        raise ArtifactFetchError(f"artifact cache is not a directory: {cache_dir}")

    removed: list[Path] = []
    stale_before = (now or datetime.now(UTC)) - _STALE_PARTIAL_AGE
    for path in cache_dir.iterdir():
        is_partial = path.name.startswith(".") and path.name.endswith(".partial")
        if is_partial:
            modified_at = _latest_modified_at(path)
            if modified_at is None or modified_at > stale_before.timestamp():
                continue
        if not is_partial and path.name in keep:
            continue
        _remove_path(path)
        removed.append(path)
    return removed


def _artifact_directory_ready(path: Path) -> bool:
    try:
        return path.is_dir() and any(path.iterdir())
    except FileNotFoundError:
        return False


def _latest_modified_at(path: Path) -> float | None:
    try:
        if path.is_symlink():
            return path.lstat().st_mtime
        latest = path.stat().st_mtime
    except FileNotFoundError:
        return None
    if not path.is_dir():
        return latest
    for child in path.rglob("*"):
        try:
            latest = max(latest, child.stat().st_mtime)
        except FileNotFoundError:
            continue
    return latest


def _download(client: httpx.Client, url: str, destination: Path) -> None:
    try:
        with client.stream("GET", url) as response:
            if response.status_code == 403:
                raise ArtifactLinkRefused("artifact download link was refused")
            response.raise_for_status()
            with destination.open("xb") as output:
                for chunk in response.iter_bytes(_DOWNLOAD_CHUNK_SIZE):
                    output.write(chunk)
    except ArtifactLinkRefused:
        destination.unlink(missing_ok=True)
        raise
    except (httpx.HTTPError, OSError) as error:
        destination.unlink(missing_ok=True)
        raise ArtifactFetchError(f"artifact download failed: {error}") from error


def _refresh_link(client: httpx.Client, configuration: FetchConfiguration) -> str:
    if not (
        configuration.satellite_address
        and configuration.deployment_id
        and configuration.artifact_token
    ):
        raise ArtifactFetchError("artifact link cannot be refreshed")
    address = configuration.satellite_address.rstrip("/")
    url = f"{address}/satellites/deployments/{configuration.deployment_id}/artifact"
    try:
        response = client.get(
            url,
            headers={"X-Artifact-Token": configuration.artifact_token},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ArtifactFetchError(f"artifact link refresh failed: {error}") from error
    if not isinstance(payload, dict):
        raise ArtifactFetchError("artifact link refresh returned an invalid response")
    artifact_id = payload.get("artifact_id")
    download_url = payload.get("url")
    if artifact_id != configuration.artifact_id or not isinstance(download_url, str):
        raise ArtifactFetchError("artifact link refresh returned the wrong artifact")
    return download_url


def _extract_archive(archive: Path, staging: Path) -> None:
    try:
        with tarfile.open(archive, mode="r:*") as bundle:
            bundle.extractall(staging, filter="data")
    except (OSError, tarfile.TarError) as error:
        raise ArtifactFetchError(f"artifact unpack failed: {error}") from error


def _partial_path(cache_dir: Path, artifact_id: str, purpose: str) -> Path:
    return cache_dir / f".{artifact_id}.{os.getpid()}.{uuid4().hex}.{purpose}.partial"


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _validate_cache_name(value: str, description: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError(f"{description} must be a single path component")
    return value


def _required_environment(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch or sweep LUML model artifacts")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--keep", action="append", default=[])
    parsed = parser.parse_args(arguments)

    if parsed.sweep:
        configured = os.environ.get("MODEL_CACHE_DIR", str(_DEFAULT_CACHE_DIR))
        environment_keep = os.environ.get("MODEL_ARTIFACT_KEEP", "")
        keep = [*parsed.keep, *(item for item in environment_keep.split(",") if item)]
        sweep_cache(Path(configured), keep)
    else:
        fetch_artifact(FetchConfiguration.from_environment())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
