"""The live shadow-trade tracker on FakeMT5 with a manual clock (TAA-6C1)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.advisory.lifecycle import OpportunityLifecycle
from app.advisory.shadow_tracker import ShadowTracker
from app.broker.fake_mt5 import FakeMT5
from app.broker.gateway import ReadOnlyMT5Gateway
from app.config import AppConfig
from app.core.clock import ManualClock
from app.core.enums import Side
from app.storage.database import Database
from app.storage.models import OpportunityRow, ShadowTradeRow
from app.storage.models.base import LOCAL_ENGINE
from tests.integration.test_engine_paper import harness
from tests.integration.test_lifecycle import CONFIG, WED, add
from tests.unit.test_market_data import setup

SLIP = 1.0  # points, config.yaml


def tracker(
    db: Database, cfg: AppConfig = CONFIG
) -> tuple[ShadowTracker, ManualClock, FakeMT5, ReadOnlyMT5Gateway]:
    clock, fake, gw = setup(WED)
    return ShadowTracker(db, gw, cfg, clock, server="FBS-Demo"), clock, fake, gw


def opportunity(db: Database, gw: ReadOnlyMT5Gateway, oid: str = "o1", **kw: Any) -> OpportunityRow:
    tick = gw.tick(kw.get("symbol", "EURUSD"))
    assert tick is not None
    quote = {"bid": tick.bid, "ask": tick.ask, "quote_at": tick.time_utc}
    add(db, gw, oid, **(quote | kw))
    with db.session() as sess:
        row = sess.get(OpportunityRow, (LOCAL_ENGINE, oid))
        assert row is not None
        return row


def shadows(db: Database) -> list[ShadowTradeRow]:
    with db.session() as sess:
        return list(sess.execute(select(ShadowTradeRow).order_by(ShadowTradeRow.shadow_id)).scalars())


class TestOpen:
    def test_every_opportunity_gets_plan_and_managed(self, db: Database) -> None:
        tr, _, _, gw = tracker(db)
        opp = opportunity(db, gw)
        report = tr.tick()
        assert report.opened == ("o1:PLAN", "o1:MANAGED")
        managed, plan = shadows(db)
        assert (plan.variant, managed.variant) == ("PLAN", "MANAGED")
        assert opp.ask is not None and opp.bid is not None
        assert plan.entry_price == pytest.approx(opp.ask + SLIP * 0.00001)
        assert plan.spread_points == pytest.approx((opp.ask - opp.bid) / 0.00001)
        assert plan.entry_at == opp.quote_at and plan.cursor == plan.entry_at.replace(second=0, microsecond=0)
        assert plan.deadline == plan.entry_at + timedelta(hours=72)
        assert (plan.lot, plan.equity, plan.source, plan.status) == (0.1, 10_000.0, "LIVE", "OPEN")
        assert plan.initial_sl == opp.stop_loss and plan.tp == opp.take_profit and plan.atr == opp.atr
        assert not plan.alerted and not plan.followed and plan.flags == []
        assert tr.tick(force=True).opened == ()  # idempotent

    def test_sell_enters_at_the_bid(self, db: Database) -> None:
        tr, _, _, gw = tracker(db)
        opp = opportunity(db, gw, side="SELL")
        tr.tick()
        assert opp.bid is not None
        assert shadows(db)[0].entry_price == pytest.approx(opp.bid - SLIP * 0.00001)

    def test_not_tradable_and_fallback_entry(self, db: Database) -> None:
        tr, _, _, gw = tracker(db)
        add(db, gw, "o1", lot=None)  # no recorded quote, no lot
        tr.tick()
        row = shadows(db)[0]
        assert set(row.flags) == {"ENTRY_FALLBACK", "NOT_TRADABLE"} and row.lot is None

    def test_a_fill_beyond_the_stop_is_void(self, db: Database) -> None:
        tr, _, _, gw = tracker(db)
        tick = gw.tick("EURUSD")
        assert tick is not None
        opportunity(db, gw, stop_loss=tick.ask + 0.0001)
        tr.tick()
        assert {r.status for r in shadows(db)} == {"VOID"}
        assert tr.resolve() == ([], 0)


class TestResolve:
    def test_resolution_on_m1_bars(self, db: Database) -> None:
        tr, clock, fake, gw = tracker(db)
        tick = gw.tick("EURUSD")
        assert tick is not None
        opportunity(db, gw, stop_loss=tick.bid - 0.0008, take_profit=tick.ask + 0.0016)
        tr.tick()
        clock.advance(72 * 3600 + 120)
        report = tr.tick()
        assert set(report.closed) == {"o1:PLAN", "o1:MANAGED"}
        for row in shadows(db):
            assert row.status == "CLOSED" and row.exit_reason in ("TP", "SL", "BE", "TRAIL", "TIME")
            assert row.exit_at is not None and row.exit_price is not None and row.r_multiple is not None
            assert row.win == (row.exit_reason == "TP")
            assert row.gross_pnl is not None and row.risk_money is not None and row.r_net is not None
            assert row.risk_money > 0 and row.mae_r is not None and row.mfe_r is not None
            assert row.net_pnl == pytest.approx(
                row.gross_pnl + (row.commission or 0) + (row.swap or 0), abs=0.02
            )
        plan = next(r for r in shadows(db) if r.variant == "PLAN")
        assert plan.exit_price is not None
        expected = gw.calc_profit(Side.BUY, "EURUSD", 0.1, plan.entry_price, plan.exit_price)
        assert plan.gross_pnl == pytest.approx(expected, abs=0.01)
        assert fake.calls["copy_rates_range"] >= 1
        assert tr.tick(force=True).closed == ()  # resolved once

    def test_restart_resumes_from_the_cursor(self, db: Database, tmp_path: Path) -> None:
        tr, clock, _, gw = tracker(db)
        opportunity(db, gw)
        tr.tick()
        clock.advance(20 * 60)
        tr.tick(force=True)
        cursor = shadows(db)[0].cursor
        assert cursor > WED  # progress was persisted
        clock.advance(72 * 3600)
        restarted = ShadowTracker(db, gw, CONFIG, clock, server="FBS-Demo")
        restarted.tick()

        straight = Database(f"sqlite:///{tmp_path / 'b.db'}")
        straight.create_all()
        tr2, clock2, _, gw2 = tracker(straight)
        opportunity(straight, gw2)
        tr2.tick()
        clock2.advance(20 * 60 + 72 * 3600)
        tr2.tick(force=True)
        keys = ("exit_reason", "exit_at", "exit_price", "r_multiple", "mae", "mfe", "gross_pnl")
        assert [[getattr(r, k) for k in keys] for r in shadows(db)] == [
            [getattr(r, k) for k in keys] for r in shadows(straight)
        ]
        straight.dispose()

    def test_only_closed_bars_are_used(self, db: Database) -> None:
        tr, clock, _, gw = tracker(db)
        opportunity(db, gw)
        tr.tick()
        before = shadows(db)[0].cursor
        clock.advance(30)  # WED is 10:00:30: the 10:00 bar closes at 10:01 (+ grace)
        tr.tick(force=True)
        assert shadows(db)[0].cursor == before
        clock.advance(35)
        tr.tick(force=True)
        assert shadows(db)[0].cursor == before + timedelta(minutes=1)

    def test_polling_cadence_and_budget(self, db: Database) -> None:
        tr, clock, _, gw = tracker(db)
        opportunity(db, gw)
        opportunity(db, gw, "o2", symbol="GBPUSD")
        tr.tick()
        clock.advance(10)
        assert tr.tick().opened == ()  # before poll_seconds: nothing happens
        closed, pending = tr.resolve(until_monotonic=clock.monotonic())  # no time left
        assert closed == [] and pending == 2

    def test_a_broker_failure_is_retried(self, db: Database) -> None:
        tr, clock, fake, gw = tracker(db)
        opportunity(db, gw)
        tr.tick()
        clock.advance(72 * 3600 + 120)
        fake.fail_next("copy_rates_range")
        assert tr.tick().closed == () and tr.stats.failures == 1
        assert {r.status for r in shadows(db)} == {"OPEN"}
        assert len(tr.tick(force=True).closed) == 2

    def test_ticks_are_only_read_for_ties_and_the_entry_minute(self, db: Database) -> None:
        tr, clock, fake, gw = tracker(db)
        opportunity(db, gw)
        tr.tick()
        clock.advance(3 * 60)
        tr.tick(force=True)
        # the entry minute once per variant; no tie in quiet minutes with a 50-pip stop
        assert fake.calls["copy_ticks_range"] == 2
        off = CONFIG.model_copy(
            update={
                "advisory": CONFIG.advisory.model_copy(
                    update={"shadow": CONFIG.advisory.shadow.model_copy(update={"tick_tiebreak": False})}
                )
            }
        )
        db2 = Database("sqlite://")
        db2.create_all()
        tr2, clock2, fake2, gw2 = tracker(db2, off)
        opportunity(db2, gw2)
        tr2.tick()
        clock2.advance(3 * 60)
        tr2.tick(force=True)
        assert fake2.calls["copy_ticks_range"] == 0 and "PARTIAL_BAR" in shadows(db2)[0].flags
        db2.dispose()


class TestFlags:
    def test_alerted_and_followed_are_copied(self, db: Database) -> None:
        tr, clock, _, gw = tracker(db)
        opportunity(db, gw)
        opportunity(db, gw, "o2")
        tr.tick()
        lifecycle = OpportunityLifecycle(db, gw, CONFIG, clock, server="FBS-Demo")
        assert lifecycle.mark_active("o1")
        with db.session() as sess:
            row = sess.get(OpportunityRow, (LOCAL_ENGINE, "o2"))
            assert row is not None
            row.status = "FOLLOWED"
        clock.advance(60)
        tr.tick()
        flags = {(r.opportunity_id, r.variant): (r.alerted, r.followed) for r in shadows(db)}
        assert flags[("o1", "PLAN")] == (True, False) and flags[("o2", "MANAGED")] == (False, True)

    def test_alerted_at_survives_expiry(self, db: Database) -> None:
        _, clock, _, gw = tracker(db)
        opportunity(db, gw)
        lifecycle = OpportunityLifecycle(db, gw, CONFIG, clock, server="FBS-Demo")
        lifecycle.mark_active("o1")
        clock.advance(3600)
        lifecycle.tick()
        with db.session() as sess:
            row = sess.get(OpportunityRow, (LOCAL_ENGINE, "o1"))
            assert row is not None and row.status == "EXPIRED" and row.alerted_at == WED


class TestEngine:
    def test_the_engine_tracks_shadow_trades(self, tmp_path: Path) -> None:
        h = harness(tmp_path, advisory=CONFIG.advisory)
        h.engine.start()
        assert h.engine.shadow is not None
        h.engine.run(max_cycles=3)
        status = h.engine.status()["shadow"]
        assert status["failures"] == 0 and h.engine.last_error == ""

    def test_a_tracker_failure_never_stops_the_engine(self, tmp_path: Path) -> None:
        h = harness(tmp_path, advisory=CONFIG.advisory)
        h.engine.start()
        assert h.engine.shadow is not None

        def boom(**_: object) -> None:
            raise RuntimeError("shadow exploded")

        h.engine.shadow.tick = boom  # type: ignore[method-assign]
        h.engine.run(max_cycles=2)
        assert h.engine.last_error == "" and h.engine.status()["shadow"]["last_error"].startswith(
            "RuntimeError"
        )


class TestIntegration:
    def test_opportunities_record_the_calibration_version(self, db: Database) -> None:
        from tests.integration.test_scanner import scanner

        s, _, _ = scanner(db)
        s.calibration_version = lambda: "20261004T230000Z-abc"
        s.tick()
        with db.session() as sess:
            versions = set(sess.execute(select(OpportunityRow.calibration_version)).scalars())
        assert versions == {"20261004T230000Z-abc"}

    def test_the_engine_feeds_s8_and_stamps_versions(self, tmp_path: Path) -> None:
        from app.advisory.calibration import LoadedCalibration
        from app.advisory.confidence import BucketModel, WinProbability
        from app.advisory.stats import EdgeBook

        h = harness(tmp_path, advisory=CONFIG.advisory)
        h.engine.start()
        assert h.engine.ranking is not None and isinstance(h.engine.ranking.edge_source, EdgeBook)
        assert h.engine.calibration is not None and h.engine.scanner is not None
        h.engine.calibration.current = LoadedCalibration("v-test", WED, WinProbability(BucketModel()), 0, 0)
        assert h.engine.scanner.calibration_version() == "v-test"
        h.engine.shutdown()


def with_modes(cfg: AppConfig = CONFIG, **modes: Any) -> AppConfig:
    data = cfg.model_dump(mode="json")
    data["advisory"]["shadow"]["entry_modes"] = {
        "variants": ["PULLBACK", "WIDE_STOP", "PULLBACK_WIDE"]
    } | modes
    return AppConfig.model_validate(data)


class TestEntryModes:
    """TAA-L702: entry-mode variants beside PLAN and MANAGED (off by default)."""

    def test_variants_open_beside_plan_and_resolve(self, db: Database) -> None:
        tr, clock, _, gw = tracker(db, with_modes())
        opportunity(db, gw)
        report = tr.tick()
        assert report.opened == ("o1:PLAN", "o1:MANAGED", "o1:PULLBACK", "o1:WIDE_STOP", "o1:PULLBACK_WIDE")
        rows = {r.variant: r for r in shadows(db)}
        plan, wide, pull, pw = rows["PLAN"], rows["WIDE_STOP"], rows["PULLBACK"], rows["PULLBACK_WIDE"]
        risk = plan.entry_price - plan.initial_sl
        assert wide.status == "OPEN" and wide.entry_price == plan.entry_price and wide.tp == plan.tp
        assert wide.initial_sl == pytest.approx(plan.entry_price - 2 * risk) and wide.lot == pytest.approx(
            0.05
        )
        for row in (pull, pw):
            assert row.status == "PENDING" and row.tp == plan.tp
            assert row.entry_price == pytest.approx(plan.entry_price - 0.5 * risk)
            assert row.entry_window_end == plan.entry_at + timedelta(minutes=60)
        assert pull.initial_sl == plan.initial_sl
        assert pw.initial_sl == pytest.approx(plan.entry_price - 2 * risk)
        clock.advance(72 * 3600 + 120)
        tr.tick()
        for row in shadows(db):
            assert row.status in ("CLOSED", "MISSED"), row.shadow_id
            if row.status == "MISSED":
                assert row.r_net is None and row.exit_at is None and "not filled" in row.note
            elif row.variant.startswith("PULLBACK"):
                assert row.entry_at >= plan.entry_at.replace(second=0, microsecond=0)
                assert row.entry_at < plan.entry_at + timedelta(minutes=60)
        assert tr.tick(force=True).closed == ()

    def test_a_limit_out_of_reach_is_missed_after_its_window(self, db: Database) -> None:
        tr, clock, _, gw = tracker(
            db,
            with_modes(
                variants=["PULLBACK_WIDE"],
                pullback_depth_r=0.99,
                pullback_wide_stop_r=3.0,
                entry_window_bars=1,
            ),
        )
        opportunity(db, gw, stop_loss=gw.tick("EURUSD").ask - 0.0400)  # type: ignore[union-attr]
        tr.tick()
        clock.advance(20 * 60)
        tr.tick(force=True)
        row = next(r for r in shadows(db) if r.variant == "PULLBACK_WIDE")
        assert row.status == "MISSED" and row.cursor >= row.entry_window_end  # type: ignore[operator]

    def test_off_by_default(self, db: Database) -> None:
        tr, _, _, gw = tracker(db)
        opportunity(db, gw)
        assert tr.tick().opened == ("o1:PLAN", "o1:MANAGED")
