"""Join the trades of consecutive backtest periods of one setup into one folder per world (e.g. a year from
three 4-month runs). Tickets are prefixed with the period so they stay unique.

    .venv/Scripts/python research/2026-10-11-pre-run/combine_periods.py setup_harmonic_prz 1y 4mA 4mB 4m
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("data/backtests/inv")


def main(setup: str, label: str, periods: list[str]) -> None:
    for name in (setup, f"{setup}_inverted"):
        frames = []
        for period in periods:
            t = pd.read_csv(ROOT / f"{name}_{period}" / "trades.csv")
            t["ticket"] = period + "-" + t["ticket"].astype(str)
            frames.append(t)
        out = ROOT / f"{name}_{label}"
        out.mkdir(exist_ok=True)
        joined = pd.concat(frames, ignore_index=True).sort_values("entry_time")
        joined.to_csv(out / "trades.csv", index=False)
        print(f"{out}: {len(joined)} trades from {', '.join(periods)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
