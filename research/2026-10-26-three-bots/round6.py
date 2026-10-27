"""Each bot its own exit (round 5: break-even at +0.5 R lifted the range bot +0.274 -> +0.488 and cut the trend
bot +0.280 -> +0.094), and the drawdown in R rather than a count of losing trades - most "losses" are
break-even exits costing only the spread.

    .venv/Scripts/python research/2026-10-26-three-bots/round6.py
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

EXITS = {"tp": {"exit_mode": "tp"}, "be0.5": {"exit_mode": "be", "be_at": 0.5},
         "be1.0": {"exit_mode": "be", "be_at": 1.0}}  # fmt: skip


def stats(d: pd.DataFrame) -> str:
    eq = d.sort_values("at").r.cumsum()
    dd = (eq - eq.cummax()).min()
    return (f"{len(d)} | {(d.r > 0).mean():.0%} | {d.r.mean():+.3f} | {d.r.sum():+.1f} | {dd:.1f}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    f = load()
    print("| bot | exit | trades | win % | R / trade | total R | worst drawdown (R) |")
    print("|---|---|---|---|---|---|---|")
    picked: dict[str, dict] = {}
    frames: dict[str, pd.DataFrame] = {}
    for name, p in BEST.items():
        best = None
        for label, over in EXITS.items():
            tr = bots.run(f, replace(p, **over))
            d = pd.DataFrame([{"r": t.r, "at": t.at, "out": t.out, "bot": name} for t in tr])
            print(f"| {name} | {label} | {stats(d)} |")
            if best is None or d.r.mean() > best[0]:
                best = (d.r.mean(), label, over, d)
        picked[name] = best[2]
        frames[name] = best[3]
        print(f"| {name} | **chosen: {best[1]}** | | | | | |")
    d = pd.concat(frames.values()).sort_values("at")
    print(f"\n== all three, each with its own exit ==\n")
    print("| | trades | win % | R / trade | total R | worst drawdown (R) |")
    print("|---|---|---|---|---|---|")
    for bot, g in d.groupby("bot"):
        print(f"| {bot} | {stats(g)} |")
    print(f"| ALL | {stats(d)} |")
    mo = d.groupby(pd.to_datetime(d["at"]).dt.tz_convert(bots.TH).dt.tz_localize(None).dt.to_period("M")).agg(
        n=("r", "size"), r=("r", "sum"))
    print("\n| month | trades | R |")
    print("|---|---|---|")
    for m, row in mo.iterrows():
        print(f"| {m} | {int(row.n)} | {row.r:+.1f} |")
    print(f"\n- chosen exits: " + ", ".join(f"{k}={v}" for k, v in picked.items()))
    print(f"- {len(d)} trades in 12 months = {len(d) / 12:.1f} a month")


if __name__ == "__main__":
    main()
