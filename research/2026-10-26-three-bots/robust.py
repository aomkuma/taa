"""How much of the result rests on a few trades, and what the drawdown means on the owner's account.

Each bot with its chosen exit: the total with the best trades removed one at a time, the half-year halves, and
the worst drawdown turned into account percent at the owner's risk.

    .venv/Scripts/python research/2026-10-26-three-bots/robust.py
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

CHOSEN = {"DOWN": {"exit_mode": "tp"}, "UP": {"exit_mode": "be", "be_at": 0.5},
          "RANGE": {"exit_mode": "be", "be_at": 0.5}}  # fmt: skip


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    f = load()
    rows = []
    for name, p in BEST.items():
        for t in bots.run(f, replace(p, **CHOSEN[name])):
            rows.append({"bot": name, "r": t.r, "at": t.at, "out": t.out})
    d = pd.DataFrame(rows).sort_values("at").reset_index(drop=True)

    print("== how much rests on the biggest winners ==")
    print("| | trades | R / trade | total R |")
    print("|---|---|---|---|")
    for drop in (0, 1, 3, 5):
        g = d.sort_values("r", ascending=False).iloc[drop:]
        label = "all trades" if not drop else f"without the best {drop}"
        print(f"| {label} | {len(g)} | {g.r.mean():+.3f} | {g.r.sum():+.1f} |")

    print("\n== each half of the year, on its own ==")
    print("| half | trades | win % | R / trade | total R |")
    print("|---|---|---|---|---|")
    mid = pd.Timestamp("2026-04-20", tz="UTC")
    for label, g in (("2025-10 .. 2026-04", d[d["at"] < mid]), ("2026-04 .. 2026-10", d[d["at"] >= mid])):
        print(f"| {label} | {len(g)} | {(g.r > 0).mean():.0%} | {g.r.mean():+.3f} | {g.r.sum():+.1f} |")

    eq = d.r.cumsum()
    dd = (eq - eq.cummax()).min()
    print(f"\n== the account ==")
    print(f"- worst drawdown {dd:.1f} R over the year; total {d.r.sum():+.1f} R from {len(d)} trades")
    for risk in (2.0, 6.0):
        print(f"- at {risk:.0f} % risk a trade: the drawdown is about {dd * risk:.0f} % of the account, "
              f"the year about {d.r.sum() * risk:+.0f} % (simple, not compounded)")
    print(f"- trades a month {len(d) / 12:.1f}; the owner's goal is a trade most days")


if __name__ == "__main__":
    main()
