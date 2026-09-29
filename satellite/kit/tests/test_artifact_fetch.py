import io
import os
import tarfile
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import httpx
import pytest

from luml_satellite.artifact_fetch import (
    ArtifactFetchError,
    FetchConfiguration,
    fetch_artifact,
    main,
    sweep_cache,
)


def test_fetch_cache_hit_makes_no_http_request(tmp_path: Path) -> None:
    target = tmp_path / "artifact"
    target.mkdir()
    (target / "manifest.json").write_text("{}", encoding="utf-8")

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request to {request.url}")

    with httpx.Client(transport=httpx.MockTransport(unexpected_request)) as client:
        result = fetch_artifact(
            FetchConfiguration(
                "artifact",
                "https://store.example/artifact",
                cache_dir=tmp_path,
            ),
            client=client,
        )

    assert result == target


def test_fetch_replaces_an_empty_artifact_directory(tmp_path: Path) -> None:
    target = tmp_path / "artifact"
    target.mkdir()
    archive = _archive({"manifest.json": b"{}"})
    requests = 0

    def download(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=archive)

    with httpx.Client(transport=httpx.MockTransport(download)) as client:
        result = fetch_artifact(
            FetchConfiguration(
                "artifact",
                "https://store.example/artifact",
                cache_dir=tmp_path,
            ),
            client=client,
        )

    assert result == target
    assert (target / "manifest.json").is_file()
    assert requests == 1


def test_fetch_downloads_unpacks_and_leaves_no_partial_files(tmp_path: Path) -> None:
    archive = _archive({"manifest.json": b'{"name": "fixture"}', "model.bin": b"data"})

    def download(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://store.example/artifact"
        return httpx.Response(200, content=archive)

    with httpx.Client(transport=httpx.MockTransport(download)) as client:
        target = fetch_artifact(
            FetchConfiguration(
                artifact_id="artifact",
                download_url="https://store.example/artifact",
                cache_dir=tmp_path,
            ),
            client=client,
        )

    assert (target / "manifest.json").read_text(encoding="utf-8") == '{"name": "fixture"}'
    assert (target / "model.bin").read_bytes() == b"data"
    assert not list(tmp_path.glob(".*.partial"))


def test_concurrent_fetches_share_the_completed_artifact(tmp_path: Path) -> None:
    archive = _archive({"manifest.json": b"{}"})
    downloads_ready = Barrier(2)

    def download(request: httpx.Request) -> httpx.Response:
        downloads_ready.wait()
        return httpx.Response(200, content=archive)

    configuration = FetchConfiguration(
        artifact_id="artifact",
        download_url="https://store.example/artifact",
        cache_dir=tmp_path,
    )
    with httpx.Client(transport=httpx.MockTransport(download)) as client:

        def fetch() -> Path:
            return fetch_artifact(configuration, client=client)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: fetch(), range(2)))

    assert results == [tmp_path / "artifact", tmp_path / "artifact"]
    assert (tmp_path / "artifact" / "manifest.json").is_file()
    assert not list(tmp_path.glob(".*.partial"))


def test_fetch_refreshes_once_after_a_403_and_second_run_hits_cache(tmp_path: Path) -> None:
    archive = _archive({"manifest.json": b"{}"})
    requests: list[tuple[str, str | None]] = []

    def route(request: httpx.Request) -> httpx.Response:
        requests.append((str(request.url), request.headers.get("X-Artifact-Token")))
        if request.url == "https://store.example/expired":
            return httpx.Response(403)
        if request.url == "http://satellite/satellites/deployments/deployment/artifact":
            return httpx.Response(
                200,
                json={
                    "artifact_id": "artifact",
                    "url": "https://store.example/fresh",
                },
            )
        if request.url == "https://store.example/fresh":
            return httpx.Response(200, content=archive)
        raise AssertionError(f"unexpected request to {request.url}")

    configuration = FetchConfiguration(
        artifact_id="artifact",
        download_url="https://store.example/expired",
        cache_dir=tmp_path,
        satellite_address="http://satellite/",
        deployment_id="deployment",
        artifact_token="token",
    )
    with httpx.Client(transport=httpx.MockTransport(route)) as client:
        first = fetch_artifact(configuration, client=client)
        second = fetch_artifact(configuration, client=client)

    assert first == second == tmp_path / "artifact"
    assert requests == [
        ("https://store.example/expired", None),
        (
            "http://satellite/satellites/deployments/deployment/artifact",
            "token",
        ),
        ("https://store.example/fresh", None),
    ]
    assert not list(tmp_path.glob(".*.partial"))


def test_fetch_refreshes_an_already_expired_link_before_downloading(tmp_path: Path) -> None:
    archive = _archive({"manifest.json": b"{}"})
    requested: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "satellite":
            return httpx.Response(
                200,
                json={
                    "artifact_id": "artifact",
                    "url": "https://store.example/fresh",
                },
            )
        return httpx.Response(200, content=archive)

    expired = "https://store.example/expired?X-Amz-Date=20200101T000000Z&X-Amz-Expires=1"
    with httpx.Client(transport=httpx.MockTransport(route)) as client:
        fetch_artifact(
            FetchConfiguration(
                artifact_id="artifact",
                download_url=expired,
                cache_dir=tmp_path,
                satellite_address="http://satellite",
                deployment_id="deployment",
                artifact_token="token",
            ),
            client=client,
        )

    assert requested == [
        "http://satellite/satellites/deployments/deployment/artifact",
        "https://store.example/fresh",
    ]


