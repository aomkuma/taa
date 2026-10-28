"""Features at each M1 bar's close (bars <= i only), cached to the scratch parquet in this folder."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from common import Bars, ema, h1_trend, rstd

CACHE = Path("research/2026-10-18-moments/agents/reversion/feats.parquet")


def build(B: Bars) -> pd.DataFrame:
    if CACHE.exists():
        f = pd.read_parquet(CACHE)
        if len(f) == B.n:
            return f
    c, h, lo = B.c, B.h, B.lo
    d1 = np.r_[0.0, np.diff(c)]
    f = pd.DataFrame(index=np.arange(B.n))
    f["atr"] = pd.Series(h - lo).rolling(60, min_periods=60).mean().to_numpy()
    f["sig"] = rstd(d1, 60)
    for k in (1, 2, 3, 5, 10, 15, 30):
        mv = np.full(B.n, np.nan)
        mv[k:] = c[k:] - c[:-k]
        ok = B.contiguous(k)
        f[f"z{k}"] = np.where(ok, mv / (f.sig.to_numpy() * np.sqrt(k)), np.nan)
    # VWAP-like means: tick-volume weighted typical price over n bars, distance in ATR units
    m = pd.Series(np.ones(B.n))  # tick volume is optional; equal weights keep it simple
    tp = pd.Series((h + lo + c) / 3)
    for n in (15, 30, 60):
        f[f"dv{n}"] = (c - tp.rolling(n).mean().to_numpy()) / f.atr.to_numpy()
    for n in (20, 50):
        f[f"de{n}"] = (c - ema(c, n)) / f.atr.to_numpy()
    # Bollinger (20, sd) on M1 closes: position in sd units
    s20 = pd.Series(c).rolling(20)
    f["bb20"] = (c - s20.mean().to_numpy()) / s20.std().to_numpy()
    # the run-up: highest high / lowest low of the last 15 bars against the close, in ATR
    f["hi15"] = (pd.Series(h).rolling(15).max().to_numpy() - c) / f.atr.to_numpy()
    f["lo15"] = (c - pd.Series(lo).rolling(15).min().to_numpy()) / f.atr.to_numpy()
    f["tr"] = h1_trend(B)
    f["ses"] = B.session()
    f["ok60"] = B.contiguous(60)
    del m
    f.astype({c_: "float32" for c_ in f.columns if f[c_].dtype == float}).to_parquet(CACHE)
    return f
