"""Each wave has its own target - measured per wave number [Claude, research - no trading].

The owner: *"counting like this, each one has its own target"*. The count as before (points 0 .. 5 on TF's fixed
pivots, from the move's start). Per wave, its length against its own ruler (the textbook guide in brackets):
  wave 2 / wave 1 (0.5 - 0.618), wave 3 / wave 1 (1.618), wave 4 / wave 3 (0.382), wave 5 / wave 1 (1.0).
For each: the distribution (quartiles), and the share ending within +-10 % (relative) of each Fibo line - against the
same share for control lines midway between the Fibo lines. Usage: wave_targets.py TF FROM TO"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TF, A0, A1 = sys.argv[1], sys.argv[2], sys.argv[3]
TH = bot2e.TH
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=30)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
pv = bot2e._zigzag(df)
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)

def count(ia):
    a = pv[ia]; up = a.kind.value == "HIGH"; k = ia - 1
    while k >= 0 and not (pv[k].kind is a.kind and ((pv[k].price > a.price) if up else (pv[k].price < a.price))):
        k -= 1
    opp = [i for i in range(k + 1, ia) if pv[i].kind is not a.kind]
    if not opp: return 0, None
    st = min(opp, key=lambda i: pv[i].price) if up else max(opp, key=lambda i: pv[i].price)
    return ia - st, st

w = {2: [], 3: [], 4: [], 5: []}
for ia in range(len(pv) - 2):
    if not (start <= df.index[pv[ia].pivot_pos].tz_convert(TH) < end): continue
    n, st = count(ia)
    P = lambda i: pv[st + i].price
    L = lambda i: abs(P(i) - P(i - 1))  # wave i's length
    if n == 1: w[2].append(abs(pv[ia + 1].price - P(1)) / L(1))
    if n == 3:
        w[3].append(L(3) / L(1)); w[4].append(abs(pv[ia + 1].price - P(3)) / L(3))
    if n == 5: w[5].append(L(5) / L(1))
FIB = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0, 2.618]
CTRL = [(a + b) / 2 for a, b in zip(FIB, FIB[1:])]
GUIDE = {2: "0.5-0.618", 3: "1.618", 4: "0.382", 5: "1.0"}
print(f"{TF} {A0}..{A1}")
for k, xs in w.items():
    xs = np.array(xs)
    if len(xs) == 0: continue
    hit = {x: np.mean(np.abs(xs - x) <= 0.10 * x) for x in FIB}
    ctl = np.mean([np.mean(np.abs(xs - x) <= 0.10 * x) for x in CTRL])
    best = sorted(hit.items(), key=lambda kv: -kv[1])[:3]
    print(f"  wave {k} (guide {GUIDE[k]}): n {len(xs)}, quartiles {np.quantile(xs, .25):.2f} / {np.median(xs):.2f} / "
          f"{np.quantile(xs, .75):.2f}; most hit lines " + ", ".join(f"{x} {v:.0%}" for x, v in best)
          + f"; a control line {ctl:.0%} on average")
print("  the same window around 1.0 and its neighbours (0.893, 1.136), and around each line's midpoints:")
for k, xs in w.items():
    xs = np.array(xs)
    print(f"    wave {k}: " + "  ".join(f"{x}: {np.mean(np.abs(xs - x) <= 0.10):.0%}" for x in (0.618, 0.702, 0.786, 0.893, 1.0, 1.136, 1.272, 1.445, 1.618)))
