"""verify_p2 by hand: its own metrics, the re-derivation of a trade from ticks, one position at a time, the weekdays.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_verify_p2.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_p2 as V  # noqa: E402

S = 10**9


def test_weekdays():
    assert V.weekdays("2025-10-18", "2026-01-16") == 64 and V.weekdays("2026-01-16", "2026-04-18") == 66
    assert V.weekdays("2026-01-17", "2026-01-19") == 0  # a weekend


def test_metrics_by_hand():
    # buys in at 100 with the stop at 98 (risk 2): USD 2, -1, -1, 3, -2 -> R 1, -0.5, -0.5, 1.5, -1 (mean 0.1); the
    # cumulative USD 2, 1, 0, 3, 1 -> the drawdown 2; the longest losing streak -1, -1 (2 trades, -2 USD)
    pnl = [2.0, -1.0, -1.0, 3.0, -2.0]
    ex = ["target", "stop", "structure", "target", "stop"]
    rows = [dict(entry_t=i, side=1, entry=100.0, stop=98.0, pnl=p, exit=e) for i, (p, e) in enumerate(zip(pnl, ex, strict=True))]
    m = V.metrics(rows[::-1], "P1")  # given out of order: sorted by time inside
    sd = math.sqrt(sum((x - 0.1) ** 2 for x in [1, -0.5, -0.5, 1.5, -1]) / 4)
    assert m["n"] == 5 and m["per_day"] == pytest.approx(5 / 64) and m["win"] == pytest.approx(0.4)
    assert m["R"] == pytest.approx(0.1) and m["R_hi"] == pytest.approx(0.1 + 1.96 * sd / math.sqrt(5))
    assert m["usd"] == pytest.approx(1.0) and m["dd"] == 2.0 and m["worst"] == -2.0
    assert (m["streak"], m["streak_usd"]) == (2, -2.0)
    assert (m["x_stop"], m["x_target"], m["x_structure"], m["x_time"], m["x_break"]) == (2, 2, 1, 0, 0)
    # a sell: in 100, the stop 103 (risk 3), USD +1.5 -> R 0.5; a first loss is a drawdown from 0
    m = V.metrics([dict(entry_t=0, side=-1, entry=100.0, stop=103.0, pnl=1.5, exit="time")], "P2")
    assert m["R"] == pytest.approx(0.5) and m["dd"] == 0.0 and math.isnan(m["R_lo"])
    m = V.metrics([dict(entry_t=0, side=1, entry=100.0, stop=98.0, pnl=-3.0, exit="stop"),
                   dict(entry_t=1, side=1, entry=100.0, stop=98.0, pnl=1.0, exit="time")], "P2")
    assert m["dd"] == 3.0
    # a flat trade (0) is neither a win nor a loss in the streak; the streak in time order (rows given 2, 1, 3)
    m = V.metrics([dict(entry_t=t, side=1, entry=100.0, stop=98.0, pnl=p, exit="time") for t, p in
                   ((1, -1.0), (2, 0.0), (3, -1.0))], "P1")
    assert (m["streak"], m["streak_usd"], m["win"]) == (1, -1.0, 0.0)
    m = V.metrics([dict(entry_t=t, side=1, entry=100.0, stop=98.0, pnl=p, exit="time") for t, p in
                   ((2, -1.0), (1, 2.0), (3, -1.0))], "P1")
    assert (m["streak"], m["streak_usd"]) == (2, -2.0)


def tk(rows):
    t, b = zip(*rows, strict=True)
    return pd.DataFrame(dict(t=[x * S for x in t], bid=list(b), ask=[x + 0.2 for x in b]))


def trade(**kw):
    base = dict(side=1, t_entry=0, entry_t=0, entry=100.27, stop=98.0, exit="stop", exit_t=20 * S, exit_px=97.5,
                pnl=97.5 - 100.27, R=(97.5 - 100.27) / 2.27, target=float("nan"), t_limit=3600 * S, t_struct=float("nan"))
    base.update(kw)
    return base


def test_rederive_a_stop():
    T = tk([(0, 100.0), (10, 99.0), (20, 97.5), (30, 101.0)])
    assert V.rederive(trade(), T) == []
    assert V.rederive(trade(entry=100.20), T) == ["the fill price", "the USD / R"]
    assert V.rederive(trade(exit_px=98.0, pnl=98.0 - 100.27, R=(98.0 - 100.27) / 2.27), T) == ["the stop's tick / price"]
    # a tick past the stop before the recorded exit
    T2 = tk([(0, 100.0), (10, 97.9), (20, 97.5)])
    assert "a tick past the stop before the exit" in V.rederive(trade(), T2)
    assert V.rederive(trade(entry_t=10 * S), T) == ["the fill tick"]
    assert V.rederive(trade(pnl=97.5 - 100.27 + 0.01), T) == ["the USD / R"]  # the USD wrong, the R right


def test_rederive_target_time_structure_break_and_a_sell():
    T = tk([(0, 100.0), (10, 103.9), (20, 104.6), (30, 104.0)])
    ok = trade(exit="target", target=104.0, exit_t=20 * S, exit_px=104.0, pnl=3.73, R=3.73 / 2.27)
    assert V.rederive(ok, T) == []
    assert V.rederive(dict(ok, exit_t=30 * S), T) == ["the target's tick / price"]  # it was reached at 20 s
    tm = trade(exit="time", t_limit=25 * S, exit_t=30 * S, exit_px=104.0, pnl=104.0 - 100.27, R=(104.0 - 100.27) / 2.27)
    assert V.rederive(tm, T) == []
    assert V.rederive(dict(tm, t_limit=15 * S), T) == ["the time exit tick"]  # the first tick at / after 15 s is 20 s
    st = trade(exit="structure", t_struct=20 * S, exit_t=20 * S, exit_px=104.6, pnl=104.6 - 100.27, R=(104.6 - 100.27) / 2.27)
    assert V.rederive(st, T) == []
    Tb = tk([(0, 100.0), (10, 101.0), (10 + 1801, 90.0)])
    br = trade(exit="break", exit_t=10 * S, exit_px=101.0, pnl=101.0 - 100.27, R=(101.0 - 100.27) / 2.27)
    assert V.rederive(br, Tb) == []
    assert V.rederive(br, tk([(0, 100.0), (10, 101.0), (10 + 1800, 90.0)])) == ["the break tick"]
    # a sell: in at the bid - 0.07, the stop read on the ask
    Ts = tk([(0, 100.0), (10, 101.9), (20, 99.0)])
    sell = dict(side=-1, t_entry=0, entry_t=0, entry=99.93, stop=102.0, exit="stop", exit_t=10 * S, exit_px=102.1,
                pnl=99.93 - 102.1, R=(99.93 - 102.1) / 2.07, target=float("nan"), t_limit=3600 * S, t_struct=float("nan"))
    assert V.rederive(sell, Ts) == []


def test_raw_ticks_in_nanoseconds_and_never_the_exam():
    # the 2026-01-09 release minute: the lowest bid of 13:30 UTC is 4459.03 (the A1 tick table)
    x = V.raw_ticks(pd.Timestamp("2026-01-09", tz="UTC"))
    a, b = pd.Timestamp("2026-01-09 13:30", tz="UTC").value, pd.Timestamp("2026-01-09 13:31", tz="UTC").value
    m = x[(x.t >= a) & (x.t < b)]
    assert len(m) > 100 and m.bid.min() == pytest.approx(4459.03, abs=0.001)
    assert x.t.is_monotonic_increasing
    assert V.raw_ticks(pd.Timestamp("2026-04-18", tz="UTC")).empty  # the exam is never read


def test_raw_ticks_refuses_an_exam_day_even_when_a_file_is_there(tmp_path, monkeypatch):
    # a fake file for Monday 2026-04-20 in a temporary folder (no real exam tick is ever read): refused unread
    pd.DataFrame(dict(time_utc=pd.to_datetime(["2026-04-20 10:00"], utc=True), bid=[1.0], ask=[1.2])).to_parquet(
        tmp_path / "2026-04-20.parquet")
    monkeypatch.setattr(V, "TICKS", tmp_path)
    assert V.raw_ticks(pd.Timestamp("2026-04-20", tz="UTC")).empty


def test_one_at_a_time():
    rows = [dict(entry_t=0, exit_t=10), dict(entry_t=10, exit_t=20), dict(entry_t=15, exit_t=30)]
    assert V.one_at_a_time(rows) == 1  # 15 is before the exit at 20
    assert V.one_at_a_time(rows[:2]) == 0  # an entry at the exit moment is allowed
