"""Planted bugs in the round-4 fix of app/broker/gateway.py (the tick-month sync retry), in memory only, against
tests/unit/test_ticks_sync.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_gateway_ticks
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEST = ["tests/unit/test_ticks_sync.py"]

GW = [
    ("one attempt fewer", "        for attempt in range(1, TICK_SYNC_ATTEMPTS + 1):", "        for attempt in range(1, TICK_SYNC_ATTEMPTS):"),
    ("every error retried", "            if err[0] != _TICKS_SYNCING:", "            if False:"),
    ("no error retried", "            if err[0] != _TICKS_SYNCING:", "            if True:"),
    ("no pause between attempts", "                self._sleep(TICK_SYNC_PAUSE_S)", "                pass"),
    ("a pause after the last attempt too", "            if attempt < TICK_SYNC_ATTEMPTS:", "            if True:"),
    ("an empty answer taken as a failure", "            if raw is not None:\n", "            if raw is not None and len(raw):\n"),
]

TARGETS = [("app.broker.gateway", ROOT / "app" / "broker" / "gateway.py", TEST, GW)]
