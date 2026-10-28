"""Q3 - gold's drift by the Thai clock hour, and the side of the developer's window trades.

Written before computing. Outside lead (hypothesis): gold rises in Asian hours and falls in US hours (Donati & Jung,
CBS thesis "Gold Price Dynamics Around the Clock"; Ed Steer's session split for H1 2026, Money Metals / FXStreet,
2026-07-12/13). Measured here on P1 / P2 only:
(a) for every Thai clock hour, the M1 close of the hour's last bar minus the close of the bar before the hour, in USD
    and in H1 ATR(14) units (the last H1 bar complete before the hour); mean, t-like ratio (mean / SE), share of up
    hours; per part;
(b) the owner's windows as blocks: Asia 07:00-09:00 Thai, London 13:00-14:00 Thai, NY 09:30-11:30 New York;
(c) the developer's W trades (P4) and B2 trades (P3) by side x window, per part.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/drift.py > .../strategist/out_drift.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import slib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import indicators  # noqa: E402
import foundation as F  # noqa: E402

m = slib.m1()
h1 = indicators.bars(m, "1h")
atr = F.atr(h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float), 14)
h_av = pd.DatetimeIndex(h1["avail"]).as_unit("ns").asi8

c = m.close
th = m.index.tz_convert(slib.TH)
key = th.floor("1h")
g = pd.DataFrame({"c": c.to_numpy(), "k": key, "t": m.index})
last = g.groupby("k").c.last()
first_idx = pd.DatetimeIndex(g.groupby("k")["t"].first())
# the close before the hour = the last M1 close strictly before the hour's first bar
pos = np.searchsorted(m.index.asi8, first_idx.as_unit("ns").asi8) - 1
prev = c.to_numpy()[np.clip(pos, 0, None)]
H = pd.DataFrame({"ret": last.to_numpy() - prev, "t0": first_idx}, index=last.index)
H = H[pos >= 0]
j = indicators.at(h_av, H.t0.dt.as_unit("ns").astype("int64").to_numpy())
H["atr"] = np.where(j >= 0, atr[np.clip(j, 0, None)], np.nan)
H["retn"] = H.ret / H.atr
H["part"] = slib.part_of(pd.DatetimeIndex(H.t0).tz_convert("UTC"))
H["hour"] = H.index.hour
H = H[H.part != ""]

print("(a) the Thai clock hour: mean return USD | in H1 ATR | mean/SE | share up | n   (P1 then P2)")
for hr in range(24):
    cells = []
    for p in ("P1", "P2"):
        x = H[(H.part == p) & (H.hour == hr)]
        if len(x) < 10:
            cells.append(" " * 44)
            continue
        se = x.ret.std(ddof=1) / np.sqrt(len(x))
        cells.append(f"{x.ret.mean():+6.2f} {x.retn.mean():+6.3f} {x.ret.mean() / se:+5.1f} {np.mean(x.ret > 0):.2f} {len(x):3d}")
    print(f"  {hr:02d}:00  " + "   |   ".join(cells))

# (b) the windows as blocks, per day
def block(start_utc: pd.Series, end_utc: pd.Series) -> np.ndarray:
    a = np.searchsorted(m.index.asi8, start_utc.astype("int64").to_numpy()) - 1
    b = np.searchsorted(m.index.asi8, end_utc.astype("int64").to_numpy()) - 1
    ok = (a >= 0) & (b > a)
    out = np.full(len(a), np.nan)
    out[ok] = c.to_numpy()[b[ok]] - c.to_numpy()[a[ok]]
    return out

days = pd.DatetimeIndex(sorted(set(th.normalize())))
days = days[days.dayofweek < 5]
rows = []
for d in days:
    a07 = d + pd.Timedelta(hours=7)
    rows.append(dict(day=d, asia=(a07, a07 + pd.Timedelta(hours=2)),
                     lon=(d + pd.Timedelta(hours=13), d + pd.Timedelta(hours=14))))
B = pd.DataFrame(rows)
for w in ("asia", "lon"):
    s = pd.Series([x[0] for x in B[w]]).dt.tz_convert("UTC").dt.as_unit("ns")
    e = pd.Series([x[1] for x in B[w]]).dt.tz_convert("UTC").dt.as_unit("ns")
    B[w + "_ret"] = block(s, e)
ny_s = pd.Series([(d.tz_localize(None) + pd.Timedelta(hours=9, minutes=30)) for d in days]).dt.tz_localize("America/New_York")
B["ny_ret"] = block(ny_s.dt.tz_convert("UTC").dt.as_unit("ns"), (ny_s + pd.Timedelta(hours=2)).dt.tz_convert("UTC").dt.as_unit("ns"))
B["part"] = slib.part_of(pd.DatetimeIndex(B.day).tz_convert("UTC"))
print("\n(b) the windows as blocks (close at the end minus the close before the start), per weekday")
for w, lab in (("asia_ret", "Asia 07-09 Thai"), ("lon_ret", "London 13-14 Thai"), ("ny_ret", "NY 09:30-11:30 NY")):
    for p in ("P1", "P2"):
        x = B[(B.part == p)][w].dropna()
        se = x.std(ddof=1) / np.sqrt(len(x))
        print(f"  {lab:18s} {p}: mean {x.mean():+6.2f} USD  mean/SE {x.mean() / se:+5.2f}  up {np.mean(x > 0):.2f}  n {len(x)}"
              f"  sum {x.sum():+8.1f}")

print("\n(c) the developer's trades by side x window")
for name, d in (("W (P4)", slib.dev_trades("p4_trades_W_WL.parquet", "W")),):
    for wnd in ("Asia", "London", "NY"):
        for p in ("P1", "P2"):
            x = d[(d.window == wnd) & (d.part == p)]
            print(f"  {name} {wnd:6s} {p}: buys {slib.row(x[x.side > 0])}")
            print(f"  {name} {wnd:6s} {p}: sells {slib.row(x[x.side < 0])}")
b2 = slib.dev_trades("p3_trades_all.parquet", "B2")
tth = b2.t.dt.tz_convert(slib.TH)
mins = tth.dt.hour * 60 + tth.dt.minute
b2["win"] = np.where((mins >= 420) & (mins < 540), "Asia", np.where((mins >= 780) & (mins < 840), "London", "other"))
for wnd in ("Asia", "London", "other"):
    for p in ("P1", "P2"):
        x = b2[(b2.win == wnd) & (b2.part == p)]
        print(f"  B2 (P3) {wnd:6s} {p}: buys {slib.row(x[x.side > 0])}")
        print(f"  B2 (P3) {wnd:6s} {p}: sells {slib.row(x[x.side < 0])}")
