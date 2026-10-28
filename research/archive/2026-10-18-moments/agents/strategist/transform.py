"""CHECKLIST row 39, part 1 - the transformations of the FAIL rows (owner, 2026-10-20: "before discarding a method, try
the opposite side, a wider stop, a nearer target"). Written before computing (2026-10-20, about 13:00 Thai).

The families (each FAIL row whose trades can be re-simulated from a saved trade list, without loading the exam):

| key | row | the rule's trades (P1 / P2 only) | stop | target | other exits |
|---|---|---|---|---|---|
| SR16 | #16 | `precursors/sr_break_trades.parquet` (both sides / active hours / stop 5 / surrender 3 min +2) | 5 USD from the fill | 10 USD | surrender (3 min, +2 USD), out 30 min after the entry |
| B2_17 | #17 | `dev/p2_trades.parquet` B2, news cost 0 | the pattern's stop (price) | the next level if > 1 risk, else none | the structure exit (same side), the time limit |
| A_18 | #18 | `dev/p2_trades.parquet` A (entered at the breakout), news cost 0 | as B2 | as B2 | as B2 |
| B1_18 | #18 | `dev/p2_trades.parquet` B1 (the pullback stop), news cost 0 | as B2 | as B2 | as B2 |
| W_20 | #20 | `dev/p4_trades_W_WL.parquet` W (B2 in the owner's windows), news cost 0 | as B2 | as B2 | as B2 |
| PB_13 | #13 | `precursors/pullback_trades.parquet` (rebuilt: stop = the M1 fill - side x r0) | the price | 3 R0 | surrender (5 min, +1 R0 USD), out 240 min after the entry |
| PB15_14 | #14 | `precursors/pullback15_trades.parquet` (the same rebuild) | as PB_13 | 3 R0 | as PB_13 |
| RT_25 | #25 | `strategist/retest_trades.parquet` (rebuilt: stop = the M1 fill - side x risk) | the price | 2 R | out 120 min after the entry |
| FOL15_28 | #28 | recomputed as news_follow.py FOLLOW 15m (08:30 / 10:00 NY, the first minute >= 3 USD) | the release mid - side x 1 USD | none | out 15 min after the minute |
| FOL2R_28 | #28 | FOLLOW 2R/30m | as FOL15 | 2 R | out 30 min after the minute |
| D2_41 | #41 | `dev/d2_trades.parquet` trigger 2 U, stop 8 U, hold 30, extra 0 (08:30 + 10:00 NY) | 8 U from the fill | none | out 30 min after the minute |

The grid, per family (tsim.grid): the side {same, opp} x the stop {x1, x1.5, x2} x the target {orig, x0.75, x0.5, 1R0}
= 24 cells, 264 in all; (same, x1, orig) is the rule itself. x0.75 / x0.5 act only on trades that have a target; 1R0
puts a target at 1 x the rule's own stop distance on every trade. Each trade alone (the rule's entries kept); the
one-position-at-a-time view from the same entries is printed beside it. Costs: the tick spread only, slippage 0.
The check: the rule's cell at 0.07 USD entry slippage (the families' own cost) against the families' stored R.
Not covered: #9 / #10 (their entry frame `aligned_frame()` reads the full store, the exam included), #11 / #12 (no
saved learning trades), #1-#7 / #26 / #27 (not a re-simulable entry list, or not a trade rule).

A LEAD = a cell >= +0.15 R a trade in both parts (seen after the run: a lead, never a pass).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/transform.py > .../strategist/out_transform.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import slib
import tsim

AG = slib.HERE.parent
PRE = AG / "precursors"
MIN = tsim.NS_MIN


def ns(x) -> np.ndarray:
    return pd.DatetimeIndex(pd.to_datetime(x, utc=True)).as_unit("ns").asi8


def dev_b2(file: str, variant: str) -> pd.DataFrame:
    d = pd.read_parquet(AG / "dev" / file)
    d = d[(d.variant == variant) & (d.news_cost == 0.0) & d.part.isin(["P1", "P2"])]
    if "exit_mode" in d:
        d = d[d.exit_mode == "structure"]
    ts = pd.to_numeric(d.t_struct, errors="coerce").astype(float)
    return pd.DataFrame(dict(t_in=d.t_entry.astype("int64").to_numpy(), side=d.side.to_numpy(), stop_px=d.stop.to_numpy(),
                             tgt_px=d.target.to_numpy(float), t_out=d.t_limit.astype("int64").to_numpy(), t_struct=ts.to_numpy(),
                             part=d.part.to_numpy(), R_own=d.R.to_numpy(), win=d["window"].to_numpy() if "window" in d else ""))


def m1_fill(m: pd.DataFrame, t_ns: np.ndarray, side: np.ndarray) -> np.ndarray:
    i = np.searchsorted(m.index.asi8, t_ns)
    o, sp = m.open.to_numpy()[i], m.spread.to_numpy()[i] * 0.01 + 0.08
    return np.where(side > 0, o + sp + 0.07, o - 0.07)


def families() -> dict[str, pd.DataFrame]:
    F = {}
    S = pd.read_parquet(PRE / "sr_break_trades.parquet")
    S = S[S.part.isin(["P1", "P2"])]
    F["SR16"] = pd.DataFrame(dict(t_in=S.t0.astype("int64").to_numpy(), side=S.side.to_numpy(), stop_d=5.0, tgt_px=np.nan,
                                  tgt_r=2.0, t_out=S.t0.astype("int64").to_numpy() + 30 * MIN, surr_min=3.0, surr_usd=2.0,
                                  part=S.part.to_numpy(), R_own=S.R.to_numpy()))
    F["B2_17"] = dev_b2("p2_trades.parquet", "B2")
    F["A_18"] = dev_b2("p2_trades.parquet", "A")
    F["B1_18"] = dev_b2("p2_trades.parquet", "B1")
    F["W_20"] = dev_b2("p4_trades_W_WL.parquet", "W")
    m = slib.m1("2025-10-01")
    for key, file in (("PB_13", "pullback_trades.parquet"), ("PB15_14", "pullback15_trades.parquet")):
        P = pd.read_parquet(PRE / file)
        P = P[P.part.isin(["P1", "P2"])]
        t = ns(P.t)
        e = m1_fill(m, t, P.side.to_numpy())
        F[key] = pd.DataFrame(dict(t_in=t, side=P.side.to_numpy(), stop_px=e - P.side.to_numpy() * P.r0.to_numpy(), tgt_px=np.nan,
                                   tgt_r=3.0, t_out=t + 240 * MIN, surr_min=5.0, surr_usd=P.r0.to_numpy(), part=P.part.to_numpy(),
                                   R_own=P.R.to_numpy()))
    R = pd.read_parquet(slib.HERE / "retest_trades.parquet")
    R = R[R.part.isin(["P1", "P2"])]
    t = ns(R.t)
    e = m1_fill(m, t, R.side.to_numpy())
    F["RT_25"] = pd.DataFrame(dict(t_in=t, side=R.side.to_numpy(), stop_px=e - R.side.to_numpy() * R.risk.to_numpy(), tgt_px=np.nan,
                                   tgt_r=2.0, t_out=t + 120 * MIN, part=R.part.to_numpy(), R_own=R.R.to_numpy(), win=R.win.to_numpy()))
    F["FOL15_28"], F["FOL2R_28"] = follow()
    D = pd.read_parquet(AG / "dev" / "d2_trades.parquet")
    D = D[(D.trig == 2.0) & (D.stop_u == 8.0) & (D.hold == 30) & (D.extra == 0.0) & D.part.isin(["P1", "P2"])]
    F["D2_41"] = pd.DataFrame(dict(t_in=D.entry_t.astype("int64").to_numpy(), side=D.side.to_numpy(), stop_d=8.0 * D.unit.to_numpy(),
                                   tgt_px=np.nan, t_out=D.t0.astype("int64").to_numpy() + 30 * MIN, part=D.part.to_numpy(),
                                   R_own=D.R.to_numpy(), win=D.ny.to_numpy()))
    return F


def follow() -> tuple[pd.DataFrame, pd.DataFrame]:
    """news_follow.py's FOLLOW entries: every weekday's 08:30 / 10:00 NY minute, |the first minute's mid move| >= 3."""
    from news_follow import last_mid  # noqa: PLC0415

    rows = []
    for day in pd.bdate_range("2025-10-20", "2026-04-17", tz="UTC"):
        x = slib.ticks(day)
        if x is None or len(x) < 1000:
            continue
        t = x.t.dt.as_unit("ns").astype("int64").to_numpy()
        bid, ask = x.bid.to_numpy(float), x.ask.to_numpy(float)
        for hm in ("08:30", "10:00"):
            t0 = pd.Timestamp(f"{day:%Y-%m-%d} {hm}").tz_localize("America/New_York").tz_convert("UTC").value
            if t0 < t[0] + 600 * 10**9 or t0 + 1800 * 10**9 > t[-1]:
                continue
            mid0, mid1 = last_mid(t, bid, ask, t0), last_mid(t, bid, ask, t0 + 60 * 10**9)
            if abs(mid1 - mid0) >= 3:
                s = int(np.sign(mid1 - mid0))
                rows.append(dict(t0=t0, t_in=t0 + 60 * 10**9, side=s, stop_px=mid0 - s * 1.0, win=hm,
                                 part=slib.part_of(pd.DatetimeIndex([pd.Timestamp(t0, tz="UTC")]))[0]))
    B = pd.DataFrame(rows)
    a = B.assign(tgt_px=np.nan, t_out=B.t0 + 15 * MIN)
    b = B.assign(tgt_px=np.nan, tgt_r=2.0, t_out=B.t0 + 30 * MIN)
    return a.drop(columns="t0"), b.drop(columns="t0")


