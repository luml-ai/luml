"""Frames exchanged between agent and relay over the `luml-tunnel.v1` subprotocol.

Every frame is one binary WebSocket message:

    type (uint8) | stream id (uint32, big-endian) | payload

Connection frames use stream id 0. Stream ids are chosen by the relay, which alone opens
streams. Payloads by type:

    0x01 limits           relay -> agent  JSON object of RelayLimits fields
    0x02 renew token      agent -> relay  UTF-8 token
    0x03 reconnect        relay -> agent  empty
    0x10 open HTTP        relay -> agent  JSON {"method", "target", "headers": [[name, value]]}
    0x11 open WebSocket   relay -> agent  JSON {"target", "headers": [[name, value]]}
    0x12 response head    agent -> relay  JSON {"status", "headers": [[name, value]]};
                                          status 101 accepts a WebSocket stream
    0x13 data             both            raw body bytes
    0x14 end              both            empty; no more body in this direction
    0x15 text message     both            UTF-8 WebSocket text message
    0x16 binary message   both            raw WebSocket binary message
    0x17 WebSocket close  both            close code (uint16, big-endian) | UTF-8 reason
    0x18 window update    both            credit increment (uint32, big-endian)
    0x19 reset            both            UTF-8 reason; abandons the stream in both directions

Frames of an unknown type are ignored, and so are unknown keys in JSON payloads, so
frames and fields can be added within the version.

The relay closes the connection with code 4000 when another agent takes over the
session, and with code 4001 when the token has expired.
"""

import json
import struct
from dataclasses import asdict, dataclass, fields
from enum import IntEnum
from typing import Any

SUBPROTOCOL = "luml-tunnel.v1"
CONNECTION_STREAM_ID = 0
REPLACED_CLOSE_CODE = 4000
TOKEN_EXPIRED_CLOSE_CODE = 4001

_HEADER = struct.Struct(">BI")
_CLOSE_CODE = struct.Struct(">H")
_INCREMENT = struct.Struct(">I")

Headers = list[tuple[str, str]]


class FrameType(IntEnum):
    LIMITS = 0x01
    RENEW_TOKEN = 0x02
    RECONNECT = 0x03
    OPEN_HTTP = 0x10
    OPEN_WEBSOCKET = 0x11
    RESPONSE_HEAD = 0x12
    DATA = 0x13
    END = 0x14
    TEXT_MESSAGE = 0x15
    BINARY_MESSAGE = 0x16
    WEBSOCKET_CLOSE = 0x17
    WINDOW_UPDATE = 0x18
    RESET = 0x19


class FrameDecodeError(Exception):
    pass


@dataclass(frozen=True)
class RelayLimits:
    max_concurrent_streams: int = 100
    max_request_body_bytes: int = 100 * 1024 * 1024
    idle_timeout_seconds: float = 300.0
    stream_window_bytes: int = 256 * 1024


@dataclass(frozen=True)
class RenewToken:
    token: str


@dataclass(frozen=True)
class Reconnect:
    pass


@dataclass(frozen=True)
class OpenHttp:
    stream_id: int
    method: str
    target: str
    headers: Headers


@dataclass(frozen=True)
class OpenWebSocket:
    stream_id: int
    target: str
    headers: Headers


@dataclass(frozen=True)
class ResponseHead:
    stream_id: int
    status: int
    headers: Headers


@dataclass(frozen=True)
class Data:
    stream_id: int
    data: bytes


@dataclass(frozen=True)
class End:
    stream_id: int


@dataclass(frozen=True)
class WebSocketMessage:
    stream_id: int
    data: str | bytes


@dataclass(frozen=True)
class WebSocketClose:
    stream_id: int
    code: int
    reason: str


@dataclass(frozen=True)
class WindowUpdate:
    stream_id: int
    increment: int


@dataclass(frozen=True)
class Reset:
    stream_id: int
    reason: str


ConnectionFrame = RelayLimits | RenewToken | Reconnect
OpenFrame = OpenHttp | OpenWebSocket
StreamFrame = (
    OpenHttp
    | OpenWebSocket
    | ResponseHead
    | Data
    | End
    | WebSocketMessage
    | WebSocketClose
    | WindowUpdate
    | Reset
)
Frame = ConnectionFrame | StreamFrame


