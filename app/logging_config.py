"""Logging setup: JSON lines to rotating files, readable text on the console, secrets redacted."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.context import current_ids
from app.security.redaction import redact

_RESERVED = frozenset(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class ContextFilter(logging.Filter):
    """Attach correlation ids (run_id, cycle_id, ...) to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in current_ids().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line; redaction is applied to the serialized line."""

    def __init__(self, process_name: str) -> None:
        super().__init__()
        self.process_name = process_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "process": self.process_name,
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return redact(json.dumps(payload, default=str, ensure_ascii=False))


class RedactingTextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        ids = current_ids()
        if ids:
            line += "  [" + " ".join(f"{k}={v[-8:]}" for k, v in ids.items()) + "]"
        return redact(line)


def configure_logging(
    process_name: str,
    level: str = "INFO",
    log_dir: str | Path | None = "logs",
    console: bool = True,
    max_bytes: int = 20 * 1024 * 1024,
    backup_count: int = 10,
) -> None:
    """Configure the root logger. Safe to call more than once (handlers are replaced)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)
    context_filter = ContextFilter()

    if log_dir is not None:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            path / f"{process_name}.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter(process_name))
        file_handler.addFilter(context_filter)
        root.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(RedactingTextFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        stream.addFilter(context_filter)
        root.addHandler(stream)

    # Third-party libraries can be chatty; keep them at WARNING unless debugging.
    for noisy in ("urllib3", "httpx", "httpcore", "asyncio", "multipart", "alembic.runtime.migration"):
        logging.getLogger(noisy).setLevel(logging.WARNING if level != "DEBUG" else logging.DEBUG)
