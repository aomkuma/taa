"""The owner's zone grid (owner 2026-10-22, H4 chart of XAUUSD Aug-Oct 2026): after a strong move, the zone size (one
D1 ATR(20)) is carried along in equal steps from the base the move left; price respects the steps (pauses, bounces,
the middle step as a magnet) and runs about half a step inside them; the grid shifts (re-anchors) on a new strong
move or when the step no longer matches the market's size.

Definition v0 (to be confirmed against the owner's lines before any trading test):
- impulse: the move of the last 2 closed D1 bars, |close(t) - open(t-1)| >= IMPULSE x ATR20(t);
- anchor: the edge of the base the move left - the low (a drop) / high (a rally) of the BASE_N D1 bars before it;
- step: ATR20 at the impulse day; levels: anchor + k x step;
- re-anchor: a new impulse, or |ATR20 - step| / step > DRIFT.
Closed D1 bars only (server day, Europe/Athens).
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

IMPULSE, BASE_N, DRIFT = 1.5, 3, 0.30


def d1() -> pd.DataFrame:
    d = pd.read_parquet("data/history/FBS-Demo/XAUUSD/D1.parquet")
    d["t"] = pd.to_datetime(d.open_time, utc=True)
    d = d.drop_duplicates("t", keep="last").set_index("t").sort_index()
    pc = d.close.shift(1)
    d["atr"] = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean()
    return d


def grids(d: pd.DataFrame) -> pd.DataFrame:
    """One row per day: the grid in force after that day closed (anchor, step, why)."""
    rows, cur = [], None
    for i in range(BASE_N + 1, len(d)):
        a, mv = d.atr.iloc[i], d.close.iloc[i] - d.open.iloc[i - 1]
        why = None
        if np.isfinite(a) and abs(mv) >= IMPULSE * a:
            base = d.iloc[i - 1 - BASE_N : i - 1]
            anchor = base.low.min() if mv < 0 else base.high.max()
            cur, why = dict(anchor=float(anchor), step=float(a), since=d.index[i]), "impulse " + ("down" if mv < 0 else "up")
        elif cur is not None and np.isfinite(a) and abs(a - cur["step"]) / cur["step"] > DRIFT:
            cur, why = dict(anchor=cur["anchor"], step=float(a), since=d.index[i]), "step drift"
        if cur is not None:
            rows.append(dict(day=d.index[i], close=d.close.iloc[i], atr=a, **cur, why=why or ""))
    return pd.DataFrame(rows).set_index("day")


def levels(g: pd.Series, lo: float, hi: float) -> list[float]:
    k0, k1 = int(np.floor((lo - g.anchor) / g.step)), int(np.ceil((hi - g.anchor) / g.step))
    return [round(g.anchor + k * g.step, 2) for k in range(k0, k1 + 1)]


if __name__ == "__main__":
    d = d1()
    G = grids(d)
    s, e = sys.argv[1], sys.argv[2]
    ev = G[(G.index >= s) & (G.index < e) & (G.why != "")]
    print(ev[["close", "atr", "anchor", "step", "why"]].round(2).to_string())
    last = G[G.index < e].iloc[-1]
    print("grid in force at", e, ":", round(last.anchor, 2), "step", round(last.step, 2), "since", last.since.date())
    print("levels 4000-4350:", levels(last, 4000, 4350))
