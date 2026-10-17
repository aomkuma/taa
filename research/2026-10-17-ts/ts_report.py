"""TS run table: every run of data/backtests/ts, cross-checked (trades.csv against summary.json)."""

import csv
import json
import os
import re
import sys

OUT = "data/backtests/ts"
ORDER = [f"ts_{v}_{tf}" for v in ("w", "r", "rs", "rn", "rt", "n3", "n3a", "n3c") for tf in ("m15", "m5")]


def row(name: str) -> str:
    folder, log = os.path.join(OUT, name), os.path.join(OUT, name + ".log")
    summary = os.path.join(folder, "summary.json")
    if not os.path.exists(summary):
        pct = ""
        if os.path.exists(log):
            hits = re.findall(r"^\s+([\d.]+)%", open(log, encoding="utf-8", errors="replace").read(), re.M)
            pct = f"{hits[-1]} %" if hits else "starting"
        return f"| {name} | {'running ' + pct if os.path.exists(log) else 'waiting'} | | | | | | |"
    m = json.load(open(summary, encoding="utf-8"))["metrics"]
    trades = list(csv.DictReader(open(os.path.join(folder, "trades.csv"), encoding="utf-8")))
    net = sum(float(t["net"]) for t in trades)
    rs = [float(t["r_multiple"]) for t in trades]
    if len(trades) != m["trades"] or abs(net - m["net_profit"]) > 0.01:
        return f"| {name} | MISMATCH csv {len(trades)} / {net:.2f} vs summary {m['trades']} / {m['net_profit']:.2f} |"
    n = len(rs)
    r_avg = sum(rs) / n if n else 0.0
    sides = f"{sum(t['side'] == 'BUY' for t in trades)}/{sum(t['side'] == 'SELL' for t in trades)}"
    goal = "✓" if n and r_avg >= 0.15 else "✗"
    win = f"{100 * sum(r > 0 for r in rs) / n:.0f}" if n else "-"
    return f"| {name} | done | {n} ({sides}) | {win} | {r_avg:+.3f} | {sum(rs):+.2f} | {net:+,.2f} | {goal} |"


tag = sys.argv[1] if len(sys.argv) > 1 else "2026-03"
runs = sys.argv[2:] or [v for v in ORDER if os.path.exists(os.path.join(OUT, f"{v}_{tag}.log"))]
print("| Run | Status | Trades (buy/sell) | Win % | R/trade | Sum R | Net | ≥ +0.15 |")
print("|---|---|---|---|---|---|---|---|")
for v in runs:
    print(row(f"{v}_{tag}"))
