"""The readers' lines the AI trader reads (PLAN §A37, TAA-1804): the same text the research produced by
running rhythm_scan.py, picture_read.py and routine_read.py and keeping only the lines that carry a reading
(research/2026-10-23-entry/observe.py ``KEYS``). Built here from the frames handed in, so the engine and the
research send the AI the same words. Bars closed by ``as_of`` only.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from app.strategy import big_trend as bt
from app.strategy import context_read as cr
from app.strategy import level_momentum as lm
from app.strategy import picture as pc
from app.strategy import strong_levels as sl
from app.strategy import structure_read as sr
from app.strategy import zone_break as zb
from app.strategy import zone_grid as zg
from app.strategy import zone_reject as zj
from app.strategy import zone_retest as zr
from app.strategy.knowledge import Frames, _window, bars_of
from app.strategy.plan1_b2 import Bars, mt5_atr
from app.strategy.rhythm import rhythm
from app.strategy.strong_levels import closed

TH = "Asia/Bangkok"
TFS = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}
PICTURE_N, PICTURE_SIZE = 72, 1.0
KEYS = re.compile(
    r"\| rhythm|^\s+now |equal (bottoms|tops)|SWEEP|squeeze|steps|nearest line|strong levels|"
    r"volatility|phase|structure:|ELEPHANT|TIGER|BOAR|DEER|RABBIT|nothing clear|^- \d\d:\d\d T\d"
)


def keep(lines: list[str]) -> list[str]:
    """The lines that carry a reading, stripped (observe.py's filter)."""
    return [ln.strip() for ln in lines if KEYS.search(ln) and not ln.startswith("#")]


def _frame_df(fr: Frames, tf: str) -> pd.DataFrame:
    return {"M1": fr.m1, "M15": fr.m15, "H1": fr.h1, "H4": fr.h4, "D1": fr.d1}[tf]


def _scan_bars(fr: Frames, tf: str, as_of: pd.Timestamp) -> Bars:
    """rhythm_scan.load: the frame's bars opened in the 2,600 bar-lengths before ``as_of``; M5 from M1."""
    if tf == "M5":
        m1 = fr.m1[(fr.m1.index >= as_of - pd.Timedelta(minutes=5 * 1400)) & (fr.m1.index < as_of)]
        agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
        d = m1.resample("5min").agg(agg).dropna()
    else:
        d = _frame_df(fr, tf)
        d = d[(d.index >= as_of - pd.Timedelta(minutes=TFS[tf] * 2600)) & (d.index < as_of)]
    return bars_of(d, TFS[tf])


def rhythm_lines(fr: Frames, as_of: pd.Timestamp) -> list[str]:
    """rhythm_scan.py: per frame the big trend and the rhythm, and where the running leg is now."""
    t = as_of.value
    out: list[str] = []
    for tf in TFS:
        x = closed(_scan_bars(fr, tf, as_of), t)
        r = rhythm(x, t)
        sign, atr, pts, big = r.sign, r.atr, r.swings, r.big
        highs = [p for _, k, p in pts if k == 1][-3:]
        lows = [p for _, k, p in pts if k == -1][-3:]
        down = len(highs) >= 2 and len(lows) >= 2 and highs[-1] < highs[-2] and lows[-1] < lows[-2]
        up = len(highs) >= 2 and len(lows) >= 2 and highs[-1] > highs[-2] and lows[-1] > lows[-2]
        if sign < 0:
            name = "DOWN"
        elif sign > 0:
            name = "UP"
        else:
            name = "down (big trend not)" if down else "up (big trend not)" if up else "none"
        price = float(x.c[-1])
        trend = "DOWN" if big.sign < 0 else "UP" if big.sign > 0 else "none"
        out.append(
            f"{tf:3s} ATR {atr:6.2f} | big trend {trend} (LH {big.lower_highs}, LL {big.lower_lows}, "
            f"HH {big.higher_highs}, HL {big.higher_lows}) | rhythm {name}"
        )
        if len(pts) >= 2:
            _, k, p = pts[-1]
            push = abs(p - pts[-2][2])
            now = (price - p) * (-k)  # how far the running leg has come from the last swing
            back = now / push if push else np.nan
            heading = "down" if k == 1 else "up"
            with_rhythm = (sign < 0 and k == 1) or (sign > 0 and k == -1)
            how = (
                "WITH the rhythm (a push)"
                if with_rhythm
                else "AGAINST the rhythm (a pullback)"
                if sign
                else "no rhythm"
            )
            out.append(
                f"    now {price:.2f}: running {heading} from {p:.1f} for {now:.1f} ({now / atr:.1f} ATR, "
                f"{back * 100:.0f} % of the last leg) - {how}"
            )
    return out


def picture_lines(fr: Frames, minutes: int, as_of: pd.Timestamp) -> list[str]:
    """picture_read.py on one frame built from M1: the steps, equal lows / highs, their sweeps, the
    squeeze."""
    m1 = fr.m1[
        (fr.m1.index >= as_of - pd.Timedelta(minutes=minutes * (PICTURE_N + 40))) & (fr.m1.index < as_of)
    ]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}
    d = m1.resample(f"{minutes}min").agg(agg).dropna()
    h, lo, c, v = (d[k].to_numpy(float) for k in ("high", "low", "close", "tick_volume"))
    atr = float(mt5_atr(h, lo, c, 14)[-1])
    n = PICTURE_N
    d, h, lo, c, v = d.iloc[-n:], h[-n:], lo[-n:], c[-n:], v[-n:]
    tt = [x.tz_convert(TH).strftime("%H:%M") for x in pd.DatetimeIndex(d.index)]
    out: list[str] = []
    last = 6
    hl = sum(bool(lo[i] > lo[i - 1]) for i in range(len(lo) - last + 1, len(lo)))
    hh = sum(bool(h[i] > h[i - 1]) for i in range(len(h) - last + 1, len(h)))
    steps = (
        "UP steps" if hl >= last - 2 and hh >= last - 2 else "DOWN steps" if hl <= 1 and hh <= 1 else "mixed"
    )
    out.append(f"  the last {last} bars: {hl}/{last - 1} higher lows, {hh}/{last - 1} higher highs ({steps})")
    for pool in pc.pools(h, lo, c, atr):
        name = pool["name"]
        touches = ", ".join(f"{p:.2f} @{tt[j]}" for j, p in pool["touches"])
        out.append(f"  equal {name} x{len(pool['touches'])} at {pool['mean']:.2f} ({touches})")
        for s in pc.sweeps(pool, h, lo, c, v, atr):
            out.append(
                f"    SWEEP {'under' if name == 'bottoms' else 'over'} it at {tt[s['i']]}: "
                f"{'low' if name == 'bottoms' else 'high'} {s['extreme']:.2f}, "
                f"closed back {s['close']:.2f}, volume {s['volume']:.1f} x the mean; since then "
                f"{s['after']} bars: {s['up']} higher-low-and-higher-high, "
                f"{s['down']} lower-low-and-lower-high"
            )
    rng = pc.squeeze_range(h, lo, atr)
    out.append(
        f"  the last 12 bars' range {rng:.1f} ATR{' (a squeeze)' if rng < 3 else ''}; "
        f"last volume {v[-1] / v.mean():.1f} x the mean"
    )
    _ = bt  # the swings line of picture_read carries no reading the AI is sent
    return out


