"""The weekly journal of Asia B2 moved to the NY window (20:30-23:00 Thai): the bot's trades (trades.csv) with their
decision records (journal.jsonl), plus where each entry sat in the owner's zone grid v1 (research/2026-10-22-zones).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/week.py 2025-10-20 2025-10-25
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "2026-10-22-zones"))
import zone_grid_v1 as Z  # noqa: E402


def load() -> pd.DataFrame:
    T = pd.read_csv(HERE / "trades.csv")
    J = pd.DataFrame([json.loads(x) for x in open(HERE / "journal.jsonl", encoding="utf-8")])
    J = pd.concat([J.drop(columns=["conditions"]), pd.json_normalize(J.conditions)], axis=1)
    X = T.merge(J[["signal_id", "level", "pattern", "rule", "agreement", "h1_atr", "stop_distance"]], on="signal_id", how="left")
    X["t"] = pd.to_datetime(X.entry_time, utc=True)
    g = Z.daily_grid(Z.bars("D1"))
    k = g.index.searchsorted(X.t, side="right") - 1
    anc, stp = g.anchor.values[k], g.step.values[k]
    pos = (X.entry_price - anc) / stp
    X["zone_pos"] = pos - np.floor(pos)  # 0 = on a grid line, 0.5 = mid-zone
    X["zone_line_dist"] = np.minimum(X.zone_pos, 1 - X.zone_pos) * stp  # USD to the nearest grid line
    return X


sys.path.insert(0, str(HERE.parents[1] / "precursors"))
import check_plan1 as C  # noqa: E402

MIN = 60 * 10**9
ACCOUNTS = ((100.0, 7.5), (300.0, 3.0))
H1 = None
TFS: dict = {}
TF_HOURS = {"D1": 24, "H4": 4, "H1": 1, "M15": 0.25}


def structure(b: pd.DataFrame, t: pd.Timestamp, tf: str) -> int:
    """+1 HH/HL, -1 LH/LL, 0 mixed: the last two confirmed 3-bar fractal highs and lows of the closed bars before t."""
    c = b[b.index + pd.Timedelta(hours=TF_HOURS[tf]) <= t].iloc[-200:]
    hi, lo = c.high.values, c.low.values
    fh = [hi[i] for i in range(1, len(c) - 1) if hi[i] > hi[i - 1] and hi[i] > hi[i + 1]][-2:]
    fl = [lo[i] for i in range(1, len(c) - 1) if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]][-2:]
    if len(fh) < 2 or len(fl) < 2:
        return 0
    return 1 if fh[1] > fh[0] and fl[1] > fl[0] else -1 if fh[1] < fh[0] and fl[1] < fl[0] else 0
BAND_FROM = pd.Timestamp("2025-12-08", tz="UTC")
# from week 11 (owner 2026-10-22 "why trade against the big trend?"; weeks 2-10: with the zone grid's last shift +5.48 R
# on 22, against -0.90 on 20): the realistic variant trades only in the direction of the last zone shift
TREND_FROM = pd.Timestamp("2025-12-29", tz="UTC")
# deleted after week 12: the skipped against-trend trades made +2.10 R that week; weeks 2-12 against-trend +1.20 net
TREND_UNTIL = pd.Timestamp("2026-01-12", tz="UTC")  # the realistic variant aims 0.1 step before the line from week 8


def context(X: pd.DataFrame) -> pd.DataFrame:
    """Owner 2026-10-22: reaching a level is not a reason to trade - per entry, from closed H1 bars of the last 5 days:
    how many times price touched the B2 level's band (+-0.1 D1 ATR; a touch = a run of bars inside it, 3 bars apart),
    the bounce of each touch (the best move away from the level in the trade's direction within 6 bars, USD), and the
    H1 structure (the last two 3-bar fractal highs and lows: HH/HL, LH/LL or mixed)."""
    global H1
    if H1 is None:
        H1 = Z.bars("H1")
        for tf in ("D1", "H4", "H1", "M15"):
            TFS[tf] = Z.bars(tf)
    g = Z.daily_grid(Z.bars("D1"))
    out = []
    for r in X.itertuples():
        side = 1 if r.side == "BUY" else -1
        lv = float(re.match(r"\s*([0-9.]+)", str(r.level)).group(1))
        k = g.index.searchsorted(r.t, side="right") - 1
        band = 0.1 * g.step.values[k]
        h = H1[(H1.index + pd.Timedelta(hours=1) <= r.t) & (H1.index >= r.t - pd.Timedelta(days=5))]
        inside = ((h.low <= lv + band) & (h.high >= lv - band)).values
        touches, bounces, last, ext = 0, [], -10, []
        for i in np.flatnonzero(inside):
            if i - last > 3:
                touches += 1
                after = h.iloc[i : i + 7]
                b = (after.high.max() - lv) if side > 0 else (lv - after.low.min())
                bounces.append(round(float(b), 1))
                ext.append(float(h.low.values[i]) if side > 0 else float(h.high.values[i]))
            else:
                ext[-1] = min(ext[-1], float(h.low.values[i])) if side > 0 else max(ext[-1], float(h.high.values[i]))
            last = i
        # owner: each touch making a lower low into a support (a higher high into a resistance) wears the level down
        worn = sum(1 for a, b in zip(ext, ext[1:]) if (b < a if side > 0 else b > a))
        hi, lo = h.high.values, h.low.values
        fh = [hi[i] for i in range(1, len(h) - 1) if hi[i] > hi[i - 1] and hi[i] > hi[i + 1]][-2:]
        fl = [lo[i] for i in range(1, len(h) - 1) if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]][-2:]
        st = "?"
        if len(fh) == 2 and len(fl) == 2:
            st = "HH/HL" if fh[1] > fh[0] and fl[1] > fl[0] else "LH/LL" if fh[1] < fh[0] and fl[1] < fl[0] else "mixed"
        sc, parts = 0.0, []
        for tf, w in (("D1", 3), ("H4", 2), ("H1", 2), ("M15", 1)):
            v = structure(TFS[tf], r.t, tf) * side
            sc += w * v
            parts.append(f"{tf}{'+' if v > 0 else '-' if v < 0 else '0'}")
        fresh = 1 if touches <= 2 else -1 if touches >= 5 else 0
        mom = 0 if len(bounces) < 2 else (1 if bounces[-1] > bounces[-2] else -1)
        sc += fresh + mom
        out.append(dict(touches=touches, bounces=bounces[-4:], h1_structure=st, score=sc,
                        score_parts=" ".join(parts) + f" fresh{fresh:+d} mom{mom:+d}", worn=worn))
    return pd.DataFrame(out, index=X.index)


def realistic(X: pd.DataFrame, be: bool = True, band: float = 0.0) -> pd.Series:
    """The 'closer to real trading' variant (owner 2026-10-22, from week 2): the same entry and stop; half off at +1 R
    with the stop of the rest moved to the entry; the rest aims at the owner's next zone-grid line beyond the entry
    (at least a quarter step away), out 120 minutes after the entry at the latest. Ticks, spread only."""
    g = Z.daily_grid(Z.bars("D1"))
    out = []
    for r in X.itertuples():
        side = 1 if r.side == "BUY" else -1
        risk = abs(r.entry_price - r.sl_initial)
        t, bid, ask = C.day_ticks(r.t.normalize())
        tn = r.t.value
        f = int(np.searchsorted(t, tn))
        k = g.index.searchsorted(r.t, side="right") - 1
        anc, stp = g.anchor.values[k], g.step.values[k]
        j = np.floor((r.entry_price - anc) / stp)
        lines = anc + (j + np.arange(-3, 5)) * stp
        ahead = lines[(lines - r.entry_price) * side >= 0.25 * stp]
        b = band if band else (0.1 if r.t >= BAND_FROM else 0.0)  # adopted from week 8: weeks 2-7 +10.27 vs +9.66
        tgt = float(ahead.min() if side > 0 else ahead.max()) - side * b * stp  # a line is a band: aim before it
        t_end = tn + 120 * MIN
        px1, tx1, k1 = C.manage(t, bid, ask, f, r.entry_price, side, r.sl_initial, r.entry_price + side * risk, t_end)
        if k1 != "target":
            out.append((px1 - r.entry_price) * side / risk)
            continue
        f2 = int(np.searchsorted(t, tx1))
        if (tgt - r.entry_price) * side <= risk:  # the zone line is not beyond 1 R: the whole position was out at 1 R
            out.append(1.0)
            continue
        px2, _, _ = C.manage(t, bid, ask, f2, r.entry_price, side, r.entry_price if be else r.sl_initial, tgt, t_end)
        out.append(0.5 + 0.5 * (px2 - r.entry_price) * side / risk)
    return pd.Series(out, index=X.index)  # owner 2026-10-22: every learning journal carries 100 and 300 USD


def accounts(X: pd.DataFrame, col: str = "r_multiple", tag: str = "") -> pd.DataFrame:
    """Both accounts trade by trade from the journal's first trade (equity sizing, at least 0.01 lot)."""
    X = X.sort_values("t").copy()
    for eq0, pct in ACCOUNTS:
        eq, usd, bal = eq0, [], []
        for r in X.itertuples():
            risk = abs(r.entry_price - r.sl_initial)
            lots = max(0.01, np.floor(eq * pct / 100 / (risk * 100) * 100) / 100)
            rr = getattr(r, col)
            if not np.isfinite(rr):  # skipped by a rule: no trade, the balance carries
                usd.append(0.0)
                bal.append(eq)
                continue
            u = rr * risk * lots * 100
            eq += u
            usd.append(u)
            bal.append(eq)
        X[f"usd{tag}_{eq0:.0f}"], X[f"bal{tag}_{eq0:.0f}"] = usd, bal
    return X


if __name__ == "__main__":
    X = load()
    X = X[X.t < pd.Timestamp(sys.argv[2], tz="UTC")]  # nothing after the week is read
    X["r_real"] = realistic(X)
    gg = Z.daily_grid(Z.bars("D1"))
    kk = gg.index.searchsorted(X.t, side="right") - 1
    sh = gg["shift"].values
    last = [next((sh[j] for j in range(i, -1, -1) if sh[j]), "") for i in kk]
    X["grid_trend"] = ["up" if v == "up" else "down" for v in last]
    X["with_trend"] = [(v == "up") == (sd == "BUY") for v, sd in zip(X.grid_trend, X.side)]
    X["r_real_all"] = X.r_real
    X.loc[(X.t >= TREND_FROM) & (X.t < TREND_UNTIL) & ~X.with_trend, "r_real"] = np.nan
    X["r_real_nobe"] = realistic(X, be=False)  # candidate from week 4: the rest keeps the original stop
    X["r_real_band"] = realistic(X, band=0.1)  # candidate from week 5 (owner: a line is a band): aim 0.1 step before it
    X = accounts(accounts(X), "r_real", "r")
    W = X[(X.t >= pd.Timestamp(sys.argv[1], tz="UTC")) & (X.t < pd.Timestamp(sys.argv[2], tz="UTC"))]
    W = W.join(context(W))
    for r in W.itertuples():
        tf = "M5" if r.strategy.endswith("m5") else "M1"
        how = re.sub(r",.*", "", str(r.level))
        pat = re.sub(r" \(.*", "", str(r.rule).split(": ", 1)[-1])
        risk = abs(r.entry_price - r.sl_initial)
        print(f"{r.t.tz_convert('Asia/Bangkok'):%a %d %H:%M} {tf} {r.side:4s} R {r.r_multiple:+.2f} {r.exit_reason:6s} "
              f"best {r.mfe / risk:+.2f}R worst {-r.mae / risk:+.2f}R | {pat} | level {how} | {r.agreement} | stop {str(r.stop_distance).split(' to')[0]} "
              f"| grid line {r.zone_line_dist:.1f} USD away\n"
              f"      zone-grid trend {r.grid_trend} -> {'WITH' if r.with_trend else 'AGAINST'} | "
              f"context: level touched {r.touches}x in 5 days, bounces {r.bounces} USD, H1 {r.h1_structure} | deeper touches {r.worn} | SCORE {r.score:+.0f} ({r.score_parts}) | band-target {r.r_real_band:+.2f} R\n"
              f"      base {r.r_multiple:+.2f} R: 100 {r.usd_100:+.2f} -> {r.bal_100:.2f}, 300 {r.usd_300:+.2f} -> {r.bal_300:.2f}"
              f" | real {'skipped (against the trend)' if not np.isfinite(r.r_real) else f'{r.r_real:+.2f} R'} (unfiltered {r.r_real_all:+.2f}) | 100 {r.usdr_100:+.2f} -> {r.balr_100:.2f}, 300 {r.usdr_300:+.2f} -> {r.balr_300:.2f}")
    if len(W):
        print(f"candidate (target 0.1 step before the line): week {W.r_real_band.sum():+.2f} R | weeks so far {X.r_real_band.sum():+.2f}")
        print(f"candidate (no break-even on the rest): week {W.r_real_nobe.sum():+.2f} R | weeks so far: base {X.r_multiple.sum():+.2f}, real {X.r_real.sum():+.2f}, no-BE {X.r_real_nobe.sum():+.2f}")
        print(f"real unfiltered: week {W.r_real_all.sum():+.2f} R")
        print(f"real: {np.nansum(W.r_real):+.2f} R | 100: {W.usdr_100.sum():+.2f} -> {W.balr_100.iloc[-1]:.2f} | 300: {W.usdr_300.sum():+.2f} -> {W.balr_300.iloc[-1]:.2f}")
    print(f"week: {len(W)} trades {W.r_multiple.sum():+.2f} R | 100 USD at 7.5 %: {W.usd_100.sum():+.2f} USD -> {W.bal_100.iloc[-1] if len(W) else float('nan'):.2f} | 300 USD at 3 %: {W.usd_300.sum():+.2f} USD -> {W.bal_300.iloc[-1] if len(W) else float('nan'):.2f}")
