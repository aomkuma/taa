"""The adaptive entry timeframe (owner, 2026-10-18): at each M1 bar, the smallest of M1 / M5 / M15 / M30 whose
ATR(14) (completed bars) is at least 5 USD; M30 when none is (H1 stays the largest timeframe). The chart forms
measured on that timeframe (20-bar box, Bollinger width, swing structure, momentum, wicks, tick volume), each from
completed bars of that timeframe, mapped to every M1 bar's close. Writes adaptive.parquet and prints the timeframe
in use by month.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/adaptive.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import gold  # noqa: E402
from catalogue import load  # noqa: E402
from features import at_close, frac_runs, htf  # noqa: E402

TFS = (1, 5, 15, 30)
NEED = 5.0  # USD
W = 20  # bars in the box


def forms(b: pd.DataFrame) -> pd.DataFrame:
    """Form features of one timeframe's bars (each row known at that bar's close)."""
    c, h, lo, o, v = b.close, b.high, b.low, b.open, b.tick_volume
    a = b.atr
    out = pd.DataFrame(index=b.index)
    out["atr"] = a
    out["bbw"] = 4 * c.rolling(20).std() / a
    hi, lw = h.rolling(W).max(), lo.rolling(W).min()
    hgt = (hi - lw).where(hi > lw)
    out["box_h"] = hgt / a
    out["box_pos"] = (c - lw) / hgt
    kk = np.arange(W) - (W - 1) / 2
    beta = c.rolling(W).apply(lambda y: float(np.dot(kk, y) / np.dot(kk, kk)), raw=True)
    out["box_slope"] = beta * W / hgt
    # touches of the top / bottom: 3-bar fractal swings (confirmed a bar later) within 15 % of the height
    hv, lv = h.to_numpy(), lo.to_numpy()
    n = len(b)
    sh = np.zeros(n, bool)
    sl = np.zeros(n, bool)
    sh[1:-1] = (hv[1:-1] >= hv[:-2]) & (hv[1:-1] >= hv[2:])
    sl[1:-1] = (lv[1:-1] <= lv[:-2]) & (lv[1:-1] <= lv[2:])
    top = np.zeros(n)
    bot = np.zeros(n)
    hiv, lwv, hg = hi.to_numpy(), lw.to_numpy(), hgt.to_numpy()
    for k in range(1, W):
        shk = np.r_[np.zeros(k, bool), sh[:-k]]
        slk = np.r_[np.zeros(k, bool), sl[:-k]]
        hk = np.r_[np.full(k, np.nan), hv[:-k]]
        lk = np.r_[np.full(k, np.nan), lv[:-k]]
        top += shk & (hk >= hiv - 0.15 * hg)
        bot += slk & (lk <= lwv + 0.15 * hg)
    out["touch_top"], out["touch_bot"] = top, bot
    hl, _ = frac_runs(lv, True, 1)
    lh, _ = frac_runs(hv, False, 1)
    out["hl"], out["lh"] = hl, lh
    out["struct_net"] = hl - lh
    out["ret6"] = (c - c.shift(6)) / a
    out["ema_dist"] = (c - c.ewm(span=20, adjust=False).mean()) / a
    sgn = np.sign(c - o).to_numpy()
    cons = np.zeros(n)
    for i in range(1, n):
        cons[i] = (cons[i - 1] + sgn[i] if np.sign(cons[i - 1]) == sgn[i] else sgn[i]) if sgn[i] != 0 else 0
    out["consec"] = cons
    out["wick3"] = ((np.minimum(o, c) - lo) - (h - np.maximum(o, c))).rolling(3).mean() / a
    out["tv3_20"] = v.rolling(3).mean() / v.rolling(20).mean()
    out["atr_ratio"] = a / a.rolling(100).mean()
    return out


def main() -> None:
    gold.below_normal_priority()
    m = load()
    ot = m.index
    per_tf = {}
    for tf in TFS:
        b = htf(m, tf)
        f = forms(b)
        per_tf[tf] = pd.DataFrame({k: at_close(f[k], b.end, ot) for k in f.columns}, index=ot)
        print(f"M{tf}: {len(b)} bars")
    atr = np.vstack([per_tf[tf]["atr"].to_numpy() for tf in TFS])
    ok = atr >= NEED
    pick = np.where(ok.any(0), np.argmax(ok, axis=0), len(TFS) - 1)
    tf_used = np.array(TFS)[pick]
    out = pd.DataFrame(index=ot)
    out["ad_tf"] = tf_used.astype(np.float32)
    cols = [c for c in per_tf[1].columns]
    for col in cols:
        stack = np.vstack([per_tf[tf][col].to_numpy() for tf in TFS])
        out[f"ad_{col}"] = stack[pick, np.arange(len(ot))].astype(np.float32)
    out["ad_atr_usd"] = out.pop("ad_atr")
    out.to_parquet(HERE / "adaptive.parquet")
    x = out[(ot >= pd.Timestamp("2023-11-01", tz="UTC")) & (ot.hour < 21) & (ot.dayofweek < 5)]
    tab = pd.crosstab(x.index.strftime("%Y-%m"), x.ad_tf, normalize="index").mul(100).round(0)
    tab.columns = [f"M{int(c)} %" for c in tab.columns]
    med = pd.DataFrame({f"M{tf} ATR": per_tf[tf]["atr"][x.index].groupby(x.index.strftime("%Y-%m")).median() for tf in TFS})
    print("\nThe adaptive timeframe in use (share of minutes 00-21 UTC) and the median ATR(14) in USD, by month:")
    print(pd.concat([tab, med.round(1)], axis=1).to_string())


if __name__ == "__main__":
    main()
