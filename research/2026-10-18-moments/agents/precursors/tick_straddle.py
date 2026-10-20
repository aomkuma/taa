"""The straddle on real ticks (notes.md "Let the market show the side": M1 bars hide the order inside the fill bar - the
bound from below and from above were -0.17 .. +0.05 R apart; the ticks 2025-10-01 .. 2026-10-14 settle it). At each M15
close in the active hours, c0 = the last bid: a buy stop at c0 + b (triggered by the ask, filled at that ask + 0.07) and
a sell stop at c0 - b (triggered by the bid, filled at that bid - 0.07); the first within 60 minutes is the trade, the
other cancelled; the target 10 USD (a limit: filled at its level), the stop s (the first tick at / beyond it: filled
at that tick, the gap included), out after 60 minutes at the last tick; one position at a time.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/tick_straddle.py [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[3]
TICKS = ROOT / "data/ticks/XAUUSD"
TARGET, SLIP, WAIT_MIN, HOLD_MIN = 10.0, 0.07, 60, 60
NS_MIN = 60 * 10**9
GRID = [(3.0, 5.0), (3.0, 10.0), (5.0, 5.0), (5.0, 10.0)]


def trade(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, c0: float, b: float, s: float,
          wait_ns: int = WAIT_MIN * NS_MIN, hold_ns: int = HOLD_MIN * NS_MIN) -> dict | None:
    """One straddle on ticks (t sorted, ns). None when neither stop triggers within the wait."""
    i0 = int(np.searchsorted(t, t0, side="left"))
    i1 = int(np.searchsorted(t, t0 + wait_ns, side="left"))
    up = np.nonzero(ask[i0:i1] >= c0 + b)[0]
    dn = np.nonzero(bid[i0:i1] <= c0 - b)[0]
    if not len(up) and not len(dn):
        return None
    if len(up) and (not len(dn) or up[0] < dn[0]):
        side, f = 1, i0 + int(up[0])
        entry = ask[f] + SLIP
    else:
        side, f = -1, i0 + int(dn[0])
        entry = bid[f] - SLIP
    j1 = int(np.searchsorted(t, t[f] + hold_ns, side="left"))
    seg = slice(f + 1, j1)
    if side > 0:
        hit_t = np.nonzero(bid[seg] >= entry + TARGET)[0]
        hit_s = np.nonzero(bid[seg] <= entry - s)[0]
    else:
        hit_t = np.nonzero(ask[seg] <= entry - TARGET)[0]
        hit_s = np.nonzero(ask[seg] >= entry + s)[0]
    kt = int(hit_t[0]) if len(hit_t) else None
    ks = int(hit_s[0]) if len(hit_s) else None
    if ks is not None and (kt is None or ks < kt):
        x = f + 1 + ks
        px = bid[x] if side > 0 else ask[x]
        return dict(side=side, exit="stop", pnl=(px - entry) * side, fill_t=int(t[f]), exit_t=int(t[x]), entry=entry, risk=s)
    if kt is not None:
        x = f + 1 + kt
        return dict(side=side, exit="win", pnl=TARGET, fill_t=int(t[f]), exit_t=int(t[x]), entry=entry, risk=s)
    x = max(j1 - 1, f)
    px = bid[x] if side > 0 else ask[x]
    return dict(side=side, exit="time", pnl=(px - entry) * side, fill_t=int(t[f]), exit_t=int(t[x]), entry=entry, risk=s)


def day_ticks(day: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    f = TICKS / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")


def span_ticks(day: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """A UTC day's ticks joined to the next day's, so a trade still open at midnight UTC is followed to its exit
    (one day's file alone cut it at 23:59:59 - audit2/test_simulators.py). A learning day is never joined to an exam
    day."""
    a = day_ticks(day)
    if a is None:
        return None
    nxt = pd.Timestamp(day) + pd.Timedelta(days=1)
    if pd.Timestamp(day) < EXAM_START <= nxt:
        return a
    b = day_ticks(nxt)
    if b is None:
        return a
    return np.concatenate([a[0], b[0]]), np.concatenate([a[1], b[1]]), np.concatenate([a[2], b[2]])


def run(X: pd.DataFrame, b: float, s: float) -> pd.DataFrame:
    """X: the moments (t, in time order). c0 = the last bid before t."""
    rows, busy = [], -1
    for day, D in X.groupby(pd.DatetimeIndex(X.t).normalize(), sort=True):
        tk = span_ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        for r in D.itertuples():
            t0 = pd.Timestamp(r.t).value
            if t0 <= busy:
                continue
            k = int(np.searchsorted(t, t0, side="left")) - 1
            if k < 0:
                continue
            x = trade(t, bid, ask, t0, float(bid[k]), b, s)
            if x is None:
                continue
            x["R"] = x["pnl"] / s
            rows.append(dict(t=r.t, **x))
            busy = x["exit_t"]
    return pd.DataFrame(rows)


def summary(T: pd.DataFrame, a: str, b: str) -> str:
    import wf  # noqa: PLC0415

    eq = T.pnl.cumsum()
    return (f"{len(T)} trades ({len(T) / np.busday_count(a, b):.2f} a weekday), win {(T.exit == 'win').mean():.3f}, R {T.R.mean():+.3f}, "
            f"USD {T.pnl.sum():+.1f} at 0.01 lot, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, worst {T.pnl.min():+.2f}, "
            f"longest losing streak {wf.longest_run(T.pnl.to_numpy() < 0)}, exits {T.exit.value_counts().to_dict()}")


def main() -> None:
    sys.path.insert(0, str(HERE.parents[0] / "journal"))
    import wf  # noqa: PLC0415
    from m15_trades import PARTS  # noqa: PLC0415

    X = pd.read_parquet(HERE / "burst_frame.parquet")
    act = ((X.abs_t_ny_open <= 60) | (X.abs_t_fix_pm <= 60) | (X.abs_t_us_data <= 60) | (X.abs_t_comex <= 60)).to_numpy()
    X = X[act].sort_values("t").reset_index(drop=True)
    res = {}
    for b, s in GRID:
        for p in ("P1", "P2"):
            T = run(X[X.part == p], b, s)
            res[(b, s, p)] = T
            print(f"ticks | b {b:g}, s {s:g} | {p}: {summary(T, *PARTS[p])}", flush=True)
    score = {(b, s): min(res[(b, s, "P1")].R.mean(), res[(b, s, "P2")].R.mean()) for b, s in GRID}
    good = {k: v for k, v in score.items() if v > 0}
    if not good:
        print("\nno (b, s) is positive in both learning parts on ticks: the exam is not read")
        return
    b, s = max(good, key=good.get)
    print(f"\nchosen on the learning parts: b {b:g}, s {s:g} (min R {good[(b, s)]:+.3f})")
    if sys.argv[1:] != ["exam"]:
        return
    T = run(X[X.part == "exam"], b, s)
    print(f"THE EXAM, once (ticks to 2026-10-14): {summary(T, '2026-04-20', '2026-10-15')}")
    T["cell"] = f"straddle b{b:g} s{s:g}"
    pd.set_option("display.width", 220)
    print(wf.weekly(T).to_string(index=False))
    T.to_parquet(HERE / "tick_straddle_exam.parquet")


if __name__ == "__main__":
    main()
