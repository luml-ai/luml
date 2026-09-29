import json
import struct

import pytest

from luml_tunnel.frames import (
    Data,
    End,
    Frame,
    FrameDecodeError,
    FrameType,
    OpenHttp,
    OpenWebSocket,
    Reconnect,
    RelayLimits,
    RenewToken,
    Reset,
    ResponseHead,
    WebSocketClose,
    WebSocketMessage,
    WindowUpdate,
    decode_frame,
    encode_frame,
)

HEADERS = [("content-type", "text/plain"), ("set-cookie", "a=1"), ("set-cookie", "b=2")]

EVERY_FRAME: list[Frame] = [
    RelayLimits(
        max_concurrent_streams=7,
        max_request_body_bytes=1024,
        idle_timeout_seconds=12.5,
        stream_window_bytes=4096,
    ),
    RenewToken("header.payload.signature"),
    Reconnect(),
    OpenHttp(1, "POST", "/path/ü?q=1&q=2", HEADERS),
    OpenWebSocket(3, "/socket", [("sec-websocket-protocol", "chat")]),
    ResponseHead(1, 200, HEADERS),
    ResponseHead(3, 101, []),
    Data(1, b"\x00\xffbody"),
    Data(1, b""),
    End(1),
    WebSocketMessage(3, "text ✓"),
    WebSocketMessage(3, b"\x00binary"),
    WebSocketClose(3, 1000, "bye ✓"),
    WindowUpdate(1, 2**32 - 1),
    Reset(2**32 - 1, "service did not answer"),
]


def _raw(frame_type: int, stream_id: int, payload: bytes) -> bytes:
    return struct.pack(">BI", frame_type, stream_id) + payload


@pytest.mark.parametrize("frame", EVERY_FRAME, ids=lambda frame: type(frame).__name__)
def test_every_frame_survives_a_round_trip(frame: Frame) -> None:
    assert decode_frame(encode_frame(frame)) == frame


def test_text_and_binary_messages_stay_distinct() -> None:
    assert decode_frame(encode_frame(WebSocketMessage(1, "abc"))) != WebSocketMessage(1, b"abc")


def test_unknown_frame_type_decodes_to_none() -> None:
    assert decode_frame(_raw(0xEE, 1, b"anything")) is None


def test_unknown_json_keys_are_ignored() -> None:
    payload = json.dumps(
        {"method": "GET", "target": "/", "headers": [], "priority": "high"}
    ).encode()

    assert decode_frame(_raw(FrameType.OPEN_HTTP, 5, payload)) == OpenHttp(5, "GET", "/", [])


def test_limits_keep_defaults_for_missing_and_ignore_unknown_keys() -> None:
    payload = json.dumps({"stream_window_bytes": 10, "future_limit": 1}).encode()

    assert decode_frame(_raw(FrameType.LIMITS, 0, payload)) == RelayLimits(stream_window_bytes=10)


@pytest.mark.parametrize(
    "message",
    [
        b"\x13\x00",
        _raw(FrameType.OPEN_HTTP, 1, b"not json"),
        _raw(FrameType.OPEN_HTTP, 1, b"[]"),
        _raw(FrameType.OPEN_HTTP, 1, b'{"method": "GET", "target": "/"}'),
        _raw(FrameType.OPEN_HTTP, 1, b'{"method": "GET", "target": "/", "headers": [["a"]]}'),
        _raw(FrameType.OPEN_HTTP, 1, b'{"method": "GET", "target": "/", "headers": [["a", 1]]}'),
        _raw(FrameType.RESPONSE_HEAD, 1, b'{"status": "200", "headers": []}'),
        _raw(FrameType.RESPONSE_HEAD, 1, b'{"status": true, "headers": []}'),
        _raw(FrameType.LIMITS, 0, b'{"stream_window_bytes": "big"}'),
        _raw(FrameType.WINDOW_UPDATE, 1, b"\x00"),
        _raw(FrameType.WEBSOCKET_CLOSE, 1, b"\x03"),
        _raw(FrameType.TEXT_MESSAGE, 1, b"\xff"),
        _raw(FrameType.DATA, 0, b"body"),
    ],
)
def test_malformed_frame_is_rejected(message: bytes) -> None:
    with pytest.raises(FrameDecodeError):
        decode_frame(message)
