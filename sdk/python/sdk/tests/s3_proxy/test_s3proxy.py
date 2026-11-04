import http.client
import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from luml.s3_proxy.s3proxy import MultipartUpload, S3ProxyHandler, S3ProxyServer

AUTH_HEADER = {
    "Authorization": (
        "AWS4-HMAC-SHA256 "
        "Credential=test/20261031/us-east-1/s3/aws4_request, "
        "SignedHeaders=host, Signature=test"
    )
}
ESCAPING_KEY_PATH = "/test-bucket/..%2F..%2Fcanary.txt"


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    root = tmp_path / "s3_storage"
    root.mkdir()
    return root


@pytest.fixture
def server(storage_root: Path) -> Generator[S3ProxyServer, None, None]:
    proxy = S3ProxyServer(
        ("127.0.0.1", 0),
        S3ProxyHandler,
        storage_root=str(storage_root),
        credentials={},
        cors_enabled=False,
        debug=False,
    )
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    try:
        yield proxy
    finally:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=2)


def _request(
    server: S3ProxyServer, method: str, path: str, body: bytes | None = None
) -> tuple[http.client.HTTPResponse, bytes]:
    host, port = server.server_address[:2]
    headers = dict(AUTH_HEADER)
    if body is not None:
        headers["Content-Length"] = str(len(body))
    conn = http.client.HTTPConnection(str(host), port)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp, resp.read()
    finally:
        conn.close()


def _handler(storage_root: Path) -> S3ProxyHandler:
    handler = S3ProxyHandler.__new__(S3ProxyHandler)
    handler.storage_root = str(storage_root)
    return handler


def _assert_invalid_argument(resp: http.client.HTTPResponse, body: bytes) -> None:
    text = body.decode("utf-8")
    assert resp.status == 400
    assert "<Code>InvalidArgument</Code>" in text
    assert "<Message>Invalid bucket or key path.</Message>" in text


class TestS3Proxy:
    def test_get_file_path_valid(self, storage_root: Path) -> None:
        expected = (storage_root / "mybucket" / "data" / "file.txt").resolve()
        assert _handler(storage_root).get_file_path("mybucket", "data/file.txt") == (
            expected
        )

    @pytest.mark.parametrize(
        ("bucket", "key"),
        [
            ("mybucket", "../../canary.txt"),
            ("..", "canary.txt"),
            ("mybucket", ".."),
            ("mybucket", "data/.."),
            ("mybucket", "../otherbucket/file.txt"),
            (".", "file.txt"),
        ],
    )
    def test_get_file_path_traversal_raises(
        self, storage_root: Path, bucket: str, key: str
    ) -> None:
        with pytest.raises(ValueError, match="Invalid bucket or key path."):
            _handler(storage_root).get_file_path(bucket, key)

    def test_get_escaping_path_returns_400(self, server: S3ProxyServer) -> None:
        _assert_invalid_argument(*_request(server, "GET", ESCAPING_KEY_PATH))

    def test_get_bucket_root_path_returns_400(self, server: S3ProxyServer) -> None:
        _assert_invalid_argument(*_request(server, "GET", "/mybucket/data%2F.."))

    def test_get_directory_key_returns_404(
        self, server: S3ProxyServer, storage_root: Path
    ) -> None:
        (storage_root / "mybucket" / "data").mkdir(parents=True)
        resp, body = _request(server, "GET", "/mybucket/data")
        assert resp.status == 404
        assert "<Code>NoSuchKey</Code>" in body.decode("utf-8")

    def test_put_escaping_path_returns_400(self, server: S3ProxyServer) -> None:
        _assert_invalid_argument(*_request(server, "PUT", ESCAPING_KEY_PATH, b"test"))

    def test_delete_escaping_path_returns_400(self, server: S3ProxyServer) -> None:
        _assert_invalid_argument(*_request(server, "DELETE", ESCAPING_KEY_PATH))

    def test_initiate_multipart_escaping_path_returns_400(
        self, server: S3ProxyServer
    ) -> None:
        resp, body = _request(server, "POST", f"{ESCAPING_KEY_PATH}?uploads")
        _assert_invalid_argument(resp, body)
        assert server.multipart_uploads == {}

    def test_complete_multipart_escaping_path_returns_400(
        self, server: S3ProxyServer
    ) -> None:
        upload_id = "test_upload_id"
        server.multipart_uploads[upload_id] = MultipartUpload(
            bucket="test-bucket", key="../../canary.txt"
        )
        _assert_invalid_argument(
            *_request(server, "POST", f"{ESCAPING_KEY_PATH}?uploadId={upload_id}", b"")
        )

    def test_valid_crud_flow(self, server: S3ProxyServer, storage_root: Path) -> None:
        content = b"hello s3 proxy"
        stored = storage_root / "mybucket" / "hello.txt"

        put_resp, _ = _request(server, "PUT", "/mybucket/hello.txt", content)
        assert put_resp.status == 200
        assert "ETag" in put_resp.headers
        assert stored.read_bytes() == content

        get_resp, get_body = _request(server, "GET", "/mybucket/hello.txt")
        assert get_resp.status == 200
        assert get_body == content

        del_resp, _ = _request(server, "DELETE", "/mybucket/hello.txt")
        assert del_resp.status == 204
        assert not stored.exists()
