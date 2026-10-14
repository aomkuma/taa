"""Chart read M0 (docs/CHART_READ.md §2): how the bot reads trend today vs a major-swing (zigzag) structure read, and which predicts the next move.

A: market map state (ADX/ER/EMA + fractal structure, hysteresis) - what the setups' screens use
B: fractal k=3 swing structure (HH+HL / LH+LL) - what _structure_with uses
C: major-swing structure: ATR zigzag (3 x ATR14) pivots labelled HH/HL/LH/LL - the read a trader draws
Forward: the close 24 bars later minus the close now, in ATR, signed by the read's direction.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.evidence.zigzag import zigzag  # noqa: E402
from app.indicators.market_map import MapParams, state_frame
from app.indicators.price_action import label_structure, market_structure
from app.indicators.volatility import atr

H = "data/history/FBS-Demo"
FWD = 24


def zig_trend(d: pd.DataFrame, a: pd.Series, mult: float) -> tuple[list, int]:
    piv = zigzag(d["high"], d["low"], a, mult)
    ev = label_structure(piv, 0.0)
    n = len(d)
    hi, lo = [None] * n, [None] * n
    cur = {"HIGH": None, "LOW": None}
    j = 0
    for t in range(n):
        while j < len(ev) and ev[j].swing.confirm_pos <= t:
            if ev[j].label is not None:
                cur[ev[j].swing.kind.value if hasattr(ev[j].swing.kind, "value") else str(ev[j].swing.kind)] = str(ev[j].label.value)
            j += 1
        hi[t], lo[t] = cur.get("HIGH") or cur.get("high"), cur.get("LOW") or cur.get("low")
    out = []
    for h, l in zip(hi, lo):
        if h is None or l is None:
            out.append("NONE")
        elif h == "HH" and l == "HL":
            out.append("UP")
        elif h == "LH" and l == "LL":
            out.append("DOWN")
        else:
            out.append("MIXED")
    return out, len(piv)


def flips(s: pd.Series) -> float:
    x = s[s.isin(["UP", "DOWN"])]
    return float((x != x.shift()).sum() - 1)


rows = []
for sym in ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY"):
    for tf in ("H1", "H4"):
        d = pd.read_parquet(f"{H}/{sym}/{tf}.parquet").sort_values("close_time").reset_index(drop=True)
        a = atr(d["high"].astype(float), d["low"].astype(float), d["close"].astype(float), 14)
        st = state_frame(d, MapParams())
        A = st["state"].astype(str).reset_index(drop=True)
        B = market_structure(d["high"].astype(float), d["low"].astype(float), 3)["trend"].astype(str).replace({"RANGE": "MIXED", "None": "NONE"}).reset_index(drop=True)
        C, npiv = zig_trend(d, a, 3.0)
        C = pd.Series(C)
        fwd = (d["close"].shift(-FWD) - d["close"]) / a
        ok = fwd.notna() & a.notna()
        for name, s in (("A map state", A), ("B fractal k3", B), ("C zigzag 3ATR", C)):
            sign = s.map({"UP": 1, "DOWN": -1}).fillna(0)
            m = ok & (sign != 0)
            rows.append({
                "sym": sym, "tf": tf, "read": name,
                "trend share %": round(100 * m.sum() / ok.sum(), 1),
                "flips/1000 bars": round(1000 * flips(s[ok]) / ok.sum(), 1),
                "fwd ATR with read": round((fwd[m] * sign[m]).mean(), 3),
                "hit %": round(100 * ((fwd[m] * sign[m]) > 0).mean(), 1),
            })
        # where they disagree: C says a trend, A says no trend
        cA = pd.crosstab(C[ok], A[ok], normalize="index").round(2)
        if sym == "XAUUSD" and tf == "H1":
            print("XAUUSD H1: rows = zigzag read C, cols = map state A (share of C's bars)")
            print(cA.to_string(), "\n")
t = pd.DataFrame(rows)
print(t.to_string(index=False))
print("\nmean over symbols:")
print(t.groupby(["tf", "read"])[["trend share %", "flips/1000 bars", "fwd ATR with read", "hit %"]].mean().round(3).to_string())
