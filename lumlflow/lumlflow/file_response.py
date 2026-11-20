import contextlib
import mimetypes
import os
import re
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from starlette.types import Receive, Scope, Send

from lumlflow.flow.errors import FlowError


class _FileStream(StreamingResponse):
    """Keep the file and any containing tar open until the response ends."""

    def __init__(
        self,
        resources: contextlib.ExitStack,
        chunks: Iterator[bytes],
        *,
        status: int,
        headers: dict[str, str],
        media_type: str,
    ) -> None:
        super().__init__(
            chunks, status_code=status, headers=headers, media_type=media_type
        )
        self.resources = resources

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        with self.resources:
            await super().__call__(scope, receive, send)


def _chunks(source: IO[bytes], length: int) -> Iterator[bytes]:
    while length:
        chunk = source.read(min(length, 64 * 1024))
        if not chunk:
            break
        yield chunk
        length -= len(chunk)


def _byte_range(value: str, size: int) -> tuple[int, int]:
    """Return [start, stop) in the file, or raise for an unsatisfiable range."""
    match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", value, re.IGNORECASE)
    if not match or not any(match.groups()):
        raise ValueError
    first, last = match.groups()
    if first:
        start = int(first)
        stop = min(int(last) + 1, size) if last else size
    else:
        start = max(0, size - int(last))
        stop = size
    if start >= stop:
        raise ValueError
    return start, stop


def _open_bytes(
    resources: contextlib.ExitStack, path: Path, member: str | None
) -> tuple[IO[bytes], int, str]:
    if member is None:
        source = resources.enter_context(path.open("rb"))
        return source, os.fstat(source.fileno()).st_size, path.name
    if path.suffix.lower() != ".luml":
        raise FlowError("archive entries require a .luml file")
    archive = resources.enter_context(tarfile.open(path, "r:"))
    info = archive.getmember(member)
    if not info.isfile():
        raise KeyError(member)
    entry = archive.extractfile(info)
    assert entry is not None
    return resources.enter_context(entry), info.size, info.name


def file_bytes_response(
    request: Request, path: Path, member: str | None = None
) -> Response:
    with contextlib.ExitStack() as resources:
        source, size, name = _open_bytes(resources, path, member)
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        }
        media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        # HTML, SVG and other active documents opened directly have an
        # opaque origin and cannot run scripts under the daemon's origin.
        if media_type == "text/html" or media_type.endswith(("/xml", "+xml")):
            headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
        start, stop, status = 0, size, 200
        requested = request.headers.get("range")
        # Multiple ranges and conditional ranges without a validator
        # fall back to the complete representation.
        if (
            requested is not None
            and "," not in requested
            and "if-range" not in request.headers
        ):
            try:
                start, stop = _byte_range(requested, size)
            except ValueError:
                return Response(
                    status_code=416, headers={"Content-Range": f"bytes */{size}"}
                )
            source.seek(start)
            status = 206
            headers["Content-Range"] = f"bytes {start}-{stop - 1}/{size}"
        headers["Content-Length"] = str(stop - start)
        return _FileStream(
            resources.pop_all(),
            _chunks(source, stop - start),
            status=status,
            headers=headers,
            media_type=media_type,
        )
