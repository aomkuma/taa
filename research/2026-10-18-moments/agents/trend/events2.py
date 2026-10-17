"""Breakouts of the range before a session ("prior range"), same context columns as events.py:

- lon_asia: the range 00:00 UTC .. 08:00 London, broken 08:00 .. 10:00 London;
- ny_lon:   the range 08:00 London .. 08:30 ET, broken 08:30 .. 10:30 ET;
- asia_open: the range 22:00 .. 00:00 UTC (the day's first hours after the break), broken 00:00 .. 02:00 UTC;
- ny_pre:   the range 07:00 .. 08:30 ET, broken 08:30 .. 10:30 ET.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/events2.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402

OUT = "research/2026-10-18-moments/agents/trend/prior_events.parquet"


def specs(d: pd.Timestamp) -> dict[str, tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    day = d.date()
    lon8 = pd.Timestamp(f"{day} 08:00", tz=lab.LON).tz_convert("UTC")
    lon10 = pd.Timestamp(f"{day} 10:00", tz=lab.LON).tz_convert("UTC")
    ny7 = pd.Timestamp(f"{day} 07:00", tz=lab.NY).tz_convert("UTC")
    ny830 = pd.Timestamp(f"{day} 08:30", tz=lab.NY).tz_convert("UTC")
    ny1030 = pd.Timestamp(f"{day} 10:30", tz=lab.NY).tz_convert("UTC")
    u0 = pd.Timestamp(day, tz="UTC")
    return {
        "lon_asia": (u0, lon8, lon10),
        "ny_lon": (lon8, ny830, ny1030),
        "asia_open": (u0 - pd.Timedelta(hours=2), u0, u0 + pd.Timedelta(hours=2)),
        "ny_pre": (ny7, ny830, ny1030),
    }


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    s = pd.DataFrame({"o": B.o, "h": B.h, "l": B.lo, "c": B.c}, index=B.ot)
    h1 = s.resample("60min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    e20 = h1.c.ewm(span=20, adjust=False).mean()
    e50 = h1.c.ewm(span=50, adjust=False).mean()
    h1["up"] = (e20 > e20.shift(3)) & (h1.c > e50)
    h1["dn"] = (e20 < e20.shift(3)) & (h1.c < e50)
    h1["slope"] = e20 - e20.shift(3)
    d1 = s.resample("1D").agg({"h": "max", "l": "min", "c": "last"}).dropna()
    d1 = d1[d1.index.dayofweek < 5]
    adr = (d1.h - d1.l).rolling(20).mean().shift(1)
    rows = []
    for d in pd.bdate_range("2021-10-01", "2026-10-15", inclusive="left"):
        day = pd.Timestamp(d.date(), tz="UTC")
        if day not in adr.index or np.isnan(adr.loc[day]):
            continue
        for name, (a, b, c) in specs(d).items():
            ea, eb, ec = B.idx_at(a), B.idx_at(b), B.idx_at(c)
            if eb - ea < 30 or ec - eb < 30 or ec >= len(B.o) - 300:
                continue
            hi, lo = B.h[ea:eb].max(), B.lo[ea:eb].min()
            cl = B.c[eb:ec]
            up, dn = np.flatnonzero(cl > hi), np.flatnonzero(cl < lo)
            ju = up[0] if len(up) else 10**9
            jd = dn[0] if len(dn) else 10**9
            if ju == jd:
                continue
            side, j = (1, ju) if ju < jd else (-1, jd)
            k = eb + j
            td = B.ot[k] + pd.Timedelta(minutes=1)
            hk = h1.index.searchsorted(td.floor("60min") - pd.Timedelta(hours=1), side="right") - 1
            p4 = B.idx_at(b - pd.Timedelta(hours=4))
            rows.append(dict(sess=name, t=b, f=0, e=k + 1, side=side, hi=hi, lo=lo, rng=hi - lo,
                             delay=int((B.ot[k] - b).total_seconds() // 60), h1_up=bool(h1.up.iloc[hk]),
                             h1_dn=bool(h1.dn.iloc[hk]), h1_slope=float(h1.slope.iloc[hk]), adr=float(adr.loc[day]),
                             pre=float((B.o[eb] - B.o[p4]) / adr.loc[day]), px=float(B.c[k])))
    out = pd.DataFrame(rows).sort_values(["sess", "t"])
    out["or_rel"] = out.groupby("sess").rng.transform(lambda x: x / x.rolling(20, min_periods=10).mean().shift(1))
    out["half"] = out.t.map(lab.half_of)
    out.to_parquet(OUT)
    print(out.groupby("sess").agg(N=("e", "size"), rng=("rng", "median"), delay=("delay", "median")))


if __name__ == "__main__":
    main()
