"""S1's funnel on three years of gold M1 (owner, 2026-10-17: S1 first; its gap is the trade count, 76 a year).

The pool is the event S1 was built from (``research/2026-10-11-pre-run/m1_scalp_study.py``): the first M1 close
beyond the previous ``n`` bars' high/low *against* an H1 + M15 trend that agree (market-map states, default
parameters, the last bar closed before the event), faded: traded with the trend. S1's plan on it: stop 1 A,
target 2 A (A = the mean true range of the last 60 M1 bars; S1's 2-A plan inverted), a 60-bar time stop; entry at
the next bar's open, a BUY at the ask (the plan as the engine builds it: the breakout's plan, stop 2 A plus the
spread, target 0.5 R, inverted by the fade: stop A + 1.5 spreads, target 2 A from the decision close); stops and targets on bar highs/lows, a SELL's on the ask (bid + spread),
both in one bar = the stop; 7 points of slippage on entry and exit (the account's spread above the history's).

Each stage adds one of S1's filters, so the table shows where the trades go and what each filter is worth in
every year (C 2023-10 .. 2024-09, A 2024-10 .. 2025-09, B 2025-10 .. 2026-09 in sample). This is a harness, not
the engine (its triggers are the Donchian and session-range detectors); a lever found here is coded and run in
the engine's backtest before any conclusion.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/s1_funnel.py
"""

from __future__ import annotations

import ctypes
import json
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.indicators.market_map import MapParams, state_frame  # noqa: E402

H = "data/history/FBS-Demo/XAUUSD"
NY = ZoneInfo("America/New_York")
YEARS = {
    "C": (pd.Timestamp("2023-10-01", tz="UTC"), pd.Timestamp("2024-10-01", tz="UTC")),
    "A": (pd.Timestamp("2024-10-01", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC")),
    "B": (pd.Timestamp("2025-10-01", tz="UTC"), pd.Timestamp("2026-10-01", tz="UTC")),
}
SLIP = 7.0
STOP_A, TARGET_A, TIME_STOP = 1.0, 2.0, 60


def below_normal_priority() -> None:
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def load(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(f"{H}/{tf}.parquet").sort_values("close_time")
    d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    return d


def events(m1: pd.DataFrame, n: int) -> pd.DataFrame:
    """Counter-trend breaks of the previous *n* bars (the trade's side = the trend's)."""
    states = {tf: state_frame(load(tf), MapParams())["state"] for tf in ("H1", "M15")}
    c = m1["close"]
    hh, ll = m1["high"].rolling(n).max().shift(1), m1["low"].rolling(n).min().shift(1)
    up = (c > hh) & (c.shift(1) <= hh.shift(1))
    dn = (c < ll) & (c.shift(1) >= ll.shift(1))
    idx = np.flatnonzero((up | dn).to_numpy())
    t = m1.index[idx]
    trend = {}
    for tf, s in states.items():
        j = s.index.searchsorted(t, side="right") - 1
        trend[tf] = np.where(j >= 0, s.to_numpy()[np.clip(j, 0, None)], "UNKNOWN")
    agree = (trend["H1"] == trend["M15"]) & np.isin(trend["H1"], ["UP", "DOWN"])
    side = np.where(trend["H1"] == "UP", 1, -1)
    brk = np.where(up.to_numpy()[idx], 1, -1)
    keep = agree & (brk != side)  # a break against the trend, faded
    return pd.DataFrame({"i": idx[keep], "side": side[keep], "t": t[keep]})


def outcomes(
    m1: pd.DataFrame,
    ev: pd.DataFrame,
    point: float,
    k: float = 0.0,
    scale_time: bool = False,
    spreads_only: bool = False,
    time_stop: int = TIME_STOP,
) -> pd.DataFrame:
    """*k* > 0: the plan's scale is A' = max(A, k x the round-trip cost (spread + 2 slippages)), so the cost is
    at most about 1/k of the stop (the owner, 2026-10-17: the spread must not eat the stop); *scale_time*: the
    time stop grows with A'/A (capped at 4 x)."""
    o, h, lo, c, sp = (m1[col].to_numpy(dtype=float) for col in ("open", "high", "low", "close", "spread"))
    sp = sp * point
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - pc), np.abs(lo - pc)], axis=1)
    a = pd.Series(tr).rolling(60).mean().to_numpy()
    slip = SLIP * point
    rows = []
    for i, side, t in ev.itertuples(index=False):
        if i + 1 + 4 * max(TIME_STOP, time_stop) >= len(o) or not np.isfinite(a[i]):
            continue
        cost = sp[i] if spreads_only else sp[i] + 2 * slip  # the engine's strategy sees the spread only
        scale = max(a[i], k * cost) if k > 0 else a[i]
        hold = int(time_stop * min(4.0, scale / a[i])) if scale_time else time_stop
        e = i + 1
        entry = o[e] + (sp[e] + slip if side > 0 else -slip)
        # the engine's fade of the breakout plan (stop 2 A + spread, target 0.5 R) from the decision close
        # a fade SELL of a BUY break: stop at the plan's target c + A + 1.5 sp, target at its stop c - 2 A;
        # a fade BUY of a SELL break: stop c - A - 0.5 sp, target c + 2 A + sp
        stop = c[i] - side * STOP_A * scale + (1.5 * sp[i] if side < 0 else -0.5 * sp[i])
        tp = c[i] + side * TARGET_A * scale + (sp[i] if side > 0 else 0.0)
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        r, x = None, e + hold - 1
        for j in range(e, e + hold):
            adverse = lo[j] if side > 0 else h[j] + sp[j]
            favour = h[j] if side > 0 else lo[j] + sp[j]
            if (adverse - stop) * side <= 0:
                r, x = ((stop - side * slip) - entry) * side / risk, j
                break
            if (favour - tp) * side >= 0:
                r, x = (tp - entry) * side / risk, j
                break
        if r is None:
            exit_px = c[x] - (slip if side > 0 else -(sp[x] + slip))
            r = (exit_px - entry) * side / risk
        rows.append((i, side, t, r, x, sp[i] / a[i]))
    return pd.DataFrame(rows, columns=["i", "side", "t", "r", "x", "spread_a"])


