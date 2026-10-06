"""Learning reports over the API: timing, expectancy, behavior; validation and ownership (TAA-L701/L801/L808)."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import HistoryCandle, ManualTradeLinkRow
from tests.web.test_data_api import rig  # noqa: F401  (fixture)


def test_timing_and_expectancy(rig: tuple[TestClient, str, str]) -> None:  # noqa: F811
    client, mine, theirs = rig
    t = client.get(f"/api/v1/engines/{mine}/learning/timing?scope=PAPER&days=366")
    assert t.status_code == 200
    doc = t.json()
    assert doc["scope"] == "PAPER" and doc["hypothetical"] in (True, False)
    assert {"overall", "groups", "trades", "lookahead_hours"} <= set(doc)
    for group in doc["overall"]:
        assert set(group["modes"]) == {"EARLY", "LATE", "STALL", "TF_MISMATCH", "WRONG", "OTHER", "UNKNOWN"}
    e = client.get(f"/api/v1/engines/{mine}/learning/expectancy?scope=SHADOW&days=90")
    assert e.status_code == 200
    assert {"overall", "previous", "change", "groups", "days"} <= set(e.json())
    assert client.get(f"/api/v1/engines/{theirs}/learning/timing").status_code == 404
    assert client.get(f"/api/v1/engines/{theirs}/learning/behavior").status_code == 404


def test_invalid_queries(rig: tuple[TestClient, str, str]) -> None:  # noqa: F811
    client, mine, _ = rig
    for route in ("timing?scope=LIVE", "timing?days=0", "expectancy?days=200", "behavior?days=400"):
        assert client.get(f"/api/v1/engines/{mine}/learning/{route}").status_code in (400, 422), route


def test_behavior_counts_off_plan_trades(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
    clock: ManualClock,
) -> None:
    client, mine, _ = rig
    now = clock.now_utc()
    with db.session() as sess:
        for pid, confidence, r in ((900001, "HIGH", 1.0), (900002, "UNMATCHED", -0.5)):
            sess.add(
                ManualTradeLinkRow(
                    engine_id=mine,
                    position_id=pid,
                    ticket=pid,
                    symbol="EURUSD",
                    side="BUY",
                    volume=0.1,
                    price_open=1.1000,
                    opened_at=now - timedelta(hours=5),
                    confidence=confidence,
                    candidates=0,
                    rule_version="1",
                    matched_at=now - timedelta(hours=5),
                    sl_initial=1.0950,
                    status="CLOSED",
                    closed_at=now - timedelta(hours=4),
                    close_price=1.1000 + 0.005 * r,
                    net_profit=50.0 * r,
                    r_multiple=r,
                )
            )
    doc = client.get(f"/api/v1/engines/{mine}/learning/behavior?days=30").json()
    patterns = {p["pattern"]: p for p in doc["patterns"]}
    assert doc["trades"] >= 2 and doc["hypothetical"] is True
    assert patterns["OFF_PLAN"]["count"] >= 1
    assert set(patterns) == {"EARLY_EXIT", "STOP_MOVED", "REVENGE", "OVERTRADING", "OFF_PLAN"}


def test_manual_timing_uses_the_bars_and_the_stop(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
    clock: ManualClock,
) -> None:
    client, mine, _ = rig
    now = clock.now_utc().replace(second=0, microsecond=0)
    opened = now - timedelta(hours=6)
    closed = opened + timedelta(hours=2)
    with db.session() as sess:
        sess.add(
            ManualTradeLinkRow(
                engine_id=mine,
                position_id=910001,
                ticket=910001,
                symbol="AUDUSD",
                side="BUY",
                volume=0.1,
                price_open=1.1000,
                opened_at=opened,
                confidence="UNMATCHED",
                candidates=0,
                rule_version="1",
                matched_at=opened,
                sl_initial=1.0950,
                stop_history=[],
                status="CLOSED",
                closed_at=closed,
                close_price=1.0950,
                net_profit=-50.0,
                r_multiple=-1.0,
            )
        )
        start = (opened - timedelta(hours=1)).replace(minute=0)
        for i in range(24):  # M15 bars from before the entry to after the exit, drifting down to the stop
            t = start + timedelta(minutes=15 * i)
            price = 1.1010 - 0.0003 * i
            sess.add(
                HistoryCandle(
                    engine_id=mine, server="FBS-Demo", symbol="AUDUSD", timeframe="M15", open_time=t,
                    time_server=int(t.timestamp()) + 3 * 3600, open=price, high=price + 0.0004,
                    low=price - 0.0004, close=price, tick_volume=10, spread=8,
                )
            )  # fmt: skip
    doc = client.get(f"/api/v1/engines/{mine}/learning/timing?scope=MANUAL&days=30").json()
    assert doc["scope"] == "MANUAL" and doc["trades"] >= 1 and doc["hypothetical"] is False
    (overall,) = doc["overall"]
    assert overall["losers"] >= 1
