"""Split the structure-leg prototype's trades by the H4 trend held until the opposite break (HH -> up, LL -> down,
fixed H4 pivots known at the fill) [Claude, research]."""
import sys; sys.path.insert(0, ".")
import pandas as pd
from eye import bot2e
S = r"C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\600a9d86-b3ac-4124-878e-b57c675a524d\scratchpad"
h4 = bot2e.load_frames()["H4"]; h4 = h4[h4.index >= "2025-11-01"]
pv = bot2e._zigzag(h4); STEP = pd.Timedelta(hours=4)
ev = []; lastH = lastL = None
for q in pv:
    t = h4.index[q.confirm_pos] + STEP
    if q.kind.value == "HIGH":
        if lastH is not None and q.price > lastH.price: ev.append((t, "BUY"))
        lastH = q
    else:
        if lastL is not None and q.price < lastL.price: ev.append((t, "SELL"))
        lastL = q
def h4_at(t):
    s = [x for x in ev if x[0] <= t]
    return s[-1][1] if s else None
for name in sys.argv[1:]:
    d = pd.read_pickle(S + "\\" + name)
    d["h4"] = [h4_at(t) for t in d.fill_t]
    d["side"] = ["BUY" if b else "SELL" for b in d.buy]
    d["with_h4"] = d.h4 == d.side
    g = d.groupby("with_h4").agg(n=("R", "size"), won=("why", lambda w: (w == "target").mean()), R=("R", "sum"), per=("R", "mean"))
    print(name); print(g.round(3).to_string())
