"""HMAC request authentication: signing, verification, rotation, forgery, replay and skew (TAA-702)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.clock import ManualClock
from app.core.errors import ConfigError
from app.security.hmac_auth import (
    H_BODY,
    H_NONCE,
    H_SIGNATURE,
    H_TIMESTAMP,
    AuthError,
    AuthFailure,
    MemoryNonceStore,
    Signer,
    Verifier,
    body_sha256,
    canonical,
)

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
SECRET = "s" * 40
OLD = "o" * 40
TARGET = "/api/v1/ingest/batch"
BODY = b'{"events": []}'


def rig(previous: str | None = None):  # type: ignore[no-untyped-def]
    clock = ManualClock(NOW)
    return (
        clock,
        Signer("eng-1", SECRET.encode(), clock),
        Verifier.single("eng-1", SECRET, clock, previous=previous),
    )


def fails(verifier: Verifier, reason: AuthFailure, headers: dict[str, str], body: bytes = BODY, method: str = "POST", target: str = TARGET) -> None:  # fmt: skip
    with pytest.raises(AuthError) as err:
        verifier.verify(method, target, headers, body)
    assert err.value.reason is reason


class TestSignAndVerify:
    def test_round_trip(self) -> None:
        _, signer, verifier = rig()
        headers = signer.headers("POST", TARGET, BODY)
        ok = verifier.verify("POST", TARGET, headers, BODY)
        assert ok.engine_id == "eng-1" and ok.timestamp == int(NOW.timestamp()) and not ok.previous_secret
        assert headers[H_BODY] == body_sha256(BODY) and len(headers[H_NONCE]) == 32

    def test_headers_are_case_insensitive_and_get_has_an_empty_body(self) -> None:
        _, signer, verifier = rig()
        headers = {k.lower(): v for k, v in signer.headers("GET", "/api/v1/engine/commands?cursor=3").items()}
        assert verifier.verify("get", "/api/v1/engine/commands?cursor=3", headers, b"").engine_id == "eng-1"

    def test_canonical_form(self) -> None:
        assert canonical("post", "/x?a=1", 5, "n", "h") == b"POST|/x?a=1|5|n|h"


class TestForgery:
    def test_tampered_body_target_method_and_signature(self) -> None:
        _, signer, verifier = rig()
        headers = signer.headers("POST", TARGET, BODY)
        fails(verifier, AuthFailure.BODY_MISMATCH, headers, body=b'{"events": [1]}')
        fails(verifier, AuthFailure.BAD_SIGNATURE, headers, target="/api/v1/ingest/other")
        fails(verifier, AuthFailure.BAD_SIGNATURE, headers, method="PUT")
        fails(verifier, AuthFailure.BAD_SIGNATURE, headers | {H_SIGNATURE: "0" * 64})
        query = signer.headers("GET", "/api/v1/engine/commands?cursor=1")
        fails(
            verifier,
            AuthFailure.BAD_SIGNATURE,
            query,
            body=b"",
            method="GET",
            target="/api/v1/engine/commands?cursor=9",
        )

    def test_a_body_hash_header_cannot_be_swapped_with_the_body(self) -> None:
        _, signer, verifier = rig()
        headers = signer.headers("POST", TARGET, BODY)
        other = b'{"events": ["evil"]}'
        fails(verifier, AuthFailure.BAD_SIGNATURE, headers | {H_BODY: body_sha256(other)}, body=other)

    def test_wrong_secret_unknown_engine_and_missing_headers(self) -> None:
        clock, _, verifier = rig()
        intruder = Signer("eng-1", ("x" * 40).encode(), clock)
        fails(verifier, AuthFailure.BAD_SIGNATURE, intruder.headers("POST", TARGET, BODY))
        stranger = Signer("eng-2", SECRET.encode(), clock)
        fails(verifier, AuthFailure.UNKNOWN_ENGINE, stranger.headers("POST", TARGET, BODY))
        headers = Signer("eng-1", SECRET.encode(), clock).headers("POST", TARGET, BODY)
        del headers[H_NONCE]
        fails(verifier, AuthFailure.MISSING_HEADER, headers)
        fails(verifier, AuthFailure.MISSING_HEADER, {})


class TestReplayAndSkew:
    def test_a_nonce_is_used_once(self) -> None:
        _, signer, verifier = rig()
        headers = signer.headers("POST", TARGET, BODY)
        verifier.verify("POST", TARGET, headers, BODY)
        fails(verifier, AuthFailure.REPLAYED_NONCE, headers)

    def test_forged_requests_do_not_burn_nonces(self) -> None:
        _, signer, verifier = rig()
        headers = signer.headers("POST", TARGET, BODY)
        fails(verifier, AuthFailure.BAD_SIGNATURE, headers | {H_SIGNATURE: "0" * 64})
        assert verifier.verify("POST", TARGET, headers, BODY).nonce == headers[H_NONCE]

    def test_clock_skew(self) -> None:
        clock, signer, verifier = rig()
        headers = signer.headers("POST", TARGET, BODY)
        clock.advance(301)
        fails(verifier, AuthFailure.STALE_TIMESTAMP, headers)
        early = signer.headers("POST", TARGET, BODY)
        clock.advance(-600)
        fails(verifier, AuthFailure.STALE_TIMESTAMP, early)
        clock.advance(300)
        fresh = signer.headers("POST", TARGET, BODY) | {H_TIMESTAMP: "soon"}
        fails(verifier, AuthFailure.STALE_TIMESTAMP, fresh)

    def test_a_replay_after_the_nonce_expired_is_stale(self) -> None:
        clock, signer, verifier = rig()
        headers = signer.headers("POST", TARGET, BODY)
        verifier.verify("POST", TARGET, headers, BODY)
        clock.advance(700)  # the nonce is gone, but the timestamp is far outside the skew window
        fails(verifier, AuthFailure.STALE_TIMESTAMP, headers)

    def test_memory_store_expiry(self) -> None:
        store = MemoryNonceStore()
        ttl = timedelta(seconds=600)
        assert store.add("e", "n", NOW, ttl) and not store.add("e", "n", NOW, ttl)
        assert store.add("other", "n", NOW, ttl)  # per engine
        assert store.add("e", "n", NOW + ttl, ttl)  # expired


class TestRotation:
    def test_current_and_previous_secrets_are_accepted(self) -> None:
        clock, signer, verifier = rig(previous=OLD)
        assert not verifier.verify("POST", TARGET, signer.headers("POST", TARGET, BODY), BODY).previous_secret
        old = Signer("eng-1", OLD.encode(), clock)
        assert verifier.verify("POST", TARGET, old.headers("POST", TARGET, BODY), BODY).previous_secret

    def test_after_rotation_the_old_secret_is_rejected(self) -> None:
        clock, _, verifier = rig()
        old = Signer("eng-1", OLD.encode(), clock)
        fails(verifier, AuthFailure.BAD_SIGNATURE, old.headers("POST", TARGET, BODY))


class TestConfiguration:
    def test_weak_or_missing_settings_fail_closed(self) -> None:
        clock = ManualClock(NOW)
        with pytest.raises(ConfigError, match="32"):
            Signer("eng-1", b"short", clock)
        with pytest.raises(ConfigError, match="ENGINE_ID"):
            Signer("", SECRET.encode(), clock)
        with pytest.raises(ConfigError, match="PREVIOUS"):
            Verifier.single("eng-1", SECRET, clock, previous="short")
        with pytest.raises(ConfigError, match="at most one previous"):
            Verifier({"eng-1": [SECRET.encode()] * 3}, clock)


def test_nonce_length_is_bounded() -> None:
    _, signer, verifier = rig()
    for bad in ("short", "n" * 65):
        headers = signer.headers("POST", TARGET, BODY) | {H_NONCE: bad}
        fails(verifier, AuthFailure.BAD_NONCE, headers)


def test_sql_nonce_store(db) -> None:  # type: ignore[no-untyped-def]
    from app.sync.nonces import SqlNonceStore

    store = SqlNonceStore(db)
    ttl = timedelta(seconds=600)
    assert store.add("e", "a" * 32, NOW, ttl) and not store.add("e", "a" * 32, NOW, ttl)
    assert store.add("f", "a" * 32, NOW, ttl)
    assert store.add("e", "a" * 32, NOW + ttl, ttl)  # the expired row was pruned
    clock = ManualClock(NOW)
    verifier = Verifier.single("eng-1", SECRET, clock, nonces=store)
    headers = Signer("eng-1", SECRET.encode(), clock).headers("POST", TARGET, BODY)
    verifier.verify("POST", TARGET, headers, BODY)
    fails(verifier, AuthFailure.REPLAYED_NONCE, headers)
