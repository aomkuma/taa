"""Trade each new leg toward a part of the leg before it [Claude, from the owner's "find the tops and bottoms and
take only 30 - 50 % of the move"; research - not the bot].

On TF's fixed pivots: when a pivot P1 is fixed (the close of its confirm bar), the previous leg P0 -> P1 is known.
Enter at that close in the new leg's direction (a market order at the close + the 0.30 spread in R), stop beyond P1
by 0.5, target P1 + T x |P1 - P0| toward the new leg (T 0.5 / 0.618 / 1.0); counted only when R >= MINR. Exits on M5
after the entry (both touched in a bar = the stop; a gap past the stop exits at the open); each pivot on its own.
Also printed: how far price had already run from P1 at the confirm close, as a share of the previous leg.
Usage: turn_trade.py TF T MINR FROM TO"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TF, T, MINR, A0, A1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
TH = bot2e.TH; SPREAD, BUF = 0.30, 0.50
STEP = pd.Timedelta(minutes={"M5": 5, "M15": 15, "M30": 30, "H1": 60}[TF])
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=10)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
m5 = walk.frame("M5")
t5, o5, h5, l5 = m5.index, m5.open.to_numpy(), m5.high.to_numpy(), m5.low.to_numpy()
pv = bot2e._zigzag(df)
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)
out, gone = [], []
for j in range(1, len(pv)):
    p0, p1 = pv[j - 1], pv[j]
    now = df.index[p1.confirm_pos] + STEP
    if not (start <= now.tz_convert(TH) < end): continue
    buy = p1.kind.value == "LOW"; s = 1 if buy else -1
    leg = abs(p1.price - p0.price)
    entry = df.close.iloc[p1.confirm_pos]
    gone.append((entry - p1.price) * s / leg)
    stop = p1.price - s * BUF; tgt = p1.price + s * T * leg
    risk = (entry - stop) * s
    if risk <= 0 or (tgt - entry) * s <= 0: continue
    r = ((tgt - entry) * s - SPREAD) / risk
    if r < MINR: continue
    i = int(t5.searchsorted(now)); why = None
    for k in range(i, len(t5)):
        if (l5[k] <= stop) if buy else (h5[k] >= stop):
            gap = (o5[k] < stop) if buy else (o5[k] > stop)
            ex = o5[k] if gap else stop; why = "stop"; break
        if (h5[k] >= tgt) if buy else (l5[k] <= tgt):
            ex = tgt; why = "target"; break
    if why is None: continue
    out.append((now, why, ((ex - entry) * s - SPREAD) / risk, r))
d = pd.DataFrame(out, columns=["t", "why", "R", "plan_r"])
g = np.array(gone)
print(f"{TF} T {T} minR {MINR} {A0}..{A1}: at the confirm close price had run a median {np.median(g):.2f} of the previous leg "
      f"(quartiles {np.quantile(g, .25):.2f} / {np.quantile(g, .75):.2f}); {len(d)} trades, won {(d.why == 'target').mean():.0%}, "
      f"{d.R.mean():+.3f} R a trade, median planned R {d.plan_r.median():.2f}")
