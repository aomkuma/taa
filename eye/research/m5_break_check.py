"""At each filled decision of a ledger: had price broken the counter-leg's last M5 swing before the decision?

The owner, 2026-10-30: "find the trend on M5 - a win rate this low means trading against the market on M5".
For a BUY the counter-leg falls from H100 to L0; its last M5 HIGH before L0 (the last lower high of the
fall) is the structure to break: if no M5 high after L0's bar and up to the decision went above it, M5 was
still falling - the buy was against the M5 trend. A SELL is the mirror (the last M5 LOW before the top).
Closed bars, M5 pivots fixed at the decision, as the bot sees them. Usage: m5_break_check.py
eye/research/r11_lean_off/ledger.csv"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e  # noqa: E402

LEG = re.compile(
    r"Leg: L0 ([\d.]+)@(\d\d)/(\d\d) (\d\d:\d\d) \(0 %\), H100 ([\d.]+)@(\d\d)/(\d\d) (\d\d:\d\d)"
)


def main(path: str) -> None:
    full = bot2e.load_frames()
    m5 = full["M5"]
    with open(path, encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["fill"]]
    out = []
    for r in rows:
        m = LEG.search(r["structure"])
        if not m:
            continue
        year = r["cutoff_thai"][:4]
        t0 = pd.Timestamp(f"{year}-{m[3]}-{m[2]} {m[4]}", tz=bot2e.TH).tz_convert("UTC")
        now = pd.Timestamp(f"{r['cutoff_thai'][:10]} {r['decided_at'][-5:]}", tz=bot2e.TH).tz_convert("UTC")
        now += pd.Timedelta(minutes=5)
        f = bot2e.cut({"M5": m5}, now)["M5"].tail(bot2e.FIB_BARS)
        piv = bot2e._zigzag(f)
        buy = r["side"] == "BUY"
        want = "HIGH" if buy else "LOW"
        before = [p for p in piv if p.kind.value == want and pd.Timestamp(p.pivot_at) < t0]
        if not before:
            continue
        ref = before[-1]
        after = f[(f.index > t0) & (f.index + pd.Timedelta(minutes=5) <= now)]
        broke = bool((after.high > ref.price).any()) if buy else bool((after.low < ref.price).any())
        out.append((r["id"], r["side"], float(r["r_net"]), ref.price, pd.Timestamp(ref.pivot_at), broke))
    for o in out:
        print(
            f"{o[0]} {o[1]:4} R {o[2]:+.2f}  last swing {o[3]:.2f}@{o[4].tz_convert(bot2e.TH):%d/%m %H:%M}"
            f"  broken before the decision: {o[5]}"
        )
    for flag in (True, False):
        g = [o for o in out if o[5] == flag]
        if g:
            won = sum(o[2] > 0 for o in g)
            print(f"broken={flag}: {len(g)} fills, {won} won, R {sum(o[2] for o in g):+.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