def _fmt_sign(v: int) -> str:
    return {1: "up (HH/HL)", -1: "down (LH/LL)", 0: "mixed"}[int(v)]


def routine_lines(fr: Frames, as_of: pd.Timestamp) -> list[str]:
    """routine_read.py's reading lines: the nearest line, the strong levels, volatility, phase, structure, the
    animal in front and the shadow weapons' signals today."""
    minutes = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}
    data = {tf: bars_of(_frame_df(fr, tf), m) for tf, m in minutes.items()}
    t = as_of.value
    w = {tf: _window(data[tf], t, 700) for tf in minutes}
    d1 = data["D1"]
    g = zg.grid_rows(d1.t_open, d1.o, d1.h, d1.lo, d1.c)
    st = zg.grid_at(g, t)
    price = float(sl.closed(w["M15"], t).c[-1])
    out: list[str] = []
    shifts = np.flatnonzero(g.shift[: st.row + 1])
    line, dist, share = zg.nearest_line(st, price)
    out.append(f"- price {price:.2f}: nearest line {line:.2f} ({dist:.1f} USD, {share:.2f} step)")
    lines = sl.zone_lines(
        w["H4"], w["D1"], t, st.anchor, st.step, price - 1.6 * st.step, price + 1.6 * st.step
    )
    anchors = [float(g.anchor[i]) for i in shifts[-6:]]
    strong = sl.strong_levels(w["H4"], w["D1"], t, st.step, anchors)
    above = sorted([x for x in strong if x.price > price], key=lambda x: x.price)[:3]
    below = sorted([x for x in strong if x.price < price], key=lambda x: -x.price)[:3]
    out.append(
        f"- strong levels above: {', '.join(f'{x.price:.1f} ({x.source}, {x.touches})' for x in above)}"
    )
    out.append(
        f"- strong levels below: {', '.join(f'{x.price:.1f} ({x.source}, {x.touches})' for x in below)}"
    )
    day = cr.last_day(w["D1"], t)
    ph = sr.phase(w["D1"], t)
    one_way_word = "one-way UP" if ph > 0 else "one-way DOWN" if ph < 0 else "not one-way"
    out.append(f"- phase (the last 3 D1 closes): {one_way_word}")
    for tf in ("D1", "H4", "H1", "M15"):
        s = sr.structure(w[tf], t)
        out.append(f"- {tf} structure: {_fmt_sign(s.sign)}, picture {'clear' if s.clear else 'not clear'}")
    vol = cr.vol_ratio(w["H1"], t)
    run, rng = cr.day_so_far(w["H1"], t, price, 1, st.step)
    out.append(
        f"- H1 volatility {vol:.2f} x usual; today so far: {run:+.2f} step from the open (up = +), "
        f"range {rng:.2f} step"
    )
    near_rel = [r for r in fr.releases if abs((pd.Timestamp(r.at) - as_of).total_seconds()) <= 3600]
    at_line = lm.level_momentum(w["M15"], t, line, 0.15 * st.step, 1, t - 24 * 3600 * 10**9).bars_at_line
    animals = []
    if vol > 1.4 or rng > 2:
        animals.append(f"ELEPHANT (vol {vol:.2f}, range {rng:.2f} step) -> step back")
    if near_rel:
        animals.append(f"TIGER ({', '.join(r.event for r in near_rel)})")
    if ph != 0 or day.strong:
        one_way = "3-day one-way " + ("up" if ph > 0 else "down") if ph else ""
        strong_day = "yesterday strong " + ("up" if day.direction > 0 else "down") if day.strong else ""
        animals.append(f"BOAR ({one_way}{' + ' if ph and day.strong else ''}{strong_day})")
    if at_line >= 8:
        animals.append(f"DEER (price {at_line} M15 bars at the line {line:.1f})")
    if vol < 0.9 and ph == 0:
        animals.append(f"RABBIT (quiet: vol {vol:.2f}, no one-way run)")
    out.append("- " + ("; ".join(animals) if animals else "nothing clear - no animal"))
    m15 = data["M15"]
    k = np.searchsorted(g.known, m15.avail, side="right") - 1
    sel = slice(max(0, len(m15.c) - 2000), int(np.searchsorted(m15.avail, t, side="right")))
    o, h, lo, c = (arr[sel] for arr in (m15.o, m15.h, m15.lo, m15.c))
    a_, s_ = g.anchor[k][sel], g.step[k][sel]
    t0 = m15.t_open[sel]
    day_start = as_of.tz_convert("Europe/Athens").normalize().tz_convert("UTC").value
    sig = [("T1 re-test", e.entry_bar, e.side, e.entry, e.stop) for e in zr.zone_retests(h, lo, c, a_, s_)]
    sig += [
        ("T2 rejection", e.entry_bar, e.side, e.entry, e.stop)
        for e in zj.zone_rejections(o, h, lo, c, a_, s_)
    ]
    sig += [
        (f"T4 {'through' if e.through else 'bounce'}", e.entry_bar, e.side, e.entry, e.stop)
        for e in zb.zone_breaks(h, lo, c, a_, s_)
    ]
    for name, q, side, entry, stop in sorted([x for x in sig if t0[x[1]] >= day_start], key=lambda x: x[1]):
        at = pd.Timestamp(int(t0[q]) + 15 * 60 * 10**9, tz="UTC").tz_convert(TH)
        out.append(
            f"- {at:%H:%M} {name} {'BUY' if side > 0 else 'SELL'} {entry:.2f}, stop {stop:.2f} "
            f"(risk {abs(entry - stop):.1f})"
        )
    _ = (lines, math)  # the zone lines feed the AI through the knowledge readings, not as text
    return out


def reader_lines(fr: Frames, as_of: pd.Timestamp) -> list[str]:
    """Every reading line the AI is sent, in the research's order (rhythm, picture M5 / M15, routine)."""
    raw = rhythm_lines(fr, as_of) + picture_lines(fr, 5, as_of) + picture_lines(fr, 15, as_of)
    return keep(raw + routine_lines(fr, as_of))
