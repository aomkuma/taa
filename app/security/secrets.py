"""Secret resolution.

A secret value may be given directly (environment / ``.env`` / Railway sealed variable) or as an
indirection to the operating-system credential store::

    MT5_PASSWORD=keyring:taa/mt5-demo

which reads the password stored under service ``taa`` and username ``mt5-demo`` in Windows
Credential Manager (via the ``keyring`` package). Resolved secrets are registered with the log
redactor so they can never be written to logs verbatim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import SecretStr

from app.core.errors import SecretError
from app.security.redaction import register_secret

if TYPE_CHECKING:
    from app.config import EnvSettings

KEYRING_PREFIX = "keyring:"


def resolve_secret(value: SecretStr | None, *, name: str) -> SecretStr | None:
    if value is None:
        return None
    raw = value.get_secret_value()
    if raw.startswith(KEYRING_PREFIX):
        ref = raw[len(KEYRING_PREFIX) :]
        service, sep, username = ref.partition("/")
        if not sep or not service or not username:
            raise SecretError(f"{name}: keyring reference must look like 'keyring:<service>/<username>'")
        try:
            import keyring  # optional dependency, engine only
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise SecretError(f"{name}: the 'keyring' package is not installed") from exc
        stored = keyring.get_password(service, username)
        if not stored:
            raise SecretError(f"{name}: no credential found in the OS keyring for {service}/{username}")
        raw = stored
    if not raw.strip():
        raise SecretError(f"{name}: secret is empty")
    register_secret(raw)
    return SecretStr(raw)


def resolve_env_secrets(env: EnvSettings) -> EnvSettings:
    """Return a copy of ``env`` with every SecretStr resolved and registered for redaction."""
    updates: dict[str, SecretStr | None] = {}
    for field_name in type(env).model_fields:
        value = getattr(env, field_name)
        if isinstance(value, SecretStr):
            updates[field_name] = resolve_secret(value, name=field_name)
    return env.model_copy(update=updates)
