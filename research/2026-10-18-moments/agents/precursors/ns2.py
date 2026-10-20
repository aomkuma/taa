"""NS-2: PLAN-1's 08:30-NY straddle scaled to the present volatility (notes.md "NS-2", written before computing):
k = MT5 ATR(14) of the last H1 bar closed by 08:30 NY / 16.33; trigger 2 k, stop 8 k; release days only.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/ns2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import check_plan1 as C
import ns1_ticks as N

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # gold.py
ROOT = Path(__file__).resolve().parents[4]
REF_ATR = 16.33
MIN, NS = 60 * 10**9, 10**9


def h1_atr() -> pd.Series:
    """MT5 ATR(14) per H1 bar (the simple mean of 14 true ranges), indexed by the bar's close time (open + 1 h)."""
    import gold  # noqa: PLC0415

    h = gold.bars("H1", before=pd.Timestamp("2026-10-18", tz="UTC"))
    pc = h.close.shift(1)
    tr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr.index = h.index + pd.Timedelta(hours=1)
    return atr


def k_at(atr: pd.Series, t0: int) -> float:
    i = int(np.searchsorted(atr.index.as_unit("ns").asi8, t0, side="right")) - 1  # the last H1 bar closed by t0
    return float(atr.iloc[i]) / REF_ATR if i >= 0 else float("nan")


def straddle_k(t, bid, ask, t0: int, k: float) -> dict | None:
    trig, stop_d = 2 * k, 8 * k
    i0 = int(np.searchsorted(t, t0, side="left")) - 1
    if i0 < 0 or t[-1] < t0 + 30 * MIN or not np.isfinite(k):
        return None
    up, dn = ask[i0] + trig, bid[i0] - trig
    hit = None
    for j in range(i0 + 1, len(t)):
        if t[j] >= t0 + 60 * NS:
            break
        if ask[j] >= up:
            hit = (j, 1, max(up, ask[j]))
            break
        if bid[j] <= dn:
            hit = (j, -1, min(dn, bid[j]))
            break
    if hit is None:
        return None
    j, side, e = hit
    r = C.manage(t, bid, ask, j, e, side, e - side * stop_d, None, t0 + 30 * MIN)
    if r is None:
        return None
    px, _, kind = r
    return dict(side=side, k=k, entry=e, pnl=(px - e) * side, R=(px - e) * side / stop_d, exit=kind,
                spread=float(ask[i0] - bid[i0]))


def main() -> None:
    atr = h1_atr()
    cal = pd.read_csv(ROOT / "app/news/us_releases.csv")
    rel = sorted(cal[cal.time_et == "08:30"].date)
    rows = []
    C.EXAM = pd.Timestamp("2026-10-18", tz="UTC")  # P1 / P2 / exam days are a description (the exam already read)
    for d in rel:
        if not ("2021-09-01" <= d <= "2026-10-16"):
            continue
        t0 = pd.Timestamp(f"{d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value
        x = N.load(d) if d < "2025-10-18" else C.day_ticks(pd.Timestamp(t0, tz="UTC").normalize())
        if x is None:
            continue
        r = straddle_k(*x, t0, k_at(atr, t0))
        if r is None:
            continue
        dd = pd.Timestamp(d)
        yr = dd.year if dd.month >= 10 else dd.year - 1
        per = "P1" if "2025-10-18" <= d < "2026-01-16" else "P2" if "2026-01-16" <= d < "2026-04-18" else \
            "exam" if d >= "2026-04-18" else f"{yr}-{(yr + 1) % 100:02d}"
        rows.append(dict(day=d, period=per, **r))
    T = pd.DataFrame(rows)
    order = ["2021-22", "2022-23", "2023-24", "2024-25", "P1", "P2", "exam"]
    g = T.groupby("period").agg(n=("R", "size"), R=("R", "mean"), sumR=("R", "sum"), k=("k", "median"),
                                spread_over_stop=("spread", lambda s: np.nan))
    for p in order:
        x = T[T.period == p]
        if len(x):
            print(f"{p:8s} {len(x):3d} trades, R {x.R.mean():+.3f}, sum {x.R.sum():+6.1f}, median k {x.k.median():.2f} "
                  f"(trigger {2 * x.k.median():.2f}, stop {8 * x.k.median():.2f} USD), spread / stop {np.median(x.spread / (8 * x.k)):.3f}, "
                  f"win {np.mean(x.pnl > 0):.2f}")
    old = T[T.period.isin(order[:4])]
    yrs = old.groupby("period").R.mean()
    verdict = old.R.mean() >= 0.15 and (yrs > 0).sum() >= 3
    se = old.R.std() / np.sqrt(len(old))
    print(f"old years pooled: {len(old)} trades, R {old.R.mean():+.3f} ({old.R.mean() - 1.96 * se:+.3f}..{old.R.mean() + 1.96 * se:+.3f}); "
          f"pass line: {'PASS' if verdict else 'FAIL'}")
    del g
    T.to_parquet(Path(__file__).with_name("ns2.parquet"))


if __name__ == "__main__":
    main()
