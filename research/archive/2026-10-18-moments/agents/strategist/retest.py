"""Q7 - break and retest of the levels everyone sees (the owner's trade 4 mechanism; Osler 2003: stops cluster just
beyond levels, so a broken level, once retested and rejected, gives the continuation). A crude prior for dev2's V3-2,
not its rule: horizontal levels only (dev2 adds trendlines / boxes).

Written before computing (M5 decisions from M1 bars, mlib costs, P1 / P2):
- levels per server day (Europe/Athens): the previous server day's high / low (PDH / PDL, known from the day's
  start) and the Asian range high / low (00:00-06:00 UTC = 07:00-13:00 Thai, known from 06:00 UTC); H = the H1
  ATR(14) at the decision.
- the break of a support L: the first M5 close < L - 0.1 H after the level is known, with the previous M5 close >= L
  (from above); resistance mirrored. One break per level per day.
- the retest: within 36 M5 bars of the break, the first bar whose high >= L - 0.15 H (back to the level from below);
  cancelled if an M5 close > L + 0.75 H comes first or before the entry (the break failed).
- the entry: after the retest bar r, the first M5 close below the lowest low of bars r .. k-1 (the turn), with that
  close < L + 0.5 H, within 12 bars of r -> sell at the next M1 open. Stop = the highest high since r + 0.25 H
  (trade 4: about 3 USD over the retest high); target 2 R; out after 120 minutes. Mirrored for a broken resistance.
- reported all hours and inside the owner's windows (Asia 07-09 Thai, 13-14 Thai, 09:30-11:30 NY) by the entry
  time; per level kind; one position at a time is NOT applied (each event alone - the event's own effect).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/retest.py > .../strategist/out_retest.txt
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

import os  # noqa: E402

m = slib.m1(os.environ.get("STRAT_START", "2025-09-15"))  # the older-years read sets 2023-09-15
o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
spr = m.spread.to_numpy(float) * 0.01 + 0.08
ti = m.index.asi8
MIN = 60 * 10**9
h1 = indicators.bars(m, "1h")
atr = F.atr(h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float), 14)
h_av = pd.DatetimeIndex(h1["avail"]).as_unit("ns").asi8
m5 = indicators.bars(m, "5min")
m5_av = pd.DatetimeIndex(m5["avail"]).as_unit("ns").asi8
H5, L5, C5 = (m5[k].to_numpy(float) for k in ("high", "low", "close"))
sday = m.index.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
m5_day = pd.DatetimeIndex(m5["last"]).tz_convert("Europe/Athens").tz_localize(None).floor("1D")
D = pd.DataFrame({"h": h, "l": lo, "d": sday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))


def in_window(t: pd.Timestamp) -> str:
    th = t.tz_convert(slib.TH)
    mins = th.hour * 60 + th.minute
    if 420 <= mins < 540:
        return "Asia"
    if 780 <= mins < 840:
        return "London"
    ny = t.tz_convert("America/New_York")
    nm = ny.hour * 60 + ny.minute
    if 570 <= nm < 690:
        return "NY"
    return "other"


def idx_of_day(d):
    """The M5 bars of server day d and its levels (kind, price, +1 top / -1 low, known-from ns), or None."""
    prev = D.index[D.index < d]
    if not len(prev):
        return None
    pdh, pdl = D.loc[prev[-1], "h"], D.loc[prev[-1], "l"]
    idx = np.where(m5_day == d)[0]
    if len(idx) < 50:
        return None
    day_start_ns = m5_av[idx[0]] - 5 * MIN
    asia_s = pd.Timestamp(d.date(), tz="UTC").value  # 00:00 UTC of the server day's date
    asia_e = asia_s + 6 * 60 * MIN
    a_bars = idx[(m5_av[idx] > asia_s) & (m5_av[idx] <= asia_e)]
    levels = [("PDH", pdh, 1, day_start_ns), ("PDL", pdl, -1, day_start_ns)]
    if len(a_bars) >= 60:
        levels += [("ASH", H5[a_bars].max(), 1, asia_e), ("ASL", L5[a_bars].min(), -1, asia_e)]
    return idx, levels


def main() -> None:
  rows = []
  days = D.index[(D.index >= pd.Timestamp("2025-10-18")) & (D.index < pd.Timestamp("2026-04-18"))]
  for d in days:
    got = idx_of_day(d)
    if got is None:
        continue
    idx, levels = got
    for kind, L, top, known in levels:
        # a top level (resistance) breaks upward -> a buy on the retest; a low level (support) breaks down -> a sell
        side = 1 if top == 1 else -1
        cand = idx[m5_av[idx] > known]
        if len(cand) < 3:
            continue
        b = None
        for q in range(1, len(cand)):
            k, kp = cand[q], cand[q - 1]
            j = indicators.at(h_av, np.array([m5_av[k]]))[0]
            Hk = atr[j]
            if side < 0 and C5[k] < L - 0.1 * Hk and C5[kp] >= L:
                b = (q, Hk)
                break
            if side > 0 and C5[k] > L + 0.1 * Hk and C5[kp] <= L:
                b = (q, Hk)
                break
        if b is None:
            continue
        q0, Hk = b
        r = None
        for q in range(q0 + 1, min(q0 + 37, len(cand))):
            k = cand[q]
            if (C5[k] - L) * side < -0.75 * Hk:  # closed back through the level by 0.75 H: the break failed
                break
            if (side < 0 and H5[k] >= L - 0.15 * Hk) or (side > 0 and L5[k] <= L + 0.15 * Hk):
                r = q
                break
        if r is None:
            continue
        ext = H5[cand[r]] if side < 0 else L5[cand[r]]
        lowest = L5[cand[r]] if side < 0 else H5[cand[r]]
        for q in range(r + 1, min(r + 13, len(cand))):
            k = cand[q]
            if (C5[k] - L) * side < -0.75 * Hk:
                break
            turned = (C5[k] < lowest) if side < 0 else (C5[k] > lowest)
            if turned and (C5[k] - L) * side > -0.5 * Hk:
                t_dec = m5_av[k]
                i_in = np.searchsorted(ti, t_dec)
                if i_in >= len(ti):
                    break
                stop = ext + 0.25 * Hk if side < 0 else ext - 0.25 * Hk
                e = o[i_in] + spr[i_in] + 0.07 if side > 0 else o[i_in] - 0.07
                risk = (e - stop) * side
                if risk > 0:
                    i_last = np.searchsorted(ti, ti[i_in] + 120 * MIN) - 1
                    t_in = pd.Timestamp(ti[i_in], tz="UTC")
                    res = mlib.trade(o, h, lo, c, spr, i_in, side, stop, e + side * 2 * risk, i_last,
                                     0.20 if in_window(t_in) == "NY" else 0.15)
                    if res:
                        rows.append(dict(day=d, kind=kind, side=side, t=t_in, part=slib.part_of(pd.DatetimeIndex([t_in]))[0],
                                         win=in_window(t_in), pnl=res[0], risk=res[1], R=res[0] / res[1], exit=res[2], H=Hk))
                break
            ext = max(ext, H5[k]) if side < 0 else min(ext, L5[k])
            lowest = min(lowest, L5[k]) if side < 0 else max(lowest, H5[k])

  T = pd.DataFrame(rows)
  T = T[T.part != ""]
  T.to_parquet(slib.HERE / "retest_trades.parquet")
  print(f"events per weekday: P1 {len(T[T.part == 'P1']) / 63:.2f}, P2 {len(T[T.part == 'P2']) / 64:.2f}; "
        f"median risk / H {np.median(T.risk / T.H):.2f}, median risk USD {T.risk.median():.1f}")
  for p in ("P1", "P2"):
      x = T[T.part == p]
      print(f"{p} all hours   {slib.row(x)}  exits {x.exit.value_counts().to_dict()}")
      print(f"{p} in windows  {slib.row(x[x.win != 'other'])}")
      for w in ("Asia", "London", "NY", "other"):
          print(f"   {p} {w:7s} {slib.row(x[x.win == w])}")
      for k in ("PDH", "PDL", "ASH", "ASL"):
          print(f"   {p} {k}     {slib.row(x[x.kind == k])}")


if __name__ == "__main__":
    main()
