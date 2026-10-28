"""The pullback depth that turns, split by volatility (owner 2026-10-26: "you still need ATR with everything else:
when ATR is very strong price can fake far; when ATR falls while price keeps going one way, it may be a real
trend").

The same ZigZag legs as retrace_depth.py (MetaTrader 5's ZigZag 12/5/3, 2025-04-18 .. 2026-04-17), each with:
- the ATR level at the leg's end B: the frame's ATR(14) (MetaTrader 5's: the simple mean of 14 true ranges)
  against its median of the 100 bars before - HIGH over 1.25 x, LOW under 0.8 x, else NORMAL;
- the ATR's direction over the leg: ATR at B / ATR at A - FALLING under 0.9, RISING over 1.1, else FLAT;
- the outcome: the leg undone (price beyond A) before it went on (beyond B) = a turn.

    .venv/Scripts/python research/2026-10-24-replay/retrace_atr.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from retrace_depth import frame, zigzag  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402


def atr14(x: pd.DataFrame) -> np.ndarray:
    h, lo, c = (x[k].to_numpy(float) for k in ("high", "low", "close"))
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(abs(h - prev), abs(lo - prev)))
    return pd.Series(tr).rolling(14).mean().to_numpy()


def legs(x: pd.DataFrame) -> pd.DataFrame:
    sw = zigzag(x.high.to_numpy(float), x.low.to_numpy(float))
    a14 = atr14(x)
    med = pd.Series(a14).rolling(100).median().shift(1).to_numpy()
    rows = []
    for j in range(1, len(sw) - 1):
        (ia, a, _), (ib, b, kb), (_, c, _) = sw[j - 1], sw[j], sw[j + 1]
        up, size = kb == 1, abs(b - a)
        if size <= 0 or np.isnan(med[ib]) or np.isnan(a14[ia]):
            continue
        outcome = None
        if (c < a) if up else (c > a):
            outcome = "turn"
        else:
            for _, p, kind in sw[j + 2 :]:
                if kind == kb and ((p > b) if up else (p < b)):
                    outcome = "on"
                    break
                if kind != kb and ((p < a) if up else (p > a)):
                    outcome = "turn"
                    break
        if outcome is None:
            continue
        lvl = a14[ib] / med[ib]
        slope = a14[ib] / a14[ia]
        rows.append({
            "depth": abs(c - b) / size * 100, "turn": outcome == "turn",
            "level": "HIGH" if lvl > 1.25 else "LOW" if lvl < 0.8 else "NORMAL",
            "slope": "FALLING" if slope < 0.9 else "RISING" if slope > 1.1 else "FLAT",
        })  # fmt: skip
    return pd.DataFrame(rows)


def table(df: pd.DataFrame, by: str, groups: tuple[str, ...]) -> None:
    print(f"| ATR {by} at the leg | legs | legs undone % | median pullback % | reached 38.2 -> turned | "
          "reached 61.8 -> turned | reached 78.6 -> turned | ended 50-78.6 % -> went on |")
    print("|---|---|---|---|---|---|---|---|")
    for g in groups:
        d = df[df[by] == g]
        if not len(d):
            continue

        def turned(lv: float, d: pd.DataFrame = d) -> str:
            x = d[d.depth >= lv]
            return f"{x.turn.mean():.0%} ({len(x)})" if len(x) else "-"

        mid = d[(d.depth >= 50) & (d.depth < 78.6)]
        on = f"{(~mid.turn).mean():.0%} ({len(mid)})" if len(mid) else "-"
        print(f"| {g} | {len(d)} | {d.turn.mean():.0%} | {d.depth.median():.0f} | {turned(38.2)} | {turned(61.8)} | "
              f"{turned(78.6)} | {on} |")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    tfs = (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.H4)
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in tfs}
    for tf in ("M5", "M15", "M30", "H1", "H4"):
        df = legs(frame(f, tf))
        print(f"\n== {tf}: {len(df)} legs ==")
        table(df, "level", ("HIGH", "NORMAL", "LOW"))
        table(df, "slope", ("FALLING", "FLAT", "RISING"))


if __name__ == "__main__":
    main()
