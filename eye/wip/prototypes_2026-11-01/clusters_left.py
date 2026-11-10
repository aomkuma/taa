"""Do the owner's Fibonacci clusters mark the turns? [Claude, research]

For each M15 swing (a fixed pivot A to the next fixed pivot T, July - October), the levels known while price ran
from A toward T: from the last N legs among the pivots fixed before T's bar (A included as the end of the last
leg) - each leg (a, b): retracements b - r(b - a), r in 0.382 0.5 0.618 0.786 0.886, and extensions a + e(b - a),
e in 1.272 1.618 2.0. The cluster score at a price x = the number of levels within W USD. Along the path A -> T
(a grid every 0.5 USD over the prices the swing traded through) the turn's score is ranked among the grid's
scores: 1.0 = the turn has the highest score on its swing. If clusters mark turns, the mean rank is well above 0.5
and turns sit at high scores more often than the grid does."""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from eye import bot2e

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8
W = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
RET = (0.382, 0.5, 0.618, 0.786, 0.886)
EXT = (1.272, 1.618, 2.0)
m15 = bot2e.load_frames()["M15"]
m15 = m15[(m15.index >= "2026-06-01") & (m15.index < "2026-10-31")]
pv = bot2e._zigzag(m15)
TH = bot2e.TH
ranks, turn_scores, grid_scores, sizes = [], [], [], []
for j in range(1, len(pv)):
    a, t = pv[j - 1], pv[j]
    if m15.index[t.pivot_pos].tz_convert(TH) < pd.Timestamp("2026-07-01", tz=TH):
        continue
    known = [q for q in pv[:j] if q.confirm_pos < t.pivot_pos]
    if len(known) < N + 1 or known[-1] is not a:
        # the swing's start must be fixed before the turn is made, else the swing was not "known"
        continue
    levels = np.array([q.price for q in known[-N - 1:-1]])
    lo, hi = sorted((a.price, t.price))
    grid = np.arange(lo, hi + 1e-9, 0.5)
    if len(grid) < 10:
        continue
    score = lambda p: int((np.abs(levels - p) <= W).sum())
    gs = np.array([score(p) for p in grid])
    ts = score(t.price)
    ranks.append((gs < ts).mean() + 0.5 * (gs == ts).mean())
    turn_scores.append(ts); grid_scores.extend(gs.tolist()); sizes.append(hi - lo)
ranks = np.array(ranks); ts = np.array(turn_scores); gs = np.array(grid_scores)
print(f"N {N} legs, W {W} USD: {len(ranks)} swings (median size {np.median(sizes):.1f} USD)")
print(f"  mean rank of the turn's score on its swing {ranks.mean():.3f} (0.5 = no better than any price passed)")
print(f"  turn score: mean {ts.mean():.2f}, share with >= 2 levels {np.mean(ts >= 2):.0%}, >= 3 {np.mean(ts >= 3):.0%}")
print(f"  grid score: mean {gs.mean():.2f}, share with >= 2 levels {np.mean(gs >= 2):.0%}, >= 3 {np.mean(gs >= 3):.0%}")