def one_at_a_time(d: pd.DataFrame, cooldown: int = 0) -> pd.DataFrame:
    keep, free, last = [], -1, -(10**9)
    for i, x in zip(d["i"].to_numpy(), d["x"].to_numpy(), strict=True):
        ok = i > free and i >= last + cooldown
        keep.append(ok)
        if ok:
            free, last = x, i
    return d[np.array(keep, dtype=bool)]


def report(name: str, d: pd.DataFrame) -> str:
    cells = []
    for y, (a, b) in YEARS.items():
        r = d.loc[(d.t >= a) & (d.t < b), "r"]
        cells.append(f"{y} {len(r):4} {r.mean() if len(r) else float('nan'):+.3f}")
    return f"  {name:46} " + "   ".join(cells)


def main() -> None:
    below_normal_priority()
    point = json.load(open(f"{H}/spec.json"))["spec"]["point"]
    m1 = load("M1")
    for n in (20,):
        d = outcomes(m1, events(m1, n), point)
        ny = d["t"].dt.tz_convert(NY)
        nym = ny.dt.hour * 60 + ny.dt.minute
        utc = d["t"].dt.hour + d["t"].dt.minute / 60
        wd = d["t"].dt.weekday
        session = (wd < 5) & (utc >= 7) & (utc < 20)
        friday = ~((wd == 4) & (utc >= 16))
        skip = ~((nym >= 8 * 60) & (nym < 12 * 60))
        print(f"\nDonchian {n}: per year, trades and R per trade (stop {STOP_A:g} A, target {TARGET_A:g} A, "
              f"time stop {TIME_STOP})")
        s0 = d[session]
        print(report("0 counter breaks, weekdays 07-20 UTC", s0))
        s1 = s0[friday[session]]
        print(report("1 + Friday cut-off 16:00 UTC", s1))
        s2 = s1[skip[s1.index]]
        print(report("2 + no entries 08-12 New York", s2))
        # S1's own spread rule: spread <= 0.15 x the plan's stop (2 A + spread before the fade inverts it)
        s3 = s2[s2.spread_a <= 0.3 / 0.85]
        print(report("3 + spread <= 0.15 of the plan's stop", s3))
        print(report("4 + one position at a time", one_at_a_time(s3)))
        for cd in (15, 30, 60):
            print(report(f"5 + cooldown {cd} bars after an entry", one_at_a_time(s3, cd)))
        print("  levers on the stage-3 pool, one at a time, cooldown 60 unless named:")
        for cap in (0.15, 0.2, 0.25):
            print(report(f"  spread <= {cap:g} A", one_at_a_time(s2[s2.spread_a <= cap], 60)))
        s1c = s1[s1.spread_a <= 0.3 / 0.85]
        print(report("  without the New York skip", one_at_a_time(s1c, 60)))
        print(report("  without the New York skip, cooldown 15", one_at_a_time(s1c, 15)))
        print()
        print("  the stop scaled so the cost stays small (A' = max(A, k x round-trip cost)), no spread gate,")
        print("  stage 2 pool, one position at a time, cooldown 60:")
        ev2 = events(m1, n)
        for kk, st in ((3, False), (4, False), (5, False), (6, False), (8, False), (5, True), (8, True)):
            v = outcomes(m1, ev2, point, kk, st)
            v = v[v.i.isin(s2.i)]
            label = f"  k {kk}" + (", time stop x A'/A" if st else "")
            print(report(label, one_at_a_time(v, 60)))
        d.assign(ny_min=nym, session=session, friday=friday, skip=skip).to_parquet(
            f"data/research/s1_funnel_n{n}.parquet"
        )


if __name__ == "__main__":
    main()
