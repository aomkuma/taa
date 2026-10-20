"""NS-1: the 08:30-NY straddle on M1 bars (notes.md, written before computing, 2026-10-20 18:19 Thai).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/ns1.py calib   # P1 / P2 days vs the ticks
    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/ns1.py run     # 2021-09 .. 2025-10, read once
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # gold.py
ROOT = Path(__file__).resolve().parents[4]
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
TRIG, STOP = 2.0, 8.0


def _s(r) -> float:
    """The ask over the bid: the bar's spread (points) x 0.01 + 0.08 (row 45's old-year cost model)."""
    return r.spread * 0.01 + 0.08


def straddle_m1(b: pd.DataFrame, t0: pd.Timestamp, target_r: float | None = None) -> dict | None:
    """One day. b: M1 bid bars (UTC open-time index; open / high / low / close, spread in points). The NS-1 rule.
    Returns side, entry, exit_px, pnl, R, exit kind, both (the 08:30 bar reached both stops), or None."""
    ref, out_t = t0 - pd.Timedelta(minutes=1), t0 + pd.Timedelta(minutes=30)
    if ref not in b.index or t0 not in b.index or out_t not in b.index:
        return None
    rb = b.loc[ref]
    up, dn = rb.close + _s(rb) + TRIG, rb.close - TRIG
    x = b.loc[t0]
    hit_up, hit_dn = x.high + _s(x) >= up, x.low <= dn
    if not (hit_up or hit_dn):
        return None
    sides = [1] * int(hit_up) + [-1] * int(hit_dn)
    res = [_trade(b, t0, out_t, side, up, dn, target_r) for side in sides]
    worst = min(res, key=lambda r: r["pnl"])  # both reached: the worse side counts
    worst["both"] = len(sides) == 2
    return worst


def _trade(b: pd.DataFrame, t0: pd.Timestamp, out_t: pd.Timestamp, side: int, up: float, dn: float,
           target_r: float | None) -> dict:
    x = b.loc[t0]
    e = max(up, x.open + _s(x)) if side > 0 else min(dn, x.open)
    stop = e - side * STOP
    tgt = None if target_r is None else e + side * target_r * STOP
    for t, r in b.loc[t0:out_t - pd.Timedelta(minutes=1)].iterrows():
        s = _s(r)
        # the exit side's prices: a buy exits on the bid, a sell on the ask (bid + s)
        lo_px, hi_px, op = (r.low, r.high, r.open) if side > 0 else (r.low + s, r.high + s, r.open + s)
        adverse, fav = (lo_px, hi_px) if side > 0 else (hi_px, lo_px)
        if (adverse - stop) * side <= 0:
            px = stop if (op - stop) * side > 0 or t == t0 else op
            return dict(side=side, entry=e, exit_px=px, pnl=(px - e) * side, R=(px - e) * side / STOP, exit="stop")
        if tgt is not None and t != t0 and (fav - tgt) * side >= 0:
            return dict(side=side, entry=e, exit_px=tgt, pnl=(tgt - e) * side, R=(tgt - e) * side / STOP, exit="target")
    o = b.loc[out_t]
    px = o.open if side > 0 else o.open + _s(o)
    return dict(side=side, entry=e, exit_px=px, pnl=(px - e) * side, R=(px - e) * side / STOP, exit="time")


def m1(start: str, end: pd.Timestamp) -> pd.DataFrame:
    import gold  # noqa: PLC0415

    d = gold.bars("M1", before=end)
    d = d.loc[d.index >= pd.Timestamp(start, tz="UTC")]
    assert d.index.max() < end
    return d


def run_days(b: pd.DataFrame, a: str, z: str, target_r: float | None = None) -> pd.DataFrame:
    cal = pd.read_csv(ROOT / "app/news/us_releases.csv")
    rel = set(cal[(cal.time_et == "08:30") & (cal.date >= a) & (cal.date <= z)].date)
    rows = []
    for d in pd.bdate_range(a, z):
        t0 = pd.Timestamp(f"{d:%Y-%m-%d} 08:30").tz_localize("America/New_York").tz_convert("UTC")
        r = straddle_m1(b, t0, target_r)
        if r is not None:
            yr = d.year if d.month >= 10 else d.year - 1
            rows.append(dict(day=f"{d:%Y-%m-%d}", release=f"{d:%Y-%m-%d}" in rel, year=f"{yr}-{(yr + 1) % 100:02d}", **r))
    return pd.DataFrame(rows)


def main() -> None:
    mode = sys.argv[1]
    if mode == "calib":
        b = m1("2025-10-15", EXAM)
        T = run_days(b, "2025-10-20", "2026-04-17")
        A = pd.read_parquet(Path(__file__).parents[1] / "dev" / "plan1_every_learn_s0_x0.parquet")
        A = A[A.piece == "NY straddle"].copy()
        A["day"] = pd.to_datetime(A.t_dec, utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
        J = T.merge(A[["day", "side", "R"]], on="day", how="outer", suffixes=("_m1", "_tick"), indicator=True)
        print(f"calibration, P1 + P2 every weekday: M1 {len(T)} trades, ticks {len(A)}; {J._merge.value_counts().to_dict()}")
        both = J[J._merge == "both"]
        print(f"  same day {len(both)}: same side {np.mean(both.side_m1 == both.side_tick):.2f}; R m1 {both.R_m1.mean():+.3f} vs "
              f"ticks {both.R_tick.mean():+.3f}; |dR| median {np.median(np.abs(both.R_m1 - both.R_tick)):.3f}")
        for rel in (True, False):
            x = T[T.release == rel]
            print(f"  M1 {'release' if rel else 'other'} days: {len(x)} trades, R {x.R.mean():+.3f}")
    elif mode == "run":
        b = m1("2021-08-15", pd.Timestamp("2025-10-18", tz="UTC"))
        for lab, tr in (("hold 30 min", None), ("T1, +1 R target", 1.0)):
            T = run_days(b, "2021-09-01", "2025-10-17", tr)
            print(f"\n=== NS-1 {lab}: {len(T)} trades; both stops reached in the 08:30 bar: {int(T.both.sum())}")
            print(T.groupby(["release", "year"]).R.agg(["size", "mean", "sum"]).round(3).to_string())
            for rel in (True, False):
                x = T[T.release == rel]
                print(f"  pooled {'release' if rel else 'other'}: {len(x)} trades, R {x.R.mean():+.3f}, win "
                      f"{np.mean(x.pnl > 0):.2f}, exits {x.exit.value_counts().to_dict()}")
            T.to_parquet(Path(__file__).with_name(f"ns1_{'hold' if tr is None else 't1'}.parquet"))


if __name__ == "__main__":
    main()
