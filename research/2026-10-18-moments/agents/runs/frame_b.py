"""Step 2, frame B (notes.md): which swing extremes launch a run. Every M1 swing low (the lowest low of the previous
10 bars, then 3 bars without a new low - the owner's "count three") is a long candidate at the next open; swing
highs mirrored. Labels: the swing is the start of a catalogued run (R = 10 / 15 U, same side); and the trade from the
next open (stop 0.3 U beyond the swing extreme, target 5 / 8 U, 120 min, the journal's real costs). Features at the
decision bar (the third bar's close), side-aligned (+ = in the trade's favour). Writes frame_b_events.parquet.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/frame_b.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import gold  # noqa: E402
from catalogue import load  # noqa: E402
from features import roll_max, roll_min, shift  # noqa: E402

W, K, PAD = 10, 3, 0.3
SIGNED = ["ret5", "ret15", "ret30", "ret60", "ret120", "ema20_dist", "m15_e20_dist", "h1_e20_dist", "consec", "wick10",
          "wick3", "m1f3_net", "m1f5_net", "m5_net", "slope60", "slope60_atr", "h1_tide", "m15_tide", "m5_tide",
          "usd_z5", "usd_z30", "gold_z5", "gold_z30", "div_z5", "div_z30", "spx_z5", "spx_z30", "sweep_p60",
          "sweep_day", "sweep_yday", "sweep_asia", "brk_p60", "brk_day", "brk_yday", "brk_asia"]
PLAIN = ["atr15_u", "atr1_ratio", "atr15_ratio", "bbw1", "bbw5", "rng30", "rng60", "rng120", "tv5_60", "tv60_1440",
         "tv15_slope", "sp_rel", "hour", "dow", "min_ldn", "min_ny", "min_since_rel", "min_to_rel"]


def trade_label(o, h, lo, c, sp, e: np.ndarray, side: np.ndarray, stop: np.ndarray, tp: np.ndarray,
                hz: int = 120) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized jlib-style trade: entry at bar e's open (a buy at the ask: the column + 0.08 + 0.07 slippage; a
    sell at the bid - 0.07), stop / target on bar extremes (a sell's on the ask), the stop first in a bar with both,
    stop slippage 0.15, a time exit at the last bar's close. Returns (+1 target / -1 stop / 0 time, P&L in price,
    the entry)."""
    n = len(o)
    entry = o[e] + np.where(side > 0, sp[e] + 0.08 + 0.07, -0.07)
    res = np.zeros(len(e))
    pnl = np.zeros(len(e))
    open_ = np.ones(len(e), bool)
    for j in range(hz):
        idx = np.minimum(e + j, n - 1)
        spj = sp[idx] + 0.08
        adv = np.where(side > 0, lo[idx], h[idx] + spj)
        fav = np.where(side > 0, h[idx], lo[idx] + spj)
        hit_s = open_ & ((adv - stop) * side <= 0)
        hit_t = open_ & ~hit_s & ((fav - entry) * side >= tp)
        res[hit_s] = -1
        res[hit_t] = 1
        pnl[hit_s] = ((stop - side * 0.15) - entry)[hit_s] * side[hit_s]
        pnl[hit_t] = tp[hit_t]
        open_ &= ~(hit_s | hit_t)
    x = np.minimum(e + hz - 1, n - 1)
    px = c[x] - np.where(side > 0, 0.07, -(sp[x] + 0.08 + 0.07))
    pnl[open_] = ((px - entry) * side)[open_]
    return res, pnl, entry


