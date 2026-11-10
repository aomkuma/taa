"""Does each leg end on the Fibo of the leg before it? [Claude, research - no trading]

The owner's chart of 30/10/2026 M15: the Fibo on the leg up 3989 -> 4011 (0 % at its end, 100 % at its start), and
the next leg down ended at the 200 % line (~3967). For every two consecutive legs of TF's fixed pivots (P0 -> P1,
then P1 -> P2): the level the second leg reached on the first leg's Fibo = |P2 - P1| / |P1 - P0| (2.0 = the 200 %
line). If the lines measure the targets, these levels sit within +-TOL of the Fibo lines (0.382 0.5 0.618 0.786 1.0
1.272 1.618 2.0 2.618 3.618 4.236) more often than within +-TOL of control lines midway between them.
Usage: leg_ratio.py TF FROM TO [TOL]"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TF, A0, A1 = sys.argv[1], sys.argv[2], sys.argv[3]
TOL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.03
TH = bot2e.TH
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=5)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
pv = bot2e._zigzag(df)
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)
r = np.array([abs(pv[j + 1].price - pv[j].price) / abs(pv[j].price - pv[j - 1].price)
              for j in range(1, len(pv) - 1) if start <= df.index[pv[j].pivot_pos].tz_convert(TH) < end])
FIB = [0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0, 2.618, 3.618, 4.236]
CTRL = [(a + b) / 2 for a, b in zip(FIB, FIB[1:])]
def hits(lines, scale):  # within +-TOL x the line (relative), so wide levels are not favoured
    return sum(int(np.sum(np.abs(r - x) <= TOL * x)) for x in lines if x <= scale)
print(f"{TF} {A0}..{A1}: {len(r)} legs; level the next leg reached: median {np.median(r):.2f}, quartiles "
      f"{np.quantile(r, 0.25):.2f} / {np.quantile(r, 0.75):.2f}; share >= 1.272 {np.mean(r >= 1.272):.0%}, >= 1.618 "
      f"{np.mean(r >= 1.618):.0%}, >= 2.0 {np.mean(r >= 2.0):.0%}")
fib_in = [x for x in FIB if x <= 2.618]; ctl_in = [x for x in CTRL if x <= 2.618]
h_f, h_c = hits(fib_in, 9), hits(ctl_in, 9)
print(f"   within +-{TOL:.0%} of a Fibo line (0.382 .. 2.618, {len(fib_in)} lines): {h_f} legs, {h_f/len(fib_in):.1f} a line; "
      f"of a control line midway ({len(ctl_in)} lines): {h_c}, {h_c/len(ctl_in):.1f} a line")
for x in fib_in:
    print(f"     {x:5.3f}: {int(np.sum(np.abs(r - x) <= TOL * x))}", end="")
print()
for x in ctl_in:
    print(f"     {x:5.3f}: {int(np.sum(np.abs(r - x) <= TOL * x))}", end="")
print()
