"""p4_trades by hand: the owner's windows on the Thai and New York clocks (summer and winter), the candidates kept,
and the metrics per window.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_p4_trades.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p4_trades as W  # noqa: E402

U = lambda s: pd.Timestamp(s, tz="UTC").value  # noqa: E731


def test_asia_and_london_on_the_thai_clock():
    # Thai = UTC + 7 all year: Asia 07:00 - 09:00 Thai = 00:00 - 02:00 UTC, London 13:00 - 14:00 Thai = 06:00 - 07:00 UTC
    assert W.window_of(U("2026-01-12 00:00")) == "Asia" and W.window_of(U("2026-01-12 01:59")) == "Asia"
    assert W.window_of(U("2026-01-12 02:00")) is None and W.window_of(U("2025-12-31 23:59")) is None
    assert W.window_of(U("2026-07-13 06:00")) == "London" and W.window_of(U("2026-07-13 07:00")) is None
    assert W.window_of(U("2026-01-12 05:59")) is None
    # +- 30 minutes for London (the assumption): 12:30 - 14:30 Thai = 05:30 - 07:30 UTC
    assert W.window_of(U("2026-01-12 05:30"), 30) == "London" and W.window_of(U("2026-01-12 07:29"), 30) == "London"
    assert W.window_of(U("2026-01-12 07:30"), 30) is None and W.window_of(U("2026-01-12 05:29"), 30) is None


def test_new_york_follows_new_york_time():
    # winter (EST, UTC-5): 09:30 - 11:30 NY = 14:30 - 16:30 UTC = 21:30 - 23:30 Thai
    assert W.window_of(U("2026-01-12 14:30")) == "NY" and W.window_of(U("2026-01-12 16:29")) == "NY"
    assert W.window_of(U("2026-01-12 14:29")) is None and W.window_of(U("2026-01-12 16:30")) is None
    # summer (EDT, UTC-4; the US switched on 2026-03-08): 13:30 - 15:30 UTC = 20:30 - 22:30 Thai
    assert W.window_of(U("2026-03-09 13:30")) == "NY" and W.window_of(U("2026-03-09 15:29")) == "NY"
    assert W.window_of(U("2026-03-09 15:30")) is None and W.window_of(U("2025-10-20 13:30")) == "NY"
    # the winter hour 14:30 UTC in summer is still inside (10:30 NY); 16:00 UTC in summer is 12:00 NY: outside
    assert W.window_of(U("2026-03-09 14:30")) == "NY" and W.window_of(U("2026-03-09 16:00")) is None


def test_in_windows_keeps_and_names():
    c = pd.DataFrame(dict(t_entry=[U("2026-01-12 00:30"), U("2026-01-12 03:00"), U("2026-01-12 06:15"),
                                   U("2026-01-12 15:00"), U("2026-01-12 05:45")], k=[1, 2, 3, 4, 5]))
    x = W.in_windows(c, 0)
    assert x.k.tolist() == [1, 3, 4] and x.window.tolist() == ["Asia", "London", "NY"]
    assert W.in_windows(c, 30).k.tolist() == [1, 3, 4, 5]
    assert W.in_windows(c.iloc[:0], 0).empty


def test_wn_skips_the_half_hour_after_ten_new_york():
    assert W.ny_after_ten(U("2026-01-12 15:00")) and W.ny_after_ten(U("2026-01-12 15:29"))  # winter: 10:00 NY = 15:00 UTC
    assert not W.ny_after_ten(U("2026-01-12 15:30")) and not W.ny_after_ten(U("2026-01-12 14:59"))
    assert W.ny_after_ten(U("2026-03-09 14:00")) and not W.ny_after_ten(U("2026-03-09 15:00"))  # summer: 14:00 UTC
    c = pd.DataFrame(dict(t_entry=[U("2026-01-12 14:45"), U("2026-01-12 15:10"), U("2026-01-12 15:40"), U("2026-01-12 00:30")],
                          window=["NY", "NY", "NY", "Asia"], k=[1, 2, 3, 4]))
    assert W.no_ny_ten(c, {}).k.tolist() == [1, 3, 4]


def test_metrics_by_window():
    A = pd.DataFrame(dict(variant="W", part="P1", news_cost=0.0, entry_t=[1, 2, 3, 4], pnl=[2.0, -1.0, 1.0, -2.0],
                          R=[1.0, -0.5, 0.5, -1.0], exit=["target", "stop", "structure", "stop"],
                          window=["Asia", "Asia", "NY", "NY"]))
    M = W.metrics_by_window(A).set_index("window")
    assert M.loc["all", "n"] == 4 and M.loc["Asia", "n"] == 2 and M.loc["London", "n"] == 0
    assert M.loc["Asia", "R"] == 0.25 and M.loc["NY", "R"] == -0.25 and M.loc["NY", "x_stop"] == 1
    assert M.loc["all", "x_stop"] == 2 and M.loc["all", "usd"] == 0.0


def test_small_ticks_keeps_the_last_days(monkeypatch):
    import sweep_detector as sd

    import numpy as np

    monkeypatch.setattr(sd, "learning_ticks", lambda d: (np.array([d.value], np.int64), np.array([1.0]), np.array([1.2])))
    tk = W.SmallTicks()
    for k in range(10):
        t, _, _ = tk.span(U(f"2026-01-{k + 5:02d} 12:00"))
        assert t.tolist() == [U(f"2026-01-{k + 5:02d}"), U(f"2026-01-{k + 6:02d}")]  # the day and the next, as before
    assert len(tk.spans) <= W.SmallTicks.KEEP and len(tk.days) <= W.SmallTicks.KEEP
