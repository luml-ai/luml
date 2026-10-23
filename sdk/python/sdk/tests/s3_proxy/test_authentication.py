from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta, tzinfo
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from unittest.mock import Mock

import pytest

from luml.s3_proxy import (
    __main__ as cli,
    s3_signature_validator as signatures,
    s3proxy,
)
from luml.s3_proxy.s3_signature_validator import AwsSignatureValidator
from luml.s3_proxy.schemas import S3AuthError

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)
CREDENTIALS = {"test-access-key": "test-secret-key"}
# fixtures generated independently with botocore's s3 sigv4 signers
HEADER_SIGNATURES = {
    "GET": "221503752f2124f1fc50ad25204f188a9c6b7c0a5a95b1d9102fb71c194ddc2b",
    "PUT": "bfb8bff2a5187205ca52addab934b7a2ff3c5866f40afe6ac7035dec44abcb07",
    "DELETE": "28b24d0645e1b22dcaef2a1ca6ef95d61cf816bd4bee85f5a6a1ba8a06fa5f43",
}
PRESIGNED_SIGNATURES = {
    "GET": "9897b2945b343063ef206c12b139efa1263604ce2644e84782816c484d4e23b4",
    "PUT": "95fd24ea7c4b1e4df153267e5cc4f235712e4cffb2c14228b8314a3ab9006f69",
    "DELETE": "a67150b49021c1d72aac3540c1393f2e5a3e64678aff48ffc11386ad8f90ad91",
}
PRESIGNED_PATH = (
    "/bucket/object?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=test-access-key%2F20261021%2Fus-east-1%2Fs3%2Faws4_request"
    "&X-Amz-Date=20261021T120000Z&X-Amz-Expires=60&X-Amz-SignedHeaders=host"
    "&X-Amz-Signature="
)


@pytest.fixture(autouse=True)
def frozen_time(monkeypatch: pytest.MonkeyPatch) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return NOW

    monkeypatch.setattr(signatures, "datetime", FrozenDateTime)


@pytest.fixture
def validator() -> AwsSignatureValidator:
    return AwsSignatureValidator(CREDENTIALS)


def signed_headers(method: str = "GET") -> dict[str, str]:
    payload_hash = (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        if method == "PUT"
        else "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    return {
        "Host": "localhost:9000",
        "X-Amz-Date": "20261021T120000Z",
        "X-Amz-Content-SHA256": payload_hash,
        "Authorization": (
            "AWS4-HMAC-SHA256 Credential=test-access-key/20261021/us-east-1/"
            "s3/aws4_request, SignedHeaders=host;x-amz-content-sha256;x-amz-date, "
            f"Signature={HEADER_SIGNATURES[method]}"
        ),
    }


