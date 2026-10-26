"""How far gold runs past a liquidity level before it comes back (a fake break) or goes on (a real break) - owner
2026-10-24: "measure how far gold likes to sweep past the liquidation zone, in USD or percent"; "there must be
statistics of fake break vs real turn".

Levels: the confirmed M5 swing highs / lows (a high over the 3 bars on each side; it becomes known 3 bars later)
- where the stops of the trades against them sit. A level is BROKEN at the first later bar (within one day) that
trades past it. From that bar on:
- FAKE: an M5 close back on the near side within CLOSE_BACK bars (30 minutes); its depth = the farthest price
  past the level up to that close;
- REAL: no close back within CLOSE_BACK bars; its depth by then is recorded too (the same 30 minutes), and its run
  over two hours.
Depth in USD, in percent of the price and in M5 ATR(14) at the break. Bars only (M5), closed bars, no look-ahead
in the level (a swing is used only after it is confirmed).

The design data: the twelve months before the exam (2025-04-18 .. 2026-04-17, owner 2026-10-18); the replay
months (2026-07 ..) printed apart, for information only.

    .venv/Scripts/python research/2026-10-24-replay/sweep_depth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

SIDE = 3  # bars each side of a swing
CLOSE_BACK = 6  # M5 bars (30 minutes) for a close back on the near side
LOOK = 288  # a level waits at most one day for its break
RUN = 24  # two hours: a real break's run


def atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(np.abs(h - prev), np.abs(lo - prev)))
    return pd.Series(tr).rolling(n).mean().to_numpy()


def events(df: pd.DataFrame) -> pd.DataFrame:
    h, lo, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    a = atr(h, lo, c)
    n = len(df)
    rows = []
    for i in range(SIDE, n - SIDE):
        for up in (True, False):
            x = h if up else lo
            win = x[i - SIDE : i + SIDE + 1]
            if not (x[i] == (win.max() if up else win.min()) and (win == x[i]).sum() == 1):
                continue
            level, known = x[i], i + SIDE  # usable from the bar after the confirmation
            sign = 1.0 if up else -1.0
            j = next(
                (k for k in range(known + 1, min(n, known + 1 + LOOK)) if (x[k] - level) * sign > 0), None
            )
            if j is None or np.isnan(a[j - 1]):
                continue
            end = min(n, j + CLOSE_BACK)
            back = next((k for k in range(j, end) if (c[k] - level) * sign < 0), None)
            stop = (back + 1) if back is not None else end
            ext = x[j:stop].max() if up else x[j:stop].min()
            depth = (ext - level) * sign
            run_end = min(n, j + RUN)
            run = ((x[j:run_end].max() if up else x[j:run_end].min()) - level) * sign
            rows.append(
                {
                    "t": df.index[j],
                    "side": "high" if up else "low",
                    "level": level,
                    "kind": "fake" if back is not None else "real",
                    "depth": depth,
                    "depth_pct": depth / level * 100,
                    "depth_atr": depth / a[j - 1],
                    "run": run,
                    "atr": a[j - 1],
                }
            )
    return pd.DataFrame(rows)


def summary(ev: pd.DataFrame, title: str) -> None:
    print(f"\n== {title}: {len(ev)} breaks of M5 swing levels ==")
    q = [0.5, 0.75, 0.9, 0.95]
    for kind in ("fake", "real"):
        e = ev[ev.kind == kind]
        if not len(e):
            continue
        usd = e.depth.quantile(q).round(2).tolist()
        pct = e.depth_pct.quantile(q).round(3).tolist()
        at = e.depth_atr.quantile(q).round(2).tolist()
        print(
            f"{kind}: {len(e)} ({len(e) / len(ev):.0%}); depth past the level within 30 min "
            f"(median / 75 / 90 / 95 %): USD {usd} | % of price {pct} | M5 ATR {at}"
        )
    print("chance it is a REAL break once price is this far past the level (M5 ATR):")
    for x in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
        past = ev[ev.depth_atr >= x]
        if len(past):
            print(f"  >= {x:4.2f} ATR: {len(past):5d} breaks, real {(past.kind == 'real').mean():.0%}")
    print("in USD:")
    for x in (0.5, 1, 2, 3, 5, 8):
        past = ev[ev.depth >= x]
        if len(past):
            print(f"  >= {x:3.0f} USD: {len(past):5d} breaks, real {(past.kind == 'real').mean():.0%}")
    print(f"the median M5 ATR in this period: {ev.atr.median():.2f} USD")


def main() -> None:
    m5 = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M5, None, None)
    m5 = (
        m5.assign(t=pd.to_datetime(m5.open_time, utc=True))
        .drop_duplicates("t", keep="last")
        .set_index("t")
        .sort_index()
    )
    design = m5[(m5.index >= "2025-04-18") & (m5.index < "2026-04-18")]
    replay = m5[m5.index >= "2026-07-01"]
    summary(events(design), "design: 2025-04-18 .. 2026-04-17 (before the exam)")
    summary(events(replay), "the replay months 2026-07-01 .. (information only)")


if __name__ == "__main__":
    main()
