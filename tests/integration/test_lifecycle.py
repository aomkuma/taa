"""Market windows and the opportunity lifecycle with a manual clock on FakeMT5 (TAA-6B4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.advisory.lifecycle import OpportunityLifecycle, OpportunityStatus, market_window
from app.broker.gateway import ReadOnlyMT5Gateway
from app.config import AppConfig, BlackoutWindow, load_settings
from app.core.enums import Timeframe
from app.news.calendar import ManualBlackouts, NewsFilter
from app.storage.database import Database
from app.storage.models import OpportunityRow
from tests.integration.test_scanner import scanner
from tests.unit.test_market_data import ENV, setup

WED = datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC)
BAR = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
CONFIG = load_settings(env_file=None, config_file="config.yaml", environ=ENV).config


def rig(db: Database, cfg: AppConfig = CONFIG, news: NewsFilter | None = None, at: datetime = WED):  # type: ignore[no-untyped-def]
    clock, fake, gw = setup(at)
    return OpportunityLifecycle(db, gw, cfg, clock, server="FBS-Demo", news=news), clock, fake, gw


def add(db: Database, gw: ReadOnlyMT5Gateway, oid: str, **kw: Any) -> None:
    tick = gw.tick(kw.get("symbol", "EURUSD"))
    assert tick is not None
    side = kw.get("side", "BUY")
    entry = tick.ask if side == "BUY" else tick.bid
    sign = 1 if side == "BUY" else -1
    fields: dict[str, Any] = {
        "opportunity_id": oid,
        "server": "FBS-Demo",
        "strategy": "s",
        "symbol": "EURUSD",
        "asset_class": "FOREX_MAJOR",
        "timeframe": "M15",
        "side": side,
        "bar_close_at": BAR,
        "created_at": WED,
        "signal_expires_at": BAR + timedelta(minutes=15),
        "entry": entry,
        "stop_loss": entry - sign * 0.0050,
        "take_profit": entry + sign * 0.0100,
        "rr": 2.0,
        "setup_strength": 70.0,
        "score": 50.0,
        "status": "CANDIDATE",
        "status_reason": "",
        "status_at": WED,
        "decision_id": "d",
        "warnings": [],
        "lot": 0.1,
        "risk_money": 50.0,
        "reward_money": 100.0,
        "equity": 10_000.0,
        "currency": "USD",
        "session": "LONDON",
        "regime": "TRENDING",
        "atr": 0.0100,
        "spread_points": 12.0,
        "requirements_version": "v",
        "features": {},
        "signal": {},
    } | kw
    with db.session() as sess:
        sess.add(OpportunityRow(**fields))


def get(db: Database, oid: str) -> OpportunityRow:
    with db.session() as sess:
        row = sess.get(OpportunityRow, oid)
        assert row is not None
        return row


class TestWindow:
    def test_earliest_wins_with_its_reason(self) -> None:
        base = {"bar_close": BAR, "timeframe": Timeframe.M15, "lifetime_bars": 2, "session_name": "LONDON"}
        assert market_window(**base, session_end=None, next_blackout=None) == (
            BAR + timedelta(minutes=30),
            "SIGNAL_LIFETIME",
        )
        end = BAR + timedelta(minutes=20)
        assert market_window(**base, session_end=end, next_blackout=None) == (end, "SESSION_END:LONDON")
        news = BAR + timedelta(minutes=10)
        assert market_window(**base, session_end=end, next_blackout=news) == (news, "NEWS_BLACKOUT")

    def test_window_from_lifetime_session_and_news(self, db: Database) -> None:
        lc, _, _, gw = rig(db)
        add(db, gw, "a")
        lc.tick()
        row = get(db, "a")
        assert row.valid_until == BAR + timedelta(minutes=30) and row.valid_reason == "SIGNAL_LIFETIME"
        late = datetime(2026, 9, 30, 20, 50, tzinfo=UTC)  # New York closes at 21:00 UTC (EDT)
        add(db, gw, "b", bar_close_at=late - timedelta(minutes=5), created_at=late)
        lc.tick()
        row = get(db, "b")
        assert row.valid_until == datetime(2026, 9, 30, 21, 0, tzinfo=UTC)
        assert row.valid_reason == "SESSION_END:NEW_YORK"
        blackout = BlackoutWindow(
            start_utc=WED + timedelta(minutes=10), end_utc=WED + timedelta(hours=1), currencies=["USD"]
        )
        lc.news = NewsFilter(ManualBlackouts([blackout]))
        add(db, gw, "c")
        lc.tick()
        assert get(db, "c").valid_reason == "NEWS_BLACKOUT"


class TestTransitions:
    def test_expiry(self, db: Database) -> None:
        lc, clock, _, gw = rig(db)
        add(db, gw, "a")
        assert lc.tick() == []
        clock.set(BAR + timedelta(minutes=30))
        [t] = lc.tick()
        assert t.status is OpportunityStatus.EXPIRED and t.reason == "SIGNAL_LIFETIME"
        row = get(db, "a")
        assert row.status == "EXPIRED" and row.status_reason == "SIGNAL_LIFETIME"
        assert lc.tick() == []  # terminal states stay

    def test_stop_touched_before_entry(self, db: Database) -> None:
        lc, _, _, gw = rig(db)
        tick = gw.tick("EURUSD")
        assert tick is not None
        add(db, gw, "a", stop_loss=tick.bid + 0.0001, atr=None)
        [t] = lc.tick()
        assert t.status is OpportunityStatus.INVALIDATED and t.reason == "SL_TOUCHED"

    def test_price_drift(self, db: Database) -> None:
        lc, _, _, gw = rig(db)
        tick = gw.tick("EURUSD")
        assert tick is not None
        add(db, gw, "a", entry=tick.ask - 0.0011, stop_loss=tick.ask - 0.0100, atr=0.0020)
        [t] = lc.tick()
        assert t.reason == "PRICE_DRIFT"

    def test_spread_must_stay_wide_for_30_seconds(self, db: Database) -> None:
        cfg = CONFIG.model_copy(update={"risk": CONFIG.risk.model_copy(update={"max_spread_points": 0.5})})
        lc, clock, _, gw = rig(db, cfg)
        add(db, gw, "a", atr=None)
        assert lc.tick() == []  # the spike starts
        clock.advance(20)
        assert lc.tick() == []
        clock.advance(11)
        [t] = lc.tick()
        assert t.reason == "SPREAD_SPIKE"

    def test_opposite_signal(self, db: Database) -> None:
        lc, _, _, gw = rig(db)
        add(db, gw, "buy", atr=None)
        lc.tick()
        add(db, gw, "sell", side="SELL", created_at=WED + timedelta(seconds=1), atr=None)
        transitions = lc.tick()
        assert [(t.opportunity_id, t.reason) for t in transitions] == [("buy", "OPPOSITE_SIGNAL")]
        assert get(db, "sell").status == "CANDIDATE"

    def test_followed_by_a_manual_position(self, db: Database) -> None:
        lc, clock, fake, gw = rig(db)
        add(db, gw, "a", atr=None)
        lc.tick()
        clock.advance(120)
        opened = clock.now_utc()
        fake.add_position(
            ticket=4242, symbol="EURUSD", type=0, volume=0.05, price_open=1.1, sl=0.0, tp=0.0,
            price_current=1.1, profit=0.0, swap=0.0, magic=0, comment="",
            time=gw.server_clock.utc_to_server_epoch(opened),
        )  # fmt: skip
        [t] = lc.tick()
        assert t.status is OpportunityStatus.FOLLOWED and t.reason == "position 4242"

    def test_bot_positions_and_other_sides_are_not_followed(self, db: Database) -> None:
        lc, _, fake, gw = rig(db)
        add(db, gw, "a", atr=None)
        for ticket, side, magic in ((1, 1, 0), (2, 0, 7_310_000)):
            fake.add_position(
                ticket=ticket, symbol="EURUSD", type=side, volume=0.05, price_open=1.1, sl=0.0, tp=0.0,
                price_current=1.1, profit=0.0, swap=0.0, magic=magic, comment="",
                time=gw.server_clock.utc_to_server_epoch(WED),
            )  # fmt: skip
        assert lc.tick() == []


class TestRestartAndActive:
    def test_catch_up_expires_passed_windows_only(self, db: Database) -> None:
        lc, clock, _, gw = rig(db)
        add(db, gw, "old", atr=None)
        add(
            db,
            gw,
            "new",
            bar_close_at=BAR + timedelta(hours=3),
            created_at=WED + timedelta(hours=3),
            atr=None,
        )
        lc.tick()
        clock.set(BAR + timedelta(hours=2))  # the engine was down; "old" passed its window meanwhile
        restarted = OpportunityLifecycle(db, lc.gateway, CONFIG, clock, server="FBS-Demo")
        [t] = restarted.catch_up()
        assert (t.opportunity_id, t.status, t.reason) == ("old", OpportunityStatus.EXPIRED, "SIGNAL_LIFETIME")
        assert get(db, "new").status == "CANDIDATE"

    def test_mark_active(self, db: Database) -> None:
        lc, clock, _, gw = rig(db)
        add(db, gw, "a", atr=None)
        assert lc.mark_active("a") and get(db, "a").status == "ACTIVE"
        assert not lc.mark_active("a") and not lc.mark_active("missing")
        clock.set(BAR + timedelta(minutes=31))
        lc.tick()
        assert get(db, "a").status == "EXPIRED"


def test_scanner_and_lifecycle_end_to_end(db: Database) -> None:
    s, clock, _ = scanner(db)
    lc = OpportunityLifecycle(db, s.gateway, CONFIG, clock, server="FBS-Demo", lifetime_bars=lambda: 1)
    created = s.tick().created
    assert len(created) == 2
    lc.tick()
    with db.session() as sess:
        windows = {r.valid_until for r in sess.execute(select(OpportunityRow)).scalars()}
    assert windows == {BAR + timedelta(minutes=15)}
    clock.set(BAR + timedelta(minutes=15))
    statuses = {t.status for t in lc.tick()}
    assert statuses <= {OpportunityStatus.EXPIRED, OpportunityStatus.INVALIDATED}
    with db.session() as sess:
        assert not sess.execute(select(OpportunityRow).where(OpportunityRow.status == "CANDIDATE")).first()
