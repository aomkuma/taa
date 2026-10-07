"""Manual MT5 trades matched to the signals they followed (PLAN §A34; TAA-1006)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.analytics.manual_match import Confidence, ManualFill, SignalCandidate, match, merge
from app.broker import mt5_constants as c
from app.broker.models import BrokerPosition, Deal
from app.core.clock import ManualClock
from app.core.enums import Side
from app.core.errors import BrokerError
from app.engine.manual_links import BACKFILL_SECONDS, ManualTradeLinker
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

    def test_a_closed_position_is_booked_from_its_deals(self, db: Database) -> None:
        clock = ManualClock(SYNC_T)
        linker = ManualTradeLinker(db, clock)
        linker.observe([position(1.1, SYNC_T, pid=79)])  # BUY at 1.1, stop 1.095: 1 R = 0.005

        def deal(entry: int, price: float, profit: float, ticket: int) -> Deal:
            return Deal(
                ticket=ticket, order=ticket, position_id=79, symbol="EURUSD", type=c.DEAL_TYPE_SELL,
                entry=entry, volume=0.1, price=price, profit=profit, commission=-0.35, swap=0.0, fee=0.0,
                magic=0, comment="", time_utc=SYNC_T + timedelta(hours=1),
            )  # fmt: skip

        history: list[Deal] = []
        assert linker.settle([79], lambda *_: history) == 0  # still open: nothing to book
        clock.advance(31)
        assert linker.settle([], lambda *_: history) == 0  # gone, but the exit is not in the history yet
        history.append(deal(c.DEAL_ENTRY_OUT, 1.1075, 75.0, 2))
        assert linker.settle([], lambda *_: history) == 0  # throttled
        clock.advance(31)
        assert linker.settle([], lambda *_: history) == 1
        with db.session() as sess:
            row = sess.scalars(select(ManualTradeLinkRow).where(ManualTradeLinkRow.position_id == 79)).one()
        assert (row.status, row.close_price, row.net_profit, row.r_multiple) == ("CLOSED", 1.1075, 74.65, 1.5)

    def test_a_link_without_a_stop_gets_the_positions_stop(self, db: Database) -> None:
        clock = ManualClock(SYNC_T)
        ManualTradeLinker(db, clock).observe([position(1.1, SYNC_T, pid=80)])
        with db.session() as sess:
            sess.scalars(select(ManualTradeLinkRow)).one().sl_initial = None  # an early (part 1) link
        ManualTradeLinker(db, clock).observe([position(1.1, SYNC_T, pid=80)])
        with db.session() as sess:
            assert sess.scalars(select(ManualTradeLinkRow)).one().sl_initial == 1.095

    def test_stop_changes_are_recorded_for_new_links(self, db: Database) -> None:
        clock = ManualClock(SYNC_T)
        linker = ManualTradeLinker(db, clock)
        moved = dataclasses.replace(position(1.1, SYNC_T, pid=81), sl=1.093)  # widened (BUY: lower stop)
        linker.observe([position(1.1, SYNC_T, pid=81)])
        clock.advance(60)
        linker.observe([moved])
        linker.observe([moved])  # unchanged: nothing new
        clock.advance(60)
        linker.observe([dataclasses.replace(moved, sl=0.0)])  # removed
        with db.session() as sess:
            row = sess.scalars(select(ManualTradeLinkRow)).one()
        assert [e["sl"] for e in row.stop_history or []] == [1.093, None]
        assert row.sl_initial == 1.095

    def test_links_made_before_the_history_stay_unknown(self, db: Database) -> None:
        clock = ManualClock(SYNC_T)
        ManualTradeLinker(db, clock).observe([position(1.1, SYNC_T, pid=82)])
        with db.session() as sess:
            sess.scalars(select(ManualTradeLinkRow)).one().stop_history = None
        later = dataclasses.replace(position(1.1, SYNC_T, pid=82), sl=1.09)
        ManualTradeLinker(db, clock).observe([later])
        with db.session() as sess:
            assert sess.scalars(select(ManualTradeLinkRow)).one().stop_history is None


def hist(
    pid: int,
    entry: int,
    price: float,
    at: datetime,
    *,
    volume: float = 0.1,
    profit: float = 0.0,
    magic: int = 0,
    kind: int = c.DEAL_TYPE_BUY,
) -> Deal:
    return Deal(
        ticket=pid * 10 + entry, order=pid, position_id=pid, symbol="EURUSD", type=kind, entry=entry,
        volume=volume, price=price, profit=profit, commission=-0.35, swap=0.0, fee=0.0, magic=magic,
        comment="", time_utc=at,
    )  # fmt: skip


class TestBackfill:
    """Manual trades that opened and closed while the engine did not watch, found in the deal history."""

    OPEN = SYNC_T + timedelta(minutes=5)
    CLOSE = SYNC_T + timedelta(hours=2)

    def bot(self, magic: int) -> bool:
        return 7_310_000 <= magic < 7_320_000

    def test_a_trade_never_seen_open_is_linked_and_closed(self, db: Database) -> None:
        with db.session() as sess:
            sess.add_all([r for r in sample_rows() if isinstance(r, OpportunityRow)])
        clock = ManualClock(SYNC_T + timedelta(hours=3))
        history = [
            hist(90, c.DEAL_ENTRY_IN, 1.1004, self.OPEN),
            hist(90, c.DEAL_ENTRY_OUT, 1.1075, self.CLOSE, profit=71.0, kind=c.DEAL_TYPE_SELL),
            Deal(1, 0, 0, "", c.DEAL_TYPE_BALANCE, 0, 0.0, 0.0, 1000.0, 0.0, 0.0, 0.0, 0, "", SYNC_T),
        ]
        assert ManualTradeLinker(db, clock).backfill([], lambda *_: history, self.bot) == 1
        with db.session() as sess:
            row = sess.scalars(select(ManualTradeLinkRow)).one()
        assert (row.position_id, row.side, row.volume, row.price_open) == (90, "BUY", 0.1, 1.1004)
        assert (row.confidence, row.opportunity_id) == ("HIGH", "k1")  # matched as it would have been live
        assert (row.status, row.close_price, row.net_profit) == ("CLOSED", 1.1075, 70.3)
        assert row.sl_initial is None and row.r_multiple is None  # the stop was never seen
        assert row.opened_at == self.OPEN and row.closed_at == self.CLOSE

    def test_open_partial_bot_known_and_older_positions_are_left_alone(self, db: Database) -> None:
        clock = ManualClock(SYNC_T + timedelta(hours=3))
        linker = ManualTradeLinker(db, clock)
        linker.observe([position(1.1, SYNC_T, pid=95)])  # seen open: settle() books it, not backfill()
        history = [
            hist(91, c.DEAL_ENTRY_IN, 1.1, self.OPEN),  # still open
            hist(92, c.DEAL_ENTRY_IN, 1.1, self.OPEN, volume=0.2),  # half closed, then gone from the book
            hist(92, c.DEAL_ENTRY_OUT, 1.101, self.CLOSE, volume=0.1),
            hist(93, c.DEAL_ENTRY_IN, 1.1, self.OPEN, magic=7_310_005),  # the bot's
            hist(93, c.DEAL_ENTRY_OUT, 1.101, self.CLOSE, magic=7_310_005),
            hist(94, c.DEAL_ENTRY_OUT, 1.101, self.CLOSE),  # opened before the window
            hist(95, c.DEAL_ENTRY_IN, 1.1, self.OPEN),
            hist(95, c.DEAL_ENTRY_OUT, 1.101, self.CLOSE),
        ]
        assert linker.backfill([91], lambda *_: history, self.bot) == 0
        with db.session() as sess:
            assert [r.position_id for r in sess.scalars(select(ManualTradeLinkRow))] == [95]

    def test_throttled_and_fails_closed(self, db: Database) -> None:
        clock = ManualClock(SYNC_T + timedelta(hours=3))
        linker = ManualTradeLinker(db, clock)
        calls: list[int] = []

        def failing(*_: datetime) -> list[Deal]:
            calls.append(1)
            raise BrokerError("history_deals_get failed")

        assert linker.backfill([], failing, self.bot) == 0
        assert linker.backfill([], failing, self.bot) == 0  # within BACKFILL_SECONDS: not asked again
        assert len(calls) == 1
        clock.advance(BACKFILL_SECONDS)
        history = [
            hist(96, c.DEAL_ENTRY_IN, 1.1, self.OPEN),
            hist(96, c.DEAL_ENTRY_OUT, 1.101, self.CLOSE),
        ]
        assert linker.backfill([], lambda *_: history, self.bot) == 1
        clock.advance(BACKFILL_SECONDS)
        assert linker.backfill([], lambda *_: history, self.bot) == 0  # linked once


def test_rank_lists_the_qualifying_signals_first() -> None:
    from app.analytics.manual_match import rank

    far = dataclasses.replace(BOT, key="k-far", entry=1.3215 + 0.002, decision_id="d4")
    ranked = rank(OWNER, [far, BOT, dataclasses.replace(BOT, key="k-buy", side=Side.BUY)])
    assert [r.candidate.key for r in ranked] == ["k-gbp", "k-far"]  # the BUY is not offered
    assert ranked[0].qualifies and not ranked[1].qualifies and ranked[1].score is None
