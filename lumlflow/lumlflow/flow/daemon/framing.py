"""Shared bounds for line-delimited daemon transports."""

import asyncio

STREAM_LIMIT_BYTES = 16 * 1024 * 1024
STREAM_LIMIT_LABEL = "16 MiB"


async def discard_oversized_line(
    reader: asyncio.StreamReader, overrun: asyncio.LimitOverrunError
) -> None:
    """Consume through the newline without taking bytes from the next message."""
    current = overrun
    while True:
        try:
            if current.consumed:
                await reader.readexactly(current.consumed)
            await reader.readuntil()
            return
        except asyncio.LimitOverrunError as next_overrun:
            current = next_overrun
        except asyncio.IncompleteReadError:
            return
