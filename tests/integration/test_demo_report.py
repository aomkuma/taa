from __future__ import annotations

from pathlib import Path

import pytest

from app.cli.__main__ import main
from app.config import BreakerConfig
from app.core.clock import SystemClock
from app.core.enums import TradingMode
from app.engine.demo_report import build_report
from app.monitoring.alerts import EventType
from app.risk.circuit_breaker import BreakerBoard, BreakerName, State, default_specs
from app.storage.database import Database, upgrade_schema
from tests.integration.test_engine_demo import demo, run_until, start_buyer


def test_report_after_a_demo_session(tmp_path: Path) -> None:
    d = demo(tmp_path)
    start_buyer(d)
    run_until(d, EventType.POSITION_OPENED)
    report = build_report(d.db, d.clock.now_utc(), days=1)
    assert report.intents_by_state["PROTECTED"] == 1
    assert report.retcodes["10009 DONE"] == 1
    assert report.decisions["ACCEPT"] >= 1
    assert all(report.checks.values()), report.checks
    data = report.to_dict()
    assert data["slippage_points"]["fills"] == 1
    d.engine.shutdown()


def test_an_unknown_order_fails_the_checks(tmp_path: Path) -> None:
    d = demo(tmp_path)
    start_buyer(d)
    assert d.engine.bundle.fake is not None
    d.engine.bundle.fake.desk.force(None)
    run_until(d, EventType.ORDER_UNKNOWN)
    report = build_report(d.db, d.clock.now_utc(), days=1)
    assert report.unresolved == 1
    assert not report.checks["every order in a final state"]
    assert not report.checks["no duplicate or unknown execution"]
    d.engine.shutdown()


class TestBreakerCli:
    @pytest.fixture
    def env(self, tmp_path: Path) -> Path:
        url = f"sqlite:///{(tmp_path / 'engine.db').as_posix()}"
        upgrade_schema(url)
        db = Database(url)
        board = BreakerBoard(
            db,
            default_specs(BreakerConfig(), consecutive_pause_hours=24),
            SystemClock(),
            mode=TradingMode.DEMO,
            tz_name="Europe/Athens",
        )
        board.trip(BreakerName.DUPLICATE_EXECUTION, "order outcome unknown")
        board.trip(BreakerName.MAX_DRAWDOWN, "10%")
        db.dispose()
        path = tmp_path / ".env"
        path.write_text(
            "TRADING_MODE=DEMO\nENABLE_DEMO_TRADING=true\nMT5_LOGIN=1\nMT5_PASSWORD=p\nMT5_SERVER=FBS-Demo\n"
            f"MT5_TERMINAL_PATH=x\nENGINE_DB_URL={url}\nENGINE_ID=test\n",
            encoding="utf-8",
        )
        return path

    def test_list_and_reset(self, env: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--env-file", str(env), "breaker", "list"]) == 0
        assert "DUPLICATE_EXECUTION" in capsys.readouterr().out
        assert main(["--env-file", str(env), "breaker", "reset", "duplicate_execution"]) == 1  # no reason
        assert (
            main(["--env-file", str(env), "breaker", "reset", "DUPLICATE_EXECUTION", "--reason", "reviewed"])
            == 0
        )
        assert main(["--env-file", str(env), "breaker", "reset", "MAX_DRAWDOWN", "--reason", "reviewed"]) == 1
        assert (
            main(["--env-file", str(env), "breaker", "reset", "MAX_DRAWDOWN", "--reason", "ok", "--ack"]) == 0
        )
        capsys.readouterr()
        main(["--env-file", str(env), "breaker", "list"])
        out = capsys.readouterr().out
        assert out.count(State.CLOSED.value) == 2
