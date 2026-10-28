"""Does the breakout signal carry information? Compare it with the same trades taken the other way (fade) and in
a random direction, same entry time, same stop and target distances, same costs (read-only, hypothetical)."""

import random
import statistics
import sys
from collections import defaultdict

sys.argv = sys.argv[:1]
exec(open(__file__.replace("baseline_breakout.py", "diagnose_breakout.py"), encoding="utf-8").read().split(
    'print("\\n=== 1. timing')[0])

random.seed(11)


def mirrored(tr: dict) -> dict:
    sp = (tr["spread"] or 0) * point[tr["symbol"]]
    sign = 1 if tr["side"] == "BUY" else -1
    entry = tr["entry"] - sign * sp  # the other side of the spread
    m = dict(tr)
    m["side"] = "SELL" if sign > 0 else "BUY"
    m["entry"] = entry
    m["sl"] = entry + sign * abs(tr["entry"] - tr["sl"])
    m["tp"] = entry - sign * abs(tr["tp"] - tr["entry"])
    return m


def report(label: str, results: list[tuple[dict, float]]) -> None:
    values = [r for _, r in results]
    means = sorted(statistics.fmean(random.choices(values, k=len(values))) for _ in range(1000))
    print(f"{label:28} n={len(values)} win {100 * sum(v > 0 for v in values) / len(values):3.0f}% "
          f"meanR {statistics.fmean(values):+.3f} 90%CI[{means[50]:+.2f},{means[949]:+.2f}]")
    halves, symbols = defaultdict(list), defaultdict(list)
    for tr, r in results:
        halves["Oct-Mar" if str(tr["t"]) < "2026-04-01" else "Apr-Oct"].append(r)
        symbols[tr["symbol"]].append(r)
    print("    " + "  ".join(f"{k} {statistics.fmean(v):+.3f}/{len(v)}" for k, v in sorted(halves.items())))
    print("    " + "  ".join(f"{k} {statistics.fmean(v):+.3f}" for k, v in sorted(symbols.items())))


as_is, fade, coin = [], [], []
for tr in trades:
    r = simulate(tr, None, 0)
    m = mirrored(tr)
    f = simulate(m, None, 0)
    if r is None or f is None:
        continue
    as_is.append((tr, r))
    fade.append((tr, f))
    coin.append((tr, r if random.random() < 0.5 else f))
print("\n=== information in the breakout direction (market entry, same geometry and costs) ===")
report("breakout as traded", as_is)
report("fade (the other way)", fade)
report("random direction", coin)
