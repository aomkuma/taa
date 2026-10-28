"""The indicators exactly as MetaTrader 5 computes them - the charts the owner reads - transcribed from the terminal's
own sources (MQL5/Indicators/Examples: ATR.mq5, RSI.mq5, MACD.mq5, Stochastic.mq5, ADX.mq5, Custom Moving Average.mq5,
Include/MovingAverages.mqh). One source of truth for the research; tested against literal ports of the MQL5 loops in
test_foundation.py.

NaN marks the warm-up bars where MT5 draws nothing (MT5 writes 0.0 there).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(x: np.ndarray, n: int) -> np.ndarray:
    """MT5 EMA: seeded with the first price, then x * 2/(n+1) + prev * (1 - 2/(n+1)) (Custom Moving Average.mq5)."""
    return pd.Series(np.asarray(x, float)).ewm(span=n, adjust=False).mean().to_numpy()


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(np.asarray(x, float)).rolling(n).mean().to_numpy()


def true_range(h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> np.ndarray:
    """MT5 ATR.mq5: max(high, previous close) - min(low, previous close); bar 0 has no previous close (NaN)."""
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(lo, pc)
    tr[0] = np.nan
    return tr


def atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    """MT5 ATR: the simple average of the last n true ranges (first at bar n)."""
    return pd.Series(true_range(h, lo, c)).rolling(n).mean().to_numpy()


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    """MT5 RSI.mq5: Wilder's smoothing seeded with the simple average of the first n changes (first at bar n);
    100 when there is no loss, 50 when there is no move at all."""
    c = np.asarray(c, float)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c)
    gain, loss = np.maximum(d, 0.0), np.maximum(-d, 0.0)
    pos, neg = gain[:n].mean(), loss[:n].mean()
    pos_s, neg_s = np.empty(len(c)), np.empty(len(c))
    pos_s[n], neg_s[n] = pos, neg
    for i in range(n + 1, len(c)):
        pos = (pos * (n - 1) + gain[i - 1]) / n
        neg = (neg * (n - 1) + loss[i - 1]) / n
        pos_s[i], neg_s[i] = pos, neg
    p, q = pos_s[n:], neg_s[n:]
    with np.errstate(divide="ignore", invalid="ignore"):
        out[n:] = np.where(q != 0, 100.0 - 100.0 / (1.0 + p / q), np.where(p != 0, 100.0, 50.0))
    return out


def macd(c: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray]:
    """MT5 MACD.mq5: the MACD line (EMA fast - EMA slow; drawn as the histogram) and the signal = SMA(signal) of it."""
    line = ema(c, fast) - ema(c, slow)
    return line, sma(line, signal)


def stochastic(h: np.ndarray, lo: np.ndarray, c: np.ndarray, k: int = 14, d: int = 3, slowing: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """MT5 Stochastic.mq5: main = 100 * sum(close - lowest) / sum(highest - lowest) over `slowing` bars (100 when the
    sum of ranges is 0); signal = SMA(d) of main."""
    hh = pd.Series(np.asarray(h, float)).rolling(k).max()
    ll = pd.Series(np.asarray(lo, float)).rolling(k).min()
    num = (pd.Series(np.asarray(c, float)) - ll).rolling(slowing).sum()
    den = (hh - ll).rolling(slowing).sum()
    main = np.where(den == 0, 100.0, 100.0 * num / den.replace(0, np.nan))
    main = np.where(den.isna(), np.nan, main)
    return main, sma(main, d)


def adx(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MT5 ADX.mq5 (not Wilder's ADXW): per bar +DM / -DM (the larger only, ties none) as a share of the true range,
    smoothed by an EMA(n) that starts from 0 at bar 0; ADX = EMA(n) of DX. Returns (+DI, -DI, ADX)."""
    h, lo, c = (np.asarray(x, float) for x in (h, lo, c))
    up = np.r_[0.0, h[1:] - h[:-1]]
    dn = np.r_[0.0, lo[:-1] - lo[1:]]
    up, dn = np.maximum(up, 0.0), np.maximum(dn, 0.0)
    pos = np.where(up > dn, up, 0.0)
    neg = np.where(dn > up, dn, 0.0)
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(np.maximum(np.abs(h - lo), np.abs(h - pc)), np.abs(lo - pc))
    with np.errstate(divide="ignore", invalid="ignore"):
        pd_ = np.where(tr != 0, 100.0 * pos / tr, 0.0)
        nd_ = np.where(tr != 0, 100.0 * neg / tr, 0.0)
    pd_[0] = nd_[0] = 0.0
    pdi, ndi = ema(pd_, n), ema(nd_, n)
    s = pdi + ndi
    with np.errstate(divide="ignore", invalid="ignore"):
        dx = np.where(s != 0, 100.0 * np.abs((pdi - ndi) / s), 0.0)
    dx[0] = 0.0
    return pdi, ndi, ema(dx, n)


def bands(c: np.ndarray, n: int = 20, k: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MT5 Bands: SMA(n) +- k x the population standard deviation of the last n closes."""
    s = pd.Series(np.asarray(c, float))
    mid = s.rolling(n).mean()
    sd = s.rolling(n).std(ddof=0)
    return mid.to_numpy(), (mid + k * sd).to_numpy(), (mid - k * sd).to_numpy()


def fractals(h: np.ndarray, lo: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Fractal swings: bars whose high (low) is the highest (lowest) of the k bars on each side - known only k bars
    later. Equal highs (lows) inside one window are each a swing. Returns the bar indices (highs, lows)."""
    h, lo = np.asarray(h, float), np.asarray(lo, float)
    hw = pd.Series(h).rolling(2 * k + 1, center=True).max().to_numpy()
    lw = pd.Series(lo).rolling(2 * k + 1, center=True).min().to_numpy()
    return np.nonzero((h == hw) & np.isfinite(hw))[0], np.nonzero((lo == lw) & np.isfinite(lw))[0]


def merge_levels(prices: np.ndarray, tol: float) -> tuple[np.ndarray, np.ndarray]:
    """Swing prices into levels no wider than tol: sorted, a price joins the current level while it is within tol of
    that level's FIRST price (no chaining into wide bands). Returns (level = the mean of its prices, how many)."""
    v = np.sort(np.asarray(prices, float))
    if len(v) == 0 or not tol > 0:
        return np.empty(0), np.empty(0, int)
    lv, cnt = [], []
    a = 0
    for b in range(1, len(v) + 1):
        if b == len(v) or v[b] - v[a] > tol:
            lv.append(float(v[a:b].mean()))
            cnt.append(b - a)
            a = b
    return np.array(lv), np.array(cnt)
