"""The three bots on data their parameters never saw (the prediction in PREDICTION.md).

Same bots, same parameters, same exits, same gates as round6 - only the dates change: 2023-09-01 ..
2025-10-19, the stored history before the fitted year.

    .venv/Scripts/python research/2026-10-26-three-bots/unseen.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bots  # noqa: E402
from audit import BEST  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

CHOSEN = {"DOWN": {"exit_mode": "tp"}, "UP": {"exit_mode": "be", "be_at": 0.5},
          "RANGE": {"exit_mode": "be", "be_at": 0.5}}  # fmt: skip
PERIODS = {
    "unseen 2023-09 .. 2024-09": ("2023-09-05", "2024-09-30"),
    "unseen 2024-10 .. 2025-10": ("2024-10-01", "2025-10-19"),
    "fitted 2025-10 .. 2026-10": ("2025-10-20", "2026-10-23"),
}


def show(df: pd.DataFrame, title: str) -> None:
    if not len(df):
        print(f"| {title} | - | 0 | - | - | - |")
        return
    eq = df.sort_values("at").r.cumsum()
    dd = (eq - eq.cummax()).min()
    for bot, g in df.groupby("bot"):
        print(
            f"| {title} | {bot} | {len(g)} | {(g.r > 0).mean():.0%} | {g.r.mean():+.3f} | {g.r.sum():+.1f} |"
        )
    print(f"| {title} | **ALL** | {len(df)} | {(df.r > 0).mean():.0%} | **{df.r.mean():+.3f}** | "
          f"{df.r.sum():+.1f} (worst drawdown {dd:.1f} R) |")  # fmt: skip


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    f = {}
    for tf in (Timeframe.M1, Timeframe.H1):
        f[tf] = to_frame(hs.load("FBS-Demo", "XAUUSD", tf, None, None))
    print("| period | bot | trades | win % | R / trade | total R |")
    print("|---|---|---|---|---|---|")
    for title, (s, e) in PERIODS.items():
        rows = []
        for name, p in BEST.items():
            for t in bots.run(f, replace(p, **CHOSEN[name]),
                              pd.Timestamp(s, tz="UTC"), pd.Timestamp(e, tz="UTC")):  # fmt: skip
                rows.append({"bot": name, "r": t.r, "at": t.at})
        show(pd.DataFrame(rows), title)


if __name__ == "__main__":
    main()
