"""New York continuation (design data only unless --test): at a New York checkpoint (09:30 / 09:45 / 10:00 /
10:30 ET), trade the day's direction so far for up to 2-3 hours.

Event columns (all known at the decision = the close of the bar ending at the checkpoint):
- m: the day's move from 00:00 UTC to the checkpoint, in ADR20 units (side = its sign);
- pos: where the close sits in the day's range so far (0 = low, 1 = high), signed into "at the extreme" by side;
- h1w: the last closed H1 bar's trend agrees with the side (EMA20 rising over 3 bars and close above EMA50 for a
  BUY, the mirror for a SELL); h1a: it is against the side;
- orb: the close is beyond the 08:30-09:30 ET range in the side's direction (only for checkpoints >= 09:30 + 1 bar);
- pre: the move over the 4 hours before 08:30 ET, in ADR units, signed by the side.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/nycont.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402
import sim  # noqa: E402

OUT = "research/2026-10-18-moments/agents/trend/nycont_events.parquet"
CHECKS = ("09:30", "09:45", "10:00", "10:30", "11:00")


def build(B: lab.Bars) -> pd.DataFrame:
    s = pd.DataFrame({"o": B.o, "h": B.h, "l": B.lo, "c": B.c}, index=B.ot)
    h1 = s.resample("60min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    e20 = h1.c.ewm(span=20, adjust=False).mean()
    e50 = h1.c.ewm(span=50, adjust=False).mean()
    up = ((e20 > e20.shift(3)) & (h1.c > e50)).to_numpy()
    dn = ((e20 < e20.shift(3)) & (h1.c < e50)).to_numpy()
    d1 = s.resample("1D").agg({"h": "max", "l": "min"}).dropna()
    d1 = d1[d1.index.dayofweek < 5]
    adr = (d1.h - d1.l).rolling(20).mean().shift(1)
    rows = []
    for d in pd.bdate_range("2021-10-01", "2026-10-15", inclusive="left"):
        day = pd.Timestamp(d.date(), tz="UTC")
        if day not in adr.index or np.isnan(adr.loc[day]):
            continue
        A = adr.loc[day]
        e0 = B.idx_at(day)
        r0 = B.idx_at(pd.Timestamp(f"{d.date()} 08:30", tz=lab.NY).tz_convert("UTC"))
        r1 = B.idx_at(pd.Timestamp(f"{d.date()} 09:30", tz=lab.NY).tz_convert("UTC"))
        if r1 - r0 < 50 or B.ot[e0].normalize() != day:
            continue
        orh, orl = B.h[r0:r1].max(), B.lo[r0:r1].min()
        p4 = B.idx_at(B.ot[r0] - pd.Timedelta(hours=4))
        for ck in CHECKS:
            t = pd.Timestamp(f"{d.date()} {ck}", tz=lab.NY).tz_convert("UTC")
            e = B.idx_at(t)  # entry bar; the decision at the close of bar e-1
            if e >= len(B.o) - 300 or B.ot[e] - t > pd.Timedelta(minutes=3):
                continue
            k = e - 1
            dhi, dlo = B.h[e0 : e].max(), B.lo[e0 : e].min()
            m = (B.c[k] - B.o[e0]) / A
            side = 1 if m > 0 else -1
            pos = (B.c[k] - dlo) / max(dhi - dlo, 1e-9)
            td = B.ot[k] + pd.Timedelta(minutes=1)
            hk = h1.index.searchsorted(td.floor("60min") - pd.Timedelta(hours=1), side="right") - 1
            orb = (B.c[k] > orh) if side > 0 else (B.c[k] < orl)
            rows.append(dict(t=t, ck=ck, e=e, side=side, m=m, absm=abs(m), ext=pos if side > 0 else 1 - pos,
                             h1w=bool(up[hk] if side > 0 else dn[hk]), h1a=bool(dn[hk] if side > 0 else up[hk]),
                             orb=bool(orb) and ck != "09:30", pre=float((B.o[r0] - B.o[p4]) / A * side), adr=A,
                             dayrng=(dhi - dlo) / A, orrng=(orh - orl) / A,
                             hi=orh, lo=orl, px=B.c[k]))
    d = pd.DataFrame(rows)
    d["half"] = d.t.map(lab.half_of)
    return d


def evaluate(B, d: pd.DataFrame, side: np.ndarray, stopk: float, exit_: str, hz: int, kinds_tp: float = 2.0) -> pd.DataFrame:
    P = sim.paths(B, d.e.to_numpy(), side, 260)
    risk = stopk * d.adr.to_numpy()
    kw: dict = {}
    tp = None
    if exit_.startswith("trail"):
        a, b = (float(x) for x in exit_[5:].split("/"))
        kw = dict(trail=a * risk, trail_start=b * risk)
    elif exit_.startswith("tp"):
        tp = float(exit_[2:]) * risk
    o = sim.run(P, risk, tp, hz, kind_tp=(tp if tp is not None else kinds_tp * risk), **kw)
    return pd.DataFrame(dict(t=d.t.to_numpy(), side=side, usd=o["usd"], R=o["R"], exit=o["exit"], mins=o["mins"],
                             kind=o["kind"], risk=risk, half=d.half.to_numpy()))


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    d = build(B)
    d.to_parquet(OUT)
    print(d.groupby("ck").size())


if __name__ == "__main__":
    main()
