"""Password hashing with argon2id (PLAN §A14) and the password policy for web users."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.errors import TaaError

# 8 at the owner's choice (2026-10-05): login also needs TOTP and is throttled with lockouts.
MIN_LENGTH = 8
# Long inputs would make every hash attempt expensive; nobody types more than this.
MAX_LENGTH = 256

# argon2-cffi defaults follow RFC 9106's second recommendation (argon2id, t=3, m=64 MiB, p=4).
_hasher = PasswordHasher()
# Hash of a random value: verifying against it costs the same as a real user, so an unknown username is not
# revealed by a faster response.
_DUMMY_HASH = _hasher.hash("taa-dummy-password-never-valid")


class PasswordPolicyError(TaaError):
    """The password does not meet the policy."""


def check_policy(password: str, *, username: str) -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(f"the password must have at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        raise PasswordPolicyError(f"the password must have at most {MAX_LENGTH} characters")
    if password.strip().lower() == username.strip().lower():
        raise PasswordPolicyError("the password must differ from the username")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """True when *password* matches. ``None`` (unknown user) still spends one full verification."""
    if len(password) > MAX_LENGTH:
        return False
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
