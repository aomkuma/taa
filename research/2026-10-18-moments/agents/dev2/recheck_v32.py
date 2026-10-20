"""R10: 20 trades per setting re-derived from the raw tick files by a plain loop (a second, independent simulator:
one tick at a time, written apart from tsim32's vectorised one), compared on the fill, the exit kind, the exit time and
the pnl. The 20 are rule-picked: the setting's inside-window trades in time order, every k-th (k = n // 20).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/recheck_v32.py > research/2026-10-18-moments/agents/dev2/out_recheck_v32.txt
"""

from __future__ import annotations

import bisect
import functools
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
MIN = 60_000_000_000


@functools.lru_cache(maxsize=6)
def raw(day: pd.Timestamp):
    assert day < EXAM
    f = ROOT / "data" / "ticks" / "XAUUSD" / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return ()
    x = pd.read_parquet(f)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    return tuple(sorted(zip(t.tolist(), x.bid.tolist(), x.ask.tolist()), key=lambda r: r[0]))


def plain(spec: dict, how: str) -> dict | None:
    t_in = int(spec["t_dec"])
    d = pd.Timestamp(t_in, tz="UTC").normalize()
    rows = raw(d) + (raw(d + pd.Timedelta(days=1)) if d + pd.Timedelta(days=1) < EXAM else ())
    i = bisect.bisect_left(rows, t_in, key=lambda r: r[0])  # the first tick at / after t_in
    if i >= len(rows) or rows[i][0] - t_in > 5 * MIN:
        return None
    side = int(spec["side"])
    t0, b0, a0 = rows[i]
    fill = a0 if side > 0 else b0
    if how == "e3_mirror" and spec["kind3"] == "ii":
        same = b0 if side > 0 else a0
        stop = fill - side * abs(same - spec["mirror_of"])
    elif how == "e3_mirror":
        stop = fill - side * spec["mirror_dist"]
    elif how == "e3_ext":
        stop = spec["stop_ext"]
    else:
        stop = spec["stop"]
    risk = side * (fill - stop)
    if risk <= 0:
        return None
    if how in ("e3_ext", "e3_mirror"):
        tgt = fill + side * risk
    elif how == "base":
        tgt = fill + side * 2 * risk
    else:
        k = 1.0 if how == "b" else 2.0
        best = None
        for c in spec["cands"]:
            dist = side * (c - fill)
            if dist >= k * risk - 1e-9 and (best is None or dist < best):
                best = dist
        tgt = fill + side * best if best is not None else (fill + side * 2 * risk if how == "b" else None)
    trail = sorted(spec["trail"]) if how == "a" else []
    cur = stop
    prev_t, prev_mk = t0, (b0 if side > 0 else a0)
    for j in range(i + 1, len(rows)):
        t, b, a = rows[j]
        mk = b if side > 0 else a
        if t - prev_t > 30 * MIN:
            return dict(exit="break", exit_t=prev_t, pnl=side * (prev_mk - fill))
        if t >= spec["t_out"]:
            return dict(exit="time", exit_t=t, pnl=side * (mk - fill))
        for ts, lvl in trail:
            if ts <= t:
                cur = max(cur, lvl) if side > 0 else min(cur, lvl)
        if (side > 0 and mk <= cur + 1e-9) or (side < 0 and mk >= cur - 1e-9):
            return dict(exit="stop", exit_t=t, pnl=side * (mk - fill))
        if tgt is not None and ((side > 0 and mk >= tgt - 1e-9) or (side < 0 and mk <= tgt + 1e-9)):
            return dict(exit="target", exit_t=t, pnl=side * (tgt - fill))
        prev_t, prev_mk = t, mk
    return dict(exit="end", exit_t=prev_t, pnl=side * (prev_mk - fill))


def main() -> None:
    with open(HERE / "v32_specs.pkl", "rb") as f:
        sp = pickle.load(f)["specs"]
    T = pd.read_parquet(HERE / "v32_trades.parquet")
    T = T[T.scope == "win"]
    tot = agree = 0
    for (et, setting), g in T.groupby(["etype", "setting"], sort=True):
        g = g.sort_values("t_fill")
        k = max(len(g) // 20, 1)
        pick = g.iloc[::k].head(20)
        ok = 0
        for r in pick.itertuples(index=False):
            S = sp[r.key]
            row = S[(S.t_dec == r.t_dec) & (S.side == r.side)].iloc[0].to_dict()
            p = plain(row, r.how)
            same = p is not None and p["exit"] == r.exit and p["exit_t"] == r.exit_t and abs(p["pnl"] - r.pnl) < 1e-6
            ok += same
            if not same:
                print(f"  DIFF {et} {setting} {pd.Timestamp(r.t_dec, tz='UTC')}: tsim32 {r.exit} {r.pnl:+.2f} | plain {p}")
        tot += len(pick)
        agree += ok
        print(f"{et} {setting:28s}: {ok} of {len(pick)} re-derived trades agree", flush=True)
    print(f"\nALL: {agree} of {tot} agree")


if __name__ == "__main__":
    main()
