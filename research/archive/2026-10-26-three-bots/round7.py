"""How deep the pullback may be before the trend bots take it (owner 2026-10-27: "gold's Fibonacci has to be
deeper than that - the 23 and 88 levels").

The measured band is 38.2-78.6 %. This widens it both ways on the same 12 months, one bot at a time, with
everything else unchanged.

    .venv/Scripts/python research/2026-10-26-three-bots/round7.py
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
from audit import BEST, load  # noqa: E402

BANDS = [
    (0.382, 0.786),  # the measured band, for comparison
    (0.236, 0.886),  # the owner's: 23 and 88
    (0.382, 0.886),  # deeper only at the far end
    (0.236, 0.786),  # deeper only at the near end
    (0.5, 0.886),
    (0.618, 0.886),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    f = load()
    exits = {"DOWN": {"exit_mode": "tp"}, "UP": {"exit_mode": "be", "be_at": 0.5}}
    print("| bot | retrace band | trades | win % | R / trade | total R | weeks + / - |")
    print("|---|---|---|---|---|---|---|")
    for bot in ("DOWN", "UP"):
        for band in BANDS:
            p = replace(BEST[bot], retrace=band, **exits[bot])
            tr = bots.run(f, p)
            if not tr:
                print(f"| {bot} | {band[0]:.3f}-{band[1]:.3f} | 0 | - | - | - | - |")
                continue
            d = pd.DataFrame([{"at": t.at, "r": t.r} for t in tr])
            wk = d.groupby(d["at"].dt.tz_convert(bots.TH).dt.tz_localize(None).dt.to_period("W")).r.sum()
            mark = "  <- measured" if band == (0.382, 0.786) else ""
            print(f"| {bot} | {band[0]:.3f}-{band[1]:.3f} | {len(d)} | {(d.r > 0).mean():.0%} | "
                  f"{d.r.mean():+.3f} | {d.r.sum():+.1f} | {int((wk > 0).sum())} / {int((wk <= 0).sum())} |{mark}")  # fmt: skip


if __name__ == "__main__":
    main()
