"""Security primitives of the web service: argon2id passwords, TOTP, derived keys and encryption at rest."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.security import passwords, web_totp
from app.security.crypto import DecryptionError, SecretBox, derive_key, keyed_digest
from app.web.auth import BASE_LOCK, MAX_LOCK, lock_duration

AT = datetime(2026, 10, 1, 12, 0, 10, tzinfo=UTC)
SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


class TestPasswords:
    def test_argon2id_round_trip(self) -> None:
        digest = passwords.hash_password("correct horse battery staple")
        assert digest.startswith("$argon2id$")
        assert passwords.verify_password(digest, "correct horse battery staple")
        assert not passwords.verify_password(digest, "correct horse battery stapler")

    def test_unknown_user_never_verifies(self) -> None:
        assert not passwords.verify_password(None, "taa-dummy-password-never-valid")
        assert not passwords.verify_password(None, "anything at all")

    def test_garbage_hash_is_a_mismatch(self) -> None:
        assert not passwords.verify_password("not-a-hash", "correct horse battery staple")

    def test_overlong_input_is_rejected_without_hashing(self) -> None:
        digest = passwords.hash_password("x" * passwords.MAX_LENGTH)
        assert not passwords.verify_password(digest, "x" * (passwords.MAX_LENGTH + 1))

    @pytest.mark.parametrize(
        ("password", "message"),
        [("short", "at least"), ("y" * 300, "at most"), ("Alice.Example", "differ")],
    )
    def test_policy(self, password: str, message: str) -> None:
        with pytest.raises(passwords.PasswordPolicyError, match=message):
            passwords.check_policy(password, username="alice.example")

    def test_policy_accepts_a_long_passphrase(self) -> None:
        passwords.check_policy("correct horse battery staple", username="alice")

    def test_policy_minimum_is_eight_characters(self) -> None:
        passwords.check_policy("8chars!!", username="alice")
        with pytest.raises(passwords.PasswordPolicyError, match="at least 8"):
            passwords.check_policy("7chars!", username="alice")


class TestTotp:
    def test_rfc6238_sha1_vector(self) -> None:
        # RFC 6238 appendix B: T=59 s, key "12345678901234567890", 8 digits 94287082 -> 6 digits 287082.
        rfc_secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        assert web_totp.code_at(rfc_secret, 59 // web_totp.INTERVAL) == "287082"

    def test_current_and_adjacent_steps_match(self) -> None:
        step = web_totp.time_step(AT)
        for offset in (-1, 0, 1):
            assert (
                web_totp.verify_totp(SECRET, web_totp.code_at(SECRET, step + offset), at=AT) == step + offset
            )

    def test_codes_outside_the_window_fail(self) -> None:
        step = web_totp.time_step(AT)
        assert web_totp.verify_totp(SECRET, web_totp.code_at(SECRET, step - 2), at=AT) is None
        assert web_totp.verify_totp(SECRET, web_totp.code_at(SECRET, step + 2), at=AT) is None

    def test_used_steps_cannot_be_replayed(self) -> None:
        step = web_totp.time_step(AT)
        code = web_totp.code_at(SECRET, step)
        assert web_totp.verify_totp(SECRET, code, at=AT, after_step=step) is None
        assert web_totp.verify_totp(SECRET, code, at=AT, after_step=step - 1) == step

    @pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 34 5x"])
    def test_malformed_codes_fail(self, code: str) -> None:
        assert web_totp.verify_totp(SECRET, code, at=AT) is None

    def test_spaces_are_ignored(self) -> None:
        code = web_totp.code_at(SECRET, web_totp.time_step(AT))
        assert web_totp.verify_totp(SECRET, f"{code[:3]} {code[3:]}", at=AT) is not None

    def test_naive_time_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="naive"):
            web_totp.time_step(datetime(2026, 10, 1, 12, 0))

    def test_provisioning_uri(self) -> None:
        uri = web_totp.provisioning_uri(SECRET, account="owner")
        assert uri.startswith("otpauth://totp/TAA:owner?")
        assert f"secret={SECRET}" in uri
        assert "issuer=TAA" in uri

    def test_generated_secrets_are_random_base32(self) -> None:
        first, second = web_totp.generate_secret(), web_totp.generate_secret()
        assert first != second
        assert len(first) == 32
        assert set(first) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


class TestCrypto:
    def test_keys_differ_by_purpose_and_secret(self) -> None:
        secret = "s" * 40
        assert derive_key(secret, "session-token") != derive_key(secret, "csrf")
        assert derive_key(secret, "csrf") != derive_key("t" * 40, "csrf")
        assert derive_key(secret, "csrf") == derive_key(secret, "csrf")

    def test_secret_box_round_trip_and_tamper(self) -> None:
        box = SecretBox(derive_key("s" * 40, "totp-secret"))
        token = box.encrypt(SECRET)
        assert SECRET not in token
        assert box.decrypt(token) == SECRET
        with pytest.raises(DecryptionError):
            SecretBox(derive_key("t" * 40, "totp-secret")).decrypt(token)
        with pytest.raises(DecryptionError):
            box.decrypt(token[:-4] + "AAAA")

    def test_keyed_digest(self) -> None:
        key = derive_key("s" * 40, "session-token")
        assert keyed_digest(key, "token") == keyed_digest(key, "token")
        assert keyed_digest(key, "token") != keyed_digest(key, "token2")
        assert len(keyed_digest(key, "token")) == 64


class TestLockDuration:
    def test_exponential_and_capped(self) -> None:
        assert lock_duration(4, 5) is None
        assert lock_duration(5, 5) == BASE_LOCK
        assert lock_duration(6, 5) == 2 * BASE_LOCK
        assert lock_duration(7, 5) == 4 * BASE_LOCK
        assert lock_duration(30, 5) == MAX_LOCK
        assert lock_duration(10_000, 5) == MAX_LOCK
        assert timedelta(hours=1) == MAX_LOCK
