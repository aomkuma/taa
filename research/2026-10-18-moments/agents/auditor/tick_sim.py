"""Auditor check 2b: the M1-bar simulation against a tick-by-tick simulation of the same trades, decomposed:

  A  M1 as used (ny_lab.M1.trade: ask = bid + the M1 spread column, which is the minute's MINIMUM spread)
  B  M1 bars with the real ask (the minute's ask open / high / low / close from the ticks); same rules
  C  ticks, same conventions as A/B (entry at the first tick of bar e at the ask + 0.07; stop fill stop -/+ 0.07,
     target at the limit; time exit at the last tick of bar e+hz-1 with 0.07) - only the order inside a bar differs
  D  ticks, realistic: entry at the first tick >= 250 ms after the bar opens, no fixed slippage; a stop fills at the
     first tick at or beyond it (gaps cost what they cost); target at the limit; time exit at the last tick
  E  as D with 1000 ms latency

Samples: the confluence test trades (round 9), the triple-screen test trades (round 5, tool 10/8), and random
minute x side rows of own_ml_long in the tick window with the tools 5/4, 8/6+BE0.6, 3/3, 10/8.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/tick_sim.py
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from ny_lab import M1  # noqa: E402

HERE = Path(__file__).parent
SLIP = 0.07
NS = 1_000_000_000
pd.set_option("display.width", 220)


@lru_cache(maxsize=8)
def day_ticks(day: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    f = Path("data/ticks/XAUUSD") / f"{day}.parquet"
    x = pd.read_parquet(f)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


def ticks(t0: pd.Timestamp, t1: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    parts = []
    for d in pd.date_range(t0.normalize(), t1.normalize(), freq="D"):
        if (Path("data/ticks/XAUUSD") / f"{d:%Y-%m-%d}.parquet").exists():
            parts.append(day_ticks(f"{d:%Y-%m-%d}"))
    if not parts:
        return np.array([], dtype=np.int64), np.array([]), np.array([])
    t = np.concatenate([p[0] for p in parts])
    b = np.concatenate([p[1] for p in parts])
    a = np.concatenate([p[2] for p in parts])
    i, j = np.searchsorted(t, t0.value), np.searchsorted(t, t1.value)
    return t[i:j], b[i:j], a[i:j]


class Bars:
    """M1 bars with a chosen ask (A: bid + min spread; B: the real ask from the ticks)."""

    def __init__(self, P: M1, tm: pd.DataFrame | None) -> None:
        self.P = P
        o, h, lo, c = P.o, P.h, P.lo, P.c
        if tm is None:
            self.ao, self.ah, self.al, self.ac = o + P.sp, h + P.sp, lo + P.sp, c + P.sp
        else:
            r = tm.reindex(P.ot)
            self.ao = np.where(r.a_o.notna(), r.a_o, o + P.sp)
            self.ah = np.where(r.a_h.notna(), r.a_h, h + P.sp)
            self.al = np.where(r.a_l.notna(), r.a_l, lo + P.sp)
            self.ac = np.where(r.a_c.notna(), r.a_c, c + P.sp)

    def trade(self, e: int, side: int, tp: float, sl: float, be: float | None, hz: int) -> dict:
        P = self.P
        entry = self.ao[e] + SLIP if side > 0 else P.o[e] - SLIP
        stop, armed, mfe = entry - side * sl, False, 0.0
        end = min(e + hz, len(P.o) - 1)
        both = False
        for j in range(e, end):
            adv = P.lo[j] if side > 0 else self.ah[j]
            fav = P.h[j] if side > 0 else self.al[j]
            if (adv - stop) * side <= 0:
                both = (fav - entry) * side >= tp
                return dict(exit="stop" if not armed else "be", usd=(stop - side * SLIP - entry) * side, mins=j - e + 1, both=both)
            if (fav - entry) * side >= tp:
                return dict(exit="win", usd=tp, mins=j - e + 1, both=False)
            mfe = max(mfe, (fav - entry) * side)
            if be is not None and not armed and mfe >= be * tp:
                armed, stop = True, entry
        x = end - 1
        px = P.c[x] - SLIP if side > 0 else self.ac[x] + SLIP
        return dict(exit="time", usd=(px - entry) * side, mins=end - e, both=False)


def tick_trade(P: M1, e: int, side: int, tp: float, sl: float, be: float | None, hz: int, mode: str, lat_ms: int = 250) -> dict | None:
    t0 = P.ot[e]
    end = min(e + hz, len(P.o) - 1)
    t1 = P.ot[end - 1] + pd.Timedelta(minutes=1)
    tt, bid, ask = ticks(t0, t1)
    if len(tt) < 5 or tt[0] - t0.value > 60 * NS:
        return None
    if mode == "C":
        k = 0
        drift, spread0 = 0.0, ask[0] - bid[0]
        entry = ask[0] + SLIP if side > 0 else bid[0] - SLIP
    else:
        k = int(np.searchsorted(tt, t0.value + lat_ms * 1_000_000))
        if k >= len(tt):
            return None
        entry = ask[k] if side > 0 else bid[k]
    drift = ((ask[k] if side > 0 else bid[k]) - (ask[0] if side > 0 else bid[0])) * side
    spread0 = ask[k] - bid[k]
    exitp = bid if side > 0 else ask  # the closing price stream
    stop, armed = entry - side * sl, False
    target = entry + side * tp
    i = k + 1 if mode != "C" else 0
    # vectorised: walk in segments (before / after break-even arming)
    x = exitp[i:]
    rel = (x - entry) * side
    hit_t = np.nonzero(rel >= tp)[0]
    hit_s = np.nonzero(rel <= -sl)[0]
    first_t = hit_t[0] if len(hit_t) else 10**12
    first_s = hit_s[0] if len(hit_s) else 10**12
    if be is not None:
        arm = np.nonzero(rel >= be * tp)[0]
        first_a = arm[0] if len(arm) else 10**12
        if first_a < min(first_t, first_s):
            armed = True
            hit_s2 = np.nonzero(rel[first_a + 1 :] <= 0)[0]
            first_s = first_a + 1 + hit_s2[0] if len(hit_s2) else 10**12
            stop = entry
    if first_t < first_s:
        return dict(exit="win", usd=tp, gap=0.0, drift=drift, spread0=spread0, mins=(tt[i + first_t] - t0.value) / 60 / NS)
    if first_s < 10**12:
        px = x[first_s]
        if mode == "C":
            fill = stop - side * SLIP
        else:
            fill = px
        return dict(exit="be" if armed else "stop", usd=(fill - entry) * side, gap=(stop - px) * side, drift=drift, spread0=spread0,
                    mins=(tt[i + first_s] - t0.value) / 60 / NS)
    px = x[-1] - side * (SLIP if mode == "C" else 0.0)
    return dict(exit="time", usd=(px - entry) * side, gap=0.0, drift=drift, spread0=spread0, mins=hz)


def run(name: str, rows: pd.DataFrame, P: M1, A: Bars, B: Bars) -> pd.DataFrame:
    out = []
    for r in rows.itertuples():
        e, s, tp, sl, be, hz = int(r.e), int(r.side), float(r.tp), float(r.sl), (None if pd.isna(r.be) else float(r.be)), int(r.hz)
        a = A.trade(e, s, tp, sl, be, hz)
        b = B.trade(e, s, tp, sl, be, hz)
        c = tick_trade(P, e, s, tp, sl, be, hz, "C")
        d = tick_trade(P, e, s, tp, sl, be, hz, "D", 250)
        e2 = tick_trade(P, e, s, tp, sl, be, hz, "D", 1000)
        if c is None or d is None or e2 is None:
            continue
        out.append(dict(t=r.t, side=s, tp=tp, sl=sl, hz=hz, a_exit=a["exit"], a_usd=a["usd"], both=a["both"],
                        b_exit=b["exit"], b_usd=b["usd"], c_exit=c["exit"], c_usd=c["usd"],
                        d_exit=d["exit"], d_usd=d["usd"], d_gap=d["gap"], d_drift=d["drift"], e_drift=e2["drift"], spread0=d["spread0"], m1_sp=P.sp[e], e_exit=e2["exit"], e_usd=e2["usd"]))
    R = pd.DataFrame(out)
    R["sample"] = name
    return R


def report(R: pd.DataFrame) -> None:
    for (name, tp), g in R.groupby(["sample", "tp"], sort=False):
        sl = g.sl.median()
        if len(g) < 30:
            continue
        risk = g.sl + SLIP
        line = f"{name:22} {int(tp):>2}/{sl:<5.1f} n={len(g):5}"
        for k in "abcde":
            line += f" | {k.upper()} win {100 * (g[f'{k}_exit'] == 'win').mean():4.1f}% {g[f'{k}_usd'].mean():+.3f} ({(g[f'{k}_usd'] / risk).mean():+.3f}R)"
        print(line)
        for k in "bcde":
            dd = g[f"{k}_usd"] - g.a_usd
            print(f"{'':22} {k.upper()} - A per trade: {dd.mean():+.3f} USD (se {dd.std() / np.sqrt(len(dd)):.3f})")
        print(f"{'':22} entry: real spread at fill {g.spread0.mean():.3f} vs M1 column {g.m1_sp.mean():.3f}; price drift in 250 ms {g.d_drift.mean():+.3f} (p90 {g.d_drift.quantile(0.9):+.2f}), in 1 s {g.e_drift.mean():+.3f}")
        bb = g[g.both]
        if len(bb):
            print(f"{'':22} both-in-one-bar stops in A: {len(bb)} ({100 * len(bb) / len(g):.1f}%); ticks C say: {bb.c_exit.value_counts().to_dict()}")
        st = g[g.d_exit.isin(['stop', 'be'])]
        if len(st):
            print(f"{'':22} D stop fills beyond the stop (gap, USD): mean {st.d_gap.mean():.3f} p50 {st.d_gap.median():.2f} p90 {st.d_gap.quantile(0.9):.2f} "
                  f"p99 {st.d_gap.quantile(0.99):.2f}; > 0.07 in {100 * (st.d_gap > 0.07).mean():.0f}%")


def main() -> None:
    gold.below_normal_priority()
    if "--report" in sys.argv:
        report(pd.read_parquet(HERE / "tick_sim.parquet"))
        return
    P = M1()
    tm = pd.read_parquet(HERE / "tick_minutes.parquet")
    A, B = Bars(P, None), Bars(P, tm)
    # A must reproduce ny_lab.M1.trade
    rng = np.random.default_rng(11)
    for e in rng.integers(1_000_000, len(P.o) - 200, 300):
        for s in (1, -1):
            x, y = P.trade(int(e), s, 8, 6, 0.6, 60), A.trade(int(e), s, 8, 6, 0.6, 60)
            assert x["exit"] == y["exit"] and abs(x["usd"] - y["usd"]) < 1e-9, (e, s, x, y)
    print("A reproduces ny_lab.M1.trade on 600 random trades")
    samples = []
    c = pd.read_parquet("data/research/own_confluence_test.parquet")
    c["t"] = pd.to_datetime(c.t, utc=True)
    samples.append(("confluence (r9)", c.assign(tp=8.0, be=0.6, hz=60)[["t", "e", "side", "tp", "sl", "be", "hz"]]))
    ts = pd.read_parquet("data/research/own_triple_screen_test.parquet")
    ts["t"] = pd.to_datetime(ts.t, utc=True)
    samples.append(("triple screen (r5)", ts.assign(tp=10.0, sl=8.0, be=np.nan, hz=60)[["t", "e", "side", "tp", "sl", "be", "hz"]]))
    d = pd.read_parquet("data/research/own_ml_long.parquet", columns=["t", "e", "side", "session"])
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[(d.t >= pd.Timestamp("2025-10-02", tz="UTC")) & (d.t < pd.Timestamp("2026-10-13", tz="UTC"))]
    rnd = d.iloc[rng.choice(len(d), 2500, replace=False)]
    for tp, sl, be in ((5.0, 4.0, np.nan), (8.0, 6.0, 0.6), (3.0, 3.0, np.nan), (10.0, 8.0, np.nan)):
        samples.append(("random rows", rnd.assign(tp=tp, sl=sl, be=be, hz=60)[["t", "e", "side", "tp", "sl", "be", "hz", "session"]]))
    res = []
    for name, rows in samples:
        rows = rows.sort_values("t")
        res.append(run(name, rows, P, A, B))
        print(name, "done", flush=True)
    R = pd.concat(res, ignore_index=True)
    R.to_parquet(HERE / "tick_sim.parquet")
    print("\nPer sample and tool: win % / USD a trade (R a trade) under A (M1 as used) .. E (ticks, 1 s latency)")
    report(R)
    # totals of the two test samples in USD
    for name in ("confluence (r9)", "triple screen (r5)"):
        g = R[R["sample"] == name]
        print(f"\n{name}: {len(g)} trades; totals A {g.a_usd.sum():+.1f}  B {g.b_usd.sum():+.1f}  C {g.c_usd.sum():+.1f}  D {g.d_usd.sum():+.1f}  E {g.e_usd.sum():+.1f} USD")
        print("   outcome A -> D:", pd.crosstab(g.a_exit, g.d_exit).to_dict())


if __name__ == "__main__":
    main()
