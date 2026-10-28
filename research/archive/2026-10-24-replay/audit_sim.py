"""Audit of the M5 trade simulation (owner 2026-10-25: "if everything you tested loses, the problem is your design";
memory: a heavy loss means find the error first).

reclaim_2025.trade() walks M5 bars and, when one bar touches both the stop and the target, counts the stop
(the worse case). With stops near one M5 bar's range that may bias every table toward a loss. Here the same
trades (2025, the reclaim, buffer 1.0 ATR, target 0.7 R) are walked again on M1 bars from the entry (the M5 bar's
close), with the M1 bar's own spread - and a bar that still touches both is counted apart. Printed: how often the
M5 walk met a both-touching bar, R on M5 vs on M1, and a few trades side by side to check by hand.

    .venv/Scripts/python research/2026-10-24-replay/audit_sim.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reclaim_2025 import HOLD, POINT, ROOT, m5_from_m1, signals, trade

from app.core.enums import Timeframe
from app.market_data.history_store import ParquetHistoryStore

BUF, TR = 1.0, 0.7


def plan(m5: pd.DataFrame, s: pd.Series) -> tuple[bool, float, float, float]:
    c, spr = m5.close.to_numpy(float), m5.spread.to_numpy(float) * POINT
    k, sell = int(s.k), bool(s.up)
    entry = c[k] if sell else c[k] + spr[k]
    stop = s.ext + BUF * s.atr if sell else s.ext - BUF * s.atr
    risk = (stop - entry) if sell else (entry - stop)
    tp = entry - TR * risk if sell else entry + TR * risk
    return sell, entry, stop, tp


def both_on_m5(m5: pd.DataFrame, s: pd.Series) -> bool:
    """Did the M5 walk end on a bar that touched both the stop and the target?"""
    h, lo, spr = m5.high.to_numpy(float), m5.low.to_numpy(float), m5.spread.to_numpy(float) * POINT
    sell, _, stop, tp = plan(m5, s)
    for b in range(int(s.k) + 1, min(len(m5) - 1, int(s.k) + HOLD) + 1):
        hit_stop = h[b] + spr[b] >= stop if sell else lo[b] <= stop
        hit_tp = lo[b] + spr[b] <= tp if sell else h[b] >= tp
        if hit_stop or hit_tp:
            return hit_stop and hit_tp
    return False


def on_m1(m1: pd.DataFrame, m5: pd.DataFrame, s: pd.Series) -> tuple[float, bool]:
    """R walked on M1 from the entry bar's close for the same two hours; (R, ended on a both-touching M1 bar)."""
    sell, entry, stop, tp = plan(m5, s)
    risk = abs(entry - stop)
    t0 = m5.index[int(s.k)] + pd.Timedelta(minutes=5)
    i0 = m1.index.searchsorted(t0)
    i1 = min(len(m1), i0 + HOLD * 5)
    h, lo, c = (m1[x].to_numpy(float)[i0:i1] for x in ("high", "low", "close"))
    spr = m1.spread.to_numpy(float)[i0:i1] * POINT
    for b in range(len(h)):
        hit_stop = h[b] + spr[b] >= stop if sell else lo[b] <= stop
        hit_tp = lo[b] + spr[b] <= tp if sell else h[b] >= tp
        if hit_stop:
            return -1.0, hit_tp
        if hit_tp:
            return TR, False
    if not len(c):
        return np.nan, False
    out = (entry - (c[-1] + spr[-1])) if sell else (c[-1] - entry)
    return out / risk, False


def main() -> None:
    raw = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None)
    m1 = raw.assign(t=pd.to_datetime(raw.open_time, utc=True)).drop_duplicates("t", keep="last")
    m1 = m1.set_index("t").sort_index()
    m5 = m5_from_m1(raw)
    part = m5[(m5.index >= "2024-12-31") & (m5.index < "2026-01-01")]
    sig = signals(part).reset_index(drop=True)
    rows = []
    for s in sig.itertuples():
        r5 = trade(part, s, BUF, TR)
        r1, still = on_m1(m1, part, s)
        rows.append(
            {
                "sell": s.up,
                "r5": r5,
                "r1": r1,
                "both5": both_on_m5(part, s),
                "both1": still,
                "t": part.index[s.k],
            }
        )
    ev = pd.DataFrame(rows).dropna()
    print(f"2025 reclaims, buffer {BUF} ATR, target {TR} R: {len(ev)} trades")
    print(
        f"the M5 walk ended on a bar touching BOTH stop and target: {ev.both5.mean():.1%} ({ev.both5.sum()})"
    )
    print(f"on M1 a bar still touching both: {ev.both1.mean():.1%}")
    for name, e in (("SELL", ev[ev.sell]), ("BUY", ev[~ev.sell])):
        print(
            f"{name}: M5 walk {e.r5.mean():+.3f} R (win {(e.r5 > 0).mean():.0%}) | "
            f"M1 walk {e.r1.mean():+.3f} R (win {(e.r1 > 0).mean():.0%})"
        )
    amb = ev[ev.both5]
    print(
        f"the both-touching trades: M5 {amb.r5.mean():+.3f} R, on M1 {amb.r1.mean():+.3f} R "
        f"(M1 won {(amb.r1 > 0).mean():.0%} of them)"
    )
    print("\nsamples (Thai time) to check by hand:")
    for r in ev[ev.both5].head(5).itertuples():
        print(
            f"  {r.t.tz_convert('Asia/Bangkok'):%Y-%m-%d %H:%M} {'SELL' if r.sell else 'BUY'}: M5 {r.r5:+.2f} R, "
            f"M1 {r.r1:+.2f} R"
        )


if __name__ == "__main__":
    main()
