"""Prototype [Claude, research - no bot change]: the leg comes from the same M15 structure as the side.

Side (prototype 2, rule 16 m15): an M15 HH or M -> BUY, an LL or W -> SELL, held. While BUY: L0 = the latest fixed
M15 LOW (the higher low the side stands on), H100 = the highest M15 high after it (closed bars); a BUY limit at
H100 - ENTRY x (H100 - L0), stop L0 - 0.5 (below it the next low is an LL - the side would turn), target
L0 + 1.618 x leg - 0.5; written only if R (net of the 0.30 spread) >= 2. SELL mirrored. Decisions at each M15 close;
fills and exits on M5 (fill bar: only the stop counts; a bar touching both = the stop). One order at a time; a
waiting order is replaced when the leg changes and dropped when the side turns or its target is touched first;
one fill per L0. Usage: struct_leg.py ENTRY [TOL]"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from eye import bot2e

ENTRY = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
TOL = 0.20
EXT = float(sys.argv[2]) if len(sys.argv) > 2 else 1.618
MINR = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
SPREAD, BUF = 0.30, 0.50
TH = bot2e.TH
f = bot2e.load_frames()
m15 = f["M15"][(f["M15"].index >= "2026-06-01") & (f["M15"].index < "2026-10-31")]
m5 = f["M5"][(f["M5"].index >= "2026-06-25") & (f["M5"].index < "2026-10-31")]
pv = bot2e._zigzag(m15)
STEP = pd.Timedelta(minutes=15)
known_at = [m15.index[q.confirm_pos] + STEP for q in pv]
hi, lo = m15.high.to_numpy(), m15.low.to_numpy()

def side_at(n):  # pivots known: pv[:n]
    for i in range(n - 1, 1, -1):
        p, m, q = pv[i - 2].price, pv[i - 1].price, pv[i].price
        if pv[i].kind.value == "HIGH":
            if abs(q - p) <= TOL * (max(p, q) - m) + 1e-9: return "SELL"
            if q > p: return "BUY"
        else:
            if abs(q - p) <= TOL * (m - min(p, q)) + 1e-9: return "BUY"
            if q < p: return "SELL"
    return None

m5_t = m5.index; m5_o, m5_h, m5_l = m5.open.to_numpy(), m5.high.to_numpy(), m5.low.to_numpy()
trades = []; order = None; pos = None; used = set()
start = pd.Timestamp("2026-07-01", tz=TH).tz_convert("UTC"); end = pd.Timestamp("2026-10-31", tz=TH).tz_convert("UTC")
n_known = 0; k5 = int(m5_t.searchsorted(start))
for k in range(len(m15)):
    now = m15.index[k] + STEP
    if now < start or now >= end: continue
    # M5 bars up to now: fills / exits
    while k5 < len(m5_t) and m5_t[k5] + pd.Timedelta(minutes=5) <= now:
        o, h, l = m5_o[k5], m5_h[k5], m5_l[k5]
        if pos:
            b = pos["buy"]
            if (l <= pos["stop"]) if b else (h >= pos["stop"]):
                x = pos["stop"] if ((o > pos["stop"]) if b else (o < pos["stop"])) else o
                pos["exit"], pos["why"] = x, "stop"
            elif not pos["fresh"] and ((h >= pos["tgt"]) if b else (l <= pos["tgt"])):
                pos["exit"], pos["why"] = pos["tgt"], "target"
            pos["fresh"] = False
            if "why" in pos:
                pos["R"] = ((pos["exit"] - pos["fill"]) * (1 if b else -1) - SPREAD) / abs(pos["entry"] - pos["stop"])
                trades.append(pos); pos = None
        elif order:
            b = order["buy"]
            if (h >= order["tgt"]) if b else (l <= order["tgt"]):
                order = None
            elif (l <= order["entry"]) if b else (h >= order["entry"]):
                fill = min(o, order["entry"]) if b else max(o, order["entry"])
                pos = {**order, "fill": fill, "fill_t": m5_t[k5], "fresh": True}; used.add(order["key"]); order = None
                if (l <= pos["stop"]) if b else (h >= pos["stop"]):
                    pos["exit"], pos["why"] = pos["stop"], "stop"
                    pos["R"] = ((pos["exit"] - pos["fill"]) * (1 if b else -1) - SPREAD) / abs(pos["entry"] - pos["stop"])
                    trades.append(pos); pos = None
        k5 += 1
    while n_known < len(pv) and known_at[n_known] <= now: n_known += 1
    if pos: continue
    side = side_at(n_known)
    if side is None: order = None; continue
    buy = side == "BUY"
    kind = "LOW" if buy else "HIGH"
    anchors = [i for i in range(n_known) if pv[i].kind.value == kind]
    if not anchors: order = None; continue
    a = pv[anchors[-1]]
    seg = slice(a.pivot_pos + 1, k + 1)
    if a.pivot_pos + 1 > k: order = None; continue
    l0 = a.price; h100 = hi[seg].max() if buy else lo[seg].min()
    leg = (h100 - l0) if buy else (l0 - h100)
    key = (side, a.pivot_pos)
    if leg <= 0 or key in used: order = None; continue
    s = 1 if buy else -1
    entry = h100 - s * ENTRY * leg; stop = l0 - s * BUF; tgt = l0 + s * EXT * leg - s * BUF
    r = ((tgt - entry) * s - SPREAD) / ((entry - stop) * s)
    price = m15.close.iloc[k]
    if r < MINR or (price - entry) * s <= 0: order = None; continue
    order = {"buy": buy, "entry": entry, "stop": stop, "tgt": tgt, "key": key, "t": now, "leg": leg, "l0": l0, "h100": h100}

d = pd.DataFrame(trades)
if d.empty: print("no trades"); sys.exit()
d["month"] = d.fill_t.dt.tz_convert(TH).dt.month
print(f"ENTRY {ENTRY} EXT {EXT} MINR {MINR}: {len(d)} trades, won {(d.why=='target').sum()} ({(d.why=='target').mean():.0%}), "
      f"R {d.R.sum():+.2f}, {d.R.mean():+.3f} a trade; median risk {(d.entry-d.stop).abs().median():.2f} USD, median leg {d.leg.median():.1f}")
print(d.groupby("month").agg(n=("R", "size"), won=("why", lambda w: (w == "target").sum()), R=("R", "sum")).round(2).T.to_string())
d.to_pickle(r"C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\600a9d86-b3ac-4124-878e-b57c675a524d\scratchpad" + f"\\struct_{ENTRY}_{EXT}.pkl")
