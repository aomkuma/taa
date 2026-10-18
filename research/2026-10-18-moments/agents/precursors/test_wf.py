"""The walk-forward choice (wf.py) - hand-worked answers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wf import walk_forward  # noqa: E402


def trades(month_r: dict[str, float], per_month: int = 25) -> pd.DataFrame:
    rows = []
    for mo, r in month_r.items():
        start = pd.Timestamp(mo + "-02", tz="UTC")
        for k in range(per_month):
            t = start + pd.Timedelta(hours=10 * k)
            rows.append(dict(t=t, x_t=t + pd.Timedelta(hours=1), R=r, pnl=r * 5, exit="win" if r > 0 else "stop"))
    return pd.DataFrame(rows)


MONTHS = [f"2024-{m:02d}" for m in range(1, 8)]


def test_the_choice_uses_only_the_past():
    # A pays in months 1-6 and loses in month 7; B the reverse: month 7 must use A (the past), not B (the future)
    A = trades({m: (0.5 if i < 6 else -1.0) for i, m in enumerate(MONTHS)})
    B = trades({m: (-0.5 if i < 6 else 1.0) for i, m in enumerate(MONTHS)})
    WF, months = walk_forward({"A": A, "B": B}, "2024-07", "2024-07")
    assert months.cell.tolist() == ["A"] and (WF.R == -1.0).all()


def test_too_few_trades_keeps_no_choice_until_enough():
    A = trades({m: 0.5 for m in MONTHS}, per_month=3)  # 18 trades in six months < 20
    WF, months = walk_forward({"A": A}, "2024-07", "2024-07")
    assert months.cell.tolist() == [None] and WF.empty


def test_a_trade_open_across_the_change_blocks_the_next():
    A = trades({m: 0.5 for m in MONTHS[:6]})
    long = pd.DataFrame([dict(t=pd.Timestamp("2024-06-30 23:00", tz="UTC"), x_t=pd.Timestamp("2024-07-02 05:00", tz="UTC"),
                              R=0.2, pnl=1.0, exit="win")])
    A = pd.concat([A, long, trades({"2024-07": 0.3})], ignore_index=True)
    WF, months = walk_forward({"A": A}, "2024-06", "2024-07")
    july = WF[WF.month == "2024-07"]
    assert july.t.min() >= pd.Timestamp("2024-07-02 05:00", tz="UTC")  # the 07-02 02:00 trade (open at that time) skipped


def test_unclosed_past_trades_are_not_known_yet():
    # the lookback only counts trades already closed at the month's start
    A = trades({m: 0.5 for m in MONTHS[:6]})
    A.loc[A.t >= pd.Timestamp("2024-06-01", tz="UTC"), "x_t"] = pd.Timestamp("2024-08-01", tz="UTC")  # June still open
    B = trades({m: 0.4 for m in MONTHS[:6]})
    _, months = walk_forward({"A": A, "B": B}, "2024-07", "2024-07")
    assert months.cell.tolist() == ["A"]  # A still has 125 closed trades at 0.5 > B's 0.4
    A.loc[:, "x_t"] = pd.Timestamp("2024-08-01", tz="UTC")  # none of A's trades closed by July 1
    _, months = walk_forward({"A": A, "B": B}, "2024-07", "2024-07")
    assert months.cell.tolist() == ["B"]


def test_the_longest_losing_streak():
    from wf import longest_run  # noqa: PLC0415

    assert longest_run(np.array([0, 1, 1, 0, 1, 1, 1, 0], bool)) == 3
    assert longest_run(np.array([1, 1], bool)) == 2 and longest_run(np.array([0, 0], bool)) == 0
    assert longest_run(np.array([], bool)) == 0


def test_the_weekly_report_uses_thai_weeks():
    from wf import weekly  # noqa: PLC0415

    T = pd.DataFrame({
        "t": pd.DatetimeIndex(["2026-05-04 01:00",  # Monday 08:00 Thai
                               "2026-05-08 20:00",  # Saturday 03:00 Thai: Friday's New York, the same week
                               "2026-05-10 23:00"],  # Monday 06:00 Thai, 05-11: the next week
                              tz="UTC"),
        "cell": ["a", "b", "a"], "exit": ["win", "stop", "win"], "R": [1.0, -1.0, 0.5], "pnl": [6.0, -5.2, 3.0]})
    W = weekly(T)
    assert [str(x) for x in W.week] == ["2026-05-04", "2026-05-11"]
    r = W.iloc[0]
    assert (r.cell, r.trades, r.win, r.R, r.usd, r.usd_total, r.worst) == ("a b", 2, 0.5, 0.0, 0.8, 0.8, -5.2)
    r = W.iloc[1]
    assert (r.trades, r.usd, r.usd_total) == (1, 3.0, 3.8)

