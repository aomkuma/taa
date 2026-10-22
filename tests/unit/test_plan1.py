"""Setup OWN PLAN-1 as the ``plan1`` lane (app/strategy/plan1.py): the London ORB on closed M1 bars and the NY
08:30 straddle every weekday. Every expected number is worked by hand in the comments."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.core.enums import Action, ExitReason, Side, Timeframe
from app.news.releases import Release
from app.strategy import plan1
from app.strategy.catalog import default_registry
from app.strategy.plan1 import (
    DailyStraddle,
    Plan1Orb,
    Plan1OrbParams,
    Plan1Straddle,
    Plan1StraddleParams,
    broken_pools,
    daily_release,
    h1_atr_at,
    h4_atr_change,
    orb_decide,
    pools,
)
from app.strategy.signal_models import MarketContext, OpenPosition, ReasonCode, StrategyContext
from tests.risk_data import XAUUSD_SPEC
from tests.unit.test_strategy_models import state

T0 = pd.Timestamp("2026-09-30 06:00", tz="UTC")  # Wednesday, 13:00 Thai: the London ORB's open


def utc(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz="UTC")


def frame(
    start: str, end_open: str, *, o: float = 4000.0, half: float = 5.0, special: dict | None = None
) -> pd.DataFrame:
    """M1 bars opening every minute from *start* to *end_open* (both included): open = close = *o*, high / low
    *o* +- *half*; *special*: open time -> (open, high, low, close)."""
    opens = pd.date_range(utc(start), utc(end_open), freq="1min")
    df = pd.DataFrame(
        {"open": o, "high": o + half, "low": o - half, "close": o, "spread": 30.0},
        index=opens,
    )
    for at, (a, b, c, d) in (special or {}).items():
        df.loc[utc(at), ["open", "high", "low", "close"]] = [a, b, c, d]
    df.insert(0, "open_time", df.index)
    df.index = df.index + pd.Timedelta(minutes=1)  # indexed by the close time, as the context builder does
    return df


def h1_days(ranges: list[float], first: str = "2026-09-01", close: float = 4000.0) -> pd.DataFrame:
    """H1 bars of consecutive server days (Athens midnight to midnight, 24 bars each): day k trades close +- ranges[k]
    / 2 and closes at *close*, so its true range is ranges[k]."""
    rows = []
    for k, r in enumerate(ranges):
        start = pd.Timestamp(first, tz="Europe/Athens") + pd.Timedelta(days=k)
        for hr in range(24):
            t = (start + pd.Timedelta(hours=hr)).tz_convert("UTC")
            rows.append((t, close, close + r / 2, close - r / 2, close))
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close"])
    df.index = df.open_time + pd.Timedelta(hours=1)
    return df


def wide_h1(at: datetime | pd.Timestamp) -> pd.DataFrame:
    """30 days of 100-USD days before *at*: the D1 ATR(20) is 100 (the regime switch is on)."""
    day = pd.Timestamp(at).tz_convert("Europe/Athens").normalize() - pd.Timedelta(days=31)
    df = h1_days([100.0] * 31, f"{day:%Y-%m-%d}")
    return df[df.index <= pd.Timestamp(at)]


def arrays(df: pd.DataFrame) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return plan1._m1_arrays(df)


# --- the H1 ATR ---------------------------------------------------------------------------------------------


class TestH1Atr:
    @staticmethod
    def hours() -> pd.DataFrame:
        """16 hours from 00:00: hour i trades 100+i .. 102+i and closes 101+i (true range 2 against the
        previous close 100+i); hour 15 gaps up to 116 .. 120 from the previous close 115: true range 120 - 115
        = 5 (its high - low is only 4)."""
        rows = []
        for i in range(16):
            lo, hi, c = (116.0, 120.0, 118.0) if i == 15 else (100.0 + i, 102.0 + i, 101.0 + i)
            for m in range(60):
                rows.append((utc("2026-09-30") + pd.Timedelta(hours=i, minutes=m), c, hi, lo, c))
        df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close"])
        df.index = df.open_time + pd.Timedelta(minutes=1)
        return df

    def test_mt5_atr_of_complete_hours(self) -> None:
        opens, _, h, lo, c = arrays(self.hours())
        # at 16:00 the last 14 true ranges are hours 2..15: (13 x 2 + 5) / 14
        assert h1_atr_at(opens, h, lo, c, utc("2026-09-30 16:00")) == pytest.approx(31 / 14)
        # hour 15 is not complete before 16:00: hours 1..14, all 2
        assert h1_atr_at(opens, h, lo, c, utc("2026-09-30 15:59")) == pytest.approx(2.0)
        # 14 complete hours give 13 true ranges: not ready
        assert np.isnan(h1_atr_at(opens, h, lo, c, utc("2026-09-30 14:00")))


# --- the opening range ------------------------------------------------------------------------------------


def orb_bars(**extra: tuple[float, float, float, float]) -> pd.DataFrame:
    """Flat 4000 +- 5 before 06:00; the range bars 06:00-06:14 at 4000 +- 1 with a high 4004 at 06:05 and a
    low 3998 at 06:10 (range 3998-4004, width 6); after it 4000 +- 1 unless *extra* says otherwise."""
    special = {f"2026-09-30 06:{m:02d}": (4000.0, 4001.0, 3999.0, 4000.0) for m in range(60)}
    special |= {"2026-09-30 06:05": (4000.0, 4004.0, 3999.0, 4000.0)}
    special |= {"2026-09-30 06:10": (4000.0, 4001.0, 3998.0, 4000.0)}
    special |= {f"2026-09-30 {k[1:3]}:{k[4:]}": v for k, v in extra.items()}
    return frame("2026-09-29 00:00", "2026-09-30 06:59", special=special)


class TestOrbDecide:
    P = Plan1OrbParams()

    def decide(self, df: pd.DataFrame, atr: float = 10.0) -> plan1.OrbDecision:
        opens, _, h, lo, c = arrays(df)
        return orb_decide(opens, h, lo, c, T0, atr, self.P)

    def test_the_first_close_beyond_the_range_is_the_trade(self) -> None:
        # 06:15 closes AT the high 4004 (not beyond); 06:16 closes 4004.5 > 4004: a buy at bar 06:16
        df = orb_bars(t06_15=(4003.0, 4004.0, 4002.0, 4004.0), t06_16=(4004.0, 4004.8, 4003.9, 4004.5))
        d = self.decide(df)
        assert (d.status, d.side, d.rh, d.rl) == ("trade", 1, 4004.0, 3998.0)
        assert df.open_time.iloc[d.k] == utc("2026-09-30 06:16")

    def test_a_sell_and_only_the_first_break_counts(self) -> None:
        # 06:20 closes 3997.9 < 3998 first; 06:30 closes above the high later: the day's trade is the sell
        df = orb_bars(t06_20=(3999.0, 3999.0, 3997.0, 3997.9), t06_30=(4004.0, 4006.0, 4004.0, 4005.0))
        d = self.decide(df)
        assert (d.status, d.side) == ("trade", -1)
        assert df.open_time.iloc[d.k] == utc("2026-09-30 06:20")

    def test_wide_range_late_open_and_no_break(self) -> None:
        df = orb_bars(t06_16=(4004.0, 4004.8, 4003.9, 4004.5))
        assert self.decide(df, atr=3.9).status == "wide"  # 6 > 1.5 x 3.9 = 5.85
        assert self.decide(df, atr=4.0).status == "trade"  # 6 <= 6.0
        assert self.decide(df, atr=float("nan")).status == "wide"  # unknown ATR: no trade (fail closed)
        assert self.decide(orb_bars()).status == "no_break"
        gap6 = df[(df.open_time < T0) | (df.open_time >= T0 + pd.Timedelta(minutes=6))]
        assert self.decide(gap6).status == "late_open"  # the first bar at 06:06: 6 > 5 minutes
        gap5 = df[(df.open_time < T0) | (df.open_time >= T0 + pd.Timedelta(minutes=5))]
        assert self.decide(gap5).status == "trade"  # 06:05 counts (<= 5 minutes)

    def test_a_break_after_the_entry_window_is_ignored(self) -> None:
        # the window is the 60 minutes after the range: bars opening 06:15 .. 07:14
        late = frame(
            "2026-09-29 00:00", "2026-09-30 07:20", special={"2026-09-30 07:15": (4000, 4010, 4000, 4009)}
        )
        late.loc[late.open_time.between(T0, T0 + pd.Timedelta(minutes=14)), ["high", "low"]] = [
            4004.0,
            3998.0,
        ]
        assert self.decide(late).status == "no_break"


# --- pools, pool breaks, the H4 ATR change ------------------------------------------------------------------


class TestPools:
    @staticmethod
    def bars() -> pd.DataFrame:
        """Flat 4000 +- 0.5 from 2026-09-28 20:00 UTC; server day 29th (EEST, from 09-28 21:00 UTC): a high
        4010 at 10:00 and a low 3990 at 12:00 UTC; the Asia range of the Thai 30th (09-29 17:00-24:00 UTC):
        a high 4007 at 19:00 and a low 3995 at 22:00; the server day 30th opens at 09-29 21:00 UTC at 4001
        (high 4001)."""
        return frame(
            "2026-09-28 20:00",
            "2026-09-30 06:16",
            half=0.5,
            special={
                "2026-09-29 10:00": (4000.0, 4010.0, 3999.5, 4000.0),
                "2026-09-29 12:00": (4000.0, 4000.5, 3990.0, 4000.0),
                "2026-09-29 19:00": (4000.0, 4007.0, 3999.5, 4000.0),
                "2026-09-29 21:00": (4001.0, 4001.0, 3999.5, 4000.0),
                "2026-09-29 22:00": (4000.0, 4000.5, 3995.0, 4000.0),
                # the 06:00 M15 bin rises above its left bin but its right (forming) bin rises further: no fractal
                "2026-09-30 06:05": (4000.0, 4003.0, 3997.0, 4000.0),
                "2026-09-30 06:16": (4000.0, 4005.0, 3996.0, 4000.0),
            },
        )

    def test_the_pools_at_the_decision(self) -> None:
        opens, o, h, lo, _ = arrays(self.bars())
        got = pools(opens, o, h, lo, utc("2026-09-30 06:17"))
        # yesterday = server day 29th; Asia = Thai 30th 00-07; today's open = the 21:00 UTC bar's open;
        # the last M15 fractals: the 21:00 bin's high 4001 (newer than 19:00's 4007), the 22:00 bin's low 3995;
        # the 06:00 bin (4003 / 3997) beats its left bin only - its right bin goes to 4005 / 3996: not a fractal
        assert got == {
            "yday_high": 4010.0,
            "yday_low": 3990.0,
            "asia_high": 4007.0,
            "asia_low": 3995.0,
            "today_open": 4001.0,
            "swing_high": 4001.0,
            "swing_low": 3995.0,
        }

    def test_a_monday_sees_fridays_high_and_low_and_the_asia_range_ends_at_07_thai(self) -> None:
        """Friday 2026-09-25 trades to 20:59 UTC (server day 25th) with a high 4012 and a low 3988; no bars on the
        weekend; Monday's server day opens Sunday 22:00 UTC. Monday 00:30 UTC (07:30 Thai) trades 4020 / 3980:
        after the Asia range (00:00-07:00 Thai = Sunday 17:00 .. Monday 00:00 UTC), so not in it."""
        fri = frame(
            "2026-09-25 00:00",
            "2026-09-25 20:59",
            half=0.5,
            special={
                "2026-09-25 10:00": (4000.0, 4012.0, 3999.5, 4000.0),
                "2026-09-25 12:00": (4000, 4000.5, 3988, 4000),
            },
        )
        mon = frame(
            "2026-09-27 22:00",
            "2026-09-28 06:16",
            half=0.5,
            special={
                "2026-09-27 23:00": (4000.0, 4006.0, 3999.5, 4000.0),
                "2026-09-28 00:30": (4000.0, 4020.0, 3980.0, 4000.0),
            },
        )
        opens, o, h, lo, _ = arrays(pd.concat([fri, mon]))
        got = pools(opens, o, h, lo, utc("2026-09-28 06:17"))
        assert (got["yday_high"], got["yday_low"]) == (4012.0, 3988.0)  # Friday, three days back
        assert (got["asia_high"], got["asia_low"]) == (4006.0, 3999.5)  # not the 07:30-Thai bar's 4020 / 3980

    def test_no_asia_range_before_07_thai_and_no_future_bars(self) -> None:
        df = self.bars()
        opens, o, h, lo, _ = arrays(df)
        got = pools(opens, o, h, lo, utc("2026-09-29 23:30"))  # 06:30 Thai: the Asia range is still open
        assert "asia_high" not in got and got["today_open"] == 4001.0
        # a spike after the decision changes nothing at the decision (no look-ahead)
        spiked = df.copy()
        spiked.loc[spiked.open_time == utc("2026-09-30 06:16"), "high"] = 5000.0
        o2, oo, hh, ll, _ = arrays(spiked)
        assert pools(o2, oo, hh, ll, utc("2026-09-30 06:16")) == pools(
            opens, o, h, lo, utc("2026-09-30 06:16")
        )

    def test_broken_pools_in_the_trade_direction(self) -> None:
        # the window = bars opening 06:02 .. 06:16 (15 minutes before 06:17): first open 4000, high 4004.5,
        # low 3999.5; the 06:01 bar (open 3990) is outside it
        df = frame(
            "2026-09-30 05:00",
            "2026-09-30 06:16",
            half=0.5,
            special={
                "2026-09-30 06:01": (3990.0, 3990.5, 3989.5, 3990.0),
                "2026-09-30 06:16": (4000.0, 4004.5, 3999.5, 4004.0),
            },
        )
        opens, o, h, lo, _ = arrays(df)
        found = {"a": 4002.0, "b": 4005.0, "c": 3999.8, "d": 3995.0, "e": 4000.0}
        at = utc("2026-09-30 06:17")
        # "e" sits at the window's first open 4000: opening AT a pool is not breaking it, either way
        assert broken_pools(opens, o, h, lo, at, 1, found) == ["a"]  # 4000 < 4002 < 4004.5
        assert broken_pools(opens, o, h, lo, at, -1, found) == ["c"]  # 4000 > 3999.8 > 3999.5
        # the bar opening exactly 15 minutes before the decision (06:02) is inside the window: its open 3990
        # is the window's first open, so a buy breaks 3995 too
        early = df.copy()
        early.loc[early.open_time == utc("2026-09-30 06:02"), ["open", "low"]] = [3990.0, 3989.5]
        o2, oo, hh, ll, _ = arrays(early)
        assert broken_pools(o2, oo, hh, ll, at, 1, found) == ["a", "c", "d", "e"]

    def test_contracting_is_the_journals_whole_percent_reading(self) -> None:
        # liq_journal rounds the change to a whole percent, rules_week skips at <= 0: +0.4 % is contracting
        assert plan1.is_contracting(0.004, 0.5) and plan1.is_contracting(0.005, 0.5)
        assert not plan1.is_contracting(0.006, 0.5) and not plan1.is_contracting(0.004, 0.0)
        assert plan1.is_contracting(-0.2, 0.5) and plan1.is_contracting(float("nan"), 0.5)

    def test_h4_bars_on_the_server_day_from_m1(self) -> None:
        """Wednesday 2026-09-30, EEST (UTC+3): the server's H4 bars open at 00:00 / 04:00 / 08:00 / 12:00 Athens =
        21:00 / 01:00 / 05:00 / 09:00 UTC. M1 bars 00:00-09:59 UTC at 4000 +- 1, a high of 4010 at 02:30 UTC: at
        10:00 UTC the bars closing 01:00 (partial: from 00:00 UTC), 05:00 (high 4010) and 09:00 are complete, the
        09:00-13:00 UTC one is running."""
        df = frame(
            "2026-09-30 00:00",
            "2026-09-30 09:59",
            half=1.0,
            special={"2026-09-30 02:30": (4000, 4010, 3999, 4000)},
        )
        opens, _, h, lo, c = arrays(df)
        h4 = plan1.h4_bars(opens, h, lo, c, utc("2026-09-30 10:00"))
        assert list(h4.index) == [utc("2026-09-30 01:00"), utc("2026-09-30 05:00"), utc("2026-09-30 09:00")]
        assert list(h4["high"]) == [4001.0, 4010.0, 4001.0] and list(h4["low"]) == [3999.0] * 3

    def test_h4_atr_change(self) -> None:
        """21 H4 bars of range 2 (closes flat), then the last 6 of range 4: ATR now (8 x 2 + 6 x 4) / 14,
        6 bars earlier 2: change 40 / 28 - 1."""
        closes = pd.date_range(utc("2026-09-20 04:00"), periods=27, freq="4h")
        rng = np.r_[np.full(21, 2.0), np.full(6, 4.0)]
        h4 = pd.DataFrame(
            {"open": 4000.0, "high": 4000 + rng / 2, "low": 4000 - rng / 2, "close": 4000.0}, index=closes
        )
        assert h4_atr_change(h4, closes[-1]) == pytest.approx(40 / 28 - 1)
        assert h4_atr_change(h4, closes[-7]) == pytest.approx(
            0.0
        )  # all range 2: no change (contracting: <= 0)
        assert h4_atr_change(h4, closes[-1] - pd.Timedelta(minutes=1)) == pytest.approx(
            (9 * 2 + 5 * 4) / 14 / 2 - 1
        )  # the last bar is not closed yet
        assert np.isnan(h4_atr_change(h4.iloc[:19], closes[18]))  # 19 bars < 14 + 6


# --- the ORB strategy -------------------------------------------------------------------------------------


def h4_frame(expanding: bool | None) -> pd.DataFrame:
    """H4 bars of range 6; the last six of range 8 (expanding), 4 (contracting) or 6 (None: no change)."""
    closes = pd.date_range(utc("2026-09-24 01:00"), utc("2026-09-30 05:00"), freq="4h")
    n = len(closes)
    rng = np.full(n, 6.0)
    rng[-6:] = 6.0 if expanding is None else 8.0 if expanding else 4.0
    return pd.DataFrame(
        {
            "open_time": closes - pd.Timedelta(hours=4),
            "open": 4000.0,
            "high": 4000 + rng / 2,
            "low": 4000 - rng / 2,
            "close": 4000.0,
        },
        index=closes,
    )


def orb_ctx(
    df: pd.DataFrame, *, expanding: bool | None = True, ask_over: float = 0.3, h4: bool = True
) -> StrategyContext:
    at = pd.Timestamp(df.index[-1]).to_pydatetime()
    close = float(df.close.iloc[-1])
    market = MarketContext(
        symbol="XAUUSD",
        decision_time_utc=at,
        entry_timeframe=Timeframe.M1,
        higher_timeframe=Timeframe.H4,
        states=(state(Timeframe.M1, at, close=close), state(Timeframe.H4, at, close=close)),
        bid=close,
        ask=close + ask_over,
        spread_points=ask_over / XAUUSD_SPEC.point,
    )
    frames = {Timeframe.M1: df, Timeframe.H4: h4_frame(expanding)} if h4 else {Timeframe.M1: df}
    return StrategyContext(market, {**frames, Timeframe.H1: wide_h1(at)}, at, XAUUSD_SPEC)


def upto(df: pd.DataFrame, close: str) -> pd.DataFrame:
    return df[df.index <= utc(close)]


BREAK = {"t06_16": (4004.0, 4004.8, 4003.9, 4004.5)}


class TestRegimeSwitch:
    """The regime switch (journal, CHECKLIST row 62): new entries only while the D1 ATR(20) >= 60 USD; server days
    built from H1 bars; a day is known from its server midnight + 24 h."""

    END = pd.Timestamp("2026-09-21", tz="Europe/Athens").tz_convert(
        "UTC"
    )  # the midnight after day 20 (09-01 + 19)

    def test_the_mean_of_20_true_ranges_known_by_then(self) -> None:
        # 20 days of 59.99 then 60.00 USD: ATR 59.99 / 60.00
        assert plan1.d1_atr20(h1_days([59.99] * 20), self.END) == pytest.approx(59.99)
        assert plan1.d1_atr20(h1_days([60.0] * 20), self.END) == pytest.approx(60.0)
        # 21 days, the first 200 wide: only the last 20 count (the first one drops out)
        assert plan1.d1_atr20(
            h1_days([200.0] + [60.0] * 20), self.END + pd.Timedelta(days=1)
        ) == pytest.approx(60.0)
        # the forming day (day 21, 1000 wide) is not known before its own midnight + 24 h
        forming = h1_days([60.0] * 20 + [1000.0])
        assert plan1.d1_atr20(
            forming[forming.index <= self.END + pd.Timedelta(hours=5)], self.END + pd.Timedelta(hours=5)
        ) == pytest.approx(60.0)
        # a minute before day 20 is known: only 19 days, too few
        assert np.isnan(plan1.d1_atr20(h1_days([60.0] * 20), self.END - pd.Timedelta(minutes=1)))
        assert np.isnan(plan1.d1_atr20(h1_days([60.0] * 19), self.END)) and np.isnan(
            plan1.d1_atr20(None, self.END)
        )

    def test_a_gap_day_uses_the_previous_close(self) -> None:
        # day 20 opens 50 above day 19's close and trades 4050 +- 5: its true range is 4055 - 4000 = 55, not 10
        d = h1_days([60.0] * 19)
        last = h1_days([10.0], "2026-09-20", close=4050.0)
        assert plan1.d1_atr20(pd.concat([d, last]), self.END) == pytest.approx((19 * 60 + 55) / 20)

    def test_holds_below_60_and_trades_at_60(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(plan1, "pools", lambda *a: {})
        df = upto(orb_bars(**BREAK), "2026-09-30 06:17")
        at = pd.Timestamp(df.index[-1])
        day0 = (at.tz_convert("Europe/Athens").normalize() - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
        for rng, action in ((59.99, Action.HOLD), (60.0, Action.BUY)):
            base = orb_ctx(df)
            ctx = StrategyContext(
                base.market, {**base.frames, Timeframe.H1: h1_days([rng] * 20, day0)}, base.now_utc, base.spec
            )
            sig = Plan1Orb().evaluate(ctx)
            assert sig.action is action
            reg = {c.name: c for c in sig.conditions}["regime"]
            assert reg.passed is (action is Action.BUY) and reg.detail.startswith(f"D1 ATR(20) {rng:.2f}")
        base = orb_ctx(df)
        few = StrategyContext(
            base.market, {**base.frames, Timeframe.H1: h1_days([100.0] * 5, day0)}, base.now_utc, base.spec
        )
        assert Plan1Orb().evaluate(few).action is Action.HOLD  # too few days: no trade
        off = Plan1Orb(Plan1OrbParams(d1_atr20_min_usd=None))
        assert off.evaluate(few).action is Action.BUY


class TestPlan1Orb:
    def test_the_entry_and_its_journal_record(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(plan1, "pools", lambda *a: {})
        sig = Plan1Orb().evaluate(orb_ctx(upto(orb_bars(**BREAK), "2026-09-30 06:17")))
        # the ask 4004.8; the stop at the range low 3998: risk 6.8; the target 4004.8 + 1.5 x 6.8 = 4015.0
        assert sig.action is Action.BUY
        assert (sig.entry_price, sig.stop_loss) == (pytest.approx(4004.8), 3998.0)
        assert sig.take_profit == pytest.approx(4015.0)
        names = [c.name for c in sig.conditions]
        assert names == [
            "rule",
            "h1_atr",
            "regime",
            "opening_range",
            "pools",
            "h4_atr_change",
            "pool_break",
            "stop_distance",
            "spread",
        ]
        detail = {c.name: c.detail for c in sig.conditions}
        # the H1 ATR: every H1 bar 3995 .. 4005 before 06:00 = 10; the 06:00 hour is not complete by 06:17
        assert detail["h1_atr"].startswith("H1 ATR 10.00") and "no floor" in detail["h1_atr"]
        assert detail["opening_range"].startswith("3998.00-4004.00 width 6.00 <= 1.5 x H1 ATR 10.00")
        assert "expanding" in detail["h4_atr_change"] and detail["stop_distance"].startswith("6.80")
        assert detail["spread"] == "0.30 (30 points) at the decision quote"  # bid 4004.5, ask 4004.8

    def test_contracting_h4_needs_a_pool_break(self, monkeypatch: pytest.MonkeyPatch) -> None:
        df = upto(orb_bars(**BREAK), "2026-09-30 06:17")
        monkeypatch.setattr(
            plan1, "pools", lambda *a: {"asia_high": 4010.0}
        )  # above the window's high 4004.8
        held = Plan1Orb().evaluate(orb_ctx(df, expanding=False))
        assert held.action is Action.HOLD and ReasonCode.NO_SETUP.value in held.reason_codes
        failed = [c for c in held.conditions if not c.passed]
        assert [c.name for c in failed] == ["pool_break"] and "none" in failed[0].detail
        # the window (06:02 .. 06:16) opened at 4000 and traded 4004.8: a pool at 4002 is broken
        monkeypatch.setattr(plan1, "pools", lambda *a: {"asia_high": 4002.0})
        sig = Plan1Orb().evaluate(orb_ctx(df, expanding=False))
        assert sig.action is Action.BUY
        assert "asia_high" in {c.name: c.detail for c in sig.conditions}["pool_break"]
        # the rule off: no pool needed
        monkeypatch.setattr(plan1, "pools", lambda *a: {})
        off = Plan1Orb(Plan1OrbParams(pool_break_when_h4_contracting=False))
        assert off.evaluate(orb_ctx(df, expanding=False)).action is Action.BUY
        assert off.required_timeframes() == (Timeframe.M1,)
        assert Plan1Orb().required_timeframes() == (Timeframe.M1,)

    def test_an_unchanged_or_unknown_h4_atr_counts_as_contracting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        df = upto(orb_bars(**BREAK), "2026-09-30 06:17")
        monkeypatch.setattr(plan1, "pools", lambda *a: {})
        flat = Plan1Orb().evaluate(orb_ctx(df, expanding=None))  # latest == 24 h earlier: <= is contracting
        assert flat.action is Action.HOLD
        assert "+0.0 % (contracting)" in {c.name: c.detail for c in flat.conditions}["h4_atr_change"]
        unknown = Plan1Orb().evaluate(orb_ctx(df, h4=False))  # no H4 bars: fail closed
        assert unknown.action is Action.HOLD
        assert "unknown" in {c.name: c.detail for c in unknown.conditions}["h4_atr_change"]

    def test_only_at_the_break_bar_and_inside_the_window(self) -> None:
        df = orb_bars(**BREAK)
        assert (
            Plan1Orb().evaluate(orb_ctx(upto(df, "2026-09-30 06:18"))).action is Action.HOLD
        )  # broke already
        early = Plan1Orb().evaluate(orb_ctx(upto(df, "2026-09-30 06:15")))  # the range is still forming
        assert ReasonCode.OUTSIDE_SESSION.value in early.reason_codes
        none = Plan1Orb().evaluate(orb_ctx(upto(df, "2026-09-30 06:16")))  # 06:15 closed inside the range
        assert none.action is Action.HOLD and "no_break" in none.explanation

    def test_no_orb_on_a_saturday(self) -> None:
        sat = orb_bars(**BREAK)
        sat.index = sat.index + pd.Timedelta(days=3)  # Wednesday 2026-09-30 -> Saturday 2026-10-03
        sat["open_time"] = sat["open_time"] + pd.Timedelta(days=3)
        held = Plan1Orb().evaluate(orb_ctx(upto(sat, "2026-10-03 06:17")))
        assert held.action is Action.HOLD and ReasonCode.OUTSIDE_SESSION.value in held.reason_codes

    def test_atr_floor_parameter(self) -> None:
        df = upto(orb_bars(**BREAK), "2026-09-30 06:17")
        held = Plan1Orb(Plan1OrbParams(atr_floor=12.0)).evaluate(orb_ctx(df))  # ATR 10 < 12
        assert held.action is Action.HOLD and [c.name for c in held.conditions if not c.passed] == ["h1_atr"]
        assert Plan1Orb(Plan1OrbParams(atr_floor=10.0)).evaluate(orb_ctx(df)).action is Action.BUY

    def test_time_exit_at_the_bar_close_60_minutes_after_the_entry_minute(self) -> None:
        df = frame("2026-09-29 00:00", "2026-09-30 07:30")
        pos = OpenPosition(
            Side.BUY, 4004.8, 3998.0, 3998.0, 4015.0, datetime(2026, 9, 30, 6, 17, 0, 300_000, tzinfo=UTC)
        )
        s = Plan1Orb()
        assert s.manage_position(orb_ctx(upto(df, "2026-09-30 07:16")), pos) is None
        advice = s.manage_position(orb_ctx(upto(df, "2026-09-30 07:17")), pos)
        assert advice is not None and advice.close is ExitReason.TIME_STOP

    def test_params_are_bounded(self) -> None:
        with pytest.raises(ValidationError):
            Plan1OrbParams(orb_zone="Mars/Base")
        with pytest.raises(ValidationError):
            Plan1OrbParams(orb_open="25:00")
        with pytest.raises(ValidationError):
            Plan1OrbParams(target_r=0)


# --- the NY straddle --------------------------------------------------------------------------------------

NY = datetime(2026, 9, 30, 12, 30, tzinfo=UTC)  # 08:30 New York (EDT)


def at(seconds: float) -> datetime:
    return NY + timedelta(seconds=seconds)


class TestDailyStraddle:
    def test_every_weekday_at_0830_new_york(self) -> None:
        p = Plan1StraddleParams()
        assert daily_release(date(2026, 9, 30), p) == Release(NY, "NY0830")
        assert daily_release(date(2026, 11, 4), p).at == datetime(2026, 11, 4, 13, 30, tzinfo=UTC)  # type: ignore[union-attr]  # EST
        assert daily_release(date(2026, 10, 3), p) is None  # Saturday

    def test_triggers_and_stop_in_usd(self) -> None:
        # at a bid of 2000, S2's unit would be 0.5 USD; PLAN-1's straddle is 2 / 8 USD flat
        s = DailyStraddle(Plan1StraddleParams(), ())
        assert s.on_quote(at(-1), 2000.0, 2000.4) is None  # the reference: up 2002.4, down 1998.0
        assert s.on_quote(at(0.5), 2002.0, 2002.39) is None
        e = s.on_quote(at(1.0), 2002.0, 2002.4)
        assert e is not None and e.side is Side.BUY
        assert (e.trigger, e.stop_distance) == (pytest.approx(2002.4), pytest.approx(8.0))
        assert e.close_at == at(1800)
        assert s.on_quote(at(2), 1990.0, 1990.4) is None  # once a day

    def test_the_window_and_the_weekend(self) -> None:
        s = DailyStraddle(Plan1StraddleParams(), ())
        s.on_quote(at(-1), 2000.0, 2000.4)
        assert s.on_quote(at(60), 1990.0, 1990.4) is None  # 08:31:00: the window is over
        sat = datetime(2026, 10, 3, 12, 30, tzinfo=UTC)
        s.on_quote(sat - timedelta(seconds=1), 2000.0, 2000.4)
        assert s.on_quote(sat + timedelta(seconds=1), 1990.0, 1990.4) is None

    def test_busy_spans(self) -> None:
        s = Plan1Straddle()
        assert s.busy_between(NY - timedelta(seconds=40), NY - timedelta(seconds=30))  # arm from 08:29:25
        assert not s.busy_between(NY - timedelta(seconds=60), NY - timedelta(seconds=35))
        assert s.busy_between(at(59), at(60)) and not s.busy_between(at(60), at(120))
        assert not s.busy_between(
            datetime(2026, 10, 3, 12, 0, tzinfo=UTC), datetime(2026, 10, 3, 13, 0, tzinfo=UTC)
        )


def ny_ctx(close_at: datetime, bid: float, ask: float) -> StrategyContext:
    df = frame(
        "2026-09-29 00:00", (pd.Timestamp(close_at) - pd.Timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
    )
    market = MarketContext(
        symbol="XAUUSD",
        decision_time_utc=close_at,
        entry_timeframe=Timeframe.M1,
        higher_timeframe=Timeframe.H4,
        states=(state(Timeframe.M1, close_at, close=4000.0), state(Timeframe.H4, close_at, close=4000.0)),
        bid=bid,
        ask=ask,
        spread_points=(ask - bid) / XAUUSD_SPEC.point,
        quote_time_utc=at(1),
    )
    return StrategyContext(market, {Timeframe.M1: df, Timeframe.H1: wide_h1(close_at)}, close_at, XAUUSD_SPEC)


class TestPlan1Straddle:
    def test_the_entry_with_its_journal_record(self) -> None:
        s = Plan1Straddle()
        s.attach_calendar((Release(NY, "CPI"), Release(NY + timedelta(days=1), "PPI")))
        assert s.on_quote("XAUUSD", at(-1), 4000.0, 4000.4) is None
        e = s.on_quote("XAUUSD", at(1), 4002.1, 4002.5)
        assert e is not None and e.side is Side.BUY
        sig = s.entry_signal(ny_ctx(NY, 4002.1, 4002.5), e)
        assert sig is not None and sig.action is Action.BUY
        assert (sig.entry_price, sig.stop_loss, sig.take_profit) == (
            4002.5,
            pytest.approx(3994.5),
            pytest.approx(4102.5),
        )
        detail = {c.name: c.detail for c in sig.conditions}
        assert list(detail) == ["rule", "h1_atr", "regime", "release", "pools", "stop_distance", "spread"]
        assert detail["spread"] == "0.40 (40 points) at the decision quote"  # bid 4002.1, ask 4002.5
        assert detail["release"].endswith("CPI") and "4002.40" in detail["rule"]
        # the next weekday trades too, with no release on the calendar there
        nxt = NY + timedelta(days=1)
        s.on_quote("XAUUSD", nxt - timedelta(seconds=1), 4000.0, 4000.4)
        assert s.on_quote("XAUUSD", nxt + timedelta(seconds=1), 3997.9, 3998.3) is not None

    def test_the_regime_switch_refuses_the_straddle(self) -> None:
        s = Plan1Straddle()
        s.on_quote("XAUUSD", at(-1), 4000.0, 4000.4)
        e = s.on_quote("XAUUSD", at(1), 4002.1, 4002.5)
        base = ny_ctx(NY, 4002.1, 4002.5)
        for rng, ok in ((59.99, False), (60.0, True)):
            ctx = StrategyContext(
                base.market,
                {**base.frames, Timeframe.H1: h1_days([rng] * 20, "2026-09-10")},
                base.now_utc,
                base.spec,
            )
            assert e is not None and (s.entry_signal(ctx, e) is not None) is ok

    def test_atr_floor_refuses_the_entry(self) -> None:
        s = Plan1Straddle(Plan1StraddleParams(atr_floor=12.0))  # the flat frame's H1 ATR is 10
        s.on_quote("XAUUSD", at(-1), 4000.0, 4000.4)
        e = s.on_quote("XAUUSD", at(1), 4002.1, 4002.5)
        assert e is not None and s.entry_signal(ny_ctx(NY, 4002.1, 4002.5), e) is None

    def test_out_30_minutes_after_0830(self) -> None:
        # filled at 08:31:00.1 (a trigger in the window's last tenth of a second): still out at 09:00, not 09:01
        s = Plan1Straddle()
        pos = OpenPosition(Side.BUY, 4002.6, 3994.5, 3994.5, 4102.5, at(60.1))
        assert s.manage_position(ny_ctx(at(29 * 60), 4005.0, 4005.4), pos) is None
        advice = s.manage_position(ny_ctx(at(30 * 60), 4005.0, 4005.4), pos)
        assert advice is not None and advice.close is ExitReason.TIME_STOP


def test_both_pieces_are_in_the_catalog() -> None:
    names = set(default_registry().names)
    assert {"setup_plan1_orb", "setup_plan1_ny"} <= names
