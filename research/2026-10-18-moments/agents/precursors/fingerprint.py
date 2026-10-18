"""The formation fingerprint of every snap (notes.md "similar means the same formation"): per timeframe, ATR-ZigZag
swings on the 120 visible bars and 20 attributes of the formation and the indicators' movement.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/fingerprint.py
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

import plib
from plib import HERE

T0 = time.time()
TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
WIN, ZZ_K, EQ = 120, 3.0, 0.25


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.0f}s] {msg}", flush=True)


def raw(b: pd.DataFrame) -> dict[str, np.ndarray]:
    """Prices and the MT5-exact indicators (foundation.py) of a timeframe's bars. MACD: `hist` is the MACD line (what
    MT5 draws as the histogram), `sig` its SMA(9) signal."""
    import foundation as F  # noqa: PLC0415

    h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
    atr = F.atr(h, lo, c, 14)
    rsi = F.rsi(c, 14)
    line, sig = F.macd(c)
    k, dd = F.stochastic(h, lo, c, 14, 3, 3)
    e20, e50 = F.ema(c, 20), F.ema(c, 50)
    mid, up, _low = F.bands(c, 20, 2.0)
    sd = (up - mid) / 2.0
    width = sd / mid
    wpct = pd.Series(width).rolling(120, min_periods=60).rank(pct=True).to_numpy()
    pdi, ndi, adx = F.adx(h, lo, c, 14)
    out = dict(h=h, lo=lo, c=c, atr=atr, rsi=rsi, macd=line, sig=sig, hist=line, k=k, d=dd, e20=e20, e50=e50,
               mid=mid, sd=sd, width=width, wpct=wpct, pdi=pdi, ndi=ndi, adx=adx)
    return {key: np.asarray(v, dtype=float) for key, v in out.items()}


def zigzag(h: np.ndarray, lo: np.ndarray, atr: np.ndarray, k: float = ZZ_K):
    """Causal ATR ZigZag: (pivot bar, price, +1 peak / -1 trough, the bar that confirmed it)."""
    piv = []
    n = len(h)
    i0 = int(np.argmax(np.isfinite(atr)))
    hi_i, lo_i = i0, i0
    direction = 0
    ext_i = i0
    for i in range(i0, n):
        thr = k * atr[i]
        if not np.isfinite(thr):
            continue
        if direction == 0:
            if h[i] > h[hi_i]:
                hi_i = i
            if lo[i] < lo[lo_i]:
                lo_i = i
            if h[hi_i] - lo[lo_i] >= thr:
                if lo_i < hi_i:
                    piv.append((lo_i, lo[lo_i], -1, i))
                    direction, ext_i = 1, hi_i
                else:
                    piv.append((hi_i, h[hi_i], 1, i))
                    direction, ext_i = -1, lo_i
        elif direction == 1:
            if h[i] >= h[ext_i]:
                ext_i = i
            elif h[ext_i] - lo[i] >= thr:
                piv.append((ext_i, h[ext_i], 1, i))
                direction, ext_i = -1, i
        else:
            if lo[i] <= lo[ext_i]:
                ext_i = i
            elif h[i] - lo[ext_i] >= thr:
                piv.append((ext_i, lo[ext_i], -1, i))
                direction, ext_i = 1, i
    p = np.array(piv, dtype=float).reshape(-1, 4)
    return p[:, 0].astype(int), p[:, 1], p[:, 2].astype(int), p[:, 3].astype(int)


def cmp(a: float, b: float, tol: float) -> int:
    if not (np.isfinite(a) and np.isfinite(b)):
        return 3
    return 1 if abs(a - b) <= tol else (2 if a > b else 0)


def ratio_code(x: float) -> int:
    if not np.isfinite(x):
        return 3
    return 0 if x < 0.5 else (1 if x <= 1.0 else 2)


def fingerprint(R: dict[str, np.ndarray], bi: np.ndarray) -> pd.DataFrame:
    pidx, pval, ptyp, pconf = zigzag(R["h"], R["lo"], R["atr"])
    c, atr, rsi = R["c"], R["atr"], R["rsi"]
    rows = np.zeros((len(bi), 20), np.int8)
    for r, b in enumerate(bi):
        a = atr[b] if np.isfinite(atr[b]) else np.nan
        kk = np.searchsorted(pconf, b, side="right")
        sel = np.arange(kk)[pidx[:kk] >= b - WIN + 1]
        n_in = len(sel)
        rows[r, 0] = np.digitize(n_in, [3, 6, 10])
        last = sel[-4:] if n_in else np.array([], int)
        pk = [j for j in sel if ptyp[j] == 1][-3:]
        tr = [j for j in sel if ptyp[j] == -1][-3:]
        rows[r, 1] = 2 if n_in == 0 else (0 if ptyp[sel[-1]] == 1 else 1)
        tol = EQ * a
        pkv = [pval[j] for j in pk]
        trv = [pval[j] for j in tr]
        rows[r, 2] = cmp(pkv[-1], pkv[-2], tol) if len(pkv) >= 2 else 3
        rows[r, 3] = cmp(pkv[-2], pkv[-3], tol) if len(pkv) >= 3 else 3
        rows[r, 4] = cmp(trv[-1], trv[-2], tol) if len(trv) >= 2 else 3
        rows[r, 5] = cmp(trv[-2], trv[-3], tol) if len(trv) >= 3 else 3
        if len(last) >= 2:
            cur = abs(c[b] - pval[last[-1]])
            prev = abs(pval[last[-1]] - pval[last[-2]])
            rows[r, 6] = ratio_code(cur / prev if prev > 0 else np.nan)
            rows[r, 7] = ratio_code(prev / abs(pval[last[-2]] - pval[last[-3]])) if len(last) >= 3 and \
                abs(pval[last[-2]] - pval[last[-3]]) > 0 else 3
        else:
            rows[r, 6] = rows[r, 7] = 3
        if pkv and trv:
            P, T = pkv[-1], trv[-1]
            if c[b] > P:
                rows[r, 8] = 0
            elif c[b] < T:
                rows[r, 8] = 1
            else:
                f = (c[b] - T) / (P - T) if P > T else 0.5
                rows[r, 8] = 2 if f > 2 / 3 else (3 if f >= 1 / 3 else 4)
        else:
            rows[r, 8] = 5
        net = (c[b] - c[max(b - WIN + 1, 0)]) / a if np.isfinite(a) and a > 0 else 0.0
        rows[r, 9] = np.digitize(net, [-6, -2, 2, 6])
        x = rsi[b]
        rows[r, 10] = np.digitize(x if np.isfinite(x) else 50, [30, 45, 55, 70])
        rows[r, 11] = int(b >= 3 and np.isfinite(rsi[b - 3]) and x > rsi[b - 3])
        # RSI at the swings' BARS (pidx), not at their numbers in the swing list (bug to 2026-10-18, test_parts.py)
        bear = len(pk) >= 2 and pkv[-1] > pkv[-2] + tol and rsi[pidx[pk[-1]]] < rsi[pidx[pk[-2]]]
        bull = len(tr) >= 2 and trv[-1] < trv[-2] - tol and rsi[pidx[tr[-1]]] > rsi[pidx[tr[-2]]]
        rows[r, 12] = 3 if (bear and bull) else (1 if bear else (2 if bull else 0))
        hist = R["hist"]
        rows[r, 13] = int(hist[b] > 0) * 2 + int(b >= 1 and hist[b] > hist[b - 1])
        rows[r, 14] = int(R["macd"][b] > 0)
        diff = R["macd"][max(b - 3, 0):b + 1] - R["sig"][max(b - 3, 0):b + 1]
        s = np.sign(diff)
        rows[r, 15] = 1 if (s[-1] > 0 and (s[:-1] <= 0).any()) else (2 if (s[-1] < 0 and (s[:-1] >= 0).any()) else 0)
        kv, dv = R["k"][b], R["d"][b]
        rows[r, 16] = np.digitize(kv if np.isfinite(kv) else 50, [20, 80.0001]) * 2 + int(kv > dv)
        e20, e50 = R["e20"], R["e50"]
        stack = 0 if c[b] > e20[b] > e50[b] else (1 if c[b] < e20[b] < e50[b] else 2)
        rows[r, 17] = stack * 2 + int(b >= 3 and e20[b] > e20[b - 3])
        mid, sd = R["mid"][b], R["sd"][b]
        pos = 0 if c[b] < mid - 2 * sd else (1 if c[b] < mid else (2 if c[b] <= mid + 2 * sd else 3))
        wp = R["wpct"][b]
        wstate = 0 if (np.isfinite(wp) and wp < 0.2) else (1 if (b >= 3 and R["width"][b] > R["width"][b - 3]) else 2)
        rows[r, 18] = pos * 3 + wstate
        adx = R["adx"][b]
        lead = 0 if R["pdi"][b] >= R["ndi"][b] else 1
        rows[r, 19] = 0 if not (np.isfinite(adx) and adx >= 20) else (1 + lead + 2 * int(adx < R["adx"][b - 1]))
    names = ["npiv", "leg", "pk1", "pk2", "tr1", "tr2", "legr", "legr2", "where", "net", "rsi", "rsi_up", "div",
             "macd_h", "macd0", "macd_x", "stoch", "ema", "bb", "adx"]
    return pd.DataFrame(rows, columns=names)


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.load()
    S = pd.read_parquet(HERE / "snaps.parquet")
    s_ts = S.S.to_numpy()
    parts = []
    for tf in TFS:
        if tf == "M1":
            b = m.reset_index(drop=True)
            bi = S.idx.to_numpy()
        else:
            b = plib.tf_bars(m, RULE[tf])
            bi = np.searchsorted(b["avail"].to_numpy(), s_ts, side="right") - 1
        R = raw(b)
        fp = fingerprint(R, bi)
        fp.columns = [f"{tf}_fp_{x}" for x in fp.columns]
        parts.append(fp)
        log(f"{tf}: {len(zigzag(R['h'], R['lo'], R['atr'])[0])} swings in all, {len(b)} bars")
    F = pd.concat(parts, axis=1)
    F.index = S.index
    F.to_parquet(HERE / "snap_fingerprints.parquet")
    log(f"saved {F.shape}")
    d = (S.half != "W").to_numpy()
    for tf in TFS:
        print(tf, "swings in the window (code 0: 0-2, 1: 3-5, 2: 6-9, 3: 10+):",
              F.loc[d, f"{tf}_fp_npiv"].value_counts(normalize=True).sort_index().round(2).to_dict())


if __name__ == "__main__":
    main()
