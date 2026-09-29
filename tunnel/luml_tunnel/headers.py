from luml_tunnel.frames import Headers

TOKEN_HEADER = "x-luml-tunnel-token"
USER_HEADER = "x-luml-tunnel-user"

_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


def without_hop_by_hop(headers: Headers, keep: frozenset[str] = frozenset()) -> Headers:
    """Drop headers that describe one connection, including those named in `Connection`."""
    named_by_connection = {
        token.strip().lower()
        for name, value in headers
        if name.lower() == "connection"
        for token in value.split(",")
    }
    dropped = (_HOP_BY_HOP | named_by_connection) - keep
    return [(name, value) for name, value in headers if name.lower() not in dropped]


def has_body(headers: Headers) -> bool:
    return any(name.lower() in ("content-length", "transfer-encoding") for name, _ in headers)


def header_value(headers: Headers, name: str) -> str | None:
    return next((value for key, value in headers if key.lower() == name), None)


def decode_raw_headers(raw: list[tuple[bytes, bytes]]) -> Headers:
    return [(name.decode("latin-1"), value.decode("latin-1")) for name, value in raw]


def encode_raw_headers(headers: Headers) -> list[tuple[bytes, bytes]]:
    return [(name.encode("latin-1"), value.encode("latin-1")) for name, value in headers]
