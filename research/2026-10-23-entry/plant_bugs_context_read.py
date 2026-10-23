"""Planted bugs for app/strategy/context_read.py against tests/unit/test_context_read.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_context_read.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("vol: the forming bar read", [("    x = closed(b, t)\n    atr = mt5_atr(x.h, x.lo, x.c, 14)", "    x = b\n    atr = mt5_atr(x.h, x.lo, x.c, 14)")]),
    ("vol: the mean, not the median", [("return float(atr[-1] / np.median(last))", "return float(atr[-1] / np.mean(last))")]),
    ("vol: ATR(20)", [("    atr = mt5_atr(x.h, x.lo, x.c, 14)\n    last", "    atr = mt5_atr(x.h, x.lo, x.c, 20)\n    last")]),
    ("vol: no minimum", [("if len(last) < min_periods or", "if len(last) < 1 or")]),
    ("timing: UTC, not the zone", [('local = pd.Timestamp(t, tz="UTC").tz_convert(zone)', 'local = pd.Timestamp(t, tz="UTC")')]),
    ("timing: the window's end included", [("return minutes_from(t, start, zone) >= 0 > minutes_from(t, end, zone)", "return minutes_from(t, start, zone) >= 0 >= minutes_from(t, end, zone)")]),
    ("volume: today's bar in the mean", [("wanted = t_open[i] - day_ns * np.arange(1, days + 1)", "wanted = t_open[i] - day_ns * np.arange(0, days + 1)")]),
    ("volume: the nearest bar, any time", [("ok = (pos < len(t_open)) & (t_open[np.minimum(pos, len(t_open) - 1)] == wanted)", "ok = pos < len(t_open)")]),
    ("day: the ATR of the day itself", [("a = float(atr[-2])  # the ATR known before that day", "a = float(atr[-1])  # the ATR known before that day")]),
    ("day: body 0.8 is strong", [("return DayContext(d, body, pos, body >= 1.0 and pos >= 0.7)", "return DayContext(d, body, pos, body >= 0.8 and pos >= 0.7)")]),
    ("day: the position from the low for a down day", [("pos = (c - lo) / (h - lo) if d > 0 else (h - c) / (h - lo)", "pos = (c - lo) / (h - lo)")]),
    ("day: the forming day read", [("    x = closed(d1, t)\n    if len(x.c) < 22:", "    x = d1\n    if len(x.c) < 22:")]),
    ("day so far: the UTC day", [('days = pd.DatetimeIndex(x.t_open, tz="UTC").tz_convert(SERVER_TZ).normalize()', 'days = pd.DatetimeIndex(x.t_open, tz="UTC").normalize()')]),
    ("day so far: side ignored", [("return (price - o) * side / step,", "return (price - o) / step,")]),
]

if __name__ == "__main__":
    main("app.strategy.context_read", ROOT / "tests/unit/test_context_read.py", BUGS)
