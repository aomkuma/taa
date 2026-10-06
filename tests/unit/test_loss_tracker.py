from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.broker import mt5_constants as c
from app.broker.models import Deal
from app.config import RiskConfig
from app.core.clock import ManualClock
from app.risk.loss_tracker import LossStatus, LossTracker, loss_checks, period_keys
from app.storage.database import Database

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)  # Wednesday, 13:00 broker time (EEST)
BOT = 7_310_000


def deal(
    ticket: int,
    *,
    profit: float = 0.0,
    at: datetime = T0,
    type_: int = c.DEAL_TYPE_SELL,
    entry: int = c.DEAL_ENTRY_OUT,
    magic: int = BOT,
    commission: float = 0.0,
) -> Deal:
    return Deal(
        ticket=ticket,
        order=ticket,
        position_id=ticket,
        symbol="EURUSD",
        type=type_,
        entry=entry,
        volume=0.1,
        price=1.1,
        profit=profit,
        commission=commission,
        swap=0.0,
        fee=0.0,
        magic=magic,
        comment="",
        time_utc=at,
    )


def cash(ticket: int, amount: float, at: datetime) -> Deal:
    return deal(ticket, profit=amount, at=at, type_=c.DEAL_TYPE_BALANCE, entry=c.DEAL_ENTRY_IN, magic=0)


def bot(d: Deal) -> bool:
    return d.magic == BOT


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(T0)


def tracker(db: Database, clock: ManualClock) -> LossTracker:
    return LossTracker(db, "acct", "Europe/Athens", clock)


class TestPeriods:
    def test_broker_midnight_and_iso_week(self) -> None:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Athens")
        assert period_keys(datetime(2026, 9, 30, 20, 59, tzinfo=UTC), tz) == ("2026-09-30", "2026-W40")
        assert period_keys(datetime(2026, 9, 30, 21, 0, tzinfo=UTC), tz) == ("2026-10-01", "2026-W40")
        assert period_keys(datetime(2026, 10, 4, 21, 0, tzinfo=UTC), tz) == (
            "2026-10-05",
            "2026-W41",
        )  # Monday
        # winter time (EET, +2): midnight is 22:00 UTC
        assert period_keys(datetime(2026, 11, 4, 21, 30, tzinfo=UTC), tz)[0] == "2026-11-04"

    def test_new_day_takes_a_new_baseline(self, db: Database, clock: ManualClock) -> None:
        t = tracker(db, clock)
        t.observe(10_000)
        assert t.observe(9_900).day_pnl == pytest.approx(-100)
        clock.set(datetime(2026, 9, 30, 21, 0, 1, tzinfo=UTC))
        status = t.observe(9_850)
        assert status.day_key == "2026-10-01"
        assert status.day_pnl == 0.0
        assert status.week_pnl == pytest.approx(-150)


class TestCashFlows:
    def test_deposit_and_withdrawal_never_move_pnl(self, db: Database, clock: ManualClock) -> None:
        t = tracker(db, clock)
        t.observe(10_000)
        clock.advance(60)
        s = t.observe(11_000, [cash(1, 1_000, clock.now_utc())])
        assert s.day_pnl == pytest.approx(0)
        assert s.drawdown_percent == 0.0
        clock.advance(60)
        s = t.observe(8_000, [cash(2, -3_000, clock.now_utc())])
        assert s.day_pnl == pytest.approx(0)
        assert s.week_pnl == pytest.approx(0)
        assert s.drawdown_percent == pytest.approx(0)

    def test_flow_before_the_baseline_is_already_in_it(self, db: Database, clock: ManualClock) -> None:
        early = cash(1, 500, T0 - timedelta(hours=1))
        s = tracker(db, clock).observe(10_500, [early])
        assert s.day_start == pytest.approx(10_500)

    def test_flows_before_tracking_began_are_inside_the_first_equity(
        self, db: Database, clock: ManualClock
    ) -> None:
        opening = cash(1, 1_000, T0 - timedelta(days=1))  # the account's opening deposit, in the deal history
        t = tracker(db, clock)
        s = t.observe(1_080, [opening])
        assert (s.hwm, s.drawdown_percent, s.day_pnl) == (1_080, 0.0, 0.0)
        clock.advance(60)
        s = t.observe(1_580, [opening, cash(2, 500, clock.now_utc())])  # a real later deposit still counts
        assert s.drawdown_percent == 0.0 and s.day_pnl == pytest.approx(0)

    def test_each_deal_is_booked_once(self, db: Database, clock: ManualClock) -> None:
        t = tracker(db, clock)
        t.observe(10_000)
        flow = cash(1, 1_000, T0 + timedelta(seconds=1))
        clock.advance(5)
        t.observe(11_000, [flow])
        s = t.observe(11_000, [flow])
        assert s.day_pnl == pytest.approx(0)
        assert tracker(db, clock).observe(11_000, [flow]).day_pnl == pytest.approx(0)  # after a restart


