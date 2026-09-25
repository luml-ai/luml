"""ULIDs: 48-bit millisecond timestamp + 80 random bits, Crockford base32.

Ids minted in the same millisecond increment the random component instead of
redrawing it, so lexicographic order is always mint order — cell creation
order and version order are read straight off the id.
"""

import os
import threading
import time

ULID_LENGTH = 26

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ALPHABET_SET = frozenset(_ALPHABET)
_RANDOM_BITS = 80
_MAX_RANDOM = (1 << _RANDOM_BITS) - 1

_lock = threading.Lock()
_last_ms = -1
_last_random = 0


def new_ulid() -> str:
    global _last_ms, _last_random
    with _lock:
        ms = int(time.time() * 1000)
        if ms > _last_ms:
            _last_random = int.from_bytes(os.urandom(10), "big")
        elif _last_random < _MAX_RANDOM:
            ms = _last_ms
            _last_random += 1
        else:
            ms = _last_ms + 1
            _last_random = int.from_bytes(os.urandom(10), "big")
        _last_ms = ms
        value = (ms << _RANDOM_BITS) | _last_random
    return _encode(value)


def is_ulid(value: str) -> bool:
    return len(value) == ULID_LENGTH and all(char in _ALPHABET_SET for char in value)


def _encode(value: int) -> str:
    chars = [""] * ULID_LENGTH
    for position in range(ULID_LENGTH - 1, -1, -1):
        chars[position] = _ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)
