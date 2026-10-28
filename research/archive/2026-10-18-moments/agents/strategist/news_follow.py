"""Q5 - the US data minutes as a CONTINUATION trade (the side the market shows in the first minute), on the ticks.

Why: the developer's A1 counts (dev/a1_detections.parquet) show that after the 08:30 / 10:00 NY minute the first
minute's move CONTINUES (a new extreme 3 USD past) 3-5 x more often than it fakes; the developer's P4 found its B2
pattern trades worst at 10:00-10:30 NY (-0.298 / -0.208 R) - reversal patterns run over by the data's continuation.
S2 (CPI / NFP straddle, on DEMO) is the only rule positive on its test. Task A3 (the trade from the paths) was never
finished: the developer moved to Task P.

Written before computing (P1 / P2 only; every weekday's 08:30 and 10:00 New York minute, DST-aware; t0 = the minute):
- mid0 = the last tick's mid before t0; mid1 = the last tick's mid before t0 + 60 s; d1 = mid1 - mid0.
- FOLLOW: if |d1| >= 3 USD, trade sign(d1) at the first tick at / after t0 + 60 s (a buy at the ask + 0.07 + extra, a
  sell at the bid - 0.07 - extra); stop at mid0 - side x 1 USD (1 USD past the release price: the move undone);
  exits: (a) time 15 min after t0, (b) time 30 min, (c) target 2 R with time 30 min. Stops fill at the first tick at /
  beyond (bid for a buy, ask for a sell), gap included.
- STRADDLE: the S2 shape on every one of these minutes: a buy stop at the ask at t0 + 2, a sell stop at the bid at t0 -
  2, live 60 s, the first hit; stop 8 USD from the fill; exits (a) 15 min, (b) 30 min.
- extra = 0 and 1 USD (the team's news cost); R = pnl / the fill's risk. Reported per part and per minute (08:30 /
  10:00). No setting is picked here: all are printed. One position per minute; none overlap.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/news_follow.py > .../strategist/out_news_follow.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import slib

SLIP = 0.07
NS = 10**9


def fill(t, bid, ask, t_in, side, extra):
    f = np.searchsorted(t, t_in, side="left")
    if f >= len(t):
        return None
    px = ask[f] + SLIP + extra if side > 0 else bid[f] - SLIP - extra
    return f, px


def run_trade(t, bid, ask, f, entry, side, stop, target, t_out):
    """From tick f on: the stop (gap included), the target as a limit, the time. Returns (pnl, exit name)."""
    for k in range(f + 1, len(t)):
        if t[k] >= t_out:
            px = bid[k] if side > 0 else ask[k]
            return (px - entry) * side, "time"
        px = bid[k] if side > 0 else ask[k]
        if (px - stop) * side <= 0:
            return (px - entry) * side, "stop"
        if target is not None and (px - target) * side >= 0:
            return (target - entry) * side, "target"
    return None


def last_mid(t, bid, ask, tq):
    i = np.searchsorted(t, tq, side="left") - 1
    return (bid[i] + ask[i]) / 2 if i >= 0 else np.nan


def main() -> None:
    rows = []
    days = pd.bdate_range("2025-10-20", "2026-04-17", tz="UTC")
    for day in days:
        x = slib.ticks(day)
        if x is None or len(x) < 1000:
            continue
        t = x.t.dt.as_unit("ns").astype("int64").to_numpy()
        bid, ask = x.bid.to_numpy(float), x.ask.to_numpy(float)
        for hm in ("08:30", "10:00"):
            t0 = pd.Timestamp(f"{day:%Y-%m-%d} {hm}").tz_localize("America/New_York").tz_convert("UTC")
            t0n = t0.value
            if t0n < t[0] + 600 * NS or t0n + 1800 * NS > t[-1]:
                continue
            mid0 = last_mid(t, bid, ask, t0n)
            mid1 = last_mid(t, bid, ask, t0n + 60 * NS)
            d1 = mid1 - mid0
            part = slib.part_of(pd.DatetimeIndex([t0]))[0]
            for extra in (0.0, 1.0):
                if abs(d1) >= 3:
                    side = int(np.sign(d1))
                    fl = fill(t, bid, ask, t0n + 60 * NS, side, extra)
                    if fl:
                        f, e = fl
                        stop = mid0 - side * 1.0
                        risk = (e - stop) * side
                        if risk > 0:
                            for lab, tgt, tout in (("FOLLOW 15m", None, 15), ("FOLLOW 30m", None, 30),
                                                   ("FOLLOW 2R/30m", e + side * 2 * risk, 30)):
                                r = run_trade(t, bid, ask, f, e, side, stop, tgt, t0n + tout * 60 * NS)
                                if r:
                                    rows.append(dict(rule=lab, extra=extra, hm=hm, part=part, day=day, side=side,
                                                     risk=risk, pnl=r[0], R=r[0] / risk, exit=r[1]))
                # the straddle
                i0 = np.searchsorted(t, t0n, side="left") - 1
                up, dn = ask[i0] + 2, bid[i0] - 2
                k = np.searchsorted(t, t0n, side="left")
                k_end = np.searchsorted(t, t0n + 60 * NS, side="left")
                hit = None
                for j in range(k, k_end):
                    if ask[j] >= up:
                        hit = (j, 1, max(up, ask[j]) + SLIP + extra)
                        break
                    if bid[j] <= dn:
                        hit = (j, -1, min(dn, bid[j]) - SLIP - extra)
                        break
                if hit:
                    j, side, e = hit
                    stop = e - side * 8
                    for lab, tout in (("STRADDLE 15m", 15), ("STRADDLE 30m", 30)):
                        r = run_trade(t, bid, ask, j, e, side, stop, None, t0n + tout * 60 * NS)
                        if r:
                            rows.append(dict(rule=lab, extra=extra, hm=hm, part=part, day=day, side=side, risk=8.0,
                                             pnl=r[0], R=r[0] / 8.0, exit=r[1]))

    T = pd.DataFrame(rows)
    T.to_parquet(slib.HERE / "news_follow_trades.parquet")
    for (rule, extra), g in T.groupby(["rule", "extra"]):
        print(f"=== {rule}, extra cost {extra:.0f} USD")
        for p in ("P1", "P2"):
            x = g[g.part == p]
            print(f"   {p} all    {slib.row(x)}  median risk {x.risk.median():.1f}  exits {x.exit.value_counts().to_dict()}")
            for hm in ("08:30", "10:00"):
                print(f"   {p} {hm}  {slib.row(x[x.hm == hm])}")


if __name__ == "__main__":
    main()
