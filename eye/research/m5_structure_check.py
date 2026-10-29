"""The M5 structure at each decision of a ledger, against the trade's side, and the same for every decision
bar.

The owner, 2026-10-30: a win rate this low means the bot trades against the market on M5 - find where. At
each filled decision: the latest two fixed M5 HIGHs and LOWs (fixed by the decision, closed bars): higher
high and higher low = UP, lower high and lower low = DOWN, otherwise MIXED. A BUY in an M5 DOWN (or a SELL
in an UP) is against the M5 trend. Usage: m5_structure_check.py <ledger.csv> [<ledger.csv> ...]"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e  # noqa: E402


def structure(piv: list) -> tuple[str, str]:
    hs = [p for p in piv if p.kind.value == "HIGH"][-2:]
    ls = [p for p in piv if p.kind.value == "LOW"][-2:]
    if len(hs) < 2 or len(ls) < 2:
        return "MIXED", ""
    up = hs[1].price > hs[0].price and ls[1].price > ls[0].price
    dn = hs[1].price < hs[0].price and ls[1].price < ls[0].price
    text = f"H {hs[0].price:.2f}->{hs[1].price:.2f}, L {ls[0].price:.2f}->{ls[1].price:.2f}"
    return ("UP" if up else "DOWN" if dn else "MIXED"), text


def main(paths: list[str]) -> None:
    m5 = bot2e.load_frames()["M5"]
    tally: dict[str, list[float]] = {}
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            led = list(csv.DictReader(fh))
        for r in led:
            if not r["fill"]:
                continue
            now = pd.Timestamp(f"{r['cutoff_thai'][:10]} {r['decided_at'][-5:]}", tz=bot2e.TH).tz_convert(
                "UTC"
            )
            f = bot2e.cut({"M5": m5}, now + pd.Timedelta(minutes=5))["M5"].tail(bot2e.FIB_BARS)
            st, text = structure(bot2e._zigzag(f))
            want = "UP" if r["side"] == "BUY" else "DOWN"
            rel = "with" if st == want else "MIXED" if st == "MIXED" else "against"
            tally.setdefault(rel, []).append(float(r["r_net"]))
            print(
                f"{Path(path).parent.name:13} {r['id']} {r['side']:4} R {float(r['r_net']):+.2f}"
                f"  M5 {st:5} ({text}) - {rel}"
            )
    for rel, rs in tally.items():
        print(f"{rel:8}: {len(rs)} fills, {sum(x > 0 for x in rs)} won, R {sum(rs):+.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
