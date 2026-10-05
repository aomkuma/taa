"""``GET /engines/{id}/strategies``: state, effective parameters and per-strategy performance (TAA-909)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.config import load_app_config
from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import (
    ConfigSnapshot,
    DecisionRecordRow,
    EngineHeartbeatRow,
    PaperIntentRow,
    PaperPositionRow,
    Run,
)
from app.sync.command_queue import CommandQueue
from app.web.strategies import strategy_overview
from tests.sync_data import T
from tests.web import test_data_api
from tests.web.test_data_api import get, position

rig = test_data_api.rig  # the fixture

EXAMPLE = "example_trend_pullback"
SETUP = "setup_fib_pullback"


def real_config(db: Database, engine_id: str, **changes: Any) -> dict[str, Any]:
    """The repository's config.yaml as the engine snapshots it (``Settings.summary()["config"]``), with
    :data:`SETUP` switched off in the file (config.yaml enables every strategy since 2026-10-05)."""
    config = load_app_config("config.yaml").model_dump(mode="json")
    for item in config["strategies"]["items"]:
        item.update({SETUP: {"enabled": False}}.get(item["name"], {}) | changes.get(item["name"], {}))
    with db.session() as sess:
        snap = sess.get(ConfigSnapshot, (engine_id, "c" * 32))
        assert snap is not None
        snap.payload = {"env": {}, "config": config, "config_hash": "c" * 32}
    return config


def beat(db: Database, engine_id: str, **payload: Any) -> None:
    with db.session() as sess:
        sess.merge(
            EngineHeartbeatRow(
                engine_id=engine_id,
                received_at=T,
                sent_at=T,
                run_id="r1",
                mode="PAPER",
                state="running",
                connected=True,
                market_open=True,
                payload={"at": T.isoformat(), **payload},
            )
        )


def by_name(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["name"]: s for s in body["strategies"]}


class TestStateAndParameters:
    def test_configured_strategies_with_effective_parameters(
        self, rig: tuple[TestClient, str, str], db: Database
    ) -> None:
        client, mine, _ = rig
        config = real_config(db, mine, **{SETUP: {"params": {"min_quality": 0.7}}})
        beat(db, mine, disabled_strategies=[])
        body = get(client, mine, "strategies").json()
        assert body["config_hash"] == "c" * 32 and body["mode"] == "PAPER" and body["remote_known"] is True
        assert [s["name"] for s in body["strategies"]] == [i["name"] for i in config["strategies"]["items"]]
        example, setup = by_name(body)[EXAMPLE], by_name(body)[SETUP]
        assert example["state"] == "ENABLED" and example["known"] is True and example["demo_only"] is True
        assert example["overrides"] == [] and example["params"]["expiry_bars"] == 1
        assert example["timeframes"] == [] and example["warmup_bars"] > 0  # only the configured ones
        assert body["timeframes"] == {"higher": "H1", "entry": "M15", "refinement": None}
        assert body["shared"] == {
            "cooldown_bars": 4,
            "signal_expiry_bars": 1,
            "allow_single_indicator_signals": False,
        }
        assert example["version"] and "Demonstration" in example["description"]
        assert setup["state"] == "DISABLED_CONFIG" and setup["overrides"] == ["min_quality"]
        assert setup["params"]["min_quality"] == 0.7 and len(setup["params"]) > 1

    def test_remote_disable_and_unknown_state(self, rig: tuple[TestClient, str, str], db: Database) -> None:
        client, mine, _ = rig
        real_config(db, mine)
        assert by_name(get(client, mine, "strategies").json())[EXAMPLE]["state"] == "UNKNOWN"  # no heartbeat
        beat(db, mine)  # an engine older than TAA-909 sends no list
        body = get(client, mine, "strategies").json()
        assert body["remote_known"] is False and by_name(body)[EXAMPLE]["state"] == "UNKNOWN"
        beat(db, mine, disabled_strategies=[EXAMPLE])
        body = get(client, mine, "strategies").json()
        assert by_name(body)[EXAMPLE]["state"] == "DISABLED_REMOTE"
        assert by_name(body)[SETUP]["state"] == "DISABLED_CONFIG"  # config wins: it never runs

    def test_unknown_strategy_and_invalid_overrides_show_the_configured_values(
        self, rig: tuple[TestClient, str, str], db: Database
    ) -> None:
        client, mine, _ = rig
        config = real_config(db, mine, **{SETUP: {"params": {"min_quality": "high"}}})
        config["strategies"]["items"].append(
            {"name": "from_a_newer_release", "enabled": True, "params": {"x": 1}}
        )
        with db.session() as sess:
            snap = sess.get(ConfigSnapshot, (mine, "c" * 32))
            assert snap is not None
            snap.payload = {"config": config}
        found = by_name(get(client, mine, "strategies").json())
        assert found["from_a_newer_release"]["known"] is False
        assert (
            found["from_a_newer_release"]["params"] == {"x": 1}
            and found["from_a_newer_release"]["version"] is None
        )
        assert found[SETUP]["known"] is False and found[SETUP]["params"] == {"min_quality": "high"}
        assert found[SETUP]["version"] is not None  # the class is known, its overrides are not valid here

    def test_no_run_yet(self, db: Database, clock: ManualClock) -> None:
        body = strategy_overview(db, "eng_none", clock.now_utc())
        assert body["strategies"] == [] and body["config_hash"] is None and body["remote_known"] is False


class TestPerformance:
    def test_closed_paper_trades_and_decisions_in_the_window(
        self, rig: tuple[TestClient, str, str], db: Database, clock: ManualClock
    ) -> None:
        client, mine, _ = rig
        real_config(db, mine, **{SETUP: {"enabled": True}})
        intent = PaperIntentRow  # the rig's positions 1-5 (net = ticket) and 10 (open); only p1 has an intent
        with db.session() as sess:
            template = sess.get(intent, (mine, "p1"))
            assert template is not None
            fields = {c.key: getattr(template, c.key) for c in intent.__table__.columns}
            for ticket in (2, 3, 4, 5, 10, 20):
                strategy = SETUP if ticket in (3, 20) else EXAMPLE
                sess.add(
                    intent(
                        **fields
                        | {
                            "intent_id": f"p{ticket}",
                            "idempotency_key": f"k{ticket}",
                            "order_id": ticket,
                            "strategy": strategy,
                        }
                    )
                )
            for ticket in (2, 4):
                pos = sess.get(PaperPositionRow, (mine, ticket))
                assert pos is not None
                pos.net, pos.r_multiple = -float(ticket), -1.0 if ticket == 2 else None
            old = position(mine, 20, exit_minutes=30, net=50.0)
            old.exit_time = clock.now_utc() - timedelta(days=40)  # outside the 30-day window
            sess.add(old)
            for i, (decision, codes) in enumerate(
                [
                    ("REJECT", ["SPREAD_TOO_HIGH", "BREAKER_OPEN:daily_loss"]),
                    ("REJECT", ["BREAKER_OPEN:spread"]),
                    ("HOLD", ["NO_SETUP"]),
                ]
            ):
                d1 = sess.get(DecisionRecordRow, (mine, "d1"))
                assert d1 is not None
                cols = {c.key: getattr(d1, c.key) for c in DecisionRecordRow.__table__.columns}
                sess.add(
                    DecisionRecordRow(
                        **cols | {"decision_id": f"x{i}", "decision": decision, "reason_codes": codes}
                    )
                )
        body = get(client, mine, "strategies").json()
        assert body["window"]["days"] == 30
        example = by_name(body)[EXAMPLE]
        perf = example["performance"]
        # tickets 1, 2, 4, 5: nets 1, -2, -4, 5; R from the rig's 1.0 except 2 (-1) and 4 (unknown)
        assert perf["trades"] == 4 and perf["wins"] == 2 and perf["losses"] == 2 and perf["open"] == 1
        assert perf["net"] == 0.0 and perf["win_rate"] == 0.5 and perf["profit_factor"] == 1.0
        assert perf["r_trades"] == 3 and abs(perf["avg_r"] - 1 / 3) < 1e-9 and perf["last_exit_at"]
        setup = by_name(body)[SETUP]["performance"]
        assert setup["trades"] == 1 and setup["net"] == 3.0 and setup["profit_factor"] is None
        decisions = example["decisions"]
        assert decisions["REJECT"] == 2 and decisions["HOLD"] == 1 and decisions["ACCEPT"] >= 0
        assert example["top_reject_reasons"][0] == {"code": "BREAKER_OPEN", "count": 2}
        assert {"code": "SPREAD_TOO_HIGH", "count": 1} in example["top_reject_reasons"]
        year = by_name(get(client, mine, "strategies?days=365").json())[SETUP]["performance"]
        assert year["trades"] == 2 and year["net"] == 53.0

    def test_window_bounds(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        for days in (0, 366, -1):
            assert get(client, mine, f"strategies?days={days}").status_code == 422

    def test_empty_strategy_has_no_ratios(self, rig: tuple[TestClient, str, str], db: Database) -> None:
        client, mine, _ = rig
        real_config(db, mine)
        perf = by_name(get(client, mine, "strategies").json())["setup_breakout"]["performance"]
        assert perf == {
            "trades": 0,
            "open": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "net": None,
            "profit_factor": None,
            "avg_r": None,
            "r_trades": 0,
            "last_exit_at": None,
        }


class TestLastCommand:
    def test_newest_disable_command_per_strategy(
        self, rig: tuple[TestClient, str, str], db: Database, clock: ManualClock
    ) -> None:
        client, mine, theirs = rig
        real_config(db, mine)
        queue = CommandQueue(db, clock)
        queue.enqueue(mine, "STRATEGY_DISABLE", {"strategy": EXAMPLE}, created_by="alice")
        clock.advance(1)
        newest = queue.enqueue(
            mine, "STRATEGY_DISABLE", {"strategy": EXAMPLE, "reason": "x"}, created_by="alice"
        )
        queue.enqueue(theirs, "STRATEGY_DISABLE", {"strategy": SETUP}, created_by="bob")
        found = by_name(get(client, mine, "strategies").json())
        assert found[EXAMPLE]["last_command"]["id"] == newest["id"]
        assert (
            found[EXAMPLE]["last_command"]["status"] == "QUEUED"
            and "totp" not in found[EXAMPLE]["last_command"]
        )
        assert found[SETUP]["last_command"] is None  # another engine's command
        clock.advance(300)
        assert by_name(get(client, mine, "strategies").json())[EXAMPLE]["last_command"]["status"] == "EXPIRED"


def test_run_row_is_the_latest(rig: tuple[TestClient, str, str], db: Database) -> None:
    client, mine, _ = rig
    real_config(db, mine)
    with db.session() as sess:
        sess.add(
            Run(engine_id=mine, run_id="r0", process="engine", mode="DEMO", version="0", config_hash="z" * 32)
        )
        run = sess.get(Run, (mine, "r0"))
        assert run is not None
        run.started_at = T - timedelta(days=1)
    assert get(client, mine, "strategies").json()["run_id"] == "r1"


def test_an_executed_disable_counts_before_the_next_heartbeat(
    rig: tuple[TestClient, str, str], db: Database, clock: ManualClock
) -> None:
    client, mine, _ = rig
    real_config(db, mine)
    beat(db, mine, disabled_strategies=[])  # received at T
    queue = CommandQueue(db, clock)
    cmd = queue.enqueue(mine, "STRATEGY_DISABLE", {"strategy": EXAMPLE}, created_by="alice")
    result = {
        "command_id": cmd["id"],
        "outcome": "EXECUTED",
        "detail": "disabled",
        "at": clock.now_utc().isoformat(),
    }
    assert queue.record_result(mine, result) is not None  # completed at the clock's now, after T
    assert by_name(get(client, mine, "strategies").json())[EXAMPLE]["state"] == "DISABLED_REMOTE"
    with db.session() as sess:  # a newer heartbeat without it: re-enabled locally since
        row = sess.get(EngineHeartbeatRow, mine)
        assert row is not None
        row.received_at = clock.now_utc() + timedelta(seconds=10)
    assert by_name(get(client, mine, "strategies").json())[EXAMPLE]["state"] == "ENABLED"
