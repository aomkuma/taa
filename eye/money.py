"""The record in money: every trade of both ledgers, in date order, on a real account balance.

The owner, 2026-10-28: *"make it simple - think from a 200 USD account and work it out in money."* R hides the
size of the stop; money does not. On gold, 0.01 lot is 1 oz, so a 1.00 move is 1 USD - a trade's result is
its R (already net of the 0.30 spread) times its stop distance times the ounces.

    python eye/money.py                 # 200 USD, 0.01 lot
    python eye/money.py 200 0.02        # another balance or lot
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OZ_PER_LOT = 100  # gold: 1.00 lot = 100 oz, so 0.01 lot = 1 oz = 1 USD per 1.00 of price


def when(r: dict[str, str]) -> pd.Timestamp:
    return pd.Timestamp(r["cutoff_thai"][:10])


def main() -> None:
    balance = float(sys.argv[1]) if len(sys.argv) > 1 else 200.0
    lot = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    oz = lot * OZ_PER_LOT
    rows = []
    for name in ("ledger_control.csv", "ledger.csv"):
        for r in csv.DictReader((HERE / name).open(encoding="utf-8")):
            if r["side"] in ("BUY", "SELL"):
                rows.append(r)
    rows.sort(key=when)

    start, peak, worst_dd, streak, worst_streak = balance, balance, 0.0, 0, 0
    print(
        f"start {balance:.2f} USD, {lot:.2f} lot ({oz:g} oz: 1.00 of price = {oz:g} USD), spread included\n"
    )
    print(f"{'#':>5} {'date':10} {'side':4} {'stop USD':>8} {'result':>26} {'USD':>8} {'balance':>8}")
    for r in rows:
        risk = abs(float(r["entry"]) - float(r["stop"])) * oz
        why = r["why"] or "not scored"
        usd = float(r["r_net"]) * risk if r["r_net"] and not why.startswith("no fill") else 0.0
        balance += usd
        peak = max(peak, balance)
        worst_dd = max(worst_dd, peak - balance)
        if usd:  # a plan that never filled is not a trade: it neither extends nor ends a losing run
            streak = streak + 1 if usd < 0 else 0
        worst_streak = max(worst_streak, streak)
        print(
            f"{r['id']:>5} {r['cutoff_thai'][:10]} {r['side']:4} {risk:8.2f} {why[:26]:>26} "
            f"{usd:+8.2f} {balance:8.2f}"
        )
    print(
        f"\nend {balance:.2f} USD ({balance - start:+.2f}, {(balance - start) / start:+.1%}); "
        f"deepest fall from a high {worst_dd:.2f} USD; most losses in a row {worst_streak}"
    )


if __name__ == "__main__":
    main()
