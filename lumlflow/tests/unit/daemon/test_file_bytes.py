import tarfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from luml.artifacts.dataset import save_tabular_dataset
from lumlflow.flow.daemon import web
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.stream import Streams

from tests.helpers.daemon_fixtures import SESSION_TOKEN

TOKEN = "file-preview-token"


@pytest.fixture
def http(tmp_path: Path) -> Iterator[TestClient]:
    streams = Streams()
    hub = Hub(streams=streams)
    app = web.build_app(
        hub,
        Api(hub, directory=tmp_path),
        streams,
        token=TOKEN,
        session_token=SESSION_TOKEN,
        static=tmp_path,
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture(params=["regular file", "archive member"])
def preview(
    request: pytest.FixtureRequest, tmp_path: Path
) -> tuple[str, dict[str, str]]:
    source = tmp_path / "series.csv"
    source.write_bytes(b"0123456789")
    if request.param == "archive member":
        archive = tmp_path / "dataset.luml"
        save_tabular_dataset(source, file_format="csv", output_path=str(archive))
        return web.FILE_ENTRY_PATH, {
            "path": str(archive),
            "name": "data/default/train/chunk_000.csv",
        }
    link = tmp_path / "latest.csv"
    link.symlink_to(source)
    return web.FILE_PATH, {"path": str(link)}


def test_file_bytes_require_the_workspace_token(http: TestClient, preview):
    route, params = preview
    assert http.get(route, params=params).status_code == 401
    assert http.get(route, params={**params, "token": "wrong"}).status_code == 401
    response = http.get(route, params=params, headers={web.TOKEN_HEADER: TOKEN})
    assert response.status_code == 200
    assert response.content == b"0123456789"
    assert response.headers["content-length"] == "10"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["content-type"].startswith("text/csv")


def test_ranges_are_relative_to_the_requested_file(http: TestClient, preview):
    route, params = preview
    for interval, content_range, expected in (
        ("2-5", "2-5", b"2345"),
        ("8-", "8-9", b"89"),
        ("-3", "7-9", b"789"),
        ("7-99", "7-9", b"789"),
    ):
        response = http.get(
            route,
            params={**params, "token": TOKEN},
            headers={"Range": f"bytes={interval}"},
        )
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes {content_range}/10"
        assert int(response.headers["content-length"]) == len(expected)
        assert response.content == expected
    refused = http.get(
        route, params={**params, "token": TOKEN}, headers={"Range": "bytes=10-"}
    )
    assert refused.status_code == 416
    assert refused.headers["content-range"] == "bytes */10"


def test_seek_near_the_end_of_a_large_video(http: TestClient, tmp_path: Path):
    video = tmp_path / "run.mp4"
    offset = 300 * 1024 * 1024
    with video.open("wb") as stream:
        stream.seek(offset)
        stream.write(b"frame")
    response = http.get(
        web.FILE_PATH,
        params={"path": str(video), "token": TOKEN},
        headers={"Range": f"bytes={offset}-"},
    )
    assert response.status_code == 206
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-length"] == "5"
    assert response.content == b"frame"


def test_file_bytes_reject_notebook_internals_and_relative_paths(
    http: TestClient, tmp_path: Path
):
    forbidden = tmp_path / "example.flow" / "test.txt"
    forbidden.parent.mkdir()
    forbidden.touch()
    for path in (str(forbidden), "relative.txt"):
        response = http.get(web.FILE_PATH, params={"path": path, "token": TOKEN})
        assert response.status_code == 400
        assert response.json()["error"]["kind"]
    missing = http.get(
        web.FILE_PATH, params={"path": str(tmp_path / "absent"), "token": TOKEN}
    )
    assert missing.status_code == 404


def test_html_previews_are_sandboxed(http: TestClient, tmp_path: Path):
    document = tmp_path / "report.html"
    document.write_text("<main>Report</main>")
    response = http.get(web.FILE_PATH, params={"path": str(document), "token": TOKEN})
    assert response.text == "<main>Report</main>"
    assert response.headers["content-type"].startswith("text/html")
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_only_regular_members_of_luml_archives_are_served(
    http: TestClient, tmp_path: Path
):
    source = tmp_path / "source.csv"
    source.write_text("x\n1\n")
    package = tmp_path / "package.luml"
    save_tabular_dataset(source, file_format="csv", output_path=str(package))
    with tarfile.open(package, "a") as archive:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = str(source)
        archive.addfile(link)
    for member in ("missing", "link"):
        response = http.get(
            web.FILE_ENTRY_PATH,
            params={"path": str(package), "name": member, "token": TOKEN},
        )
        assert response.status_code == 404
    for invalid in (source, tmp_path / "invalid.luml"):
        invalid.write_bytes(b"not an archive")
        response = http.get(
            web.FILE_ENTRY_PATH,
            params={"path": str(invalid), "name": "manifest.json", "token": TOKEN},
        )
        assert response.status_code == 400


def test_compressed_archive_is_rejected_without_inflating_payloads(
    tmp_path: Path, http: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import gzip
    import io

    package = tmp_path / "compressed.luml"
    member = tarfile.TarInfo("chunk")
    member.size = 2 * 1024 * 1024
    with tarfile.open(package, "w:gz") as archive:
        archive.addfile(member, io.BytesIO(bytes(member.size)))

    inflated = 0
    read = gzip._GzipReader.read

    def measured_read(*args, **kwargs):
        nonlocal inflated
        chunk = read(*args, **kwargs)
        inflated += len(chunk)
        return chunk

    monkeypatch.setattr(gzip._GzipReader, "read", measured_read)
    inspection = http.post(
        web.RPC_PATH,
        headers={web.TOKEN_HEADER: TOKEN},
        json={"method": "file.inspect", "params": {"path": str(package)}},
    )
    assert inspection.json()["result"]["kind"] == "unknown"
    assert inflated == 0
    response = http.get(
        web.FILE_ENTRY_PATH,
        params={"path": str(package), "name": member.name, "token": TOKEN},
        headers={"Range": "bytes=0-0"},
    )
    assert response.status_code == 400
    assert inflated == 0
