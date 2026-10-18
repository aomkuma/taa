"""Round 16 (docs/OWN_SETUP_ROUNDS.md): trading the range like the owner's trade 1 - R1 fade the edge, R2 the false break
back inside - on 2-4 hour M5 ranges 10-30 USD tall. Gold, real costs (agents/journal/jlib.py).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/range_trade.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path("research/2026-10-18-moments/agents/journal")))
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
import jlib  # noqa: E402

REF = 4100.0
HALVES = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01"], utc=True)


def _m1(sym: str) -> pd.DataFrame:
    m = gold.bars("M1")
    m = m[(m.index >= pd.Timestamp("2023-08-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-17", tz="UTC"))]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


jlib.m1_frame = _m1


def signals(P: jlib.Instr) -> pd.DataFrame:
    m = P.m
    m5 = m.resample("5min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    m5["atr"] = (m5.high - m5.low).rolling(14).mean()
    end5 = pd.DatetimeIndex(m5.index + pd.Timedelta(minutes=5))
    ot = P.ot
    o, h, lo, c = P.o, P.h, P.lo, P.c
    rows = []
    for W in (24, 48):
        hi = m5.high.rolling(W).max().to_numpy()
        lw = m5.low.rolling(W).min().to_numpy()
        H5, L5 = m5.high.to_numpy(), m5.low.to_numpy()
        for k in range(W + 14, len(m5) - 1):
            t0 = end5[k]  # the range is known at this M5 close; watch the next 5 M1 bars
            if t0 < pd.Timestamp("2023-11-01", tz="UTC") or t0.hour >= 20:
                continue
            top, bot = hi[k], lw[k]
            hgt = top - bot
            u = c[ot.searchsorted(t0) - 1] / REF if ot.searchsorted(t0) > 0 else 1.0
            if not (10 * u <= hgt <= 30 * u):
                continue
            tol = 0.15 * hgt
            tests_top = int((H5[k - W + 1 : k + 1] >= top - tol).sum())
            tests_bot = int((L5[k - W + 1 : k + 1] <= bot + tol).sum())
            i0 = ot.searchsorted(t0)
            if i0 + 70 >= len(o) or ot[i0] != t0:
                continue
            a5 = m5.atr.iloc[k]
            for j in range(i0, i0 + 5):
                for s, edge, tests in ((-1, top, tests_top), (1, bot, tests_bot)):
                    if tests < 3:  # the edge itself plus at least 2 earlier tests
                        continue
                    # R1: touch inside within 10 % of the edge, then the turn
                    near = (h[j] >= edge - 0.1 * hgt and h[j] <= edge) if s < 0 else (lo[j] <= edge + 0.1 * hgt and lo[j] >= edge)
                    if near and j + 1 < len(o):
                        turn = c[j + 1] < lo[j] if s < 0 else c[j + 1] > h[j]
                        if turn:
                            stop_px = edge + 0.2 * hgt if s < 0 else edge - 0.2 * hgt
                            rows.append(dict(rule="R1 edge fade", t=ot[j + 2], e=j + 2, side=s, stop_px=stop_px,
                                             mid=(top + bot) / 2, u=u, W=W))
                    # R2: beyond the edge, back inside within 5 bars by 0.1 of the height
                    beyond = h[j] > edge if s < 0 else lo[j] < edge
                    if beyond:
                        for q in range(j, min(j + 5, len(o) - 1)):
                            back = c[q] < edge - 0.1 * hgt if s < 0 else c[q] > edge + 0.1 * hgt
                            if back:
                                ext = h[j : q + 1].max() if s < 0 else lo[j : q + 1].min()
                                stop_px = ext + 0.25 * a5 if s < 0 else ext - 0.25 * a5
                                rows.append(dict(rule="R2 false break", t=ot[q + 1], e=q + 1, side=s, stop_px=stop_px,
                                                 mid=(top + bot) / 2, u=u, W=W))
                                break
    S = pd.DataFrame(rows).drop_duplicates(["rule", "t", "side"]).sort_values("t")
    return S


def run(S: pd.DataFrame, P: jlib.Instr) -> pd.DataFrame:
    out, free = [], pd.Timestamp(0, tz="UTC")
    for r in S.itertuples():
        if r.t < free:
            continue
        e, s = int(r.e), int(r.side)
        fill = float(P.fill(np.array([e]), np.array([s]))[0])
        sl = (fill - r.stop_px) * s
        if not (3 * r.u <= sl <= 10 * r.u):
            continue
        tp = min(5 * r.u, (r.mid - fill) * s) if (r.mid - fill) * s > 0 else 0
        if tp < 2.5 * r.u:  # no room to the middle
            continue
        ss = P.stop_slip_ny if r.t.hour >= 12 else P.stop_slip
        x = P.trade(e, s, tp, sl, None, 60, ss)
        x |= dict(t=r.t, rule=r.rule, side=s, sl=sl, tp=tp, R=x["pnl"] / (sl + ss))
        out.append(x)
        free = r.t + pd.Timedelta(minutes=int(x["mins"]))
    return pd.DataFrame(out)


def main() -> None:
    gold.below_normal_priority()
    P = jlib.Instr("XAUUSD")
    S = signals(P)
    S.to_parquet("data/research/own_range_signals.parquet")
    for part, a, b in (("DESIGN 2023-11 .. 2026-02", "2023-11-01", "2026-03-01"), ("WINDOW 2026-03 .. 10-16", "2026-03-01", "2026-10-17")):
        print(f"\n== {part}")
        for rule in ("R1 edge fade", "R2 false break"):
            x = S[(S.rule == rule) & (S.t >= pd.Timestamp(a, tz="UTC")) & (S.t < pd.Timestamp(b, tz="UTC"))]
            z = run(x, P)
            if not len(z):
                print(f"  {rule}: 0 trades")
                continue
            eq = z.pnl.cumsum()
            streak = mx = 0
            for v in z.pnl:
                streak = streak + 1 if v < 0 else 0
                mx = max(mx, streak)
            g = z.groupby(pd.cut(z.t, HALVES, right=False) if part.startswith("DESIGN") else z.t.dt.strftime("%m"), observed=True)
            per = " ".join(f"{v.R.mean():+.2f}({len(v)})" for _, v in g)
            los = z[z.exit == "stop"].kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
            print(f"  {rule}: {len(z)} trades, win {100 * (z.exit == 'win').mean():.0f}%, R {z.R.mean():+.3f}, {z.pnl.sum():+.1f} USD,"
                  f" worst {z.pnl.min():.2f}, streak {mx}, max DD {(eq.cummax() - eq).max():.1f}; losers 1/2/3 "
                  f"{100 * los['1']:.0f}/{100 * los['2']:.0f}/{100 * los['3']:.0f}% | {per}")
            z.to_parquet(f"data/research/own_range_{rule[:2]}_{'design' if part.startswith('DESIGN') else 'window'}.parquet")


if __name__ == "__main__":
    main()
