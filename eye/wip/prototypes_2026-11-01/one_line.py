"""One line of the previous leg's Fibo, its own stop and target [Claude, research - not the bot]; the owner: *"do it;
TP at the Fibo level it can reasonably reach"*.

When a pivot P1 of TF is fixed (previous leg P0 -> P1, d; the owner's Fibo 0 % at P1, 100 % at P0, lines beyond 100 %
are the extensions): a limit against the current leg at line ENTRY (e.g. 1.618), placed only if price has not passed
it; stop beyond line SL_LINE by 0.5 (e.g. 2.0); target at line TP_LINE (e.g. 0.618 - back up the Fibo) - R (net of
0.30) reported, and the trade taken only if R >= MINR. Withdrawn if the next pivot is fixed before the fill (the target
lies between P1 and the line - price passes it on the way, so it cannot withdraw the order). Fills / exits on M5 (fill bar: stop only; both = stop; a gap past the stop exits at its open).
Usage: one_line.py TF ENTRY SL_LINE TP_LINE MINR FROM TO"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TF = sys.argv[1]; ENTRY, SLL, TPL, MINR = map(float, sys.argv[2:6]); A0, A1 = sys.argv[6], sys.argv[7]
TH = bot2e.TH; SPREAD, BUF = 0.30, 0.50
STEP = pd.Timedelta(minutes={"M5": 5, "M15": 15, "M30": 30, "H1": 60}[TF])
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=10)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
m5 = walk.frame("M5")
t5, o5, h5, l5 = m5.index, m5.open.to_numpy(), m5.high.to_numpy(), m5.low.to_numpy()
pv = bot2e._zigzag(df)
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)
out = []
for j in range(1, len(pv) - 1):
    p0, p1 = pv[j - 1], pv[j]
    now = df.index[p1.confirm_pos] + STEP
    if not (start <= now.tz_convert(TH) < end): continue
    s = 1 if p1.kind.value == "HIGH" else -1  # +1: the current leg is down, the trade a BUY
    d = abs(p1.price - p0.price)
    line = lambda x: p1.price - s * x * d
    entry, stop, tgt = line(ENTRY), line(SLL) - s * BUF, line(TPL)
    r = ((tgt - entry) * s - SPREAD) / ((entry - stop) * s)
    if r < MINR: continue
    if (df.close.iloc[p1.confirm_pos] - entry) * s <= 0: continue
    next_fix = df.index[pv[j + 1].confirm_pos] + STEP
    i = int(t5.searchsorted(now)); fill = None
    while i < len(t5) and t5[i] < next_fix:
        if (l5[i] <= entry) if s > 0 else (h5[i] >= entry):
            fill = min(o5[i], entry) if s > 0 else max(o5[i], entry); break
        i += 1
    if fill is None: continue
    why = None
    for k in range(i, len(t5)):
        if (l5[k] <= stop) if s > 0 else (h5[k] >= stop):
            ex = o5[k] if ((o5[k] < stop) if s > 0 else (o5[k] > stop)) else stop; why = "stop"; break
        if k > i and ((h5[k] >= tgt) if s > 0 else (l5[k] <= tgt)):
            ex = tgt; why = "target"; break
    if why is None: continue
    R = ((ex - fill) * s - SPREAD) / ((entry - stop) * s)
    assert why == "target" or R < 0
    out.append((now, why, R, r, (ex - fill) * s - SPREAD))
d_ = pd.DataFrame(out, columns=["t", "why", "R", "plan_r", "usd"])
if d_.empty: print(f"{TF} entry {ENTRY} sl {SLL} tp {TPL} {A0}..{A1}: no trades"); sys.exit()
print(f"{TF} entry {ENTRY*100:.1f} sl {SLL*100:.1f} tp {TPL*100:.1f} {A0[:7]}..{A1[:7]}: {len(d_)} trades, won {(d_.why == 'target').mean():.0%}, "
      f"{d_.R.mean():+.3f} R a trade (planned R median {d_.plan_r.median():.2f}), {d_.usd.sum():+.0f} USD at 0.01 lot")
