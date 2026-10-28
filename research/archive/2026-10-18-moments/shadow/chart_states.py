"""Round 14 (docs/OWN_SETUP_ROUNDS.md): the chart-state statistics - triple screen (H1 tide, M15 tide, M5 position against
the M15 EMA20) + M5 compression + session at every M5 close, and what followed (a 5 USD run within 30 min; which side
reached 5 first within 60 min; the move against first). Then the states that pass the selection, traded.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/chart_states.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path("research/2026-10-18-moments/agents/journal")))
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
import jlib  # noqa: E402

REF = 4100.0
HALVES = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01"], utc=True)


def _m1(sym: str) -> pd.DataFrame:
    m = gold.bars("M1")
    m = m[(m.index >= pd.Timestamp("2023-08-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-17", tz="UTC"))]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


jlib.m1_frame = _m1


def bars(m: pd.DataFrame, mins: int) -> pd.DataFrame:
    b = m.resample(f"{mins}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b.index = b.index + pd.Timedelta(minutes=mins)  # close-time index
    return b


def tide(b: pd.DataFrame) -> pd.Series:
    e20, e50 = b.close.ewm(span=20, adjust=False).mean(), b.close.ewm(span=50, adjust=False).mean()
    up = (e20 > e20.shift(3)) & (b.close > e50)
    dn = (e20 < e20.shift(3)) & (b.close < e50)
    return pd.Series(np.where(up, 1, np.where(dn, -1, 0)), index=b.index)


def asof(s: pd.Series, t: pd.DatetimeIndex) -> np.ndarray:
    k = s.index.searchsorted(t, side="right") - 1
    v = s.to_numpy()[np.clip(k, 0, None)]
    return np.where(k >= 0, v, np.nan)


def build(P: jlib.Instr) -> pd.DataFrame:
    m = P.m
    m5, m15, h1 = bars(m, 5), bars(m, 15), bars(m, 60)
    t = m5.index[(m5.index >= pd.Timestamp("2023-11-01", tz="UTC")) & (m5.index.hour < 20)]
    d = pd.DataFrame(index=t)
    d["h1"] = asof(tide(h1), t)
    d["m15"] = asof(tide(m15), t)
    e15 = m15.close.ewm(span=20, adjust=False).mean()
    a15 = (m15.high - m15.low).rolling(14).mean()
    c5 = m5.close.reindex(t).to_numpy()
    ext = (c5 - asof(e15, t)) / asof(a15, t)  # the M5 close against the M15 EMA20, in M15 ATR
    side = d.h1.to_numpy()
    sext = ext * np.where(side == 0, 1, side)
    d["pos"] = np.where(side == 0, "n/a", np.where((sext < 0) & (sext > -1), "pullback", np.where(sext > 2, "extended", "neutral")))
    w = 4 * m5.close.rolling(20).std() / m5.close.rolling(20).mean()
    wp = w.rolling(288, min_periods=144).rank(pct=True) * 100
    wpv = wp.reindex(t).to_numpy()
    d["squeeze"] = np.where(wpv <= 20, "squeeze", np.where(wpv >= 80, "wide", "normal"))
    hr = t.hour
    d["session"] = np.where(hr < 7, "Asia", np.where(hr < 12, "London", "NY"))
    # what followed, from the mid price at the M5 close (the M1 bar opening at t)
    pos = P.ot.searchsorted(t)
    ok = (pos + 61 < len(P.o)) & (P.ot[np.clip(pos, 0, len(P.ot) - 1)] == t)
    d = d[ok]
    pos = pos[ok]
    mid = P.o[pos] + P.sp0[pos] / 2
    k = mid / REF * 5.0
    from numpy.lib.stride_tricks import sliding_window_view as win
    H, L = win(P.h, 60)[pos], win(P.lo, 60)[pos]
    up, dn = H - mid[:, None], mid[:, None] - L
    first_up = np.where((up >= k[:, None]).any(1), (up >= k[:, None]).argmax(1), 10**6)
    first_dn = np.where((dn >= k[:, None]).any(1), (dn >= k[:, None]).argmax(1), 10**6)
    d["run30"] = (up[:, :30].max(1) >= k) | (dn[:, :30].max(1) >= k)
    d["first"] = np.where((first_up < first_dn), 1, np.where(first_dn < first_up, -1, 0))
    tide_side = d.h1.to_numpy()
    fr = d["first"].to_numpy()
    d["run60"] = (fr != 0).astype(float)
    # among the points where one side reached 5 USD within 60 minutes: did the H1 tide's side get there first?
    d["tide_first"] = np.where((tide_side == 0) | (fr == 0), np.nan, (fr == tide_side).astype(float))
    d["e"] = pos
    d["k"] = k
    d["half"] = pd.cut(d.index, HALVES, labels=["H1", "H2", "H3", "H4", "H5"], right=False)
    return d


def main() -> None:
    gold.below_normal_priority()
    P = jlib.Instr("XAUUSD")
    d = build(P)
    d.to_parquet("data/research/own_chart_states.parquet")
    des = d[d.index < pd.Timestamp("2026-03-01", tz="UTC")]
    tst = d[d.index >= pd.Timestamp("2026-03-01", tz="UTC")]
    print(f"points: design {len(des)}, window {len(tst)}")
    print(f"base: a 5 USD run within 30 min {100 * des.run30.mean():.0f}%; with the H1 tide first (tide up/down only) "
          f"{100 * des.tide_first.mean():.1f}%")
    keys = ["h1", "m15", "pos", "squeeze", "session"]
    g = des[des.h1 != 0].groupby(keys, observed=True)
    rows = []
    for key, x in g:
        if x.tide_first.notna().sum() < 80:
            continue
        by = x.groupby("half", observed=True).tide_first.mean()
        hits_with = int((by >= 0.58).sum())
        hits_against = int((by <= 0.42).sum())
        rows.append(dict(zip(keys, key, strict=True)) | dict(n=len(x), n_run=int(x.tide_first.notna().sum()), run30=x.run30.mean(), run60=x.run60.mean(), tide_first=x.tide_first.mean(),
                                                              halves_with=hits_with, halves_against=hits_against))
    T = pd.DataFrame(rows).sort_values("tide_first")
    pd.set_option("display.width", 220)
    print("\nStates (H1 tide up/down) with >= 80 design points - the share where the H1 tide's side reached 5 USD first:")
    print(T.round(3).to_string(index=False))
    print("\nBy single factor (design):")
    for f in ("m15", "pos", "squeeze", "session"):
        print(f"  {f}: " + ", ".join(f"{k}: tide-first {v.tide_first.mean():.3f} run30 {v.run30.mean():.2f} (n {len(v)})"
                                     for k, v in des[des.h1 != 0].groupby(f)))
    chosen = T[(T.halves_with >= 4) | (T.halves_against >= 4)]
    print(f"\nChosen states (>= 4 of 5 half-years at >= 58 % / <= 42 %): {len(chosen)}")
    print(chosen.round(3).to_string(index=False))
    T.to_csv("research/2026-10-18-moments/shadow/chart_states_design.csv", index=False)


if __name__ == "__main__":
    main()
