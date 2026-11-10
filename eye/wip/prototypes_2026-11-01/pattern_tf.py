"""On which timeframe does "2 - 3 groups of peaks, then a far turn" happen most? [Claude, research]

Per timeframe, MT5 ZigZag 12 / 5 / 3 over 15/06 - 30/10 (pivots in July - October counted). A run up: from a fixed
LOW `L`, the fixed HIGHs that follow, each above the one before, with no LOW below the LOW before it (an LL ends the
run); pushes = how many highs. The run ends at its last high `H` (the next high is not higher, or an LL comes). The
turn after it: the lowest low from `H` until price goes above `H` again (or the data ends), as a share of the run
`H - L`. A far turn: >= 0.618 of the run. Runs down mirrored. Reported per pushes 1 / 2 / 3 / 4+: runs and the share
with a far turn - the pattern is "2 - 3 pushes, then a far turn"."""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from eye import bot2e, walk

TH = bot2e.TH
FAR = float(sys.argv[1]) if len(sys.argv) > 1 else 0.618
out = []
for tf in ("M5", "M15", "M30", "H1", "H4"):
    df = walk.frame(tf)
    df = df[(df.index >= "2026-03-01" if tf == "H4" else df.index >= "2026-06-15") & (df.index < "2026-10-31")]
    pv = bot2e._zigzag(df)
    hi, lo = df.high.to_numpy(), df.low.to_numpy()
    for sign in (1, -1):  # 1: runs up (pushes = HIGHs), -1: runs down
        top = "HIGH" if sign > 0 else "LOW"
        i = 0
        while i < len(pv):
            if pv[i].kind.value == top or i + 1 >= len(pv):
                i += 1; continue
            start = pv[i]; pushes = 0; last = None; j = i + 1; prev_low = start
            while j < len(pv):
                q = pv[j]
                if q.kind.value == top:
                    if last is None or (q.price - last.price) * sign > 0:
                        pushes += 1; last = q
                    else:
                        break
                else:
                    if (q.price - prev_low.price) * sign < 0:
                        break  # an LL (HH for a run down) ends the run
                    prev_low = q
                j += 1
            if last is None:
                i += 1; continue
            when = df.index[last.pivot_pos].tz_convert(TH)
            run = abs(last.price - start.price)
            k = last.pivot_pos + 1
            beyond = np.where((hi[k:] > last.price) if sign > 0 else (lo[k:] < last.price))[0]
            stop = k + (beyond[0] if len(beyond) else len(hi) - k)
            ext = lo[k:stop].min() if sign > 0 else hi[k:stop].max()
            turn = abs(last.price - ext) / run if run > 0 and stop > k else 0.0
            if pd.Timestamp("2026-07-01", tz=TH) <= when < pd.Timestamp("2026-10-31", tz=TH):
                out.append((tf, min(pushes, 4), turn >= FAR, run))
            i = max(i + 1, j - 1)
d = pd.DataFrame(out, columns=["tf", "pushes", "far", "run"])
t = d.groupby(["tf", "pushes"]).agg(runs=("far", "size"), far=("far", "mean")).unstack("pushes")
print(f"far turn = at least {FAR} of the run; July - October")
print(t.round(2).to_string())
pat = d[d.pushes.isin([2, 3])].groupby("tf").agg(pattern=("far", "sum"), runs23=("far", "size"), far23=("far", "mean"))
one = d[d.pushes == 1].groupby("tf").far.mean().rename("far_after_1")
print((pat.join(one)).round(2).to_string())
