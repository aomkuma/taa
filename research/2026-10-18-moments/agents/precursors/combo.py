"""Checklist #34 - a daily plan from the PARTIAL pieces, each in its own window (notes.md, written before it is computed;
owner, 2026-10-20: "take my input with the research and the results that were profitable, and adjust until it is
profitable"). Trades already simulated on the ticks by their owners are joined in time order, one position at a time
(a trade entering before the previous exit is dropped):
  Asia - the first developer's B2 in the Asia window (p4_trades_W_WL_WN.parquet, variant W, news cost 0);
  London - the strategist's 13:00-Thai opening-range break (orb_ticks.py's rule, re-simulated here on the ticks, with
           the entry and exit times kept);
  NY - the strategist's 08:30-NY straddle held 30 minutes (news_follow_trades.parquet, no extra slippage; and with +1
       USD as a stress).
Reported per part: trades, a weekday, win (pnl > 0), R mean with its 95 % range, USD, max DD from 0, the pooled mean.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/combo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AG = HERE.parents[0]
sys.path.insert(0, str(AG / "strategist"))
WEEKDAYS = {"P1": 64, "P2": 66}


def stream(T: pd.DataFrame) -> pd.DataFrame:
    """One position at a time: time order, a trade entering before the kept trade's exit is dropped."""
    T = T.sort_values("t_in").reset_index(drop=True)
    keep, busy = [], pd.Timestamp.min.tz_localize("UTC")
    for r in T.itertuples():
        if r.t_in < busy:
            continue
        keep.append(r.Index)
        busy = r.t_out
    return T.loc[keep]


def stats(T: pd.DataFrame, weekdays: int) -> str:
    r = T.R.to_numpy(float)
    eq = np.r_[0.0, np.cumsum(T.sort_values("t_in").pnl.to_numpy(float))]
    se = r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
    return (f"{len(r)} trades ({len(r) / weekdays:.2f} a weekday), win {np.mean(T.pnl > 0):.2f}, R {r.mean():+.3f} "
            f"({r.mean() - 1.96 * se:+.2f}..{r.mean() + 1.96 * se:+.2f}), USD {T.pnl.sum():+.1f}, max DD {(np.maximum.accumulate(eq) - eq).max():.1f}")


def london_orb() -> pd.DataFrame:
    """orb_ticks.py's ORB rule, re-simulated on the ticks, with the entry / exit times kept."""
    import slib  # noqa: PLC0415
    from news_follow import run_trade  # noqa: PLC0415

    MIN = 60 * 10**9
    m = slib.m1("2025-10-15")
    ti, c, h, lo = m.index.asi8, m.close.to_numpy(), m.high.to_numpy(), m.low.to_numpy()
    O = pd.read_parquet(AG / "strategist" / "opens_trades.parquet")
    O = O[(O.rule == "ORB15") & (O.open == "London")]
    days_ok = {pd.Timestamp(d).tz_localize(None).normalize() if pd.Timestamp(d).tzinfo is None else pd.Timestamp(d).tz_convert(None).normalize() for d in O.day}
    rows = []
    for day in pd.bdate_range("2025-10-20", "2026-04-17"):
        if day.normalize() not in days_ok:
            continue
        t0 = (day + pd.Timedelta(hours=13)).tz_localize(slib.TH).tz_convert("UTC")
        i0 = np.searchsorted(ti, t0.value)
        if i0 >= len(ti) or ti[i0] - t0.value > 5 * MIN:
            continue
        i15 = np.searchsorted(ti, t0.value + 15 * MIN)
        rh, rl = h[i0:i15].max(), lo[i0:i15].min()
        for k in range(i15, min(i15 + 60, len(c))):
            side = 1 if c[k] > rh else (-1 if c[k] < rl else 0)
            if not side:
                continue
            t_dec = int(ti[k] + MIN)
            x = slib.ticks(pd.Timestamp(t_dec, tz="UTC").normalize())
            if x is None:
                break
            t = x.t.dt.as_unit("ns").astype("int64").to_numpy()
            bid, ask = x.bid.to_numpy(float), x.ask.to_numpy(float)
            f = np.searchsorted(t, t_dec, side="left")
            if f >= len(t) or t[f] - t_dec > 5 * MIN:
                break
            e = ask[f] + 0.07 if side > 0 else bid[f] - 0.07
            stop = rl if side > 0 else rh
            risk = (e - stop) * side
            if risk <= 0:
                break
            r = run_trade(t, bid, ask, f, e, side, stop, e + side * 2.0 * risk, t[f] + 60 * MIN)
            if r is not None:
                t_out = pd.Timestamp(int(r[2]), tz="UTC") if len(r) > 2 else pd.Timestamp(int(t[f] + 60 * MIN), tz="UTC")
                rows.append(dict(piece="London ORB", t_in=pd.Timestamp(int(t[f]), tz="UTC"), t_out=t_out, pnl=r[0], R=r[0] / risk,
                                 part=slib.part_of(pd.DatetimeIndex([t0]))[0]))
            break
    return pd.DataFrame(rows)


def main() -> None:
    P = pd.read_parquet(AG / "dev" / "p4_trades_W_WL_WN.parquet")
    P = P[(P.variant == "W") & (P.news_cost == 0.0) & (P.window == "Asia")] if "window" in P else P[(P.variant == "W") & (P.news_cost == 0.0)]
    asia = pd.DataFrame(dict(piece="Asia B2", t_in=pd.to_datetime(P.entry_t, utc=True), t_out=pd.to_datetime(P.exit_t, utc=True),
                             pnl=P.pnl.to_numpy(), R=P.R.to_numpy(), part=P.part.to_numpy()))
    london = london_orb()
    S = pd.read_parquet(AG / "strategist" / "news_follow_trades.parquet")
    ny = {}
    for extra in sorted(S.extra.unique()):
        X = S[(S.rule == "STRADDLE 30m") & (S.hm == "08:30") & (S.extra == extra)]
        t_in = [pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=8, minute=30, tz="America/New_York").tz_convert("UTC")
                for d in pd.to_datetime(X.day)]
        ny[extra] = pd.DataFrame(dict(piece="NY straddle", t_in=t_in, t_out=[t + pd.Timedelta(minutes=30) for t in t_in],
                                      pnl=X.pnl.to_numpy(), R=X.R.to_numpy(), part=X.part.to_numpy()))
    print("the pieces alone:")
    for name, T in (("Asia B2", asia), ("London ORB", london), ("NY straddle +0", ny[0.0]), ("NY straddle +1", ny.get(1.0, ny[0.0]))):
        for p in ("P1", "P2"):
            G = T[T.part == p]
            print(f"  {name:16s} {p}: {stats(G, WEEKDAYS[p])}")
    for label, extra in (("the plan (NY slippage +0)", 0.0), ("the plan (NY slippage +1 USD)", 1.0)):
        if extra not in ny:
            continue
        A = stream(pd.concat([asia, london, ny[extra]], ignore_index=True))
        print(f"\n{label}: dropped for overlap {len(asia) + len(london) + len(ny[extra]) - len(A)}")
        for p in ("P1", "P2"):
            G = A[A.part == p]
            print(f"  {p}: {stats(G, WEEKDAYS[p])}  | by piece R: {G.groupby('piece').R.mean().round(3).to_dict()}")
        L = A[A.part.isin(["P1", "P2"])]
        print(f"  pooled P1 + P2: {stats(L, WEEKDAYS['P1'] + WEEKDAYS['P2'])}")
        A.to_parquet(HERE / f"combo_trades_slip{int(extra)}.parquet")


if __name__ == "__main__":
    main()
