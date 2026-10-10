from luml_relay.frames import Headers

TOKEN_HEADER = "x-luml-relay-token"
USER_HEADER = "x-luml-relay-user"

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


def without_cookie(headers: Headers, cookie_name: str) -> Headers:
    """Remove one cookie from the `Cookie` headers, and a header left empty."""
    result: Headers = []
    for name, value in headers:
        if name.lower() == "cookie":
            kept = [
                pair.strip()
                for pair in value.split(";")
                if pair.strip() and pair.split("=", 1)[0].strip() != cookie_name
            ]
            if not kept:
                continue
            value = "; ".join(kept)
        result.append((name, value))
    return result


def cookie_value(headers: Headers, cookie_name: str) -> str | None:
    for name, value in headers:
        if name.lower() != "cookie":
            continue
        for pair in value.split(";"):
            key, separator, cookie = pair.partition("=")
            if separator and key.strip() == cookie_name:
                return cookie.strip()
    return None


def rewrite_response_headers(headers: Headers, app_origins: tuple[str, ...]) -> Headers:
    """Replace the service's framing restrictions with the relay's and keep cookies host-only.

    Framing is allowed for the LUML app's origins only, and forbidden when there are none.
    """
    result: Headers = []
    for name, value in headers:
        lowered = name.lower()
        if lowered == "x-frame-options":
            continue
        if lowered == "content-security-policy":
            value = _without_directive(value, "frame-ancestors")
            if not value:
                continue
        elif lowered == "set-cookie":
            value = _without_attribute(value, "domain")
        result.append((name, value))
    ancestors = " ".join(app_origins) or "'none'"
    result.append(("content-security-policy", f"frame-ancestors {ancestors}"))
    if not app_origins:
        result.append(("x-frame-options", "DENY"))
    return result


def _without_directive(policy: str, directive: str) -> str:
    kept = [
        part.strip()
        for part in policy.split(";")
        if part.strip() and part.split()[0].lower() != directive
    ]
    return "; ".join(kept)


def _without_attribute(set_cookie: str, attribute: str) -> str:
    cookie, *attributes = set_cookie.split(";")
    kept = [part for part in attributes if part.split("=", 1)[0].strip().lower() != attribute]
    return ";".join([cookie, *kept])
