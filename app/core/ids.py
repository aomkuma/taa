"""Identifier helpers: time-ordered UUIDv7 and short display ids."""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_counter = 0


def uuid7() -> uuid.UUID:
    """Return an RFC 9562 UUIDv7 (48-bit Unix ms timestamp + randomness).

    Monotonic within a process: if called twice in the same millisecond, a 12-bit
    counter in ``rand_a`` keeps ordering stable.
    """
    global _last_ms, _counter
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms <= _last_ms:
            ms = _last_ms
            _counter = (_counter + 1) & 0xFFF
            if _counter == 0:  # counter overflow: advance the timestamp
                ms += 1
        else:
            _counter = int.from_bytes(os.urandom(2), "big") & 0x7FF  # leave headroom
        _last_ms = ms
        counter = _counter
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version 7
    value |= counter << 64
    value |= 0b10 << 62  # RFC 4122 variant
    value |= rand_b
    return uuid.UUID(int=value)


def new_id() -> str:
    """String UUIDv7, the default primary key for persisted records."""
    return str(uuid7())


def short_id(full_id: str, length: int = 8) -> str:
    """Compact display id (stable for a given full id)."""
    return full_id.replace("-", "")[-length:]


def stable_hash(*parts: object, length: int = 64) -> str:
    """Deterministic SHA-256 hex digest of the given parts, joined with '|'."""
    joined = "|".join(str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]
