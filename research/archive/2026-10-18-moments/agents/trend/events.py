"""Opening-range breakout events with their context, for every weekday 2021-09-01 .. 2026-10-14 (all sessions).

For each session open (Asia 00:00 UTC, London 08:00 London, New York 08:30 and 09:30 ET) and opening-range
length f (15, 30, 60 minutes): the first M1 bar after the range whose close is beyond the range's high (BUY) or
low (SELL), within 120 minutes of the range's end. Decision at that bar's close, entry at the next bar's open.

Context (all known at the decision; nothing from bars at or after the entry bar):
- h1_up / h1_dn: the last closed H1 bar's EMA20 rising over 3 bars and the H1 close above / below EMA50;
- adr: the mean daily (UTC) high-low range of the previous 20 complete days;
- or_rel: the range's size / the mean of this session's range over the previous 20 sessions;
- pre: the move over the 4 hours before the session open, in ADR units (signed later by the side);
- delay: minutes from the range's end to the breakout bar.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/events.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402

OUT = "research/2026-10-18-moments/agents/trend/orb_events.parquet"


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    s = pd.DataFrame({"o": B.o, "h": B.h, "l": B.lo, "c": B.c}, index=B.ot)
    h1 = s.resample("60min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    e20 = h1.c.ewm(span=20, adjust=False).mean()
    e50 = h1.c.ewm(span=50, adjust=False).mean()
    h1["up"] = (e20 > e20.shift(3)) & (h1.c > e50)
    h1["dn"] = (e20 < e20.shift(3)) & (h1.c < e50)
    h1["slope"] = (e20 - e20.shift(3))
    d1 = s.resample("1D").agg({"h": "max", "l": "min", "c": "last"}).dropna()
    d1 = d1[d1.index.dayofweek < 5]
    adr = (d1.h - d1.l).rolling(20).mean().shift(1)  # known at the start of each day
    opens = lab.session_opens(B.ot, "2021-10-01", "2026-10-15")
    rows = []
    for sess, ts in opens.items():
        for t in ts:
            e0 = B.idx_at(t)
            if e0 >= len(B.o) - 400 or B.ot[e0] - t > pd.Timedelta(minutes=2):
                continue
            day = t.normalize()
            if day not in adr.index or np.isnan(adr.loc[day]):
                continue
            p4 = B.idx_at(t - pd.Timedelta(hours=4))
            pre = (B.o[e0] - B.o[p4]) / adr.loc[day]
            for f in (15, 30, 60):
                ef = B.idx_at(t + pd.Timedelta(minutes=f))
                if ef - e0 < f - 3:
                    continue
                hi, lo = B.h[e0:ef].max(), B.lo[e0:ef].min()
                lim = B.idx_at(t + pd.Timedelta(minutes=f + 120))
                c = B.c[ef:lim]
                up = np.flatnonzero(c > hi)
                dn = np.flatnonzero(c < lo)
                ju = up[0] if len(up) else 10**9
                jd = dn[0] if len(dn) else 10**9
                if ju == jd:
                    continue
                side, j = (1, ju) if ju < jd else (-1, jd)
                k = ef + j  # the breakout bar (decision at its close)
                e = k + 1
                td = B.ot[k] + pd.Timedelta(minutes=1)
                hk = h1.index.searchsorted(td.floor("60min") - pd.Timedelta(hours=1), side="right") - 1
                rows.append(dict(sess=sess, t=t, f=f, e=e, side=side, hi=hi, lo=lo, rng=hi - lo,
                                 delay=int((B.ot[k] - t).total_seconds() // 60) - f + 1,
                                 h1_up=bool(h1.up.iloc[hk]), h1_dn=bool(h1.dn.iloc[hk]),
                                 h1_slope=float(h1.slope.iloc[hk]), adr=float(adr.loc[day]), pre=float(pre),
                                 px=float(B.c[k])))
    d = pd.DataFrame(rows)
    d = d.sort_values(["sess", "f", "t"])
    d["or_rel"] = d.groupby(["sess", "f"]).rng.transform(lambda x: x / x.rolling(20, min_periods=10).mean().shift(1))
    d["half"] = d.t.map(lab.half_of)
    d.to_parquet(OUT)
    print(d.groupby(["sess", "f"]).size())
    print(d.describe().T)


if __name__ == "__main__":
    main()
