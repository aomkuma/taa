"""Replay trades on gold ticks (2025-10+) to check the M1 approximation of limit fills, stops and targets.

Tick rules: a BUY limit at ask level L fills on the first tick with ask <= L - 0.01 (``touch=True``: ask <= L) at
min(L, ask); a SELL limit at bid level L when bid >= L + 0.01 at max(L, bid). Market: the first tick after the
decision bar's close, ask + 0.07 / bid - 0.07. Then the stop on the bid (buy) / ask (sell), exit stop - 0.07; the
target at the target price; the time exit at the bid / ask with 0.07 slippage.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from common import SLIP

TICKS = Path("data/ticks/XAUUSD")
NS_MIN = 60_000_000_000


@lru_cache(maxsize=8)
def day(d: str) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    p = TICKS / f"{d}.parquet"
    if not p.exists():
        return None
    x = pd.read_parquet(p)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    return t, x.bid.to_numpy(float), x.ask.to_numpy(float)


def window(t0: int, t1: int):
    parts = []
    for d in pd.date_range(pd.Timestamp(t0, tz="UTC").normalize(), pd.Timestamp(t1, tz="UTC").normalize()):
        z = day(d.strftime("%Y-%m-%d"))
        if z is not None:
            parts.append(z)
    if not parts:
        return None
    t = np.concatenate([p[0] for p in parts])
    b = np.concatenate([p[1] for p in parts])
    a = np.concatenate([p[2] for p in parts])
    m = (t >= t0) & (t < t1)
    return t[m], b[m], a[m]


def replay(t_dec_open: int, side: int, L: float | None, sl: float, tp: float, valid: int, hold: int,
           touch: bool = False, stop_slip: float = SLIP) -> dict | None:
    t0 = t_dec_open + NS_MIN  # the decision bar's close
    w = window(t0, t0 + (valid + hold + 2) * NS_MIN)
    if w is None or not len(w[0]):
        return None
    t, b, a = w
    if L is None:
        k = 0
        fill = a[0] + SLIP if side > 0 else b[0] - SLIP
    else:
        eps = 0.0 if touch else 0.01
        tv = t < t0 + valid * NS_MIN
        hit = (a <= L - eps) if side > 0 else (b >= L + eps)
        hit &= tv
        if not hit.any():
            return dict(filled=False)
        k = int(hit.argmax())
        fill = min(L, a[k]) if side > 0 else max(L, b[k])
    tf = t[k]
    stop, tgt = fill - side * sl, fill + side * tp
    m = (np.arange(len(t)) > k) & (t < tf + hold * NS_MIN)
    px = b if side > 0 else a
    s_hit = m & ((px - stop) * side <= 0)
    g_hit = m & ((px - tgt) * side >= 0)
    js = int(s_hit.argmax()) if s_hit.any() else 10**12
    jg = int(g_hit.argmax()) if g_hit.any() else 10**12
    if js < jg:
        return dict(filled=True, exit="stop", usd=-sl - stop_slip, t_fill=tf)
    if jg < 10**12:
        return dict(filled=True, exit="win", usd=tp, t_fill=tf)
    idx = np.flatnonzero(m)
    if not len(idx):
        return None
    j = idx[-1]
    out = (b[j] - SLIP - fill) if side > 0 else (fill - a[j] - SLIP)
    return dict(filled=True, exit="time", usd=out, t_fill=tf)
