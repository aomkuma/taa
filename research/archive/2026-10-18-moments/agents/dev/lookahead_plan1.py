"""The no-look-ahead check of the PLAN-1 runner (plan1.py) on the learning parts, every plan trade:

(a) the D1 state: every M1 bar opening at / after the fill replaced by other prices (x 1.07) and the D1 bars rebuilt -
    the state at the fill must be unchanged; the D1 bar it reads must end before the fill and belong to an earlier
    server day; power: the M1 bars of that D1 bar replaced -> the state must change on some trades;
(b) the decisions: London - every M1 bar opening at / after the decision replaced: the range, side, stop and decision
    time unchanged (power: the range's bars replaced -> changes); NY - every tick after the fill tick replaced: the side,
    the fill tick and price unchanged (power: the ticks in the first minute replaced -> changes);
(c) the trades (London, NY): every tick after the exit tick replaced: pnl / exit / exit time unchanged (power: the ticks
    between the fill and the exit replaced -> changes). Asia B2's engine is P3's (its look-ahead check passed, DEV_LOG
    P3 / P4); the runner only sets its slippage.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_plan1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan1 as L  # noqa: E402

OHLC = ["open", "high", "low", "close"]
NS_MIN = L.NS_MIN


def replaced_after(m: pd.DataFrame, t_ns: int) -> pd.DataFrame:
    m2 = m.copy()
    k = m.index.as_unit("ns").asi8 >= t_ns
    m2.loc[k, OHLC] = m.loc[k, OHLC].to_numpy() * 1.07
    return m2


def main() -> None:
    from indicators import bars  # noqa: PLC0415

    A = pd.read_parquet(HERE / "plan1_trades_learn_s0_x0.parquet")
    m = L.load_m1(L.EXAM_START, False)
    d1 = bars(m, "1D")
    d1_av = pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8
    t_m = m.index.as_unit("ns").asi8
    eq = pw = 0
    bad = []
    order_ok = 0
    for r in A.itertuples(index=False):
        s0 = L.trend_state(d1, [r.t_in])[0]
        s1 = L.trend_state(bars(replaced_after(m, int(r.t_in)), "1D"), [r.t_in])[0]
        eq += s0 == s1
        if s0 != s1:
            bad.append(("state", r.piece, pd.Timestamp(r.t_in, tz="UTC")))
        k = int(np.searchsorted(d1_av, r.t_in, side="right")) - 1
        last = int(d1["last"].iloc[k].value)
        day_bar = pd.Timestamp(last, tz="UTC").tz_convert("Europe/Athens").date()
        day_in = pd.Timestamp(int(r.t_in), tz="UTC").tz_convert("Europe/Athens").date()
        order_ok += last < r.t_in and day_bar < day_in
        # power: the M1 bars of the D1 bar read, with the closes reversed around their mean (the day's direction flipped)
        a = int(d1["last"].iloc[k - 1].value) if k > 0 else 0
        sel = (t_m > a) & (t_m <= last)
        m3 = m.copy()
        mid = m.loc[sel, "close"].mean()
        m3.loc[sel, OHLC] = (2 * mid - m.loc[sel, OHLC].to_numpy()) * 1.3 - 0.3 * mid
        pw += L.trend_state(bars(m3, "1D"), [r.t_in])[0] != s0
    n = len(A)
    print(f"(a) the D1 state unchanged with every M1 bar from the fill replaced: {eq} of {n}")
    print(f"    the D1 bar read ends before the fill, on an earlier server day: {order_ok} of {n}")
    print(f"    power - the bar read changed -> the state changed: {pw} of {n}")

    # (b) London decisions
    mk = L.D1.Market(m)
    Lt = A[A.piece == "London ORB"]
    eqb = pwb = 0
    for r in Lt.itertuples(index=False):
        day = pd.Timestamp(int(r.t_dec), tz="UTC").normalize()
        t0 = int((day + pd.Timedelta(hours=L.D1.OPEN_UTC)).value)
        d0 = L.D1.decide(mk.t_open, mk.h, mk.lo, mk.c, t0, mk.H(t0), L.ORB_MIN)
        c2 = mk.c.copy()
        h2, lo2 = mk.h.copy(), mk.lo.copy()
        after = mk.t_open >= r.t_dec
        c2[after], h2[after], lo2[after] = c2[after] * 1.07, h2[after] * 1.07, lo2[after] * 1.07
        d2 = L.D1.decide(mk.t_open, h2, lo2, c2, t0, mk.H(t0), L.ORB_MIN)
        keys = ("status", "side", "stop", "t_dec", "rh", "rl")
        eqb += all(d0.get(k) == d2.get(k) for k in keys) and d0["t_dec"] == r.t_dec and d0["side"] == r.side
        rng = (mk.t_open >= t0) & (mk.t_open < t0 + L.ORB_MIN * NS_MIN)
        h3, lo3 = mk.h.copy(), mk.lo.copy()
        h3[rng], lo3[rng] = h3[rng] + 3.0, lo3[rng] - 3.0
        d3 = L.D1.decide(mk.t_open, h3, lo3, mk.c, t0, mk.H(t0), L.ORB_MIN)
        pwb += any(d0.get(k) != d3.get(k) for k in keys)
    print(f"(b) London: the decision unchanged with every M1 bar from the decision replaced: {eqb} of {len(Lt)}; "
          f"power - the range's bars widened by 3 USD -> changed: {pwb} of {len(Lt)}")

    ticks = L.PlanTicks(L.EXAM_START)
    N = A[A.piece == "NY straddle"]
    eqn = pwn = 0
    for r in N.itertuples(index=False):
        day = pd.Timestamp(int(r.t_dec), tz="UTC").normalize()
        t, bid, ask = ticks.day(day)
        x0 = L.straddle(t, bid, ask, int(r.t_dec), 0.0)
        j = x0["i_in"]  # the fill tick by its index (ticks can share a time stamp)
        b2, a2 = bid.copy(), ask.copy()
        b2[j + 1:], a2[j + 1:] = b2[j + 1:] + 50, a2[j + 1:] + 50
        try:
            x1 = L.straddle(t, b2, a2, int(r.t_dec), 0.0)
        except AssertionError:
            x1 = None
        eqn += x1 is not None and (x1["side"], x1["t_in"], x1["entry"]) == (x0["side"], x0["t_in"], x0["entry"])
        f0 = int(np.searchsorted(t, r.t_dec, side="left"))
        b3, a3 = bid.copy(), ask.copy()
        b3[f0:j + 1], a3[f0:j + 1] = b3[f0:j + 1] - 5 * x0["side"], a3[f0:j + 1] - 5 * x0["side"]
        x3 = L.straddle(t, b3, a3, int(r.t_dec), 0.0)
        pwn += x3 is None or (x3["side"], x3["t_in"], x3["entry"]) != (x0["side"], x0["t_in"], x0["entry"])
    print(f"    NY: the side / fill tick / price unchanged with every tick after the fill replaced: {eqn} of {len(N)}; "
          f"power - the ticks up to the fill moved 5 USD against the side -> changed: {pwn} of {len(N)}")

    # (c) the trades after their exits
    eqc = pwc = nc = same = 0
    for r in pd.concat([Lt, N]).itertuples(index=False):
        day = pd.Timestamp(int(r.t_dec), tz="UTC").normalize()
        t, bid, ask = ticks.day(day)

        def redo(b, a, r=r):
            if r.piece == "London ORB":
                return L.orb_trade(t, b, a, int(r.t_dec), int(r.side), float(r.stop), 0.0)
            return L.straddle(t, b, a, int(r.t_dec), 0.0)

        y0 = redo(bid, ask)  # the trade again from the raw ticks: it must be the stored one
        f, x = y0["i_in"], y0["i_out"]
        same += (y0["pnl"], y0["exit"], y0["t_out"], y0["t_in"]) == (r.pnl, r.exit, r.t_out, r.t_in)

        b2, a2 = bid.copy(), ask.copy()
        b2[x + 1:], a2[x + 1:] = b2[x + 1:] * 1.07, a2[x + 1:] * 1.07
        y = redo(b2, a2)
        nc += 1
        eqc += y is not None and (y["pnl"], y["exit"], y["t_out"]) == (r.pnl, r.exit, r.t_out)
        if x > f + 1:
            b3, a3 = bid.copy(), ask.copy()
            b3[f + 1:x], a3[f + 1:x] = b3[f + 1:x] - 20 * r.side, a3[f + 1:x] - 20 * r.side
            y3 = redo(b3, a3)
            pwc += y3 is None or (y3["pnl"], y3["exit"], y3["t_out"]) != (r.pnl, r.exit, r.t_out)
    print(f"    London + NY trades re-derived from the raw ticks equal to the stored ones: {same} of {nc}")
    print(f"(c) London + NY trades unchanged with every tick after the exit replaced: {eqc} of {nc}; "
          f"power - the ticks between the fill and the exit moved 20 USD against -> changed: {pwc}")
    ok = eq == n and order_ok == n and pw > 0 and eqb == len(Lt) and pwb > 0 and eqn == len(N) and pwn > 0 and eqc == nc and pwc > 0 and same == nc
    for b in bad[:10]:
        print("  state changed:", b)
    print("PASSED" if ok else "FAILED")


if __name__ == "__main__":
    main()
