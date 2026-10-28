"""Setup quality from the one-year replays (PLAN variant shadow trades, net of costs, in R).

- per strategy: n, win %, mean R with a bootstrap 90 % CI, per half-year (stability)
- nearer targets: with a target X R at or below the trade's own, the trade wins X when its MFE reached X
  before it ended, else keeps its actual result (valid only for X <= its own target)
- higher-timeframe alignment (ctx:htf_aligned) split
"""

import glob
import json
import random
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime

S = str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'data' / 'research')
rows = []
import sys
for path in sorted(glob.glob(f"{S}/{sys.argv[1] if len(sys.argv) > 1 else 'fam_*'}.db")):
    if path.endswith("replay_probe.db"):
        continue
    db = sqlite3.connect(path)
    try:
        rows += db.execute(
            "select strategy, symbol, side, signal_at, r_multiple, r_net, mfe_r, mae_r, rr, features, exit_reason "
            "from shadow_trades where status='CLOSED' and variant='PLAN'"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(path, exc)
print(f"closed replay trades: {len(rows)}")
random.seed(7)


def ci(values: list[float]) -> tuple[float, float]:
    if len(values) < 5:
        return (float("nan"), float("nan"))
    means = sorted(statistics.fmean(random.choices(values, k=len(values))) for _ in range(2000))
    return means[100], means[1899]


def line(label: str, values: list[float]) -> str:
    if not values:
        return f"{label:34} n=0"
    lo, hi = ci(values)
    win = 100 * sum(v > 0 for v in values) / len(values)
    return f"{label:34} n={len(values):4d} win={win:4.0f}% meanR={statistics.fmean(values):+.3f} 90%CI[{lo:+.2f},{hi:+.2f}] totalR={sum(values):+.1f}"


by = defaultdict(list)
for r in rows:
    by[r[0]].append(r)

print("\n=== by strategy (actual targets) ===")
for strat, items in sorted(by.items()):
    print(line(strat, [x[5] or 0.0 for x in items]))
    halves = defaultdict(list)
    for x in items:
        t = datetime.fromisoformat(str(x[3])[:19])
        halves["H1 Oct-Mar" if t < datetime(2026, 4, 1) else "H2 Apr-Oct"].append(x[5] or 0.0)
    for h in sorted(halves):
        print("   " + line(h, halves[h]))
    by_symbol = defaultdict(list)
    for x in items:
        by_symbol[x[1]].append(x[5] or 0.0)
    print("   symbols: " + ", ".join(f"{s} {statistics.fmean(v):+.2f}R/{len(v)}" for s, v in sorted(by_symbol.items())))

print("\n=== nearer targets (only trades whose own target is at least X) ===")
for strat, items in sorted(by.items()):
    for target in (1.0, 1.5, 2.0):
        values = []
        for _, _, _, _, r_mult, r_net, mfe, _, rr, _, _ in items:
            if rr is None or rr < target or r_mult is None or r_net is None:
                continue
            cost = r_mult - r_net
            values.append((target if (mfe or 0) >= target else r_mult) - cost)
        print(line(f"{strat} @{target}R", values))

print("\n=== higher-timeframe alignment ===")
for strat, items in sorted(by.items()):
    for flag in (1.0, 0.0):
        values = [
            x[5] or 0.0 for x in items if (json.loads(x[9]) if x[9] else {}).get("ctx:htf_aligned", 0.0) == flag
        ]
        print(line(f"{strat} aligned={int(flag)}", values))

print("\n=== how the losers lost ===")
for strat, items in sorted(by.items()):
    losers = [x for x in items if (x[5] or 0) <= 0]
    if not losers:
        continue
    never = sum(1 for x in losers if (x[6] or 0) < 0.2)
    halfway = sum(1 for x in losers if (x[6] or 0) >= 1.0)
    print(f"{strat:28} losers {len(losers):4d}: never reached +0.2R {100 * never / len(losers):3.0f}%, reached +1R first {100 * halfway / len(losers):3.0f}%")
