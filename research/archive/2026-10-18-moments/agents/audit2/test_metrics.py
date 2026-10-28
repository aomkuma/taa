"""Audit 8: the metrics - the drawdown from 0, break-even trades, the losing streak in time order, the weekday counts,
the Thai-week table - on hand-worked trade lists.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

AG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AG / "precursors"))
sys.path.insert(0, str(AG / "journal"))
import m15_trades  # noqa: E402
import sr_break  # noqa: E402
import surrender  # noqa: E402
import tick_straddle  # noqa: E402
import wf  # noqa: E402


def trades(pnl: list[float], start: str = "2026-01-12 14:00") -> pd.DataFrame:
    t = pd.date_range(start, periods=len(pnl), freq="1h", tz="UTC")
    p = np.array(pnl, float)
    return pd.DataFrame({"t": t, "pnl": p, "R": p / 10, "exit": np.where(p >= 10, "win", np.where(p < 0, "stop", "time")),
                         "cell": "x"})


def max_dd(text: str) -> float:
    return float(re.search(r"max DD ([0-9.]+)", text).group(1))


@pytest.mark.parametrize("summary", [sr_break.summary, surrender.summary, tick_straddle.summary])
def test_the_drawdown_counts_from_the_starting_balance(summary) -> None:  # noqa: ANN001
    # -5, -5, +1: the balance goes 0 -> -5 -> -10 -> -9; the deepest fall from a peak (the start, 0) is 10, not 5
    T = trades([-5.0, -5.0, 1.0])
    out = summary(T, "2026-01-12", "2026-01-17")
    assert max_dd(out) == pytest.approx(10.0)


def test_no_summary_measures_the_drawdown_without_the_start() -> None:
    """Every precursors summary: (eq.cummax() - eq).max() misses the start at 0 when the first trades lose."""
    bad = [f.name for f in sorted((AG / "precursors").glob("*.py")) if "(eq.cummax() - eq).max()" in f.read_text(encoding="utf-8")]
    assert bad == []


def test_the_drawdown_after_a_first_win_is_unchanged() -> None:
    # +3, -5, -5, +20: peak 3, trough -7 -> 10 (the start does not matter here)
    assert max_dd(sr_break.summary(trades([3.0, -5.0, -5.0, 20.0]), "2026-01-12", "2026-01-17")) == pytest.approx(10.0)


def test_the_longest_losing_streak_in_time_order_and_a_break_even_trade() -> None:
    pnl = np.array([-1.0, -2.0, 0.0, -1.0, -1.0, -1.0, 5.0, -1.0])
    assert wf.longest_run(pnl < 0) == 3  # the 0.0 (break-even) ends the first run of 2
    assert wf.longest_run(np.array([], bool)) == 0


@pytest.mark.parametrize(("part", "n"), [("P1", 64), ("P2", 66)])
def test_the_weekday_counts(part: str, n: int) -> None:
    # P1 2025-10-18 (Sat) .. 2026-01-15: Mon 2025-10-20 .. Fri 2026-01-09 = 12 weeks = 60, Mon 01-12 .. Thu 01-15 = 4
    # P2 2026-01-16 (Fri) .. 2026-04-17: Fri 01-16 = 1, Mon 01-19 .. Fri 04-17 = 13 weeks = 65
    a, b = m15_trades.PARTS[part]
    assert np.busday_count(a, b) == n == len(pd.bdate_range(a, b, inclusive="left"))


def test_the_weekly_table_on_the_thai_week() -> None:
    # Fri 2026-01-16 23:30 UTC = Sat 06:30 Thai: still the week of Mon 2026-01-12 (Thai); Sun 2026-01-18 22:10 UTC =
    # Mon 05:10 Thai: the week of 2026-01-19
    T = pd.DataFrame({"t": pd.to_datetime(["2026-01-12 02:00", "2026-01-16 23:30", "2026-01-18 22:10"], utc=True),
                      "pnl": [10.0, -4.0, 2.5], "R": [1.0, -0.4, 0.25], "exit": ["win", "stop", "time"], "cell": "x"})
    W = wf.weekly(T)
    assert [str(w) for w in W.week] == ["2026-01-12", "2026-01-19"]
    assert W.trades.tolist() == [2, 1] and W.usd.tolist() == [6.0, 2.5] and W.usd_total.tolist() == [6.0, 8.5]
    assert W.worst.tolist() == [-4.0, 2.5] and W.R.tolist() == [0.6, 0.25]


def test_the_weekly_win_share_is_the_trades_that_made_money() -> None:
    """The measurer's answer (2026-10-20): a win is pnl > 0 after costs, whatever the exit is called."""
    T = pd.DataFrame({"t": pd.to_datetime(["2026-01-12 02:00", "2026-01-12 05:00", "2026-01-12 06:00", "2026-01-12 07:00"],
                                          utc=True),
                      "pnl": [10.0, 3.0, 0.0, -2.0], "R": [1.0, 0.3, 0.0, -0.2], "exit": ["target", "structure", "time", "time"],
                      "cell": "x"})
    assert wf.weekly(T).win.tolist() == [0.5]  # 10 and 3 made money; the break-even 0.0 and the -2 did not


def test_the_walk_forward_months_win_share_is_the_trades_that_made_money() -> None:
    # one cell; December 2025 is its past (2 trades, closed before January); January 2026 takes 4 trades in sequence:
    # +10 (target), +0.5 (time, in profit), 0.0 (break-even), -10 (stop) -> 2 of 4 made money
    t = pd.to_datetime(["2025-12-03 10:00", "2025-12-04 10:00", "2026-01-05 10:00", "2026-01-06 10:00",
                        "2026-01-07 10:00", "2026-01-08 10:00"], utc=True)
    T = pd.DataFrame({"t": t, "x_t": t + pd.Timedelta(minutes=30), "pnl": [1.0, 1.0, 10.0, 0.5, 0.0, -10.0],
                      "R": [0.1, 0.1, 1.0, 0.05, 0.0, -1.0], "exit": ["win", "win", "win", "time", "time", "stop"]})
    taken, months = wf.walk_forward({"c": T}, "2026-01", "2026-01", lookback=6, min_trades=2)
    assert months.trades.tolist() == [4] and len(taken) == 4
    assert months.win.tolist() == [0.5]


def win_share(text: str) -> float:
    return float(re.search(r"win ([0-9.]+)", text).group(1))


@pytest.mark.parametrize("summary", [sr_break.summary, surrender.summary, tick_straddle.summary])
def test_a_profitable_time_exit_is_a_win(summary) -> None:  # noqa: ANN001
    # the target (+10), a time exit in profit (+0.5), a stop (-10), a break-even time exit (0.0): 2 of 4 made money
    T = trades([10.0, 0.5, -10.0, 0.0])
    assert win_share(summary(T, "2026-01-12", "2026-01-17")) == pytest.approx(0.5)


def test_no_summary_counts_a_win_by_the_exit_name() -> None:
    """Every win share in precursors is pnl > 0 (or R > 0); the exit name may still select trades, and the labels'
    own outcome columns (fp1, out) are not trades."""
    pat = re.compile(r"""(\.exit == ['"]win['"]\)\.mean\(\)|\((?:x|e) == ['"]win['"]\)\.mean\(\)|_exit == ['"]win['"]\)\.mean\(\))""")
    bad = [f"{f.name}:{i}" for f in sorted((AG / "precursors").glob("*.py")) if not f.name.startswith("test_")
           for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if pat.search(line)]
    assert bad == []
