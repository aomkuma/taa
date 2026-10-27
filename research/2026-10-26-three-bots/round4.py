"""A real exit instead of "the test stopped here" (the Thai day's end carried 29-48 % of each bot's gross R).

Every exit policy of bots.P run on all three bots side by side; the entries are unchanged, only how a trade
ends. Owner 2026-10-26: holding hours, even overnight, is fine as long as it pays.

    .venv/Scripts/python research/2026-10-26-three-bots/round4.py
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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    f = load()
    print("| exit | trades | win % | R / trade | total R | median hold | R from the day's end |")
    print("|---|---|---|---|---|---|---|")
    for label, over in [
        ("stop and take-profit only (baseline)", {"exit_mode": "tp"}),
        ("break-even at +1 R", {"exit_mode": "be", "be_at": 1.0}),
        ("break-even at +0.5 R", {"exit_mode": "be", "be_at": 0.5}),
        ("trail 30 min after +1 R", {"exit_mode": "trail", "be_at": 1.0, "trail_min": 30}),
        ("trail 60 min after +1 R", {"exit_mode": "trail", "be_at": 1.0, "trail_min": 60}),
        ("trail 120 min after +1 R", {"exit_mode": "trail", "be_at": 1.0, "trail_min": 120}),
        ("3 M5 closes back across the entry", {"exit_mode": "struct", "struct_bars": 3}),
    ]:
        rows = []
        for name, p in BEST.items():
            for t in bots.run(f, replace(p, **over)):
                rows.append({"bot": name, "r": t.r, "out": t.out, "at": t.at, "closed": t.extra["closed"]})
        d = pd.DataFrame(rows)
        d["h"] = (pd.to_datetime(d["closed"]) - pd.to_datetime(d["at"])).dt.total_seconds() / 3600
        eod = d[d.out == "eod"].r.sum()
        print(f"| {label} | {len(d)} | {(d.r > 0).mean():.0%} | {d.r.mean():+.3f} | {d.r.sum():+.1f} | "
              f"{d.h.median():.1f} h | {eod:+.1f} |")


if __name__ == "__main__":
    main()
