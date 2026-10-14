"""Chart read M0 (docs/CHART_READ.md §2): the proven setups' trades (harmonic V1 year, breakout F1 12 months) split by the major-swing read at entry."""
import glob
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.evidence.zigzag import zigzag
from app.indicators.market_map import MapParams, state_frame
from app.indicators.price_action import label_structure
from app.indicators.volatility import atr

H = "data/history/FBS-Demo"
B = "data/backtests/inv/"
h = pd.read_csv(B + "setup_harmonic_prz_v11y/trades.csv").assign(setup="harmonic V1")
f = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(B + "setup_breakout_f1_20*/trades.csv"))]).assign(setup="breakout F1")
t = pd.concat([h, f], ignore_index=True)
t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
t["dir"] = np.where(t["side"] == "BUY", 1, -1)


def reads(sym: str, tf: str, mult: float) -> pd.DataFrame:
    d = pd.read_parquet(f"{H}/{sym}/{tf}.parquet").sort_values("close_time").reset_index(drop=True)
    hi, lo, cl = (d[k].astype(float) for k in ("high", "low", "close"))
    a = atr(hi, lo, cl, 14)
    ev = label_structure(zigzag(hi, lo, a, mult), 0.0)
    n = len(d)
    lab = {"HIGH": None, "LOW": None}
    trend, last_lh, last_hl = [None] * n, [np.nan] * n, [np.nan] * n
    lh = hl = np.nan
    j = 0
    for i in range(n):
        while j < len(ev) and ev[j].swing.confirm_pos <= i:
            e = ev[j]
            k = "HIGH" if "HIGH" in str(e.swing.kind).upper() else "LOW"
            if e.label is not None:
                lab[k] = str(e.label.value)
            if k == "HIGH":
                lh = e.swing.price
            else:
                hl = e.swing.price
            j += 1
        hh, ll = lab["HIGH"], lab["LOW"]
        trend[i] = "UP" if (hh, ll) == ("HH", "HL") else "DOWN" if (hh, ll) == ("LH", "LL") else "MIXED" if hh and ll else None
        last_lh[i], last_hl[i] = lh, hl
    st = state_frame(d, MapParams())["state"].to_numpy()
    out = pd.DataFrame({"trend": trend, "state": st, "last_high": last_lh, "last_low": last_hl, "close": cl, "atr": a})
    out.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    return out


cache: dict = {}
for tf in ("H1", "H4"):
    col = []
    for _, r in t.iterrows():
        key = (r.symbol, tf)
        if key not in cache:
            cache[key] = reads(r.symbol, tf, 3.0)
        x = cache[key]
        j = x.index.searchsorted(r.entry_time, side="right") - 1
        rd = x.iloc[j]
        tr = rd["trend"]
        col.append("with" if (tr == "UP" and r.dir > 0) or (tr == "DOWN" and r.dir < 0) else "against" if tr in ("UP", "DOWN") else "mixed")
    t[f"zz_{tf}"] = col

print(f"trades {len(t)}")
for s, g in t.groupby("setup"):
    print(f"\n== {s}: {len(g)} trades, {g.r_multiple.mean():+.3f} R")
    for tf in ("H1", "H4"):
        x = g.groupby(f"zz_{tf}")["r_multiple"].agg(["size", "mean", lambda v: (v > 0).mean() * 100]).round(3)
        x.columns = ["n", "R/trade", "win %"]
        print(f"  major-swing structure {tf} vs the trade:\n" + x.to_string())
    both = g[(g.zz_H1 == "with") & (g.zz_H4 == "with")]
    print(f"  with on both H1 and H4: n {len(both)}  {both.r_multiple.mean():+.3f} R")
    noag = g[(g.zz_H1 == "against") | (g.zz_H4 == "against")]
    print(f"  against on H1 or H4:     n {len(noag)}  {noag.r_multiple.mean():+.3f} R")

print("\n=== halves (split 2026-04-09) and 90 % CI by bootstrap ===")
rng = np.random.default_rng(42)
t["half"] = np.where(t.entry_time < pd.Timestamp("2026-04-09", tz="UTC"), "1st", "2nd")
def ci(v):
    v = v.to_numpy()
    if len(v) < 3:
        return float("nan"), float("nan")
    b = rng.choice(v, (4000, len(v))).mean(axis=1)
    return np.quantile(b, 0.05), np.quantile(b, 0.95)
for s, g in t.groupby("setup"):
    for tf in ("H1",):
        for k, x in g.groupby(f"zz_{tf}"):
            lo, hi = ci(x.r_multiple)
            hv = x.groupby("half").r_multiple.agg(["size", "mean"]).round(3)
            print(f"{s:12} {tf} {k:8} n {len(x):3}  {x.r_multiple.mean():+.3f} R  CI90 [{lo:+.3f}, {hi:+.3f}]  halves " +
                  "  ".join(f"{h} n{int(r['size'])} {r['mean']:+.3f}" for h, r in hv.iterrows()))