def test_fetch_does_not_refresh_a_refused_fresh_link_twice(tmp_path: Path) -> None:
    refreshes = 0

    def route(request: httpx.Request) -> httpx.Response:
        nonlocal refreshes
        if request.url.host == "satellite":
            refreshes += 1
            return httpx.Response(
                200,
                json={
                    "artifact_id": "artifact",
                    "url": "https://store.example/still-refused",
                },
            )
        return httpx.Response(403)

    with (
        httpx.Client(transport=httpx.MockTransport(route)) as client,
        pytest.raises(ArtifactFetchError, match="refused"),
    ):
        fetch_artifact(
            FetchConfiguration(
                artifact_id="artifact",
                download_url="https://store.example/refused",
                cache_dir=tmp_path,
                satellite_address="http://satellite",
                deployment_id="deployment",
                artifact_token="token",
            ),
            client=client,
        )

    assert refreshes == 1
    assert list(tmp_path.iterdir()) == []


def test_sweep_keeps_only_named_artifacts_and_removes_partials(tmp_path: Path) -> None:
    keep = tmp_path / "keep"
    remove_one = tmp_path / "remove-one"
    remove_two = tmp_path / "remove-two"
    partial_file = tmp_path / ".artifact.1.partial"
    partial_directory = tmp_path / ".artifact.2.partial"
    for path in (keep, remove_one, remove_two, partial_directory):
        path.mkdir()
    partial_file.write_bytes(b"partial")
    now = datetime(2026, 9, 19, tzinfo=UTC)
    stale_time = (now - timedelta(hours=4)).timestamp()
    os.utime(partial_file, (stale_time, stale_time))
    os.utime(partial_directory, (stale_time, stale_time))

    removed = sweep_cache(tmp_path, {"keep"}, now=now)

    assert keep.is_dir()
    assert {path.name for path in removed} == {
        "remove-one",
        "remove-two",
        ".artifact.1.partial",
        ".artifact.2.partial",
    }
    assert {path.name for path in tmp_path.iterdir()} == {"keep"}


def test_sweep_leaves_an_active_partial_file(tmp_path: Path) -> None:
    now = datetime(2026, 9, 19, tzinfo=UTC)
    partial = tmp_path / ".artifact.active.partial"
    partial.write_bytes(b"downloading")
    active_time = (now - timedelta(minutes=1)).timestamp()
    os.utime(partial, (active_time, active_time))

    removed = sweep_cache(tmp_path, set(), now=now)

    assert removed == []
    assert partial.is_file()


def test_sweep_leaves_a_partial_directory_with_active_contents(tmp_path: Path) -> None:
    now = datetime(2026, 9, 19, tzinfo=UTC)
    partial = tmp_path / ".artifact.active.partial"
    partial.mkdir()
    active_file = partial / "model.bin"
    active_file.write_bytes(b"downloading")
    stale_time = (now - timedelta(hours=4)).timestamp()
    active_time = (now - timedelta(minutes=1)).timestamp()
    os.utime(partial, (stale_time, stale_time))
    os.utime(active_file, (active_time, active_time))

    removed = sweep_cache(tmp_path, set(), now=now)

    assert removed == []
    assert active_file.is_file()


def test_sweep_mode_reads_the_cache_and_keep_list_from_its_interface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("keep-from-argument", "keep-from-environment", "remove"):
        (tmp_path / name).mkdir()
    partial = tmp_path / ".artifact.stale.partial"
    partial.write_bytes(b"partial")
    os.utime(partial, (0, 0))
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_ARTIFACT_KEEP", "keep-from-environment")

    result = main(["--sweep", "--keep", "keep-from-argument"])

    assert result == 0
    assert {path.name for path in tmp_path.iterdir()} == {
        "keep-from-argument",
        "keep-from-environment",
    }


def test_fetch_configuration_reads_the_init_container_environment(tmp_path: Path) -> None:
    configuration = FetchConfiguration.from_environment(
        {
            "MODEL_ARTIFACT_ID": "artifact",
            "MODEL_ARTIFACT_URL": "https://store.example/artifact",
            "MODEL_CACHE_DIR": str(tmp_path),
            "SATELLITE_AGENT_URL": "http://satellite",
            "DEPLOYMENT_ID": "deployment",
            "MODEL_ARTIFACT_TOKEN": "token",
        }
    )

    assert configuration == FetchConfiguration(
        artifact_id="artifact",
        download_url="https://store.example/artifact",
        cache_dir=tmp_path,
        satellite_address="http://satellite",
        deployment_id="deployment",
        artifact_token="token",
    )


def test_failed_unpack_leaves_no_partial_files(tmp_path: Path) -> None:
    def invalid_archive(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not a tar archive")

    with (
        httpx.Client(transport=httpx.MockTransport(invalid_archive)) as client,
        pytest.raises(ArtifactFetchError, match="unpack failed"),
    ):
        fetch_artifact(
            FetchConfiguration(
                artifact_id="artifact",
                download_url="https://store.example/artifact",
                cache_dir=tmp_path,
            ),
            client=client,
        )

    assert list(tmp_path.iterdir()) == []


def test_fetch_configuration_rejects_partial_refresh_credentials(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be set together"):
        FetchConfiguration(
            artifact_id="artifact",
            download_url="https://store.example/artifact",
            cache_dir=tmp_path,
            satellite_address="http://satellite",
        )
    with pytest.raises(ValueError, match="single path component"):
        FetchConfiguration(
            artifact_id="../artifact",
            download_url="https://store.example/artifact",
            cache_dir=tmp_path,
        )


def _archive(files: Mapping[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()