def main() -> None:
    gold.below_normal_priority()
    m = load()
    ot = m.index
    o, h, lo, c, v = (m[k].to_numpy(float) for k in ("open", "high", "low", "close", "tick_volume"))
    sp = m.spread.to_numpy(float) * 0.01
    n = len(o)
    F = pd.read_parquet(HERE / "feats.parquet")
    a15 = (F.atr15_u.to_numpy(float) * c / 4100.0)
    pmin, pmax = shift(roll_min(lo, W), 1), shift(roll_max(h, W), 1)
    nmin = np.r_[roll_min(lo, K)[K:], np.full(K, np.nan)]  # min of lo[j+1 .. j+K]
    nmax = np.r_[roll_max(h, K)[K:], np.full(K, np.nan)]
    ev = []
    for side in (1, -1):
        if side > 0:
            ok = (lo < pmin) & (nmin > lo)
        else:
            ok = (h > pmax) & (nmax < h)
        j = np.nonzero(ok)[0]
        j = j[(j > 1500) & (j + K + 130 < n)]
        ev.append(pd.DataFrame({"j": j, "side": side}))
    E = pd.concat(ev, ignore_index=True)
    j, s = E.j.to_numpy(), E.side.to_numpy()
    d, e = j + K, j + K + 1
    E["t"] = ot[e]
    E = E[(E.t.dt.hour <= 20) & (E.t.dt.dayofweek < 5) & (E.t >= pd.Timestamp("2023-11-01", tz="UTC"))]
    E = E.reset_index(drop=True)
    j, s = E.j.to_numpy(), E.side.to_numpy()
    d, e = j + K, j + K + 1
    u = c[d] / 4100.0
    ext = np.where(s > 0, lo[j], h[j])
    E["u"] = u
    E["ext"] = ext
    stop = ext - s * PAD * u
    E["stop_px"] = stop
    # labels: a catalogued run starts at the swing bar
    C = pd.read_parquet(HERE / "catalogue.parquet")
    for R in (10, 15):
        key = set(zip(C[C.R == R].i, C[C.R == R].side, strict=True))
        E[f"run{R}"] = [((jj, ss) in key) for jj, ss in zip(j, s, strict=True)]
    for tp in (5, 8):
        res, pnl, entry = trade_label(o, h, lo, c, sp, e, s, stop, tp * u)
        E[f"win{tp}"] = res
        sl_px = (entry - stop) * s
        E[f"R{tp}"] = pnl / np.maximum(sl_px + 0.15, 1e-6)
        # the mirror: the other side at the same minute, the same stop distance and target
        m_entry = o[e] + np.where(-s > 0, sp[e] + 0.08 + 0.07, -0.07)
        mres, mpnl, _ = trade_label(o, h, lo, c, sp, e, -s, m_entry + s * sl_px, tp * u)
        E[f"mwin{tp}"] = mres
        E[f"mR{tp}"] = mpnl / np.maximum(sl_px + 0.15, 1e-6)
    E["entry"] = entry
    E["stop_u"] = (entry - stop) * s / u
    # swing features (side-aligned)
    hi120, lo120 = shift(roll_max(h, 120), 1), shift(roll_min(lo, 120), 1)
    hi30, lo30 = shift(roll_max(h, 30), 1), shift(roll_min(lo, 30), 1)
    E["new30"] = np.where(s > 0, lo[j] < lo30[j], h[j] > hi30[j]).astype(float)
    E["new120"] = np.where(s > 0, lo[j] < lo120[j], h[j] > hi120[j]).astype(float)
    # the previous swing of the same kind in the last 120 bars (a 5-bar fractal before j-2): higher low / lower high
    sl = np.zeros(n, bool)
    sh = np.zeros(n, bool)
    sh[2:-2] = (h[2:-2] >= np.maximum.reduce([h[:-4], h[1:-3], h[3:-1], h[4:]]))
    sl[2:-2] = (lo[2:-2] <= np.minimum.reduce([lo[:-4], lo[1:-3], lo[3:-1], lo[4:]]))
    last_sl = pd.Series(np.where(sl, lo, np.nan)).shift(2).ffill().to_numpy()  # confirmed 2 bars later
    last_sh = pd.Series(np.where(sh, h, np.nan)).shift(2).ffill().to_numpy()
    prev = np.where(s > 0, last_sl[j], last_sh[j])
    E["vs_prev_swing"] = (ext - prev) * s / a15[d]  # > 0: a higher low (long) / lower high (short)
    run_into = np.where(s > 0, roll_max(h, 30)[j] - lo[j], h[j] - roll_min(lo, 30)[j])
    E["drop_into"] = run_into / a15[d]
    bar_rng = np.maximum(h[j] - lo[j], 1e-9)
    E["wick_j"] = np.where(s > 0, np.minimum(o[j], c[j]) - lo[j], h[j] - np.maximum(o[j], c[j])) / bar_rng
    E["tv_j"] = v[j] / roll_max(np.r_[v], 1)[j] if False else v[j] / pd.Series(v).rolling(60).mean().shift(1).to_numpy()[j]
    E["bounce"] = (c[d] - ext) * s / a15[d]
    E["close_vs_jbar"] = np.where(s > 0, c[d] > h[j], c[d] < lo[j]).astype(float)  # the count-three close beyond
    # tests of the level: earlier 5-bar fractal swings of the same kind within 0.15 M15 ATR of the extreme (120 min)
    tests = np.zeros(len(E))
    for k in range(3, 121):
        jk = np.maximum(j - k, 0)
        same = np.where(s > 0, sl[jk], sh[jk])
        px = np.where(s > 0, lo[jk], h[jk])
        tests += same & (np.abs(px - ext) <= 0.15 * a15[d])
    E["tests"] = tests
    # level sweeps by the swing extreme, reclaimed at the decision close
    day = ot.normalize()
    dlo = pd.Series(lo).groupby(day.to_numpy()).cummin().to_numpy()
    dhi = pd.Series(h).groupby(day.to_numpy()).cummax().to_numpy()
    same_day = day[j - 1] == day[j]
    pdl = np.where(same_day, np.where(s > 0, dlo[j - 1], dhi[j - 1]), np.nan)
    E["sweep_daylvl"] = np.where(s > 0, (lo[j] < pdl) & (c[d] > pdl), (h[j] > pdl) & (c[d] < pdl)).astype(float)
    E["new_day_ext"] = np.where(s > 0, lo[j] < pdl, h[j] > pdl).astype(float)
    E["sweep_120"] = np.where(s > 0, (lo[j] < lo120[j]) & (c[d] > lo120[j]), (h[j] > hi120[j]) & (c[d] < hi120[j])).astype(float)
    for step in (10.0, 50.0):
        r = np.round(ext / step) * step
        E[f"round{int(step)}_u"] = np.abs(ext - r) / u
    # the snapshot features at the decision bar, side-aligned
    Fd = F.iloc[d].reset_index(drop=True)
    for f in SIGNED:
        E[f] = Fd[f].to_numpy() * s
    for f in PLAIN:
        E[f] = Fd[f].to_numpy()
    E["h1_struct"] = np.where(np.abs(Fd.h1_struct) == 1, Fd.h1_struct * s, Fd.h1_struct)  # +1 with, -1 against
    E["m15_struct"] = np.where(np.abs(Fd.m15_struct) == 1, Fd.m15_struct * s, Fd.m15_struct)
    E["pos60"] = np.where(s > 0, Fd.pos60, 1 - Fd.pos60)
    E["d_daymid"] = np.where(s > 0, -Fd.d_dlo, Fd.d_dhi)  # distance from the day's extreme on the trade's side (<= 0)
    E["part"] = np.where(E.t < pd.Timestamp("2026-03-01", tz="UTC"), "design", "window")
    E["half"] = pd.cut(E.t, pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01",
                                            "2026-03-01", "2026-10-17"], utc=True), labels=["H1", "H2", "H3", "H4", "H5", "W"],
                       right=False)
    E.to_parquet(HERE / "frame_b_events.parquet")
    D = E[(E.part == "design") & (E.stop_u >= 1)]
    print(f"events design {len(D)} ({len(D) / D.t.dt.normalize().nunique():.1f} a day), window {len(E) - len(D)}")
    print(f"launch R10 {100 * D.run10.mean():.1f} %, R15 {100 * D.run15.mean():.1f} %;"
          f" trade win5 {100 * (D.win5 > 0).mean():.1f} % stop {100 * (D.win5 < 0).mean():.1f} %;"
          f" win8 {100 * (D.win8 > 0).mean():.1f} %; median stop {D.stop_u.median():.2f} U")
    print(f"R5 {D.R5.mean():+.3f} (mirror {D.mR5.mean():+.3f}); R8 {D.R8.mean():+.3f} (mirror {D.mR8.mean():+.3f});"
          f" mirror win5 {100 * (D.mwin5 > 0).mean():.1f} %")


if __name__ == "__main__":
    main()
