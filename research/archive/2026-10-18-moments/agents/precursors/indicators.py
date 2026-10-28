"""Why gold runs the way it does - the components (owner, 2026-10-19: "dig deeper into why it runs that way, looking at
many components - the larger timeframes and the indicators"). For every moment of the present library, each
timeframe's indicators exactly as MetaTrader 5 draws them (foundation.py) at the last bar closed by that moment:
- RSI(14); MACD(12, 26, 9) line and line - signal, in ATRs; Stochastic(14, 3, 3) main and main - signal;
  ADX(14) and +DI - -DI; Bollinger(20, 2) %B and width in ATRs;
- the close against EMA 20 / 50 / 200 (in ATRs) and each EMA's slope over 5 bars (in ATRs);
- ATR(14) against its own median of the last 100 bars;
on M5, M15, H1, H4 and D1 (D1 and H4 on the broker's server day, Europe/Athens, as the terminal draws them), and on D1
the close's place in the previous day's range and its distance from today's open. Only bars complete by the moment.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/indicators.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402

TFS = {"M5": "5min", "M15": "15min", "H1": "1h", "H4": "4h", "D1": "1D"}


def bars(m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Bars of a timeframe from M1 (open, high, low, close, avail = complete by). H4 and D1 on the server day
    (Europe/Athens) like the terminal's chart; the others on the clock."""
    if rule in ("4h", "1D"):
        key = m.index.tz_convert("Europe/Athens").tz_localize(None).floor(rule)
    else:
        key = m.index.floor(rule)
    g = m.assign(_k=key, _t=m.index).groupby("_k", sort=True)
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(), "last": g._t.max()})
    b["avail"] = b["last"] + pd.Timedelta(minutes=1)
    return b.reset_index(drop=True)


def series(b: pd.DataFrame) -> dict[str, np.ndarray]:
    """Every indicator of one timeframe, bar by bar (each bar's value uses that bar and the ones before it only)."""
    h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
    a = F.atr(h, lo, c, 14)
    out = {"rsi": F.rsi(c, 14)}
    line, sig = F.macd(c)
    out["macd"], out["macd_sig"] = line / a, (line - sig) / a
    st, st_sig = F.stochastic(h, lo, c)
    out["stoch"], out["stoch_sig"] = st, st - st_sig
    pdi, ndi, ad = F.adx(h, lo, c)
    out["adx"], out["di"] = ad, pdi - ndi
    mid, up, dn = F.bands(c)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["bb_pos"] = (c - dn) / (up - dn)
    out["bb_width"] = (up - dn) / a
    for n in (20, 50, 200):
        e = np.array(F.ema(c, n), float)
        e[: n - 1] = np.nan  # the warm-up: too few bars for the average to mean anything
        out[f"ema{n}"] = (c - e) / a
        out[f"ema{n}_slope"] = (e - pd.Series(e).shift(5).to_numpy()) / a  # over 5 bars
    out["atr_rel"] = a / pd.Series(a).rolling(100, min_periods=50).median().to_numpy()
    return out


def at(avail_ns: np.ndarray, t_ns: np.ndarray) -> np.ndarray:
    """The last bar complete by each moment (avail <= t); -1 when none."""
    return np.searchsorted(avail_ns, t_ns, side="right") - 1


def features(m: pd.DataFrame, t: pd.DatetimeIndex) -> pd.DataFrame:
    """Every timeframe's indicators at each moment t (UTC), from the bars complete by t."""
    t_ns = t.as_unit("ns").asi8
    cols = {}
    for tf, rule in TFS.items():
        b = bars(m, rule)
        bi = at(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, t_ns)
        ok = bi >= 0
        for k, v in series(b).items():
            x = np.full(len(t), np.nan)
            x[ok] = v[bi[ok]]
            cols[f"{tf}_{k}"] = x
        if tf == "D1":
            h, lo, c, o = (b[k].to_numpy(float) for k in ("high", "low", "close", "open"))
            a = F.atr(h, lo, c, 14)
            # today's day is the bar after the last complete one; the close now is the last M1 close by t
            m_av = (m.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8
            px = m.close.to_numpy(float)[np.searchsorted(m_av, t_ns, side="right") - 1]
            nxt = np.minimum(bi + 1, len(b) - 1)
            with np.errstate(divide="ignore", invalid="ignore"):
                cols["D1_prev_pos"] = np.where(ok, (px - lo[np.maximum(bi, 0)]) / (h[np.maximum(bi, 0)] - lo[np.maximum(bi, 0)]), np.nan)
                cols["D1_from_open"] = np.where(ok & (bi + 1 < len(b)), (px - o[nxt]) / a[np.maximum(bi, 0)], np.nan)
    return pd.DataFrame(cols, index=t)


def main() -> None:
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    P = pd.read_parquet(HERE / "present_3y.parquet")
    m = plib.load()
    t = pd.DatetimeIndex(P.t_dec)
    X = features(m, t)
    X.reset_index(drop=True).to_parquet(HERE / "indicators_3y.parquet")
    print(f"{len(X)} moments x {X.shape[1]} indicator readings; missing share by timeframe:",
          {tf: round(float(X.filter(like=f"{tf}_").isna().mean().mean()), 4) for tf in TFS})


if __name__ == "__main__":
    main()
