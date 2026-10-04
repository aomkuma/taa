"""TOTP for web users (RFC 6238: SHA-1, 6 digits, 30 s steps): login, step-up and enrollment.

Stateless: the caller stores the last used step per user (``users.totp_last_step``) and the web service holds
the secrets (encrypted). Remote trading commands use a different secret that only the engine knows
(``CONTROL_TOTP_SECRET``, ``app/security/totp.py``).

:func:`verify_totp` accepts the current step and one step either side (clock skew) and returns the matched
step, so callers can reject a code whose step is not newer than the last one used (no replay within its
lifetime).
"""

from __future__ import annotations

import hmac
from datetime import datetime

import pyotp

from app.core.clock import ensure_utc

DIGITS = 6
INTERVAL = 30
VALID_WINDOW = 1


def generate_secret() -> str:
    """A new random base32 secret (160 bits)."""
    return pyotp.random_base32(length=32)


def provisioning_uri(secret: str, *, account: str, issuer: str = "TAA") -> str:
    """``otpauth://`` URI for the QR code shown at enrollment."""
    return pyotp.TOTP(secret, digits=DIGITS, interval=INTERVAL).provisioning_uri(
        name=account, issuer_name=issuer
    )


def time_step(at: datetime) -> int:
    return int(ensure_utc(at).timestamp()) // INTERVAL


def code_at(secret: str, step: int) -> str:
    return pyotp.TOTP(secret, digits=DIGITS, interval=INTERVAL).at(step * INTERVAL)


def verify_totp(secret: str, code: str, *, at: datetime, after_step: int = 0) -> int | None:
    """The time step *code* belongs to, or ``None``. Steps at or before *after_step* never match."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now_step = time_step(at)
    matched: int | None = None
    for step in range(now_step - VALID_WINDOW, now_step + VALID_WINDOW + 1):
        # Compare every candidate in constant time; don't stop early.
        if hmac.compare_digest(code_at(secret, step), code) and step > after_step:
            matched = step
    return matched
