"""The owner, 2026-11-01: *"the turning point of the current price is the target measured from the previous leg"*;
*"go in - 0.01 lot at every important Fibo % line"*. The form [Claude, research - not the bot]:

A cycle starts when a pivot P1 of TF is fixed (the previous leg P0 -> P1, length d; the owner's Fibo 0 % at P1, 100 %
at P0). The current leg runs from P1 toward P0 and beyond; at each line x of LEVELS (price P1 - x (P1 - P0)) a
limit of 0.01 lot against the current leg (a BUY when the current leg is down), placed only if price has not passed
it. Exit together: once filled, all open layers close when price comes back by BACK x (P1 - the leg's extreme so
far) from the extreme (BACK 0.382 - the owner's "30 - 50 %"); all close if price goes beyond the last line by
STOP x d. A cycle ends at its exit; unfilled limits are dropped then (or if none filled when the next pivot is
fixed). M5 bars; a bar touching the exit and the stop counts the stop; the spread 0.30 on every layer. USD at 0.01
lot = 1 USD per 1.00. Cycles overlap; each counted on its own. Usage: layers.py TF FROM TO [BACK] [STOP]"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TF, A0, A1 = sys.argv[1], sys.argv[2], sys.argv[3]
BACK = float(sys.argv[4]) if len(sys.argv) > 4 else 0.382
STOPX = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
LEVELS = (1.0, 1.272, 1.618, 2.0, 2.618, 4.236)
TH = bot2e.TH; SPREAD = 0.30
STEP = pd.Timedelta(minutes={"M5": 5, "M15": 15, "M30": 30, "H1": 60}[TF])
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=10)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
m5 = walk.frame("M5")
t5, h5, l5 = m5.index, m5.high.to_numpy(), m5.low.to_numpy()
pv = bot2e._zigzag(df)
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)
rows = []; LAY = []
for j in range(1, len(pv) - 1):
    p0, p1 = pv[j - 1], pv[j]
    now = df.index[p1.confirm_pos] + STEP
    if not (start <= now.tz_convert(TH) < end): continue
    s = 1 if p1.kind.value == "HIGH" else -1  # +1: the current leg is down (we buy its lines)
    d = abs(p1.price - p0.price)
    price0 = df.close.iloc[p1.confirm_pos]
    lvl = {p1.price - s * x * d: x for x in LEVELS}
    lines = [L for L in lvl if (price0 - L) * s > 0]  # not yet passed
    if not lines: continue
    stop = p1.price - s * (LEVELS[-1] + STOPX) * d
    next_fix = df.index[pv[j + 1].confirm_pos] + STEP
    i = int(t5.searchsorted(now)); filled = []; ext = price0; res = None; last_fill = -1
    for k in range(i, len(t5)):
        for L in lines:  # fills: price reaching a line
            if L in filled: continue
            if (l5[k] <= L) if s > 0 else (h5[k] >= L):
                filled.append(L); last_fill = k
        ext = min(ext, l5[k]) if s > 0 else max(ext, h5[k])
        if filled and ((l5[k] <= stop) if s > 0 else (h5[k] >= stop)):
            res = ("stop", stop, k); break
        if filled and k > last_fill:  # the take-back counts only on a bar after the last fill (conservative)
            exit_px = ext + s * BACK * abs(p1.price - ext)
            if (h5[k] >= exit_px) if s > 0 else (l5[k] <= exit_px):
                res = ("back", exit_px, k); break
        if not filled and t5[k] >= next_fix:
            break
    if res is None: continue
    why, px, k = res
    usd = sum((px - L) * s - SPREAD for L in filled)
    rows.append((now, why, len(filled), usd, (t5[k] - now) / pd.Timedelta(hours=1)))
    for L in filled:
        LAY.append((lvl[L], (px - L) * s - SPREAD, why))
r = pd.DataFrame(rows, columns=["t", "why", "layers", "usd", "hours"])
r["m"] = r.t.dt.tz_convert(TH).dt.strftime("%y-%m")
print(f"{TF} {A0}..{A1} BACK {BACK} STOP {STOPX}: {len(r)} cycles with a fill; {(r.usd > 0).mean():.0%} won; "
      f"total {r.usd.sum():+.0f} USD at 0.01 lot a line; median cycle {r.usd.median():+.2f}; worst {r.usd.min():+.0f}; "
      f"stops {int((r.why == 'stop').sum())}; layers filled - median {r.layers.median():.0f}, max {r.layers.max()}")
print("   by layers filled:", {n: (len(g), f"{(g.usd > 0).mean():.0%}", round(g.usd.sum())) for n, g in r.groupby("layers")})
print("   by month USD:", {m: round(g.usd.sum()) for m, g in r.groupby("m")})
la = pd.DataFrame(LAY, columns=["level", "usd", "why"])
print("   by line (each 0.01 lot layer): line: layers, won, total USD, USD a layer")
for x, g in la.groupby("level"):
    print(f"     {x*100:6.1f} %: {len(g):4d}, {(g.usd > 0).mean():4.0%}, {g.usd.sum():+7.0f}, {g.usd.mean():+6.2f}")