class TestHighWaterMark:
    def test_drawdown_from_the_peak(self, db: Database, clock: ManualClock) -> None:
        t = tracker(db, clock)
        t.observe(10_000)
        t.observe(12_000)
        s = t.observe(10_800)
        assert s.hwm == 12_000
        assert s.drawdown_percent == pytest.approx(10.0)

    def test_hwm_survives_a_restart(self, db: Database, clock: ManualClock) -> None:
        tracker(db, clock).observe(12_000)
        assert tracker(db, clock).observe(11_400).drawdown_percent == pytest.approx(5.0)


class TestConsecutiveLosses:
    def test_streak(self, db: Database, clock: ManualClock) -> None:
        t = tracker(db, clock)
        deals = [
            deal(1, profit=-10),
            deal(2, profit=-5, commission=-1),
            deal(3, profit=0.0),  # flat: no change
            deal(4, profit=-2, magic=0),  # manual trade: ignored
            deal(5, profit=-3, entry=c.DEAL_ENTRY_IN),  # opening deal: ignored
        ]
        assert t.observe(10_000, deals, is_bot=bot).consecutive_losses == 2
        assert t.observe(10_000, [deal(6, profit=4, commission=-1)], is_bot=bot).consecutive_losses == 0

    def test_net_of_costs(self, db: Database, clock: ManualClock) -> None:
        s = tracker(db, clock).observe(10_000, [deal(1, profit=1.0, commission=-1.5)], is_bot=bot)
        assert s.consecutive_losses == 1

    def test_streak_survives_restart_and_manual_reset(self, db: Database, clock: ManualClock) -> None:
        tracker(db, clock).observe(10_000, [deal(1, profit=-1), deal(2, profit=-1)], is_bot=bot)
        again = tracker(db, clock)
        assert again.observe(10_000, [deal(1, profit=-1)], is_bot=bot).consecutive_losses == 2
        again.reset_consecutive_losses()
        assert again.observe(10_000).consecutive_losses == 0


def status(**kw: object) -> LossStatus:
    base: dict[str, object] = {
        "as_of": T0,
        "equity": 10_000.0,
        "day_key": "2026-09-30",
        "week_key": "2026-W40",
        "day_start": 10_000.0,
        "week_start": 10_000.0,
        "hwm": 10_000.0,
        "adjusted_equity": 10_000.0,
        "consecutive_losses": 0,
        "last_loss_at": None,
    }
    base.update(kw)
    return LossStatus(**base)  # type: ignore[arg-type]


class TestChecks:
    def failing(self, s: LossStatus) -> list[str]:
        return [ch.reason.value for ch in loss_checks(s, RiskConfig()) if not ch.passed]

    def test_healthy(self) -> None:
        assert self.failing(status()) == []

    @pytest.mark.parametrize(
        ("kw", "reason"),
        [
            ({"equity": 9_800.0, "adjusted_equity": 9_800.0}, "DAILY_LOSS_LIMIT"),
            ({"equity": 9_850.0, "day_start": 10_000.0, "week_start": 10_300.0}, "WEEKLY_LOSS_LIMIT"),
            ({"hwm": 11_200.0}, "MAX_DRAWDOWN"),
        ],
    )
    def test_limits(self, kw: dict[str, object], reason: str) -> None:
        assert reason in self.failing(status(**kw))

    def test_just_under_the_daily_limit_passes(self) -> None:
        assert self.failing(status(equity=9_801.0, adjusted_equity=9_801.0)) == []

    def test_streak_pauses_for_24h(self) -> None:
        s = status(consecutive_losses=4, last_loss_at=T0 - timedelta(hours=23))
        assert self.failing(s) == ["CONSECUTIVE_LOSSES"]
        assert self.failing(status(consecutive_losses=4, last_loss_at=T0 - timedelta(hours=25))) == []
        assert self.failing(status(consecutive_losses=3, last_loss_at=T0)) == []
