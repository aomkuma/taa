"""Manual MT5 trades matched to the signals they followed (PLAN §A34; TAA-1006)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.analytics.manual_match import Confidence, ManualFill, SignalCandidate, match, merge
from app.broker.models import BrokerPosition
from app.core.clock import ManualClock
from app.core.enums import Side
from app.engine.manual_links import ManualTradeLinker
from app.storage.database import Database
from app.storage.models import ManualTradeLinkRow, OpportunityRow
from tests.sync_data import T as SYNC_T
from tests.sync_data import sample_rows

T = datetime(2026, 10, 5, 15, 15, tzinfo=UTC)  # 22:15 Bangkok
M15 = 900

# 2026-10-05: the engine's PAPER #2 GBPUSD SELL at 1.32196 (stop 1.32308) and the owner's manual 0.1-lot SELL
# at 1.32167, four minutes later.
BOT = SignalCandidate(
    key="k-gbp",
    symbol="GBPUSD",
    side=Side.SELL,
    entry=1.32196,
    stop=1.32308,
    issued_at=T,
    expires_at=T + timedelta(minutes=30),
    bar_seconds=M15,
    strategy="setup_harmonic_prz",
    decision_id="d2",
)
OWNER = ManualFill(2078278005, "GBPUSD", Side.SELL, 1.32167, T + timedelta(minutes=4, seconds=57))


def test_the_owners_gbpusd_trade_follows_the_bots_signal() -> None:
    m = match(OWNER, [BOT])
    assert m.confidence is Confidence.HIGH and m.candidate is not None and m.candidate.decision_id == "d2"
    assert m.distance_r is not None and 0.25 < m.distance_r < 0.27
    assert m.score is not None and 0 < m.score <= 1


def test_the_same_signal_from_the_bot_and_an_alert_is_one_candidate() -> None:
    alert = dataclasses.replace(BOT, decision_id=None, opportunity_id="o9", expires_at=T + timedelta(hours=1))
    [one] = merge([BOT, alert])
    assert (one.decision_id, one.opportunity_id) == ("d2", "o9") and one.expires_at == alert.expires_at
    assert match(OWNER, [BOT, alert]).confidence is Confidence.HIGH


def test_unmatched_when_side_time_or_price_do_not_fit() -> None:
    assert match(dataclasses.replace(OWNER, side=Side.BUY), [BOT]).confidence is Confidence.UNMATCHED
    late = T + timedelta(minutes=30, seconds=M15 + 1)  # past expiry plus the one-bar grace
    assert match(dataclasses.replace(OWNER, opened_at=late), [BOT]).confidence is Confidence.UNMATCHED
    early = T - timedelta(seconds=1)
    assert match(dataclasses.replace(OWNER, opened_at=early), [BOT]).confidence is Confidence.UNMATCHED
    far = 1.32196 - 0.6 * 0.00112  # 0.6 R from the entry
    assert match(dataclasses.replace(OWNER, price_open=far), [BOT]).confidence is Confidence.UNMATCHED
    assert match(dataclasses.replace(OWNER, symbol="EURUSD"), [BOT]).confidence is Confidence.UNMATCHED


def test_a_fill_within_the_grace_bar_still_matches() -> None:
    within = T + timedelta(minutes=30, seconds=M15 - 1)
    assert match(dataclasses.replace(OWNER, opened_at=within), [BOT]).confidence is Confidence.HIGH


def test_two_qualifying_signals_keep_the_closer_one_as_likely() -> None:
    other = dataclasses.replace(
        BOT, key="k-other", entry=1.32205, decision_id="d3", strategy="setup_breakout"
    )
    m = match(OWNER, [other, BOT])
    assert m.confidence is Confidence.LIKELY and m.candidates == 2
    assert m.candidate is not None and m.candidate.decision_id == "d2"


def test_a_signal_without_a_stop_distance_is_skipped() -> None:
    flat = dataclasses.replace(BOT, stop=BOT.entry)
    assert match(OWNER, [flat]).confidence is Confidence.UNMATCHED


def position(price: float, opened: datetime, pid: int = 77) -> BrokerPosition:
    return BrokerPosition(
        ticket=pid,
        symbol="EURUSD",
        side=Side.BUY,
        volume=0.1,
        price_open=price,
        sl=1.095,
        tp=0.0,
        price_current=price,
        profit=0.0,
        swap=0.0,
        magic=0,
        comment="",
        time_utc=opened,
        identifier=pid,
    )


class TestLinker:
    """The engine's linker on stored opportunities (EURUSD BUY at 1.1, stop 1.095, M15, from tests/sync_data)."""

    def test_links_once_and_keeps_the_link_across_restarts(self, db: Database) -> None:
        with db.session() as sess:
            sess.add_all([r for r in sample_rows() if isinstance(r, OpportunityRow)])
        clock = ManualClock(SYNC_T + timedelta(minutes=5))
        linker = ManualTradeLinker(db, clock)
        row = linker.observe([position(1.1004, SYNC_T + timedelta(minutes=5))])[77]
        assert (row.confidence, row.opportunity_id, row.strategy) == ("HIGH", "k1", "example_trend_pullback")
        with db.session() as sess:  # a newer opportunity must not rewrite the stored link
            sess.query(OpportunityRow).delete()
        again = ManualTradeLinker(db, clock).observe([position(1.1004, SYNC_T + timedelta(minutes=5))])[77]
        assert again.confidence == "HIGH" and again.opportunity_id == "k1"
        with db.session() as sess:
            assert len(sess.scalars(select(ManualTradeLinkRow)).all()) == 1

    def test_a_trade_of_its_own_is_unmatched(self, db: Database) -> None:
        clock = ManualClock(SYNC_T)
        row = ManualTradeLinker(db, clock).observe([position(1.2, SYNC_T, pid=78)])[78]
        assert row.confidence == "UNMATCHED" and row.opportunity_id is None and row.decision_id is None
