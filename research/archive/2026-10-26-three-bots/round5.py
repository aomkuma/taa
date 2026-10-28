"""How long to let a trade run: break-even at +0.5 R (the best exit of round 4) with a cap on the hold.

The baseline closes a trade at the Thai day's end, which carried most of the R - a rule only because the test
stopped there. A fixed cap makes the hold the same for every window.

    .venv/Scripts/python research/2026-10-26-three-bots/round5.py
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


def run_all(f: dict, over: dict) -> pd.DataFrame:
    rows = []
    for name, p in BEST.items():
        for t in bots.run(f, replace(p, **over)):
            rows.append({"bot": name, "r": t.r, "out": t.out, "at": t.at, "closed": t.extra["closed"]})
    d = pd.DataFrame(rows)
    d["h"] = (pd.to_datetime(d["closed"]) - pd.to_datetime(d["at"])).dt.total_seconds() / 3600
    return d


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    f = load()
    print(
        "| hold cap (break-even at +0.5 R) | trades | win % | R / trade | total R | median hold | R from the cap |"
    )
    print("|---|---|---|---|---|---|---|")
    best = None
    for cap in (3, 4, 6, 8, 12, 0):
        d = run_all(f, {"exit_mode": "be", "be_at": 0.5, "max_hours": cap})
        label = f"{cap} h" if cap else "none (to the day's end)"
        timed = d[d.out.isin(["time", "eod"])].r.sum()
        print(
            f"| {label} | {len(d)} | {(d.r > 0).mean():.0%} | {d.r.mean():+.3f} | {d.r.sum():+.1f} | "
            f"{d.h.median():.1f} h | {timed:+.1f} |"
        )
        if best is None or d.r.mean() > best[1]:
            best = (cap, d.r.mean(), d)
    cap, _, d = best
    print(f"\n== the chosen cap: {cap or 'day end'} ==")
    print("| bot | trades | win % | R / trade | total R |")
    print("|---|---|---|---|---|")
    for bot, g in d.groupby("bot"):
        print(f"| {bot} | {len(g)} | {(g.r > 0).mean():.0%} | {g.r.mean():+.3f} | {g.r.sum():+.1f} |")
    print(f"| ALL | {len(d)} | {(d.r > 0).mean():.0%} | {d.r.mean():+.3f} | {d.r.sum():+.1f} |")
    print("\n| how it ended | trades | R |")
    print("|---|---|---|")
    for out, g in d.groupby("out"):
        print(f"| {out} | {len(g)} | {g.r.sum():+.1f} |")
    mo = d.groupby(pd.to_datetime(d["at"]).dt.tz_convert(bots.TH).dt.tz_localize(None).dt.to_period("M")).agg(
        n=("r", "size"), r=("r", "sum")
    )
    print("\n| month | trades | R |")
    print("|---|---|---|")
    for m, row in mo.iterrows():
        print(f"| {m} | {int(row.n)} | {row.r:+.1f} |")
    worst = cur = 0
    for r in d.sort_values("at").r:
        cur = cur + 1 if r < 0 else 0
        worst = max(worst, cur)
    print(f"\n- {len(d)} trades in 12 months = {len(d) / 12:.1f} a month; longest losing streak {worst}")


if __name__ == "__main__":
    main()
