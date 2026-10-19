"""Q6 - the owner's three window opens: does the first leg FAKE (the owner: "Asia often makes a small fake move before
going the big way") or CONTINUE, and does an opening-range break pay? On M1 bars (mlib's cost model), P1 / P2.

Written before computing (all rules fixed here; nothing chosen from the results):
- the opens: Asia 07:00 Thai (00:00 UTC), London 13:00 Thai (06:00 UTC), New York 09:30 New York (DST-aware); weekdays.
- H = the ATR(14) of the last H1 bar complete before the open; p0 = the close of the M1 bar before the open.
- the first leg: the first M1 bar in the first 15 minutes whose high >= p0 + 0.3 H or low <= p0 - 0.3 H (both in one
  bar: the larger excursion) sets the leg's side; its extreme = the leg's furthest price up to the decision.
- FADE (the developer's P5 family 6): within 60 minutes of the open, the first M1 close beyond p0 against the leg ->
  enter the other way at the next bar's open; stop = the leg's extreme + 0.1 H; target 2 R; out 60 minutes after the
  entry at the latest.
- FOLLOW: at the close of the bar that set the leg (if it closed beyond p0 + 0.3 H the leg's way; else no trade),
  enter the leg's way at the next open; stop = p0 -/+ 0.1 H (the move undone); target 2 R; 60 minutes.
- ORB15: the high / low of the first 15 M1 bars; the first close beyond it in the next 60 minutes -> that way at the
  next open; stop = the range's other side (no trade if the range > 1.5 H); target 2 R; 60 minutes.
Reported per open x part (n, R with its 95 % range, win, USD at 0.01 lot, exits). One trade per rule per open.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/opens.py > .../strategist/out_opens.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import mlib
import slib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import foundation as F  # noqa: E402
import indicators  # noqa: E402

m = slib.m1("2025-09-15")
o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
spr = m.spread.to_numpy(float) * 0.01 + 0.08
ti = m.index.asi8
h1 = indicators.bars(m, "1h")
atr = F.atr(h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float), 14)
h_av = pd.DatetimeIndex(h1["avail"]).as_unit("ns").asi8
MIN = 60 * 10**9


def opens_of(day: pd.Timestamp) -> list[tuple[str, pd.Timestamp]]:
    d = day.tz_localize(None)
    return [("Asia", (d + pd.Timedelta(hours=7)).tz_localize(slib.TH).tz_convert("UTC")),
            ("London", (d + pd.Timedelta(hours=13)).tz_localize(slib.TH).tz_convert("UTC")),
            ("NY", (d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC"))]


rows = []
for day in pd.bdate_range("2025-10-20", "2026-04-17"):
    for name, t0 in opens_of(day):
        part = slib.part_of(pd.DatetimeIndex([t0]))[0]
        if part == "":
            continue
        i0 = np.searchsorted(ti, t0.value)  # the first bar at / after the open
        if i0 >= len(ti) or i0 == 0 or ti[i0] - t0.value > 5 * MIN:
            continue
        j = indicators.at(h_av, np.array([t0.value]))[0]
        if j < 0 or not np.isfinite(atr[j]):
            continue
        H, p0 = atr[j], c[i0 - 1]
        i15 = np.searchsorted(ti, t0.value + 15 * MIN)
        i60 = np.searchsorted(ti, t0.value + 60 * MIN)
        nyslip = 0.20 if name == "NY" else 0.15

        def add(rule, i_in, side, stop):
            if i_in >= len(o):
                return
            e = o[i_in] + spr[i_in] + 0.07 if side > 0 else o[i_in] - 0.07
            risk = (e - stop) * side
            if risk <= 0:
                return
            i_last = np.searchsorted(ti, ti[i_in] + 60 * MIN) - 1
            r = mlib.trade(o, h, lo, c, spr, i_in, side, stop, e + side * 2 * risk, i_last, nyslip)
            if r:
                rows.append(dict(rule=rule, open=name, part=part, day=day, side=side, pnl=r[0], risk=r[1], R=r[0] / r[1],
                                 exit=r[2], H=H))

        # the first leg
        leg, k_leg = 0, -1
        for k in range(i0, i15):
            up, dn = h[k] - p0, p0 - lo[k]
            if up >= 0.3 * H or dn >= 0.3 * H:
                leg = 1 if up >= dn else -1
                k_leg = k
                break
        if leg:
            # FOLLOW
            if (c[k_leg] - p0) * leg >= 0.3 * H:
                add("FOLLOW", k_leg + 1, leg, p0 - leg * 0.1 * H)
            # FADE
            ext = h[k_leg] if leg > 0 else lo[k_leg]
            for k in range(k_leg, i60):
                ext = max(ext, h[k]) if leg > 0 else min(ext, lo[k])
                if (c[k] - p0) * leg < 0:
                    add("FADE", k + 1, -leg, ext + leg * 0.1 * H)
                    break
        # ORB15
        rh, rl = h[i0:i15].max(), lo[i0:i15].min()
        if rh - rl <= 1.5 * H:
            for k in range(i15, i15 + 60):
                if k >= len(c):
                    break
                if c[k] > rh:
                    add("ORB15", k + 1, 1, rl)
                    break
                if c[k] < rl:
                    add("ORB15", k + 1, -1, rh)
                    break

T = pd.DataFrame(rows)
T.to_parquet(slib.HERE / "opens_trades.parquet")
for rule in ("FADE", "FOLLOW", "ORB15"):
    print(f"=== {rule}")
    for name in ("Asia", "London", "NY"):
        for p in ("P1", "P2"):
            x = T[(T.rule == rule) & (T.open == name) & (T.part == p)]
            print(f"  {name:6s} {p}: {slib.row(x)}  risk/H {np.median(x.risk / x.H) if len(x) else np.nan:.2f}"
                  f"  exits {x.exit.value_counts().to_dict()}")
    for p in ("P1", "P2"):
        x = T[(T.rule == rule) & (T.part == p)]
        print(f"  all    {p}: {slib.row(x)}")
