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


@pytest.fixture
def proxy_server(tmp_path: Path) -> Generator[tuple[str, int, Path], None, None]:
    storage_root = tmp_path / "s3_storage"
    storage_root.mkdir()

    server = S3ProxyServer(
        ("127.0.0.1", 0),
        S3ProxyHandler,
        storage_root=str(storage_root),
        credentials={},
        cors_enabled=False,
        debug=False,
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address[:2]
    try:
        yield host, port, storage_root
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_get_file_path_valid(tmp_path: Path) -> None:
    handler = S3ProxyHandler.__new__(S3ProxyHandler)
    handler.storage_root = str(tmp_path)

    expected = (tmp_path / "mybucket" / "data" / "file.txt").resolve()
    assert handler.get_file_path("mybucket", "data/file.txt") == expected


def test_get_file_path_traversal_raises(tmp_path: Path) -> None:
    handler = S3ProxyHandler.__new__(S3ProxyHandler)
    handler.storage_root = str(tmp_path)

    with pytest.raises(ValueError, match="Invalid bucket or key path."):
        handler.get_file_path("mybucket", "../../canary.txt")

    with pytest.raises(ValueError, match="Invalid bucket or key path."):
        handler.get_file_path("..", "canary.txt")

    # Path resolving to storage_root itself
    with pytest.raises(ValueError, match="Invalid bucket or key path."):
        handler.get_file_path("mybucket", "..")


def test_get_escaping_path_returns_400_invalid_argument(
    proxy_server: tuple[str, int, Path],
) -> None:
    host, port, _ = proxy_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/test-bucket/..%2F..%2Fcanary.txt", headers=AUTH_HEADER)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()

    assert resp.status == 400
    assert "<Code>InvalidArgument</Code>" in body
    assert "<Message>Invalid bucket or key path.</Message>" in body


def test_put_escaping_path_returns_400_invalid_argument(
    proxy_server: tuple[str, int, Path],
) -> None:
    host, port, _ = proxy_server
    conn = http.client.HTTPConnection(host, port)
    headers = {**AUTH_HEADER, "Content-Length": "4"}
    conn.request(
        "PUT",
        "/test-bucket/..%2F..%2Fcanary.txt",
        body=b"test",
        headers=headers,
    )
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()

    assert resp.status == 400
    assert "<Code>InvalidArgument</Code>" in body
    assert "<Message>Invalid bucket or key path.</Message>" in body


def test_delete_escaping_path_returns_400_invalid_argument(
    proxy_server: tuple[str, int, Path],
) -> None:
    host, port, _ = proxy_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("DELETE", "/test-bucket/..%2F..%2Fcanary.txt", headers=AUTH_HEADER)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()

    assert resp.status == 400
    assert "<Code>InvalidArgument</Code>" in body
    assert "<Message>Invalid bucket or key path.</Message>" in body


def test_initiate_multipart_escaping_path_returns_400_invalid_argument(
    proxy_server: tuple[str, int, Path],
) -> None:
    host, port, _ = proxy_server
    conn = http.client.HTTPConnection(host, port)
    conn.request(
        "POST",
        "/test-bucket/..%2F..%2Fcanary.txt?uploads",
        headers=AUTH_HEADER,
    )
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()

    assert resp.status == 400
    assert "<Code>InvalidArgument</Code>" in body
    assert "<Message>Invalid bucket or key path.</Message>" in body


def test_complete_multipart_escaping_path_returns_400_invalid_argument(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "s3_storage"
    storage_root.mkdir()

    server = S3ProxyServer(
        ("127.0.0.1", 0),
        S3ProxyHandler,
        storage_root=str(storage_root),
        credentials={},
        cors_enabled=False,
        debug=False,
    )
    # Register an active multipart upload
    upload_id = "test_upload_id"
    server.multipart_uploads[upload_id] = MultipartUpload(
        bucket="test-bucket",
        key="../../canary.txt",
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address[:2]
    try:
        conn = http.client.HTTPConnection(host, port)
        headers = {**AUTH_HEADER, "Content-Length": "0"}
        conn.request(
            "POST",
            f"/test-bucket/..%2F..%2Fcanary.txt?uploadId={upload_id}",
            body=b"",
            headers=headers,
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()

        assert resp.status == 400
        assert "<Code>InvalidArgument</Code>" in body
        assert "<Message>Invalid bucket or key path.</Message>" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_valid_crud_flow(proxy_server: tuple[str, int, Path]) -> None:
    host, port, storage_root = proxy_server

    # 1. PUT an object
    conn = http.client.HTTPConnection(host, port)
    content = b"hello s3 proxy"
    headers = {**AUTH_HEADER, "Content-Length": str(len(content))}
    conn.request("PUT", "/mybucket/hello.txt", body=content, headers=headers)
    put_resp = conn.getresponse()
    assert put_resp.status == 200
    assert "ETag" in put_resp.headers
    conn.close()

    assert (storage_root / "mybucket" / "hello.txt").read_bytes() == content

    # 2. GET the object
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/mybucket/hello.txt", headers=AUTH_HEADER)
    get_resp = conn.getresponse()
    assert get_resp.status == 200
    assert get_resp.read() == content
    conn.close()

    # 3. DELETE the object
    conn = http.client.HTTPConnection(host, port)
    conn.request("DELETE", "/mybucket/hello.txt", headers=AUTH_HEADER)
    del_resp = conn.getresponse()
    assert del_resp.status == 204
    conn.close()

    assert not (storage_root / "mybucket" / "hello.txt").exists()
