"""The no-look-ahead check for Task D (d1_orb, d2_straddle), on the real data of the learning parts (and O1 / O2 days for
D1's readings).

D1: for every P1 / P2 day and 60 days of O1 / O2 (core cell): everything read at the decision - the day's status, the
range, the side, the stop, the decision time, H, ADR20 and the level ahead - computed on a window of M1 around the day,
then again with every M1 bar from the decision on replaced by other prices (a no-trade day: from the end of the entry
window); all must stay equal. The tick trade: equal when every tick after its exit is replaced. Power: replacing the
ticks after the fill changes the trades; moving the decision bar's close back inside the range removes the decision.
D2: for every core trade (2 U, 8 U, 30 minutes, +0.5 USD): the side, the fill tick and price equal when every tick after
the fill is replaced; the whole trade equal when every tick after the exit is replaced. Power: the ticks after the fill.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_d.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import d1_orb as D1  # noqa: E402
import d2_straddle as D2  # noqa: E402
import p2_trades as P2  # noqa: E402
import patterns as P  # noqa: E402
from lookahead_p import replaced  # noqa: E402
from lookahead_p2 import ticks_replaced  # noqa: E402
from sweep_detector import EXAM_START  # noqa: E402

NS_MIN = 60 * 10**9
KEYS = ("status", "side", "stop", "t_dec", "close", "rh", "rl")
TRADE_KEYS = ("side", "entry", "entry_t", "stop", "risk", "exit", "exit_px", "exit_t", "pnl", "R")


def readings(w: pd.DataFrame, t0: int) -> dict:
    mk = D1.Market(w)
    L, k_r, X = D1.CORE
    H = mk.H(t0)
    d = D1.decide(mk.t_open, mk.h, mk.lo, mk.c, t0, H, L)
    out = {k: d.get(k) for k in KEYS}
    out["H"] = round(H, 9)
    if d["status"] == "trade":
        rd = d["side"] * (d["close"] - d["stop"])
        out["adr20"] = round(mk.adr20(d["t_dec"]), 9)
        la = D1.level_in_way(mk.levels(d["t_dec"], d["close"]), d["close"], d["side"], rd)
        out["level"] = None if np.isnan(la) else round(la, 9)
    return out


def check_d1(rng: np.random.Generator) -> bool:
    m = P.load_m1(pd.Timestamp("2023-09-01", tz="UTC"), EXAM_START)
    idx = m.index.as_unit("ns").asi8
    days = list(pd.bdate_range("2025-10-20", "2026-04-17", tz="UTC"))
    old = list(pd.bdate_range("2023-10-18", "2025-10-17", tz="UTC"))
    days += [old[i] for i in sorted(rng.choice(len(old), 60, replace=False))]
    eq = n = power = power_n = 0
    bad = []
    for day in days:
        t0 = int((day.normalize() + pd.Timedelta(hours=D1.OPEN_UTC)).value)
        a = int(np.searchsorted(idx, t0 - 35 * 1440 * NS_MIN))
        b = int(np.searchsorted(idx, t0 + 1440 * NS_MIN))
        w = m.iloc[a:b]
        r0 = readings(w, t0)
        cut = r0["t_dec"] if r0["status"] == "trade" else t0 + (D1.CORE[0] + D1.ENTRY_WIN) * NS_MIN
        r1 = readings(replaced(w, cut, rng), t0)
        n += 1
        if r0 == r1:
            eq += 1
        else:
            bad.append(f"{day:%Y-%m-%d}")
        if r0["status"] == "trade":  # power: the decision bar's close moved back inside the range
            w2 = w.copy()
            k = int(np.searchsorted(w2.index.as_unit("ns").asi8, r0["t_dec"] - NS_MIN))
            w2.iloc[k, w2.columns.get_loc("close")] = (r0["rh"] + r0["rl"]) / 2
            power_n += 1
            power += readings(w2, t0).get("t_dec") != r0["t_dec"]
    print(f"D1 1. the readings at the decision equal after every later M1 bar was replaced: {eq} of {n} days"
          + (f"; DIFFERENT: {bad[:10]}" if bad else ""))
    print(f"   power: the decision bar's close moved inside the range changed the decision in {power} of {power_n}")
    # the tick trades
    A = pd.read_parquet(HERE / "d1_trades.parquet")
    T = A[(A.src == "ticks") & (A.L == 15) & (A.k == 2.0) & (A.X == 60) & A.traded.fillna(False).astype(bool)]
    ticks = P2.Ticks()
    same = changed = 0
    for r in T.itertuples(index=False):
        span = ticks.span(int(r.t_dec))
        x0 = D1.tick_trade(*span, int(r.t_dec), int(r.side), float(r.stop), 2.0, 60)
        x1 = D1.tick_trade(*ticks_replaced(span, int(x0["exit_t"]), rng), int(r.t_dec), int(r.side), float(r.stop), 2.0, 60)
        x2 = D1.tick_trade(*ticks_replaced(span, int(x0["entry_t"]), rng), int(r.t_dec), int(r.side), float(r.stop), 2.0, 60)
        same += all(x0[k] == x1[k] for k in TRADE_KEYS) and all(x0[k] == getattr(r, k) for k in TRADE_KEYS)
        changed += any(x0[k] != x2[k] for k in TRADE_KEYS)
        ticks.days.clear()
        ticks.spans.clear()
    print(f"D1 2. the trade (and the stored one) equal after every tick after its exit was replaced: {same} of {len(T)}; "
          f"power: the ticks after the fill replaced changed {changed} of {len(T)}")
    return eq == n and same == len(T)


def check_d2(rng: np.random.Generator) -> bool:
    B = pd.read_parquet(HERE / "d2_trades.parquet")
    T = B[(B.trig == 2.0) & (B.stop_u == 8.0) & (B.hold == 30) & (B.extra == 0.5)]
    ticks = P2.Ticks()
    fill_eq = same = changed = 0
    for r in T.itertuples(index=False):
        span = ticks.span(int(r.t0))
        x0 = D2.straddle(*span, int(r.t0), 2.0, 8.0, 30, 0.5)
        x1 = D2.straddle(*ticks_replaced(span, int(x0["entry_t"]), rng), int(r.t0), 2.0, 8.0, 30, 0.5)
        x2 = D2.straddle(*ticks_replaced(span, int(x0["exit_t"]), rng), int(r.t0), 2.0, 8.0, 30, 0.5)
        fill_eq += all(x0[k] == x1[k] for k in ("side", "entry", "entry_t", "stop", "risk"))
        same += all(x0[k] == x2[k] for k in TRADE_KEYS) and all(x0[k] == getattr(r, k) for k in TRADE_KEYS)
        changed += any(x0[k] != x1[k] for k in TRADE_KEYS)
        if len(ticks.spans) > 2:
            ticks.days.clear()
            ticks.spans.clear()
    print(f"D2 1. the side, the fill tick and price equal after every tick after the fill was replaced: {fill_eq} of {len(T)}")
    print(f"D2 2. the trade (and the stored one) equal after every tick after its exit was replaced: {same} of {len(T)}; "
          f"power: the ticks after the fill replaced changed {changed} of {len(T)}")
    return fill_eq == len(T) and same == len(T)


def main() -> None:
    rng = np.random.default_rng(20261019)
    ok = check_d2(rng)
    ok = check_d1(rng) and ok
    if not ok:
        raise SystemExit("LOOK-AHEAD CHECK FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
