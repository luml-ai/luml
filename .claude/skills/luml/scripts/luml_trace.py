"""Log every HTTP request the LUML SDK makes, to the console and optionally to a file.

`luml_api` builds its `httpx.Client` internally and offers no hook, and uploads
and downloads go through module-level `httpx.put` / `httpx.stream` calls and
their own short-lived clients. So this patches `httpx.Client.send` and
`httpx.AsyncClient.send` instead: one switch covers the API calls, the
constructor's own validation calls, and the presigned bucket traffic.

Usage:

    from luml_trace import trace

    with trace("requests.jsonl"):
        luml = LumlClient()          # its validation calls are captured too
        luml.artifacts.list()

or, to keep it on for a whole script:

    import luml_trace; luml_trace.start()

Bearer tokens and the signature parameters of presigned URLs are redacted.
"""

from __future__ import annotations

import contextlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

_REDACTED = "<redacted>"
_SECRET_HEADERS = {"authorization", "x-api-key", "x-amz-security-token"}
_SECRET_PARAMS = {"X-Amz-Signature", "X-Amz-Credential", "sig", "signature"}

_original_send: Any = None
_original_async_send: Any = None
_state: dict[str, Any] = {"seq": 0, "fh": None, "bodies": True, "max_body": 2000}


def _safe_url(url: httpx.URL) -> str:
    params = url.params
    for key in _SECRET_PARAMS:
        if key in params:
            params = params.set(key, _REDACTED)
    return str(url.copy_with(query=str(params).encode() or None))


def _safe_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        k: (_REDACTED if k.lower() in _SECRET_HEADERS else v) for k, v in headers.items()
    }


def _body(raw: bytes | None) -> Any:
    if not _state["bodies"] or not raw:
        return None
    limit = _state["max_body"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"<{len(raw)} bytes of binary>"
    if len(text) > limit:
        text = text[:limit] + f"... <truncated, {len(text)} chars total>"
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(text)
    return text


def _request_body(request: httpx.Request) -> Any:
    # A streamed upload has no readable .content; do not consume the stream.
    try:
        raw = request.content
    except (httpx.StreamConsumed, RuntimeError):
        return "<streamed>"
    return _body(raw)


def _response_body(response: httpx.Response) -> Any:
    if not response.is_closed:
        return "<streamed>"
    return _body(response.content)


def _record(request: httpx.Request, response: httpx.Response | None,
            elapsed_ms: float, error: BaseException | None) -> None:
    _state["seq"] += 1
    entry = {
        "seq": _state["seq"],
        "method": request.method,
        "url": _safe_url(request.url),
        "request_headers": _safe_headers(request.headers),
        "request_body": _request_body(request),
        "status": response.status_code if response is not None else None,
        "response_body": _response_body(response) if response is not None else None,
        "elapsed_ms": round(elapsed_ms, 1),
        "error": repr(error) if error is not None else None,
    }

    status = entry["status"] if error is None else f"ERR {type(error).__name__}"
    print(
        f"[luml {entry['seq']:>3}] {request.method:<6} {entry['url']} "
        f"-> {status} ({entry['elapsed_ms']}ms)",
        file=sys.stderr,
    )
    if error is not None or (response is not None and response.status_code >= 400):
        print(f"          request : {json.dumps(entry['request_body'], default=str)}",
              file=sys.stderr)
        print(f"          response: {json.dumps(entry['response_body'], default=str)}",
              file=sys.stderr)

    fh = _state["fh"]
    if fh is not None:
        fh.write(json.dumps(entry, default=str) + "\n")
        fh.flush()


def start(path: str | Path | None = None, *, bodies: bool = True,
          max_body: int = 2000) -> None:
    """Begin logging. `path` also writes one JSON object per request to that file."""
    global _original_send, _original_async_send
    if _original_send is not None:
        return

    _state.update(seq=0, bodies=bodies, max_body=max_body)
    _state["fh"] = open(path, "w") if path is not None else None  # noqa: SIM115

    _original_send = httpx.Client.send
    _original_async_send = httpx.AsyncClient.send

    def send(self: httpx.Client, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        started = time.perf_counter()
        try:
            response = _original_send(self, request, **kwargs)
        except BaseException as exc:
            _record(request, None, (time.perf_counter() - started) * 1000, exc)
            raise
        _record(request, response, (time.perf_counter() - started) * 1000, None)
        return response

    async def async_send(self: httpx.AsyncClient, request: httpx.Request,
                         **kwargs: Any) -> httpx.Response:
        started = time.perf_counter()
        try:
            response = await _original_async_send(self, request, **kwargs)
        except BaseException as exc:
            _record(request, None, (time.perf_counter() - started) * 1000, exc)
            raise
        _record(request, response, (time.perf_counter() - started) * 1000, None)
        return response

    httpx.Client.send = send  # type: ignore[method-assign]
    httpx.AsyncClient.send = async_send  # type: ignore[method-assign]


def stop() -> None:
    """Restore httpx and close the log file."""
    global _original_send, _original_async_send
    if _original_send is None:
        return
    httpx.Client.send = _original_send  # type: ignore[method-assign]
    httpx.AsyncClient.send = _original_async_send  # type: ignore[method-assign]
    _original_send = None
    _original_async_send = None
    if _state["fh"] is not None:
        _state["fh"].close()
        _state["fh"] = None


@contextlib.contextmanager
def trace(path: str | Path | None = None, *, bodies: bool = True,
          max_body: int = 2000):
    """Context-manager form of `start()` / `stop()`."""
    start(path, bodies=bodies, max_body=max_body)
    try:
        yield
    finally:
        stop()
