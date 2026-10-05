"""Go-live drills rehearsed on LIVE with FakeMT5 and a REAL account (TAA-1403; docs/RUNBOOK_LIVE.md).

Each drill is the automated half of a runbook step; the owner repeats it on the engine machine before LIVE.
Credential rotation is rehearsed in tests/web/test_engines_api.py (HMAC rotate/revoke) and
tests/web/test_engine_registry.py (control TOTP); the engine-offline response in tests/unit/test_worker.py
(watchdog); restore from backup in tests/unit/test_backup.py.
"""

from __future__ import annotations

from pathlib import Path

from app.broker import mt5_constants as c
from app.monitoring.alerts import EventType
from app.risk.circuit_breaker import BreakerName
from app.risk.kill_switch import KillMode
from app.risk.mode_gates import GateCondition
from tests.integration.test_engine_demo import run_until, start_buyer
from tests.integration.test_engine_live import live


def test_drill_kill_switch_halt_then_flatten_then_release(tmp_path: Path) -> None:
    d = live(tmp_path)
    start_buyer(d)
    run_until(d, EventType.POSITION_OPENED)
    fake = d.engine.bundle.fake
    assert fake is not None
    sent = fake.calls["order_send"]
    # 1. HALT: no new orders, the open position stays
    d.engine.kill_switch.activate("drill: halt", "owner", "cli")
    for _ in range(20):
        d.engine.cycle()
        d.clock.advance(30)
    assert fake.calls["order_send"] == sent and len(d.engine.gateway.positions()) == 1
    gate = d.engine.gate()
    assert gate is not None and GateCondition.KILL_SWITCH in gate.failed_conditions
    # 2. FLATTEN: the bot's positions are closed at the broker
    d.engine.kill_switch.release("drill done", "owner", "cli")
    d.engine.kill_switch.activate("drill: flatten", "owner", "cli", KillMode.FLATTEN)
    d.clock.advance(10)
    d.engine.cycle()
    assert d.engine.gateway.positions() == []
    assert any(x.entry == c.DEAL_ENTRY_OUT for x in fake.deals)
    # 3. release (local only): the gate passes again
    d.engine.kill_switch.release("drill done", "owner", "cli")
    gate = d.engine.gate()
    assert gate is not None and gate.passed
    d.engine.shutdown()


def test_drill_a_latched_breaker_blocks_until_its_manual_reset(tmp_path: Path) -> None:
    d = live(tmp_path)
    start_buyer(d)
    d.engine.board.trip(BreakerName.MAX_DRAWDOWN, "drill: drawdown limit")
    gate = d.engine.gate()
    assert gate is not None and GateCondition.BREAKERS in gate.failed_conditions
    d.engine.board.reset(BreakerName.MAX_DRAWDOWN, actor="owner", reason="drill done", acknowledge=True)
    gate = d.engine.gate()
    assert gate is not None and gate.passed
    d.engine.shutdown()
