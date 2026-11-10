"""Rule 17 (the break and its retest) on every leg of a timeframe [Claude, research - not the bot].

Legs: every pair of consecutive fixed pivots (L0 -> H100) of TF's MT5 ZigZag 12 / 5 / 3 (one pass, 01/05 - 30/10;
a pivot counts from its confirm bar). The break: the first TF close strictly beyond H100 among the bars opening at
or after H100's fix, while no price has gone back beyond L0 since H100. Lb = the extreme of the bars after H100's bar
up to the bar before the break. A limit at H100, stop Lb -/+ 0.5, target L0 + 1.618 x leg (else 2.0 x leg) -/+ 0.5,
R (net 0.30) >= 2 else no order. Life: 24 M5 bars from the break close; withdrawn if the target is touched first.
Fills and exits on M5 (fill bar: stop only; both touched = stop; a bar opening beyond the stop exits at its open).
Every leg is counted on its own (trades may overlap). FILTER m15 keeps only orders on the rule 16 m15 side at the
break (the M15 held side with M and W, TOL 0.20). Usage: retest_all.py TF [none|m15]"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TF = sys.argv[1] if len(sys.argv) > 1 else "M15"
FILTER = sys.argv[2] if len(sys.argv) > 2 else "none"
TH = bot2e.TH; SPREAD, BUF, TOL = 0.30, 0.50, 0.20
STEP = pd.Timedelta(minutes={"M5": 5, "M15": 15, "M30": 30}[TF])
df = walk.frame(TF); df = df[(df.index >= "2026-05-01") & (df.index < "2026-10-31")]
m5 = walk.frame("M5"); m5 = m5[(m5.index >= "2026-06-20") & (m5.index < "2026-11-01")]
pv = bot2e._zigzag(df)
H, L, C = df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy()
t5, o5, h5, l5 = m5.index, m5.open.to_numpy(), m5.high.to_numpy(), m5.low.to_numpy()

m15 = walk.frame("M15"); m15 = m15[(m15.index >= "2026-05-01") & (m15.index < "2026-10-31")]
pv15 = bot2e._zigzag(m15); known15 = [m15.index[q.confirm_pos] + pd.Timedelta(minutes=15) for q in pv15]
def side15(now):
    n = int(np.searchsorted(np.array(known15, dtype="datetime64[ns]"), np.datetime64(now.tz_convert("UTC").tz_localize(None)), side="right"))
    for i in range(n - 1, 1, -1):
        p, m, q = pv15[i - 2].price, pv15[i - 1].price, pv15[i].price
        if pv15[i].kind.value == "HIGH":
            if abs(q - p) <= TOL * (max(p, q) - m) + 1e-9: return "SELL"
            if q > p: return "BUY"
        else:
            if abs(q - p) <= TOL * (m - min(p, q)) + 1e-9: return "BUY"
            if q < p: return "SELL"
    return None

out = []
start, end = pd.Timestamp("2026-07-01", tz=TH), pd.Timestamp("2026-10-31", tz=TH)
for j in range(1, len(pv)):
    a, b = pv[j - 1], pv[j]
    buy = b.kind.value == "HIGH"; s = 1 if buy else -1
    l0, h100 = a.price, b.price; leg = (h100 - l0) * s
    if leg <= 0: continue
    k0 = b.confirm_pos + 1  # bars opening at or after the fix (the fix is at the confirm bar's close)
    brk = None
    for k in range(b.pivot_pos + 1, len(df)):
        if (L[k] < l0) if buy else (H[k] > l0): break
        if k >= k0 and ((C[k] > h100) if buy else (C[k] < h100)):
            brk = k; break
    if brk is None or brk <= b.pivot_pos + 1: continue
    now = df.index[brk] + STEP
    if not (start <= now.tz_convert(TH) < end): continue
    if FILTER == "m15" and side15(now) != ("BUY" if buy else "SELL"): continue
    lb = L[b.pivot_pos + 1:brk].min() if buy else H[b.pivot_pos + 1:brk].max()
    entry, stop = h100, lb - s * BUF
    r = None
    for ext in (1.618, 2.0):
        tgt = l0 + s * ext * leg - s * BUF
        r = ((tgt - entry) * s - SPREAD) / ((entry - stop) * s) if (entry - stop) * s > 0 else -1
        if r >= 2: break
    if r < 2: continue
    i = int(t5.searchsorted(now)); fill = None
    for i in range(i, min(i + 24, len(t5))):
        if (h5[i] >= tgt) if buy else (l5[i] <= tgt): break
        if (l5[i] <= entry) if buy else (h5[i] >= entry):
            fill = (min(o5[i], entry) if buy else max(o5[i], entry)); break
    if fill is None: continue
    why = None
    for k in range(i, len(t5)):
        hit_stop = (l5[k] <= stop) if buy else (h5[k] >= stop)
        if hit_stop:
            ex = stop if ((o5[k] > stop) if buy else (o5[k] < stop)) or k == i else o5[k]; why = "stop"; break
        if k > i and ((h5[k] >= tgt) if buy else (l5[k] <= tgt)):
            ex = tgt; why = "target"; break
    if why is None: continue
    R = ((ex - fill) * s - SPREAD) / ((entry - stop) * s)
    out.append((now, "BUY" if buy else "SELL", why, R, (entry - stop) * s, leg))
d = pd.DataFrame(out, columns=["t", "side", "why", "R", "risk", "leg"])
d["m"] = d.t.dt.tz_convert(TH).dt.month
print(f"{TF} filter {FILTER}: {len(d)} retests filled and resolved, won {(d.why == 'target').mean():.0%}, "
      f"R {d.R.sum():+.1f}, {d.R.mean():+.3f} a trade; median risk {d.risk.median():.2f}, median leg {d.leg.median():.1f}")
print("  by month R / n:", {m: (round(g.R.sum(), 1), len(g)) for m, g in d.groupby("m")})
print("  by side:", {sd: (len(g), f"{(g.why == 'target').mean():.0%}", round(g.R.mean(), 3)) for sd, g in d.groupby("side")})
print("  by month and side R:", d.groupby(["m", "side"]).R.agg(["size", "sum"]).round(1).to_dict("index"))
