"""Loser diagnosis: concrete situations at each trade's decision bar (closed bars only), the share of stopped losers
and winners in each, and R with / without it by half-year (development only unless --test).

    python diag.py RULE      (RULE in RULES below)
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

from common import DEV, SLIP, TEST, Bars, ema, gold
from exp import Lab
from sim import one_at_a_time

warnings.filterwarnings("ignore")


def h1_frame(B: Bars) -> tuple[pd.DataFrame, np.ndarray]:
    """Closed H1 bars and, for each M1 bar, the position of the last H1 bar closed by its close."""
    m = pd.DataFrame({"o": B.o, "h": B.h, "l": B.lo, "c": B.c}, index=B.ot)
    h1 = m.resample("1h", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    tr = np.maximum(h1.h - h1.l, np.maximum((h1.h - h1.c.shift()).abs(), (h1.l - h1.c.shift()).abs()))
    h1["atr"] = tr.rolling(14).mean()
    h1["e20"] = ema(h1.c.to_numpy(), 20)
    h1["e50"] = ema(h1.c.to_numpy(), 50)
    avail = (h1.index + pd.Timedelta(hours=1)).as_unit("ns").asi8
    pos = np.searchsorted(avail, B.t64 + 60_000_000_000, side="right") - 1
    return h1, pos


def situations(L: Lab) -> pd.DataFrame:
    B, F = L.B, L.F
    h1, pos = h1_frame(B)
    p = np.clip(pos, 0, None)
    c = B.c
    atr = F.atr.to_numpy(float)
    S = pd.DataFrame(index=np.arange(B.n))
    h1c, h1e50, h1atr = h1.c.to_numpy(), h1.e50.to_numpy(), h1.atr.to_numpy()
    S["h1_gap_e50"] = (c - h1e50[p]) / h1atr[p]  # signed later by side
    leg = np.r_[np.full(3, np.nan), h1c[3:] - h1c[:-3]]
    S["h1_leg3"] = leg[p] / h1atr[p]
    leg1 = np.r_[np.nan, np.diff(h1c)]
    S["h1_last"] = leg1[p] / h1atr[p]
    hi240 = pd.Series(B.h).rolling(240).max().to_numpy()
    lo240 = pd.Series(B.lo).rolling(240).min().to_numpy()
    S["pos240"] = (c - lo240) / (hi240 - lo240)
    S["run60"] = np.r_[np.full(60, np.nan), c[60:] - c[:-60]] / atr
    S["bar1"] = np.r_[np.nan, np.diff(c)] / atr
    med = pd.Series(atr).rolling(1440, min_periods=300).median().to_numpy()
    S["atr_ratio"] = atr / med
    m15 = pd.Series(c, index=B.ot).resample("15min", label="left", closed="left").last().dropna()
    e = pd.Series(ema(m15.to_numpy(), 20), index=m15.index)
    sl15 = e.diff().to_numpy()
    av15 = (m15.index + pd.Timedelta(minutes=15)).as_unit("ns").asi8
    p15 = np.clip(np.searchsorted(av15, B.t64 + 60_000_000_000, side="right") - 1, 0, None)
    S["m15_slope"] = sl15[p15]
    S["dv60"] = F.dv60.to_numpy(float)
    rel = gold.releases()
    rt = rel.t.dt.as_unit("ns").astype("int64").to_numpy() if hasattr(rel.t.dt, "as_unit") else rel.t.astype("int64").to_numpy()
    rt = np.sort(rt)
    k = np.searchsorted(rt, B.t64)
    nxt = np.where(k < len(rt), rt[np.clip(k, 0, len(rt) - 1)], np.iinfo(np.int64).max)
    prv = np.where(k > 0, rt[np.clip(k - 1, 0, len(rt) - 1)], np.iinfo(np.int64).min)
    S["news_min"] = np.minimum((nxt - B.t64) / 6e10, (B.t64 - prv) / 6e10)
    S["ny_min"] = B.ny_min
    S["ldn_min"] = B.ldn_min
    S["ses"] = F.ses.to_numpy()
    mean60 = (pd.Series((B.h + B.lo + c) / 3).rolling(60).mean()).to_numpy()
    c3 = np.r_[np.full(3, np.nan), c[:-3]]
    c15 = np.r_[np.full(15, np.nan), c[:-15]]
    S["spike_share"] = (c - c3) / (c - mean60)  # share of the stretch made in the last 3 bars
    S["move15"] = (c - c15) / atr
    hi60 = pd.Series(B.h).rolling(60).max().to_numpy()
    lo60 = pd.Series(B.lo).rolling(60).min().to_numpy()
    S["top60_is_4h"] = hi60 >= hi240  # the last hour made the 4-hour high
    S["bot60_is_4h"] = lo60 <= lo240
    lo3 = pd.Series(B.lo).rolling(3).min().to_numpy()
    hi3 = pd.Series(B.h).rolling(3).max().to_numpy()
    lo240p = np.r_[np.full(3, np.nan), lo240[:-3]]
    hi240p = np.r_[np.full(3, np.nan), hi240[:-3]]
    S["new4h_low"] = lo3 < lo240p  # the last 3 bars broke the 4-hour low that stood before them
    S["new4h_high"] = hi3 > hi240p
    S["round10_d"] = (c - np.floor(c / 10) * 10) / atr  # distance above the round 10 below
    S["round10_u"] = (np.ceil(c / 10) * 10 - c) / atr
    return S


def flags(S: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    s = t.side.to_numpy()
    x = S.iloc[t.i.to_numpy()].reset_index(drop=True)
    f = pd.DataFrame(index=t.index)
    f["H1 leg (3h) against"] = (x.h1_leg3.to_numpy() * s < 0)
    f["H1 last bar against"] = (x.h1_last.to_numpy() * s < 0)
    f["flat H1 (|c-EMA50| < 0.85 H1 ATR)"] = (np.abs(x.h1_gap_e50.to_numpy()) < 0.85)
    pw = np.where(s > 0, x.pos240, 1 - x.pos240)
    f["low half of 4h range (trade's way)"] = pw < 0.5
    f["low quarter of 4h range"] = pw < 0.25
    f["1h run against >= 4 ATR (knife)"] = (x.run60.to_numpy() * s <= -4)
    f["last bar against >= 1 ATR"] = (x.bar1.to_numpy() * s <= -1)
    f["volatility spike (ATR > 1.5x day median)"] = x.atr_ratio.to_numpy() > 1.5
    f["quiet (ATR < 0.8x day median)"] = x.atr_ratio.to_numpy() < 0.8
    f["M15 EMA20 slope against"] = (x.m15_slope.to_numpy() * s < 0)
    f["big stretch (|dv60| >= 5)"] = np.abs(x.dv60.to_numpy()) >= 5
    f["news within 15 min"] = x.news_min.to_numpy() <= 15
    f["London session"] = x.ses.to_numpy() == 1
    f["New York 08-12 ET"] = x.ses.to_numpy() == 2
    f["afternoon 12-15:30 ET"] = x.ses.to_numpy() == 3
    f["spike: >= 60 % of the stretch in the last 3 bars"] = x.spike_share.to_numpy() >= 0.6
    f["slow leg: < 30 % in the last 3 bars"] = x.spike_share.to_numpy() < 0.3
    f["15-bar move against >= 4 ATR"] = x.move15.to_numpy() * s <= -4
    f["came off a 4h extreme the other way (top for a buy)"] = np.where(s > 0, x.top60_is_4h, x.bot60_is_4h).astype(bool)
    f["broke the 4h extreme against (new 4h low for a buy)"] = np.where(s > 0, x.new4h_low, x.new4h_high).astype(bool)
    rd = np.where(s > 0, x.round10_d, x.round10_u)
    f["round 10 level within 2 ATR behind entry"] = rd <= 2
    return f


RULES = {
    "tdl10": dict(feat="dv60", thr=3.0, ses=[1, 2, 3], trend="with", sl=10, tp=10, hold=240, off=1.0, valid=15),
    "tdl4": dict(feat="dv60", thr=3.0, ses=[1, 2, 3], trend="with", sl=4, tp=4, hold=120, off=1.0, valid=15,
                 sl_cap=10.0),
}


def trades(L: Lab, cfg: dict, windows) -> pd.DataFrame:
    cfg = cfg | dict(extra=lambda F, side: (L.B.ny_min < 930) & (L.B.ldn_min >= 420))
    i, side = L.candidates(cfg)
    if cfg.get("sl_cap"):
        keep = cfg["sl"] * L.F.atr.to_numpy(float)[i] <= cfg["sl_cap"]
        i, side = i[keep], side[keep]
    d = L.sim(cfg, i, side)
    out = []
    for name, a, b in windows:
        ia, ib = L.B.idx(a), L.B.idx(b)
        t = one_at_a_time(d[(d.i >= ia) & (d.i < ib)])
        t = t[t.filled].copy()
        t["half"] = name[:2] if not name.startswith("TEST") else "T"
        out.append(t)
    t = pd.concat(out)
    t["R"] = t.usd / (t.sl + SLIP)
    t["t"] = L.B.ot[t.i.to_numpy()]
    return t


def report(t: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    los = t.exit == "stop"
    win = t.exit == "win"
    rows = []
    for col in f.columns:
        m = f[col].to_numpy()
        by = t.groupby("half")
        w_ = [t.R[m & (t.half == h).to_numpy()].mean() for h in by.groups]
        wo = [t.R[~m & (t.half == h).to_numpy()].mean() for h in by.groups]
        worse = sum(1 for a, b in zip(w_, wo) if a < b)
        rows.append({"situation": col, "share": m.mean(), "losers in": m[los.to_numpy()].mean(),
                     "winners in": m[win.to_numpy()].mean(), "R with": t.R[m].mean(), "R without": t.R[~m].mean(),
                     "worse in": f"{worse}/{len(w_)}"})
    return pd.DataFrame(rows).set_index("situation")


if __name__ == "__main__":
    gold.below_normal_priority()
    name = sys.argv[1]
    L = Lab()
    S = situations(L)
    t = trades(L, RULES[name], TEST if "--test" in sys.argv else DEV)
    t = t.reset_index(drop=True)
    f = flags(S, t)
    pd.set_option("display.width", 250)
    print(f"{name}: {len(t)} trades, R {t.R.mean():+.3f}, stopped {int((t.exit == 'stop').sum())}, won "
          f"{int((t.exit == 'win').sum())}, time {int((t.exit == 'time').sum())}")
    print(t.groupby("half").R.agg(["size", "mean"]).round(3).T.to_string())
    print(report(t, f).round(3).to_string())
    t.join(f).to_parquet(f"research/2026-10-18-moments/agents/reversion/diag_{name}.parquet")
