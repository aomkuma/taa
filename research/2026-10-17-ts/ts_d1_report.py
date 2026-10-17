"""TS-d1 month by month (data/backtests/ts/d1): trades, win %, R/trade, sum R, net, each cross-checked against
summary.json; running totals per year and over both years."""

import csv
import json
import os
import re

OUT = "data/backtests/ts/d1"
MONTHS = [f"{y}-{m:02d}" for y, m in [(2024, 10), (2024, 11), (2024, 12)] + [(2025, i) for i in range(1, 13)]
          + [(2026, i) for i in range(1, 10)]]
rows, allr = [], {"OOS 2024-10..2025-09": [], "In-sample 2025-10..2026-09": []}
print("| Month | Status | Trades (buy/sell) | Win % | R/trade | Sum R | Net |")
print("|---|---|---|---|---|---|---|")
for m in MONTHS:
    folder, log = os.path.join(OUT, m), os.path.join(OUT, m + ".log")
    if not os.path.exists(os.path.join(folder, "summary.json")):
        status = "waiting"
        if os.path.exists(log):
            hits = re.findall(r"^\s+([\d.]+)%", open(log, encoding="utf-8", errors="replace").read(), re.M)
            status = f"running {hits[-1]} %" if hits else ("FAILED" if "Error" in open(log, encoding="utf-8", errors="replace").read() else "starting")
        print(f"| {m} | {status} | | | | | |")
        continue
    met = json.load(open(os.path.join(folder, "summary.json"), encoding="utf-8"))["metrics"]
    t = list(csv.DictReader(open(os.path.join(folder, "trades.csv"), encoding="utf-8")))
    rs = [float(x["r_multiple"]) for x in t]
    net = sum(float(x["net"]) for x in t)
    assert len(t) == met["trades"] and abs(net - met["net_profit"]) < 0.01, m
    key = "OOS 2024-10..2025-09" if m < "2025-10" else "In-sample 2025-10..2026-09"
    allr[key] += rs
    n = len(rs)
    sides = f"{sum(x['side'] == 'BUY' for x in t)}/{sum(x['side'] == 'SELL' for x in t)}"
    win = f"{100 * sum(r > 0 for r in rs) / n:.0f}" if n else "-"
    avg = f"{sum(rs) / n:+.3f}" if n else "-"
    print(f"| {m} | done | {n} ({sides}) | {win} | {avg} | {sum(rs):+.2f} | {net:+,.2f} |")
for k, rs in allr.items():
    if rs:
        print(f"| **{k}** | {sum(1 for _ in rs)} trades | | {100 * sum(r > 0 for r in rs) / len(rs):.0f} | **{sum(rs) / len(rs):+.3f}** | {sum(rs):+.2f} | |")
both = allr["OOS 2024-10..2025-09"] + allr["In-sample 2025-10..2026-09"]
if both:
    print(f"| **Both years** | {len(both)} trades | | {100 * sum(r > 0 for r in both) / len(both):.0f} | **{sum(both) / len(both):+.3f}** | {sum(both):+.2f} | |")
