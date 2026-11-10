"""Which known price marks wave 4's end best? [Claude, research - no trading]

The count as the owner allows it (*"once each point has formed and the ZigZag draws through them, that is fine"*):
points 0 .. 4 on TF's fixed pivots (wave_depth.py's count). At point 3 these prices are known; each is a guess for 4:
  fib38 / fib50 / fib62 / fib79 - the owner's Fibo on the move 0 -> 3 (0 % at 3) at 38.2 / 50 / 61.8 / 78.6 %;
  p1 - the price of point 1; p2 - the price of point 2; eq2 - point 3 moved back by wave 2's length;
  leg62 / leg79 - 61.8 / 78.6 % back of the leg 2 -> 3.
For each guess: the miss |4 - guess| as a share of the move 0 -> 3 - the median miss, and the share of waves 4 that
end within 10 % of the move from it. The best guess has the smallest miss. Usage: w4_where.py TF FROM TO"""
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

miss = {}
for ia in range(len(pv) - 1):
    if not (start <= df.index[pv[ia].pivot_pos].tz_convert(TH) < end): continue
    n, st = count(ia)
    if n != 3: continue
    p0, p1, p2, p3, p4 = (pv[st].price, pv[st + 1].price, pv[st + 2].price, pv[ia].price, pv[ia + 1].price)
    move = p3 - p0  # signed
    g = {f"fib{int(round(x*100))}": p3 - x * move for x in (0.382, 0.5, 0.618, 0.786)}
    g.update(p1=p1, p2=p2, eq2=p3 - (p1 - p2), leg62=p3 - 0.618 * (p3 - p2), leg79=p3 - 0.786 * (p3 - p2))
    for k, v in g.items():
        miss.setdefault(k, []).append(abs(p4 - v) / abs(move))
print(f"{TF} {A0}..{A1}: {len(miss['p1'])} waves 4")
for k, v in sorted(miss.items(), key=lambda kv: np.median(kv[1])):
    v = np.array(v)
    print(f"   {k:6s} median miss {np.median(v):.3f} of the move; within 10 %: {np.mean(v <= 0.10):.0%}; within 5 %: {np.mean(v <= 0.05):.0%}")