@pytest.mark.parametrize(
    "credentials", [None, {}, {"": "value"}, {"key": ""}, {" ": "value"}, {"key": " "}]
)
def test_validator_requires_credentials(credentials: dict[str, str] | None) -> None:
    with pytest.raises(ValueError, match="credentials"):
        AwsSignatureValidator(credentials)


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0"])
def test_server_refuses_empty_credentials_before_binding(
    host: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bind = Mock()
    monkeypatch.setattr(s3proxy.HTTPServer, "__init__", bind)
    with pytest.raises(ValueError, match="credentials"):
        s3proxy.S3ProxyServer(
            (host, 0), s3proxy.S3ProxyHandler, str(tmp_path), {}, False, False
        )
    bind.assert_not_called()


@pytest.mark.parametrize("keys", [{}, {"access_key": "key"}, {"secret_key": "value"}])
def test_run_server_requires_both_keys(
    keys: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(s3proxy, "S3ProxyServer", Mock())
    with pytest.raises(ValueError, match="credentials"):
        s3proxy.run_server(**keys)


def test_cli_passes_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    run_server = Mock()
    monkeypatch.setattr(cli, "run_server", run_server)
    monkeypatch.setattr(
        "sys.argv",
        [
            "s3-proxy",
            "--access-key",
            "test-access-key",
            "--secret-key",
            "test-secret-key",
        ],
    )
    cli.main()
    assert run_server.call_args.kwargs["access_key"] == "test-access-key"
    assert run_server.call_args.kwargs["secret_key"] == "test-secret-key"


@pytest.mark.parametrize("case", [str.lower, str.upper, str.title])
def test_header_authentication_is_case_insensitive(
    validator: AwsSignatureValidator, case: Callable[[str], str]
) -> None:
    headers = {case(key): value for key, value in signed_headers().items()}
    assert (
        validator.validate_request(headers, "GET", "/bucket/object")
        == "test-access-key"
    )


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_valid_presigned_request(validator: AwsSignatureValidator, method: str) -> None:
    assert (
        validator.validate_request(
            {"HOST": "localhost:9000"},
            method,
            PRESIGNED_PATH + PRESIGNED_SIGNATURES[method],
        )
        == "test-access-key"
    )


@pytest.mark.parametrize(
    ("source", "replacement"),
    [
        ("X-Amz-Signature=", "X-Amz-Signature=deadbeef"),
        ("test-access-key", "unknown-key"),
        ("X-Amz-Date=20261021T120000Z", "X-Amz-Date=20200101"),
        ("X-Amz-Expires=60", "X-Amz-Expires=-1"),
        ("X-Amz-Expires=60", "X-Amz-Expires=invalid"),
        ("X-Amz-Algorithm=AWS4-HMAC-SHA256", "X-Amz-Algorithm=invalid"),
    ],
)
def test_invalid_presigned_request(
    validator: AwsSignatureValidator, source: str, replacement: str
) -> None:
    path = (PRESIGNED_PATH + PRESIGNED_SIGNATURES["GET"]).replace(source, replacement)
    with pytest.raises(S3AuthError) as error:
        validator.validate_request({"Host": "localhost:9000"}, "GET", path)
    assert error.value.status_code == 403


@pytest.mark.parametrize("age", [61, -901])
def test_presigned_expiration(
    validator: AwsSignatureValidator, monkeypatch: pytest.MonkeyPatch, age: int
) -> None:
    monkeypatch.setattr(__name__ + ".NOW", NOW + timedelta(seconds=age))
    with pytest.raises(S3AuthError):
        validator.validate_request(
            {"Host": "localhost:9000"},
            "GET",
            PRESIGNED_PATH + PRESIGNED_SIGNATURES["GET"],
        )


@pytest.mark.parametrize(
    "change", ["signature", "access_key", "method", "path", "host"]
)
def test_header_rejects_tampering(
    validator: AwsSignatureValidator, change: str
) -> None:
    headers = signed_headers()
    if change == "signature":
        headers["Authorization"] += "0"
    elif change == "access_key":
        headers["Authorization"] = headers["Authorization"].replace(
            "test-access-key", "unknown-key"
        )
    elif change == "host":
        headers["Host"] = "other-host"
    with pytest.raises(S3AuthError) as error:
        validator.validate_request(
            headers,
            "DELETE" if change == "method" else "GET",
            "/bucket/other" if change == "path" else "/bucket/object",
        )
    assert error.value.status_code == 403


@pytest.fixture
def server(tmp_path: Path) -> Iterator[s3proxy.S3ProxyServer]:
    with s3proxy.S3ProxyServer(
        ("127.0.0.1", 0),
        s3proxy.S3ProxyHandler,
        str(tmp_path),
        CREDENTIALS,
        False,
        False,
    ) as httpd:
        thread = Thread(target=httpd.serve_forever)
        thread.start()
        try:
            yield httpd
        finally:
            httpd.shutdown()
            thread.join()


@pytest.mark.parametrize("presigned", [False, True])
def test_authenticated_object_lifecycle(
    server: s3proxy.S3ProxyServer, presigned: bool
) -> None:
    connection = HTTPConnection(*server.server_address, timeout=5)
    for method, status in [("PUT", 200), ("GET", 200), ("DELETE", 204)]:
        path = "/bucket/object"
        headers = signed_headers(method)
        if presigned:
            path = PRESIGNED_PATH + PRESIGNED_SIGNATURES[method]
            headers = {"Host": "localhost:9000"}
        connection.request(method, path, b"hello" if method == "PUT" else None, headers)
        response = connection.getresponse()
        assert response.status == status
        body = response.read()
        if method == "GET":
            assert body == b"hello"
    connection.close()


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
@pytest.mark.parametrize(
    "authentication", ["missing", "bogus-header", "bogus-presigned"]
)
def test_http_rejects_unauthenticated_requests(
    server: s3proxy.S3ProxyServer, method: str, authentication: str
) -> None:
    connection = HTTPConnection(*server.server_address, timeout=5)
    path = "/bucket/object"
    headers = {"Host": "localhost:9000"}
    if authentication == "bogus-header":
        headers = signed_headers(method)
        headers["Authorization"] += "0"
    elif authentication == "bogus-presigned":
        path = PRESIGNED_PATH + "deadbeef"
    connection.request(method, path, b"hello" if method == "PUT" else None, headers)
    response = connection.getresponse()
    assert response.status == 403
    response.read()
    connection.close()
    assert not (Path(server.storage_root) / "bucket" / "object").exists()


@pytest.mark.parametrize("age", [-901, 901])
def test_header_rejects_expired_or_future_timestamp(
    validator: AwsSignatureValidator, monkeypatch: pytest.MonkeyPatch, age: int
) -> None:
    monkeypatch.setattr(__name__ + ".NOW", NOW + timedelta(seconds=age))
    with pytest.raises(S3AuthError) as error:
        validator.validate_request(signed_headers(), "GET", "/bucket/object")
    assert error.value.status_code == 403


@pytest.mark.parametrize("header", ["Host", "X-Amz-Date", "X-Amz-Content-SHA256"])
def test_header_rejects_missing_signed_header(
    validator: AwsSignatureValidator, header: str
) -> None:
    headers = signed_headers()
    del headers[header]
    with pytest.raises(S3AuthError):
        validator.validate_request(headers, "GET", "/bucket/object")


@pytest.mark.parametrize(
    "parameter",
    ["Algorithm", "Credential", "Date", "Expires", "SignedHeaders", "Signature"],
)
def test_presigned_rejects_duplicate_authentication_parameter(
    validator: AwsSignatureValidator, parameter: str
) -> None:
    path = PRESIGNED_PATH + PRESIGNED_SIGNATURES["GET"] + f"&X-Amz-{parameter}=other"
    with pytest.raises(S3AuthError):
        validator.validate_request({"Host": "localhost:9000"}, "GET", path)


def test_run_server_configures_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    server = Mock()
    monkeypatch.setattr(s3proxy, "S3ProxyServer", server)
    s3proxy.run_server(access_key="test-access-key", secret_key="test-secret-key")
    assert server.call_args.kwargs["credentials"] == CREDENTIALS
    server.return_value.serve_forever.assert_called_once_with()


@pytest.mark.parametrize(
    ("expires", "signature"),
    [
        (0, "b12e38f4a07dcf8c7554a72e5a876fdc20e789095ebde053621792220d71919e"),
        (604801, "a25fb07283edf1a7fa91a50dc9dbb86d9b1467d2d02f86a66ebd414b2f8e22bc"),
    ],
)
def test_presigned_rejects_signed_invalid_expiration(
    validator: AwsSignatureValidator, expires: int, signature: str
) -> None:
    path = PRESIGNED_PATH.replace("X-Amz-Expires=60&", f"X-Amz-Expires={expires}&")
    with pytest.raises(S3AuthError):
        validator.validate_request({"Host": "localhost:9000"}, "GET", path + signature)


def test_header_authentication_canonicalizes_query(
    validator: AwsSignatureValidator,
) -> None:
    headers = signed_headers()
    headers["Authorization"] = headers["Authorization"].replace(
        HEADER_SIGNATURES["GET"],
        "bace81e25086259c951f10ac22c6865c3eac5a5c5f04d143bad2c3aa846fce92",
    )
    assert (
        validator.validate_request(headers, "GET", "/bucket/object?z=last&a=first")
        == "test-access-key"
    )