def cell_table(T: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (sv, sm, tg), g in T.groupby(["side_v", "stop_m", "tgt"], sort=False):
        r = dict(side=sv, stop=f"x{sm:g}", target=tg)
        for p in ("P1", "P2"):
            x = g[g.part == p]
            o = tsim.one_at_a_time(x)
            r.update({f"{p} n": len(x), f"{p} R": x.R.mean(), f"{p} win": (x.pnl > 0).mean(), f"{p} R 1-at-a-time": o.R.mean(),
                      f"{p} n1": len(o)})
        lo, hi = slib.ci95(g.R.to_numpy())
        r.update(pooled=g.R.mean(), lo=lo, hi=hi, lead="LEAD" if min(r["P1 R"], r["P2 R"]) >= 0.15 else "")
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    tsim.idle()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    F = families()
    allT, leads = [], []
    for key, S in F.items():
        S = S[S.part.isin(["P1", "P2"])].copy()
        assert pd.Timestamp(int(S.t_in.max()), tz="UTC") < slib.EXAM_START
        # the check: the rule's own cell at 0.07 USD entry slippage against the stored R
        C = tsim.run(S, slip=0.07, sides=("same",), stops=(1.0,), targets=("orig",))
        chk = " | ".join(f"{p}: n {int((C.part == p).sum())} R {C[C.part == p].R.mean():+.3f} (stored: n {int((S.part == p).sum())} "
                         f"R {S[S.part == p].R_own.mean():+.3f})" for p in ("P1", "P2")) if "R_own" in S else "-"
        T = tsim.run(S)
        T["family"] = key
        allT.append(T)
        tab = cell_table(T)
        print(f"\n=== {key}: {len(S)} rule trades; the check at 0.07 slippage - {chk}")
        print(f"    trades with a rule target: {T[(T.side_v == 'same') & (T.stop_m == 1) & (T.tgt == 'orig')].has_tgt.mean():.2f}")
        print(tab.round(3).to_string(index=False))
        for _, r in tab[tab.lead == "LEAD"].iterrows():
            leads.append(f"{key} {r.side} {r.stop} {r.target}: P1 n {r['P1 n']} R {r['P1 R']:+.3f} | P2 n {r['P2 n']} R {r['P2 R']:+.3f} | "
                         f"one at a time {r['P1 R 1-at-a-time']:+.3f} / {r['P2 R 1-at-a-time']:+.3f} | pooled {r.pooled:+.3f} ({r.lo:+.2f}..{r.hi:+.2f})")
        if "win" in S and S.win.astype(str).str.len().max() > 0:
            print("    by window / minute, the rule's own cell and the opposite x1 orig:")
            for sv in ("same", "opp"):
                g = T[(T.side_v == sv) & (T.stop_m == 1) & (T.tgt == "orig")]
                for (w, p), x in g.groupby(["win", "part"]):
                    print(f"      {sv:4s} {w:7s} {p}: n {len(x):4d} R {x.R.mean():+.3f} win {(x.pnl > 0).mean():.2f}")
    A = pd.concat(allT, ignore_index=True)
    A.to_parquet(slib.HERE / "transform_trades.parquet")
    print(f"\ncells: {A.groupby(['family', 'side_v', 'stop_m', 'tgt']).ngroups}")
    print("\nLEADS (>= +0.15 R in both parts; seen after the run):")
    for x in leads:
        print("  ", x)


if __name__ == "__main__":
    main()
