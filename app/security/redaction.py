"""Log redaction.

Two layers protect secrets from reaching logs:

1. Every resolved secret value is registered here and replaced verbatim wherever it appears.
2. Regular expressions catch common credential shapes (API keys, bearer tokens,
   ``password=...`` pairs) even if they were never registered.

Redaction is applied to the *final formatted* log line, so exception tracebacks and
``repr`` output are covered too.
"""

from __future__ import annotations

import re
import threading

REDACTED = "[REDACTED]"
_MIN_SECRET_LEN = 4

_lock = threading.Lock()
_secrets: set[str] = set()

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Anthropic / OpenAI style API keys
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{16,}\b"), REDACTED),
    # Bearer / Basic authorization headers
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]{12,}"), r"\1 " + REDACTED),
    # key=value or "key": "value" pairs for sensitive keys
    (
        re.compile(
            r"(?i)(\"?(?:password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key|totp)\"?\s*[:=]\s*)"
            r"(\"[^\"]*\"|'[^']*'|[^\s,;}&]+)"
        ),
        r"\1" + REDACTED,
    ),
    # Telegram-style bot tokens
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_\-]{30,}\b"), REDACTED),
]
# Note: long hex strings are deliberately NOT redacted by pattern; they are usually audit
# hashes or idempotency keys. Real secrets are covered by registration above.


def register_secret(value: str | None) -> None:
    """Register a secret so it is masked wherever it appears in log output."""
    if value and len(value) >= _MIN_SECRET_LEN:
        with _lock:
            _secrets.add(value)


def clear_registered_secrets() -> None:
    """Test helper."""
    with _lock:
        _secrets.clear()


def redact(text: str) -> str:
    if not text:
        return text
    with _lock:
        secrets = sorted(_secrets, key=len, reverse=True)  # longest first: no partial leaks
    for secret in secrets:
        if secret in text:
            text = text.replace(secret, REDACTED)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_login(login: int | str | None) -> str:
    """Show only the last three digits of an account number: 12345678 -> '*****678'."""
    if login is None:
        return "?"
    s = str(login)
    if len(s) <= 3:
        return "*" * len(s)
    return "*" * (len(s) - 3) + s[-3:]
