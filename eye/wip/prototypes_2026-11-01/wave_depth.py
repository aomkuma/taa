"""Where do wave 4 and the bounce after wave 5 end, on the owner's Fibo? [Claude, research - no trading]

The owner's count on a move up (a move down mirrored): from its start S (the lowest LOW since the last HIGH above
the current top), up 1, down 2, up 3, down 4, up 5 (fixed pivots of TF). The owner: after 3, buy wave 4 (if an entry
is found) and sell at the top above; after 5, sell the bounce (the owner's chart: the bounce to the 23.6 % line).
Measured, every count on TF's fixed pivots over FROM .. TO:
- wave 4's end on the owner's Fibo of wave 3 (0 % at wave 3's top, 100 % at wave 2's low; a level x = top - x * leg):
  x = (top3 - low4) / (top3 - low2); and on the whole move S -> top3;
- the bounce after wave 5: the first leg down from top5 to B, the bounce to C; on the owner's Fibo (0 % at top5,
  100 % at B) the bounce ends at the line 1 - (C - B) / (top5 - B) - 0.236 = the owner's 23.6 % line.
Usage: wave_depth.py TF FROM TO"""
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

w4_leg, w4_move, b5 = [], [], []
for ia in range(len(pv) - 2):
    t = df.index[pv[ia].pivot_pos].tz_convert(TH)
    if not (start <= t < end): continue
    n, st = count(ia)
    top = pv[ia].price
    if n == 3:  # pv[ia] = top 3, pv[ia-1] = low 2, pv[ia+1] = low 4
        l2, l4, s0 = pv[ia - 1].price, pv[ia + 1].price, pv[st].price
        w4_leg.append((top - l4) / (top - l2)); w4_move.append((top - l4) / (top - s0))
    if n == 5:  # pv[ia] = top 5, pv[ia+1] = B, pv[ia+2] = C
        b, c = pv[ia + 1].price, pv[ia + 2].price
        b5.append(1 - abs(c - b) / abs(top - b))

def show(name, xs):
    xs = np.array(xs)
    bins = [-np.inf, 0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0, 1.272, 1.618, np.inf]
    lab = ["<0", "0-23.6", "23.6-38.2", "38.2-50", "50-61.8", "61.8-78.6", "78.6-88.6", "88.6-100", "100-127", "127-162", ">162"]
    h = pd.cut(xs, bins, labels=lab).value_counts().reindex(lab)
    print(f"{name}: n {len(xs)}, median {np.median(xs):.3f}")
    print("   " + "  ".join(f"{k} {v}" for k, v in h.items()))

print(f"{TF} {A0}..{A1}")
show("wave 4 on the Fibo of wave 3 (0 % at top 3, 100 % at low 2)", w4_leg)
show("wave 4 on the Fibo of the move S -> top 3", w4_move)
show("bounce after wave 5 - the line it reaches (0 % at top 5, 100 % at the first low; 0.236 = the 23.6 % line)", b5)
