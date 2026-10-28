"""The assessment's data (SPEC.md section 3): every candidate of triggers T1 (re-test), T2 (rejection) and T4
(consolidation, then the break) on M15, 2023-09 .. 2026-10-16, with every component's reading at its entry - only
the bot's code (app/strategy/*), only bars closed by the entry - and its outcome with the exits of zone_wait.py
(the next half-step line at least 0.25 step away, the stop first, out after 32 bars, 0.35 USD spread).

Frames (gold intraday, SPEC section 0): entry E = M15, E+1 = H1, trend M15 / H1 / H4 / D1, zone D1, near / far
H4 / D1, volatility H1.

    .venv/Scripts/python research/2026-10-23-entry/candidates.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import zone_wait as ZW  # noqa: E402

from app.strategy import context_read as cr  # noqa: E402
from app.strategy import level_momentum as lm  # noqa: E402
from app.strategy import strong_levels as sl  # noqa: E402
from app.strategy import structure_read as sr  # noqa: E402
from app.strategy import zone_break as zb  # noqa: E402
from app.strategy import zone_grid as zg  # noqa: E402
from app.strategy import zone_reject as zj  # noqa: E402
from app.strategy import zone_retest as zr  # noqa: E402
from app.strategy.plan1_b2 import Bars  # noqa: E402

MIN = 60 * 10**9
FRAMES = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}
KEEP = {"M15": 400, "H1": 600, "H4": 600, "D1": 300}  # bars kept before a decision (the lookbacks fit inside)


def frame(tf: str) -> tuple[pd.DataFrame, Bars]:
    d = ZW.load(tf)
    t = d.index.as_unit("ns").asi8
    return d, Bars(t, t + FRAMES[tf] * MIN, d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float),
                   d.close.to_numpy(float))


def window(b: Bars, t: int, n: int) -> Bars:
    j = int(np.searchsorted(b.avail, t, side="right"))
    s = slice(max(0, j - n), j)
    return Bars(b.t_open[s], b.avail[s], b.o[s], b.h[s], b.lo[s], b.c[s])


def main() -> None:
    data = {tf: frame(tf) for tf in FRAMES}
    d1df, D1 = data["D1"]
    G = zg.grid_rows(D1.t_open, D1.o, D1.h, D1.lo, D1.c)
    m, M = data["M15"]
    sel = (m.index >= "2023-08-15") & (m.index < "2026-10-17")
    m = m[sel]
    M = Bars(M.t_open[sel], M.avail[sel], M.o[sel], M.h[sel], M.lo[sel], M.c[sel])
    vol = m.tick_volume.to_numpy(float)
    k = np.searchsorted(G.known, M.avail, side="right") - 1
    A, S = G.anchor[k], G.step[k]
    o, h, lo, c = M.o, M.h, M.lo, M.c
    ev = [("T1", e.entry_bar, e.side, e.entry, e.stop, e.line) for e in zr.zone_retests(h, lo, c, A, S)]
    ev += [("T2", e.entry_bar, e.side, e.entry, e.stop, e.line) for e in zj.zone_rejections(o, h, lo, c, A, S)]
    ev += [(f"T4 {'through' if e.through else 'bounce'}", e.entry_bar, e.side, e.entry, e.stop, e.line)
           for e in zb.zone_breaks(h, lo, c, A, S)]
    rows = []
    for trig, q, side, entry, stop, line in ev:
        if q + 33 >= len(c) or not math.isfinite(S[q]):
            continue
        t = int(M.avail[q])
        step, anchor = float(S[q]), float(A[q])
        w = {tf: window(data[tf][1], t, KEEP[tf]) for tf in FRAMES}
        r = ZW.trade(h, lo, c, q, side, entry, stop, step, anchor)
        risk = abs(entry - stop)
        # C1: the stop against the pools (recent M15 / H1 swings, the previous day's high / low, round numbers)
        pools = [s.price for s in sl.swings(w["M15"], t, last=96)] + [s.price for s in sl.swings(w["H1"], t, last=120)]
        dctx = cr.last_day(w["D1"], t)
        xd = sl.closed(w["D1"], t)
        if len(xd.c):
            pools += [float(xd.h[-1]), float(xd.lo[-1])]
        in_zone, margin = sl.stop_check(pools, side, entry, stop, sl.pool_band(step))
        # C2 / C3
        st_h1 = sr.structure(w["H1"], t)
        trend = sr.trend([w["M15"], w["H1"], w["H4"], w["D1"]], t, side)
        # C4 at the traded line on H1 over 5 days (bounce side: the side the line pushes price toward the trade)
        mom = lm.level_momentum(w["H1"], t, line, 0.15 * step, side, t - 5 * 24 * 60 * MIN)
        mom_e = lm.level_momentum(w["M15"], t, line, 0.15 * step, side, t - 24 * 60 * MIN)
        # C5 / C5b
        _, _, share = zg.nearest_line(zg.GridState(anchor, step, 0, 0), entry)
        st_now = zg.grid_at(G, t)
        anchors = [float(G.anchor[i]) for i in np.flatnonzero(G.shift[: st_now.row + 1])[-6:]]
        lv = sl.strong_levels(w["H4"], w["D1"], t, step, anchors)
        room = sl.room(lv, side, entry, stop, 0.15 * step)
        zl = sl.zone_lines(w["H4"], w["D1"], t, anchor, step, line - 0.01, line + 0.01)
        # C6-C9
        run, rng = cr.day_so_far(w["H1"], t, entry, side, step)
        rows.append(dict(
            trig=trig, t=pd.Timestamp(t, tz="UTC"), side=side, r=r, risk=risk, risk_step=risk / step,
            c1_stop_in_pool=in_zone, c1_margin_step=margin / step if math.isfinite(margin) else np.nan,
            c1_late_step=abs(entry - line) / step,
            c2_h1_struct=st_h1.sign * side, c2_h1_clear=st_h1.clear,
            c3_m15=trend[0], c3_h1=trend[1], c3_h4=trend[2], c3_d1=trend[3], c3_phase=sr.phase(w["D1"], t) * side,
            c4_touches=mom.touches, c4_worn=mom.worn, c4_approach=mom.approach, c4_bars_at_line=mom_e.bars_at_line,
            c5_share=share, c5b_room_r=room, c5b_line_touches=zl[0].touches if zl else np.nan,
            c6_vol=cr.vol_ratio(w["H1"], t, window=480, min_periods=100),
            c7_min_10ny=cr.minutes_from(t, "10:00", "America/New_York"),
            c7_thai_hour=pd.Timestamp(t, tz="UTC").tz_convert("Asia/Bangkok").hour,
            c8_rel_vol=cr.rel_volume(M.t_open, vol, q),
            c9_day_dir=dctx.direction * side, c9_day_strong=dctx.strong, c9_day_body=dctx.body_atr,
            c9_run=run, c9_range=rng,
        ))
    X = pd.DataFrame(rows)
    X.to_parquet(HERE / "candidates.parquet")
    print(X.groupby("trig").r.agg(n="size", R="mean").round(3).to_string())
    print(f"{len(X)} candidates written")


if __name__ == "__main__":
    main()
