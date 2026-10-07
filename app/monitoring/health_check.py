"""Engine-local health (PLAN §A19; TAA-605): ``GET http://127.0.0.1:8765/health`` and a heartbeat file.

- The endpoint binds to loopback only (the config refuses anything else) and serves the engine's status as
  JSON: 200 while the engine runs and is connected, 503 otherwise. Nothing else is served.
- The heartbeat file is rewritten atomically every health interval and once more on shutdown with
  ``"status": "stopped"`` (a deliberate stop) or ``"failed"`` (the run ended on an error, or stopped within
  10 minutes of a failed cycle). ``scripts/watchdog.ps1`` and ``scripts/demo-tasks.ps1 -Check`` restart the
  engine when the heartbeat goes stale or the health endpoint does not answer, but not after a deliberate
  stop.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.core.clock import ensure_utc

log = logging.getLogger(__name__)

StatusFn = Callable[[], dict[str, Any]]


def is_healthy(status: dict[str, Any]) -> bool:
    return bool(status.get("running")) and bool(status.get("connected"))


class HealthServer:
    def __init__(self, status: StatusFn, host: str = "127.0.0.1", port: int = 8765) -> None:
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("the health endpoint binds to loopback only")
        status_fn = status

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path.rstrip("/") != "/health":
                    self.send_error(404)
                    return
                try:
                    body = status_fn()
                    code = 200 if is_healthy(body) else 503
                except Exception as exc:  # the probe must answer even when the engine is broken
                    log.exception("health status failed")
                    body, code = {"running": False, "error": type(exc).__name__}, 503
                payload = json.dumps(body, default=str).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: Any) -> None:
                log.debug("health %s", format % args)

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="health", daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._thread.start()
        log.info("health endpoint on http://127.0.0.1:%s/health", self.port)

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def write_heartbeat(path: Path, at: datetime, status: dict[str, Any], *, state: str = "running") -> None:
    """Atomic rewrite: the watchdog never reads a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": ensure_utc(at).isoformat(), "pid": os.getpid(), "status": state, **status}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    tmp.replace(path)


def heartbeat_age(path: Path, now: datetime) -> float | None:
    """Seconds since the last heartbeat, or None when there is none (or it is unreadable)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (ensure_utc(now) - datetime.fromisoformat(data["ts"])).total_seconds()
    except (OSError, ValueError, KeyError):
        return None
