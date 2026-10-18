"""moments by hand: which runs join the library (run_starts), and the zoom - the smaller timeframe's bars covering a
larger window (small_span) and the readings filled from them (zoom_all).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_moments.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from moments import run_starts, small_span, zoom_all  # noqa: E402


def test_run_starts():
    # a summer Wednesday (EDT): 13:31 UTC = New York 09:31 (a window); 04:00 UTC = 11:00 Thai (a window);
    # 20:00 UTC = New York 16:00 (no window); a Saturday 13:31 UTC (no window)
    index = pd.DatetimeIndex(["2026-07-15 13:31", "2026-07-15 04:00", "2026-07-15 20:00", "2026-07-18 13:31",
                              "2023-10-31 13:31"], tz="UTC")
    C = pd.DataFrame({"i": [0, 1, 2, 3, 4], "side": [1, -1, 1, 1, -1]})
    R = run_starts(C, index, pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-10-17", tz="UTC"))
    assert R.i.tolist() == [0, 1]  # in a window, on a weekday, inside the span
    assert R.cls.tolist() == ["ran_up", "ran_dn"]
    assert R.bar_t.tolist() == [index[0], index[1]]


def test_small_span_by_hand():
    # a larger bar = 4 smaller ones; completion times in minutes
    big, small = np.array([4, 8, 12, 16, 20]), np.arange(1, 21)
    assert small_span(big, small, 4, 3) == (8, 19)  # larger bars 2..4 = the smaller ones completing at 9..20
    assert small_span(big, small, 1, 3) == (0, 7)  # the window starts at the first bar
    # a larger bar missing its last minute completes with its last smaller bar (7); a weekend gap (7 -> 27)
    big = np.array([4, 7, 30, 34])
    small = np.array([1, 2, 3, 4, 5, 6, 7, 27, 28, 29, 30, 31, 32, 33, 34])
    assert small_span(big, small, 3, 2) == (7, 14)
    assert small_span(big, small, 2, 2) == (4, 10)


def test_zoom_all_reads_the_smaller_span_against_the_larger_close():
    # the smaller timeframe: 14 bars completing at 1..14; the larger: 3 bars of 4 (completing at 4, 8, 12); a window of
    # 2 larger bars ending at bar 2 = the smaller bars 4..11 (bars 12, 13 belong to the larger bar still forming)
    h, lo = np.full(14, 125.0), np.full(14, 112.0)
    # ZigZag swings (bar, value, type, confirmed at): trough 1, peak 2 before the span; inside: trough 4 (100), peak 6
    # (130), trough 8 (110), peak 10 (150, confirmed only at 12); after: trough 11 (95, confirmed at 13)
    sw = [(1, 105.0, -1, 2), (2, 140.0, 1, 3), (4, 100.0, -1, 5), (6, 130.0, 1, 7), (8, 110.0, -1, 9), (10, 150.0, 1, 12),
          (11, 95.0, -1, 13)]
    for i, v, t, _ in sw:
        (h if t > 0 else lo)[i] = v
    piv = tuple(np.array([s[j] for s in sw]) for j in range(4))
    c_small = np.full(14, 120.0)
    c_small[11], c_small[13] = 135.0, 105.0  # the span's last close is the larger bar's; bar 13 comes later
    sm = dict(R=dict(h=h, lo=lo, c=c_small), piv=piv, avail=np.arange(1, 15))
    big = dict(R=dict(c=np.array([118.0, 121.0, 135.0])), avail=np.array([4, 8, 12]), bi=np.array([2, 2, 2, 0]))
    keep = dict(struct=-1, brk=-1, size=5.0)
    f = [keep, dict(struct=9, brk=0, size=6.0), dict(struct=0, brk=9, size=7.0), dict(struct=9, brk=0, size=8.0)]
    changed = zoom_all(f, big, sm, 2)
    # at bar 11: troughs 100 -> 110 (higher), peaks 130 -> the running high since the trough at 8 (150, higher): HH/HL
    # = 1; the close 135 above the last confirmed top 130 (the peak at 10 is confirmed only at 12): 1
    assert f[0] is keep  # its own readings: untouched
    assert (f[1]["struct"], f[1]["brk"], f[1]["size"]) == (1, 0, 6.0)  # only the missing reading filled
    assert (f[2]["struct"], f[2]["brk"], f[2]["size"]) == (0, 1, 7.0)
    # the 4th moment at larger bar 0 (its window starts at the first bar: smaller bars 0..3): one peak (140) and the
    # troughs 105 -> the running low since the peak (112) - too few swings at the smaller timeframe too
    assert f[3]["struct"] == 9
    assert changed.tolist() == [0, 1, 1, 0]
