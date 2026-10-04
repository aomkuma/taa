"""HMAC request authentication between the engine and the cloud (PLAN §A13, §A20; TAA-702).

Every engine → cloud request (ingest, command poll, command result, advisory-config pull) carries:

| Header | Value |
|---|---|
| ``X-Engine-Id`` | the engine's id (``ENGINE_ID``) |
| ``X-Timestamp`` | Unix seconds (integer) |
| ``X-Nonce`` | 32 random hex characters, never reused |
| ``X-Content-SHA256`` | hex SHA-256 of the exact body bytes (of ``b""`` for GET) |
| ``X-Signature`` | hex ``HMAC-SHA256(secret, METHOD|TARGET|TIMESTAMP|NONCE|BODY_SHA256)`` |

``TARGET`` is the path plus the query string (``/api/v1/engine/commands?cursor=42``), so a query cannot be
changed either.

:meth:`Verifier.verify` fails closed, in this order: missing headers, unknown engine, body hash mismatch,
timestamp skew above ``max_skew`` (300 s), signature (constant-time, against the current **and** the previous
secret during a rotation), then a reused nonce. The nonce is recorded only after the signature checks out, so
forged requests cannot fill the nonce store; nonces are kept ``nonce_ttl`` (600 s, more than twice the skew
window), after which the timestamp check alone rejects a replay.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from app.core.clock import Clock, ensure_utc
from app.core.errors import ConfigError, TaaError

H_ENGINE = "X-Engine-Id"
H_TIMESTAMP = "X-Timestamp"
H_NONCE = "X-Nonce"
H_BODY = "X-Content-SHA256"
H_SIGNATURE = "X-Signature"
HEADERS = (H_ENGINE, H_TIMESTAMP, H_NONCE, H_BODY, H_SIGNATURE)

MIN_SECRET_LENGTH = 32
MAX_SKEW_SECONDS = 300.0
NONCE_TTL_SECONDS = 600.0


class AuthFailure(StrEnum):
    MISSING_HEADER = "MISSING_HEADER"
    BAD_NONCE = "BAD_NONCE"
    UNKNOWN_ENGINE = "UNKNOWN_ENGINE"
    BODY_MISMATCH = "BODY_MISMATCH"
    STALE_TIMESTAMP = "STALE_TIMESTAMP"
    BAD_SIGNATURE = "BAD_SIGNATURE"
    REPLAYED_NONCE = "REPLAYED_NONCE"


class AuthError(TaaError):
    """A request failed authentication; ``reason`` says why (log it, never echo details to the caller)."""

    def __init__(self, reason: AuthFailure, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical(method: str, target: str, timestamp: int, nonce: str, body_hash: str) -> bytes:
    return f"{method.upper()}|{target}|{timestamp}|{nonce}|{body_hash}".encode()


def signature(secret: bytes, method: str, target: str, timestamp: int, nonce: str, body_hash: str) -> str:
    return hmac.new(
        secret, canonical(method, target, timestamp, nonce, body_hash), hashlib.sha256
    ).hexdigest()


def check_secret(secret: str | bytes, name: str = "ENGINE_HMAC_SECRET") -> bytes:
    raw = secret.encode() if isinstance(secret, str) else secret
    if len(raw) < MIN_SECRET_LENGTH:
        raise ConfigError(f"{name} must be at least {MIN_SECRET_LENGTH} characters")
    return raw


# --- signing (engine side) ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Signer:
    engine_id: str
    secret: bytes
    clock: Clock

    def __post_init__(self) -> None:
        if not self.engine_id:
            raise ConfigError("ENGINE_ID is required to sign cloud requests")
        check_secret(self.secret)

    def headers(self, method: str, target: str, body: bytes = b"") -> dict[str, str]:
        ts = int(self.clock.now_utc().timestamp())
        nonce = secrets.token_hex(16)
        digest = body_sha256(body)
        return {
            H_ENGINE: self.engine_id,
            H_TIMESTAMP: str(ts),
            H_NONCE: nonce,
            H_BODY: digest,
            H_SIGNATURE: signature(self.secret, method, target, ts, nonce, digest),
        }


# --- nonce stores -------------------------------------------------------------------------------------------


class NonceStore(Protocol):
    def add(self, engine_id: str, nonce: str, now: datetime, ttl: timedelta) -> bool:
        """Record a nonce; False when it was already seen and has not expired."""
        ...


class MemoryNonceStore:
    """In-process store (tests, a single web process). A multi-process web uses the database store."""

    def __init__(self) -> None:
        self._seen: dict[tuple[str, str], datetime] = {}
        self._lock = threading.Lock()

    def add(self, engine_id: str, nonce: str, now: datetime, ttl: timedelta) -> bool:
        now = ensure_utc(now)
        with self._lock:
            self._seen = {k: exp for k, exp in self._seen.items() if exp > now}
            key = (engine_id, nonce)
            if key in self._seen:
                return False
            self._seen[key] = now + ttl
            return True


# --- verification (cloud side) ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Verified:
    engine_id: str
    timestamp: int
    nonce: str
    previous_secret: bool  # signed with the previous secret (a rotation is in progress)


@dataclass
class Verifier:
    engines: Mapping[str, Sequence[bytes]]  # engine id → [current secret, previous secret?]
    clock: Clock
    nonces: NonceStore = field(default_factory=MemoryNonceStore)
    max_skew: float = MAX_SKEW_SECONDS
    nonce_ttl: float = NONCE_TTL_SECONDS

    def __post_init__(self) -> None:
        for engine_id, keys in self.engines.items():
            if not keys or len(keys) > 2:
                raise ConfigError(f"engine {engine_id}: one current and at most one previous secret")
            for key in keys:
                check_secret(key)

    @classmethod
    def single(
        cls,
        engine_id: str,
        secret: str | bytes,
        clock: Clock,
        *,
        previous: str | bytes | None = None,
        nonces: NonceStore | None = None,
    ) -> Verifier:
        keys = [check_secret(secret)] + (
            [check_secret(previous, "ENGINE_HMAC_SECRET_PREVIOUS")] if previous else []
        )
        return cls({engine_id: keys}, clock, nonces or MemoryNonceStore())

    def verify(self, method: str, target: str, headers: Mapping[str, str], body: bytes) -> Verified:
        h = {k.lower(): v for k, v in headers.items()}
        missing = [name for name in HEADERS if not h.get(name.lower())]
        if missing:
            raise AuthError(AuthFailure.MISSING_HEADER, ", ".join(missing))
        engine_id = h[H_ENGINE.lower()]
        keys = self.engines.get(engine_id)
        if not keys:
            raise AuthError(AuthFailure.UNKNOWN_ENGINE, engine_id)
        digest = body_sha256(body)
        if not hmac.compare_digest(digest, h[H_BODY.lower()]):
            raise AuthError(AuthFailure.BODY_MISMATCH)
        try:
            ts = int(h[H_TIMESTAMP.lower()])
        except ValueError as exc:
            raise AuthError(AuthFailure.STALE_TIMESTAMP, "not an integer") from exc
        now = self.clock.now_utc()
        skew = abs(now.timestamp() - ts)
        if skew > self.max_skew:
            raise AuthError(AuthFailure.STALE_TIMESTAMP, f"skew {skew:.0f}s")
        nonce = h[H_NONCE.lower()]
        if not 16 <= len(nonce) <= 64:
            raise AuthError(AuthFailure.BAD_NONCE, f"length {len(nonce)}")
        given = h[H_SIGNATURE.lower()]
        matched = None
        for index, key in enumerate(keys):
            if hmac.compare_digest(signature(key, method, target, ts, nonce, digest), given):
                matched = index
                break
        if matched is None:
            raise AuthError(AuthFailure.BAD_SIGNATURE)
        if not self.nonces.add(engine_id, nonce, now, timedelta(seconds=self.nonce_ttl)):
            raise AuthError(AuthFailure.REPLAYED_NONCE)
        return Verified(engine_id, ts, nonce, previous_secret=matched == 1)
