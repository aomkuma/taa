"""Audit 5: the tick simulators (precursors/surrender.py, tick_straddle.py) by hand.

Ticks are (seconds, bid); the ask is bid + 0.30 unless given. Every expected number is worked out in the comment.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import surrender  # noqa: E402
import tick_straddle  # noqa: E402

S = 10**9


def ticks(rows: list[tuple[float, float]], spread: float = 0.3) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t, b = zip(*rows, strict=True)
    b = np.array(b, float)
    return (np.array(t, float) * S).astype(np.int64), b, b + spread


class TestSurrenderTrade:
    def test_a_buy_stop_is_read_on_the_bid_and_fills_through_its_gap(self) -> None:
        # buy at the ask 100.3 + 0.07 = 100.37; stop 10 -> out when the bid <= 90.37. The bid 92 (-8.37) does not stop;
        # the next tick's bid 85 is past it: out there, -15.37 (the gap included); R over the fill's risk -1.537
        t, bid, ask = ticks([(0, 100), (60, 92), (120, 85), (180, 120)])
        x = surrender.trade(t, bid, ask, 0, 1, None, None)
        assert x["exit"] == "stop" and x["pnl"] == pytest.approx(85 - 100.37) and x["exit_t"] == 120 * S
        assert x["pnl"] / surrender.STOP == pytest.approx(-1.537)

    def test_the_target_is_a_limit_never_better(self) -> None:
        # a sell at the bid 100 - 0.07 = 99.93; the ask falls to 80.3 (19.63 our way): the target pays 10.0 exactly
        t, bid, ask = ticks([(0, 100), (60, 80)])
        x = surrender.trade(t, bid, ask, 0, -1, None, None)
        assert x["exit"] == "win" and x["pnl"] == 10.0

    def test_the_entry_is_the_first_tick_at_or_after_the_decision(self) -> None:
        # the decision at 3 s: the tick at 0 s is before it; the entry is the 5 s tick's ask 101.3 + 0.07
        t, bid, ask = ticks([(0, 100), (5, 101), (65, 101.5)])
        x = surrender.trade(t, bid, ask, 3 * S, 1, None, None)
        assert x["entry"] == pytest.approx(101.37) and x["exit"] == "time"

    def test_a_stop_and_the_surrender_on_one_tick_is_the_stop(self) -> None:
        # nothing ran 2 our way by 180 s; the tick at 180 s is also past the stop (bid 90 <= 90.37): 'stop', -10.37
        t, bid, ask = ticks([(0, 100), (60, 100.5), (180, 90)])
        x = surrender.trade(t, bid, ask, 0, 1, 3, 2.0)
        assert x["exit"] == "stop" and x["pnl"] == pytest.approx(90 - 100.37)

    def test_the_daily_break_inside_the_hold_exits_at_the_last_tick_before_it(self) -> None:
        # a buy at 20:50 UTC; ticks stop at 20:54:59 and resume at 22:05 (after the 60-minute hold ended at 21:50):
        # out at the 20:54:59 tick's bid 101 -> +0.63; nothing after the break is used
        base = 20 * 3600 + 50 * 60
        t, bid, ask = ticks([(base, 100), (base + 299, 101), (base + 75 * 60, 150)])
        x = surrender.trade(t, bid, ask, base * S, 1, None, None)
        assert x["exit"] == "time" and x["pnl"] == pytest.approx(101 - 100.37) and x["exit_t"] == (base + 299) * S


def two_days(monkeypatch: pytest.MonkeyPatch, module: object) -> None:
    """Day 1 (2026-01-14): ticks from 23:30 to 23:59:59 UTC at 100; day 2: from 00:00 the bid falls to 85 at 00:10."""
    d1, d2 = pd.Timestamp("2026-01-14", tz="UTC").value, pd.Timestamp("2026-01-15", tz="UTC").value
    m = 60 * S
    files = {
        d1: (np.array([d1 + (23 * 60 + 30) * m, d1 + (23 * 60 + 45) * m, d1 + 24 * 60 * m - S]), [100.0, 100.2, 100.1]),
        d2: (np.array([d2, d2 + 5 * m, d2 + 10 * m, d2 + 20 * m]), [100.0, 95.0, 85.0, 84.0]),
    }

    def fake(day: pd.Timestamp):  # noqa: ANN202
        f = files.get(pd.Timestamp(day).value)
        if f is None:
            return None
        b = np.array(f[1], float)
        return f[0].astype(np.int64), b, b + 0.3

    # at the source (tick_straddle.day_ticks, which span_ticks reads) and, for the code before the fix, where a
    # module imported it by name
    monkeypatch.setattr(tick_straddle, "day_ticks", fake)
    monkeypatch.setattr(module, "day_ticks", fake, raising=False)


class TestAcrossMidnight:
    def test_surrender_run_follows_a_trade_past_midnight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # a buy at 23:30 UTC, the 60-minute hold ends 00:30: the stop (bid <= 90.37) comes at 00:10 on day 2 at 85,
        # -15.37. Cut at the UTC day's last tick it would be a 'time' exit at 23:59:59 instead.
        two_days(monkeypatch, surrender)
        X = pd.DataFrame({"t": [pd.Timestamp("2026-01-14 23:30", tz="UTC")], "side": [1]})
        T = surrender.run(X, None, None)
        assert T["exit"].tolist() == ["stop"] and T["pnl"].iloc[0] == pytest.approx(85 - 100.37)
        assert T["exit_t"].iloc[0] == pd.Timestamp("2026-01-15 00:10", tz="UTC").value

    def test_tick_straddle_run_follows_a_trade_past_midnight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # the straddle from 23:44 (c0 = the last bid before it, 100.0), b 3, s 5, a 60-minute wait: no trigger on day 1;
        # on day 2 the bid 95.0 at 00:05 is <= 97 -> a sell at 95 - 0.07 = 94.93; the target needs the ask <= 84.93:
        # 85.3 at 00:10 no, 84.3 at 00:20 yes -> 'win' +10 at 00:20; the stop (ask >= 99.93) never comes.
        # Cut at the UTC day's end there is no trigger at all and no trade.
        two_days(monkeypatch, tick_straddle)
        X = pd.DataFrame({"t": [pd.Timestamp("2026-01-14 23:44", tz="UTC")], "part": ["P1"]})
        T = tick_straddle.run(X, 3.0, 5.0)
        assert T["side"].tolist() == [-1] and T["exit"].tolist() == ["win"]
        assert T["exit_t"].iloc[0] == pd.Timestamp("2026-01-15 00:20", tz="UTC").value
        assert T["R"].iloc[0] == pytest.approx(10 / 5)  # R over the stop s (the fill's risk), not the trigger b


def test_a_learning_day_is_never_joined_to_an_exam_day(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    def fake(day: pd.Timestamp):  # noqa: ANN202
        asked.append(f"{pd.Timestamp(day):%Y-%m-%d}")
        return np.array([pd.Timestamp(day).value], np.int64), np.array([1.0]), np.array([1.3])

    monkeypatch.setattr(tick_straddle, "day_ticks", fake)
    tick_straddle.span_ticks(pd.Timestamp("2026-04-17", tz="UTC"))
    tick_straddle.span_ticks(pd.Timestamp("2026-04-16", tz="UTC"))
    assert asked == ["2026-04-17", "2026-04-16", "2026-04-17"]  # 2026-04-18 (the exam's first day) never read


def test_touches_outcome_needs_the_full_x_back() -> None:
    import touches  # noqa: PLC0415

    # a support test at 100 (side +1), x = 10: bar 1's high 109.5 is 9.5 back -> not yet; bar 2's 110.0 -> reversed
    h, lo = np.array([101.0, 109.5, 105.0]), np.array([99.5, 104.0, 101.0])
    assert touches.outcome(h, lo, 0, 100.0, 1, 10.0, 3)["outcome"] == "neither"
    h2 = np.array([101.0, 109.5, 110.0])
    x = touches.outcome(h2, lo, 0, 100.0, 1, 10.0, 3)
    assert x["outcome"] == "reversed" and x["bars"] == 2
