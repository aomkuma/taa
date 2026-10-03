from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import SecretStr

from app.core.context import bind
from app.logging_config import configure_logging
from app.security.redaction import REDACTED, mask_login, redact, register_secret
from app.security.secrets import resolve_secret


def test_registered_secret_redacted() -> None:
    register_secret("S3cr3t-Value!")
    assert redact("password is S3cr3t-Value! ok") == f"password is {REDACTED} ok"


def test_pattern_redaction() -> None:
    assert "sk-ant-abcdefghijklmnop1234" not in redact("key sk-ant-abcdefghijklmnop1234")
    assert "abc123" not in redact('{"password": "abc123"}')
    assert REDACTED in redact("Authorization: Bearer abcdefghijklmnopqrstuvwxyz")
    assert REDACTED in redact("api_key=XYZ987654")


def test_mask_login() -> None:
    assert mask_login(12345678) == "*****678"
    assert mask_login("12") == "**"


def test_resolve_secret_registers() -> None:
    s = resolve_secret(SecretStr("very-secret-pass"), name="X")
    assert s is not None
    assert redact("very-secret-pass") == REDACTED


def test_secrets_never_reach_log_files(tmp_path: Path) -> None:
    secret = "Pa55word-XYZ-123"
    register_secret(secret)
    configure_logging("testproc", level="DEBUG", log_dir=tmp_path, console=False)
    log = logging.getLogger("t")
    with bind(run_id="run-1"):
        log.info("connecting with %s", secret)
        try:
            raise RuntimeError(f"login failed for password {secret}")
        except RuntimeError:
            log.exception("boom")
    for h in logging.getLogger().handlers:
        h.flush()
    content = (tmp_path / "testproc.log").read_text(encoding="utf-8")
    assert secret not in content
    first = json.loads(content.splitlines()[0])
    assert first["run_id"] == "run-1"
    assert first["level"] == "INFO"
    configure_logging("testproc", log_dir=None, console=False)
