"""Counting the pushes [Claude, research]: on M15 fixed pivots, a run of pushes = successive HHs (each fixed HIGH
above the one before, the lows between not making an LL) - push 1, 2, 3 ...; the run ends at the first high that is
not higher. After push n (a HIGH), the next move down = that high minus the next fixed LOW, compared with the push's
own leg (the low before the high to the high). Mirrored for LLs. If the owner's 2-3 groups then a far turn holds,
the move after push 3 is larger (in USD and x its leg) than after push 1 - 2."""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e
m15 = bot2e.load_frames()["M15"]; m15 = m15[(m15.index >= "2026-06-01") & (m15.index < "2026-10-31")]
pv = bot2e._zigzag(m15); TH = bot2e.TH
rows = []
for sign, kind in ((1, "HIGH"), (-1, "LOW")):
    n = 0
    for i in range(2, len(pv) - 1):
        q = pv[i]
        if q.kind.value != kind: continue
        p = pv[i - 2]
        if (q.price - p.price) * sign > 0 and (pv[i - 1].price - pv[i - 3].price) * sign > 0 if i >= 3 else False:
            n += 1
        elif (q.price - p.price) * sign > 0:
            n = 1
        else:
            n = 0; continue
        if m15.index[q.pivot_pos].tz_convert(TH) < pd.Timestamp("2026-07-01", tz=TH): continue
        leg = abs(q.price - pv[i - 1].price); after = abs(q.price - pv[i + 1].price)
        rows.append((n, after, after / leg))
d = pd.DataFrame(rows, columns=["push", "after_usd", "after_x_leg"]); d["push"] = d.push.clip(upper=5)
print(d.groupby("push").agg(n=("after_usd", "size"), after_usd_median=("after_usd", "median"),
      after_x_leg_median=("after_x_leg", "median"), deep_ge_1x=("after_x_leg", lambda x: (x >= 1).mean())).round(2).to_string())
