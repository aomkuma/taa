from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.monitoring.health_check import HealthServer, heartbeat_age, write_heartbeat

T = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]


def get(port: int, path: str = "/health") -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        body = err.read()
        return err.code, json.loads(body) if body.startswith(b"{") else {}


class TestEndpoint:
    def serve(self, status: Any) -> HealthServer:
        server = HealthServer(status, port=0)
        server.start()
        return server

    def test_healthy_and_unhealthy(self) -> None:
        state = {"running": True, "connected": True, "cycles": 3}
        server = self.serve(lambda: dict(state))
        try:
            assert get(server.port) == (200, state)
            state["connected"] = False
            code, body = get(server.port)
            assert code == 503 and body["connected"] is False
            assert get(server.port, "/other")[0] == 404
        finally:
            server.stop()

    def test_a_broken_status_still_answers(self) -> None:
        def broken() -> dict[str, Any]:
            raise RuntimeError("boom")

        server = self.serve(broken)
        try:
            assert get(server.port) == (503, {"running": False, "error": "RuntimeError"})
        finally:
            server.stop()

    def test_loopback_only(self) -> None:
        with pytest.raises(ValueError, match="loopback"):
            HealthServer(dict, host="0.0.0.0", port=0)  # noqa: S104 - the point of the test


def test_heartbeat_file(tmp_path: Path) -> None:
    path = tmp_path / "data" / "heartbeat.json"
    assert heartbeat_age(path, T) is None
    write_heartbeat(path, T, {"cycles": 7}, state="running")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "running" and data["cycles"] == 7 and data["pid"] > 0
    assert heartbeat_age(path, T + timedelta(seconds=42)) == pytest.approx(42)
    path.write_text("{not json", encoding="utf-8")
    assert heartbeat_age(path, T) is None


def test_engine_writes_heartbeats(tmp_path: Path) -> None:
    from tests.integration.test_engine_paper import harness

    h = harness(tmp_path)
    h.engine.start()
    h.engine.run(max_cycles=3)
    data = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert data["status"] == "stopped"  # the final write after a deliberate stop
    assert data["run_id"] == h.engine.run_id


POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


@pytest.mark.skipif(sys.platform != "win32" or POWERSHELL is None, reason="Windows PowerShell scripts")
class TestWatchdog:
    def run(self, root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        script = REPO / "scripts" / "watchdog.ps1"
        cmd = [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-RepoRoot",
            str(root),
            *extra,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)  # noqa: S603

    def heartbeat(self, root: Path, age: float, status: str) -> None:
        ts = datetime.now(UTC) - timedelta(seconds=age)  # the script compares with the real wall clock
        write_heartbeat(root / "data" / "heartbeat.json", ts, {"pid": 999999}, state=status)

    def test_fresh_heartbeat_does_nothing(self, tmp_path: Path) -> None:
        self.heartbeat(tmp_path, 5, "running")
        assert self.run(tmp_path).returncode == 0
        assert not (tmp_path / "logs" / "watchdog.log").exists()

    def test_deliberate_stop_is_respected(self, tmp_path: Path) -> None:
        self.heartbeat(tmp_path, 3600, "stopped")
        assert self.run(tmp_path).returncode == 0
        assert not (tmp_path / "logs" / "watchdog.log").exists()

    def test_stale_heartbeat_would_restart(self, tmp_path: Path) -> None:
        self.heartbeat(tmp_path, 3600, "running")
        (tmp_path / ".venv" / "Scripts").mkdir(parents=True)
        (tmp_path / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
        result = self.run(tmp_path, "-WhatIf")
        assert result.returncode == 0, result.stderr
        assert "Start" in result.stdout and "heartbeat" in result.stdout

    def test_missing_python_is_reported(self, tmp_path: Path) -> None:
        result = self.run(tmp_path)
        assert result.returncode == 1
        assert "cannot restart" in (tmp_path / "logs" / "watchdog.log").read_text(encoding="utf-8")
