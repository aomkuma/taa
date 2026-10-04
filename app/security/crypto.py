"""Keys derived from one server secret, and authenticated encryption for small values at rest.

``WEB_SESSION_SECRET`` is the only key material of the web service. Purpose-specific keys are derived from it
with HKDF-SHA256, so a key used for one job (session token hashing, CSRF tokens, TOTP secret encryption) is
never reused for another. Rotating the secret therefore ends every session and requires TOTP re-enrollment
(PLAN §A20, credential rotation).
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.errors import TaaError


class DecryptionError(TaaError):
    """A stored value could not be decrypted (wrong key or tampered data)."""


def derive_key(secret: str, purpose: str) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"taa-web", info=purpose.encode("ascii"))
    return hkdf.derive(secret.encode("utf-8"))


def keyed_digest(key: bytes, value: str) -> str:
    """HMAC-SHA256 hex digest; used to store session tokens without storing the tokens."""
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


class SecretBox:
    """Fernet (AES-128-CBC + HMAC-SHA256) around a derived key."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise DecryptionError("stored value cannot be decrypted with the current key") from exc