def encode_frame(frame: Frame) -> bytes:
    match frame:
        case RelayLimits():
            return _pack(FrameType.LIMITS, CONNECTION_STREAM_ID, _dump_json(asdict(frame)))
        case RenewToken(token):
            return _pack(FrameType.RENEW_TOKEN, CONNECTION_STREAM_ID, token.encode())
        case Reconnect():
            return _pack(FrameType.RECONNECT, CONNECTION_STREAM_ID, b"")
        case OpenHttp(stream_id, method, target, headers):
            return _pack(
                FrameType.OPEN_HTTP,
                stream_id,
                _dump_json({"method": method, "target": target, "headers": headers}),
            )
        case OpenWebSocket(stream_id, target, headers):
            return _pack(
                FrameType.OPEN_WEBSOCKET,
                stream_id,
                _dump_json({"target": target, "headers": headers}),
            )
        case ResponseHead(stream_id, status, headers):
            return _pack(
                FrameType.RESPONSE_HEAD,
                stream_id,
                _dump_json({"status": status, "headers": headers}),
            )
        case Data(stream_id, data):
            return _pack(FrameType.DATA, stream_id, data)
        case End(stream_id):
            return _pack(FrameType.END, stream_id, b"")
        case WebSocketMessage(stream_id, str() as text):
            return _pack(FrameType.TEXT_MESSAGE, stream_id, text.encode())
        case WebSocketMessage(stream_id, bytes() as data):
            return _pack(FrameType.BINARY_MESSAGE, stream_id, data)
        case WebSocketClose(stream_id, code, reason):
            return _pack(
                FrameType.WEBSOCKET_CLOSE, stream_id, _CLOSE_CODE.pack(code) + reason.encode()
            )
        case WindowUpdate(stream_id, increment):
            return _pack(FrameType.WINDOW_UPDATE, stream_id, _INCREMENT.pack(increment))
        case Reset(stream_id, reason):
            return _pack(FrameType.RESET, stream_id, reason.encode())
    raise TypeError(f"not a frame: {frame!r}")


def decode_frame(message: bytes) -> Frame | None:
    """Decode one message; None for a frame type this version does not know."""
    if len(message) < _HEADER.size:
        raise FrameDecodeError("frame shorter than its header")
    type_code, stream_id = _HEADER.unpack_from(message)
    try:
        frame_type = FrameType(type_code)
    except ValueError:
        return None
    payload = message[_HEADER.size :]
    try:
        return _decode_payload(frame_type, stream_id, payload)
    except (ValueError, KeyError, TypeError, struct.error) as error:
        raise FrameDecodeError(f"malformed {frame_type.name} frame: {error}") from error


def _decode_payload(frame_type: FrameType, stream_id: int, payload: bytes) -> Frame:
    if frame_type is FrameType.LIMITS:
        return _decode_limits(payload)
    if frame_type is FrameType.RENEW_TOKEN:
        return RenewToken(payload.decode())
    if frame_type is FrameType.RECONNECT:
        return Reconnect()
    if stream_id == CONNECTION_STREAM_ID:
        raise ValueError("stream frame on the connection stream")
    match frame_type:
        case FrameType.OPEN_HTTP:
            obj = _load_json(payload)
            return OpenHttp(
                stream_id,
                _typed(obj["method"], str),
                _typed(obj["target"], str),
                _headers(obj["headers"]),
            )
        case FrameType.OPEN_WEBSOCKET:
            obj = _load_json(payload)
            return OpenWebSocket(stream_id, _typed(obj["target"], str), _headers(obj["headers"]))
        case FrameType.RESPONSE_HEAD:
            obj = _load_json(payload)
            return ResponseHead(stream_id, _typed(obj["status"], int), _headers(obj["headers"]))
        case FrameType.DATA:
            return Data(stream_id, payload)
        case FrameType.END:
            return End(stream_id)
        case FrameType.TEXT_MESSAGE:
            return WebSocketMessage(stream_id, payload.decode())
        case FrameType.BINARY_MESSAGE:
            return WebSocketMessage(stream_id, payload)
        case FrameType.WEBSOCKET_CLOSE:
            (code,) = _CLOSE_CODE.unpack_from(payload)
            return WebSocketClose(stream_id, code, payload[_CLOSE_CODE.size :].decode())
        case FrameType.WINDOW_UPDATE:
            (increment,) = _INCREMENT.unpack(payload)
            return WindowUpdate(stream_id, increment)
        case FrameType.RESET:
            return Reset(stream_id, payload.decode())
    raise ValueError(f"unhandled frame type {frame_type.name}")


def _decode_limits(payload: bytes) -> RelayLimits:
    obj = _load_json(payload)
    known: dict[str, Any] = {}
    for limit in fields(RelayLimits):
        if limit.name in obj:
            value = obj[limit.name]
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError(f"{limit.name} is not a number")
            known[limit.name] = value
    return RelayLimits(**known)


def _pack(frame_type: FrameType, stream_id: int, payload: bytes) -> bytes:
    return _HEADER.pack(frame_type, stream_id) + payload


def _dump_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def _load_json(payload: bytes) -> dict[str, Any]:
    obj = json.loads(payload)
    if not isinstance(obj, dict):
        raise TypeError("payload is not a JSON object")
    return obj


def _typed[T](value: object, expected: type[T]) -> T:
    if isinstance(value, bool) or not isinstance(value, expected):
        raise TypeError(f"expected {expected.__name__}, got {type(value).__name__}")
    return value


def _headers(value: object) -> Headers:
    pairs = _typed(value, list)
    headers: Headers = []
    for pair in pairs:
        name, header_value = _typed(pair, list)
        headers.append((_typed(name, str), _typed(header_value, str)))
    return headers
