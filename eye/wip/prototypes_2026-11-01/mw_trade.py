"""Trade the owner's M and W at the first pivot's price [Claude, research - not the bot].

The owner: buy the M and sell up above. On TF's fixed pivots (ZigZag 12 / 5 / 3, one pass): a fixed LOW L1 and the
fixed HIGH Hm after it (the bounce, swing = Hm - L1). Once Hm is fixed: a BUY limit at L1 (the second bottom of an
M), stop L1 - TOL x swing - 0.5 (below it the new low is an LL, not an M), target Hm - 0.5 (the top above) - or
EXT x swing above L1 when EXT > 1; R (net 0.30) >= 2 else no order. Withdrawn if price goes above the target before
the fill, or after LIFE M5 bars. Fills / exits on M5 (fill bar: stop only; both touched = stop; a bar opening beyond
the stop exits at its open). A W mirrored. Each counted on its own. Usage: mw_trade.py TF TOL EXT LIFE FROM TO"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TF, TOL, EXT, LIFE = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
A0, A1 = sys.argv[5], sys.argv[6]
TH = bot2e.TH; SPREAD, BUF = 0.30, 0.50
STEP = pd.Timedelta(minutes={"M5": 5, "M15": 15, "M30": 30}[TF])
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=30)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
m5 = walk.frame("M5")
pv = bot2e._zigzag(df)
t5, o5, h5, l5 = m5.index, m5.open.to_numpy(), m5.high.to_numpy(), m5.low.to_numpy()
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)
out = []
for j in range(1, len(pv)):
    p1, pm = pv[j - 1], pv[j]
    buy = p1.kind.value == "LOW"; s = 1 if buy else -1
    swing = (pm.price - p1.price) * s
    if swing <= 0: continue
    now = df.index[pm.confirm_pos] + STEP  # Hm known
    if not (start <= now.tz_convert(TH) < end): continue
    entry = p1.price; stop = entry - s * (TOL * swing + BUF)
    tgt = (pm.price - s * BUF) if EXT <= 1 else (entry + s * EXT * swing - s * BUF)
    r = ((tgt - entry) * s - SPREAD) / ((entry - stop) * s)
    if r < 2: continue
    i0 = int(t5.searchsorted(now)); fill = None
    price = df.close.iloc[pm.confirm_pos]
    if (price - entry) * s <= 0: continue  # price already back at or past L1 when Hm is known: no M to wait for
    for i in range(i0, min(i0 + LIFE, len(t5))):
        if (h5[i] >= tgt) if buy else (l5[i] <= tgt): break
        if (l5[i] <= entry) if buy else (h5[i] >= entry):
            fill = min(o5[i], entry) if buy else max(o5[i], entry); break
    if fill is None: continue
    why = None
    for k in range(i, len(t5)):
        if (l5[k] <= stop) if buy else (h5[k] >= stop):
            gap = (o5[k] < stop) if buy else (o5[k] > stop)
            ex = o5[k] if gap else stop; why = "stop"; break
        if k > i and ((h5[k] >= tgt) if buy else (l5[k] <= tgt)):
            ex = tgt; why = "target"; break
    if why is None: continue
    R = ((ex - fill) * s - SPREAD) / ((entry - stop) * s)
    assert R <= r + 1e-6 and (why == "target" or R < 0), (now, why, R, fill, entry, stop, ex)
    out.append((now, "BUY" if buy else "SELL", why, R, r, swing))
d = pd.DataFrame(out, columns=["t", "side", "why", "R", "plan_r", "swing"])
d["m"] = d.t.dt.tz_convert(TH).dt.strftime("%y-%m")
w = (d.why == "target").mean()
print(f"{TF} TOL {TOL} EXT {EXT} LIFE {LIFE} {A0}..{A1}: {len(d)} trades, won {w:.0%}, R {d.R.sum():+.1f}, "
      f"{d.R.mean():+.3f} a trade; median planned R {d.plan_r.median():.1f}, median swing {d.swing.median():.1f}")
print("   by side:", {sd: (len(g), f"{(g.why == 'target').mean():.0%}", round(g.R.mean(), 3)) for sd, g in d.groupby("side")})
print("   by month R:", {m: round(g.R.sum(), 1) for m, g in d.groupby("m")})
