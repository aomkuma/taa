"""The AI's day-4 method on 2025 - owner 2026-10-25: "try the same conditions, the same method, on 2025".

On 9 Jul 2026 the AI sold five reclaims (a sweep over a high closed back) and won one. Is that the method, or the
day? The W07 reclaim as a rule, on every M5 swing level of 2025 (all before the exam):
- level: a confirmed M5 swing high / low (sweep_depth.py's definition: over the 3 bars each side, known 3 bars
  later), waiting at most one day for its break;
- the sweep: the first bar that trades past it; the reclaim: an M5 close back on the near side within 30 minutes
  (6 bars). Entry at that close: a swept HIGH sells, a swept LOW buys;
- stop: the sweep's extreme up to the entry plus BUFFER x the M5 ATR(14) (the AI used about 1.0);
- target: TARGET_R x the risk; out at the close after two hours if neither is hit. The stop is checked before the
  target inside a bar (the worse case first).
Prices are bid; a buy enters and a sell exits at bid + the bar's spread (costs = the spread, owner 2026-10-20).
Every level trades on its own (overlapping trades allowed): a measurement of the method, not an account.
M5 is built from M1 (the stored M5 starts 2025-10-05). State at the sweep: sweep_sides.py's 24-hour efficiency.

    .venv/Scripts/python research/2026-10-24-replay/reclaim_2025.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sweep_depth import ROOT, SIDE, atr  # noqa: E402
from sweep_sides import states  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

POINT = 0.01  # XAUUSD
CLOSE_BACK = 6
LOOK = 288
HOLD = 24
BUFFERS = (0.5, 1.0, 1.3, 1.8)
TARGETS = (0.5, 0.7, 1.0)


def m5_from_m1(m1: pd.DataFrame) -> pd.DataFrame:
    m1 = m1.assign(t=pd.to_datetime(m1.open_time, utc=True)).drop_duplicates("t", keep="last").set_index("t")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "spread": "median"}
    return m1.sort_index().resample("5min").agg(agg).dropna()


def signals(df: pd.DataFrame) -> pd.DataFrame:
    h, lo, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    a = atr(h, lo, c)
    n, rows = len(df), []
    for i in range(SIDE, n - SIDE):
        for up in (True, False):
            x = h if up else lo
            win = x[i - SIDE : i + SIDE + 1]
            if not (x[i] == (win.max() if up else win.min()) and (win == x[i]).sum() == 1):
                continue
            level, known, sign = x[i], i + SIDE, 1.0 if up else -1.0
            j = next(
                (k for k in range(known + 1, min(n, known + 1 + LOOK)) if (x[k] - level) * sign > 0), None
            )
            if j is None or np.isnan(a[j - 1]):
                continue
            back = next((k for k in range(j, min(n, j + CLOSE_BACK)) if (c[k] - level) * sign < 0), None)
            if back is None or back + 1 >= n:
                continue
            ext = x[j : back + 1].max() if up else x[j : back + 1].min()
            rows.append({"j": j, "k": back, "up": up, "ext": ext, "atr": a[j - 1]})
    return pd.DataFrame(rows)


def trade(df: pd.DataFrame, s: pd.Series, buffer: float, target_r: float) -> float:
    """R after the spread of one reclaim trade."""
    h, lo, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    spr = df.spread.to_numpy(float) * POINT
    k, sell = int(s.k), bool(s.up)
    if sell:
        entry = c[k]
        stop = s.ext + buffer * s.atr
        risk = stop - entry
        tp = entry - target_r * risk
    else:
        entry = c[k] + spr[k]
        stop = s.ext - buffer * s.atr
        risk = entry - stop
        tp = entry + target_r * risk
    if risk <= 0:
        return np.nan
    last = min(len(df) - 1, k + HOLD)
    for b in range(k + 1, last + 1):
        if sell:
            if h[b] + spr[b] >= stop:
                return -1.0 - (h[b] + spr[b] - stop) * 0  # a stop fills at the stop (no slippage)
            if lo[b] + spr[b] <= tp:
                return target_r
        else:
            if lo[b] <= stop:
                return -1.0
            if h[b] >= tp:
                return target_r
    out = (entry - (c[last] + spr[last])) if sell else (c[last] - entry)
    return out / risk


def table(df: pd.DataFrame, sig: pd.DataFrame, title: str) -> None:
    print(f"\n== {title}: {len(sig)} reclaims (sweep + M5 close back within 30 min) ==")
    print("side            | buffer ATR | target R | trades | win % | avg R net | sum R")
    for up in (True, False):
        side = "SELL (high swept)" if up else "BUY (low swept)"
        part = sig[sig.up == up]
        for buf in BUFFERS:
            for tr in TARGETS:
                r = np.array([trade(df, s, buf, tr) for s in part.itertuples()])
                r = r[~np.isnan(r)]
                print(
                    f"{side:17s} | {buf:10.1f} | {tr:8.1f} | {len(r):6d} | {(r > 0).mean():5.0%} | "
                    f"{r.mean():+9.3f} | {r.sum():+7.1f}"
                )


def split(df: pd.DataFrame, sig: pd.DataFrame, buf: float, tr: float, title: str) -> None:
    r = np.array([trade(df, s, buf, tr) for s in sig.itertuples()])
    sig = sig.assign(r=r).dropna(subset=["r"])
    print(f"\n-- {title}: buffer {buf} ATR, target {tr} R, by state and by month --")
    print("state      | side | trades | win % | avg R net")
    for state in ("trend up", "trend down", "sideways"):
        for up in (True, False):
            e = sig[(sig.state == state) & (sig.up == up)]
            if len(e):
                print(
                    f"{state:10s} | {'SELL' if up else 'BUY ':4s} | {len(e):6d} | {(e.r > 0).mean():5.0%} | "
                    f"{e.r.mean():+.3f}"
                )
    print("month   | SELL trades / avg R | BUY trades / avg R")
    sig = sig.assign(m=pd.DatetimeIndex(sig.t).strftime("%Y-%m"))
    for m, g in sig.groupby("m"):
        s, b = g[g.up], g[~g.up]
        print(f"{m} | {len(s):5d} / {s.r.mean():+.3f}      | {len(b):5d} / {b.r.mean():+.3f}")


def main() -> None:
    m1 = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None)
    m5 = m5_from_m1(m1)
    for title, part in (
        (
            "2025-01-01 .. 2025-12-31 (before the exam)",
            m5[(m5.index >= "2024-12-31") & (m5.index < "2026-01-01")],
        ),
        ("the replay months 2026-07-01 .. (information only)", m5[m5.index >= "2026-06-30"]),
    ):
        sig = signals(part)
        sig = sig.assign(t=part.index[sig.j.to_numpy()])
        sig = sig[sig.t >= part.index[0] + pd.Timedelta(days=1)]
        sig = sig.assign(state=states(part, pd.DatetimeIndex(sig.t)))
        sig = sig[sig.state != "?"].reset_index(drop=True)
        table(part, sig, title)
        split(part, sig, 1.0, 0.7, title)


if __name__ == "__main__":
    main()
