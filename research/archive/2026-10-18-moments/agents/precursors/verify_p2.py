"""The measurer's independent check of the developer's P2 trades (owner, 2026-10-19: "beware of interpreting correctly
while the metric is wrong; check the code for bugs carefully"). Imports nothing of the developer's code:
1. every reported metric recomputed from p2_trades.parquet by separate code;
2. one position at a time;
3. a random 20 trades a variant re-derived from the raw ticks (the fill, no stop crossed before the exit, the exit tick
   and price, USD, R);
4. every structure exit re-read with fingerprint.zigzag (an independent ZigZag) on the entry TF's closed bars.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/verify_p2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
DEV = HERE.parents[0] / "dev"
TICKS = HERE.parents[3] / "data" / "ticks" / "XAUUSD"
SLIP = 0.07


def metrics(T: pd.DataFrame, weekdays: int) -> dict:
    """The report's numbers from a trade list, computed plainly."""
    T = T.sort_values("entry_t")
    p = T.pnl.to_numpy(float)
    r = T.R.to_numpy(float)
    eq = np.concatenate([[0.0], np.cumsum(p)])
    peak = np.maximum.accumulate(eq)
    run = best = 0
    for v in p:
        run = run + 1 if v < 0 else 0
        best = max(best, run)
    se = r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
    return dict(n=len(T), per_day=len(T) / weekdays, win=float(np.mean(p > 0)), R=float(r.mean()),
                R_lo=float(r.mean() - 1.96 * se), R_hi=float(r.mean() + 1.96 * se), usd=float(p.sum()),
                dd=float((peak - eq).max()), worst=float(p.min()), streak=best)


def raw_ticks(t0: int, t1: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The raw ticks from t0 to t1 (ns), read straight from the day files."""
    days = pd.date_range(pd.Timestamp(t0, tz="UTC").normalize(), pd.Timestamp(t1, tz="UTC").normalize(), freq="D")
    parts = []
    for d in days:
        f = TICKS / f"{d:%Y-%m-%d}.parquet"
        if f.exists() and d < pd.Timestamp("2026-04-18", tz="UTC"):
            parts.append(pd.read_parquet(f))
    x = pd.concat(parts)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


def rederive(r) -> list[str]:
    """What disagrees between the trade row and the raw ticks (empty = all agree)."""
    bad = []
    t, bid, ask = raw_ticks(int(r.t_entry), int(r.exit_t))
    f = int(np.searchsorted(t, int(r.t_entry), side="left"))
    if t[f] != int(r.entry_t):
        bad.append("fill tick")
    extra = float(r.entry - (ask[f] + SLIP)) if r.side > 0 else float((bid[f] - SLIP) - r.entry)
    if not (abs(extra) < 1e-6 or (r.news and abs(extra - r.news_cost) < 1e-6)):
        bad.append(f"fill price ({extra:+.3f})")
    x = int(np.searchsorted(t, int(r.exit_t), side="left"))
    mkt = bid if r.side > 0 else ask
    crossed = np.nonzero(r.side * (mkt[f + 1:x] - r.stop) <= 0)[0]
    if len(crossed):
        bad.append("a stop crossed before the exit")
    px = float(r.target) if r.exit == "target" else float(mkt[x])
    if abs(px - r.exit_px) > 1e-6:
        bad.append("exit price")
    if r.exit == "stop" and r.side * (mkt[x] - r.stop) > 0:
        bad.append("a stop exit not past the stop")
    if r.exit == "target" and r.side * (mkt[x] - r.target) < 0:
        bad.append("a target exit short of the target")
    pnl = r.side * (px - r.entry)
    if abs(pnl - r.pnl) > 1e-6 or abs(pnl / (r.side * (r.entry - r.stop)) - r.R) > 1e-6:
        bad.append("USD / R")
    return bad


def structure_check(T: pd.DataFrame) -> tuple[int, int]:
    """Each structure exit: the entry TF's bar closing at t_struct closed past the last swing fingerprint.zigzag had
    confirmed by then (a buy below the last trough). Returns (agree, checked)."""
    import plib  # noqa: PLC0415
    from fingerprint import raw, zigzag  # noqa: PLC0415

    from indicators import bars  # noqa: PLC0415

    m = plib.load_learning(start=pd.Timestamp("2025-09-01", tz="UTC"))  # ends before 2026-04-18; no exam row read
    ok = n = 0
    for tf, G in T[T.exit == "structure"].groupby("tf"):
        b = bars(m, "1min" if tf == "M1" else "5min")
        R = raw(b)
        pidx, pval, ptyp, pconf = zigzag(R["h"], R["lo"], R["atr"], 2.0)  # the developer's rule: 2 x ATR (fingerprint's own ZZ_K is 3)
        av = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
        for r in G.itertuples():
            k = int(np.searchsorted(av, int(r.t_struct), side="left"))
            if k >= len(av) or av[k] != int(r.t_struct):
                continue
            known = np.asarray(pconf) <= k
            kind = -1 if r.side > 0 else 1
            sel = np.nonzero(known & (np.asarray(ptyp) == kind))[0]
            if not len(sel):
                continue
            last = np.asarray(pval)[sel[np.argmax(np.asarray(pconf)[sel])]]
            n += 1
            ok += bool(R["c"][k] < last) if r.side > 0 else bool(R["c"][k] > last)
    return ok, n


def main() -> None:
    from m15_trades import PARTS  # noqa: PLC0415

    A = pd.read_parquet(DEV / "p2_trades.parquet")
    M = A[A.news_cost == 0.0]
    print("1. the metrics recomputed (variant, part):")
    for (v, p), G in M.groupby(["variant", "part"]):
        print(f"   {v} {p}: " + ", ".join(f"{k} {x:.3f}" if isinstance(x, float) else f"{k} {x}"
                                           for k, x in metrics(G, int(np.busday_count(*PARTS[p]))).items()))
    over = 0
    for (v, c), G in A.groupby(["variant", "news_cost"]):
        G = G.sort_values("entry_t")
        over += int((G.entry_t.to_numpy()[1:] < G.exit_t.to_numpy()[:-1]).sum())
    print(f"2. one position at a time: entries before the previous exit = {over}")
    rng = np.random.default_rng(19)
    tot = bad = 0
    for v, G in M.groupby("variant"):
        for r in G.iloc[rng.choice(len(G), min(20, len(G)), replace=False)].itertuples():
            b = rederive(r)
            tot += 1
            bad += bool(b)
            if b:
                print(f"   {v} {pd.Timestamp(int(r.entry_t), tz='UTC')}: {b}")
    print(f"3. trades re-derived from the raw ticks: {tot - bad} of {tot} agree")
    ok, n = structure_check(M)
    print(f"4. structure exits re-read with fingerprint.zigzag: {ok} of {n} agree")


if __name__ == "__main__":
    main()
