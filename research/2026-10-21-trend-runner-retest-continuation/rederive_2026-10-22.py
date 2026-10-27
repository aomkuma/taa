# ruff: noqa: E501, T201
"""Independent re-derivation of the smoke-run TR1 SPLIT trades from raw ticks (2026-10-22).

Written without importing tr1 or candidate code: its own M1 ATR, its own M5/M15 bars and pivots, its own tick loop.
For each trade it also shows the ORIGINAL 3-year walk-forward approximation of the same entry (M1 open + the M1
``spread`` column, walkforward.m1_fill) to make bug B6 visible.

    .venv\\Scripts\\python research\\2026-10-21-trend-runner-retest-continuation\\rederive_2026-10-22.py JOURNAL.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
M1 = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
TICKS = REPO / "data" / "ticks" / "XAUUSD"
EXAM = (pd.Timestamp("2026-04-18", tz="UTC"), pd.Timestamp("2026-10-18", tz="UTC"))


def read_m1(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    assert end <= EXAM[0] or start >= EXAM[1], "exam"  # noqa: S101
    f = pd.read_parquet(
        M1,
        columns=["open_time", "open", "high", "low", "close", "spread"],
        filters=[("open_time", ">=", start.to_pydatetime()), ("open_time", "<", end.to_pydatetime())],
    )
    return f.drop_duplicates("open_time").sort_values("open_time").set_index("open_time")


def read_ticks(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    parts = []
    for day in pd.date_range(start.normalize(), end.normalize(), freq="D"):
        assert not (EXAM[0] <= day < EXAM[1]), "exam"  # noqa: S101
        path = TICKS / f"{day.date()}.parquet"
        if path.exists():
            parts.append(pd.read_parquet(path, columns=["time_utc", "bid", "ask"]))
    t = pd.concat(parts, ignore_index=True).sort_values("time_utc", kind="stable")
    return t.loc[(t.time_utc >= start) & (t.time_utc <= end)].reset_index(drop=True)


def my_atr(h, lo, c, n=14):
    tr = np.empty(len(c))
    tr[0] = np.nan
    for i in range(1, len(c)):
        tr[i] = max(h[i], c[i - 1]) - min(lo[i], c[i - 1])
    out = np.full(len(c), np.nan)
    for i in range(n, len(c)):
        out[i] = tr[i - n + 1 : i + 1].mean()
    return out


def my_bars(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    key = m1.index.floor(f"{minutes}min")
    g = m1.groupby(key)
    b = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    b["end"] = b.index + pd.Timedelta(minutes=minutes)
    b["atr"] = my_atr(b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy())
    return b


def my_events(b: pd.DataFrame, side: int, entry_time, spread, tf):
    ev = []
    lo, hi = b.low.to_numpy(), b.high.to_numpy()
    for i in range(1, len(b) - 1):
        if b.index[i] < entry_time:
            continue
        piv = lo[i] if side > 0 else hi[i]
        ok = (
            (lo[i] <= lo[i - 1] and lo[i] <= lo[i + 1])
            if side > 0
            else (hi[i] >= hi[i - 1] and hi[i] >= hi[i + 1])
        )
        a = b.atr.iloc[i + 1]
        if ok and np.isfinite(a) and a > 0:
            buf = max(spread, 0.1 * a)
            ev.append((b.end.iloc[i + 1], tf, piv - buf if side > 0 else piv + buf))
    return sorted(ev, key=lambda e: (e[0], e[1]))


def my_split(ticks, side, entry, stop0, entry_time, events):
    risk = (entry - stop0) * side
    stop, partial, grad, grad_t = stop0, False, False, None
    end = entry_time + pd.Timedelta(hours=8)
    mark = ticks.bid.to_numpy() if side > 0 else ticks.ask.to_numpy()
    k = 0

    def usable(e):
        if e[0] > end:
            return False
        return e[1] == "M5" if not grad else (e[1] == "M15" and e[0] >= grad_t)

    def tighten(s, v):
        return max(s, v) if side > 0 else min(s, v)

    for t, p in zip(ticks.time_utc, mark, strict=True):
        while k < len(events) and events[k][0] < t:
            if usable(events[k]):
                stop = tighten(stop, events[k][2])
            k += 1
        same = []
        while k < len(events) and events[k][0] == t:
            same.append(events[k])
            k += 1
        hit = p <= stop if side > 0 else p >= stop
        if not hit:
            if not partial and (p - entry) * side >= risk:
                partial = True
            if not grad and (p - entry) * side >= 3 * risk:
                grad, grad_t = True, t
            for e in same:
                if usable(e):
                    stop = tighten(stop, e[2])
            hit = p <= stop if side > 0 else p >= stop
        if hit or t >= end:
            raw = (p - entry) * side / risk
            return t, p, ("STOP" if hit else "TIME"), (1 / 3 + 2 / 3 * raw) if partial else raw
    return None, np.nan, "CENSORED", np.nan


def main() -> None:
    journal = pd.read_csv(sys.argv[1])
    trades = journal.loc[journal.variant.str.startswith("TR1")]
    lo = pd.Timestamp(trades.entry_time_utc.min()) - pd.Timedelta(days=3)
    hi = pd.Timestamp(trades.entry_time_utc.max()) + pd.Timedelta(days=2)
    m1 = read_m1(lo, hi)
    m1_atr = pd.Series(my_atr(m1.high.to_numpy(), m1.low.to_numpy(), m1.close.to_numpy()), index=m1.index)
    m5, m15 = my_bars(m1, 5), my_bars(m1, 15)
    rows = []
    for r in trades.itertuples(index=False):
        side = 1 if r.side == "BUY" else -1
        decision = pd.Timestamp(r.decision_time_utc)
        tk = read_ticks(decision, decision + pd.Timedelta(hours=8, minutes=10))
        first = tk.iloc[0]
        entry_t, entry = first.time_utc, (first.ask if side > 0 else first.bid)
        spread = first.ask - first.bid
        pivot_t = pd.Timestamp(r.pivot_time_utc)
        pivot = m1.loc[pivot_t, "low" if side > 0 else "high"]
        atr = m1_atr.loc[
            decision - pd.Timedelta(minutes=1)
        ]  # the decision bar (opens 1 min before its close)
        stop = pivot - side * max(spread, 0.1 * atr)
        events = my_events(m5, side, entry_t, spread, "M5") + my_events(m15, side, entry_t, spread, "M15")
        events.sort(key=lambda e: (e[0], e[1]))
        path = tk.loc[tk.time_utc >= entry_t].reset_index(drop=True)
        xt, xp, why, rr = my_split(path, side, entry, stop, entry_t, events)
        bar = m1.loc[m1.index >= decision].iloc[
            0
        ]  # ORIGINAL walk-forward entry: next M1 open + M1 spread column
        orig_entry = bar.open + (bar.spread * 0.01 if side > 0 else 0.0)
        rows.append(
            {
                "trade": r.trade_id,
                "side": r.side,
                "entry_code": r.entry,
                "entry_ticks": entry,
                "entry_M1approx": round(orig_entry, 2),
                "stop_code": round(r.stop, 3),
                "stop_ticks": round(stop, 3),
                "exit_code": r.exit,
                "exit_ticks": xp,
                "exit_time_same": pd.Timestamp(r.exit_time_utc) == xt,
                "R_code": round(r.r, 4),
                "R_ticks": round(rr, 4),
                "reason_ticks": why,
            }
        )
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out.to_string(index=False))
    same = (
        np.isclose(out.entry_code, out.entry_ticks)
        & np.isclose(out.stop_code, out.stop_ticks, atol=1e-3)
        & np.isclose(out.exit_code, out.exit_ticks)
        & out.exit_time_same
        & np.isclose(out.R_code, out.R_ticks, atol=1e-4)
    )
    print(f"\n{int(same.sum())} of {len(out)} trades identical (entry, stop, exit price and time, R)")
    diff = (out.entry_M1approx - out.entry_ticks).abs()
    print(
        f"M1-approximation entry differs from the tick fill on {int((diff > 1e-9).sum())} of {len(out)}; "
        f"mean |diff| {diff.mean():.3f} USD, max {diff.max():.3f} USD"
    )


if __name__ == "__main__":
    main()
