"""The foundation indicators against literal Python ports of the MetaTrader 5 sources (the loops copied line by line
from C:/MT5/taa-bot/MQL5/Indicators/Examples), on random bars and on real gold bars; plus hand-worked values.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_foundation.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundation as F  # noqa: E402


# ---------------------------------------------------------------- literal ports of the MQL5 loops (the reference)
def mql_ema(price, n):  # Custom Moving Average.mq5 CalculateEMA
    out = np.zeros(len(price))
    sf = 2.0 / (1.0 + n)
    out[0] = price[0]
    for i in range(1, len(price)):
        out[i] = price[i] * sf + out[i - 1] * (1.0 - sf)
    return out


def mql_atr(high, low, close, n):  # ATR.mq5
    tr = np.zeros(len(close))
    out = np.zeros(len(close))
    for i in range(1, len(close)):
        tr[i] = max(high[i], close[i - 1]) - min(low[i], close[i - 1])
    first = 0.0
    for i in range(1, n + 1):
        first += tr[i]
    out[n] = first / n
    for i in range(n + 1, len(close)):
        out[i] = out[i - 1] + (tr[i] - tr[i - n]) / n
    return out


def mql_rsi(price, n):  # RSI.mq5
    rsi = np.zeros(len(price))
    pos_b = np.zeros(len(price))
    neg_b = np.zeros(len(price))
    sp = sn = 0.0
    for i in range(1, n + 1):
        d = price[i] - price[i - 1]
        sp += d if d > 0 else 0
        sn += -d if d < 0 else 0
    pos_b[n], neg_b[n] = sp / n, sn / n
    rsi[n] = 100.0 - 100.0 / (1.0 + pos_b[n] / neg_b[n]) if neg_b[n] != 0 else (100.0 if pos_b[n] != 0 else 50.0)
    for i in range(n + 1, len(price)):
        d = price[i] - price[i - 1]
        pos_b[i] = (pos_b[i - 1] * (n - 1) + (d if d > 0 else 0.0)) / n
        neg_b[i] = (neg_b[i - 1] * (n - 1) + (-d if d < 0 else 0.0)) / n
        rsi[i] = 100.0 - 100.0 / (1 + pos_b[i] / neg_b[i]) if neg_b[i] != 0 else (100.0 if pos_b[i] != 0 else 50.0)
    return rsi


def mql_sma_on_buffer(price, period):  # MovingAverages.mqh SimpleMAOnBuffer, begin = 0
    buf = np.zeros(len(price))
    start = period
    buf[start - 1] = sum(price[0:start]) / period
    for i in range(start, len(price)):
        buf[i] = buf[i - 1] + (price[i] - price[i - period]) / period
    return buf


def mql_stoch(high, low, close, k, d, slowing):  # Stochastic.mq5
    n = len(close)
    lows, highs, main, sig = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    for i in range(k - 1, n):
        lows[i] = min(low[i - k + 1:i + 1])
        highs[i] = max(high[i - k + 1:i + 1])
    for i in range(k - 1 + slowing - 1, n):
        sl = sum(close[j] - lows[j] for j in range(i - slowing + 1, i + 1))
        sh = sum(highs[j] - lows[j] for j in range(i - slowing + 1, i + 1))
        main[i] = 100.0 if sh == 0 else sl / sh * 100
    for i in range(d - 1, n):
        sig[i] = sum(main[i - j] for j in range(d)) / d
    return main, sig


def mql_adx(high, low, close, n):  # ADX.mq5
    m = len(close)
    pdi, ndi, adx, pdb, ndb, tmpb = (np.zeros(m) for _ in range(6))
    pr = 2.0 / (n + 1.0)
    for i in range(1, m):
        tp, tn = high[i] - high[i - 1], low[i - 1] - low[i]
        tp, tn = max(tp, 0.0), max(tn, 0.0)
        if tp > tn:
            tn = 0.0
        elif tp < tn:
            tp = 0.0
        else:
            tp = tn = 0.0
        tr = max(max(abs(high[i] - low[i]), abs(high[i] - close[i - 1])), abs(low[i] - close[i - 1]))
        pdb[i], ndb[i] = (100.0 * tp / tr, 100.0 * tn / tr) if tr != 0 else (0.0, 0.0)
        pdi[i] = pdb[i] * pr + pdi[i - 1] * (1 - pr)
        ndi[i] = ndb[i] * pr + ndi[i - 1] * (1 - pr)
        s = pdi[i] + ndi[i]
        tmpb[i] = 100.0 * abs((pdi[i] - ndi[i]) / s) if s != 0 else 0.0
        adx[i] = tmpb[i] * pr + adx[i - 1] * (1 - pr)
    return pdi, ndi, adx


# ---------------------------------------------------------------- data
def random_bars(n=600, seed=1):
    rng = np.random.default_rng(seed)
    c = 2000 + np.cumsum(rng.normal(0, 1.5, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 1.2, n)
    lo = np.minimum(o, c) - rng.uniform(0, 1.2, n)
    c[100:104] = c[99]  # a flat stretch (zero moves) to exercise the special cases
    h[100:104], lo[100:104], o[100:104] = c[99], c[99], c[99]
    return o, h, lo, c


@pytest.fixture(scope="module", params=["random", "gold"])
def bars(request):
    if request.param == "random":
        return random_bars()
    import plib  # noqa: PLC0415

    m = plib.load()
    m = m[(m.index >= "2026-03-09 00:00") & (m.index < "2026-03-09 12:00")]  # the 2026-03-09 morning, 720 M1 bars
    return tuple(m[k].to_numpy(float) for k in ("open", "high", "low", "close"))


def close_after(a, b, start):
    np.testing.assert_allclose(a[start:], b[start:], rtol=0, atol=1e-9)


def test_ema_is_mt5s(bars):
    _o, _h, _l, c = bars
    for n in (20, 50, 12, 26):
        close_after(F.ema(c, n), mql_ema(c, n), 0)


def test_atr_is_mt5s(bars):
    _o, h, lo, c = bars
    close_after(F.atr(h, lo, c, 14), mql_atr(h, lo, c, 14), 14)


def test_rsi_is_mt5s(bars):
    _o, _h, _l, c = bars
    close_after(F.rsi(c, 14), mql_rsi(c, 14), 14)


def test_macd_is_mt5s(bars):
    _o, _h, _l, c = bars
    line, sig = F.macd(c)
    close_after(line, mql_ema(c, 12) - mql_ema(c, 26), 0)
    close_after(sig, mql_sma_on_buffer(mql_ema(c, 12) - mql_ema(c, 26), 9), 8)


def test_stochastic_is_mt5s(bars):
    _o, h, lo, c = bars
    main, sig = F.stochastic(h, lo, c, 14, 3, 3)
    rm, rs = mql_stoch(h, lo, c, 14, 3, 3)
    close_after(main, rm, 15)
    close_after(sig, rs, 15 + 2)  # MT5 averages its warm-up zeros into the first signals; compare after them


def test_adx_is_mt5s(bars):
    _o, h, lo, c = bars
    for mine, ref in zip(F.adx(h, lo, c, 14), mql_adx(h, lo, c, 14)):
        close_after(mine, ref, 1)


def test_hand_worked_values():
    # true ranges of these bars: bar1 max(12,10)-min(9,10)=3, bar2 max(13,11)-min(10,11)=3, bar3 max(12,12)-min(8,12)=4
    h, lo, c = np.array([11.0, 12, 13, 12]), np.array([9.0, 9, 10, 8]), np.array([10.0, 11, 12, 9])
    assert F.true_range(h, lo, c)[1:].tolist() == [3.0, 3.0, 4.0]
    assert F.atr(h, lo, c, 3)[3] == pytest.approx(10 / 3)
    # RSI over 2 bars: changes +1, +1, -3 -> seed gains 1, losses 0 -> 100; next: gain (1*1+0)/2=0.5, loss (0+3)/2=1.5
    r = F.rsi(np.array([10.0, 11, 12, 9]), 2)
    assert r[2] == 100.0 and r[3] == pytest.approx(100 - 100 / (1 + 0.5 / 1.5))
    # a flat market: RSI 50, Stochastic 100 (MT5's conventions)
    assert F.rsi(np.full(10, 5.0), 3)[5] == 50.0
    flat = np.full(10, 5.0)
    assert F.stochastic(flat, flat, flat, 3, 2, 2)[0][6] == 100.0
