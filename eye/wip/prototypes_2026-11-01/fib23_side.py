"""The owner's chart of 30/10/2026 M15: a leg down, the Fibo drawn 0 % at the top and 100 % at the bottom, and the
bounce that reaches the 23.6 % line - the point to find [owner]; the form [Claude, research - not the bot]:

Every leg of TF's fixed pivots (A -> B, ZigZag 12 / 5 / 3, one pass). Once B is fixed and price is still below the
level: a SELL limit (leg down; a BUY for a leg up) at A - LEVEL x (A - B) (0 % = A, 100 % = B; LEVEL 0.236 = the
owner's 23.6 % line), stop A + 0.5 (beyond 0 %), target A - EXT x (A - B) + 0.5 (EXT 1.0 = back to the bottom, 1.618
the extension); R (net 0.30) >= 2. Withdrawn if the target is touched first or after LIFE M5 bars. Fills / exits on
M5 (fill bar: stop only; both touched = stop; a gap past the stop exits at the open); every leg on its own.
Usage: fib23.py TF LEVEL EXT LIFE FROM TO [MINLEG]"""
import sys
sys.path.insert(0, ".")
import pandas as pd
from eye import bot2e, walk

TF, LEVEL, EXT, LIFE, A0, A1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
MINLEG = float(sys.argv[7]) if len(sys.argv) > 7 else 0.0
TH = bot2e.TH; SPREAD, BUF = 0.30, 0.50
STEP = pd.Timedelta(minutes={"M5": 5, "M15": 15, "M30": 30, "H1": 60}[TF])
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=30)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
m5 = walk.frame("M5")
pv = bot2e._zigzag(df)
t5, o5, h5, l5 = m5.index, m5.open.to_numpy(), m5.high.to_numpy(), m5.low.to_numpy()
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)
def side_at(n, TOL=0.20):
    for i in range(n - 1, 1, -1):
        p, m, q = pv[i - 2].price, pv[i - 1].price, pv[i].price
        if pv[i].kind.value == "HIGH":
            if abs(q - p) <= TOL * (max(p, q) - m) + 1e-9: return "SELL" if i == n - 1 or True else None
            if q > p: return "BUY"
        else:
            if abs(q - p) <= TOL * (m - min(p, q)) + 1e-9: return "BUY"
            if q < p: return "SELL"
    return None
out = []
for j in range(1, len(pv)):
    a, b = pv[j - 1], pv[j]
    sell = a.kind.value == "HIGH"; s = -1 if sell else 1  # s: the trade's direction
    leg = abs(a.price - b.price)
    if leg <= 0 or leg < MINLEG: continue
    now = df.index[b.confirm_pos] + STEP
    if not (start <= now.tz_convert(TH) < end): continue
    # the trade side only: the M15 side held (HH / M -> BUY, LL / W -> SELL) at the order, and the leg is the one
    # that made the side's last event (its end B is that event's pivot) - the impulse the owner draws
    if side_at(j + 1) != ("SELL" if sell else "BUY"): continue
    entry = a.price - LEVEL * (a.price - b.price)
    stop = a.price - s * BUF
    tgt = a.price - EXT * (a.price - b.price) - s * BUF
    r = ((tgt - entry) * s - SPREAD) / ((entry - stop) * s)
    if r < 2: continue
    price = df.close.iloc[b.confirm_pos]
    if (entry - price) * s >= 0: continue  # price already at or beyond the level
    i0 = int(t5.searchsorted(now)); fill = None
    for i in range(i0, min(i0 + LIFE, len(t5))):
        if (l5[i] <= tgt) if sell else (h5[i] >= tgt): break
        if (h5[i] >= entry) if sell else (l5[i] <= entry):
            fill = max(o5[i], entry) if sell else min(o5[i], entry); break
    if fill is None: continue
    why = None
    for k in range(i, len(t5)):
        if (h5[k] >= stop) if sell else (l5[k] <= stop):
            gap = (o5[k] > stop) if sell else (o5[k] < stop)
            ex = o5[k] if gap else stop; why = "stop"; break
        if k > i and ((l5[k] <= tgt) if sell else (h5[k] >= tgt)):
            ex = tgt; why = "target"; break
    if why is None: continue
    R = ((ex - fill) * s - SPREAD) / ((entry - stop) * s)
    assert why == "target" or R < 0, (now, R)
    out.append((now, "SELL" if sell else "BUY", why, R, r, leg, df.index[a.pivot_pos], a.price, df.index[b.pivot_pos], b.price, entry, stop, tgt, t5[i], t5[k]))
d = pd.DataFrame(out, columns=["t", "side", "why", "R", "plan_r", "leg", "ta", "pa", "tb", "pb", "entry", "stop", "tgt", "fill_t", "exit_t"])
d.to_pickle(sys.argv[8]) if len(sys.argv) > 8 else None
d["m"] = d.t.dt.tz_convert(TH).dt.strftime("%y-%m")
print(f"{TF} level {LEVEL} ext {EXT} life {LIFE} minleg {MINLEG} {A0}..{A1}: {len(d)} trades, won {(d.why == 'target').mean():.0%}, "
      f"R {d.R.sum():+.1f}, {d.R.mean():+.3f} a trade; median planned R {d.plan_r.median():.1f}, median leg {d.leg.median():.1f}")
print("   by side:", {sd: (len(g), f"{(g.why == 'target').mean():.0%}", round(g.R.mean(), 3)) for sd, g in d.groupby("side")})
print("   by month R:", {m: round(g.R.sum(), 1) for m, g in d.groupby("m")})
