"""How deep a pullback goes before it is a real reversal, per timeframe (owner 2026-10-26: "research, on M5,
M15, M30, H1 and H4, how many percent price runs before it really turns").

On each frame:
- swing points: MetaTrader 5's ZigZag (12, 5, 3), the one on the owner's chart (a first try with 3-bar
  fractals caught only noise: the median pullback was 96 % of the leg);
- a leg A -> B between two swing points, and the counter swing B -> C; its depth = |C - B| / |B - A| in %;
- what came first after C: a swing beyond B (the leg went on: a pullback) or beyond A (the whole leg was undone:
  a real reversal). A counter swing already beyond A (depth over 100 %) is a reversal by itself;
- the counts per depth band, the share that turned, the median leg in USD, and the depth from which the turns
  outnumber the continuations.

The 12 months before the exam: 2025-04-18 .. 2026-04-17 (nothing from the exam months).

    .venv/Scripts/python research/2026-10-24-replay/retrace_depth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.zigzag import zigzag as mt5_zigzag  # noqa: E402

START, END = pd.Timestamp("2025-04-18", tz="UTC"), pd.Timestamp("2026-04-18", tz="UTC")
BANDS = [0, 23.6, 38.2, 50.0, 61.8, 78.6, 100.0, 1e9]


def zigzag(h: np.ndarray, lo: np.ndarray) -> list[tuple[int, float, int]]:
    """The confirmed swings of MetaTrader 5's ZigZag (12, 5, 3) as (bar, price, kind): app/strategy/zigzag.py."""
    return [(s.bar, s.price, s.kind) for s in mt5_zigzag(h, lo)[0]]


def legs(sw: list[tuple[int, float, int]]) -> pd.DataFrame:
    rows = []
    for j in range(1, len(sw) - 1):
        a, b, c = sw[j - 1][1], sw[j][1], sw[j + 1][1]
        up = sw[j][2] == 1  # the leg A -> B went up
        size = abs(b - a)
        if size <= 0:
            continue
        depth = abs(c - b) / size * 100
        outcome = None
        if (c < a) if up else (c > a):
            outcome = "turn"
        else:
            for _, p, kind in sw[j + 2 :]:
                if kind == sw[j][2] and ((p > b) if up else (p < b)):
                    outcome = "on"
                    break
                if kind != sw[j][2] and ((p < a) if up else (p > a)):
                    outcome = "turn"
                    break
        if outcome:
            rows.append({"size": size, "depth": depth, "outcome": outcome})
    return pd.DataFrame(rows)


def frame(f: dict, tf: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if tf == "M5":
        x = f[Timeframe.M1].resample("5min").agg(agg).dropna()
    elif tf == "M30":
        x = f[Timeframe.M15].resample("30min").agg(agg).dropna()
    else:
        x = f[{"M15": Timeframe.M15, "H1": Timeframe.H1, "H4": Timeframe.H4}[tf]]
    return x[(x.index >= START) & (x.index < END)]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(ROOT / "data/history")
    tfs = (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.H4)
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in tfs}
    labels = [f"{BANDS[i]:g}-{BANDS[i + 1]:g} %" if BANDS[i + 1] < 1e9 else "over 100 %" for i in range(len(BANDS) - 1)]
    for tf in ("M5", "M15", "M30", "H1", "H4"):
        x = frame(f, tf)
        df = legs(zigzag(x.high.to_numpy(float), x.low.to_numpy(float)))
        df["band"] = pd.cut(df.depth, BANDS, labels=labels, right=False)
        print(f"\n== {tf}: {len(x)} bars, {len(df)} legs judged; median leg {df['size'].median():.1f} USD; "
              f"median pullback depth {df.depth.median():.1f} % ==")
        print("| pullback depth (of the leg before) | legs | went on | turned | turned % |")
        print("|---|---|---|---|---|")
        cross = None
        for lab in labels:
            g = df[df.band == lab]
            if not len(g):
                continue
            turned = (g.outcome == "turn").mean()
            if cross is None and lab != "over 100 %" and turned > 0.5:
                cross = lab
            print(f"| {lab} | {len(g)} | {(g.outcome == 'on').sum()} | {(g.outcome == 'turn').sum()} | {turned:.0%} |")
        # the cumulative view: once a pullback has reached X %, how often does it end as a turn
        print("| reached at least | legs | turned % |")
        print("|---|---|---|")
        for lv in (23.6, 38.2, 50.0, 61.8, 78.6, 100.0):
            g = df[df.depth >= lv]
            print(f"| {lv:g} % | {len(g)} | {(g.outcome == 'turn').mean():.0%} |")
        print(f"- turns outnumber continuations from the band: {cross or 'none below 100 %'}")


if __name__ == "__main__":
    main()
